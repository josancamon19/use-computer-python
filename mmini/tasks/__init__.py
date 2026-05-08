"""Retrieve and export collected tasks from the gateway."""

from __future__ import annotations

import builtins
import json
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from mmini.ax_transpile import patch_curl_timeouts, transpile

logger = logging.getLogger(__name__)

_TEMPLATES = Path(__file__).parent / "templates"


def _tpl(name: str) -> str:
    return (_TEMPLATES / name).read_text(encoding="utf-8")


def _render(text: str, **kwargs: str) -> str:
    out = text
    for k, v in kwargs.items():
        out = out.replace("{{" + k + "}}", v)
    return out


@dataclass
class TaskSummary:
    """Lightweight task info from the list endpoint."""

    id: str
    task_name: str
    instruction: str
    category: str
    platform: str
    step_count: int
    has_grader: bool
    created_at: str
    completed_at: str | None = None

    @property
    def runnable(self) -> bool:
        """A task is runnable only if it has a grader."""
        return self.has_grader


@dataclass
class Task:
    """Full task detail from the gateway."""

    id: str
    sandbox_id: str
    platform: str
    phase: str
    task_name: str
    instruction: str
    category: str
    setup_commands: list
    steps: list
    app_state: dict
    accessibility_tree: dict | None = None
    grader: str = ""
    setup_actions: list = field(default_factory=list)

    @property
    def runnable(self) -> bool:
        return self.grader != ""


class TasksClient:
    """Client for the gateway's task collection endpoints."""

    def __init__(self, http: httpx.Client):
        self._http = http

    def list(self, limit: int = 50, offset: int = 0) -> builtins.list[TaskSummary]:
        resp = self._http.get("/admin/tasks", params={"limit": limit, "offset": offset})
        resp.raise_for_status()
        return [
            TaskSummary(
                id=t["id"],
                task_name=t.get("task_name", ""),
                instruction=t.get("instruction", ""),
                category=t.get("category", ""),
                platform=t.get("platform", "macos"),
                step_count=t.get("step_count", 0),
                has_grader=t.get("has_grader", False),
                created_at=t.get("created_at", ""),
                completed_at=t.get("completed_at"),
            )
            for t in resp.json()
        ]

    def get(self, task_id: str) -> Task:
        resp = self._http.get(f"/admin/tasks/{task_id}")
        resp.raise_for_status()
        d = resp.json()
        meta = d.get("task_meta", {})
        return Task(
            id=d["id"],
            sandbox_id=d.get("sandbox_id", ""),
            platform=d.get("platform", meta.get("platform", "macos")),
            phase=d.get("phase", ""),
            task_name=meta.get("name", ""),
            instruction=meta.get("instruction", ""),
            category=meta.get("category", ""),
            setup_commands=d.get("setup_commands", []),
            steps=d.get("steps", []),
            app_state=d.get("app_state", {}),
            accessibility_tree=d.get("accessibility_tree"),
            grader=d.get("grader", ""),
            setup_actions=d.get("setup_actions") or [],
        )

    def export_harbor(
        self,
        task_id: str,
        output_dir: str | Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        task = self.get(task_id)

        # Fetch each persisted upload via /admin/tasks/{id}/files/{name}.
        # Returns None on 404 — task_to_harbor logs + skips.
        def fetch_file(local_name: str) -> bytes | None:
            r = self._http.get(f"/admin/tasks/{task_id}/files/{local_name}")
            if r.status_code != 200:
                return None
            return r.content

        return task_to_harbor(task, Path(output_dir), overwrite=overwrite, fetch_file=fetch_file)


def _build_test_sh(task: Task) -> str:
    """iOS = JSON checker DSL POSTed to /grade. macOS = bash with perl-alarm wrap."""
    if task.platform == "ios":
        return _build_test_sh_ios(task)
    return _build_test_sh_macos(task)


def _build_test_sh_ios(task: Task) -> str:
    grader = (task.grader or "").strip()
    if not grader.startswith("["):
        return _tpl("test_ios_nograder.sh")
    specs = grader.replace("'", "'\\''")
    return _render(_tpl("test_ios.sh"), SPECS=specs)


def _build_test_sh_macos(task: Task) -> str:
    grader = (task.grader or "").strip()
    if not grader:
        return _tpl("test_macos_nograder.sh")
    check_tpl = _tpl("test_macos_check.sh")
    checks = _render(check_tpl, N="1", CMD=grader.replace("'", "'\\''"))
    out = _render(_tpl("test_macos.sh"), CHECKS=checks)
    out, _ = transpile(out)
    out, _ = patch_curl_timeouts(out)
    return out


def _build_pre_command_sh(task: Task) -> str | None:
    # `defaults delete` fails on fresh VMs (key never set). Tasks recording such
    # commands likely rely on the cleanup; skip the whole task instead of
    # silently shipping a broken pre_command.
    for c in task.setup_commands:
        if "defaults delete" in c:
            raise ValueError(
                f"task setup_commands contain `defaults delete` — skipping export: {c!r}"
            )
    if not task.setup_commands:
        return None
    return _render(_tpl("pre_command.sh"), COMMANDS="\n".join(task.setup_commands))


def task_to_harbor(
    task: Task,
    output_root: Path,
    *,
    overwrite: bool = False,
    fetch_file=None,
) -> Path:
    """Convert a collected Task into a Harbor task directory.

    Layout:
        {category}__{task_id}/
            instruction.md
            task.toml
            environment/
            tests/
                test.sh
                setup/
                    pre_command.sh
                    files/
                        manifest.json
                        <local_name>...

    `fetch_file(local_name) -> bytes | None` fetches collect-time file uploads
    from the gateway so the runner's setup.py can re-upload them. Pass None to
    skip — the resulting harbor dir will have no file uploads.
    """
    output_root = Path(output_root)
    category = task.category or "uncategorized"
    short_id = task.id.replace("col-", "")[:36]
    task_dir = output_root / f"{category}__{short_id}"

    if task_dir.exists() and not overwrite:
        raise FileExistsError(f"Already exists: {task_dir}")

    # Build pre_command early so we fail before creating any dirs if all setup
    # commands got stripped (raises ValueError).
    pre_cmd = _build_pre_command_sh(task)

    if task_dir.exists():
        shutil.rmtree(task_dir)

    task_dir.mkdir(parents=True)
    (task_dir / "environment").mkdir()
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()

    # instruction.md
    (task_dir / "instruction.md").write_text(task.instruction + "\n", encoding="utf-8")

    # task.toml
    tags = ["collected", "gui", task.platform]
    if category:
        tags.append(category)
    toml = _render(
        _tpl("task.toml"),
        TAGS=json.dumps(tags),
        PLATFORM=task.platform,
        RUNNABLE="true" if task.runnable else "false",
    )
    (task_dir / "task.toml").write_text(toml, encoding="utf-8")

    # actions.json — flat {steps: [{function, args}, ...]} for the debug agent's
    # replay path. Pulls the first tool_call from each ATIF step; non-tool steps
    # (text-only assistant messages) drop out.
    actions = []
    for step in task.steps or []:
        tcs = step.get("tool_calls") if isinstance(step, dict) else None
        if not tcs:
            continue
        tc = tcs[0]
        actions.append({"function": tc.get("function"), "args": tc.get("args") or {}})
    (task_dir / "actions.json").write_text(
        json.dumps({"steps": actions}, indent=2) + "\n", encoding="utf-8"
    )

    # tests/setup/pre_command.sh — skip directory entirely if no setup commands
    setup_dir = tests_dir / "setup"
    if pre_cmd:
        setup_dir.mkdir(exist_ok=True)
        pre_cmd_path = setup_dir / "pre_command.sh"
        pre_cmd_path.write_text(pre_cmd, encoding="utf-8")
        pre_cmd_path.chmod(0o755)

    # tests/setup/files/<local_name> + manifest.json — files captured at
    # collect time. The runner's setup.py reads manifest.json and uploads
    # each entry to its remote_path before pre_command runs.
    upload_actions = [
        sa
        for sa in (task.setup_actions or [])
        if (sa.get("action_type") if isinstance(sa, dict) else None) == "upload_file"
    ]
    if upload_actions:
        if fetch_file is None:
            logger.warning(
                "task has %d upload_file actions but no fetch_file callback — "
                "skipping (runner won't have collected files)",
                len(upload_actions),
            )
        else:
            files_dir = setup_dir / "files"
            files_dir.mkdir(parents=True, exist_ok=True)
            manifest = []
            for sa in upload_actions:
                params = sa.get("params") or {}
                remote_path = params.get("remote_path")
                local_name = params.get("local_name")
                if not remote_path or not local_name:
                    continue
                data = fetch_file(local_name)
                if data is None:
                    logger.warning("collected file missing on gateway: %s", local_name)
                    continue
                (files_dir / local_name).write_bytes(data)
                manifest.append({"remote_path": remote_path, "local_name": local_name})
                logger.info("exported file %s → %s (%dB)", local_name, remote_path, len(data))
            if manifest:
                (files_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2) + "\n",
                    encoding="utf-8",
                )

    # tests/test.sh
    test_path = tests_dir / "test.sh"
    test_path.write_text(_build_test_sh(task), encoding="utf-8")
    test_path.chmod(0o755)

    return task_dir

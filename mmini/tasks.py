"""Retrieve and export collected tasks from the gateway."""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path

import httpx


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
    grading_candidates: list | None = None
    grader: str = ""

    @property
    def runnable(self) -> bool:
        return self.grader != ""


class TasksClient:
    """Client for the gateway's task collection endpoints."""

    def __init__(self, http: httpx.Client):
        self._http = http

    def list(self, limit: int = 50, offset: int = 0) -> list[TaskSummary]:
        """List collected tasks. Returns lightweight summaries."""
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
        """Get full task details."""
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
            grading_candidates=d.get("grading_candidates"),
            grader=d.get("grader", ""),
        )

    def export_harbor(
        self,
        task_id: str,
        output_dir: str | Path,
        *,
        overwrite: bool = False,
    ) -> Path:
        """Export a single task as a Harbor task directory.

        Returns the path to the generated task directory.
        Raises ValueError if the task has no grader (not runnable).
        """
        task = self.get(task_id)
        return task_to_harbor(task, Path(output_dir), overwrite=overwrite)


def _build_test_sh(task: Task) -> str:
    """Generate test.sh. iOS = JSON checker DSL POSTed to /grade.
    macOS = bash, perl-alarm wrap + temp-file capture (matches macosworld)."""
    if task.platform == "ios":
        return _build_test_sh_ios(task)
    return _build_test_sh_macos(task)


def _build_test_sh_ios(task: Task) -> str:
    grader = (task.grader or "").strip()
    lines = [
        "#!/bin/bash",
        "# iOS test.sh — runs on the harbor host, evaluator runs server-side at /grade.",
        'REWARD="${HARBOR_REWARD_FILE:-./reward.txt}"',
        'GRADER_LOG="${HARBOR_GRADER_LOG:-./grader.log}"',
        ': "${GATEWAY_URL:?GATEWAY_URL is required}"',
        ': "${SANDBOX_ID:?SANDBOX_ID is required}"',
        ': "${MMINI_API_KEY:?MMINI_API_KEY is required}"',
        "",
    ]
    if not grader.startswith("["):
        lines += [
            "# iOS graders must be a JSON checker DSL (array of {kind, ...} specs).",
            'echo "0" > "$REWARD"',
            'echo "Score: 0 — iOS task has no DSL grader" >> "$GRADER_LOG"',
            'echo "Score: 0 (no DSL grader)"',
        ]
        return "\n".join(lines) + "\n"

    specs = grader.replace("'", "'\\''")
    lines += [
        f"SPECS='{specs}'",
        'PAYLOAD=$(printf \'{"specs": %s}\' "$SPECS")',
        ('RESP=$(curl -sS -H "Authorization: Bearer $MMINI_API_KEY" '
         '-H "Content-Type: application/json" -X POST '
         '"$GATEWAY_URL/v1/sandboxes/$SANDBOX_ID/grade" --data-binary "$PAYLOAD")'),
        'echo "$RESP" >> "$GRADER_LOG"',
        ('if echo "$RESP" | python3 -c "import sys,json; '
         'sys.exit(0 if json.load(sys.stdin).get(\\"passed\\") else 1)"; then'),
        '  echo "1" > "$REWARD"',
        '  echo "Score: 1"',
        "  exit 0",
        "fi",
        "",
        'echo "0" > "$REWARD"',
        'echo "Score: 0 — grader response: $(echo "$RESP" | head -c 500)"',
    ]
    return "\n".join(lines) + "\n"


def _build_test_sh_macos(task: Task) -> str:
    lines = [
        "#!/bin/bash",
        "# macOS test.sh — runs inside the VM via Harbor.",
        'PREFIX=""',
        '[ -d "/tmp/harbor/logs" ] && PREFIX="/tmp/harbor"',
        'REWARD="${PREFIX}/logs/verifier/reward.txt"',
        'GRADER_LOG="${PREFIX}/logs/verifier/grader.log"',
        "",
    ]

    # Single grader wins; otherwise fall back to score=100 candidates.
    grader = (task.grader or "").strip()
    if grader:
        cmds = [grader]
    else:
        cmds = [gc["command"] for gc in task.grading_candidates if gc.get("score", 0) == 100]

    if not cmds:
        lines += ['echo "0" > "$REWARD"', 'echo "Score: 0 (no grader)"']
    else:
        for i, cmd in enumerate(cmds, 1):
            escaped = cmd.replace("'", "'\\''")
            lines += [
                f"# Check {i}",
                "_r=$(mktemp)",
                f"perl -e 'alarm 5; exec @ARGV' -- bash -c '{escaped}' > \"$_r\" 2>>\"$GRADER_LOG\"",
                'if grep -qi "true" "$_r" 2>/dev/null; then',
                '  rm -f "$_r"',
                '  echo "1" > "$REWARD"',
                '  echo "Score: 1"',
                "  exit 0",
                "fi",
                'rm -f "$_r"',
                "",
            ]
        lines += ['echo "0" > "$REWARD"', 'echo "Score: 0"']

    out = "\n".join(lines) + "\n"
    try:
        from .ax_transpile import patch_curl_timeouts, transpile
        out, _ = transpile(out)
        out = patch_curl_timeouts(out)[0]
    except Exception:
        pass
    return out


def _build_pre_command_sh(task: Task) -> str:
    """Generate pre_command.sh from setup commands."""
    lines = ["#!/bin/bash"]
    for cmd in task.setup_commands:
        # defaults delete fails on fresh VMs where the key was never set —
        # the clean state is already the desired state, so skip these
        if "defaults delete" in cmd:
            lines.append(f"# skipped (fresh VM already in expected state): {cmd}")
        else:
            lines.append(cmd)
    lines.append("")
    return "\n".join(lines) + "\n"


def task_to_harbor(task: Task, output_root: Path, *, overwrite: bool = False) -> Path:
    """Convert a collected Task into a Harbor task directory.

    Directory structure:
        {category}__{task_id}/
            instruction.md
            task.toml
            environment/
            tests/
                test.sh
                setup/
                    config.json
                    pre_command.sh
    """
    output_root = Path(output_root)
    category = task.category or "uncategorized"
    short_id = task.id.replace("col-", "")[:36]
    dir_name = f"{category}__{short_id}"
    task_dir = output_root / dir_name

    if task_dir.exists() and not overwrite:
        raise FileExistsError(f"Already exists: {task_dir}")
    if task_dir.exists():
        shutil.rmtree(task_dir)

    task_dir.mkdir(parents=True)
    (task_dir / "environment").mkdir()
    tests_dir = task_dir / "tests"
    tests_dir.mkdir()
    setup_dir = tests_dir / "setup"
    setup_dir.mkdir()

    # instruction.md
    (task_dir / "instruction.md").write_text(task.instruction + "\n", encoding="utf-8")

    # task.toml
    tags = ["collected", "gui", task.platform]
    if category:
        tags.append(category)
    toml = (
        "[metadata]\n"
        f'author_name = "mmini-collect"\n'
        f'difficulty = "unknown"\n'
        f'category = "desktop-automation"\n'
        f"tags = {json.dumps(tags)}\n"
        f'platform = "{task.platform}"\n'
        f"runnable = {'true' if task.runnable else 'false'}\n"
        "\n"
        "[verifier]\n"
        "timeout_sec = 1800\n"
        "\n"
        "[agent]\n"
        "timeout_sec = 1800\n"
        "\n"
        "[environment]\n"
        "cpus = 4\n"
        "memory_mb = 8192\n"
        "allow_internet = true\n"
    )
    (task_dir / "task.toml").write_text(toml, encoding="utf-8")

    # tests/setup/config.json
    config = {
        "task_id": task.id,
        "platform": task.platform,
        "before_action_delay_seconds": 10,
        "before_grading_delay_seconds": 5,
    }
    (setup_dir / "config.json").write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")

    # tests/setup/pre_command.sh
    pre_cmd = _build_pre_command_sh(task)
    pre_cmd_path = setup_dir / "pre_command.sh"
    pre_cmd_path.write_text(pre_cmd, encoding="utf-8")
    pre_cmd_path.chmod(0o755)

    # tests/test.sh
    test_sh = _build_test_sh(task)
    test_path = tests_dir / "test.sh"
    test_path.write_text(test_sh, encoding="utf-8")
    test_path.chmod(0o755)

    return task_dir

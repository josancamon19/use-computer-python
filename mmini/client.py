from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Literal, overload

import httpx

from mmini.retry import AsyncRetryTransport, RetryTransport
from mmini.sandbox import (
    AsyncIOSSandbox,
    AsyncMacOSSandbox,
    AsyncSandbox,
    IOSSandbox,
    MacOSSandbox,
    Sandbox,
    SandboxType,
)
from mmini.tasks import TasksClient


@dataclass
class RunStatus:
    """Status of an ad-hoc or model run."""

    id: str
    status: str  # "starting" | "running" | "completed" | "failed"
    model: str = ""
    task_id: str = ""
    sandbox_id: str = ""
    mini_ip: str = ""
    mini_hostname: str = ""
    max_steps: int = 0
    reward: float | None = None
    error: str = ""
    n_steps: int | None = None
    n_actions: int | None = None
    started_at: str = ""
    finished_at: str | None = None

    @property
    def done(self) -> bool:
        return self.status in ("completed", "failed")

    @staticmethod
    def _from_dict(d: dict[str, Any]) -> RunStatus:
        return RunStatus(
            id=d.get("id", ""),
            status=d.get("status", ""),
            model=d.get("model", ""),
            task_id=d.get("task_id", ""),
            sandbox_id=d.get("sandbox_id", ""),
            mini_ip=d.get("mini_ip", ""),
            mini_hostname=d.get("mini_hostname", ""),
            max_steps=d.get("max_steps", 0),
            reward=d.get("reward"),
            error=d.get("error", ""),
            n_steps=d.get("n_steps"),
            n_actions=d.get("n_actions"),
            started_at=d.get("started_at", ""),
            finished_at=d.get("finished_at"),
        )


class Mmini:
    """mmini client. Creates and manages macOS and iOS sandboxes."""

    def __init__(self, api_key: str | None = None, base_url: str = "http://localhost:8080"):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=60.0,
            transport=RetryTransport(httpx.HTTPTransport()),
        )
        self.tasks = TasksClient(self._http)

    def platforms(self) -> dict:
        """Discover available platforms, images, runtimes, and device types."""
        resp = self._http.get("/v1/platforms")
        resp.raise_for_status()
        return resp.json()

    @overload
    def create(self, *, type: Literal["macos"] = ..., host: str = ...) -> MacOSSandbox: ...
    @overload
    def create(
        self, *, type: Literal["ios"], device_type: str = ..., runtime: str = ...
    ) -> IOSSandbox: ...

    def create(
        self,
        *,
        type: str = "macos",
        host: str = "",
        device_type: str = "",
        runtime: str = "",
    ) -> MacOSSandbox | IOSSandbox:
        """Create a new sandbox.

        Args:
            type: "macos" (default) or "ios".
            host: Pin sandbox to a specific host machine (e.g. "mm001").
            device_type: iOS only — simulator device type identifier.
            runtime: iOS only — simulator runtime identifier.
        """
        body: dict = {"type": type}
        if host:
            body["host"] = host
        if type == "ios":
            if device_type:
                body["device_type"] = device_type
            if runtime:
                body["runtime"] = runtime

        resp = self._http.post("/v1/sandboxes", json=body, timeout=180.0)
        resp.raise_for_status()
        data = resp.json()
        sid = data["sandbox_id"]

        if type == "ios":
            return IOSSandbox(sandbox_id=sid, http=self._http)
        return MacOSSandbox(
            sandbox_id=sid,
            http=self._http,
            vnc_url=f"{self._base_url}{data.get('vnc_url', '')}",
            vm_ip=data.get("vm_ip", ""),
            host=data.get("host", ""),
            ssh_url=f"{self._base_url}{data.get('ssh_url', '')}",
        )

    def get(self, sandbox_id: str) -> Sandbox:
        """Get an existing sandbox by ID. Returns base Sandbox (use create() for typed access)."""
        resp = self._http.get(f"/v1/sandboxes/{sandbox_id}")
        resp.raise_for_status()
        data = resp.json()
        sb_type = SandboxType(data.get("type", "macos"))
        if sb_type == SandboxType.IOS:
            return IOSSandbox(sandbox_id=data["sandbox_id"], http=self._http)
        return MacOSSandbox(
            sandbox_id=data["sandbox_id"],
            http=self._http,
            vnc_url=f"{self._base_url}{data.get('vnc_url', '')}",
            ssh_url=f"{self._base_url}{data.get('ssh_url', '')}",
        )

    def adhoc_run(
        self,
        instruction: str,
        *,
        platform: str = "macos",
        model: str = "claude-sonnet-4-6",
        max_steps: int = 50,
        files: list[dict[str, str]] | None = None,
        poll: bool = True,
        poll_interval: float = 3.0,
    ) -> RunStatus:
        """Run an ad-hoc task: spin up a sandbox and drive a model against a free-form instruction.

        Args:
            instruction: What the agent should do.
            platform: "macos" or "ios".
            model: Model to use.
            max_steps: Max agent steps.
            files: Optional list of {remote_path, content_b64} to pre-upload.
            poll: If True, block until the run finishes.
            poll_interval: Seconds between status polls.
        """
        body: dict[str, Any] = {
            "instruction": instruction,
            "platform": platform,
            "model": model,
            "max_steps": max_steps,
        }
        if files:
            body["files"] = files
        resp = self._http.post("/admin/adhoc-runs/", json=body, timeout=30.0)
        resp.raise_for_status()
        status = RunStatus._from_dict(resp.json())
        if not poll:
            return status
        return self._poll_run(status.id, poll_interval)

    def get_run(self, run_id: str) -> RunStatus:
        """Get current status of a model run."""
        resp = self._http.get(f"/admin/tasks/model-runs/{run_id}")
        resp.raise_for_status()
        return RunStatus._from_dict(resp.json())

    def _poll_run(self, run_id: str, interval: float = 3.0) -> RunStatus:
        while True:
            status = self.get_run(run_id)
            if status.done:
                return status
            time.sleep(interval)

    def close(self):
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


class AsyncMmini:
    """Async mmini client."""

    def __init__(self, api_key: str | None = None, base_url: str = "http://localhost:8080"):
        self._base_url = base_url.rstrip("/")
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=self._base_url,
            headers=headers,
            timeout=60.0,
            transport=AsyncRetryTransport(httpx.AsyncHTTPTransport()),
        )

    async def platforms(self) -> dict:
        """Discover available platforms, images, runtimes, and device types."""
        resp = await self._http.get("/v1/platforms")
        resp.raise_for_status()
        return resp.json()

    @overload
    async def create(
        self, *, type: Literal["macos"] = ..., host: str = ...
    ) -> AsyncMacOSSandbox: ...
    @overload
    async def create(
        self, *, type: Literal["ios"], device_type: str = ..., runtime: str = ...
    ) -> AsyncIOSSandbox: ...

    async def create(
        self,
        *,
        type: str = "macos",
        host: str = "",
        device_type: str = "",
        runtime: str = "",
    ) -> AsyncMacOSSandbox | AsyncIOSSandbox:
        """Create a new sandbox.

        Args:
            type: "macos" (default) or "ios".
            host: Pin sandbox to a specific host machine (e.g. "mm001").
            device_type: iOS only — simulator device type identifier.
            runtime: iOS only — simulator runtime identifier.
        """
        body: dict = {"type": type}
        if host:
            body["host"] = host
        if type == "ios":
            if device_type:
                body["device_type"] = device_type
            if runtime:
                body["runtime"] = runtime

        resp = await self._http.post("/v1/sandboxes", json=body, timeout=180.0)
        resp.raise_for_status()
        data = resp.json()
        sid = data["sandbox_id"]

        if type == "ios":
            return AsyncIOSSandbox(sandbox_id=sid, http=self._http)
        return AsyncMacOSSandbox(
            sandbox_id=sid,
            http=self._http,
            vnc_url=f"{self._base_url}{data.get('vnc_url', '')}",
            ssh_url=f"{self._base_url}{data.get('ssh_url', '')}",
            vm_ip=data.get("vm_ip", ""),
            host=data.get("host", ""),
        )

    async def get(self, sandbox_id: str) -> AsyncSandbox:
        """Get an existing sandbox by ID."""
        resp = await self._http.get(f"/v1/sandboxes/{sandbox_id}")
        resp.raise_for_status()
        data = resp.json()
        sb_type = SandboxType(data.get("type", "macos"))
        if sb_type == SandboxType.IOS:
            return AsyncIOSSandbox(sandbox_id=data["sandbox_id"], http=self._http)
        return AsyncMacOSSandbox(
            sandbox_id=data["sandbox_id"],
            http=self._http,
            vnc_url=f"{self._base_url}{data.get('vnc_url', '')}",
            ssh_url=f"{self._base_url}{data.get('ssh_url', '')}",
        )

    async def adhoc_run(
        self,
        instruction: str,
        *,
        platform: str = "macos",
        model: str = "claude-sonnet-4-6",
        max_steps: int = 50,
        files: list[dict[str, str]] | None = None,
        poll: bool = True,
        poll_interval: float = 3.0,
    ) -> RunStatus:
        """Run an ad-hoc task: spin up a sandbox and drive a model against a free-form instruction."""
        body: dict[str, Any] = {
            "instruction": instruction,
            "platform": platform,
            "model": model,
            "max_steps": max_steps,
        }
        if files:
            body["files"] = files
        resp = await self._http.post("/admin/adhoc-runs/", json=body, timeout=30.0)
        resp.raise_for_status()
        status = RunStatus._from_dict(resp.json())
        if not poll:
            return status
        return await self._poll_run(status.id, poll_interval)

    async def get_run(self, run_id: str) -> RunStatus:
        """Get current status of a model run."""
        resp = await self._http.get(f"/admin/tasks/model-runs/{run_id}")
        resp.raise_for_status()
        return RunStatus._from_dict(resp.json())

    async def _poll_run(self, run_id: str, interval: float = 3.0) -> RunStatus:
        while True:
            status = await self.get_run(run_id)
            if status.done:
                return status
            await asyncio.sleep(interval)

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

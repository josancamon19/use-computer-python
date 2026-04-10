from __future__ import annotations

from typing import Literal, overload

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

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

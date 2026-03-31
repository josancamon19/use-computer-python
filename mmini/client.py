from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal, overload

import httpx

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

_log = logging.getLogger(__name__)
_RETRY_STATUSES = frozenset({500, 502, 503, 504, 529})
_NO_RETRY_PATTERNS = ("not found", "connection refused")
_MAX_RETRIES = 3
_RETRY_DELAY = 2.0


def _is_retryable(body: str) -> bool:
    """Check if the error body indicates a retryable (transient) failure."""
    lower = body.lower()
    return not any(p in lower for p in _NO_RETRY_PATTERNS)


class _RetryTransport(httpx.BaseTransport):
    """Wraps an httpx sync transport to retry on transient server errors."""

    def __init__(
        self,
        transport: httpx.BaseTransport,
        max_retries: int = _MAX_RETRIES,
        delay: float = _RETRY_DELAY,
    ):
        self._transport = transport
        self._max_retries = max_retries
        self._delay = delay

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = None
        for attempt in range(self._max_retries + 1):
            resp = self._transport.handle_request(request)
            if resp.status_code not in _RETRY_STATUSES or attempt == self._max_retries:
                return resp
            body = ""
            try:
                resp.read()
                body = resp.text[:500]
            except Exception:
                pass
            if not _is_retryable(body):
                return resp
            _log.warning(
                "retry %d/%d: %s %s → %d %s",
                attempt + 1, self._max_retries, request.method, request.url,
                resp.status_code, body,
            )
            resp.close()
            time.sleep(self._delay)
        return resp  # type: ignore[return-value]

    def close(self) -> None:
        self._transport.close()


class _AsyncRetryTransport(httpx.AsyncBaseTransport):
    """Wraps an httpx async transport to retry on transient server errors."""

    def __init__(
        self,
        transport: httpx.AsyncBaseTransport,
        max_retries: int = _MAX_RETRIES,
        delay: float = _RETRY_DELAY,
    ):
        self._transport = transport
        self._max_retries = max_retries
        self._delay = delay

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        resp = None
        for attempt in range(self._max_retries + 1):
            resp = await self._transport.handle_async_request(request)
            if resp.status_code not in _RETRY_STATUSES or attempt == self._max_retries:
                return resp
            body = ""
            try:
                await resp.aread()
                body = resp.text[:500]
            except Exception:
                pass
            if not _is_retryable(body):
                return resp
            _log.warning(
                "retry %d/%d: %s %s → %d %s",
                attempt + 1, self._max_retries, request.method, request.url,
                resp.status_code, body,
            )
            await resp.aclose()
            await asyncio.sleep(self._delay)
        return resp  # type: ignore[return-value]

    async def aclose(self) -> None:
        await self._transport.aclose()


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
            transport=_RetryTransport(httpx.HTTPTransport()),
        )
        self.tasks = TasksClient(self._http)

    def platforms(self) -> dict:
        """Discover available platforms, images, runtimes, and device types."""
        resp = self._http.get("/v1/platforms")
        resp.raise_for_status()
        return resp.json()

    @overload
    def create(self, *, type: Literal["macos"] = ..., wait: bool = ..., host: str = ...) -> MacOSSandbox: ...
    @overload
    def create(
        self, *, type: Literal["ios"], device_type: str = ..., runtime: str = ...
    ) -> IOSSandbox: ...

    def create(
        self,
        *,
        type: str = "macos",
        wait: bool = False,
        device_type: str = "",
        runtime: str = "",
        host: str = "",
    ) -> MacOSSandbox | IOSSandbox:
        """Create a new sandbox.

        Args:
            type: "macos" (default) or "ios".
            wait: macOS only — if True, gateway retries up to 2min when pool is empty.
            device_type: iOS only — simulator device type identifier.
            runtime: iOS only — simulator runtime identifier.
            host: Pin sandbox to a specific host machine.
        """
        body: dict = {"type": type}
        if type == "ios":
            if device_type:
                body["device_type"] = device_type
            if runtime:
                body["runtime"] = runtime
        if host:
            body["host"] = host
        params = {"wait": "true"} if wait else {}

        resp = self._http.post("/v1/sandboxes", json=body, params=params)
        resp.raise_for_status()
        data = resp.json()
        sid = data["sandbox_id"]

        if type == "ios":
            return IOSSandbox(sandbox_id=sid, http=self._http)
        return MacOSSandbox(
            sandbox_id=sid,
            http=self._http,
            vnc_url=f"{self._base_url}{data.get('vnc_url', '')}",
            ssh_url=f"{self._base_url}{data.get('ssh_url', '')}",
            vm_ip=data.get("vm_ip", ""),
            host=data.get("host", ""),
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
            transport=_AsyncRetryTransport(httpx.AsyncHTTPTransport()),
        )

    async def platforms(self) -> dict:
        """Discover available platforms, images, runtimes, and device types."""
        resp = await self._http.get("/v1/platforms")
        resp.raise_for_status()
        return resp.json()

    @overload
    async def create(
        self, *, type: Literal["macos"] = ..., wait: bool = ..., host: str = ...
    ) -> AsyncMacOSSandbox: ...
    @overload
    async def create(
        self, *, type: Literal["ios"], device_type: str = ..., runtime: str = ...
    ) -> AsyncIOSSandbox: ...

    async def create(
        self,
        *,
        type: str = "macos",
        wait: bool = False,
        device_type: str = "",
        runtime: str = "",
        host: str = "",
    ) -> AsyncMacOSSandbox | AsyncIOSSandbox:
        """Create a new sandbox.

        Args:
            type: "macos" (default) or "ios".
            wait: macOS only — if True, gateway retries up to 2min when pool is empty.
            device_type: iOS only — simulator device type identifier.
            runtime: iOS only — simulator runtime identifier.
            host: Pin sandbox to a specific host machine.
        """
        body: dict = {"type": type}
        if type == "ios":
            if device_type:
                body["device_type"] = device_type
            if runtime:
                body["runtime"] = runtime
        if host:
            body["host"] = host
        params = {"wait": "true"} if wait else {}

        resp = await self._http.post("/v1/sandboxes", json=body, params=params)
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

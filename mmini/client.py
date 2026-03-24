from __future__ import annotations

import httpx

from mmini.sandbox import AsyncSandbox, Sandbox


class Mmini:
    """mmini client. Creates and manages macOS sandboxes."""

    def __init__(self, api_key: str | None = None, base_url: str = "http://localhost:8080"):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.Client(base_url=self._base_url, headers=headers, http2=True, timeout=60.0)

    def create(self) -> Sandbox:
        resp = self._http.post("/v1/sandboxes")
        resp.raise_for_status()
        data = resp.json()
        return Sandbox(
            sandbox_id=data["sandbox_id"],
            vnc_url=f"{self._base_url}{data['vnc_url']}",
            ssh_url=f"{self._base_url}{data['ssh_url']}",
            http=self._http,
        )

    def get(self, sandbox_id: str) -> Sandbox:
        resp = self._http.get(f"/v1/sandboxes/{sandbox_id}")
        resp.raise_for_status()
        data = resp.json()
        return Sandbox(
            sandbox_id=data["sandbox_id"],
            vnc_url=f"{self._base_url}{data['vnc_url']}",
            ssh_url=f"{self._base_url}{data['ssh_url']}",
            http=self._http,
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
        self._http = httpx.AsyncClient(base_url=self._base_url, headers=headers, http2=True, timeout=60.0)

    async def create(self) -> AsyncSandbox:
        resp = await self._http.post("/v1/sandboxes")
        resp.raise_for_status()
        data = resp.json()
        return AsyncSandbox(
            sandbox_id=data["sandbox_id"],
            vnc_url=f"{self._base_url}{data['vnc_url']}",
            ssh_url=f"{self._base_url}{data['ssh_url']}",
            http=self._http,
        )

    async def get(self, sandbox_id: str) -> AsyncSandbox:
        resp = await self._http.get(f"/v1/sandboxes/{sandbox_id}")
        resp.raise_for_status()
        data = resp.json()
        return AsyncSandbox(
            sandbox_id=data["sandbox_id"],
            vnc_url=f"{self._base_url}{data['vnc_url']}",
            ssh_url=f"{self._base_url}{data['ssh_url']}",
            http=self._http,
        )

    async def close(self):
        await self._http.aclose()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

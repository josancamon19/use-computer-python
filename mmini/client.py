from __future__ import annotations

import httpx

from mmini.sandbox import Sandbox


class Mmini:
    """mmini client. Creates and manages macOS sandboxes."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "http://localhost:8080",
    ):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._http = httpx.Client(
            base_url=self._base_url,
            headers=self._headers(),
            http2=True,
            timeout=60.0,
        )

    def _headers(self) -> dict[str, str]:
        h: dict[str, str] = {}
        if self._api_key:
            h["Authorization"] = f"Bearer {self._api_key}"
        return h

    def create(self, *, seed: list[dict] | None = None) -> Sandbox:
        kwargs: dict = {}
        if seed:
            kwargs["json"] = {"seed": seed}
        resp = self._http.post("/v1/sandboxes", **kwargs)
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

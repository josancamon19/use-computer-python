from __future__ import annotations

from pathlib import Path

import httpx

from mmini.display import Display
from mmini.keyboard import Keyboard
from mmini.mouse import Mouse
from mmini.recording import Recording
from mmini.screenshot import Screenshot


class Sandbox:
    """A macOS sandbox session with mouse, keyboard, screenshot, recording, and display."""

    def __init__(
        self,
        sandbox_id: str,
        vnc_url: str,
        ssh_url: str,
        http: httpx.Client,
    ):
        self.sandbox_id = sandbox_id
        self.vnc_url = vnc_url
        self.ssh_url = ssh_url
        self._http = http
        self._prefix = f"/v1/sandboxes/{sandbox_id}"

        self.mouse = Mouse(http, self._prefix)
        self.keyboard = Keyboard(http, self._prefix)
        self.screenshot = Screenshot(http, self._prefix)
        self.recording = Recording(http, self._prefix)
        self.display = Display(http, self._prefix)

    def act(
        self,
        action: dict,
        screenshot_after: bool = True,
        screenshot_delay_ms: int = 100,
    ) -> dict:
        """Execute an action and optionally capture a screenshot in a single round trip."""
        resp = self._http.post(
            f"{self._prefix}/act",
            json={
                "action": action,
                "screenshot_after": screenshot_after,
                "screenshot_delay_ms": screenshot_delay_ms,
            },
        )
        resp.raise_for_status()

        if screenshot_after and resp.headers.get("content-type", "").startswith("image/"):
            return {"screenshot": resp.content}

        return resp.json()

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        """Upload a local file to the sandbox."""
        with open(local_path, "rb") as f:
            data = f.read()
        self.upload_bytes(data, remote_path)

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        """Upload raw bytes to a file path on the sandbox."""
        resp = self._http.put(
            f"{self._prefix}/files",
            params={"path": remote_path},
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

    def close(self):
        """Destroy this sandbox."""
        self._http.delete(f"{self._prefix}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self):
        return f"Sandbox({self.sandbox_id!r})"

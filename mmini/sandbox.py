from __future__ import annotations

from pathlib import Path

import httpx

from mmini.display import AsyncDisplay, Display
from mmini.keyboard import AsyncKeyboard, Keyboard
from mmini.mouse import AsyncMouse, Mouse
from mmini.recording import AsyncRecording, Recording
from mmini.screenshot import AsyncScreenshot, Screenshot


class Sandbox:
    """A macOS sandbox session with mouse, keyboard, screenshot, recording, and display."""

    def __init__(self, sandbox_id: str, vnc_url: str, ssh_url: str, http: httpx.Client):
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

    def act(self, action: dict, screenshot_after: bool = True, screenshot_delay_ms: int = 100) -> dict:
        resp = self._http.post(
            f"{self._prefix}/act",
            json={"action": action, "screenshot_after": screenshot_after, "screenshot_delay_ms": screenshot_delay_ms},
        )
        resp.raise_for_status()
        if screenshot_after and resp.headers.get("content-type", "").startswith("image/"):
            return {"screenshot": resp.content}
        return resp.json()

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        with open(local_path, "rb") as f:
            data = f.read()
        self.upload_bytes(data, remote_path)

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        resp = self._http.put(
            f"{self._prefix}/files", params={"path": remote_path},
            content=data, headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

    def close(self):
        self._http.delete(f"{self._prefix}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self):
        return f"Sandbox({self.sandbox_id!r})"


class AsyncSandbox:
    """Async version of Sandbox."""

    def __init__(self, sandbox_id: str, vnc_url: str, ssh_url: str, http: httpx.AsyncClient):
        self.sandbox_id = sandbox_id
        self.vnc_url = vnc_url
        self.ssh_url = ssh_url
        self._http = http
        self._prefix = f"/v1/sandboxes/{sandbox_id}"

        self.mouse = AsyncMouse(http, self._prefix)
        self.keyboard = AsyncKeyboard(http, self._prefix)
        self.screenshot = AsyncScreenshot(http, self._prefix)
        self.recording = AsyncRecording(http, self._prefix)
        self.display = AsyncDisplay(http, self._prefix)

    async def act(self, action: dict, screenshot_after: bool = True, screenshot_delay_ms: int = 100) -> dict:
        resp = await self._http.post(
            f"{self._prefix}/act",
            json={"action": action, "screenshot_after": screenshot_after, "screenshot_delay_ms": screenshot_delay_ms},
        )
        resp.raise_for_status()
        if screenshot_after and resp.headers.get("content-type", "").startswith("image/"):
            return {"screenshot": resp.content}
        return resp.json()

    async def upload(self, local_path: str | Path, remote_path: str) -> None:
        with open(local_path, "rb") as f:
            data = f.read()
        await self.upload_bytes(data, remote_path)

    async def upload_bytes(self, data: bytes, remote_path: str) -> None:
        resp = await self._http.put(
            f"{self._prefix}/files", params={"path": remote_path},
            content=data, headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

    async def upload_dir(self, local_dir: str | Path, remote_dir: str) -> None:
        import io
        import tarfile

        local_dir = Path(local_dir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for item in local_dir.rglob("*"):
                tar.add(str(item), arcname=str(item.relative_to(local_dir)))
        await self.upload_bytes(buf.getvalue(), f"/tmp/_mmini_upload_{self.sandbox_id[-8:]}.tar.gz")
        await self.exec_ssh(
            f"mkdir -p {remote_dir} && tar xzf /tmp/_mmini_upload_{self.sandbox_id[-8:]}.tar.gz"
            f" -C {remote_dir} && rm -f /tmp/_mmini_upload_{self.sandbox_id[-8:]}.tar.gz"
        )

    async def download_dir(self, remote_dir: str, local_dir: str | Path) -> None:
        import io
        import tarfile

        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        tar_remote = f"/tmp/_mmini_download_{self.sandbox_id[-8:]}.tar.gz"
        await self.exec_ssh(f"tar czf {tar_remote} -C {remote_dir} . 2>/dev/null; true")

        resp = await self._http.get(f"{self._prefix}/files", params={"path": tar_remote})
        if resp.status_code != 200 or len(resp.content) == 0:
            return

        try:
            with tarfile.open(fileobj=io.BytesIO(resp.content), mode="r:gz") as tar:
                tar.extractall(path=str(local_dir))
        except tarfile.ReadError:
            return
        await self.exec_ssh(f"rm -f {tar_remote}")

    async def download_file(self, remote_path: str, local_path: str | Path) -> None:
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = await self._http.get(f"{self._prefix}/files", params={"path": remote_path})
        resp.raise_for_status()
        local_path.write_bytes(resp.content)

    async def exec_ssh(self, command: str, timeout: int = 120) -> tuple[int, str]:
        resp = await self._http.post(f"{self._prefix}/exec", json={"command": command}, timeout=timeout)
        if resp.status_code == 404:
            raise NotImplementedError("exec endpoint not available on gateway")
        resp.raise_for_status()
        data = resp.json()
        return data.get("return_code", 0), data.get("stdout", "")

    async def close(self):
        await self._http.delete(f"{self._prefix}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    def __repr__(self):
        return f"AsyncSandbox({self.sandbox_id!r})"

"""Async versions of the mmini SDK classes."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx


class AsyncScreenshot:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def take_full_screen(self, show_cursor: bool = False) -> bytes:
        resp = await self._http.get(
            f"{self._prefix}/screenshot",
            params={"show_cursor": show_cursor},
        )
        resp.raise_for_status()
        return resp.content

    async def take_region(self, x: int, y: int, width: int, height: int) -> bytes:
        resp = await self._http.get(
            f"{self._prefix}/screenshot/region",
            params={"x": x, "y": y, "width": width, "height": height},
        )
        resp.raise_for_status()
        return resp.content

    async def take_compressed(
        self, format: str = "jpeg", quality: int = 80, scale: float | None = None
    ) -> bytes:
        params: dict = {"format": format, "quality": quality}
        if scale is not None:
            params["scale"] = scale
        resp = await self._http.get(
            f"{self._prefix}/screenshot/compressed", params=params,
        )
        resp.raise_for_status()
        return resp.content


class AsyncMouse:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def click(self, x: int, y: int, button: str = "left", double: bool = False) -> dict:
        resp = await self._http.post(
            f"{self._prefix}/mouse/click",
            json={"x": x, "y": y, "button": button, "double": double},
        )
        resp.raise_for_status()
        return resp.json()

    async def move(self, x: int, y: int) -> dict:
        resp = await self._http.post(
            f"{self._prefix}/mouse/move", json={"x": x, "y": y},
        )
        resp.raise_for_status()
        return resp.json()

    async def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left"
    ) -> dict:
        resp = await self._http.post(
            f"{self._prefix}/mouse/drag",
            json={
                "startX": start_x, "startY": start_y,
                "endX": end_x, "endY": end_y, "button": button,
            },
        )
        resp.raise_for_status()
        return resp.json()

    async def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> dict:
        resp = await self._http.post(
            f"{self._prefix}/mouse/scroll",
            json={"x": x, "y": y, "direction": direction, "amount": amount},
        )
        resp.raise_for_status()
        return resp.json()

    async def get_position(self) -> dict:
        resp = await self._http.get(f"{self._prefix}/mouse/position")
        resp.raise_for_status()
        return resp.json()


class AsyncKeyboard:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def type(self, text: str, delay: int | None = None) -> dict:
        payload: dict = {"text": text}
        if delay is not None:
            payload["delay"] = delay
        resp = await self._http.post(f"{self._prefix}/keyboard/type", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def press(self, key: str, modifiers: list[str] | None = None) -> dict:
        payload: dict = {"key": key}
        if modifiers:
            payload["modifiers"] = modifiers
        resp = await self._http.post(f"{self._prefix}/keyboard/press", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def hotkey(self, keys: str) -> dict:
        resp = await self._http.post(f"{self._prefix}/keyboard/hotkey", json={"keys": keys})
        resp.raise_for_status()
        return resp.json()


class AsyncDisplay:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def get_info(self) -> dict:
        resp = await self._http.get(f"{self._prefix}/display/info")
        resp.raise_for_status()
        return resp.json()

    async def get_windows(self) -> dict:
        resp = await self._http.get(f"{self._prefix}/display/windows")
        resp.raise_for_status()
        return resp.json()


class AsyncRecording:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def start(self, name: str | None = None) -> dict:
        payload: dict = {}
        if name:
            payload["name"] = name
        resp = await self._http.post(f"{self._prefix}/recording/start", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def stop(self, recording_id: str) -> dict:
        resp = await self._http.post(
            f"{self._prefix}/recording/stop", json={"id": recording_id},
        )
        resp.raise_for_status()
        return resp.json()

    async def list_all(self) -> list[dict[str, Any]]:
        resp = await self._http.get(f"{self._prefix}/recordings")
        resp.raise_for_status()
        return resp.json()

    async def get(self, recording_id: str) -> dict:
        resp = await self._http.get(f"{self._prefix}/recordings/{recording_id}")
        resp.raise_for_status()
        return resp.json()

    async def download(self, recording_id: str, local_path: str) -> None:
        url = f"{self._prefix}/recordings/{recording_id}/download"
        async with self._http.stream("GET", url) as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    async def delete(self, recording_id: str) -> None:
        resp = await self._http.delete(f"{self._prefix}/recordings/{recording_id}")
        resp.raise_for_status()


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

    async def act(
        self, action: dict, screenshot_after: bool = True, screenshot_delay_ms: int = 100,
    ) -> dict:
        resp = await self._http.post(
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

    async def upload(self, local_path: str | Path, remote_path: str) -> None:
        with open(local_path, "rb") as f:
            data = f.read()
        await self.upload_bytes(data, remote_path)

    async def upload_bytes(self, data: bytes, remote_path: str) -> None:
        resp = await self._http.put(
            f"{self._prefix}/files",
            params={"path": remote_path},
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

    async def upload_dir(self, local_dir: str | Path, remote_dir: str) -> None:
        """Upload a directory by tarring locally, uploading, and untarring on the VM."""
        import io
        import tarfile

        local_dir = Path(local_dir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for item in local_dir.rglob("*"):
                tar.add(str(item), arcname=str(item.relative_to(local_dir)))
        tar_bytes = buf.getvalue()

        tar_remote = f"/tmp/_mmini_upload_{self.sandbox_id[-8:]}.tar.gz"
        await self.upload_bytes(tar_bytes, tar_remote)
        await self.exec_ssh(
            f"mkdir -p {remote_dir} && tar xzf {tar_remote}"
            f" -C {remote_dir} && rm -f {tar_remote}"
        )

    async def download_dir(self, remote_dir: str, local_dir: str | Path) -> None:
        """Download a directory by tarring on the VM, downloading, and untarring locally."""
        import io
        import tarfile

        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)

        tar_remote = f"/tmp/_mmini_download_{self.sandbox_id[-8:]}.tar.gz"
        await self.exec_ssh(f"tar czf {tar_remote} -C {remote_dir} . 2>/dev/null; true")

        resp = await self._http.get(
            f"{self._prefix}/files",
            params={"path": tar_remote},
        )
        if resp.status_code != 200 or len(resp.content) == 0:
            return  # Directory might be empty or not exist

        buf = io.BytesIO(resp.content)
        try:
            with tarfile.open(fileobj=buf, mode="r:gz") as tar:
                tar.extractall(path=str(local_dir))
        except tarfile.ReadError:
            return  # Empty or invalid tar

        await self.exec_ssh(f"rm -f {tar_remote}")

    async def download_file(
        self, remote_path: str, local_path: str | Path,
    ) -> None:
        """Download a single file from the VM."""
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = await self._http.get(
            f"{self._prefix}/files",
            params={"path": remote_path},
        )
        resp.raise_for_status()
        local_path.write_bytes(resp.content)

    async def exec_ssh(self, command: str, timeout: int = 120) -> tuple[int, str]:
        """Execute a command on the VM via the gateway's exec proxy.

        Falls back to a no-op if the endpoint doesn't exist.
        Returns (return_code, stdout).
        """
        resp = await self._http.post(
            f"{self._prefix}/exec",
            json={"command": command},
            timeout=timeout,
        )
        if resp.status_code == 404:
            # Endpoint not available — caller should handle
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


class AsyncMmini:
    """Async mmini client."""

    def __init__(self, api_key: str | None = None, base_url: str = "http://localhost:8080"):
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        headers: dict[str, str] = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        self._http = httpx.AsyncClient(
            base_url=self._base_url, headers=headers, http2=True, timeout=60.0,
        )

    async def create(self, *, seed: list[dict] | None = None) -> AsyncSandbox:
        kwargs: dict = {}
        if seed:
            kwargs["json"] = {"seed": seed}
        resp = await self._http.post("/v1/sandboxes", **kwargs)
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

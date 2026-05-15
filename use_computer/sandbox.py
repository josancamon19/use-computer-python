from __future__ import annotations

import io
import tarfile
import threading
import urllib.request
from enum import Enum
from pathlib import Path

import httpx

from use_computer.accessibility import Accessibility, AsyncAccessibility
from use_computer.display import AsyncDisplay, Display
from use_computer.ios.apps import Apps, AsyncApps
from use_computer.ios.environment import AsyncEnvironment, Environment
from use_computer.ios.input import AsyncInput, Input
from use_computer.macos.keyboard import AsyncKeyboard, Keyboard
from use_computer.macos.mouse import AsyncMouse, Mouse
from use_computer.models import ActResult, ExecResult
from use_computer.recording import AsyncRecording, Recording
from use_computer.screenshot import AsyncScreenshot, Screenshot


class SandboxType(str, Enum):
    MACOS = "macos"
    IOS = "ios"


# ---------------------------------------------------------------------------
# Keepalive helper — shared by sync and async sandboxes
# ---------------------------------------------------------------------------


def _start_keepalive_thread(
    http_client: httpx.Client | httpx.AsyncClient,
    prefix: str,
    interval: float,
) -> tuple[threading.Event, threading.Thread]:
    """Spawn a daemon thread that POSTs `<prefix>/keepalive` every `interval` seconds.

    Uses urllib.request directly (not the SDK's httpx client) so the thread
    runs independently of any asyncio loop or shared connection pool. This is
    why it works for both sync Sandbox and AsyncSandbox: the thread never
    touches the caller's HTTP client.
    """
    base_url = str(http_client.base_url).rstrip("/")
    keepalive_url = f"{base_url}{prefix}/keepalive"
    auth = http_client.headers.get("Authorization", "")
    headers = {"Authorization": auth} if auth else {}

    stop = threading.Event()

    def _loop() -> None:
        while not stop.is_set():
            stop.wait(interval)
            if stop.is_set():
                break
            try:
                req = urllib.request.Request(keepalive_url, method="POST", headers=headers)
                urllib.request.urlopen(req, timeout=10).close()
            except Exception:
                pass

    thread = threading.Thread(target=_loop, daemon=True)
    thread.start()
    return stop, thread


def _stop_keepalive_thread(
    stop: threading.Event | None,
    thread: threading.Thread | None,
) -> None:
    if stop:
        stop.set()
    if thread:
        thread.join(timeout=2)


# ---------------------------------------------------------------------------
# Sync
# ---------------------------------------------------------------------------


class Sandbox:
    """Base sandbox — shared operations that work on both macOS and iOS."""

    def __init__(
        self,
        sandbox_id: str,
        type: SandboxType,
        http: httpx.Client,
        *,
        vnc_url: str = "",
        ssh_url: str = "",
    ):
        self.sandbox_id = sandbox_id
        self.type = type
        self.vnc_url = vnc_url
        self.ssh_url = ssh_url
        self._http = http
        self._prefix = f"/v1/sandboxes/{sandbox_id}"
        self._keepalive_stop: threading.Event | None = None
        self._keepalive_thread: threading.Thread | None = None

        self.screenshot = Screenshot(http, self._prefix)
        self.recording = Recording(http, self._prefix)
        self.display = Display(http, self._prefix)
        self.accessibility = Accessibility(http, self._prefix)

    def upload(self, local_path: str | Path, remote_path: str) -> None:
        with open(local_path, "rb") as f:
            data = f.read()
        self.upload_bytes(data, remote_path)

    def upload_bytes(self, data: bytes, remote_path: str) -> None:
        # NOTE: parent directories must exist — SCP won't create them.
        # Use upload_dir() for nested paths or mkdir -p via exec_ssh first.
        resp = self._http.put(
            f"{self._prefix}/files",
            params={"path": remote_path},
            content=data,
            headers={"Content-Type": "application/octet-stream"},
        )
        resp.raise_for_status()

    def download_file(self, remote_path: str, local_path: str | Path) -> None:
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = self._http.get(f"{self._prefix}/files", params={"path": remote_path})
        resp.raise_for_status()
        local_path.write_bytes(resp.content)

    def start_keepalive(self, interval: float = 30.0) -> None:
        """Start a background thread that pings the gateway every `interval` seconds."""
        self._keepalive_stop, self._keepalive_thread = _start_keepalive_thread(
            self._http, self._prefix, interval
        )

    def stop_keepalive(self) -> None:
        """Stop the keepalive background thread."""
        _stop_keepalive_thread(self._keepalive_stop, self._keepalive_thread)
        self._keepalive_stop = None
        self._keepalive_thread = None

    def close(self):
        self.stop_keepalive()
        self._http.delete(f"{self._prefix}")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __repr__(self):
        return f"Sandbox({self.sandbox_id!r}, type={self.type.value!r})"


class MacOSSandbox(Sandbox):
    """macOS VM sandbox — full mouse, keyboard, SSH exec, VNC."""

    def __init__(
        self,
        sandbox_id: str,
        http: httpx.Client,
        *,
        vnc_url: str = "",
        ssh_url: str = "",
        vm_ip: str = "",
        host: str = "",
    ):
        super().__init__(sandbox_id, SandboxType.MACOS, http, vnc_url=vnc_url, ssh_url=ssh_url)
        self.vm_ip = vm_ip
        self.host = host
        self.mouse = Mouse(http, self._prefix)
        self.keyboard = Keyboard(http, self._prefix)

    def act(
        self,
        action: dict,
        screenshot_after: bool = True,
        screenshot_delay_ms: int = 100,
    ) -> ActResult:
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
            return ActResult(screenshot=resp.content)
        return ActResult(data=resp.json())

    def exec_ssh(self, command: str, timeout: int = 120) -> ExecResult:
        resp = self._http.post(f"{self._prefix}/exec", json={"command": command}, timeout=timeout)
        resp.raise_for_status()
        return ExecResult.from_dict(resp.json())

    def exec_ax(self, command: str, timeout: int = 120) -> ExecResult:
        """Run a shell command on the VM via cua-server's run_command.

        Use this *only* when your command needs the macOS Accessibility API
        (AXUIElementCopyAttributeValue, synthetic CGEvent, etc.). The
        responsibility chain through cua-server (`launchd → cua-server →
        bash → command`) lets the system TCC grant on python3.12 actually
        apply, while the SSH-backed `exec_ssh` puts `sshd-keygen-wrapper`
        in the chain and TCC denies AX calls with -25211.

        Sparser env than `exec_ssh` — set $PATH explicitly inside your
        command if you need brew binaries.
        """
        resp = self._http.post(
            f"{self._prefix}/exec_ax", json={"command": command}, timeout=timeout
        )
        resp.raise_for_status()
        return ExecResult.from_dict(resp.json())

    def upload_dir(self, local_dir: str | Path, remote_dir: str) -> None:
        local_dir = Path(local_dir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for item in local_dir.rglob("*"):
                tar.add(str(item), arcname=str(item.relative_to(local_dir)))
        tmp = f"/tmp/_use_computer_upload_{self.sandbox_id[-8:]}.tar.gz"
        self.upload_bytes(buf.getvalue(), tmp)
        self.exec_ssh(f'mkdir -p "{remote_dir}" && tar xzf {tmp} -C "{remote_dir}" && rm -f {tmp}')

    def download_dir(self, remote_dir: str, local_dir: str | Path) -> None:
        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        # List files via exec, then download each
        result = self.exec_ssh(f'find "{remote_dir}" -type f')
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            rel = line[len(remote_dir) :].lstrip("/")
            local_path = local_dir / rel
            self.download_file(line, local_path)


class IOSSandbox(Sandbox):
    """iOS simulator sandbox — tap, swipe, hardware buttons, app management."""

    def __init__(self, sandbox_id: str, http: httpx.Client):
        super().__init__(sandbox_id, SandboxType.IOS, http)
        self.input = Input(http, self._prefix)
        self.apps = Apps(http, self._prefix)
        self.environment = Environment(http, self._prefix)


# ---------------------------------------------------------------------------
# Async
# ---------------------------------------------------------------------------


class AsyncSandbox:
    """Base async sandbox — shared operations that work on both macOS and iOS."""

    def __init__(
        self,
        sandbox_id: str,
        type: SandboxType,
        http: httpx.AsyncClient,
        *,
        vnc_url: str = "",
        ssh_url: str = "",
    ):
        self.sandbox_id = sandbox_id
        self.type = type
        self.vnc_url = vnc_url
        self.ssh_url = ssh_url
        self._http = http
        self._prefix = f"/v1/sandboxes/{sandbox_id}"
        self._keepalive_stop: threading.Event | None = None
        self._keepalive_thread: threading.Thread | None = None

        self.screenshot = AsyncScreenshot(http, self._prefix)
        self.recording = AsyncRecording(http, self._prefix)
        self.display = AsyncDisplay(http, self._prefix)
        self.accessibility = AsyncAccessibility(http, self._prefix)

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

    async def download_file(self, remote_path: str, local_path: str | Path) -> None:
        local_path = Path(local_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        resp = await self._http.get(f"{self._prefix}/files", params={"path": remote_path})
        resp.raise_for_status()
        local_path.write_bytes(resp.content)

    async def start_keepalive(self, interval: float = 30.0) -> None:
        """Start a background OS thread that pings the gateway every `interval` seconds.

        Uses a real thread (not an asyncio task) so it fires reliably even when
        the event loop is blocked by sync calls (e.g. sync Anthropic client).
        """
        self._keepalive_stop, self._keepalive_thread = _start_keepalive_thread(
            self._http, self._prefix, interval
        )

    async def stop_keepalive(self) -> None:
        """Stop the keepalive background thread."""
        _stop_keepalive_thread(self._keepalive_stop, self._keepalive_thread)
        self._keepalive_stop = None
        self._keepalive_thread = None

    async def close(self):
        await self.stop_keepalive()
        await self._http.delete(f"{self._prefix}")

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        await self.close()

    def __repr__(self):
        return f"AsyncSandbox({self.sandbox_id!r}, type={self.type.value!r})"


class AsyncMacOSSandbox(AsyncSandbox):
    """Async macOS VM sandbox."""

    def __init__(
        self,
        sandbox_id: str,
        http: httpx.AsyncClient,
        *,
        vnc_url: str = "",
        ssh_url: str = "",
        vm_ip: str = "",
        host: str = "",
    ):
        super().__init__(sandbox_id, SandboxType.MACOS, http, vnc_url=vnc_url, ssh_url=ssh_url)
        self.vm_ip = vm_ip
        self.host = host
        self.mouse = AsyncMouse(http, self._prefix)
        self.keyboard = AsyncKeyboard(http, self._prefix)

    async def act(
        self,
        action: dict,
        screenshot_after: bool = True,
        screenshot_delay_ms: int = 100,
    ) -> ActResult:
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
            return ActResult(screenshot=resp.content)
        return ActResult(data=resp.json())

    async def exec_ssh(self, command: str, timeout: int = 120) -> ExecResult:
        resp = await self._http.post(
            f"{self._prefix}/exec", json={"command": command}, timeout=timeout
        )
        resp.raise_for_status()
        return ExecResult.from_dict(resp.json())

    async def exec_ax(self, command: str, timeout: int = 120) -> ExecResult:
        """Async version of exec_ax — see MacOSSandbox.exec_ax for details."""
        resp = await self._http.post(
            f"{self._prefix}/exec_ax", json={"command": command}, timeout=timeout
        )
        resp.raise_for_status()
        return ExecResult.from_dict(resp.json())

    async def upload_dir(self, local_dir: str | Path, remote_dir: str) -> None:
        local_dir = Path(local_dir)
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode="w:gz") as tar:
            for item in local_dir.rglob("*"):
                tar.add(str(item), arcname=str(item.relative_to(local_dir)))
        tmp = f"/tmp/_use_computer_upload_{self.sandbox_id[-8:]}.tar.gz"
        await self.upload_bytes(buf.getvalue(), tmp)
        cmd = f'mkdir -p "{remote_dir}" && tar xzf {tmp} -C "{remote_dir}" && rm -f {tmp}'
        await self.exec_ssh(cmd)

    async def download_dir(self, remote_dir: str, local_dir: str | Path) -> None:
        local_dir = Path(local_dir)
        local_dir.mkdir(parents=True, exist_ok=True)
        # List files via exec, then download each
        result = await self.exec_ssh(f'find "{remote_dir}" -type f')
        for line in result.stdout.strip().splitlines():
            line = line.strip()
            if not line:
                continue
            rel = line[len(remote_dir) :].lstrip("/")
            local_path = local_dir / rel
            await self.download_file(line, local_path)


class AsyncIOSSandbox(AsyncSandbox):
    """Async iOS simulator sandbox."""

    def __init__(self, sandbox_id: str, http: httpx.AsyncClient):
        super().__init__(sandbox_id, SandboxType.IOS, http)
        self.input = AsyncInput(http, self._prefix)
        self.apps = AsyncApps(http, self._prefix)
        self.environment = AsyncEnvironment(http, self._prefix)

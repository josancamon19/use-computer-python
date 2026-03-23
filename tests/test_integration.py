"""Integration tests for the mmini SDK against the gateway + mock computer-server.

Requires:
  - Gateway running on localhost:8080
  - Mock computer-server on localhost:9000
  - A warm slot registered via POST /debug/register-slot
"""

from __future__ import annotations

import json
import subprocess
import sys
import textwrap
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Thread

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from mmini import Mmini


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

GATEWAY_PORT = 18080
MOCK_PORT = 19000


class MockComputerServer(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"path": self.path, "method": "GET"}).encode())

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length).decode() if length else ""
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"path": self.path, "method": "POST", "body": body}).encode())

    def do_DELETE(self):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps({"path": self.path, "method": "DELETE"}).encode())

    def log_message(self, *_args):
        pass


@pytest.fixture(scope="session")
def mock_server():
    server = HTTPServer(("127.0.0.1", MOCK_PORT), MockComputerServer)
    t = Thread(target=server.serve_forever, daemon=True)
    t.start()
    yield server
    server.shutdown()


@pytest.fixture(scope="session")
def gateway(mock_server):
    gateway_dir = Path(__file__).parent.parent.parent / "gateway"
    config_path = gateway_dir / "config.json"

    # Write a test config pointing to mock server
    test_config = {
        "listen_addr": f":{GATEWAY_PORT}",
        "mac_minis": [
            {
                "id": "test-mac",
                "ip": "127.0.0.1",
                "lume_port": 7777,
                "vm_ports": [MOCK_PORT],
            }
        ],
        "health_check_interval": "60s",
        "session_idle_timeout": "30m",
    }
    test_config_path = gateway_dir / "config.test.json"
    test_config_path.write_text(json.dumps(test_config))

    # Build gateway
    subprocess.run(
        ["/opt/homebrew/bin/go", "build", "-o", str(gateway_dir / "gateway-test"), "./cmd/gateway/"],
        cwd=str(gateway_dir),
        check=True,
    )

    # Start gateway
    proc = subprocess.Popen(
        [str(gateway_dir / "gateway-test"), "--config", str(test_config_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    time.sleep(1)

    # Register a mock warm slot
    import httpx

    httpx.post(
        f"http://127.0.0.1:{GATEWAY_PORT}/debug/register-slot",
        json={
            "mac_mini_id": "test-mac",
            "mac_mini_ip": "127.0.0.1",
            "lume_port": 7777,
            "vm_name": "test-vm",
            "vm_ip": "127.0.0.1",
            "vm_comp_port": MOCK_PORT,
            "vm_vnc_port": 8006,
        },
    )

    yield proc

    proc.terminate()
    proc.wait()
    test_config_path.unlink(missing_ok=True)
    (gateway_dir / "gateway-test").unlink(missing_ok=True)


def _register_slot():
    import httpx

    httpx.post(
        f"http://127.0.0.1:{GATEWAY_PORT}/debug/register-slot",
        json={
            "mac_mini_id": "test-mac",
            "mac_mini_ip": "127.0.0.1",
            "lume_port": 7777,
            "vm_name": "test-vm",
            "vm_ip": "127.0.0.1",
            "vm_comp_port": MOCK_PORT,
            "vm_vnc_port": 8006,
        },
    )


@pytest.fixture()
def client(gateway):
    _register_slot()
    c = Mmini(base_url=f"http://127.0.0.1:{GATEWAY_PORT}")
    yield c
    c.close()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestSandboxLifecycle:
    def test_create_and_destroy(self, client: Mmini):
        sandbox = client.create()
        assert sandbox.sandbox_id.startswith("sb-")
        assert sandbox.vnc_url
        assert sandbox.ssh_url
        sandbox.close()

    def test_get_sandbox(self, client: Mmini):
        sandbox = client.create()
        fetched = client.get(sandbox.sandbox_id)
        assert fetched.sandbox_id == sandbox.sandbox_id
        sandbox.close()

    def test_context_manager(self, client: Mmini):
        with client.create() as sandbox:
            assert sandbox.sandbox_id.startswith("sb-")


class TestMouse:
    def test_click(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.click(100, 200)
            assert result["path"] == "/mouse/click"
            body = json.loads(result["body"])
            assert body["x"] == 100
            assert body["y"] == 200

    def test_click_right(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.click(100, 200, "right")
            body = json.loads(result["body"])
            assert body["button"] == "right"

    def test_click_double(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.click(100, 200, double=True)
            body = json.loads(result["body"])
            assert body["double"] is True

    def test_move(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.move(300, 400)
            assert result["path"] == "/mouse/move"

    def test_drag(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.drag(10, 20, 30, 40)
            body = json.loads(result["body"])
            assert body["startX"] == 10
            assert body["endX"] == 30

    def test_scroll(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.scroll(100, 200, "up", 5)
            body = json.loads(result["body"])
            assert body["direction"] == "up"
            assert body["amount"] == 5

    def test_get_position(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.mouse.get_position()
            assert result["path"] == "/mouse/position"


class TestKeyboard:
    def test_type(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.keyboard.type("hello")
            body = json.loads(result["body"])
            assert body["text"] == "hello"

    def test_type_with_delay(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.keyboard.type("slow", delay=50)
            body = json.loads(result["body"])
            assert body["delay"] == 50

    def test_press(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.keyboard.press("Return")
            body = json.loads(result["body"])
            assert body["key"] == "Return"

    def test_press_with_modifiers(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.keyboard.press("c", modifiers=["cmd"])
            body = json.loads(result["body"])
            assert body["modifiers"] == ["cmd"]

    def test_hotkey(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.keyboard.hotkey("cmd+v")
            body = json.loads(result["body"])
            assert body["keys"] == "cmd+v"


class TestScreenshot:
    def test_full_screen(self, client: Mmini):
        with client.create() as sandbox:
            data = sandbox.screenshot.take_full_screen()
            assert len(data) > 0

    def test_region(self, client: Mmini):
        with client.create() as sandbox:
            data = sandbox.screenshot.take_region(x=0, y=0, width=800, height=600)
            assert len(data) > 0

    def test_compressed(self, client: Mmini):
        with client.create() as sandbox:
            data = sandbox.screenshot.take_compressed(format="jpeg", quality=80)
            assert len(data) > 0


class TestDisplay:
    def test_get_info(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.display.get_info()
            assert result["path"] == "/display/info"

    def test_get_windows(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.display.get_windows()
            assert result["path"] == "/display/windows"


class TestRecording:
    def test_start(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.recording.start("test")
            body = json.loads(result["body"])
            assert body["name"] == "test"

    def test_list(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.recording.list_all()
            assert result["path"] == "/recordings"


class TestAct:
    def test_act_no_screenshot(self, client: Mmini):
        with client.create() as sandbox:
            result = sandbox.act(
                action={"type": "click", "x": 100, "y": 200},
                screenshot_after=False,
            )
            body = json.loads(result["body"])
            assert body["action"]["type"] == "click"
            assert body["screenshot_after"] is False

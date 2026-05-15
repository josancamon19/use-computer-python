from __future__ import annotations

from enum import Enum

import httpx

from use_computer.models import ActionResult


class Button(str, Enum):
    """Hardware buttons available on iOS simulators."""

    HOME = "home"
    LOCK = "lock"
    SIRI = "siri"
    SIDE_BUTTON = "side-button"
    APPLE_PAY = "apple-pay"


class RemoteButton(str, Enum):
    """Apple TV remote-style controls."""

    UP = "up"
    DOWN = "down"
    LEFT = "left"
    RIGHT = "right"
    SELECT = "select"
    MENU = "menu"
    HOME = "home"
    PLAY_PAUSE = "play-pause"


class Key(int, Enum):
    """Common HID keycodes for iOS simulator key presses."""

    RETURN = 40
    BACKSPACE = 42
    TAB = 43
    SPACE = 44
    ESCAPE = 41
    DELETE = 76
    UP = 82
    DOWN = 81
    LEFT = 80
    RIGHT = 79
    F1 = 58
    F2 = 59
    F3 = 60
    F4 = 61
    F5 = 62
    F6 = 63
    F7 = 64
    F8 = 65
    F9 = 66
    F10 = 67


class Input:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def tap(self, x: float, y: float) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/tap", json={"x": x, "y": y})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def swipe(self, from_x: float, from_y: float, to_x: float, to_y: float) -> ActionResult:
        resp = self._http.post(
            f"{self._prefix}/swipe",
            json={"fromX": from_x, "fromY": from_y, "toX": to_x, "toY": to_y},
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def type_text(self, text: str) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/type", json={"text": text})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def press_button(self, button: Button | str) -> ActionResult:
        """Press a hardware button. Use Button enum for type safety."""
        val = button.value if isinstance(button, Button) else button
        resp = self._http.post(f"{self._prefix}/button", json={"button": val})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def press_key(self, keycode: Key | int) -> ActionResult:
        """Press a key by HID keycode. Use Key enum for common keys."""
        val = keycode.value if isinstance(keycode, Key) else keycode
        resp = self._http.post(f"{self._prefix}/key", json={"keycode": val})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def press_remote(self, button: RemoteButton | str) -> ActionResult:
        """Press an Apple TV remote-style control."""
        val = button.value if isinstance(button, RemoteButton) else button
        resp = self._http.post(f"{self._prefix}/remote", json={"button": val})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())


class AsyncInput:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def tap(self, x: float, y: float) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/tap", json={"x": x, "y": y})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def swipe(self, from_x: float, from_y: float, to_x: float, to_y: float) -> ActionResult:
        resp = await self._http.post(
            f"{self._prefix}/swipe",
            json={"fromX": from_x, "fromY": from_y, "toX": to_x, "toY": to_y},
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def type_text(self, text: str) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/type", json={"text": text})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def press_button(self, button: Button | str) -> ActionResult:
        """Press a hardware button. Use Button enum for type safety."""
        val = button.value if isinstance(button, Button) else button
        resp = await self._http.post(f"{self._prefix}/button", json={"button": val})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def press_key(self, keycode: Key | int) -> ActionResult:
        """Press a key by HID keycode. Use Key enum for common keys."""
        val = keycode.value if isinstance(keycode, Key) else keycode
        resp = await self._http.post(f"{self._prefix}/key", json={"keycode": val})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def press_remote(self, button: RemoteButton | str) -> ActionResult:
        """Press an Apple TV remote-style control."""
        val = button.value if isinstance(button, RemoteButton) else button
        resp = await self._http.post(f"{self._prefix}/remote", json={"button": val})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

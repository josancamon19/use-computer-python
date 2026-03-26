from __future__ import annotations

import httpx

from mmini.models import ActionResult


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

    def press_button(self, button: str) -> ActionResult:
        """Press a hardware button: HOME, LOCK, SIRI, APPLE_PAY, SIDE_BUTTON."""
        resp = self._http.post(f"{self._prefix}/button", json={"button": button})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def press_key(self, keycode: int) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/key", json={"keycode": keycode})
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

    async def press_button(self, button: str) -> ActionResult:
        """Press a hardware button: HOME, LOCK, SIRI, APPLE_PAY, SIDE_BUTTON."""
        resp = await self._http.post(f"{self._prefix}/button", json={"button": button})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def press_key(self, keycode: int) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/key", json={"keycode": keycode})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

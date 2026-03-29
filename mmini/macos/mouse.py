from __future__ import annotations

import httpx

from mmini.models import ActionResult, CursorPosition


class Mouse:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def click(self, x: int, y: int, button: str = "left", double: bool = False) -> ActionResult:
        resp = self._http.post(
            f"{self._prefix}/mouse/click",
            json={"x": x, "y": y, "button": button, "double": double},
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def move(self, x: int, y: int) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/mouse/move", json={"x": x, "y": y})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left"
    ) -> ActionResult:
        resp = self._http.post(
            f"{self._prefix}/mouse/drag",
            json={
                "startX": start_x,
                "startY": start_y,
                "endX": end_x,
                "endY": end_y,
                "button": button,
            },
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> ActionResult:
        resp = self._http.post(
            f"{self._prefix}/mouse/scroll",
            json={"x": x, "y": y, "direction": direction, "amount": amount},
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def get_position(self) -> CursorPosition:
        resp = self._http.get(f"{self._prefix}/mouse/position")
        resp.raise_for_status()
        return CursorPosition.from_dict(resp.json())


class AsyncMouse:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def click(
        self, x: int, y: int, button: str = "left", double: bool = False
    ) -> ActionResult:
        resp = await self._http.post(
            f"{self._prefix}/mouse/click",
            json={"x": x, "y": y, "button": button, "double": double},
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def move(self, x: int, y: int) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/mouse/move", json={"x": x, "y": y})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def drag(
        self, start_x: int, start_y: int, end_x: int, end_y: int, button: str = "left"
    ) -> ActionResult:
        resp = await self._http.post(
            f"{self._prefix}/mouse/drag",
            json={
                "startX": start_x,
                "startY": start_y,
                "endX": end_x,
                "endY": end_y,
                "button": button,
            },
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def scroll(
        self, x: int, y: int, direction: str = "down", amount: int = 3
    ) -> ActionResult:
        resp = await self._http.post(
            f"{self._prefix}/mouse/scroll",
            json={"x": x, "y": y, "direction": direction, "amount": amount},
        )
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def get_position(self) -> CursorPosition:
        resp = await self._http.get(f"{self._prefix}/mouse/position")
        resp.raise_for_status()
        return CursorPosition.from_dict(resp.json())

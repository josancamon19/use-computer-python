from __future__ import annotations

import httpx


class Screenshot:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def take_full_screen(self, show_cursor: bool = False) -> bytes:
        resp = self._http.get(f"{self._prefix}/screenshot", params={"show_cursor": show_cursor})
        resp.raise_for_status()
        return resp.content

    def take_region(self, x: int, y: int, width: int, height: int) -> bytes:
        resp = self._http.get(
            f"{self._prefix}/screenshot/region",
            params={"x": x, "y": y, "width": width, "height": height},
        )
        resp.raise_for_status()
        return resp.content

    def take_compressed(self, format: str = "jpeg", quality: int = 80, scale: float | None = None) -> bytes:
        params: dict = {"format": format, "quality": quality}
        if scale is not None:
            params["scale"] = scale
        resp = self._http.get(f"{self._prefix}/screenshot/compressed", params=params)
        resp.raise_for_status()
        return resp.content


class AsyncScreenshot:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def take_full_screen(self, show_cursor: bool = False) -> bytes:
        resp = await self._http.get(f"{self._prefix}/screenshot", params={"show_cursor": show_cursor})
        resp.raise_for_status()
        return resp.content

    async def take_region(self, x: int, y: int, width: int, height: int) -> bytes:
        resp = await self._http.get(
            f"{self._prefix}/screenshot/region",
            params={"x": x, "y": y, "width": width, "height": height},
        )
        resp.raise_for_status()
        return resp.content

    async def take_compressed(self, format: str = "jpeg", quality: int = 80, scale: float | None = None) -> bytes:
        params: dict = {"format": format, "quality": quality}
        if scale is not None:
            params["scale"] = scale
        resp = await self._http.get(f"{self._prefix}/screenshot/compressed", params=params)
        resp.raise_for_status()
        return resp.content

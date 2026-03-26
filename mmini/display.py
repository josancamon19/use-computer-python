from __future__ import annotations

from typing import Any

import httpx

from mmini.models import DisplayInfo


class Display:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def get_info(self) -> DisplayInfo:
        resp = self._http.get(f"{self._prefix}/display/info")
        resp.raise_for_status()
        return DisplayInfo.from_dict(resp.json())

    def get_windows(self) -> list[dict[str, Any]]:
        resp = self._http.get(f"{self._prefix}/display/windows")
        resp.raise_for_status()
        return resp.json()


class AsyncDisplay:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def get_info(self) -> DisplayInfo:
        resp = await self._http.get(f"{self._prefix}/display/info")
        resp.raise_for_status()
        return DisplayInfo.from_dict(resp.json())

    async def get_windows(self) -> list[dict[str, Any]]:
        resp = await self._http.get(f"{self._prefix}/display/windows")
        resp.raise_for_status()
        return resp.json()

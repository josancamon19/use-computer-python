from __future__ import annotations

import httpx

from use_computer.models import ActionResult


class Environment:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def set_location(self, lat: float, lon: float) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/location", json={"lat": lat, "lon": lon})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def clear_location(self) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/location", json={"action": "clear"})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def set_appearance(self, mode: str) -> ActionResult:
        """Set dark or light mode."""
        resp = self._http.post(f"{self._prefix}/appearance", json={"mode": mode})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())


class AsyncEnvironment:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def set_location(self, lat: float, lon: float) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/location", json={"lat": lat, "lon": lon})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def clear_location(self) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/location", json={"action": "clear"})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def set_appearance(self, mode: str) -> ActionResult:
        """Set dark or light mode."""
        resp = await self._http.post(f"{self._prefix}/appearance", json={"mode": mode})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

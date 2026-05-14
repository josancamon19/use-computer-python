from __future__ import annotations

import httpx

from use_computer.models import ActionResult


class Apps:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def open_url(self, url: str) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/openurl", json={"url": url})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def install(self, app_path: str) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/install", json={"appPath": app_path})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def launch(self, bundle_id: str) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/launch", json={"bundleId": bundle_id})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def terminate(self, bundle_id: str) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/terminate", json={"bundleId": bundle_id})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())


class AsyncApps:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def open_url(self, url: str) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/openurl", json={"url": url})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def install(self, app_path: str) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/install", json={"appPath": app_path})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def launch(self, bundle_id: str) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/launch", json={"bundleId": bundle_id})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def terminate(self, bundle_id: str) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/terminate", json={"bundleId": bundle_id})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

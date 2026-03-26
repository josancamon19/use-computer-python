from __future__ import annotations

import httpx

from mmini.models import ActionResult


class Keyboard:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def type(self, text: str, delay: int | None = None) -> ActionResult:
        payload: dict = {"text": text}
        if delay is not None:
            payload["delay"] = delay
        resp = self._http.post(f"{self._prefix}/keyboard/type", json=payload)
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def press(self, key: str, modifiers: list[str] | None = None) -> ActionResult:
        payload: dict = {"key": key}
        if modifiers:
            payload["modifiers"] = modifiers
        resp = self._http.post(f"{self._prefix}/keyboard/press", json=payload)
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    def hotkey(self, keys: str) -> ActionResult:
        resp = self._http.post(f"{self._prefix}/keyboard/hotkey", json={"keys": keys})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())


class AsyncKeyboard:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def type(self, text: str, delay: int | None = None) -> ActionResult:
        payload: dict = {"text": text}
        if delay is not None:
            payload["delay"] = delay
        resp = await self._http.post(f"{self._prefix}/keyboard/type", json=payload)
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def press(self, key: str, modifiers: list[str] | None = None) -> ActionResult:
        payload: dict = {"key": key}
        if modifiers:
            payload["modifiers"] = modifiers
        resp = await self._http.post(f"{self._prefix}/keyboard/press", json=payload)
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

    async def hotkey(self, keys: str) -> ActionResult:
        resp = await self._http.post(f"{self._prefix}/keyboard/hotkey", json={"keys": keys})
        resp.raise_for_status()
        return ActionResult.from_dict(resp.json())

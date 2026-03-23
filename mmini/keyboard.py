from __future__ import annotations

import httpx


class Keyboard:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def type(self, text: str, delay: int | None = None) -> dict:
        payload: dict = {"text": text}
        if delay is not None:
            payload["delay"] = delay
        resp = self._http.post(
            f"{self._prefix}/keyboard/type",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def press(
        self,
        key: str,
        modifiers: list[str] | None = None,
    ) -> dict:
        payload: dict = {"key": key}
        if modifiers:
            payload["modifiers"] = modifiers
        resp = self._http.post(
            f"{self._prefix}/keyboard/press",
            json=payload,
        )
        resp.raise_for_status()
        return resp.json()

    def hotkey(self, keys: str) -> dict:
        resp = self._http.post(
            f"{self._prefix}/keyboard/hotkey",
            json={"keys": keys},
        )
        resp.raise_for_status()
        return resp.json()

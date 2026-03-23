from __future__ import annotations

from typing import Any

import httpx


class Recording:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def start(self, name: str | None = None) -> dict:
        payload: dict = {}
        if name:
            payload["name"] = name
        resp = self._http.post(f"{self._prefix}/recording/start", json=payload)
        resp.raise_for_status()
        return resp.json()

    def stop(self, recording_id: str) -> dict:
        resp = self._http.post(f"{self._prefix}/recording/stop", json={"id": recording_id})
        resp.raise_for_status()
        return resp.json()

    def list_all(self) -> list[dict[str, Any]]:
        resp = self._http.get(f"{self._prefix}/recordings")
        resp.raise_for_status()
        return resp.json()

    def get(self, recording_id: str) -> dict:
        resp = self._http.get(f"{self._prefix}/recordings/{recording_id}")
        resp.raise_for_status()
        return resp.json()

    def download(self, recording_id: str, local_path: str) -> None:
        with self._http.stream("GET", f"{self._prefix}/recordings/{recording_id}/download") as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=65536):
                    f.write(chunk)

    def delete(self, recording_id: str) -> None:
        resp = self._http.delete(f"{self._prefix}/recordings/{recording_id}")
        resp.raise_for_status()


class AsyncRecording:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def start(self, name: str | None = None) -> dict:
        payload: dict = {}
        if name:
            payload["name"] = name
        resp = await self._http.post(f"{self._prefix}/recording/start", json=payload)
        resp.raise_for_status()
        return resp.json()

    async def stop(self, recording_id: str) -> dict:
        resp = await self._http.post(f"{self._prefix}/recording/stop", json={"id": recording_id})
        resp.raise_for_status()
        return resp.json()

    async def list_all(self) -> list[dict[str, Any]]:
        resp = await self._http.get(f"{self._prefix}/recordings")
        resp.raise_for_status()
        return resp.json()

    async def get(self, recording_id: str) -> dict:
        resp = await self._http.get(f"{self._prefix}/recordings/{recording_id}")
        resp.raise_for_status()
        return resp.json()

    async def download(self, recording_id: str, local_path: str) -> None:
        async with self._http.stream("GET", f"{self._prefix}/recordings/{recording_id}/download") as resp:
            resp.raise_for_status()
            with open(local_path, "wb") as f:
                async for chunk in resp.aiter_bytes(chunk_size=65536):
                    f.write(chunk)

    async def delete(self, recording_id: str) -> None:
        resp = await self._http.delete(f"{self._prefix}/recordings/{recording_id}")
        resp.raise_for_status()

from __future__ import annotations

import httpx

from use_computer.models import AccessibilityTree


class Accessibility:
    def __init__(self, http: httpx.Client, prefix: str):
        self._http = http
        self._prefix = prefix

    def get_tree(self, *, best_effort: bool = True) -> AccessibilityTree:
        params = {"best_effort": "1"} if best_effort else None
        resp = self._http.get(f"{self._prefix}/display/windows", params=params)
        if best_effort and resp.status_code >= 400:
            return AccessibilityTree(available=False, error=resp.text)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "available" in data:
            return AccessibilityTree.from_dict(data)
        return AccessibilityTree(available=True, tree=data)


class AsyncAccessibility:
    def __init__(self, http: httpx.AsyncClient, prefix: str):
        self._http = http
        self._prefix = prefix

    async def get_tree(self, *, best_effort: bool = True) -> AccessibilityTree:
        params = {"best_effort": "1"} if best_effort else None
        resp = await self._http.get(f"{self._prefix}/display/windows", params=params)
        if best_effort and resp.status_code >= 400:
            return AccessibilityTree(available=False, error=resp.text)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, dict) and "available" in data:
            return AccessibilityTree.from_dict(data)
        return AccessibilityTree(available=True, tree=data)

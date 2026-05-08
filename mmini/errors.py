"""Typed exceptions for mmini SDK errors that callers should catch by class
rather than by parsing HTTP status codes or response bodies."""

from __future__ import annotations

import httpx


class MminiError(Exception):
    """Base class for typed mmini SDK errors."""


class PlatformNotSupportedError(MminiError):
    """Raised when an action is not supported on the sandbox's platform.

    The gateway returns 501 with a JSON body of the shape:
        {"error": "...", "sandbox_type": "ios", "action": "POST /mouse/click",
         "hint": "use POST /tap"}
    """

    def __init__(self, action: str, sandbox_type: str, hint: str, response: httpx.Response):
        self.action = action
        self.sandbox_type = sandbox_type
        self.hint = hint
        self.response = response
        super().__init__(f"{action} not supported on {sandbox_type} sandbox: {hint}")


def _raise_if_unsupported(resp: httpx.Response) -> None:
    """httpx event hook: convert 501-with-platform-shape into a typed error.

    httpx hooks run before the body is read on streaming responses, so we
    only touch the body when the status is 501 — anything else is left
    untouched for raise_for_status() to handle normally.
    """
    if resp.status_code != 501:
        return
    try:
        resp.read()
        data = resp.json()
    except Exception:
        return
    if not isinstance(data, dict) or data.get("error") != "not supported on iOS sandbox":
        return
    raise PlatformNotSupportedError(
        action=data.get("action", ""),
        sandbox_type=data.get("sandbox_type", ""),
        hint=data.get("hint", ""),
        response=resp,
    )


async def _araise_if_unsupported(resp: httpx.Response) -> None:
    if resp.status_code != 501:
        return
    try:
        await resp.aread()
        data = resp.json()
    except Exception:
        return
    if not isinstance(data, dict) or data.get("error") != "not supported on iOS sandbox":
        return
    raise PlatformNotSupportedError(
        action=data.get("action", ""),
        sandbox_type=data.get("sandbox_type", ""),
        hint=data.get("hint", ""),
        response=resp,
    )

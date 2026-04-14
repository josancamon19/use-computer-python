"""Single retry layer for all mmini SDK HTTP calls.

Retries are handled at the httpx transport level so they apply
automatically to every request — no per-method wrappers needed.
"""

from __future__ import annotations

import asyncio
import logging
import time

import httpx

_log = logging.getLogger("mmini.retry")

RETRYABLE_EXCEPTIONS = (httpx.TimeoutException, httpx.ConnectError, httpx.ReadError, httpx.WriteError)
RETRYABLE_STATUS_CODES = frozenset({500, 502, 503, 504, 529})
NO_RETRY_PATTERNS = ("not found", "connection refused")
MAX_RETRIES = 3
RETRY_DELAY = 2.0


def _is_retryable_body(body: str) -> bool:
    lower = body.lower()
    return not any(p in lower for p in NO_RETRY_PATTERNS)


class RetryTransport(httpx.BaseTransport):
    def __init__(self, transport: httpx.BaseTransport):
        self._transport = transport

    def handle_request(self, request: httpx.Request) -> httpx.Response:
        resp = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = self._transport.handle_request(request)
            except RETRYABLE_EXCEPTIONS as exc:
                if attempt == MAX_RETRIES:
                    raise
                _log.warning("retry %d/%d: %s %s → %s", attempt + 1, MAX_RETRIES, request.method, request.url, type(exc).__name__)
                time.sleep(RETRY_DELAY)
                continue

            if resp.status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES:
                return resp

            body = ""
            try:
                resp.read()
                body = resp.text[:500]
            except Exception:
                pass
            if not _is_retryable_body(body):
                return resp

            _log.warning("retry %d/%d: %s %s → %d %s", attempt + 1, MAX_RETRIES, request.method, request.url, resp.status_code, body)
            resp.close()
            time.sleep(RETRY_DELAY)
        return resp  # type: ignore[return-value]

    def close(self) -> None:
        self._transport.close()


class AsyncRetryTransport(httpx.AsyncBaseTransport):
    def __init__(self, transport: httpx.AsyncBaseTransport):
        self._transport = transport

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        resp = None
        for attempt in range(MAX_RETRIES + 1):
            try:
                resp = await self._transport.handle_async_request(request)
            except RETRYABLE_EXCEPTIONS as exc:
                if attempt == MAX_RETRIES:
                    raise
                _log.warning("retry %d/%d: %s %s → %s", attempt + 1, MAX_RETRIES, request.method, request.url, type(exc).__name__)
                await asyncio.sleep(RETRY_DELAY)
                continue

            if resp.status_code not in RETRYABLE_STATUS_CODES or attempt == MAX_RETRIES:
                return resp

            body = ""
            try:
                await resp.aread()
                body = resp.text[:500]
            except Exception:
                pass
            if not _is_retryable_body(body):
                return resp

            _log.warning("retry %d/%d: %s %s → %d %s", attempt + 1, MAX_RETRIES, request.method, request.url, resp.status_code, body)
            await resp.aclose()
            await asyncio.sleep(RETRY_DELAY)
        return resp  # type: ignore[return-value]

    async def aclose(self) -> None:
        await self._transport.aclose()

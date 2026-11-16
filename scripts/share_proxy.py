"""One origin for a shared development `serve` (CONTRIBUTING.md, 画面の共有): `/v1/*` to the API, the rest to Web.

The browser then sees the workspace and the API on one origin, so the production cookie (SameSite=Strict) and
the API's exact Origin check stay unchanged. Bodies stream through untouched and are never logged; each new
browser address (Origin, or the forwarded host) is printed once, so the owner can see the one a preview
pane uses and pass it to `serve --share-origin`.

    uv run uvicorn --app-dir scripts share_proxy:app --host 127.0.0.1 --port 8080
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import httpx

API = os.environ.get("CYTELLECT_SHARE_API", "http://localhost:8000")
WEB = os.environ.get("CYTELLECT_SHARE_WEB", "http://localhost:3000")
# Hop-by-hop headers (RFC 9110 §7.6.1) end at this proxy; the rest pass unchanged, Origin and Cookie included.
HOP_BY_HOP = {b"connection", b"keep-alive", b"proxy-authenticate", b"proxy-authorization", b"te", b"trailer",
              b"transfer-encoding", b"upgrade", b"host"}
_client: httpx.AsyncClient | None = None
_origins: set[str] = set()

Scope = dict[str, Any]
Receive = Callable[[], Awaitable[dict[str, Any]]]
Send = Callable[[dict[str, Any]], Awaitable[None]]


def upstream(path: str) -> str:
    return API if path == "/v1" or path.startswith("/v1/") else WEB


async def _body(receive: Receive) -> AsyncIterator[bytes]:
    while True:
        message = await receive()
        if message["type"] == "http.disconnect":
            return
        yield message.get("body", b"")
        if not message.get("more_body", False):
            return


async def app(scope: Scope, receive: Receive, send: Send) -> None:
    global _client
    if scope["type"] == "lifespan":
        while (await receive())["type"] != "lifespan.shutdown":
            await send({"type": "lifespan.startup.complete"})
        await send({"type": "lifespan.shutdown.complete"})
        return
    if scope["type"] != "http":
        return
    if _client is None:
        _client = httpx.AsyncClient(timeout=None, follow_redirects=False)
        _client.headers.clear()  # send only the browser's headers: no added Accept-Encoding or User-Agent
    headers = [(name, value) for name, value in scope["headers"] if name.lower() not in HOP_BY_HOP]
    seen = {name.lower(): value.decode("latin-1") for name, value in scope["headers"]
            if name.lower() in {b"origin", b"host", b"x-forwarded-host", b"x-forwarded-proto"}}
    address = seen.get(b"origin") or (seen.get(b"x-forwarded-proto", "http") + "://"
                                       + seen.get(b"x-forwarded-host", seen.get(b"host", "")))
    if address not in _origins:
        _origins.add(address)
        print(f"share: browser address {address}", file=sys.stderr, flush=True)
    url = upstream(scope["path"]) + scope["raw_path"].decode("latin-1")
    if scope.get("query_string"):
        url += "?" + scope["query_string"].decode("latin-1")
    has_body = scope["method"] not in {"GET", "HEAD"}
    request = _client.build_request(scope["method"], url, headers=headers,
                                    content=_body(receive) if has_body else None)
    response = await _client.send(request, stream=True)
    try:
        await send({"type": "http.response.start", "status": response.status_code,
                    "headers": [(name, value) for name, value in response.headers.raw
                                if name.lower() not in HOP_BY_HOP]})
        async for chunk in response.aiter_raw():
            await send({"type": "http.response.body", "body": chunk, "more_body": True})
        await send({"type": "http.response.body", "body": b"", "more_body": False})
    finally:
        await response.aclose()

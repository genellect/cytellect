"""Reject unauthorized/oversized uploads before multipart parsing or disk spooling."""
from __future__ import annotations

import asyncio
import re
import time

from starlette.formparsers import MultiPartException
from starlette.requests import Request
from starlette.responses import JSONResponse

from .db import digest, fields, sessions, workspaces

UPLOAD_ROUTE = re.compile(r"^/v1/workspaces/([^/]+)/(fields|region-fields|tables)$")


class UploadGuardMiddleware:
    """Streaming guard for one API process; no buffering of the complete body.

    File multipart parsing happens before FastAPI endpoint dependencies. This
    outer guard therefore authenticates and checks ownership before even the
    first receive(). Starlette closes open spools on the raised multipart error.
    """
    def __init__(self, app, store, settings, *, concurrency=2,
                 field_body_limit=257 * 1024**2, table_body_limit=8 * 1024**2 + 65536,
                 idle_timeout_seconds=30):
        self.app = app
        self.store = store
        self.settings = settings
        self.concurrency = concurrency
        self.field_limit = field_body_limit
        self.table_limit = table_body_limit
        self.idle_timeout = idle_timeout_seconds
        self.active = 0

    async def __call__(self, scope, receive, send):
        route = UPLOAD_ROUTE.fullmatch(scope.get("path", ""))
        if scope["type"] != "http" or scope.get("method") != "POST" or route is None:
            await self.app(scope, receive, send)
            return

        async def reject(status, code):
            await JSONResponse({"detail": code}, status_code=status,
                               headers={"Cache-Control": "no-store"})(scope, receive, send)

        request = Request(scope)
        token = request.cookies.get(self.settings.cookie_name)
        session = self.store.one(sessions, digest=digest(token)) if token else None
        now = time.time()
        if not session or session["revoked"] or session["expires"] <= now:
            await reject(401, "session_required")
            return
        wid, kind = route.groups()
        workspace = self.store.one(workspaces, id=wid)
        if (not workspace or workspace["owner"] != session["owner"] or workspace["deleted"]
                or workspace["expires"] <= now):
            await reject(404, "workspace_not_found")
            return
        if self.settings.demo:
            await reject(403, "demo_uploads_disabled")
            return
        if kind != "tables" and len(self.store.rows(fields, workspace_id=wid)) >= self.settings.max_fields:
            await reject(413, "workspace_limit")
            return
        remaining = self.settings.max_upload_bytes - workspace["bytes"]
        if remaining <= 0:
            await reject(413, "workspace_limit")
            return
        if not request.headers.get("content-type", "").lower().startswith("multipart/form-data;"):
            await reject(415, "multipart_required")
            return
        limit = min(self.table_limit if kind == "tables" else self.field_limit, remaining + 1024**2)
        length = request.headers.get("content-length")
        if length is not None:
            try:
                declared = int(length)
                if declared < 0:
                    raise ValueError
            except ValueError:
                await reject(400, "invalid_content_length")
                return
            if declared > limit:
                await reject(413, "upload_body_limit")
                return
        # There is no await between reading and changing this per-process counter.
        if self.active >= self.concurrency:
            await reject(429, "upload_concurrency_limit")
            return
        self.active += 1
        received = 0
        failure = None
        replacement_sent = False

        async def bounded_receive():
            nonlocal received, failure
            try:
                async with asyncio.timeout(self.idle_timeout):
                    message = await receive()
            except TimeoutError:
                failure = (408, "upload_read_timeout")
                raise MultiPartException("upload_read_timeout") from None
            if message["type"] == "http.request":
                received += len(message.get("body", b""))
                if received > limit:
                    failure = (413, "upload_body_limit")
                    # Raising within the parser stream triggers its spool cleanup.
                    raise MultiPartException("upload_body_limit")
            return message

        async def bounded_send(message):
            nonlocal replacement_sent
            if failure:
                if message["type"] == "http.response.start" and not replacement_sent:
                    replacement_sent = True
                    await reject(*failure)
                return
            await send(message)

        try:
            await self.app(scope, bounded_receive, bounded_send)
        except MultiPartException:
            if failure is None:
                raise
        finally:
            self.active -= 1
        if failure and not replacement_sent:
            await reject(*failure)

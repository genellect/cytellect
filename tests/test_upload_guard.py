import asyncio
import time
from types import SimpleNamespace

import pytest
from cytellect_api.db import digest
from cytellect_api.upload_guard import UploadGuardMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


class AuthStore:
    def __init__(self):
        self.token = "fixture-session-token"
        self.session = {"owner": "owner", "expires": time.time() + 100, "revoked": False}
        self.workspace = {"owner": "owner", "expires": time.time() + 100, "deleted": False, "bytes": 0}

    def one(self, table, **filters):
        if table.name == "sessions":
            return self.session if filters.get("digest") == digest(self.token) else None
        return self.workspace if filters.get("id") == "workspace" else None

    def rows(self, table, **filters):
        return []

    def workspace_is_live(self, record, now=None):
        return bool(record and not record["deleted"] and record["expires"] > (time.time() if now is None else now))


def context(auth=True, extra=(), route="fields"):
    headers = [(b"content-type", b"multipart/form-data; boundary=BOUNDARY")]
    if auth:
        headers.append((b"cookie", b"session=fixture-session-token"))
    headers += extra
    return {"type": "http", "method": "POST", "path": f"/v1/workspaces/workspace/{route}",
            "headers": headers, "query_string": b"", "http_version": "1.1", "scheme": "http",
            "server": ("test", 80), "client": ("test", 1)}


def settings():
    return SimpleNamespace(cookie_name="session", demo=False, max_fields=100, max_upload_bytes=2**31)


async def invoke(app, scope, chunks=()):
    messages, reads = [], 0
    iterator = iter(chunks)

    async def receive():
        nonlocal reads
        reads += 1
        try:
            data, more = next(iterator)
        except StopIteration:
            raise AssertionError("Request body was read unexpectedly") from None
        return {"type": "http.request", "body": data, "more_body": more}

    async def send(message):
        messages.append(message)

    await app(scope, receive, send)
    return messages, reads


async def never_called(scope, receive, send):
    raise AssertionError("Unauthorized body reached multipart parsing")


def status(messages):
    return next(m["status"] for m in messages if m["type"] == "http.response.start")


@pytest.mark.parametrize("case,expected", [("no-session", 401), ("foreign", 404), ("deleted", 404),
                                          ("expired", 404), ("oversized-header", 413)])
@pytest.mark.parametrize("route", ["fields", "region-fields", "region-fields/ome", "tables"])
def test_rejects_before_first_body_read(case, expected, route):
    store = AuthStore()
    scope = context(auth=case != "no-session", route=route)
    if case == "foreign":
        store.workspace["owner"] = "someone-else"
    if case == "deleted":
        store.workspace["deleted"] = True
    if case == "expired":
        store.workspace["expires"] = 0
    if case == "oversized-header":
        scope["headers"].append((b"content-length", b"999999999"))
    guard = UploadGuardMiddleware(never_called, store, settings())
    messages, reads = asyncio.run(invoke(guard, scope))
    assert status(messages) == expected and reads == 0 and guard.active == 0


@pytest.mark.parametrize("case,expected", [("no-session", 401), ("oversized-header", 413), ("demo", 403)])
def test_intake_inspection_is_guarded_like_a_field_upload_without_a_workspace(case, expected):
    store = AuthStore()
    # The inspection names no workspace, so a missing one is no reason to refuse it.
    store.workspace = None
    scope = context(auth=case != "no-session") | {"path": "/v1/intake/inspect"}
    if case == "oversized-header":
        scope["headers"].append((b"content-length", str(257 * 1024**2 + 1).encode()))
    configured = settings()
    configured.demo = case == "demo"
    guard = UploadGuardMiddleware(never_called, store, configured)
    messages, reads = asyncio.run(invoke(guard, scope))
    assert status(messages) == expected and reads == 0 and guard.active == 0


def test_intake_inspection_has_no_workspace_quota():
    async def accept(scope, receive, send):
        await JSONResponse({"ok": True})(scope, receive, send)

    store = AuthStore()
    store.workspace = None
    configured = settings()
    configured.max_upload_bytes = 0
    scope = context(extra=[(b"content-length", b"4")]) | {"path": "/v1/intake/inspect"}
    messages, _ = asyncio.run(invoke(UploadGuardMiddleware(accept, store, configured), scope, [(b"body", False)]))
    assert status(messages) == 200


@pytest.mark.parametrize("false_small_length", [False, True])
def test_stream_limit_closes_actual_spooled_files(monkeypatch, false_small_length):
    import starlette.formparsers as parsers

    opened = []
    original = parsers.SpooledTemporaryFile

    def tracked(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(parsers, "SpooledTemporaryFile", tracked)

    async def parse(scope, receive, send):
        async with Request(scope, receive).form() as form:
            await JSONResponse({"files": len(form)})(scope, receive, send)

    prefix = b'--BOUNDARY\r\nContent-Disposition: form-data; name="file"; filename="public-test.csv"\r\nContent-Type: application/octet-stream\r\n\r\n'
    chunks = [(prefix, True)] + [(b"a" * 65536, True)] * 20
    scope = context(extra=[(b"content-length", b"1")] if false_small_length else [])
    guard = UploadGuardMiddleware(parse, AuthStore(), settings(), field_body_limit=1024**2 + 1000)
    messages, reads = asyncio.run(invoke(guard, scope, chunks))
    assert status(messages) == 413
    assert reads < len(chunks)
    assert opened and all(file.closed for file in opened)
    assert guard.active == 0


def test_concurrency_cap_rejects_third_request_without_consuming_it():
    async def scenario():
        started, release = asyncio.Event(), asyncio.Event()
        count = 0

        async def held(scope, receive, send):
            nonlocal count
            count += 1
            if count == 2:
                started.set()
            await release.wait()
            await JSONResponse({"ok": True})(scope, receive, send)

        guard = UploadGuardMiddleware(held, AuthStore(), settings())
        first = asyncio.create_task(invoke(guard, context()))
        second = asyncio.create_task(invoke(guard, context()))
        await started.wait()
        messages, reads = await invoke(guard, context())
        assert status(messages) == 429 and reads == 0
        release.set()
        await first
        await second
        assert guard.active == 0

    asyncio.run(scenario())


def test_valid_multipart_reaches_parser_and_frees_slot():
    async def parse(scope, receive, send):
        async with Request(scope, receive).form() as form:
            assert await form["file"].read() == b"1,2"
            await JSONResponse({"ok": True}, status_code=201)(scope, receive, send)

    body = b'--BOUNDARY\r\nContent-Disposition: form-data; name="file"; filename="public.csv"\r\n\r\n1,2\r\n--BOUNDARY--\r\n'
    guard = UploadGuardMiddleware(parse, AuthStore(), settings())
    messages, reads = asyncio.run(invoke(guard, context(route="tables"), [(body, False)]))
    assert status(messages) == 201 and reads == 1 and guard.active == 0


def test_private_tmp_is_explicit_even_if_tempfile_was_previously_cached(tmp_path, monkeypatch):
    import os
    import tempfile
    from pathlib import Path

    from cytellect_api.config import Settings, configure_private_tmp
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path / "old"))
    for variable in ("TMPDIR", "TEMP", "TMP", "MPLCONFIGDIR"):
        monkeypatch.setenv(variable, str(tmp_path / "old"))
    private = tmp_path / "runtime"
    directory = configure_private_tmp(Settings(private))
    with tempfile.NamedTemporaryFile() as handle:
        assert Path(handle.name).parent == directory == private / "tmp"
    assert tempfile.gettempdir() == str(directory)
    assert Path(os.environ["MPLCONFIGDIR"]) == directory / "matplotlib"
    assert (directory / "matplotlib").is_dir()


@pytest.mark.parametrize("route", ["fields", "region-fields", "region-fields/ome", "tables"])
def test_demo_mode_rejects_every_upload_before_first_body_read(route):
    demo = settings()
    demo.demo = True
    guard = UploadGuardMiddleware(never_called, AuthStore(), demo)
    messages, reads = asyncio.run(invoke(guard, context(route=route)))
    assert status(messages) == 403 and reads == 0 and guard.active == 0


def test_every_route_that_accepts_a_file_is_guarded(tmp_path):
    """A new upload route cannot be added without the guard: the guard's pattern is checked against the app."""
    from cytellect_api.app import create_app
    from cytellect_api.config import Settings
    from cytellect_api.upload_guard import INTAKE_ROUTE, UPLOAD_ROUTE
    from fastapi.routing import APIRoute

    app = create_app(Settings(tmp_path / "private", app_origin="http://localhost:3000", secure_cookies=False))
    uploads = [route.path for route in app.routes
               if isinstance(route, APIRoute) and route.body_field is not None
               and any(getattr(param.field_info, "media_type", "") == "multipart/form-data"
                       for param in route.dependant.body_params)]
    assert len(uploads) >= 5
    # The inspection before registration (#284 W4) names no workspace: the guard matches it by its own path.
    assert INTAKE_ROUTE in uploads
    for path in uploads:
        assert path == INTAKE_ROUTE or UPLOAD_ROUTE.fullmatch(path.replace("{wid}", "workspace")), path

import asyncio
import json
import time
from types import SimpleNamespace

import pytest
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import digest
from cytellect_api.upload_guard import UPLOAD_ROUTE, UploadGuardMiddleware
from fastapi.testclient import TestClient
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
@pytest.mark.parametrize("route", ["fields", "region-fields", "region-fields/ome", "tables", "region-fields/ome\n"])
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


def test_ome_region_upload_keeps_stream_cap_and_closes_spools_even_at_quota(monkeypatch):
    import starlette.formparsers as parsers

    opened = []
    original = parsers.SpooledTemporaryFile

    def tracked(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(parsers, "SpooledTemporaryFile", tracked)

    async def parse(scope, receive, send):
        async with Request(scope, receive).form():
            await JSONResponse({"parsed": True})(scope, receive, send)

    # Like the generic region upload, a retry of an accepted OME upload must
    # reach the endpoint's key lookup at quota; the body cap still applies.
    store, configuration = AuthStore(), settings()
    store.workspace["bytes"] = configuration.max_upload_bytes
    guard = UploadGuardMiddleware(parse, store, configuration, field_body_limit=1000)
    prefix = b'--BOUNDARY\r\nContent-Disposition: form-data; name="ome"; filename="public.ome.tif"\r\n\r\n'
    messages, reads = asyncio.run(invoke(guard, context(route="region-fields/ome"),
                                        [(prefix, True), (b"x" * 1200, True)]))
    assert status(messages) == 413 and reads == 2
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


def api_with_session(tmp_path, **options):
    app = create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False, **options))
    client = TestClient(app)
    headers = {"origin": "http://test", "x-cytellect-request": "1"}
    assert client.post("/v1/invitations/redeem", headers=headers,
                       json={"token": app.state.store.invite()}).status_code == 200
    return app, client, headers


def test_every_multipart_route_of_the_api_is_guarded(tmp_path):
    app, _, _ = api_with_session(tmp_path)
    multipart = [path for path, item in app.openapi()["paths"].items()
                 if "multipart/form-data" in item.get("post", {}).get("requestBody", {}).get("content", {})]
    assert "/v1/workspaces/{wid}/region-fields/ome" in multipart
    unguarded = [path for path in multipart if UPLOAD_ROUTE.match(path.replace("{wid}", "workspace")) is None]
    assert unguarded == []


@pytest.mark.parametrize("route", ["fields", "region-fields", "region-fields/ome", "tables"])
@pytest.mark.parametrize("case,expected", [("no-session", (401, "session_required")),
                                          ("foreign", (404, "workspace_not_found")),
                                          ("demo", (403, "demo_uploads_disabled")),
                                          ("oversized-header", (413, "upload_body_limit"))])
def test_api_rejects_upload_before_first_body_read(tmp_path, route, case, expected):
    app, client, headers = api_with_session(tmp_path, demo=case == "demo")
    wid = client.post("/v1/workspaces", headers=headers, json={"title": "Guard fixture"}).json()["id"]
    if case == "foreign":
        client = TestClient(app)
        assert client.post("/v1/invitations/redeem", headers=headers,
                           json={"token": app.state.store.invite()}).status_code == 200
    cookie = "; ".join(f"{name}={value}" for name, value in client.cookies.items())
    scope = context(auth=False, route=route, extra=[(key.encode(), value.encode()) for key, value in headers.items()])
    scope["path"] = f"/v1/workspaces/{wid}/{route}"
    if case != "no-session":
        scope["headers"].append((b"cookie", cookie.encode()))
    if case == "oversized-header":
        scope["headers"].append((b"content-length", b"999999999"))
    messages, reads = asyncio.run(invoke(app, scope))
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    assert (status(messages), json.loads(body)["detail"]) == expected and reads == 0


@pytest.mark.parametrize("route", ["fields", "region-fields", "region-fields/ome", "tables"])
@pytest.mark.parametrize("shape", ["trailing-newline", "root-path"])
def test_api_guard_matches_every_path_the_router_dispatches(tmp_path, route, shape):
    # The router accepts a decoded trailing newline (`%0A`) and strips a mount
    # prefix; the guard must see the same route or the body is parsed first.
    app, _, headers = api_with_session(tmp_path)
    scope = context(auth=False, route=route, extra=[(key.encode(), value.encode()) for key, value in headers.items()])
    if shape == "trailing-newline":
        scope["path"] += "\n"
    else:
        scope["root_path"], scope["path"] = "/api", "/api" + scope["path"]
    messages, reads = asyncio.run(invoke(app, scope))
    body = b"".join(m.get("body", b"") for m in messages if m["type"] == "http.response.body")
    assert (status(messages), json.loads(body)["detail"]) == (401, "session_required") and reads == 0


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

"""Sign-in to the cloud service from a local installation, against a fake cloud server.

No real service is contacted: a loopback HTTP server implements the documented
cloud contract (/v1/auth/*, /v1/cellpose/*, /v1/proposals). The addresses are
reserved example domains, never a researcher's.
"""
from __future__ import annotations

import json
import os
import secrets
import stat
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import numpy as np
import pytest
from cytellect_analysis import cellpose_engine as engine
from cytellect_analysis.cellpose_engine import (
    CellposeDetectorSpec,
    detect_cellpose,
    remote_target,
    runtime_status,
)
from cytellect_api import local as local_module
from cytellect_api import proposals
from cytellect_api.cloud_account import ACCOUNT_FILE, SCHEMA, CloudAccount
from cytellect_api.config import Settings
from cytellect_api.local import WorkerSupervisor, create_local_app
from fastapi.testclient import TestClient
from test_cellpose_remote import FakeRunner, image, load_server
from test_proposals import CONTEXT

ORIGIN = "http://127.0.0.1:8765"
HEADERS = {"Origin": ORIGIN, "X-Cytellect-Request": "1", "Sec-Fetch-Site": "same-origin"}
ALLOWED = "researcher@example.org"
UNAPPROVED = "newcomer@example.org"


class FakeCloud:
    """The cloud contract's auth routes, with switchable failures."""

    def __init__(self):
        self.allowed, self.pending, self.revoked = {ALLOWED}, set(), set()
        self.codes: dict[str, str] = {}
        self.attempts: dict[str, int] = {}
        self.tokens: dict[str, str] = {}
        self.requests: list[tuple[str, str, dict, bytes]] = []
        self.status_reply: tuple[int, dict] | None = None
        self.health: list[tuple[int, dict]] = []
        self.rate_limited = False
        self.code_reply: tuple[int, dict] | None = None
        self.verify_reply: tuple[int, dict] | None = None
        cloud = self

        class Handler(BaseHTTPRequestHandler):
            def reply(self, status, body=None):
                data = b"" if body is None else json.dumps(body).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def bearer(self):
                value = self.headers.get("Authorization", "")
                return cloud.tokens.get(value[7:]) if value.startswith("Bearer ") else None

            def record(self):
                length = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(length) if length else b""
                cloud.requests.append((self.command, self.path, dict(self.headers), body))
                return json.loads(body) if body else {}

            def do_GET(self):
                self.record()
                path = urlsplit(self.path)
                if path.path == "/v1/auth/status":
                    if cloud.status_reply:
                        return self.reply(*cloud.status_reply)
                    email = self.bearer()
                    if email is None:
                        return self.reply(401, {"error": "auth_required"})
                    if email in cloud.revoked:
                        return self.reply(403, {"error": "revoked"})
                    return self.reply(200, {"state": "allowed", "email": email,
                                            "limits": {"gpu_seconds_month": 3600, "proposal_usd_month": 5},
                                            "usage": {"gpu_seconds": 120, "proposal_usd": 0.4},
                                            "resets_at": "2026-11-01T00:00:00Z", "internal_note": "dropped"})
                if path.path == "/v1/auth/request":
                    email = parse_qs(path.query)["email"][0]
                    state = ("revoked" if email in cloud.revoked else "allowed" if email in cloud.allowed
                             else "pending_approval" if email in cloud.pending else "none")
                    return self.reply(200, {"state": state})
                if path.path == "/v1/cellpose/health":
                    if self.bearer() is None:
                        return self.reply(401, {"error": "auth_required"})
                    status, body = cloud.health.pop(0) if cloud.health else (200, {"status": "ok"})
                    return self.reply(status, body)
                self.reply(404, {"error": "not_found"})

            def do_POST(self):
                body = self.record()
                if self.path == "/v1/auth/code":
                    if cloud.rate_limited:
                        return self.reply(429, {"error": "rate_limited", "retry_after_seconds": 42})
                    if cloud.code_reply:
                        return self.reply(*cloud.code_reply)
                    email = body["email"]
                    if email in cloud.revoked:
                        return self.reply(200, {"state": "revoked"})
                    if email not in cloud.allowed:
                        cloud.pending.add(email)
                        return self.reply(200, {"state": "pending_approval"})
                    cloud.codes[email], cloud.attempts[email] = "123456", 5
                    return self.reply(200, {"state": "code_sent", "retry_after_seconds": 60})
                if self.path == "/v1/auth/verify":
                    email = body["email"]
                    if cloud.verify_reply:
                        return self.reply(*cloud.verify_reply)
                    if body["code"] != cloud.codes.get(email):
                        cloud.attempts[email] -= 1
                        return self.reply(400, {"error": "code_invalid", "attempts_left": cloud.attempts[email]})
                    token = "dev_" + secrets.token_urlsafe(32)
                    cloud.tokens[token] = email
                    return self.reply(200, {"device_token": token, "email": email,
                                            "expires_at": "2099-01-01T00:00:00Z"})
                if self.path == "/v1/auth/logout":
                    value = self.headers.get("Authorization", "")
                    cloud.tokens.pop(value[7:], None)
                    return self.reply(204)
                self.reply(404, {"error": "not_found"})

            def log_message(self, *_args):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()


@pytest.fixture
def cloud(monkeypatch):
    value = FakeCloud()
    monkeypatch.setenv("CYTELLECT_CLOUD_URL", value.url)
    for name in ("CYTELLECT_CELLPOSE_REMOTE_URL", "CYTELLECT_CELLPOSE_REMOTE_TOKEN", "CYTELLECT_CELLPOSE_REMOTE_SECRET"):
        monkeypatch.delenv(name, raising=False)
    yield value
    value.httpd.shutdown()
    value.httpd.server_close()


def local(tmp_path):
    web = tmp_path / "web"
    web.mkdir(parents=True, exist_ok=True)
    (web / "index.html").write_text("<h1>public static shell</h1>", encoding="utf-8")
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False)
    app = create_local_app(settings, web, 8765)
    client = TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 45000))
    assert client.post("/v1/local/session", headers=HEADERS).status_code == 200
    return client, app, settings


def signed_in(client, cloud):
    assert client.post("/v1/account/code", json={"email": "  Researcher@Example.org "}, headers=HEADERS).json() == {
        "state": "code_sent", "email": ALLOWED, "retry_after_seconds": 60}
    response = client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS)
    assert response.json() == {"state": "allowed", "email": ALLOWED}
    return next(iter(cloud.tokens))


def test_sign_in_stores_the_token_user_only_and_never_returns_it(tmp_path, cloud):
    client, app, settings = local(tmp_path)
    responses = [client.get("/v1/account", headers=HEADERS)]
    assert responses[0].json() == {"state": "signed_out"}
    responses.append(client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS))
    wrong = client.post("/v1/account/verify", json={"code": "000000"}, headers=HEADERS)
    assert wrong.status_code == 400 and wrong.json() == {"detail": "account_code_invalid", "attempts_left": 4}
    assert client.get("/v1/account").json()["attempts_left"] == 4
    responses.append(client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS))
    token = next(iter(cloud.tokens))
    assert cloud.requests[-1][3] and json.loads(cloud.requests[-1][3])["device_name"].startswith("Cytellect (")
    view = client.get("/v1/account")
    responses.append(view)
    # Only documented fields reach the browser; unknown service fields are dropped.
    assert view.json() == {"state": "allowed", "email": ALLOWED,
                           "limits": {"gpu_seconds_month": 3600, "proposal_usd_month": 5},
                           "usage": {"gpu_seconds": 120, "proposal_usd": 0.4}, "resets_at": "2026-11-01T00:00:00Z"}
    stored = settings.data_dir / ACCOUNT_FILE
    record = json.loads(stored.read_text(encoding="utf-8"))
    assert record["schema"] == SCHEMA and record["device_token"] == token and record["base_url"] == cloud.url
    if os.name != "nt":
        assert stat.S_IMODE(stored.stat().st_mode) == 0o600
    assert not list(settings.data_dir.glob(".cloud-account.json.*"))
    responses.append(client.post("/v1/account/logout", headers=HEADERS))
    assert responses[-1].json() == {"state": "signed_out"}
    assert ("POST", "/v1/auth/logout") in [(m, p) for m, p, *_ in cloud.requests]
    assert cloud.tokens == {} and not stored.exists()
    assert client.get("/v1/account").json() == {"state": "signed_out"}
    for response in responses:
        assert token not in response.text and "device_token" not in response.text


def test_unapproved_address_waits_and_the_banner_learns_of_approval(tmp_path, cloud):
    client, _, _ = local(tmp_path)
    pending = client.post("/v1/account/code", json={"email": UNAPPROVED}, headers=HEADERS).json()
    assert pending["state"] == "pending_approval" and pending["email"] == UNAPPROVED
    assert isinstance(pending["requested_at"], float)
    assert client.get("/v1/account").json() == pending
    # Local analysis continues while approval is pending.
    assert client.get("/v1/workspaces").status_code == 200
    cloud.allowed.add(UNAPPROVED)
    assert client.get("/v1/account").json() == {**pending, "approved": True}
    assert client.post("/v1/account/code", json={"email": UNAPPROVED}, headers=HEADERS).json()["state"] == "code_sent"
    assert client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS).json()["state"] == "allowed"


def test_revocation_expiry_and_offline_end_only_the_cloud_features(tmp_path, cloud, monkeypatch):
    client, _, settings = local(tmp_path)
    token = signed_in(client, cloud)
    cloud.httpd.shutdown()
    cloud.httpd.server_close()
    assert client.get("/v1/account").json() == {"state": "offline", "email": ALLOWED}
    assert json.loads((settings.data_dir / ACCOUNT_FILE).read_text())["device_token"] == token
    assert client.get("/v1/workspaces").status_code == 200

    revived = FakeCloud()
    revived.tokens[token] = ALLOWED
    revived.revoked.add(ALLOWED)
    record = json.loads((settings.data_dir / ACCOUNT_FILE).read_text())
    record["base_url"] = revived.url
    (settings.data_dir / ACCOUNT_FILE).write_text(json.dumps(record))
    monkeypatch.setenv("CYTELLECT_CLOUD_URL", revived.url)
    try:
        assert client.get("/v1/account").json() == {"state": "revoked", "email": ALLOWED}
        assert "device_token" not in json.loads((settings.data_dir / ACCOUNT_FILE).read_text())
        assert client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS).json() == {
            "state": "revoked", "email": ALLOWED}
        revived.revoked.clear()
        signed_in_again = client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS)
        assert signed_in_again.status_code == 200
    finally:
        revived.httpd.shutdown()
        revived.httpd.server_close()


def test_expired_login_asks_to_sign_in_again(tmp_path, cloud):
    client, _, settings = local(tmp_path)
    signed_in(client, cloud)
    cloud.status_reply = (401, {"error": "auth_required"})
    assert client.get("/v1/account").json() == {"state": "expired", "email": ALLOWED}
    assert "device_token" not in json.loads((settings.data_dir / ACCOUNT_FILE).read_text())
    cloud.status_reply = None
    record = json.loads((settings.data_dir / ACCOUNT_FILE).read_text())
    (settings.data_dir / ACCOUNT_FILE).write_text(json.dumps({**record, "state": "allowed", "device_token": "x" * 40,
                                                              "expires_at": "2000-01-01T00:00:00Z"}))
    assert client.get("/v1/account").json() == {"state": "expired", "email": ALLOWED}


def test_rate_limit_invalid_input_and_service_failures_are_codes_only(tmp_path, cloud):
    client, _, _ = local(tmp_path)
    cloud.rate_limited = True
    limited = client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS)
    assert limited.status_code == 429 and limited.json() == {"detail": "account_rate_limited", "retry_after_seconds": 42}
    cloud.rate_limited = False
    assert client.post("/v1/account/code", json={"email": "not-an-address"}, headers=HEADERS).json() == {
        "detail": "account_email_invalid"}
    assert client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS).json() == {
        "detail": "account_code_not_requested"}
    client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS)
    assert client.post("/v1/account/verify", json={"code": "12a456"}, headers=HEADERS).json() == {
        "detail": "account_code_format_invalid"}
    cloud.httpd.shutdown()
    cloud.httpd.server_close()
    unreachable = client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS)
    assert unreachable.status_code == 503 and unreachable.json() == {"detail": "account_cloud_unreachable"}


@pytest.mark.parametrize(("reply", "detail"), [((400, {"error": "email_invalid"}), "account_email_invalid"),
                                               ((503, {"error": "mail_unavailable"}), "account_mail_failed"),
                                               ((502, {"error": "mail_failed"}), "account_mail_failed"),
                                               ((503, {"error": "auth_unavailable"}), "account_cloud_unavailable"),
                                               ((500, {"error": "unexpected"}), "account_cloud_failed")])
def test_documented_sign_in_failures_become_fixed_codes(tmp_path, cloud, reply, detail):
    client, _, _ = local(tmp_path)
    cloud.code_reply = reply
    response = client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS)
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize("error", ["revoked", "pending_approval"])
def test_verification_can_find_the_address_revoked_or_not_yet_approved(tmp_path, cloud, error):
    client, _, settings = local(tmp_path)
    client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS)
    cloud.verify_reply = (403, {"error": error})
    result = client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS)
    assert result.status_code == 200 and result.json()["state"] == error
    record = json.loads((settings.data_dir / ACCOUNT_FILE).read_text())
    assert record["state"] == error and "device_token" not in record


def test_account_routes_need_the_local_session_and_csrf_header(tmp_path, cloud):
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("<h1>shell</h1>", encoding="utf-8")
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False)
    client = TestClient(create_local_app(settings, web, 8765), base_url=ORIGIN, client=("127.0.0.1", 45000))
    assert client.get("/v1/local/first-run").json() == {"first_run": True}
    assert client.get("/v1/account").status_code == 401
    assert client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS).status_code == 401
    client.post("/v1/local/session", headers=HEADERS)
    assert client.post("/v1/account/code", json={"email": ALLOWED},
                       headers={"Origin": ORIGIN, "Sec-Fetch-Site": "same-origin"}).status_code == 403
    assert client.post("/v1/account/code", json={"email": ALLOWED},
                       headers={**HEADERS, "Origin": "https://attacker.example"}).status_code == 403
    assert not cloud.requests
    client.post("/v1/workspaces", json={"title": "synthetic"}, headers=HEADERS)
    assert client.get("/v1/local/first-run").json() == {"first_run": False}


def test_gpu_warm_up_waits_through_503_and_reports_quota_and_revocation(tmp_path, cloud):
    slept: list[float] = []
    account = CloudAccount(tmp_path, sleep=slept.append)
    assert account.start_gpu() == {"state": "unconfigured"}
    client, app, _ = local(tmp_path / "app")
    signed_in(client, cloud)
    account = CloudAccount(app.state.cloud_account.store.root, sleep=slept.append)
    cloud.health = [(503, {}), (503, {}), (200, {"status": "ok"})]
    assert account.start_gpu() == {"state": "starting"}
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "ready"} and slept == [5.0, 10.0]
    health = [entry for entry in cloud.requests if entry[1] == "/v1/cellpose/health"]
    assert len(health) == 3 and all(entry[2]["Authorization"].startswith("Bearer dev_") for entry in health)
    # A recent ready state is reused instead of calling the GPU again.
    calls = len(cloud.requests)
    assert account.start_gpu() == {"state": "ready"} and len(cloud.requests) == calls
    account._gpu["state"] = "idle"
    cloud.health = [(429, {"error": "quota_exceeded", "resets_at": "2026-11-01T00:00:00Z"})]
    account.start_gpu()
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "quota_exceeded", "resets_at": "2026-11-01T00:00:00Z"}
    account._gpu["state"] = "idle"
    cloud.health = [(403, {"error": "revoked"})]
    account.start_gpu()
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "revoked"}
    # The browser route reports the same states and never the token.
    started = client.post("/v1/account/gpu", headers=HEADERS)
    assert started.status_code == 200 and "dev_" not in started.text
    app.state.cloud_account._gpu_thread.join(5)
    assert client.get("/v1/account/gpu").json()["state"] in {"ready", "quota_exceeded", "revoked"}


def test_gpu_warm_up_gives_up_after_its_bound_and_on_network_failure(tmp_path, cloud, monkeypatch):
    clock = [1000.0]
    client, app, _ = local(tmp_path)
    signed_in(client, cloud)
    account = CloudAccount(app.state.cloud_account.store.root, clock=lambda: clock[0],
                           sleep=lambda seconds: clock.__setitem__(0, clock[0] + seconds))
    cloud.health = [(503, {})] * 100
    account.start_gpu()
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "timeout"}
    assert len([entry for entry in cloud.requests if entry[1] == "/v1/cellpose/health"]) < 30
    cloud.httpd.shutdown()
    cloud.httpd.server_close()
    account._gpu["state"] = "idle"
    account.start_gpu()
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "offline"}


def account_file(path: Path, base: str, token: str = "dev_" + "a" * 40, state: str = "allowed") -> Path:
    path.write_text(json.dumps({"schema": SCHEMA, "state": state, "email": ALLOWED, "base_url": base,
                                "device_token": token}), encoding="utf-8")
    return path


def test_cellpose_remote_precedence_explicit_then_account_then_local(tmp_path, monkeypatch):
    for name in ("CYTELLECT_CELLPOSE_REMOTE_URL", "CYTELLECT_CELLPOSE_REMOTE_TOKEN", "CYTELLECT_CELLPOSE_REMOTE_SECRET",
                 "CYTELLECT_CLOUD_ACCOUNT_FILE"):
        monkeypatch.delenv(name, raising=False)
    assert remote_target() is None
    path = account_file(tmp_path / ACCOUNT_FILE, "https://cloud.example")
    monkeypatch.setenv("CYTELLECT_CLOUD_ACCOUNT_FILE", str(path))
    assert remote_target() == ("https://cloud.example/v1/cellpose", {"Authorization": "Bearer dev_" + "a" * 40})
    # Explicit configuration (local.20 installs, CI, development) keeps working unchanged.
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_URL", "https://gpu.example")
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_TOKEN", "wk-test.ws-test")
    assert remote_target() == ("https://gpu.example", {"Authorization": "Bearer wk-test.ws-test"})
    monkeypatch.delenv("CYTELLECT_CELLPOSE_REMOTE_URL")
    monkeypatch.delenv("CYTELLECT_CELLPOSE_REMOTE_TOKEN")
    for state in ("revoked", "expired", "pending_approval"):
        account_file(path, "https://cloud.example", state=state)
        assert remote_target() is None
    account_file(path, "http://cloud.example")
    assert runtime_status()["error"] == "cellpose_remote_url_invalid"
    account_file(path, "https://cloud.example", token="short")
    assert remote_target() is None
    target = account_file(tmp_path / "target.json", "https://cloud.example")
    path.unlink()
    path.symlink_to(target)
    assert remote_target() is None


@pytest.fixture
def cloud_gpu(monkeypatch):
    """The cloud relay in front of the scientific server: /v1/cellpose/<route>, Bearer device token."""
    server_module = load_server()
    runner = FakeRunner()
    monkeypatch.setattr(server_module, "load_runner", lambda: runner)
    service = server_module.Service(Path("/model/cpsam_v2"), require_gpu=False)
    base = server_module.handler_for(service, None)
    state = {"token": "dev_" + secrets.token_urlsafe(24), "replies": [], "paths": []}

    class Relay(base):
        def do_POST(self):
            state["paths"].append(self.path)
            if self.headers.get("Authorization") != "Bearer " + state["token"]:
                return self.error(401, "auth_required")
            if state["replies"]:
                status, code = state["replies"].pop(0)
                self.rfile.read(int(self.headers["Content-Length"]))
                return self.error(status, code)
            if not self.path.startswith("/v1/cellpose/"):
                return self.error(404, "not_found")
            self.path = self.path[len("/v1/cellpose"):]
            return super().do_POST()

    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Relay)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    for name in ("CYTELLECT_CELLPOSE_REMOTE_URL", "CYTELLECT_CELLPOSE_REMOTE_TOKEN", "CYTELLECT_CELLPOSE_REMOTE_SECRET"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(engine.time, "sleep", lambda _seconds: None)
    state.update(url=f"http://127.0.0.1:{httpd.server_port}", runner=runner)
    yield state
    httpd.shutdown()
    httpd.server_close()


def test_signed_in_cellpose_uses_the_cloud_relay_with_the_same_verification(cloud_gpu, tmp_path, monkeypatch):
    path = account_file(tmp_path / ACCOUNT_FILE, cloud_gpu["url"], token=cloud_gpu["token"])
    monkeypatch.setenv("CYTELLECT_CLOUD_ACCOUNT_FILE", str(path))
    cloud_gpu["replies"] = [(503, "starting")]
    labels, info = detect_cellpose(image(), CellposeDetectorSpec(), tmp_path / "attempt")
    assert np.array_equal(labels, (image() > 100).astype(np.uint32))
    assert cloud_gpu["paths"] == ["/v1/cellpose/v1/cellpose", "/v1/cellpose/v1/cellpose"]
    # Same receipt contract as an explicit service: hashes checked, GPU device recorded.
    assert info["runtime"]["device"] == "cuda"
    assert info["runtime"]["execution_backend"] == {"kind": "remote", "host": "127.0.0.1", "requested_compute_device": "cpu"}
    assert info["runtime"]["service"]["model_sha256"] == engine.MODEL_SHA256
    assert cloud_gpu["token"] not in json.dumps(info)


@pytest.mark.parametrize(("reply", "code"), [((403, "revoked"), "cellpose_remote_rejected"),
                                             ((401, "auth_required"), "cellpose_remote_rejected"),
                                             ((429, "quota_exceeded"), "cellpose_remote_failed")])
def test_signed_in_cellpose_failures_are_final_and_never_echo_the_token(cloud_gpu, tmp_path, monkeypatch, reply, code):
    path = account_file(tmp_path / ACCOUNT_FILE, cloud_gpu["url"], token=cloud_gpu["token"])
    monkeypatch.setenv("CYTELLECT_CLOUD_ACCOUNT_FILE", str(path))
    cloud_gpu["replies"] = [reply]
    with pytest.raises(ValueError) as error:
        detect_cellpose(image(), CellposeDetectorSpec(), tmp_path / "attempt")
    assert str(error.value) == code and cloud_gpu["token"] not in str(error.value)
    assert len(cloud_gpu["paths"]) == 1 and cloud_gpu["runner"].calls == []


@pytest.mark.parametrize(("reply", "code"), [((503, "gpu_service_disabled"), "cellpose_remote_unavailable"),
                                             ((502, "gpu_upstream_invalid"), "cellpose_remote_failed")])
def test_a_disabled_gateway_is_not_waited_on(cloud_gpu, tmp_path, monkeypatch, reply, code):
    path = account_file(tmp_path / ACCOUNT_FILE, cloud_gpu["url"], token=cloud_gpu["token"])
    monkeypatch.setenv("CYTELLECT_CLOUD_ACCOUNT_FILE", str(path))
    cloud_gpu["replies"] = [reply]
    with pytest.raises(ValueError, match=code):
        detect_cellpose(image(), CellposeDetectorSpec(), tmp_path / "attempt")
    assert len(cloud_gpu["paths"]) == 1


def test_warm_up_reports_a_global_quota_and_a_disabled_service(tmp_path, cloud):
    client, app, _ = local(tmp_path)
    signed_in(client, cloud)
    account = CloudAccount(app.state.cloud_account.store.root, sleep=lambda _seconds: None)
    cloud.health = [(429, {"error": "quota_exceeded", "resets_at": "2026-11-01T00:00:00Z", "scope": "global"})]
    account.start_gpu()
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "quota_exceeded", "resets_at": "2026-11-01T00:00:00Z", "scope": "global"}
    account._gpu["state"] = "idle"
    cloud.health = [(503, {"error": "gpu_service_disabled"})]
    account.start_gpu()
    account._gpu_thread.join(5)
    assert account.gpu() == {"state": "disabled"}


def test_a_busy_gpu_is_waited_on_like_a_starting_one(cloud_gpu, tmp_path, monkeypatch):
    path = account_file(tmp_path / ACCOUNT_FILE, cloud_gpu["url"], token=cloud_gpu["token"])
    monkeypatch.setenv("CYTELLECT_CLOUD_ACCOUNT_FILE", str(path))
    cloud_gpu["replies"] = [(503, "gpu_busy"), (503, "gpu_busy")]
    labels, _ = detect_cellpose(image(), CellposeDetectorSpec(), tmp_path / "attempt")
    assert int(labels.max()) == 1 and len(cloud_gpu["paths"]) == 3


def test_warm_up_says_the_gpu_is_busy_while_it_waits(tmp_path, cloud):
    client, app, _ = local(tmp_path)
    signed_in(client, cloud)
    seen: list[dict] = []
    account = CloudAccount(app.state.cloud_account.store.root, sleep=lambda _seconds: seen.append(account.gpu()))
    cloud.health = [(503, {"error": "gpu_busy"}), (200, {"status": "ok"})]
    account.start_gpu()
    account._gpu_thread.join(5)
    assert seen == [{"state": "starting", "busy": True}] and account.gpu() == {"state": "ready"}


def test_warm_up_keeps_waiting_while_the_gateway_reports_the_gpu_starting(tmp_path, cloud):
    from cytellect_api import cloud_account

    assert cloud_account.HEALTH_TIMEOUT_SECONDS > 25  # The gateway holds a health request up to 25 s.
    client, app, _ = local(tmp_path)
    signed_in(client, cloud)
    seen: list[dict] = []
    account = CloudAccount(app.state.cloud_account.store.root, sleep=lambda _seconds: seen.append(account.gpu()))
    starting = (503, {"error": "gpu_starting", "retry_after_seconds": 5})
    cloud.health = [starting, starting, (200, {"status": "ok"})]
    account.start_gpu()
    account._gpu_thread.join(5)
    assert seen == [{"state": "starting"}, {"state": "starting"}] and account.gpu() == {"state": "ready"}


def test_too_many_codes_or_wrong_codes_wait_up_to_a_day(tmp_path, cloud):
    client, _, _ = local(tmp_path)
    client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS)
    cloud.verify_reply = (429, {"error": "rate_limited", "retry_after_seconds": 20 * 3600})
    limited = client.post("/v1/account/verify", json={"code": "123456"}, headers=HEADERS)
    assert limited.status_code == 429 and limited.json() == {"detail": "account_rate_limited", "retry_after_seconds": 72000}
    cloud.code_reply = (429, {"error": "rate_limited", "retry_after_seconds": 86400})
    assert client.post("/v1/account/code", json={"email": ALLOWED}, headers=HEADERS).json() == {
        "detail": "account_rate_limited", "retry_after_seconds": 86400}
    assert client.get("/v1/workspaces").status_code == 200


def test_launcher_names_the_account_file_for_the_worker(tmp_path, monkeypatch):
    captured = {}

    def refuse(_command, **options):
        captured.update(options["env"])
        raise RuntimeError("stop before starting a process")

    monkeypatch.setattr(local_module.subprocess, "Popen", refuse)
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False)
    with pytest.raises(RuntimeError):
        WorkerSupervisor(settings, lambda: None)._spawn()
    assert captured["CYTELLECT_CLOUD_ACCOUNT_FILE"] == str(settings.data_dir / ACCOUNT_FILE)
    assert not any("dev_" in value for value in captured.values())


def test_proposals_use_explicit_configuration_first_then_the_account(tmp_path):
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False)
    account = ("https://cloud.example", "dev_" + "b" * 40)

    def endpoint(value, credentials=None):
        current = proposals.effective_settings(value, credentials)
        url = proposals.service_url(current)
        return (url, current.proposal_token) if url else None

    assert endpoint(settings) is None
    assert endpoint(settings, lambda: None) is None
    assert endpoint(settings, lambda: account) == account
    with pytest.raises(ValueError, match="proposal_service_requires_https"):
        endpoint(settings, lambda: ("http://cloud.example", account[1]))
    explicit = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False,
                        proposal_url="https://proposals.example", proposal_token="operator-token-value")
    assert endpoint(explicit, lambda: account) == ("https://proposals.example", "operator-token-value")
    # An explicit URL without its token stays disabled rather than borrowing the account.
    partial = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False, proposal_url="https://p.example")
    assert endpoint(partial, lambda: account) is None


def test_proposal_request_carries_the_device_token_to_the_cloud(tmp_path, cloud):
    client, app, settings = local(tmp_path)
    token = signed_in(client, cloud)
    service = proposals.effective_settings(settings, app.state.cloud_account.credentials)
    with pytest.raises(proposals.ProposalServiceError) as error:
        proposals.request_draft(service, CONTEXT, "request-1")
    assert error.value.code == "proposal_service_unavailable"  # The fake has no /v1/proposals route.
    method, path, headers, _ = cloud.requests[-1]
    assert (method, path, headers["Authorization"]) == ("POST", "/v1/proposals", "Bearer " + token)
    client.post("/v1/account/logout", headers=HEADERS)
    with pytest.raises(proposals.ProposalServiceError) as disabled:
        proposals.request_draft(proposals.effective_settings(settings, app.state.cloud_account.credentials), CONTEXT)
    assert disabled.value.code == "proposal_service_disabled"


def test_proposal_failures_for_a_revoked_user_and_a_monthly_quota(tmp_path, monkeypatch):
    import io
    import urllib.error

    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False,
                        proposal_url="https://proposals.example", proposal_token="dev_" + "c" * 40)

    def failing(status, body):
        def open_(_request, timeout):
            raise urllib.error.HTTPError("https://proposals.example/v1/proposals", status, "failure", {},
                                         io.BytesIO(json.dumps(body).encode()))
        return open_

    for status, body, expected in [(403, {"code": "revoked"}, (503, "proposal_access_revoked")),
                                   (403, {}, (503, "proposal_service_unauthorized")),
                                   (429, {"code": "quota_exceeded", "resets_at": "2026-11-01T00:00:00Z"},
                                    (429, "proposal_quota_exhausted"))]:
        monkeypatch.setattr(proposals._OPENER, "open", failing(status, body))
        with pytest.raises(proposals.ProposalServiceError) as error:
            proposals.request_draft(settings, CONTEXT)
        assert (error.value.status, error.value.code) == expected

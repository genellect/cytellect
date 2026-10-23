"""Access-code redemption, device-token storage and its use for Cellpose and proposals."""
import http.server
import json
import os
import threading
from pathlib import Path

import pytest
from cytellect_analysis import cellpose_engine, paid_access
from cytellect_api.config import Settings
from cytellect_api.local import create_local_app
from fastapi.testclient import TestClient

ORIGIN = "http://127.0.0.1:8765"
HEADERS = {"Origin": ORIGIN, "X-Cytellect-Request": "1", "Sec-Fetch-Site": "same-origin"}
TOKEN = "device-token-0123456789abcdef"
DEVICE_ID = "ab" * 8


class AccessService:
    """A loopback stand-in for the operator's access service."""

    def __init__(self):
        self.calls, self.revoked = [], False
        service = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                service.calls.append((self.path, self.headers.get("Authorization"), body))
                if self.path == "/v1/devices":
                    ok = body == {"invitation": "valid-code-0123456789abcd"}
                    self.reply(201 if ok else 403, {"device_token": TOKEN, "device_id": DEVICE_ID} if ok
                               else {"code": "invitation_invalid"})
                elif self.path == "/v1/status":
                    if service.revoked or self.headers.get("Authorization") != f"Bearer {TOKEN}":
                        return self.reply(401, {"code": "unauthorized"})
                    self.reply(200, {"device_id": DEVICE_ID, "label": "研究室PC-1", "month": "2026-10",
                                     "cellpose": {"enabled": True, "used": 3, "limit": 200},
                                     "proposals": {"enabled": False, "used": 0, "limit": 0}})

            def reply(self, status, value):
                data = json.dumps(value).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *_args):
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self):
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def service(monkeypatch):
    access = AccessService()
    monkeypatch.setenv(paid_access.SERVICE_ENV, access.url)
    monkeypatch.setenv("NO_PROXY", "127.0.0.1")
    yield access
    access.close()


def client(tmp_path):
    web = tmp_path / "web"
    web.mkdir(exist_ok=True)
    (web / "index.html").write_text("<h1>shell</h1>", encoding="utf-8")
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False,
                        paid_access_file=tmp_path / "settings" / "paid-access.json")
    return TestClient(create_local_app(settings, web, 8765), base_url=ORIGIN, client=("127.0.0.1", 45000)), settings


def test_credential_round_trip_is_private_and_damaged_files_are_ignored(tmp_path):
    path = tmp_path / "settings" / "paid-access.json"
    paid_access.write(path, paid_access.Credential("https://access.example", TOKEN, DEVICE_ID, "PC"))
    assert paid_access.read(path) == paid_access.Credential("https://access.example", TOKEN, DEVICE_ID, "PC")
    stored = json.loads(path.read_text(encoding="utf-8"))
    if os.name == "nt":
        assert stored["token"]["protection"] == "dpapi" and TOKEN not in path.read_text(encoding="utf-8")
    else:
        assert stored["token"]["protection"] == "file" and path.stat().st_mode & 0o077 == 0
    for damaged in ("{", json.dumps({**stored, "schema": "other"}), json.dumps({**stored, "service": "http://access.example"}),
                    json.dumps({**stored, "token": {"protection": "unknown", "value": TOKEN}})):
        path.write_text(damaged, encoding="utf-8")
        assert paid_access.read(path) is None
    assert paid_access.read(None) is None and paid_access.read(tmp_path / "missing.json") is None


def test_redeemed_code_routes_cellpose_through_the_access_service_before_a_configured_one(tmp_path, monkeypatch):
    path = tmp_path / "paid-access.json"
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_URL", "https://gpu.example")
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_TOKEN", "legacy-shared-key")
    monkeypatch.setenv(paid_access.FILE_ENV, str(path))
    assert cellpose_engine._remote_target() == ("https://gpu.example", "legacy-shared-key")
    paid_access.write(path, paid_access.Credential("https://access.example", TOKEN, DEVICE_ID))
    assert cellpose_engine._remote_target() == ("https://access.example", TOKEN)
    assert cellpose_engine.remote_endpoint() == "https://access.example"
    monkeypatch.delenv("CYTELLECT_CELLPOSE_REMOTE_URL")
    paid_access.remove(path)
    assert cellpose_engine.remote_endpoint() is None


def test_proposals_use_the_redeemed_code_unless_a_service_is_configured_explicitly(tmp_path):
    path = tmp_path / "paid-access.json"
    settings = Settings(tmp_path / "private", paid_access_file=path)
    assert settings.proposal_service() == ("", "")
    paid_access.write(path, paid_access.Credential("https://access.example", TOKEN, DEVICE_ID))
    assert settings.proposal_service() == ("https://access.example", TOKEN)
    explicit = Settings(tmp_path / "private", proposal_url="https://docker.example", proposal_token="x" * 30, paid_access_file=path)
    assert explicit.proposal_service() == ("https://docker.example", "x" * 30)


def test_local_activation_status_revocation_and_removal(tmp_path, service):
    app, settings = client(tmp_path)
    assert app.get("/v1/local/paid-access").json() == {"activated": False, "service_configured": True, "reachable": None,
                                                       "revoked": False, "label": None, "month": None,
                                                       "cellpose": None, "proposals": None}
    assert app.post("/v1/local/paid-access", json={"code": "valid-code-0123456789abcd"}).status_code == 403  # CSRF
    wrong = app.post("/v1/local/paid-access", json={"code": "wrong-code-0123456789abcd"}, headers=HEADERS)
    assert (wrong.status_code, wrong.json()["detail"]) == (400, "paid_access_code_invalid")
    assert app.post("/v1/local/paid-access", json={"code": "short"}, headers=HEADERS).status_code == 400
    active = app.post("/v1/local/paid-access", json={"code": " valid-code-0123456789abcd "}, headers=HEADERS).json()
    assert active["activated"] and active["reachable"] and active["label"] == "研究室PC-1"
    assert active["cellpose"] == {"enabled": True, "used": 3, "limit": 200}
    assert paid_access.read(settings.paid_access_file).token == TOKEN
    assert TOKEN not in json.dumps(active)
    service.revoked = True
    assert app.get("/v1/local/paid-access").json()["revoked"] is True
    removed = app.delete("/v1/local/paid-access", headers=HEADERS).json()
    assert removed["activated"] is False and not Path(settings.paid_access_file).exists()


def test_activation_explains_an_unconfigured_or_unreachable_service(tmp_path, monkeypatch):
    app, _ = client(tmp_path)
    monkeypatch.delenv(paid_access.SERVICE_ENV, raising=False)
    monkeypatch.setattr(paid_access, "SERVICE_URL", "")
    response = app.post("/v1/local/paid-access", json={"code": "valid-code-0123456789abcd"}, headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (503, "paid_access_service_unconfigured")
    monkeypatch.setenv(paid_access.SERVICE_ENV, "http://127.0.0.1:9")
    response = app.post("/v1/local/paid-access", json={"code": "valid-code-0123456789abcd"}, headers=HEADERS)
    assert (response.status_code, response.json()["detail"]) == (503, "paid_access_service_unreachable")

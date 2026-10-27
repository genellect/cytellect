"""scripts/dev.py doctor/serve: readiness probes never spend money or leak credentials."""
import http.server
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dev import (  # noqa: E402
    API_ORIGIN,
    APP_ORIGIN,
    MODAL_CELLPOSE_URL,
    cellpose_state,
    cloud_env,
    probe,
    proposal_state,
    serve_env,
)


def serve_once(handler: type[http.server.BaseHTTPRequestHandler]) -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_an_empty_proposal_request_proves_the_token_only_when_the_service_rejects_its_body():
    assert proposal_state(400, "request_invalid")[0]
    assert not proposal_state(401, "unauthorized")[0]
    assert not proposal_state(503, "proposal_service_disabled")[0]
    assert "budget_reconciliation_required" in proposal_state(503, "budget_reconciliation_required")[1]
    assert not proposal_state(200, "")[0]
    assert not proposal_state(0, "unreachable")[0]


def test_cellpose_health_distinguishes_a_rejected_key_from_a_starting_server():
    assert cellpose_state(200)[0]
    assert "rejected" in cellpose_state(401)[1]
    assert "starting" in cellpose_state(503)[1]


def test_probe_reads_the_error_code_without_following_redirects():
    seen: list[str | None] = []

    class Target(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    target, target_url = serve_once(Target)

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            if self.path == "/moved":
                self.send_response(307)
                self.send_header("Location", target_url + "/v1/proposals")
                self.end_headers()
                return
            body = b'{"code":"request_invalid"}'
            self.send_response(400)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    source, source_url = serve_once(Redirect)
    try:
        headers = {"Authorization": "Bearer device-token-for-test"}
        assert probe(urllib.request.Request(source_url + "/v1/proposals", data=b"{}", headers=headers), 5) == (
            400, "request_invalid")
        status, _ = probe(urllib.request.Request(source_url + "/moved", data=b"{}", headers=headers), 5)
        assert status == 307
        assert seen == []
    finally:
        source.shutdown()
        target.shutdown()
    assert probe(urllib.request.Request(source_url + "/v1/proposals", data=b"{}"), 2) == (0, "unreachable")


def test_serve_uses_loopback_origins_and_passes_cloud_settings_through(tmp_path):
    env = serve_env({"CYTELLECT_CELLPOSE_REMOTE_URL": "https://gpu.example", "CYTELLECT_PROPOSAL_URL": "https://p.example",
                     "CYTELLECT_SECURE_COOKIES": "true"}, tmp_path)
    assert env["CYTELLECT_DATA_DIR"] == str(tmp_path)
    assert env["CYTELLECT_APP_ORIGIN"] == APP_ORIGIN == "http://localhost:3000"
    assert env["NEXT_PUBLIC_API_ORIGIN"] == API_ORIGIN == "http://localhost:8000"
    assert env["CYTELLECT_SECURE_COOKIES"] == "false"
    assert env["CYTELLECT_CELLPOSE_REMOTE_URL"] == "https://gpu.example"
    assert env["CYTELLECT_PROPOSAL_URL"] == "https://p.example"


def test_a_modal_proxy_token_stored_in_two_parts_becomes_the_engine_bearer_value():
    env = cloud_env({"CYTELLECT_MODAL_PROXY_KEY": " wk-abc ", "CYTELLECT_MODAL_PROXY_SECRET": "ws-def"})
    assert env["CYTELLECT_CELLPOSE_REMOTE_TOKEN"] == "wk-abc.ws-def"
    assert env["CYTELLECT_CELLPOSE_REMOTE_URL"] == MODAL_CELLPOSE_URL
    explicit = cloud_env({"CYTELLECT_MODAL_PROXY_KEY": "wk-abc", "CYTELLECT_MODAL_PROXY_SECRET": "ws-def",
                          "CYTELLECT_CELLPOSE_REMOTE_TOKEN": "other", "CYTELLECT_CELLPOSE_REMOTE_URL": "https://x.example"})
    assert explicit["CYTELLECT_CELLPOSE_REMOTE_TOKEN"] == "other"
    assert explicit["CYTELLECT_CELLPOSE_REMOTE_URL"] == "https://x.example"
    assert "CYTELLECT_CELLPOSE_REMOTE_TOKEN" not in cloud_env({"CYTELLECT_MODAL_PROXY_KEY": "wk-abc"})

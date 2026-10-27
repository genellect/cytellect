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
    assert "capacity" in cellpose_state(503)[1]


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
    # An env.sh that already joined the token still gets the deployed server as its default.
    joined = cloud_env({"CYTELLECT_MODAL_PROXY_KEY": "wk-abc", "CYTELLECT_CELLPOSE_REMOTE_TOKEN": "wk-abc.ws-def"})
    assert joined["CYTELLECT_CELLPOSE_REMOTE_URL"] == MODAL_CELLPOSE_URL


def test_fiji_falls_back_to_the_cloud_setup_location(tmp_path, monkeypatch):
    import dev

    monkeypatch.delenv("CYTELLECT_FIJI_EXECUTABLE", raising=False)
    monkeypatch.setattr(dev, "CLOUD_RUNTIME", tmp_path)
    assert dev.fiji_path() == ""
    (tmp_path / "fiji").mkdir()
    assert dev.fiji_path() == str(tmp_path / "fiji")
    monkeypatch.setenv("CYTELLECT_FIJI_EXECUTABLE", "/explicit/fiji")
    assert dev.fiji_path() == "/explicit/fiji"


def test_require_cloud_fails_when_a_cloud_service_is_not_configured(monkeypatch, capsys):
    import argparse

    import dev
    import pytest

    for name in ("CYTELLECT_CELLPOSE_REMOTE_URL", "CYTELLECT_CELLPOSE_REMOTE_TOKEN", "CYTELLECT_MODAL_PROXY_KEY",
                 "CYTELLECT_MODAL_PROXY_SECRET", "CYTELLECT_PROPOSAL_URL", "CYTELLECT_PROPOSAL_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(dev, "tool_version", lambda argv: "")  # no tools, so every run exits on them
    for required, state in ((False, "[--]"), (True, "[NG]")):
        with pytest.raises(SystemExit):
            dev.doctor(argparse.Namespace(live=False, require_cloud=required))
        lines = capsys.readouterr().out.splitlines()
        assert f"{state} Cloud GPU (Cellpose): not configured; nucleoli and cytoplasm detection is unavailable" in lines
        assert any(line.startswith(f"{state} Analysis proposals (LLM)") for line in lines)


def test_stop_also_ends_descendants_that_outlive_their_leader():
    import os
    import subprocess
    import time

    import dev
    import pytest

    if not sys.platform.startswith("linux"):
        pytest.skip("process groups and /proc")

    def alive(pid: int) -> bool:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            return False
        return state != "Z"

    child = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print(flush=True); time.sleep(60)"
    leader = (f"import subprocess, sys; c = subprocess.Popen([sys.executable, '-c', {child!r}], stdout=subprocess.PIPE); "
              "c.stdout.readline(); print(c.pid, flush=True); c.wait()")
    process = subprocess.Popen([sys.executable, "-c", leader], stdout=subprocess.PIPE, text=True, start_new_session=True)
    descendant = int(process.stdout.readline())
    try:
        dev.stop([process], grace=1)
        assert process.returncode is not None
        deadline = time.monotonic() + 5
        while alive(descendant) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not alive(descendant)
    finally:
        if alive(descendant):
            os.kill(descendant, 9)

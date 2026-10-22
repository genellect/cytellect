"""Setup downloads survive rate limits and dropped connections, never other errors."""
from __future__ import annotations

import hashlib
import http.server
import importlib.util
import threading
import urllib.error
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAYLOAD = bytes(range(256)) * 4096


def load(name: str):
    spec = importlib.util.spec_from_file_location(f"setup_download_{name}", ROOT / "scripts" / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def serve(script: list[str]):
    """Answer each GET with the next scripted behavior, honoring Range requests."""
    requests: list[str | None] = []

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            requests.append(self.headers.get("Range"))
            step = script.pop(0) if script else "ok"
            if step == "reset":
                # Close before any response, as an interrupted connection does.
                self.close_connection = True
                self.connection.shutdown(2)
                return
            if step.isdigit():
                self.send_response(int(step))
                self.send_header("Retry-After", "0")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            start = int(self.headers["Range"][6:-1]) if self.headers.get("Range") else 0
            body = PAYLOAD[start:]
            self.send_response(206 if start else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            # "drop" closes the connection after sending part of the declared body.
            self.wfile.write(body[: len(body) // 3] if step == "drop" else body)

        def do_HEAD(self):
            self.send_response(200)
            self.send_header("Content-Length", str(len(PAYLOAD)))
            self.end_headers()

        def log_message(self, *_):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/artifact", requests


@pytest.fixture(params=["fiji_setup", "cellpose_setup"])
def fetch(request, monkeypatch):
    module = load(request.param)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    expected = hashlib.sha256(PAYLOAD).hexdigest()
    if request.param == "fiji_setup":
        return lambda url, directory: module.download(url, directory / "artifact", expected)
    return lambda url, directory: module.provision_model(
        directory, {"id": "artifact", "url": url, "size": len(PAYLOAD), "sha256": expected})


@pytest.mark.parametrize("script", [["429", "503"], ["reset"], ["drop"], ["502", "reset", "drop"]])
def test_transient_failures_retry_and_resume_to_the_exact_bytes(tmp_path, fetch, script):
    server, url, requests = serve(list(script))
    try:
        fetch(url, tmp_path)
    finally:
        server.shutdown()
    assert (tmp_path / "artifact").read_bytes() == PAYLOAD
    if "drop" in script:
        assert requests[-1] is not None and requests[-1].startswith("bytes=")


def test_other_http_errors_stop_without_retry(tmp_path, fetch):
    server, url, requests = serve(["404"])
    try:
        with pytest.raises(urllib.error.HTTPError):
            fetch(url, tmp_path)
    finally:
        server.shutdown()
    assert len(requests) == 1
    assert not (tmp_path / "artifact").exists()

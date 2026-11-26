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


def serve(script: list[str], head: list[str] | None = None):
    """Answer each GET (and HEAD) with the next scripted behavior, honoring Range requests."""
    requests: list[str | None] = []
    head = list(head or [])

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
            if start >= len(PAYLOAD):
                self.send_response(416)
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
            # "wrong" sends a complete body of the right length with altered bytes.
            body = bytes(len(PAYLOAD)) if step == "wrong" else PAYLOAD[start:]
            self.send_response(206 if start else 200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            # "drop" closes the connection after sending part of the declared body.
            self.wfile.write(body[: len(body) // 3] if step == "drop" else body)

        def do_HEAD(self):
            step = head.pop(0) if head else "ok"
            if step == "reset":
                self.close_connection = True
                self.connection.shutdown(2)
                return
            if step.isdigit():
                self.send_response(int(step))
                self.send_header("Retry-After", "0")
                self.send_header("Content-Length", "0")
                self.end_headers()
                return
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


def test_fiji_cache_reuses_a_verified_download_without_contacting_the_host(tmp_path, monkeypatch):
    module = load("fiji_setup")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    expected = hashlib.sha256(PAYLOAD).hexdigest()
    cache = tmp_path / "cache"
    server, url, requests = serve([])
    try:
        module.download(url, tmp_path / "first", expected, cache=cache)
    finally:
        server.shutdown()
    assert (cache / expected).read_bytes() == PAYLOAD
    assert len(requests) == 1
    # The host is unreachable now; the cached copy alone completes the setup.
    module.download("http://127.0.0.1:9/unreachable", tmp_path / "second", expected, cache=cache)
    assert (tmp_path / "second").read_bytes() == PAYLOAD


def test_fiji_cache_discards_an_altered_copy_and_downloads_again(tmp_path, monkeypatch):
    module = load("fiji_setup")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    expected = hashlib.sha256(PAYLOAD).hexdigest()
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / expected).write_bytes(b"altered")
    server, url, requests = serve([])
    try:
        module.download(url, tmp_path / "artifact", expected, cache=cache)
    finally:
        server.shutdown()
    assert (tmp_path / "artifact").read_bytes() == PAYLOAD
    assert (cache / expected).read_bytes() == PAYLOAD
    assert len(requests) == 1


def test_fiji_reports_the_last_transient_failure_when_retries_run_out(tmp_path, monkeypatch):
    module = load("fiji_setup")
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    server, url, requests = serve(["429"] * 6)
    try:
        with pytest.raises(RuntimeError, match=r"Download failed after retries \(last: HTTP 429\)"):
            module.download(url, tmp_path / "artifact", hashlib.sha256(PAYLOAD).hexdigest(), cache=tmp_path / "cache")
    finally:
        server.shutdown()
    assert len(requests) == 6
    assert len(sleeps) == 5  # no wait after the last attempt
    assert not (tmp_path / "cache").exists()


def test_fiji_setup_continues_when_the_cache_cannot_be_written(tmp_path, monkeypatch):
    module = load("fiji_setup")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("file", encoding="utf-8")
    server, url, _requests = serve([])
    try:
        module.download(url, tmp_path / "artifact", hashlib.sha256(PAYLOAD).hexdigest(), cache=blocker / "cache")
    finally:
        server.shutdown()
    assert (tmp_path / "artifact").read_bytes() == PAYLOAD


@pytest.mark.parametrize("head", [["429"], ["reset"]])
def test_fiji_transient_head_failure_keeps_the_partial_download_and_resumes(tmp_path, monkeypatch, head):
    module = load("fiji_setup")
    sleeps: list[float] = []
    monkeypatch.setattr("time.sleep", sleeps.append)
    server, url, requests = serve(["drop"], head=head)
    try:
        module.download(url, tmp_path / "artifact", hashlib.sha256(PAYLOAD).hexdigest())
    finally:
        server.shutdown()
    assert (tmp_path / "artifact").read_bytes() == PAYLOAD
    assert len(requests) == 2 and requests[-1] is not None and requests[-1].startswith("bytes=")
    assert len(sleeps) == 1  # the transient HEAD failure waits before the next attempt


def test_fiji_complete_wrong_payload_restarts_from_zero_when_head_fails(tmp_path, monkeypatch):
    module = load("fiji_setup")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    server, url, requests = serve(["wrong"], head=["503"])
    try:
        module.download(url, tmp_path / "artifact", hashlib.sha256(PAYLOAD).hexdigest())
    finally:
        server.shutdown()
    assert (tmp_path / "artifact").read_bytes() == PAYLOAD
    # The resumed request is answered 416, so the copy is fetched again from byte zero.
    assert requests == [None, f"bytes={len(PAYLOAD)}-", None]


def test_fiji_cache_falls_back_to_downloading_when_the_cached_copy_cannot_be_read(tmp_path, monkeypatch):
    module = load("fiji_setup")
    monkeypatch.setattr("time.sleep", lambda _seconds: None)
    expected = hashlib.sha256(PAYLOAD).hexdigest()
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / expected).write_bytes(PAYLOAD)

    def unreadable(*_args, **_kwargs):
        raise PermissionError("cache")

    monkeypatch.setattr(module.shutil, "copyfile", unreadable)
    server, url, requests = serve([])
    try:
        module.download(url, tmp_path / "artifact", expected, cache=cache)
    finally:
        server.shutdown()
    assert (tmp_path / "artifact").read_bytes() == PAYLOAD
    assert len(requests) == 1


def test_fiji_setup_rejects_offline_and_cache_directories_together(tmp_path, monkeypatch):
    module = load("fiji_setup")
    monkeypatch.setattr("sys.argv", ["fiji_setup.py", str(tmp_path / "fiji"),
                                     "--offline-dir", str(tmp_path), "--cache-dir", str(tmp_path / "cache")])
    with pytest.raises(SystemExit) as raised:
        module.main()
    assert raised.value.code == 2
    assert not (tmp_path / "fiji").exists()

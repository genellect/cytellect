"""Transport-only checks for the deployment verifier; no microscopy or model mock."""
import importlib.util
import subprocess
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def checker():
    spec = importlib.util.spec_from_file_location("deployment_checker", ROOT / "scripts/cellpose_modal_check.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("status", [200, 401, 503])
def test_relay_preserves_status_and_body_without_forwarding_credentials(checker, monkeypatch, tmp_path, capsys, status):
    calls = []
    def curl(args, **kwargs):
        calls.append(args)
        Path(args[args.index("--output") + 1]).write_bytes(b"transport response")
        assert Path(args[args.index("--data-binary") + 1][1:]).read_bytes() == b"transport request"
        return subprocess.CompletedProcess(args, 0, str(status).encode(), b"unlogged diagnostic")
    monkeypatch.setattr(checker.subprocess, "run", curl)
    server = ThreadingHTTPServer(("127.0.0.1", 0), checker.relay_handler(tmp_path))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        request = urllib.request.Request(f"http://127.0.0.1:{server.server_port}/v1/cellpose",
                                         data=b"transport request", headers={"Authorization": "Bearer not-forwarded"})
        try:
            response = urllib.request.urlopen(request)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            assert response.status == status
            assert response.read() == b"transport response"
        assert calls[0][-1] == checker.URL + "/v1/cellpose"
        assert "not-forwarded" not in " ".join(calls[0])
        assert capsys.readouterr().err == ""
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_baseline_uses_the_immutable_published_source(checker, monkeypatch, tmp_path):
    refs = []
    def show(args, **kwargs):
        refs.append(args[-1])
        if args[-1].endswith("cellpose_engine.py"):
            return b""  # import plumbing only; no detector or scientific output
        return b"{}"
    monkeypatch.setattr(checker.subprocess, "check_output", show)
    checker.baseline_client(tmp_path / "baseline")
    assert len(refs) == 6
    assert all(ref.startswith("3090c044fe642b989d51c1c6acca1f4778ae3ea8:") for ref in refs)
    assert all(checker.BASELINE_REF not in ref for ref in refs)


def test_baseline_child_does_not_receive_modal_credentials(checker, monkeypatch):
    for key in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "MODAL_PROFILE", "CYTELLECT_CELLPOSE_REMOTE_TOKEN",
                "CYTELLECT_CELLPOSE_REMOTE_SECRET", "XDG_CACHE_HOME"):
        monkeypatch.setenv(key, "must-not-inherit")
    environment = checker.client_environment("http://127.0.0.1:1234")
    assert not any(key.startswith("MODAL_") for key in environment)
    assert "must-not-inherit" not in environment.values()
    assert environment["CYTELLECT_CELLPOSE_REMOTE_URL"] == "http://127.0.0.1:1234"

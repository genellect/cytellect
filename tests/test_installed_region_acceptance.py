"""The installed acceptance harness itself must fail closed and use independent references."""
import importlib.util
import io
import json
import threading
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import pytest
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated

spec = importlib.util.spec_from_file_location(
    "installed_acceptance", Path(__file__).resolve().parents[1] / "scripts/verify_installed_regions.py")
assert spec is not None and spec.loader is not None
acceptance = importlib.util.module_from_spec(spec)
spec.loader.exec_module(acceptance)


@pytest.mark.parametrize("origin", ["https://example.com", "http://localhost:8765", "http://127.0.0.1",
                                   "http://user@127.0.0.1:8765", "http://127.0.0.1:8765/?token=unused"])
def test_live_acceptance_refuses_nonliteral_or_ambiguous_destinations(origin):
    with pytest.raises(ValueError, match="literal_loopback"):
        acceptance.LocalSession(origin)


def test_acceptance_refuses_checkout_interpreter_as_installed_proof(tmp_path):
    with pytest.raises(ValueError, match="installed_interpreter_required"):
        acceptance.source_identity(tmp_path / "not-the-installed-app", "a" * 40)


def test_live_transport_checks_cache_policy_and_never_follows_redirects():
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(302 if self.path == "/v1/redirect" else 200)
            self.send_header("Content-Type", "application/json")
            if self.path != "/v1/cacheable":
                self.send_header("Cache-Control", "no-store")
            if self.path == "/v1/redirect":
                self.send_header("Location", "https://external.invalid/never-follow")
            self.end_headers()
            self.wfile.write(b'{"test":true}')

        def log_message(self, *args):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        session = acceptance.LocalSession(f"http://127.0.0.1:{server.server_port}")
        assert session.json("/v1/ok") == {"test": True}
        with pytest.raises(ValueError, match="private_response_cache_required"):
            session.json("/v1/cacheable")
        with pytest.raises(ValueError, match="redirect_forbidden"):
            session.json("/v1/redirect")
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def test_acceptance_archive_validates_paths_before_writing(tmp_path):
    stream = io.BytesIO()
    with zipfile.ZipFile(stream, "w") as archive:
        archive.writestr("../outside.txt", "never extract")
    with pytest.raises(ValueError, match="archive_path_invalid"):
        acceptance.extract_verified_bundle(stream.getvalue(), tmp_path / "unpacked")
    assert not (tmp_path / "outside.txt").exists()
    assert not (tmp_path / "unpacked").exists()


def test_four_known_units_cross_real_api_and_closed_form_inference_then_replay(tmp_path, monkeypatch):
    # This tests the harness in the checkout. It does not claim installed-copy acceptance.
    monkeypatch.setenv("CYTELLECT_CODE_REVISION", "a" * 40)
    client, app, settings = authenticated(tmp_path)

    class Adapter:
        def request(self, path, *, body=None, content_type="application/json", method=None):
            response = client.request(method or ("POST" if body is not None else "GET"), path,
                                      content=body, headers={**HEADERS, "Content-Type": content_type})
            assert response.is_success, response.text
            assert response.headers["cache-control"] == "no-store"
            return response.content

        def json(self, path, body=None):
            if path == "/v1/local/setup":
                return {"mode": "local", "ready": True}
            if path == "/v1/local/session":
                return {"authenticated": True}
            return json.loads(self.request(path, body=json.dumps(body).encode() if body is not None else None))

        def wait(self, job_id):
            process_one(app.state.store, settings)
            assert self.json(f"/v1/jobs/{job_id}")["state"] == "succeeded"

    output = tmp_path / "generated-output"
    output.mkdir()
    result = acceptance.verify_workflow(Adapter(), output, "a" * 40)
    assert result["repeat_review_export"] and result["generated_workspace_deleted"]
    assert result["replay"]["matched_saved_measurements"] and result["replay"]["matched_saved_comparisons"]
    assert [row["design"] for row in result["closed_form_checks"]] == ["independent", "paired"]
    assert result["closed_form_checks"][0]["expected"]["p_value"] != result["closed_form_checks"][1]["expected"]["p_value"]
    result_path = next((output / "bundle" / "statistics").glob("*/result.json"))
    altered = json.loads(result_path.read_text(encoding="utf-8"))
    altered["comparisons"][0]["estimate"] = 0
    with pytest.raises(ValueError, match="independent_reference_mismatch"):
        acceptance.verify_reference(altered, paired=altered["spec"]["design"]["kind"] == "paired")
    client.close()
    app.state.store.engine.dispose()

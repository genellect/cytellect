"""Remote GPU inference keeps the local contract: same runner identity, raw labels only."""
from __future__ import annotations

import importlib.util
import io
import json
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from cytellect_analysis import cellpose_engine as engine
from cytellect_analysis.cellpose_engine import CellposeDetectorSpec, detect_cellpose, runtime_status
from cytellect_api.local import local_cellpose_remote_environment

ASSETS = Path(__file__).resolve().parents[1] / "engines" / "cellpose"


def load_server():
    spec = importlib.util.spec_from_file_location("cytellect_cellpose_server_test", ASSETS / "server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class FakeRunner:
    """Stands in for the Torch runner; labels every pixel above 100 as object 1."""

    def __init__(self, lock_name="gpu.lock.json"):
        self.lock = json.loads((ASSETS / lock_name).read_text(encoding="utf-8"))
        self.calls = []
        self._NETWORK = {}

    def prepare_runtime(self, _model_path):
        return dict(self.lock["packages"])

    def verify_model(self, path, profile):
        assert path.name == profile["id"]

    def selected_model(self, lock, parameters):
        return engine.model_profile(lock, parameters["model"])

    def runtime_lock(self):
        return self.lock

    def infer(self, parameters, image, nuclei, _model_path, versions):
        self.calls.append({"parameters": parameters, "shape": image.shape, "parent": nuclei is not None, "model": _model_path.name})
        labels = (image > 100).astype(np.uint32)
        return labels, {"status": "succeeded", "runtime_packages": versions, "device": "cuda", "precision": "float32",
                        "normalization": {"constant_signal": False}, "preprocessing": {"algorithm": "none"},
                        "coordinate_transform": {"scale_x": 1, "scale_y": 1}}


@pytest.fixture
def service(monkeypatch, tmp_path):
    server_module = load_server()
    runner = FakeRunner()
    monkeypatch.setattr(server_module, "load_runner", lambda: runner)
    state = SimpleNamespace(module=server_module, runner=runner, unavailable=0, secret=None)
    model_cache = tmp_path / "models"
    model_cache.mkdir()
    for name in runner.lock["ncl_candidates"]:
        (model_cache / name).write_bytes(b"routing contract only; not model weights")

    def start(secret=None, unavailable=0, identity=None):
        service = server_module.Service(model_cache / "cpsam_v2", require_gpu=False)
        state.service = service
        if identity:
            service.identity.update(identity)
        base = server_module.handler_for(service, secret)
        counter = {"left": unavailable}

        class Handler(base):
            def do_POST(self):
                if counter["left"]:
                    counter["left"] -= 1
                    self.rfile.read(int(self.headers["Content-Length"]))
                    return self.error(503, "starting")
                state.headers = dict(self.headers)
                return super().do_POST()

        httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        threading.Thread(target=httpd.serve_forever, daemon=True).start()
        state.httpd = httpd
        monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_URL", f"http://127.0.0.1:{httpd.server_port}")
        return state

    state.start = start
    monkeypatch.setattr(engine.time, "sleep", lambda _seconds: None)
    yield state
    if hasattr(state, "httpd"):
        state.httpd.shutdown()


def image():
    value = np.full((24, 32), 50, np.uint16)
    value[4:10, 6:14] = 400
    return value


def test_remote_inference_returns_the_services_labels_with_recorded_backend(service, tmp_path, monkeypatch):
    service.start()
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_TOKEN", "test-token")
    status = runtime_status()
    assert status["available"] and status["backend"] == "remote"
    labels, info = detect_cellpose(image(), CellposeDetectorSpec(), tmp_path)
    assert np.array_equal(labels, (image() > 100).astype(np.uint32))
    assert info["runtime"]["device"] == "cuda"
    assert info["runtime"]["execution_backend"] == {"kind": "remote", "host": "127.0.0.1", "requested_compute_device": "cpu"}
    # The saved recipe keeps its value; the service is asked to choose its own device.
    assert info["parameters"]["compute_device"] == "cpu"
    assert service.runner.calls[0]["parameters"]["compute_device"] == "auto"
    assert service.headers["Authorization"] == "Bearer test-token"
    assert not list(tmp_path.glob("cellpose-input.npy")) and not list(tmp_path.glob("cellpose-request.json"))


def test_remote_inference_waits_while_the_endpoint_scales_up(service, tmp_path):
    service.start(unavailable=3)
    labels, _ = detect_cellpose(image(), CellposeDetectorSpec(), tmp_path)
    assert int(labels.max()) == 1


def test_remote_inference_rejects_another_runner_version(service, tmp_path):
    service.start(identity={"runner_sha256": "0" * 64})
    with pytest.raises(ValueError, match="cellpose_remote_version_mismatch"):
        detect_cellpose(image(), CellposeDetectorSpec(), tmp_path)


def test_remote_inference_reports_a_rejected_key_without_echoing_it(service, tmp_path, monkeypatch):
    service.start(secret="expected")
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_SECRET", "wrong")
    with pytest.raises(ValueError) as error:
        detect_cellpose(image(), CellposeDetectorSpec(), tmp_path)
    assert str(error.value) == "cellpose_remote_rejected"
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_SECRET", "expected")
    labels, _ = detect_cellpose(image(), CellposeDetectorSpec(), tmp_path)
    assert int(labels.max()) == 1


@pytest.mark.parametrize("url", ["http://example.com", "ftp://127.0.0.1", "https://user:pw@example.com", "https://example.com/?key=1"])
def test_only_https_or_a_loopback_test_service_is_accepted(monkeypatch, url):
    monkeypatch.setenv("CYTELLECT_CELLPOSE_REMOTE_URL", url)
    status = runtime_status()
    assert status == {"available": False, "error": "cellpose_remote_url_invalid", "runtime_downloads": False}


def test_service_refuses_pickles_and_malformed_requests(service):
    state = service.start()
    module = state.module
    target = state.httpd.server_address

    def post(body):
        import urllib.error
        import urllib.request

        request = urllib.request.Request(f"http://{target[0]}:{target[1]}/v1/cellpose", data=body, method="POST")
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read())

    stream = io.BytesIO()
    np.savez(stream, request=np.array([{"parameters": {}}], dtype=object), image=image())
    assert post(stream.getvalue()) == (400, {"error": "cellpose_remote_input_invalid"})
    assert post(b"not an archive") == (400, {"error": "cellpose_remote_input_invalid"})
    stream = io.BytesIO()
    np.savez(stream, request=np.frombuffer(b'{"parameters":{}}', np.uint8), image=image().astype(np.float32))
    assert post(stream.getvalue()) == (400, {"error": "cellpose_remote_input_invalid"})
    assert module.MAX_SIDE == 8192
    assert state.runner.calls == []


def test_launcher_passes_only_a_valid_remote_setting(tmp_path):
    data = tmp_path / "data"
    data.mkdir()
    settings = tmp_path / "settings"
    settings.mkdir()
    path = settings / "cellpose-remote.json"
    path.write_text(json.dumps({"schema": "cytellect-cellpose-remote/1", "url": "https://gpu.example", "token": "t"}))
    assert local_cellpose_remote_environment(data) == {"CYTELLECT_CELLPOSE_REMOTE_URL": "https://gpu.example",
                                                       "CYTELLECT_CELLPOSE_REMOTE_TOKEN": "t"}
    path.write_text(json.dumps({"schema": "cytellect-cellpose-remote/1", "url": "https://gpu.example", "extra": 1}))
    assert local_cellpose_remote_environment(data) == {}
    path.write_text("not json")
    assert local_cellpose_remote_environment(data) == {}


def test_gpu_lock_matches_the_cpu_runtime_except_the_torch_build():
    cpu = json.loads((ASSETS / "runtime.lock.json").read_text(encoding="utf-8"))
    gpu = json.loads((ASSETS / "gpu.lock.json").read_text(encoding="utf-8"))
    assert gpu["runner_sha256"] == cpu["runner_sha256"] and gpu["model"] == cpu["model"]
    assert {k: v for k, v in gpu["packages"].items() if k not in {"torch", "torchvision"}} == \
        {k: v for k, v in cpu["packages"].items() if k not in {"torch", "torchvision"}}
    assert gpu["packages"]["torch"] == "2.8.0+cu126" and gpu["torch_backend"] == "cu126"

    def pins(name):
        return {line.split(" ")[0] for line in (ASSETS / name).read_text(encoding="utf-8").splitlines()
                if "==" in line and not line.startswith((" ", "#", "-"))}

    shared = {pin.split("==")[0] for pin in pins("requirements-cuda.lock")} & {pin.split("==")[0] for pin in pins("requirements.lock")}
    assert shared >= {"cellpose", "numpy", "scipy", "fastremap", "fill-voids", "opencv-python-headless"}
    cpu_pins = {pin for pin in pins("requirements.lock") if pin.split("==")[0] in shared - {"torch", "torchvision"}}
    gpu_pins = {pin for pin in pins("requirements-cuda.lock") if pin.split("==")[0] in shared - {"torch", "torchvision"}}
    assert cpu_pins == gpu_pins


@pytest.mark.parametrize("model_id", list(engine.NCL_MODEL_HASHES))
def test_remote_selected_weights_keep_identity_and_reject_baseline_runner(service, tmp_path, model_id):
    """Transport contract on a registered public image; fake runner is not accuracy evidence."""
    import tifffile

    state = service.start()
    public = tifffile.imread(ASSETS.parents[1] / "fixtures/public/bbbc013/A01-dapi.tif")[:24, :32]
    parameters = engine.NclParentCellposeDetectorSpec(model=model_id, model_sha256=engine.NCL_MODEL_HASHES[model_id])
    _, receipt = engine._remote_inference(public, np.ones(public.shape, np.uint32), parameters)
    assert state.runner.calls[-1]["model"] == model_id
    assert receipt["model_identity"]["id"] == model_id
    assert receipt["service"]["model_sha256"] == parameters.model_sha256
    state.service.identity["runner_sha256"] = state.runner.lock["baseline_runner_sha256"]
    with pytest.raises(ValueError, match="cellpose_remote_version_mismatch"):
        engine._remote_inference(public, np.ones(public.shape, np.uint32), parameters)


def test_missing_selected_model_never_falls_back(service):
    state = service.start()
    model_id = engine.NCL_750_MODEL_ID
    state.service.models.remove(model_id)
    parameters = engine.NclParentCellposeDetectorSpec(model=model_id, model_sha256=engine.NCL_750_MODEL_SHA256)
    with pytest.raises(ValueError, match="cellpose_model_missing"):
        engine._remote_inference(image(), np.ones(image().shape, np.uint32), parameters)
    assert not state.runner.calls


def test_baseline_client_compatibility_and_network_release(service, monkeypatch):
    state = service.start()
    legacy = FakeRunner()
    legacy.lock = {**legacy.lock, "runner_sha256": legacy.lock["baseline_runner_sha256"]}
    state.service.legacy_runner = legacy
    state.runner._NETWORK["network"] = object()
    _, receipt = engine._remote_inference(image(), None, CellposeDetectorSpec())
    assert receipt["service"]["runner_sha256"] == legacy.lock["runner_sha256"]
    assert receipt["service"]["model_sha256"] == engine.MODEL_SHA256
    assert not state.runner._NETWORK
    assert legacy.calls[-1]["model"] == "cpsam_v2"
    # Replay the previous release's strict identity rule against the actual receipt.
    assert receipt["service"]["runner_sha256"] == "98db8e818ec4a547d87078d1c634f81a99c0c9d911de50a8dcde229bf0442201"
    legacy._NETWORK["network"] = object()
    selected = engine.NclParentCellposeDetectorSpec(model=engine.NCL_750_MODEL_ID, model_sha256=engine.NCL_750_MODEL_SHA256)
    engine._remote_inference(image(), np.ones(image().shape, np.uint32), selected)
    assert not legacy._NETWORK
    assert state.runner.calls[-1]["model"] == engine.NCL_750_MODEL_ID

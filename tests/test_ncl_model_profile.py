"""Model/configuration contracts only: no pixels, inference or model loading."""
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from cytellect_analysis import cellpose_engine as engine
from pydantic import ValidationError

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = list(engine.NCL_MODEL_HASHES.items())


def load_script(name):
    spec = importlib.util.spec_from_file_location(name.stem, name)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.mark.parametrize("model_id,model_sha", CANDIDATES)
def test_optional_profile_preserves_defaults_and_registered_identity(model_id, model_sha):
    runtime = json.loads((ROOT / "engines/cellpose/runtime.lock.json").read_text())
    provisioning = json.loads((ROOT / "engines/cellpose/provisioning.lock.json").read_text())
    profile = engine.model_profile(runtime, model_id)
    assert profile == provisioning["ncl_candidates"][model_id]
    assert profile["sha256"] == model_sha
    assert profile["revision"] in profile["url"]
    assert profile["url"].endswith("/" + profile["path"])
    assert profile["base_model_sha256"] == engine.MODEL_SHA256
    assert profile["license"] == "BSD-3-Clause"
    assert profile["repository"] == "Genellect/Cytellect"
    assert runtime["model"] == provisioning["model"]
    for detector in (engine.CellposeDetectorSpec(), engine.NclCellposeDetectorSpec(),
                     engine.NclParentCellposeDetectorSpec()):
        assert detector.model == "cpsam_v2"
        assert detector.model_sha256 == engine.MODEL_SHA256
    assert hashlib.sha256((ROOT / "engines/cellpose/runner.py").read_bytes()).hexdigest() == runtime["runner_sha256"]


@pytest.mark.parametrize("model_id,model_sha", CANDIDATES)
def test_candidate_requires_exact_pair_and_parent_430(model_id, model_sha):
    selection = {"model": model_id, "model_sha256": model_sha}
    candidate = engine.NclParentCellposeDetectorSpec(**selection)
    assert engine.NclParentCellposeDetectorSpec.model_validate_json(candidate.model_dump_json()) == candidate
    for cls in (engine.CellposeDetectorSpec, engine.NclCellposeDetectorSpec):
        with pytest.raises(ValidationError):
            cls(**selection)
    other_sha = next(value for key, value in CANDIDATES if key != model_id)
    for invalid in ({"model": model_id}, {"model_sha256": model_sha},
                    {**selection, "model_sha256": other_sha},
                    {**selection, "protocol_version": "4.2.1"}):
        with pytest.raises(ValidationError):
            engine.NclParentCellposeDetectorSpec(**invalid)


@pytest.mark.parametrize("model_id,model_sha", CANDIDATES)
def test_runner_resolves_same_identity_and_rejects_conflicting_request(model_id, model_sha):
    runner = load_script(ROOT / "engines/cellpose/runner.py")
    lock = json.loads((ROOT / "engines/cellpose/runtime.lock.json").read_text())
    runner.verify_assets(lock)
    candidate = engine.NclParentCellposeDetectorSpec(
        model=model_id, model_sha256=model_sha).model_dump()
    assert runner.selected_model(lock, candidate) == engine.model_profile(lock, model_id)
    other_sha = next(value for key, value in CANDIDATES if key != model_id)
    for patch in ({"model_sha256": engine.MODEL_SHA256}, {"protocol_version": "4.2.1"},
                  {"engine": "cellpose-sam"}, {"model": "arbitrary-model"}, {"model_sha256": other_sha}):
        with pytest.raises(RuntimeError):
            runner.selected_model(lock, {**candidate, **patch})


@pytest.mark.parametrize("model_id,model_sha", CANDIDATES)
def test_runtime_missing_candidate_does_not_claim_baseline(monkeypatch, tmp_path, model_id, model_sha):
    monkeypatch.setenv("CYTELLECT_CELLPOSE_PYTHON", str(Path(__file__)))
    monkeypatch.setenv("CYTELLECT_CELLPOSE_MODEL_DIR", str(tmp_path))
    assert engine.runtime_status(model_id) == {
        "available": False, "error": "cellpose_model_missing", "runtime_downloads": False}



def test_weight_verification_precedes_deserialization(tmp_path):
    """Small text payload tests integrity checking, not a model or microscopy image."""
    runner = load_script(ROOT / "engines/cellpose/runner.py")
    path = tmp_path / "weights"
    data = b"integrity contract"
    path.write_bytes(data)
    profile = {"sha256": hashlib.sha256(data).hexdigest(), "size": len(data)}
    runner.verify_model(path, profile)
    path.write_bytes(b"x" * len(data))
    with pytest.raises(RuntimeError, match="cellpose_model_integrity_failed"):
        runner.verify_model(path, profile)


def test_gpu_cpu_and_provisioning_share_checkpoint_identities():
    manifests = [json.loads((ROOT / "engines/cellpose" / name).read_text())
                 for name in ("runtime.lock.json", "gpu.lock.json", "provisioning.lock.json")]
    assert manifests[0]["ncl_candidates"] == manifests[1]["ncl_candidates"] == manifests[2]["ncl_candidates"]
    docker = (ROOT / "infra/Dockerfile.cellpose-gpu").read_text()
    assert "--all-models" in docker
    assert "COPY --from=baseline /app/engines/cellpose /app/engines/cellpose/baseline" in docker

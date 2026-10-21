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
    assert profile["status"] == "experimental_development_candidate"
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


def test_redirect_does_not_forward_private_hf_credential():
    setup = load_script(ROOT / "scripts/cellpose_setup.py")
    request = setup.urllib.request.Request("https://huggingface.co/model",
                                          headers={"Authorization": "Bearer example-placeholder"})
    redirected = setup.ModelRedirectHandler().redirect_request(
        request, None, 302, "redirect", {}, "https://storage.example/model")
    assert not redirected.has_header("Authorization")


def test_local_source_staging_alias_is_rejected_without_deleting_bytes(tmp_path):
    """Ordinary text bytes only; neither a model nor an image is loaded."""
    setup = load_script(ROOT / "scripts/cellpose_setup.py")
    cache = tmp_path / "cache"
    cache.mkdir()
    partial = cache / "example.partial"
    content = b"configuration contract fixture; not model or image data"
    partial.write_bytes(content)
    artifact = {"id": "example", "size": len(content),
                "sha256": hashlib.sha256(content).hexdigest()}
    alias = tmp_path / "source.txt"
    alias.hardlink_to(partial)
    for source in (partial, alias):
        with pytest.raises(RuntimeError, match="cellpose_source_is_staging_file"):
            setup.provision_model(cache, artifact, source)
        assert partial.read_bytes() == content
        assert alias.read_bytes() == content
        assert not (cache / artifact["id"]).exists()

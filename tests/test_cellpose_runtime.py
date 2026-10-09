"""Runtime and mask-contract checks, not biological segmentation acceptance."""
import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
from cytellect_analysis import cellpose_engine as engine
from cytellect_analysis.cellpose_engine import (
    CellposeDetectorSpec,
    NclCellposeDetectorSpec,
    NclParentCellposeDetectorSpec,
    bind_nucleolar_candidates,
    detect_cellpose,
    exclude_nuclear_scale_candidates,
)
from pydantic import ValidationError


def test_model_and_runtime_are_fixed():
    lock = json.loads((engine._assets() / "runtime.lock.json").read_text())
    assert lock["model"]["sha256"] == engine.MODEL_SHA256
    assert lock["model"]["size"] == engine.MODEL_SIZE
    assert lock["model"]["url"].endswith(f"/{lock['model']['revision']}/cpsam_v2")
    assert lock["runtime_downloads"] is False
    for name, key in (("runner.py", "runner_sha256"), ("requirements.lock", "requirements_sha256")):
        assert hashlib.sha256((engine._assets() / name).read_bytes()).hexdigest() == lock[key]
    with pytest.raises(ValidationError):
        CellposeDetectorSpec(model="unknown")
    with pytest.raises(ValidationError):
        CellposeDetectorSpec(normalization_percentile_low=99., normalization_percentile_high=1.)
    with pytest.raises(ValidationError):
        CellposeDetectorSpec(diameter_px=float("nan"))


def test_protocols_share_pins_without_reinterpreting_legacy_settings():
    original, ncl = CellposeDetectorSpec(), NclCellposeDetectorSpec()
    assert (original.engine, original.protocol_version) == ("cellpose-sam", "4.0.0")
    assert (ncl.engine, ncl.protocol_version) == ("cellpose-sam-ncl", "4.1.0")
    assert (ncl.smoothing_sigma_px, ncl.background_radius_px) == (.9, 10)
    assert (ncl.cellprob_threshold, ncl.flow_threshold, ncl.diameter_px) == (0., .4, None)
    assert ncl.model == original.model and ncl.model_sha256 == original.model_sha256
    with pytest.raises(ValidationError):
        CellposeDetectorSpec.model_validate(ncl.model_dump())
    with pytest.raises(ValidationError):
        NclCellposeDetectorSpec(protocol_version="4.0.0")
    runtime = json.loads((engine._assets() / "runtime.lock.json").read_text())
    provisioning = json.loads((engine._assets() / "provisioning.lock.json").read_text())
    assert provisioning["schema"] == "cytellect-cellpose-provisioning/1"
    assert "runner_sha256" not in provisioning
    for field in ("python", "packages", "model", "requirements_sha256", "runtime_downloads"):
        assert provisioning[field] == runtime[field]


def test_parent_protocol_is_separate_and_requires_an_adopted_mask(tmp_path):
    from cytellect_analysis.compartment_engine import NucleolarDetector
    from pydantic import TypeAdapter

    detector = NclParentCellposeDetectorSpec()
    assert TypeAdapter(NucleolarDetector).validate_python(detector.model_dump()) == detector
    assert detector.protocol_version == "4.3.0" and detector.diameter_px is None
    assert NclParentCellposeDetectorSpec(protocol_version="4.2.0").protocol_version == "4.2.0"
    assert detector.parent_background_percentile == 75 and detector.nuclear_diameter_fraction == .25
    with pytest.raises(ValidationError):
        NclCellposeDetectorSpec.model_validate(detector.model_dump())
    with pytest.raises(ValidationError):
        NclParentCellposeDetectorSpec(nuclear_diameter_fraction=0)
    # Validation only: no generated detection image is sent to the model.
    with pytest.raises(ValueError, match="cellpose_adopted_nuclei_required"):
        detect_cellpose(np.empty((1, 1), np.uint8), detector, tmp_path)


def test_partial_parent_keeps_valid_object_but_not_a_complete_complement():
    from cytellect_analysis.compartment_engine import derive_compartment_masks

    # Set-membership fixture, not an image/segmentation acceptance fixture.
    parent = np.ones((4, 4), np.uint32)
    child = np.zeros_like(parent)
    child[1:3, 1:3] = 2
    old, _ = derive_compartment_masks(parent, child, {1: "review_required"})
    new, info = derive_compartment_masks(parent, child, {1: "review_required"}, retain_review_candidates=True)
    assert not old["nucleoli"].any()
    assert np.array_equal(new["nucleoli"], child) and not new["nucleoplasm"].any()
    assert info["compartment_protocol_version"] == "1.1.0"
    assert info["incomplete_nucleolar_parent_ids"] == [1]
    assert info["compartment_status"] == "incomplete"


def test_nuclear_instance_rejection_preserves_small_contained_objects_and_raw_ids():
    # Label-set arithmetic only, not a generated biological image/model test.
    nuclei = np.ones((10, 20), dtype=np.uint32)
    nuclei[:, 10:] = 2
    raw = np.zeros_like(nuclei)
    raw[1:9, 1:9] = 7
    raw[3:5, 13:15] = 12
    filtered, excluded = exclude_nuclear_scale_candidates(raw, nuclei, .5)
    assert (raw == 7).sum() == 64 and not (filtered == 7).any()
    assert np.array_equal(filtered == 12, raw == 12)
    assert excluded == [{"source_label_id": 7, "component": 1, "parent_id": 1,
                         "reason": "nuclear_scale_candidate", "nuclear_coverage": .64, "parent_purity": 1.}]
    labels, info = bind_nucleolar_candidates(filtered, nuclei)
    assert labels[3, 13] == 1 and info["parent_ids"] == {1: 2}


def test_preprocessing_contract_without_model_inference(monkeypatch):
    # Numeric call-contract fixture only, never image-segmentation acceptance.
    module_spec = importlib.util.spec_from_file_location("cellpose_preprocessing_contract", engine._assets() / "runner.py")
    assert module_spec is not None and module_spec.loader is not None
    runner = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)
    image = np.arange(30, dtype=np.uint16).reshape(5, 6)
    unchanged = image.copy()
    calls = []
    def smooth(values, sigma, *, mode):
        assert values.dtype == np.float32 and np.array_equal(values, unchanged)
        assert sigma == .9 and mode == "reflect"
        calls.append("smooth")
        return values + 4
    def background(values, *, footprint, mode):
        assert np.array_equal(values, unchanged.astype(np.float32) + 4)
        assert footprint.dtype == bool and footprint.shape == (21, 21)
        assert footprint[10, 0] and not footprint[0, 0] and mode == "reflect"
        calls.append("background")
        return np.full(values.shape, 10, np.float32)
    monkeypatch.setattr(engine.ndi, "gaussian_filter", smooth)
    monkeypatch.setattr(engine.ndi, "grey_opening", background)
    original, legacy_metadata = runner.prepare_detection_input(image, CellposeDetectorSpec().model_dump())
    assert original is image and not calls and legacy_metadata["algorithm"] == "none"
    transformed, metadata = runner.prepare_detection_input(image, NclCellposeDetectorSpec().model_dump())
    assert calls == ["smooth", "background"]
    assert np.array_equal(transformed, np.maximum(unchanged.astype(np.float32) - 6, 0))
    assert np.array_equal(image, unchanged)
    assert metadata["nuclear_mask_applied_before_inference"] is False
    assert metadata["parameter_units"] == "original_image_pixels"
    with pytest.raises(RuntimeError, match="cellpose_protocol_invalid"):
        runner.prepare_detection_input(image, {"engine": "cellpose-sam-ncl", "protocol_version": "4.0.0"})


def test_final_runner_verifies_its_release_lock(monkeypatch, tmp_path):
    source = engine._assets()
    module_spec = importlib.util.spec_from_file_location("cellpose_integrity_contract", source / "runner.py")
    assert module_spec is not None and module_spec.loader is not None
    runner = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)
    lock = json.loads((source / "runtime.lock.json").read_text())
    runner.verify_assets(lock)
    for name in ("runner.py", "requirements.lock"):
        shutil.copyfile(source / name, tmp_path / name)
    monkeypatch.setattr(runner, "__file__", str(tmp_path / "runner.py"))
    (tmp_path / "requirements.lock").write_bytes(b"changed dependency lock")
    with pytest.raises(RuntimeError, match="cellpose_adapter_integrity_failed"):
        runner.verify_assets(lock)


def test_ncl_delegates_normalization_and_legacy_arithmetic_stays_unchanged(monkeypatch):
    module_spec = importlib.util.spec_from_file_location("cellpose_normalization_contract", engine._assets() / "runner.py")
    assert module_spec is not None and module_spec.loader is not None
    runner = importlib.util.module_from_spec(module_spec)
    module_spec.loader.exec_module(runner)
    values = np.arange(30, dtype=np.float32).reshape(5, 6)
    unchanged = values.copy()
    calls = []
    def normalize_img(channels, *, normalize, percentile):
        assert channels.dtype == np.float32 and channels.shape == (5, 6, 3)
        assert normalize is True and percentile == (1., 99.)
        assert np.array_equal(channels[..., 0], unchanged)
        assert not channels[..., 1:].any()
        calls.append("official")
        channels[..., 0] = 2
        return channels
    monkeypatch.setitem(runner.sys.modules, "cellpose", SimpleNamespace(transforms=SimpleNamespace(normalize_img=normalize_img)))
    channels, metadata = runner.normalize_detection_channels(values, NclCellposeDetectorSpec().model_dump())
    assert calls == ["official"] and np.all(channels[..., 0] == 2)
    assert metadata["implementation"] == "cellpose.transforms.normalize_img"
    assert metadata["percentile_sampling_stride"] == [1, 1]
    legacy, old_metadata = runner.normalize_detection_channels(values, CellposeDetectorSpec().model_dump())
    low, high = np.percentile(values, [1., 99.])
    assert np.array_equal(legacy[..., 0], (values.astype(np.float32) - low) / (high - low))
    assert calls == ["official"] and "original_low" in old_metadata
    assert np.array_equal(values, unchanged)


def test_model_mutation_rejected(tmp_path):
    path = tmp_path / "model"
    path.write_bytes(b"fixed model")
    original_stat = path.stat()
    expected = hashlib.sha256(path.read_bytes()).hexdigest()
    engine._verify_file(path, expected, path.stat().st_size, "cellpose_model_integrity_failed")
    path.write_bytes(b"other model")
    os.utime(path, ns=(original_stat.st_atime_ns, original_stat.st_mtime_ns))
    with pytest.raises(ValueError, match="cellpose_model_integrity_failed"):
        engine._verify_file(path, expected, path.stat().st_size, "cellpose_model_integrity_failed")


def test_installed_wheel_uses_verified_app_cwd_assets(monkeypatch, tmp_path):
    source = engine._assets()
    app = tmp_path / "app"
    assets = app / "engines/cellpose"
    assets.mkdir(parents=True)
    entries = []
    for name in ("runtime.lock.json", "runner.py", "requirements.lock"):
        path = assets / name
        shutil.copyfile(source / name, path)
        entries.append({"path": f"engines/cellpose/{name}", "size": path.stat().st_size,
                        "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (app / "local-release.json").write_text(json.dumps({"schema": "cytellect-local-release/1",
                                                       "platform": "windows-x64", "files": entries}))
    monkeypatch.delenv("CYTELLECT_CELLPOSE_ASSETS", raising=False)
    monkeypatch.setattr(engine, "__file__", str(tmp_path / "isolated-wheel/site-packages/cytellect_analysis/cellpose_engine.py"))
    monkeypatch.chdir(app)
    assert engine._assets() == assets
    explicit = tmp_path / "operator-specified-assets"
    monkeypatch.setenv("CYTELLECT_CELLPOSE_ASSETS", str(explicit))
    assert engine._assets() == explicit
    monkeypatch.delenv("CYTELLECT_CELLPOSE_ASSETS")
    (assets / "runner.py").write_bytes(b"changed executable")
    with pytest.raises(ValueError, match="cellpose_adapter_integrity_failed"):
        engine._assets()


def test_cwd_assets_without_release_manifest_are_rejected(monkeypatch, tmp_path):
    assets = tmp_path / "engines/cellpose"
    assets.mkdir(parents=True)
    (assets / "runtime.lock.json").write_text("{}")
    monkeypatch.delenv("CYTELLECT_CELLPOSE_ASSETS", raising=False)
    # Keep the simulated wheel elsewhere, so its own ancestors do not discover
    # this directory through the existing trusted-source path.
    monkeypatch.setattr(engine, "__file__", str(tmp_path.parent / "other-wheel/site-packages/cytellect_analysis/cellpose_engine.py"))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(ValueError, match="cellpose_adapter_integrity_failed"):
        engine._assets()


def test_runtime_missing_does_not_invoke_inference(monkeypatch, tmp_path):
    monkeypatch.delenv("CYTELLECT_CELLPOSE_PYTHON", raising=False)
    def forbidden(*args, **kwargs):
        raise AssertionError("missing runtime must not launch or fetch")
    monkeypatch.setattr(engine.subprocess, "run", forbidden)
    assert engine.runtime_status()["error"] == "cellpose_runtime_missing"
    with pytest.raises(ValueError, match="cellpose_runtime_missing"):
        detect_cellpose(np.zeros((3, 3), np.uint8), CellposeDetectorSpec(), tmp_path)


def test_ambiguous_boundary_candidates_not_clipped():
    # Integer membership fixture only; no artificial image detection is run.
    nuclei = np.zeros((9, 13), np.uint32)
    nuclei[1:8, 1:6] = 7
    nuclei[1:8, 7:12] = 9
    raw = np.zeros_like(nuclei)
    raw[3:5, 2:4] = 3
    raw[3, 5:8] = 4
    raw[1, 3] = 5
    raw[0, 0] = 6
    labels, info = bind_nucleolar_candidates(raw, nuclei)
    assert int(labels.max()) == 1
    assert info["parent_ids"] == {1: 7}
    assert labels[3, 5] == 0 and labels[1, 3] == 0
    assert {item["reason"] for item in info["review_candidates"]} == {
        "multiple_parent_nuclei", "touches_nuclear_boundary", "outside_adopted_nuclei"}
    assert info["nucleolar_states"] == {7: "review_required", 9: "review_required"}
    assert raw[3, 5] == 4


def test_disconnected_input_label_has_distinct_output_ids():
    nuclei = np.ones((10, 10), np.uint32)
    raw = np.zeros_like(nuclei)
    raw[2:4, 2:4] = 1
    raw[6:8, 6:8] = 1
    labels, info = bind_nucleolar_candidates(raw, nuclei)
    assert set(np.unique(labels)) == {0, 1, 2}
    assert info["parent_ids"] == {1: 1, 2: 1}


@pytest.mark.parametrize("detector", [CellposeDetectorSpec(), NclCellposeDetectorSpec()])
def test_subprocess_roundtrip_preserves_original_pixels(monkeypatch, tmp_path, detector):
    image = np.arange(12, dtype=np.uint16).reshape((3, 4))
    original = image.copy()
    monkeypatch.setattr(engine, "runtime_status", lambda: {"available": True})
    monkeypatch.setenv("CYTELLECT_CELLPOSE_PYTHON", "isolated-python")
    monkeypatch.setenv("CYTELLECT_CELLPOSE_MODEL_DIR", str(tmp_path / "models"))
    def execute(command, **kwargs):
        assert command[1] == "-I"
        assert kwargs["env"]["HF_HUB_OFFLINE"] == "1"
        assert "PYTHONPATH" not in kwargs["env"]
        request = json.loads(Path(command[-2]).read_text())
        assert np.array_equal(np.load(request["input_path"]), image)
        assert request["parameters"]["maximum_size_fraction"] == 1.
        assert request["parameters"]["engine"] == detector.engine
        assert request["parameters"]["protocol_version"] == detector.protocol_version
        labels = np.zeros(image.shape, np.uint32)
        np.save(request["output_path"], labels)
        Path(command[-1]).write_text(json.dumps({"status": "succeeded", "coordinate_transform": {"scale_x": 1},
                                               "preprocessing": {"protocol_version": detector.protocol_version}}))
        return subprocess.CompletedProcess(command, 0)
    monkeypatch.setattr(engine.subprocess, "run", execute)
    labels, info = detect_cellpose(image, detector, tmp_path / "attempt")
    assert labels.dtype == np.uint32 and labels.shape == image.shape
    assert np.array_equal(image, original)
    assert info["measurement_pixels"] == "original, unchanged"
    assert info["detection_preprocessing"]["protocol_version"] == detector.protocol_version
    assert not (tmp_path / "attempt/cellpose-input.npy").exists()
    assert not (tmp_path / "attempt/cellpose-request.json").exists()


def test_specific_runner_error_preserved(monkeypatch, tmp_path):
    monkeypatch.setattr(engine, "runtime_status", lambda: {"available": True})
    monkeypatch.setenv("CYTELLECT_CELLPOSE_PYTHON", "isolated-python")
    monkeypatch.setenv("CYTELLECT_CELLPOSE_MODEL_DIR", str(tmp_path / "models"))
    def execute(command, **kwargs):
        Path(command[-1]).write_text(json.dumps({"status": "failed", "error": "cellpose_gpu_unavailable"}))
        return subprocess.CompletedProcess(command, 1)
    monkeypatch.setattr(engine.subprocess, "run", execute)
    with pytest.raises(ValueError, match="cellpose_gpu_unavailable"):
        detect_cellpose(np.ones((3, 4), np.uint8), CellposeDetectorSpec(), tmp_path / "attempt")


@pytest.mark.parametrize("version", ["4.2.0", "4.2.1", "4.3.0"])
def test_refinement_dispatch_retains_parent_evidence_and_legacy_replay(monkeypatch, tmp_path, version):
    # Integer membership/call-contract only. Biological acceptance uses private
    # supplied specimens separately, never these tiny algebraic arrays.
    from cytellect_analysis import ncl_signal_support

    image = np.arange(100, dtype=np.uint8).reshape(10, 10)
    nuclei = np.ones((10, 10), np.uint32)
    raw = np.zeros_like(nuclei)
    raw[3:5, 3:5] = 8
    raw[0, 2] = 9  # truncated sibling keeps the parent incomplete
    calls = []
    monkeypatch.setattr(engine, "runtime_status", lambda: {"available": True})
    monkeypatch.setenv("CYTELLECT_CELLPOSE_PYTHON", "isolated-python")
    monkeypatch.setenv("CYTELLECT_CELLPOSE_MODEL_DIR", str(tmp_path / "models"))

    def execute(command, **kwargs):
        request = json.loads(Path(command[-2]).read_text())
        assert request["parameters"]["protocol_version"] == version
        np.save(request["output_path"], raw)
        Path(command[-1]).write_text(json.dumps({"status": "succeeded", "coordinate_transform": {"scale_x": 1}}))
        return subprocess.CompletedProcess(command, 0)

    def refine(original, anchors, parents):
        assert np.array_equal(original, image) and np.array_equal(parents, nuclei)
        assert set(np.unique(anchors)) == {0, 1}
        calls.append("refine")
        labels = anchors.copy()
        labels[5, 3] = 1
        return labels, labels.copy(), {"parent_ids": {1: 1}, "objects": {
            1: {"parent_id": 1, "source_anchor_ids": [1], "support_ids": [1]}},
            "signal_support_policy": {"protocol_version": "1.0.0"}}

    monkeypatch.setattr(engine.subprocess, "run", execute)
    monkeypatch.setattr(ncl_signal_support, "refine_ncl_signal_support", refine)
    destination = tmp_path / version
    labels, info = detect_cellpose(image, NclParentCellposeDetectorSpec(protocol_version=version), destination, nuclei)
    assert info["nucleolar_states"] == {1: "review_required"}
    assert info["review_candidate_count"] == 1
    assert np.array_equal(np.load(destination / "cellpose-raw-labels.npy"), raw)
    assert info["parent_ids"] == {1: 1}
    if version == "4.3.0":
        assert calls == ["refine"] and labels[5, 3] == 1
        assert info["objects"][1]["source_model_objects"][0]["source_label_id"] == 8
        assert np.load(destination / info["anchor_mask_artifact"])[5, 3] == 0
        assert np.load(destination / info["signal_support_artifact"])[5, 3] == 1
    else:
        assert not calls and labels[5, 3] == 0
        assert "signal_support_policy" not in info


def test_signal_support_never_creates_anchorless_objects_or_changes_constant_anchors():
    from cytellect_analysis.ncl_signal_support import refine_ncl_signal_support

    # Undefined-class and empty-set arithmetic, not model/image acceptance.
    image = np.full((5, 5), 3, np.uint8)
    parents = np.ones((5, 5), np.uint32)
    anchors = np.zeros((5, 5), np.uint32)
    labels, support, info = refine_ncl_signal_support(image, anchors, parents)
    assert not labels.any() and not support.any() and info["objects"] == {}
    anchors[2, 2] = 7
    labels, support, info = refine_ncl_signal_support(image, anchors, parents)
    assert np.array_equal(labels > 0, anchors > 0) and not support.any()
    assert info["signal_support_parents"][0]["status"] == "insufficient_signal_classes"
    parents[2, 2] = 0
    with pytest.raises(ValueError, match="cellpose_refinement_anchor_parent_invalid"):
        refine_ncl_signal_support(image, anchors, parents)


def test_missing_python_dependency_has_runtime_error(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("cellpose_runner_test", engine._assets() / "runner.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    def missing_dependency(_request):
        raise ModuleNotFoundError("private details should never be emitted")
    monkeypatch.setattr(module, "run", missing_dependency)
    receipt = tmp_path / "receipt.json"
    monkeypatch.setattr(module.sys, "argv", ["runner.py", str(tmp_path / "request.json"), str(receipt)])
    assert module.main() == 1
    assert json.loads(receipt.read_text()) == {"status": "failed", "error": "cellpose_runtime_missing"}

"""Nuclear-only adapter: one native plane, actual parameters and fixed runtime."""
from __future__ import annotations

import json
import os
from pathlib import Path

import numpy as np
import pytest
import tifffile
from cytellect_analysis import engine
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.region_contracts import NuclearDetectorSpec
from cytellect_analysis.regions import _array_hash


def fake_bridge(tmp_path, monkeypatch, *, output=None, info_change=None):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    java = runtime / "java"
    java.write_bytes(b"fixed test executable")
    calls = []
    monkeypatch.setattr(engine, "runtime_info", lambda executable: (
        runtime, java, {"model": {"sha256": "a" * 64}, "plugins": []},
    ))

    def execute(destination, actual_runtime, actual_java, scratch):
        request = json.loads((destination / "request.json").read_text())
        image = tifffile.imread(destination / "nuclear.tif")
        calls.append((request, image.copy(), scratch))
        assert actual_runtime == runtime and actual_java == java
        assert set(path.name for path in destination.glob("*.tif")) == {"nuclear.tif"}
        labels = np.zeros(image.shape, dtype=np.float32) if output is None else output
        tifffile.imwrite(destination / "nuclei.tif", labels, photometric="minisblack")
        info = {"operation": "nuclear-only", "model": "Versatile (fluorescent nuclei)",
                "parameters": request["detector"], "headless": True, "n_tiles": 1}
        info.update(info_change or {})
        (destination / "engine-result.json").write_text(json.dumps(info))
        return engine._assets()

    monkeypatch.setattr(engine, "_execute_bridge", execute)
    return calls


@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_one_native_plane_and_requested_parameters_preserved(tmp_path, monkeypatch, dtype):
    image = np.arange(24, dtype=dtype).reshape(4, 6)
    image.flags.writeable = False
    original = image.copy()
    calls = fake_bridge(tmp_path, monkeypatch)
    specification = NuclearDetectorSpec(probability=0.67, nms=0.22, percentile_low=2, percentile_high=98)
    labels, info = engine.detect_nuclei(image, specification, tmp_path / "out", "fixed", tmp_path / "scratch")
    request, transported, scratch = calls[0]
    assert request["mode"] == "nuclear-only" and "recipe" not in request
    assert request["detector"] == specification.model_dump(mode="json")
    assert scratch == tmp_path / "scratch"
    np.testing.assert_array_equal(transported, original)
    np.testing.assert_array_equal(image, original)
    assert transported.dtype == image.dtype and labels.dtype == np.uint32 and not labels.any()
    assert info["parameters"] == request["detector"]
    assert info["nuclear_detector_protocol_version"] == "1.0.0"
    assert info["input_sha256"] == _array_hash(image, "|u1" if image.dtype.itemsize == 1 else "<u2")
    assert info["coordinate_transform"] == {"scale_x": 1, "scale_y": 1}
    assert not list((tmp_path / "out").glob("ncl*"))
    assert not list((tmp_path / "out").glob("gfp*"))
    assert not (tmp_path / "out" / "nucleoli.tif").exists()


@pytest.mark.parametrize("shape", [(2049, 3), (1644, 1644), (4096, 4096)])
def test_capacity_fails_before_runtime_or_writes(tmp_path, monkeypatch, shape):
    monkeypatch.setattr(engine, "runtime_info", lambda _: pytest.fail("runtime must not be inspected"))
    image = np.zeros(shape, dtype=np.uint8)
    with pytest.raises(engine.EngineUnavailable, match="fiji_detection_capacity_exceeded"):
        engine.detect_nuclei(image, NuclearDetectorSpec(), tmp_path / "out", "unused")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("image,error", [
    (np.empty((0, 3), dtype=np.uint8), "fiji_input_dimensions"),
    (np.zeros((2, 3, 3), dtype=np.uint8), "fiji_input_dimensions"),
    (np.zeros((2, 3), dtype=np.float32), "fiji_input_format"),
    (np.zeros((2, 3), dtype=bool), "fiji_input_format"),
])
def test_unsupported_input_never_reinterpreted(tmp_path, image, error):
    with pytest.raises(ValueError, match=error):
        engine.detect_nuclei(image, NuclearDetectorSpec(), tmp_path / "out", "unused")
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("value", [-1, 0.5, np.nan, np.inf, 2**24])
def test_invalid_output_labels_fail_closed(tmp_path, monkeypatch, value):
    fake_bridge(tmp_path, monkeypatch, output=np.full((3, 4), value, dtype=np.float32))
    with pytest.raises(engine.EngineUnavailable, match="fiji_invalid_output_labels"):
        engine.detect_nuclei(np.zeros((3, 4), dtype=np.uint8), NuclearDetectorSpec(), tmp_path / "out", "fixed")


def test_output_shape_and_provenance_must_match_request(tmp_path, monkeypatch):
    fake_bridge(tmp_path, monkeypatch, output=np.zeros((4, 3), dtype=np.float32))
    with pytest.raises(engine.EngineUnavailable, match="fiji_invalid_output_labels"):
        engine.detect_nuclei(np.zeros((3, 4), dtype=np.uint8), NuclearDetectorSpec(), tmp_path / "out", "fixed")


def test_foreign_output_provenance_rejected(tmp_path, monkeypatch):
    fake_bridge(tmp_path, monkeypatch, info_change={"parameters": {}})
    with pytest.raises(engine.EngineUnavailable, match="fiji_invalid_output_provenance"):
        engine.detect_nuclei(np.zeros((3, 4), dtype=np.uint8), NuclearDetectorSpec(), tmp_path / "out", "fixed")


def test_unconfigured_nuclear_engine_never_substitutes_detector(tmp_path):
    with pytest.raises(engine.EngineUnavailable, match="fiji_not_configured"):
        engine.detect_nuclei(np.zeros((3, 4), dtype=np.uint8), NuclearDetectorSpec(), tmp_path / "out", "")
    assert not (tmp_path / "out").exists()


@pytest.mark.fiji
@pytest.mark.parametrize("parameters", [NuclearDetectorSpec(), NuclearDetectorSpec(
    probability=0.63, nms=0.25, percentile_low=2, percentile_high=98,
)])
def test_real_public_hoechst_exactly_matches_old_nuclear_command(tmp_path, parameters):
    executable = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not executable:
        pytest.skip("Actual Fiji not configured; nuclear-only inference has NOT passed")
    root = Path(__file__).resolve().parents[1]
    manifest = json.loads((root / "fixtures/public/bbbc039/manifest.json").read_text())
    image = tifffile.imread(root / "fixtures/public/bbbc039" / manifest["images"][0]["image"]["path"])
    original = image.copy()
    values = parameters.model_dump(exclude={"engine", "model"})
    old, _, _ = engine.detect({"dapi": image}, Recipe(id="gfp-nuclear-2d", **values),
                              tmp_path / "old", executable, scratch_root=tmp_path)
    actual, info = engine.detect_nuclei(image, parameters, tmp_path / "new", executable, scratch_root=tmp_path)
    np.testing.assert_array_equal(actual, old)
    np.testing.assert_array_equal(image, original)
    assert info["parameters"] == parameters.model_dump(mode="json")
    assert info["operation"] == "nuclear-only" and info["headless"] is True
    assert info["model_sha256"] == "b0eb820e455db0ec8326d3b6f456a1b2d4aff8d7dd818a71481f8041958309e3"
    assert not (tmp_path / "new" / "nucleoli.tif").exists()

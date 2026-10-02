"""Real Fiji tests are opt-in and never replaced by synthetic ground-truth masks."""
import os

import numpy as np
import pytest
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.engine import EngineUnavailable, detect
from cytellect_analysis.masks import validate_labels
from cytellect_analysis.synthetic import synthetic_field


@pytest.mark.parametrize("recipe_id", ["ncl-native-2d", "gfp-nuclear-2d"])
@pytest.mark.parametrize("shape", [(2049, 1), (1, 2049), (2048, 1319), (4096, 4096)])
def test_automatic_detection_capacity_rejected_before_runtime_or_writes(tmp_path, monkeypatch, recipe_id, shape):
    from cytellect_analysis import engine
    from cytellect_worker.errors import SAFE_ERRORS

    def forbidden_runtime(_):
        pytest.fail("An over-capacity request must not inspect or launch Fiji")

    monkeypatch.setattr(engine, "runtime_info", forbidden_runtime)
    # Broadcast views exercise admission without allocating full image buffers.
    pixels = np.broadcast_to(np.zeros((1, 1), dtype=np.uint16), shape)
    channels = {"dapi": pixels, "ncl": pixels, "gfp": pixels}
    output = tmp_path / "attempt"
    with pytest.raises(EngineUnavailable, match="^fiji_detection_capacity_exceeded$"):
        detect(channels, Recipe(id=recipe_id), output, "unused")
    assert not output.exists()
    assert "fiji_detection_capacity_exceeded" in SAFE_ERRORS


@pytest.mark.parametrize("shape,reuse", [
    ((1536, 1739), False),  # The published NCL field used in resource profiling.
    ((2048, 1318), False),  # Just below the pixel ceiling and at the edge ceiling.
    ((1800, 1500), False),  # Exactly 2,700,000 pixels.
    ((4096, 4096), True),  # Supplied labels do not invoke automatic nuclei inference.
])
def test_capacity_admission_and_edited_nuclei_reuse(tmp_path, monkeypatch, shape, reuse):
    from cytellect_analysis import engine

    class RuntimeReached(Exception):
        pass

    def runtime_reached(_):
        raise RuntimeReached

    monkeypatch.setattr(engine, "runtime_info", runtime_reached)
    pixels = np.broadcast_to(np.zeros((1, 1), dtype=np.uint16), shape)
    labels = np.broadcast_to(np.zeros((1, 1), dtype=np.uint32), shape) if reuse else None
    with pytest.raises(RuntimeReached):
        detect({"dapi": pixels, "ncl": pixels}, Recipe(), tmp_path, "unused", nuclei=labels)


def test_unconfigured_engine_fails_closed(tmp_path):
    channels, *_ = synthetic_field()
    with pytest.raises(EngineUnavailable, match="fiji_not_configured"):
        detect(channels, Recipe(), tmp_path, "")


@pytest.fixture
def fiji():
    path = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not path:
        pytest.skip("Real Fiji runtime not configured; this check has NOT passed")
    return path


@pytest.mark.fiji
def test_real_cpu_stardist_and_nucleoli(tmp_path, fiji):
    channels, *_ = synthetic_field()
    original = {key: value.copy() for key, value in channels.items()}
    nuclei, nucleoli, provenance = detect(channels, Recipe(), tmp_path, fiji)
    assert nuclei.shape == (256, 256)
    assert len(np.unique(nuclei)) - 1 == 9
    assert len(np.unique(nucleoli)) - 1 == 18
    validate_labels(nuclei, nucleoli)
    assert provenance["headless"] is True
    assert provenance["automatic_detection_admission"] == {
        "profile": "standard-2g", "applied": True, "max_side_px": 2048, "max_pixels": 2_700_000,
    }
    assert provenance["model_sha256"] == "b0eb820e455db0ec8326d3b6f456a1b2d4aff8d7dd818a71481f8041958309e3"
    assert all(np.array_equal(channels[key], original[key]) for key in channels)
    assert (tmp_path / "engine-result.json").is_file()


@pytest.mark.fiji
def test_edited_nuclei_preserved_and_uniform_signal_not_substituted(tmp_path, fiji):
    channels, nuclei, _ = synthetic_field()
    channels["ncl"] = np.full_like(channels["ncl"], 500)
    detected, nucleoli, info = detect(channels, Recipe(), tmp_path, fiji, nuclei=nuclei)
    np.testing.assert_array_equal(detected, nuclei)
    assert np.count_nonzero(nucleoli) == 0
    assert set(info["nucleolar_status"].values()) == {"indeterminate"}
    assert info["automatic_detection_admission"]["applied"] is False


@pytest.mark.fiji
def test_explicit_auxiliary_and_size_filters(tmp_path, fiji):
    channels, nuclei, _ = synthetic_field()
    _, nucleoli, info = detect(channels, Recipe(minimum_area_px=100000, nucleolar_method="dapi-low",
                                               smoothing_sigma_px=1, split_touching=True),
                               tmp_path, fiji, nuclei=nuclei)
    assert not np.any(nucleoli)
    assert set(info["nucleolar_status"].values()) <= {"no_candidate", "indeterminate"}


@pytest.mark.fiji
def test_actual_imagej_roi_decoder_preserves_holes_labels_and_edges(tmp_path, fiji):
    import json

    from cytellect_analysis.engine import _assets, _classpath, _run, runtime_info
    from cytellect_analysis.roi import export_roi_zip
    labels = np.zeros((21, 25), dtype=np.uint32)
    labels[0:15, 0:17] = 7
    labels[3:9, 4:10] = 0
    labels[18:21, 20:25] = 3000000000
    archive = export_roi_zip(labels, tmp_path / "roi.zip")
    raw = tmp_path / "pixels.u32"
    request = tmp_path / "request.json"
    request.write_text(json.dumps({"roi_zip": str(archive), "roi_output": str(raw)}))
    runtime, java, _ = runtime_info(fiji)
    command = [str(java), "--add-opens=java.base/java.lang=ALL-UNNAMED", "-Djava.awt.headless=true",
               "-cp", _classpath(runtime, tmp_path), str(_assets() / "CytellectEngine.java"), str(request)]
    _run(command, tmp_path, 120, os.environ.copy())
    actual = np.fromfile(raw, dtype="<u4").reshape(labels.shape)
    np.testing.assert_array_equal(actual, labels)


@pytest.mark.fiji
def test_legacy_actual_stardist_restores_original_coordinates(tmp_path, fiji):
    from skimage.transform import resize
    channels, *_ = synthetic_field()
    channels = {key: np.rint(resize(value, (512,512), preserve_range=True)).astype(np.uint16)
                for key, value in channels.items()}
    nuclei, nucleoli, info = detect(channels, Recipe(id="ncl-legacy-rgb"), tmp_path, fiji)
    assert nuclei.shape == (512,512)
    assert len(np.unique(nuclei)) - 1 == 9
    validate_labels(nuclei,nucleoli)
    assert info["coordinate_transform"]["measurement_shape"] == [320,320]
    assert info["coordinate_transform"]["scale_x"] == 0.625
    assert info["recipe"] == "ncl-legacy-rgb"

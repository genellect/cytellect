"""ImageJ/MorphoLibJ signal masks; original plane and explicit threshold rules."""
import json
import os

import numpy as np
import pytest
import tifffile
from cytellect_analysis import engine
from cytellect_analysis.signal_engine import SignalDetectorSpec, detect_positive_regions
from pydantic import ValidationError


@pytest.mark.parametrize("parameters", [
    {}, {"threshold_method": "manual"}, {"threshold_method": "otsu", "threshold": 10.0},
    {"threshold_method": "manual", "threshold": float("nan")},
])
def test_no_implicit_or_inconsistent_threshold(parameters):
    with pytest.raises(ValidationError):
        SignalDetectorSpec(**parameters)


def test_adapter_preserves_source_and_validates_operation(tmp_path, monkeypatch):
    runtime = tmp_path / "runtime"
    runtime.mkdir()
    java = runtime / "java"
    java.write_bytes(b"fixed test executable")
    monkeypatch.setattr(engine, "runtime_info", lambda _: (
        runtime, java, {"model": {"sha256": "a" * 64}, "plugins": []}))
    image = np.arange(20, dtype=np.uint16).reshape(4, 5)
    image.flags.writeable = False
    parameters = SignalDetectorSpec(threshold_method="manual", threshold=8.0)

    def execute(output, *_):
        request = json.loads((output / "request.json").read_text())
        assert request["mode"] == "signal-only"
        np.testing.assert_array_equal(tifffile.imread(output / "signal.tif"), image)
        tifffile.imwrite(output / "regions.tif", (image > 8).astype(np.float32))
        (output / "engine-result.json").write_text(json.dumps({
            "operation": "signal-only", "parameters": request["detector"],
            "status": "candidate", "biological_positivity_established": False,
        }))
        return engine._assets()

    monkeypatch.setattr(engine, "_execute_bridge", execute)
    labels, info = detect_positive_regions(image, parameters, tmp_path / "out", "fixed")
    np.testing.assert_array_equal(labels > 0, image > 8)
    assert labels.shape == image.shape and labels.dtype == np.uint32
    assert info["signal_detector_protocol_version"] == "1.0.0"
    assert "model_sha256" not in info
    assert info["exploratory_threshold"] and not info["biological_positivity_established"]


@pytest.mark.fiji
@pytest.mark.parametrize("dtype", [np.uint8, np.uint16])
def test_real_fiji_otsu_manual_uniform_and_original_pixels(tmp_path, dtype):
    runtime = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not runtime:
        pytest.skip("Locked Fiji runtime is required for this integration check")
    # Known disconnected foreground, including an isolated pixel to remove.
    image = np.full((48, 64), 12, dtype=dtype)
    image[4:12, 5:15] = 160
    image[22:35, 40:55] = 220
    image[40, 2] = 220
    expected = image > 12
    expected[40, 2] = False
    original = image.copy()
    for method in ("otsu", "manual"):
        parameters = SignalDetectorSpec(threshold_method=method,
                                        threshold=12.0 if method == "manual" else None,
                                        minimum_area_px=2)
        labels, info = detect_positive_regions(image, parameters, tmp_path / method, runtime)
        np.testing.assert_array_equal(labels > 0, expected)
        assert set(np.unique(labels)) == {0, 1, 2}
        assert info["status"] == "candidate" and info["headless"]
        assert info["connectivity"] == 8 and info["operation"] == "signal-only"
        # Analytical reference uses the original uint source, never blurred input.
        assert sorted(image[labels == i].sum(dtype=np.float64) for i in (1, 2)) == [12800, 42900]
    uniform = np.full_like(image, 90)
    labels, info = detect_positive_regions(uniform, SignalDetectorSpec(threshold_method="otsu"),
                                           tmp_path / "uniform", runtime)
    assert not labels.any() and info["status"] == "indeterminate"
    np.testing.assert_array_equal(image, original)

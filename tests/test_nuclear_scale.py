"""Automatic nuclear detection scale (nuclear-size/1.0.0): estimate, choice, recipe and worker."""
import copy
import json
import os
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis.nuclear_scale import (
    TARGET_DIAMETER_PX,
    automatic_detection_max_side,
    estimate_nuclear_diameter,
)
from cytellect_analysis.region_contracts import AutoScaledNuclearRecipe, RegionAnalysisRequest
from cytellect_analysis.region_exports import region_methods
from cytellect_api.storage import read_json
from cytellect_worker import regions
from test_region_nuclear_worker import detected_labels, nuclear_fields
from test_region_worker import execute


def textured_nuclei(side, radius, centres, seed=0):
    """Bright textured disks (chromatin-like specks and dark holes) with bright debris outside."""
    rng = np.random.default_rng(seed)
    y, x = np.mgrid[:side, :side]
    image = rng.normal(8, 2, (side, side))
    for cy, cx in centres:
        disk = (y - cy) ** 2 + (x - cx) ** 2 <= radius ** 2
        image[disk] = 120 + rng.normal(0, 25, int(disk.sum()))
        hole = (y - cy - radius // 3) ** 2 + (x - cx) ** 2 <= (radius // 5) ** 2
        image[hole] = 40
    for cy, cx in rng.integers(0, side, (30, 2)):
        image[max(0, cy - 2):cy + 2, max(0, cx - 2):cx + 2] = 250
    return np.clip(image, 0, 255).astype(np.uint8)


def test_large_nuclei_are_measured_and_get_a_detection_copy_at_the_target_size():
    centres = [(400, 400), (400, 1200), (1200, 400), (1200, 1200), (800, 1600)]
    image = textured_nuclei(2000, 150, centres)
    record = estimate_nuclear_diameter(image)
    assert record["protocol"] == "nuclear-size/1.0.0" and record["missing_reason"] is None
    assert record["diameter_px"] == pytest.approx(300, rel=0.08)
    side = automatic_detection_max_side(image.shape, record["diameter_px"])
    assert side == round(2000 * TARGET_DIAMETER_PX / record["diameter_px"])


def test_small_nuclei_are_never_enlarged_and_bounds_hold():
    image = textured_nuclei(400, 10, [(50 + 60 * i, 50 + 60 * j) for i in range(5) for j in range(5)])
    record = estimate_nuclear_diameter(image)
    assert record["diameter_px"] == pytest.approx(20, rel=0.2)
    assert automatic_detection_max_side(image.shape, record["diameter_px"]) is None
    assert automatic_detection_max_side((4000, 4000), 4000.0) == 64
    assert automatic_detection_max_side((4000, 4000), 50.0) == 2048
    assert automatic_detection_max_side((100, 100), None) is None


def test_no_foreground_or_uniform_image_keeps_capacity_only_detection_with_a_reason():
    assert estimate_nuclear_diameter(np.full((64, 64), 7, np.uint16))["missing_reason"] == "uniform_image"
    with pytest.raises(ValueError, match="nuclear_scale_input_invalid"):
        estimate_nuclear_diameter(np.zeros((4, 4, 3), np.uint8))


def auto_recipe():
    return AutoScaledNuclearRecipe(region_set_id="nuclei", label="Nuclei", defining_channel_id="dna",
                                   nuclear_role_source="recorded_stain")


def test_recipe_is_a_separate_version_with_a_fixed_scale_protocol():
    data = auto_recipe().model_dump(mode="json")
    assert data["version"] == "1.7.0" and data["detection_scale"] == "nuclear-size/1.0.0"
    assert RegionAnalysisRequest.model_validate({"field_ids": ["f1"], "recipe": data}).recipe == auto_recipe()
    with pytest.raises(ValueError):
        AutoScaledNuclearRecipe.model_validate({**data, "detection_scale": "nuclear-size/9.9.9"})


def test_worker_sizes_the_detection_copy_per_field_records_it_and_reuses_masks(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    config["recipe"] = auto_recipe().model_dump(mode="json")
    calls = []

    def detector(image, parameters, destination, executable, scratch_root=None, *, detection_max_side=None):
        calls.append(detection_max_side)
        return detected_labels(), {}
    monkeypatch.setattr(regions, "detect_nuclei", detector)
    report = execute(store, settings, config)
    assert not report["field_failures"] and len(calls) == 1
    event = read_json(store.safe_path("results", "r1", "provenance.json"))["fields"]["f1"]["detector"]
    scale = event["detection_scale"]
    assert scale["protocol"] == "nuclear-size/1.0.0" and scale["detection_max_side_px"] == calls[0]
    image = np.load(store.safe_path("workspaces", "w", "fields", "f1", "channel-dna.npy"))
    expected = estimate_nuclear_diameter(image)
    assert scale["diameter_px"] == expected["diameter_px"]
    assert calls[0] == automatic_detection_max_side(image.shape, expected["diameter_px"])
    provenance = read_json(store.safe_path("results", "r1", "provenance.json"))
    assert "Detection scale: nuclear-size/1.0.0" in region_methods(config, report, provenance)
    repeated = execute(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert not repeated["field_failures"] and len(calls) == 1
    reused = read_json(store.safe_path("results", "r2", "provenance.json"))["fields"]["f1"]["detector"]
    assert reused["detection_scale"] == scale and not reused["executed_this_attempt"]
    tampered = copy.deepcopy(read_json(store.safe_path("results", "r1", "provenance.json")))
    tampered["fields"]["f1"]["detector"]["detection_scale"]["protocol"] = "other"
    store.safe_path("results", "r1", "provenance.json").write_text(json.dumps(tampered))
    refused = execute(store, settings, {**config, "reuse_revision": "r1"}, "r3")
    assert refused["field_failures"] == [{"field_id": "f1", "reason": "region_parent_detector_provenance_invalid"}]


@pytest.mark.fiji
def test_high_resolution_nuclei_are_not_split_into_texture(tmp_path):
    """Regression: oversized nuclei (Airyscan-like) must segment like the original-resolution image.

    The public BBBC013 nuclear image is enlarged six times. Capacity-only detection splits the
    nuclei; the automatic scale must recover the original-resolution count.
    """
    executable = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not executable:
        pytest.skip("Real Fiji runtime not configured; this check has NOT passed")
    import tifffile
    from cytellect_analysis.engine import detect_nuclei
    from cytellect_analysis.region_contracts import NuclearDetectorSpec
    from skimage.transform import resize

    root = Path(__file__).resolve().parents[1]
    original = tifffile.imread(root / "fixtures/public/bbbc013/A01-dapi.tif")
    large = np.rint(resize(original, (original.shape[0] * 6, original.shape[1] * 6), order=1,
                           preserve_range=True)).astype(original.dtype)

    def count(image, side, name):
        labels, _ = detect_nuclei(image, NuclearDetectorSpec(), tmp_path / name, executable,
                                  detection_max_side=side)
        return len(np.unique(labels)) - 1

    reference = count(original, None, "original")
    side = automatic_detection_max_side(large.shape, estimate_nuclear_diameter(large)["diameter_px"])
    assert side is not None
    assert count(large, side, "automatic") == pytest.approx(reference, rel=0.1)
    assert count(large, None, "capacity-only") > reference * 1.1  # the failure this protects against

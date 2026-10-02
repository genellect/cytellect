import math

import numpy as np
import pytest
import tifffile
from cytellect_analysis.contracts import Recipe
from cytellect_analysis.images import read_tiff
from cytellect_analysis.legacy import (
    detect_legacy_nucleoli,
    labels_to_original,
    prepare_legacy_channels,
)
from cytellect_analysis.measurement import apply_gfp_gate, measure


def case():
    shape = (100, 100)
    labels = np.zeros(shape, dtype=np.uint32)
    labels[20:60, 20:60] = 1
    channels = {name: np.full(shape, 20, dtype=np.uint8) for name in ("dapi", "ncl", "gfp")}
    channels["dapi"][labels > 0] = 140
    channels["ncl"][labels > 0] = 40
    channels["ncl"][30:40, 30:40] = 120
    channels["gfp"][labels > 0] = 60
    return channels, labels


def test_rgb_max_handles_planar_alpha_and_native_rejects(tmp_path):
    rgb = np.zeros((20, 30, 4), np.uint8)
    rgb[..., 0], rgb[..., 1], rgb[..., 2], rgb[..., 3] = 10, 40, 20, 255
    path = tmp_path / "display.tif"
    tifffile.imwrite(path, rgb, photometric="rgb")
    np.testing.assert_array_equal(read_tiff(path, legacy=True), np.full((20, 30), 40, np.uint8))
    with pytest.raises(ValueError):
        read_tiff(path)
    tifffile.imwrite(path, np.moveaxis(rgb, -1, 0), photometric="rgb", planarconfig="separate")
    assert np.unique(read_tiff(path, legacy=True)).tolist() == [40]


def test_downsampled_detection_dtype_float_measurements_and_label_roundtrip():
    source = {name: np.full((640, 480), 25, np.uint8) for name in ("dapi", "ncl", "gfp")}
    resized, detection, coordinate = prepare_legacy_channels(source, Recipe(id="ncl-legacy-rgb"))
    assert detection.shape == (320, 240) and detection.dtype == np.uint8
    assert resized["ncl"].dtype == np.float64 and np.all(resized["ncl"] == 25)
    assert coordinate["scale_x"] == coordinate["scale_y"] == .5
    assert source["ncl"].shape == (640, 480)
    labels = np.zeros((320, 240), np.uint32)
    labels[5:25, 6:27] = 70000
    full = labels_to_original(labels, (640, 480))
    assert full.dtype == np.uint32
    np.testing.assert_array_equal(full[::2, ::2], labels)


def test_legacy_reference_mean_clipping_epsilon_and_quality():
    channels, nuclei = case()
    recipe = Recipe(id="ncl-legacy-rgb")
    nucleoli, statuses = detect_legacy_nucleoli(channels, nuclei, recipe)
    cells, objects, _ = measure(channels, nuclei, nucleoli, None, recipe,
                                {"condition": "Synthetic", "experimental_unit": "u", "sample": "s",
                                 "acquisition_date": "d", "pair": None}, "field")
    row = cells[0]
    # 1500 pixels at corrected20 and 100 at corrected100.
    mean = (1500*20 + 100*100) / 1600
    assert row["ncl_nucleus_mean_corrected"] == mean
    assert row["ncl_nucleoli_mean_corrected"] == 100
    assert row["legacy_epsilon"] == 1
    assert row["ncl_legacy_release"] == pytest.approx(math.log2((mean+1)/101))
    assert row["independent_nucleus_qc_pass"] is True and not row["excluded"]
    assert row["ncl_log2_nucleoplasm_over_nucleoli"] is None
    assert row["legacy_high_mask_modified"] is False
    assert len(objects) == 1 and not statuses[0]["fallback_top10"]
    gated = apply_gfp_gate(cells, recipe)[0]
    assert gated["gfp_positive"] is True
    assert gated["gfp_gate_threshold"] == 40
    assert gated["gfp_log2_plus1"] == pytest.approx(math.log2(41))


def test_legacy_uniform_and_small_candidate_fallback_are_explicit():
    channels, nuclei = case()
    channels["ncl"][nuclei > 0] = 10  # Below20 background: historicalclip => allzero.
    recipe = Recipe(id="ncl-legacy-rgb")
    nucleoli, statuses = detect_legacy_nucleoli(channels, nuclei, recipe)
    assert statuses[0]["uniform_all_high"] is True
    assert np.array_equal(nucleoli > 0, nuclei > 0)
    row = measure(channels, nuclei, nucleoli, None, recipe, {"acquisition_date": "d"}, "f")[0][0]
    assert row["ncl_nucleus_mean_corrected"] == 0
    assert row["ncl_legacy_release"] == 0
    channels["ncl"][nuclei > 0] = 40
    channels["ncl"][30, 30] = 120
    nucleoli, statuses = detect_legacy_nucleoli(channels, nuclei, recipe)
    assert statuses[0]["fallback_top10"] is True
    assert np.array_equal(nucleoli > 0, nuclei > 0)  # percentile tie, explicitly historical behavior


def test_legacy_batch_gate_uses_only_independent_qc():
    rows = [{"acquisition_date": "d", "gfp_mean_corrected": value, "independent_nucleus_qc_pass": qc,
             "excluded": not qc} for value, qc in [(10, True), (10, True), (1000, False)]]
    gated = apply_gfp_gate(rows, Recipe(id="ncl-legacy-rgb"))
    assert all(r["gfp_gate_threshold"] == 10 for r in gated)
    assert gated[-1]["excluded"] is True
    assert gated[0]["gfp_log2_date_centered"] == 0


def test_restored_candidates_stay_inside_manually_edited_original_parents():
    from cytellect_analysis.masks import validate_labels
    shape = (640, 640)
    nuclei = np.zeros(shape, np.uint32)
    nuclei[100:260, 100:213] = 1
    nuclei[100:260, 213:330] = 2
    channels = {name: np.full(shape, 20, np.uint8) for name in ("dapi", "ncl", "gfp")}
    for image in channels.values():
        image[nuclei > 0] = 100
    labels, _ = detect_legacy_nucleoli(channels, nuclei, Recipe(id="ncl-legacy-rgb"))
    validate_labels(nuclei, labels)

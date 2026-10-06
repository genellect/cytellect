"""Original-coordinate NCL compartments reuse nuclei and retain omitted parents."""
import os

import numpy as np
import pytest
from cytellect_analysis import engine
from cytellect_analysis.compartment_engine import (
    NucleolarDetectorSpec,
    derive_compartment_masks,
    detect_compartments,
)
from cytellect_analysis.regions import _array_hash


def known_field():
    nuclei = np.zeros((48, 64), dtype=np.uint32)
    nuclei[2:18, 2:18] = 3
    nuclei[2:18, 24:40] = 7
    nuclei[24:40, 2:18] = 11
    nuclei[24:40, 24:40] = 19
    ncl = np.full(nuclei.shape, 1200, np.uint16)
    expected = np.zeros(nuclei.shape, dtype=np.uint32)
    ncl[6:10, 6:11] = 40000
    expected[6:10, 6:11] = 1
    ncl[27:29, 27:30] = 50000
    expected[27:29, 27:30] = 2
    ncl[34:37, 33:37] = 40000
    expected[34:37, 33:37] = 3
    ncl[30, 8] = 50000  # This lone pixel is below the explicit minimum area.
    channels = {"dapi": (nuclei > 0).astype(np.uint16) * 30000, "ncl": ncl}
    return channels, nuclei, expected


def test_exact_parent_ids_complement_and_missing_reasons():
    channels, nuclei, nucleoli = known_field()
    states = {3: "candidate", 7: "indeterminate", 11: "no_candidate", 19: "candidate"}
    original = nuclei.copy()
    masks, info = derive_compartment_masks(nuclei, nucleoli, states)
    np.testing.assert_array_equal(masks["nucleoli"], nucleoli)
    expected_plasma = np.where(np.isin(nuclei, [3, 19]) & (nucleoli == 0), nuclei, 0)
    np.testing.assert_array_equal(masks["nucleoplasm"], expected_plasma)
    np.testing.assert_array_equal(nuclei, original)
    assert info["parent_ids"] == {1: 3, 2: 19, 3: 19}
    assert info["nucleolar_states"] == states and info["missing_parent_count"] == 2
    assert info["excluded_nucleus_ids"] == {7: "indeterminate", 11: "no_candidate"}
    assert info["missing_parent_reasons"] == {"indeterminate": 1, "no_candidate": 1}
    assert info["compartment_status"] == "incomplete"
    assert np.sum(channels["ncl"][masks["nucleoli"] == 1], dtype=np.float64) == 800000
    assert np.sum(channels["ncl"][masks["nucleoplasm"] == 3], dtype=np.float64) == 283200
    assert not np.any((masks["nucleoli"] > 0) & (masks["nucleoplasm"] > 0))


@pytest.mark.parametrize("state", ["processing_failed", "indeterminate", "review_required", "no_candidate"])
def test_unresolved_parent_never_becomes_whole_nucleus_nucleoplasm(state):
    nuclei = np.ones((3, 4), dtype=np.uint32)
    masks, info = derive_compartment_masks(nuclei, np.zeros_like(nuclei), {1: state})
    assert not masks["nucleoli"].any() and not masks["nucleoplasm"].any()
    assert info["missing_parent_count"] == 1 and info["nucleolar_states"] == {1: state}


def test_no_fabricated_zero_rows_for_empty_nucleoplasm_or_missing_states():
    nuclei = np.full((3, 4), 19, dtype=np.uint32)
    masks, info = derive_compartment_masks(nuclei, np.ones_like(nuclei), {19: "candidate"})
    assert not masks["nucleoplasm"].any()
    assert info["nucleoplasm_missing_reasons"] == {19: "empty_after_subtraction"}
    assert info["compartment_missing_parent_count"] == {"nucleoli": 0, "nucleoplasm": 1}
    with pytest.raises(ValueError, match="compartment_parent_states_incomplete"):
        derive_compartment_masks(nuclei, np.ones_like(nuclei), {})
    with pytest.raises(ValueError, match="compartment_candidate_mask_missing"):
        derive_compartment_masks(nuclei, np.zeros_like(nuclei), {19: "candidate"})


def test_adapter_reuses_exact_nuclei_and_original_planes(tmp_path, monkeypatch):
    channels, nuclei, expected = known_field()
    for array in [nuclei, *channels.values()]:
        array.flags.writeable = False
    specification = NucleolarDetectorSpec(minimum_area_px=2)
    calls = []

    def existing_detect(actual, recipe, output_dir, executable, *, nuclei, scratch_root):
        assert actual is channels and nuclei.flags.writeable is False
        assert recipe.nucleolar_method == "ncl-otsu" and recipe.minimum_area_px == 2
        assert recipe.smoothing_sigma_px == 0 and not recipe.split_touching
        calls.append(True)
        return nuclei.copy(), expected, {"nuclei_reused": True, "model": "unused", "model_sha256": "unused",
                                        "nucleolar_states": {3: "candidate", 7: "indeterminate",
                                                             11: "no_candidate", 19: "candidate"}}

    monkeypatch.setattr(engine, "detect", existing_detect)
    masks, info = detect_compartments(channels, nuclei, specification, tmp_path, "fixed")
    assert calls == [True] and info["nuclear_detection_performed"] is False
    assert info["parent_nuclear_mask_sha256"] == _array_hash(nuclei, "<u4")
    assert "model" not in info and "model_sha256" not in info
    assert info["canonical_mask_sha256"]["nucleoli"] == _array_hash(masks["nucleoli"], "<u4")


@pytest.mark.fiji
def test_real_fiji_supplied_nuclei_exact_ncl_compartments(tmp_path):
    runtime = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not runtime:
        pytest.skip("Locked Fiji runtime is required for this integration check")
    channels, nuclei, expected = known_field()
    originals = {name: image.copy() for name, image in channels.items()}
    nucleus_original = nuclei.copy()
    masks, info = detect_compartments(channels, nuclei, NucleolarDetectorSpec(minimum_area_px=2),
                                     tmp_path / "engine", runtime)
    np.testing.assert_array_equal(masks["nucleoli"], expected)
    np.testing.assert_array_equal(masks["nucleoplasm"],
                                  np.where(np.isin(nuclei, [3, 19]) & (expected == 0), nuclei, 0))
    assert info["nucleolar_states"] == {3: "candidate", 7: "indeterminate", 11: "no_candidate", 19: "candidate"}
    assert info["missing_parent_count"] == 2 and info["parent_ids"] == {1: 3, 2: 19, 3: 19}
    assert info["nuclei_reused"] and info["n_tiles"] == 0 and not info["nuclear_detection_performed"]
    assert np.sum(channels["ncl"][masks["nucleoli"] == 2], dtype=np.float64) == 300000
    np.testing.assert_array_equal(nuclei, nucleus_original)
    for name, image in channels.items():
        np.testing.assert_array_equal(image, originals[name])

"""Original-coordinate NCL compartments reuse nuclei and retain omitted parents."""
import os

import numpy as np
import pytest
from cytellect_analysis import engine
from cytellect_analysis.compartment_engine import (
    NucleolarDetectorSpec,
    NucleolarDetectorV11,
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
    assert info["compartment_status"] == "incomplete"
    assert info["compartment_protocol_version"] == "1.0.1"
    with pytest.raises(ValueError, match="compartment_parent_states_incomplete"):
        derive_compartment_masks(nuclei, np.ones_like(nuclei), {})
    with pytest.raises(ValueError, match="compartment_candidate_mask_missing"):
        derive_compartment_masks(nuclei, np.zeros_like(nuclei), {19: "candidate"})


def test_versioned_threshold_contract_preserves_legacy_defaults():
    from cytellect_analysis.region_contracts import RegionCompartmentRecipe
    from pydantic import ValidationError

    common = {"region_set_id": "nl", "label": "NCL candidates", "compartment": "nucleoli",
              "nuclear_revision_id": "r", "nuclear_channel_id": "dna", "defining_channel_id": "ncl"}
    old = RegionCompartmentRecipe(**common, detector={"minimum_area_px": 2})
    assert type(old.detector) is NucleolarDetectorSpec
    assert old.detector.model_dump() == NucleolarDetectorSpec(minimum_area_px=2).model_dump()
    new = RegionCompartmentRecipe(**common, detector={"protocol_version": "1.1.0", "threshold_method": "manual",
                                                    "threshold": 50, "minimum_area_px": 2, "maximum_area_px": 10})
    assert type(new.detector) is NucleolarDetectorV11
    assert RegionCompartmentRecipe.model_validate(new.model_dump()).model_dump() == new.model_dump()
    for bad in [{"protocol_version": "1.0.0", "threshold_method": "manual", "threshold": 50},
                {"protocol_version": "1.1.0", "threshold_method": "manual"},
                {"protocol_version": "1.1.0", "threshold_method": "otsu", "threshold": 50},
                {"protocol_version": "1.1.0", "minimum_area_px": 20, "maximum_area_px": 10},
                {"protocol_version": "1.1.0", "maximum_area_px": True}]:
        with pytest.raises(ValidationError):
            RegionCompartmentRecipe(**common, detector=bad)


def test_manual_threshold_cannot_exceed_recorded_pixel_dtype(tmp_path, monkeypatch):
    channels = {"dapi": np.ones((3, 4), np.uint8), "ncl": np.ones((3, 4), np.uint8)}
    monkeypatch.setattr(engine, "detect", lambda *a, **k: pytest.fail("Fiji must not execute"))
    with pytest.raises(ValueError, match="nucleolar_threshold_outside_input_range"):
        detect_compartments(channels, np.ones((3, 4), np.uint32),
                            NucleolarDetectorV11(threshold_method="manual", threshold=256), tmp_path, "unused")


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


@pytest.mark.fiji
def test_real_fiji_controlled_otsu_and_manual_threshold_area_bounds(tmp_path):
    runtime = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not runtime:
        pytest.skip("Locked Fiji runtime is required for this integration check")
    channels, nuclei, expected = known_field()
    originals = {name: image.copy() for name, image in channels.items()}
    old, _ = detect_compartments(channels, nuclei, NucleolarDetectorSpec(minimum_area_px=2),
                                tmp_path / "old", runtime, scratch_root=tmp_path)
    new, info = detect_compartments(channels, nuclei, NucleolarDetectorV11(minimum_area_px=2),
                                   tmp_path / "otsu", runtime, scratch_root=tmp_path)
    for key in old:
        np.testing.assert_array_equal(new[key], old[key])
    np.testing.assert_array_equal(new["nucleoli"], expected)
    assert info["nucleolar_thresholds"]["7"]["missing_reason"] == "uniform_signal"
    assert info["nucleolar_thresholds"]["3"]["otsu_bin"] >= 0
    assert info["nucleolar_thresholds"]["3"]["source_bin_boundary"] > 1200
    assert info["nucleolar_detector_protocol_version"] == "1.1.0"
    for name, image in channels.items():
        np.testing.assert_array_equal(image, originals[name])

    # Equal-threshold pixels, oversized components, and sub-minimum components
    # are excluded; the much brighter outside-nucleus pixels can never enter.
    channels["ncl"][34:37, 33:37] = 35000
    channels["ncl"][nuclei == 0] = 65535
    original = channels["ncl"].copy()
    manual, info = detect_compartments(
        channels, nuclei, NucleolarDetectorV11(threshold_method="manual", threshold=35000,
                                             minimum_area_px=2, maximum_area_px=10),
        tmp_path / "manual", runtime, scratch_root=tmp_path,
    )
    selected = np.zeros_like(nuclei)
    selected[27:29, 27:30] = 1
    np.testing.assert_array_equal(manual["nucleoli"], selected)
    np.testing.assert_array_equal(manual["nucleoplasm"], np.where((nuclei == 19) & (selected == 0), 19, 0))
    assert info["nucleolar_states"] == {3: "no_candidate", 7: "no_candidate", 11: "no_candidate", 19: "candidate"}
    assert info["nucleolar_thresholds"]["19"]["threshold"] == 35000
    assert info["nucleolar_thresholds"]["19"]["selection_rule"] == "signal > threshold"
    assert info["parent_ids"] == {1: 19} and info["missing_parent_count"] == 3
    assert np.sum(channels["ncl"][selected > 0], dtype=np.float64) == 300000
    np.testing.assert_array_equal(channels["ncl"], original)


@pytest.mark.fiji
def test_real_manual_uniform_above_threshold_is_candidate_with_missing_nucleoplasm(tmp_path):
    runtime = os.environ.get("CYTELLECT_FIJI_EXECUTABLE")
    if not runtime:
        pytest.skip("Locked Fiji runtime is required for this integration check")
    nuclei = np.zeros((10, 12), np.uint32)
    nuclei[2:6, 3:8] = 9
    channels = {"dapi": np.ones_like(nuclei, dtype=np.uint8), "ncl": np.full(nuclei.shape, 100, np.uint8)}
    masks, info = detect_compartments(channels, nuclei,
        NucleolarDetectorV11(threshold_method="manual", threshold=50), tmp_path / "uniform", runtime, scratch_root=tmp_path)
    np.testing.assert_array_equal(masks["nucleoli"] > 0, nuclei > 0)
    assert not masks["nucleoplasm"].any()
    assert info["nucleolar_states"] == {9: "candidate"}
    assert info["compartment_status"] == "incomplete"
    assert info["nucleoplasm_missing_reasons"] == {9: "empty_after_subtraction"}

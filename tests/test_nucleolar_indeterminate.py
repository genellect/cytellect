"""Marker protocol 2.2.0 (owner decision 20, 2026-11-21): noise-based contrast rule and physical minimum area.

The arrays here are synthetic (合成): minimal label and value arrays for checking the formulas, states and records.
Whether the rule is useful on real nucleolar images is checked on public images by
scripts/validate_nucleolar_indeterminate_public.py (docs/public-nucleolar-shape-validation.md).
"""
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis.compartment_engine import detect_compartments
from cytellect_analysis.nucleolar_detector_v2 import (
    MINIMUM_CONTRAST_SNR,
    NucleolarDetectorV21,
    NucleolarDetectorV22,
    detect_nucleoli_v2,
    effective_minimum_area,
)
from cytellect_analysis.nucleus_table import nucleolar_morphology
from scipy import ndimage as ndi

ROOT = Path(__file__).resolve().parents[1]


def synthetic_field(textured=True):
    """Synthetic (合成): two square parents; parent 1 carries a 6 x 6 block (1.6% of it, above its 99th percentile)
    and a 3 x 3 block raised by 800 code units, parent 2 none.

    ``textured``: a checkerboard of +/-20 around 1000 inside the parents (300 outside) gives a measurable noise, for
    the statistic. Without it the plane is flat at 1000 (noise at its floor), so the objects found depend on neither
    texture nor edges.
    """
    shape = (64, 128)
    nuclei = np.zeros(shape, np.uint32)
    nuclei[8:56, 8:56] = 1
    nuclei[8:56, 72:120] = 2
    y, x = np.indices(shape)
    marker = (np.where((y + x) % 2 == 0, 1020, 980) if textured else np.full(shape, 1000)).astype(np.uint16)
    if textured:
        marker[nuclei == 0] = 300
    marker[28:34, 28:34] += 800
    marker[18:21, 40:43] += 800
    return nuclei, np.full(shape, 500, np.uint16), marker


def independent_snr(marker, nuclei, parent):
    """The 4.2.0 statistic written again with NumPy/SciPy for the check."""
    original = marker.astype(np.float64)
    smoothed = ndi.gaussian_filter(original, 0.9, mode="reflect")
    active = nuclei > 0
    lower = active & (smoothed <= np.percentile(smoothed[active], 75))
    residual = (original - smoothed)[lower]
    noise = max(0.5, 1.4826 * float(np.median(np.abs(residual - np.median(residual)))))
    values = smoothed[nuclei == parent]
    return float(np.percentile(values, 99) - np.percentile(values, 75)) / noise, noise


def test_low_contrast_parent_is_indeterminate_with_a_reason_and_its_candidates_are_not_adopted():
    nuclei, dapi, marker = synthetic_field()
    labels, info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22())
    states, thresholds = info["nucleolar_states"], info["nucleolar_thresholds"]
    snr2, noise = independent_snr(marker, nuclei, 2)
    assert snr2 < MINIMUM_CONTRAST_SNR and states[2] == "indeterminate"
    assert thresholds[2]["missing_reason"] == "insufficient_marker_contrast"
    assert thresholds[2]["marker_contrast_snr"] == pytest.approx(snr2, rel=1e-12)
    assert thresholds[2]["marker_noise"] == pytest.approx(noise, rel=1e-12)
    assert not (labels[nuclei == 2] > 0).any()
    snr1, _ = independent_snr(marker, nuclei, 1)
    assert snr1 >= MINIMUM_CONTRAST_SNR and states[1] == "candidate"
    assert thresholds[1]["marker_contrast_snr"] == pytest.approx(snr1, rel=1e-12)
    assert info["marker_contrast"]["precedent"] == "cellpose-sam-ncl-parent/4.2.0"
    # Under 2.1.0 the same parent is a detector outcome (candidate or no candidate), not indeterminate.
    _, old_info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV21())
    assert old_info["nucleolar_states"][2] in ("candidate", "no_candidate")


def test_the_rule_compares_contrast_with_noise_not_with_the_nucleolar_signal_itself():
    nuclei, dapi, marker = synthetic_field()
    snr, _ = independent_snr(marker, nuclei, 1)
    # A k just above the parent's ratio makes it indeterminate; just below keeps it.
    _, above = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22(minimum_contrast_snr=snr * 1.001))
    _, below = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22(minimum_contrast_snr=snr * 0.999))
    assert above["nucleolar_states"][1] == "indeterminate" and below["nucleolar_states"][1] == "candidate"
    # A kept parent's objects are those of 2.1.0: no object is cut for its brightness.
    nuclei, dapi, marker = synthetic_field(textured=False)
    labels, _ = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22())
    old, _ = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV21())
    assert np.array_equal(labels[nuclei == 1] > 0, old[nuclei == 1] > 0) and (labels[nuclei == 1] > 0).any()


def test_minimum_area_is_physical_only_with_a_calibration_and_never_below_4_px():
    detector = NucleolarDetectorV22()
    assert effective_minimum_area(detector, None) == {"px": 4, "source": "pixels_without_calibration",
                                                      "pixel_area_um2": None}
    # DS6a / DS1, 0.1625 um/px: 0.3 / 0.02640625 = 11.36 -> 11 px. DS6b, 0.325 um/px: 2.84 -> 3 -> the 4 px floor.
    assert effective_minimum_area(detector, 0.1625 * 0.1625)["px"] == 11
    assert effective_minimum_area(detector, 0.1625 * 0.1625)["source"] == "calibration"
    assert effective_minimum_area(detector, 0.325 * 0.325) == {"px": 4, "source": "pixel_floor",
                                                               "pixel_area_um2": 0.325 * 0.325, "calibrated_px": 3}
    explicit = NucleolarDetectorV22(minimum_area_px=6, minimum_area_um2=None)
    assert effective_minimum_area(explicit, 0.1625 * 0.1625)["px"] == 6
    with pytest.raises(ValueError, match="nucleolar_pixel_area_invalid"):
        effective_minimum_area(detector, 0.0)


def test_calibrated_minimum_removes_the_4_px_object_and_is_recorded():
    nuclei, dapi, marker = synthetic_field(textured=False)
    labels, info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22(minimum_contrast_snr=1e-9))
    small = labels[19, 41]
    assert small and 4 <= int((labels == small).sum()) < 11 and info["minimum_area"]["px"] == 4
    labels, info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22(minimum_contrast_snr=1e-9),
                                      pixel_area_um2=0.1625 * 0.1625)
    assert not labels[19, 41] and (labels[29:33, 29:33] > 0).all()
    assert info["minimum_area"] == {"px": 11, "source": "calibration", "pixel_area_um2": 0.1625 * 0.1625,
                                    "calibrated_px": 11}


def test_earlier_protocols_ignore_the_calibration_and_replay_unchanged():
    nuclei, dapi, marker = synthetic_field()
    plain, plain_info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV21())
    calibrated, info = detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV21(), pixel_area_um2=0.026)
    assert np.array_equal(plain, calibrated) and info == plain_info
    assert "minimum_area" not in info and "marker_contrast" not in info


def test_compartments_keep_indeterminate_parents_missing_never_zero():
    nuclei, dapi, marker = synthetic_field(textured=False)
    masks, info = detect_compartments({"dapi": dapi, "ncl": marker}, nuclei, NucleolarDetectorV22().model_dump(),
                                      Path("unused"), "", pixel_area_um2=0.1625 * 0.1625)
    assert info["nucleolar_states"][2] == "indeterminate"
    assert not (masks["nucleoli"][nuclei == 2] > 0).any() and not (masks["nucleoplasm"][nuclei == 2] > 0).any()
    morphology = nucleolar_morphology(nuclei, masks["nucleoli"], info["nucleolar_states"], None)
    assert morphology[2].status == "missing" and morphology[2].reason == "indeterminate"
    assert morphology[2].count is None and morphology[2].union_area_px is None
    assert morphology[1].status == "measured" and morphology[1].count == 1  # the 3 x 3 block is below 11 px


def test_new_marker_definitions_stay_2_1_0_because_2_2_0_failed_its_acceptance_criteria():
    """2026-11-21: 2.2.0 failed the pre-registered public validation; new marker definitions keep 2.1.0."""
    from cytellect_api import run_recipes

    assert run_recipes.MARKER_PROTOCOL == "2.1.0" and run_recipes.NUCLEAR_SCALE_PROTOCOL == "nuclear-size/1.1.0"
    detector = run_recipes._nucleolar_defaults({"source": "marker", "pixelUm": None, "relative": 0.7})
    assert NucleolarDetectorV21.model_validate(detector) == NucleolarDetectorV21()
    assert "minimum_contrast_snr" not in detector and "minimum_area_um2" not in detector
    dapi = run_recipes._nucleolar_defaults({"source": "dapi_poor", "pixelUm": None, "relative": 0.7})
    assert dapi["protocol_version"] == "2.0.0" and "minimum_contrast_snr" not in dapi
    # The browser builds the same (nucleolar-definition.ts keeps 2.1.0 and has no 2.2.0 fields).
    source = (ROOT / "apps/web/src/lib/workspace/nucleolar-definition.ts").read_text(encoding="utf-8")
    assert '"2.1.0" as const' in source and "minimum_contrast_snr" not in source
    # The explicit 2.2.0 keeps its own defaults for reproducing the validation.
    assert NucleolarDetectorV22().minimum_contrast_snr == MINIMUM_CONTRAST_SNR == 5.0


def test_methods_text_states_the_contrast_rule_and_the_physical_minimum():
    from cytellect_analysis.region_contracts import RegionCompartmentRecipe
    from cytellect_analysis.region_exports import _compartment_initial

    recipe = RegionCompartmentRecipe(region_set_id="nucleoli", label="Nucleoli", compartment="nucleoli",
                                     nuclear_revision_id="n1", nuclear_channel_id="dapi", defining_channel_id="npm1",
                                     detector=NucleolarDetectorV22())
    text = _compartment_initial(recipe)
    assert "cytellect-nucleolar-v2 2.2.0" in text and "indeterminate" in text and "missing, not zero" in text
    assert f"{MINIMUM_CONTRAST_SNR:g} × the field's noise" in text and "0.3 µm²" in text
    # 2.1.0 keeps its earlier (absent) text.
    old = RegionCompartmentRecipe(region_set_id="nucleoli", label="Nucleoli", compartment="nucleoli",
                                  nuclear_revision_id="n1", nuclear_channel_id="dapi", defining_channel_id="npm1",
                                  detector=NucleolarDetectorV21())
    assert _compartment_initial(old) is None


def test_demo_runtime_keeps_the_protocols_its_recordings_were_made_with():
    """The published demo seed (nuclear-size/1.0.0, marker 2.1.0) must keep asking for what was recorded."""
    from cytellect_api import run_recipes
    from cytellect_showcase.runtime import _pin_protocols

    class Store:
        def __init__(self, recipes):
            self.recipes = recipes

        def rows(self, _table):
            return [{"config": {"recipe": recipe}} for recipe in self.recipes]

    old = Store([{"source": "stardist_nuclear", "detection_scale": "nuclear-size/1.0.0"},
                 {"source": "fiji_nuclear_compartment", "detector": {"engine": "cytellect-nucleolar-v2",
                                                                     "source": "marker", "protocol_version": "2.1.0"}}])
    restore: list = []
    _pin_protocols(restore, old)
    try:
        assert run_recipes.NUCLEAR_SCALE_PROTOCOL == "nuclear-size/1.0.0" and run_recipes.MARKER_PROTOCOL == "2.1.0"
        detector = run_recipes._nucleolar_defaults({"source": "marker", "pixelUm": None, "relative": 0.7})
        assert NucleolarDetectorV21.model_validate(detector) == NucleolarDetectorV21()
    finally:
        for undo in reversed(restore):
            undo()
    assert run_recipes.NUCLEAR_SCALE_PROTOCOL == "nuclear-size/1.1.0" and run_recipes.MARKER_PROTOCOL == "2.1.0"
    restore = []
    _pin_protocols(restore, Store([]))  # a seed without detections keeps the current protocols
    assert not restore


def test_size_breakdown_counts_confirmed_nucleoli_of_kept_nuclei_in_the_shared_implementation():
    from types import SimpleNamespace

    from cytellect_analysis.nucleus_table import nucleolar_sizes

    def row(areas, excluded=False, status="measured"):
        return SimpleNamespace(excluded=excluded, nucleoli=SimpleNamespace(status=status, object_areas_px=areas))

    rows = [row([4, 30, 40]), row([10], excluded=True), row(None, status="missing")]
    # 0.1625 um/px: 30 px = 0.79 um2 (< 1), 40 px = 1.06 um2.
    sizes = nucleolar_sizes(rows, 0.1625 * 0.1625)
    assert (sizes.unit, sizes.small_limit, sizes.small, sizes.other) == ("um2", 1.0, 2, 1)
    sizes = nucleolar_sizes(rows, None)
    assert (sizes.unit, sizes.small_limit, sizes.small, sizes.other) == ("px2", 8, 1, 2)
    assert nucleolar_sizes([row(None, status="missing")], None) is None


def test_2_2_0_physical_minimum_stays_inside_2_2_0():
    from cytellect_api.run_recipes import _nucleolar_defaults

    # The 2.1.0 default keeps its workspace-pixel-size conversion and has no physical minimum of its own.
    detector = _nucleolar_defaults({"source": "marker", "pixelUm": 0.0355, "relative": 0.7})
    assert detector["protocol_version"] == "2.1.0" and detector["minimum_area_px"] == 238
    assert "minimum_area_um2" not in detector
    assert effective_minimum_area(NucleolarDetectorV22(), 0.1625 * 0.1625)["px"] == 11
    with pytest.raises(ValueError, match="nucleolar_area_range_invalid"):
        nuclei, dapi, marker = synthetic_field(textured=False)
        detect_nucleoli_v2(dapi, marker, nuclei, NucleolarDetectorV22(maximum_area_px=20), pixel_area_um2=0.01)


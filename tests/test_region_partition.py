"""Synthetic arithmetic only: minimal numeric/label arrays, not cell images.

These tests establish formulas, exact IDs, missingness and input rejection. They
do not validate detection, thresholds, quality, biological identity or UI.
"""
import math

import numpy as np
import pytest
from cytellect_analysis.region_partition import PROTOCOL, region_partition


def synthetic_arithmetic_arrays():
    maximum = np.iinfo(np.uint32).max
    nuclei = np.array([[7, 7, 7, 7, 0], [maximum, maximum, maximum, maximum, maximum]], dtype=np.uint32)
    target = np.array([[91, 2, 2, 0, 0], [5, 0, 0, 0, 0]], dtype=np.uint32)
    reference = np.array([[0, 0, 0, 8, 0], [0, 23, 23, 0, 0]], dtype=np.uint32)
    # Unassigned nuclear and exterior values are deliberately distinct.
    image = np.array([[2, 6, 10, 3, 99], [10, 2, 4, 777, 888]], dtype=np.float64)
    return nuclei, target, reference, image


def test_synthetic_union_arithmetic_and_sparse_exact_parent_ids():
    inputs = synthetic_arithmetic_arrays()
    originals = tuple(value.copy() for value in inputs)
    result = region_partition(*inputs, background=1)
    assert result["protocol"] == PROTOCOL == "region-partition/1.0.0"
    assert result["background"] == 1
    assert [row["nucleus_id"] for row in result["rows"]] == [7, 4294967295]
    first, last = result["rows"]
    assert first["nucleus_area_px"] == 4
    assert first["target"] == {
        "area_px": 3, "raw_mean": 6, "raw_integrated": 18,
        "corrected_mean": 5, "corrected_integrated": 15,
        "raw_missing_reason": None, "corrected_missing_reason": None,
    }
    assert first["reference"] == {
        "area_px": 1, "raw_mean": 3, "raw_integrated": 3,
        "corrected_mean": 2, "corrected_integrated": 2,
        "raw_missing_reason": None, "corrected_missing_reason": None,
    }
    assert first["raw"] == {"k": 2, "log2_k": 1, "missing_reasons": []}
    assert first["corrected"]["k"] == 2.5
    assert first["corrected"]["log2_k"] == pytest.approx(math.log2(2.5))
    assert last["nucleus_area_px"] == 5
    assert last["target"]["area_px"] == 1
    assert last["reference"]["area_px"] == 2
    assert last["reference"]["raw_integrated"] == 6
    assert last["raw"]["k"] == pytest.approx(10 / 3)
    assert last["corrected"]["k"] == 4.5
    for actual, original in zip(inputs, originals, strict=True):
        np.testing.assert_array_equal(actual, original)


def test_synthetic_membership_label_and_coordinate_invariance():
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    expected = region_partition(nuclei, target, reference, image, background=1)
    # Independent label magnitudes, repeated object IDs and traversal order do
    # not assign parent IDs or weight object means.
    actual = region_partition(
        nuclei[:, ::-1], (target > 0)[:, ::-1], (reference > 0)[:, ::-1], image[:, ::-1], background=1,
    )
    assert actual == expected
    assert region_partition(nuclei.astype(np.uint64), target, reference, image, background=1) == expected


def test_synthetic_ratio_direction_and_common_scale_invariance():
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    forward = region_partition(nuclei, target, reference, image, background=1)["rows"]
    inverse = region_partition(nuclei, reference, target, image, background=1)["rows"]
    scaled = region_partition(nuclei, target, reference, image * 4, background=4)["rows"]
    for original, swapped, multiplied in zip(forward, inverse, scaled, strict=True):
        for basis in ("raw", "corrected"):
            assert swapped[basis]["k"] == pytest.approx(1 / original[basis]["k"])
            assert swapped[basis]["log2_k"] == pytest.approx(-original[basis]["log2_k"])
            assert multiplied[basis]["k"] == pytest.approx(original[basis]["k"])
            assert multiplied[basis]["log2_k"] == pytest.approx(original[basis]["log2_k"])
        for region in ("target", "reference"):
            values = original[region]
            assert values["raw_integrated"] == pytest.approx(values["raw_mean"] * values["area_px"])
            assert values["corrected_integrated"] == pytest.approx(
                values["raw_integrated"] - values["area_px"],
            )


def test_synthetic_confirmed_offset_invariance_allows_signed_background():
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    expected = region_partition(nuclei, target, reference, image, background=np.float64(1))["rows"]
    shifted = region_partition(nuclei, target, reference, image - 5, background=-4)["rows"]
    for original, offset in zip(expected, shifted, strict=True):
        assert offset["corrected"] == original["corrected"]
        for region in ("target", "reference"):
            assert offset[region]["corrected_mean"] == original[region]["corrected_mean"]
            assert offset[region]["corrected_integrated"] == original[region]["corrected_integrated"]


def test_synthetic_unconfirmed_background_keeps_raw_and_corrected_separate():
    row = region_partition(*synthetic_arithmetic_arrays())["rows"][0]
    assert row["raw"]["k"] == 2
    assert row["corrected"] == {
        "k": None, "log2_k": None, "missing_reasons": ["background_not_confirmed"],
    }
    for region in ("target", "reference"):
        assert row[region]["raw_mean"] is not None
        assert row[region]["raw_missing_reason"] is None
        assert row[region]["corrected_mean"] is None
        assert row[region]["corrected_integrated"] is None
        assert row[region]["corrected_missing_reason"] == "background_not_confirmed"


@pytest.mark.parametrize("background, expected_target, expected_reference, reasons", [
    (3, 3, 0, ["nonpositive_reference_mean"]),
    (6, 0, -3, ["nonpositive_target_mean", "nonpositive_reference_mean"]),
    (7, -1, -4, ["nonpositive_target_mean", "nonpositive_reference_mean"]),
])
def test_synthetic_signed_correction_never_clips_or_falls_back(
    background, expected_target, expected_reference, reasons,
):
    row = region_partition(*synthetic_arithmetic_arrays(), background=background)["rows"][0]
    assert row["raw"]["k"] == 2
    assert row["target"]["corrected_mean"] == expected_target
    assert row["target"]["corrected_integrated"] == 3 * expected_target
    assert row["reference"]["corrected_mean"] == expected_reference
    assert row["corrected"] == {"k": None, "log2_k": None, "missing_reasons": reasons}


@pytest.mark.parametrize("target_value, reference_value, reasons", [
    (0, 3, ["nonpositive_target_mean"]),
    (2, -3, ["nonpositive_reference_mean"]),
    (-2, 0, ["nonpositive_target_mean", "nonpositive_reference_mean"]),
])
def test_synthetic_nonpositive_raw_values_remain_measurements_with_missing_ratios(
    target_value, reference_value, reasons,
):
    nuclei = np.array([[1, 1]], dtype=np.uint8)
    target = np.array([[True, False]])
    reference = ~target
    row = region_partition(nuclei, target, reference, np.array([[target_value, reference_value]]))["rows"][0]
    assert row["target"]["raw_mean"] == target_value
    assert row["reference"]["raw_mean"] == reference_value
    assert row["raw"] == {"k": None, "log2_k": None, "missing_reasons": reasons}


@pytest.mark.parametrize("empty", [("target",), ("reference",), ("target", "reference")])
def test_synthetic_empty_memberships_are_missing_including_area(empty):
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    if "target" in empty:
        target[:] = 0
    if "reference" in empty:
        reference[:] = 0
    for background in (None, 1):
        row = region_partition(nuclei, target, reference, image, background=background)["rows"][0]
        expected_reasons = [f"empty_{region}" for region in empty]
        assert row["raw"]["missing_reasons"] == expected_reasons
        assert row["corrected"]["missing_reasons"] == (
            expected_reasons + (["background_not_confirmed"] if background is None else [])
        )
        assert row["raw"]["k"] is None
        assert row["raw"]["log2_k"] is None
        for region in empty:
            values = row[region]
            assert values["raw_missing_reason"] == f"empty_{region}"
            assert values["corrected_missing_reason"] == f"empty_{region}"
            for key in ("area_px", "raw_mean", "raw_integrated", "corrected_mean", "corrected_integrated"):
                assert values[key] is None


def test_synthetic_no_nuclei_produces_no_rows():
    labels = np.zeros((1, 2), dtype=np.uint32)
    assert region_partition(labels, labels.copy(), labels.copy(), np.array([[1, 2]]))["rows"] == []


@pytest.mark.parametrize("name, replacement", [
    ("nuclei", np.array([[1, -1]], dtype=np.int32)),
    ("nuclei", np.ones((1, 2), dtype=np.int32)),
    ("nuclei", np.ones((1, 2), dtype=bool)),
    ("nuclei", np.ones((1, 2), dtype=float)),
    ("nuclei", np.array([[1, 4294967296]], dtype=np.uint64)),
    ("target", np.array([[1, -1]], dtype=np.int32)),
    ("target", np.array([[1, np.nan]])),
    ("target", np.array([[1, 4294967296]], dtype=np.uint64)),
    ("reference", np.array([[1, 1]], dtype=float)),
    ("reference", np.array([[1, 4294967296]], dtype=np.uint64)),
])
def test_synthetic_invalid_label_types_and_range_are_rejected(name, replacement):
    inputs = dict(zip(("nuclei", "target", "reference", "image"), synthetic_arithmetic_arrays(), strict=True))
    inputs[name] = replacement
    with pytest.raises(ValueError, match=f"^region_partition_invalid_{name}$"):
        region_partition(**inputs)


@pytest.mark.parametrize("labels", [np.array([], dtype=np.uint32).reshape(0, 1), np.array([1], dtype=np.uint32)])
def test_synthetic_empty_or_non_2d_nuclear_labels_are_rejected(labels):
    with pytest.raises(ValueError, match="^region_partition_invalid_nuclei$"):
        region_partition(labels, labels, labels, np.ones(labels.shape))


@pytest.mark.parametrize("index", [1, 2, 3])
def test_synthetic_mismatched_shapes_are_rejected(index):
    inputs = list(synthetic_arithmetic_arrays())
    inputs[index] = inputs[index][:, :-1]
    with pytest.raises(ValueError, match="^region_partition_shape_mismatch$"):
        region_partition(*inputs)


@pytest.mark.parametrize("name", ["target", "reference"])
def test_synthetic_exterior_membership_is_rejected_without_clipping(name):
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    membership = target if name == "target" else reference
    membership[0, -1] = 1
    with pytest.raises(ValueError, match=f"^region_partition_{name}_outside_nuclei$"):
        region_partition(nuclei, target, reference, image)


def test_synthetic_overlap_is_rejected_without_subtraction():
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    reference[0, 0] = 1
    with pytest.raises(ValueError, match="^region_partition_overlap$"):
        region_partition(nuclei, target, reference, image)


@pytest.mark.parametrize("dtype", [bool, complex, object, "U2"])
def test_synthetic_invalid_intensity_types_are_rejected(dtype):
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    with pytest.raises(ValueError, match="^region_partition_invalid_image$"):
        region_partition(nuclei, target, reference, image.astype(dtype))


@pytest.mark.parametrize("value", [np.nan, np.inf, -np.inf])
@pytest.mark.parametrize("position", [(0, 0), (0, 4), (1, 4)])
def test_synthetic_nonfinite_input_is_rejected_even_outside_memberships(value, position):
    nuclei, target, reference, image = synthetic_arithmetic_arrays()
    image[position] = value
    with pytest.raises(ValueError, match="^region_partition_nonfinite_image$"):
        region_partition(nuclei, target, reference, image)


@pytest.mark.parametrize("background", [
    True, np.bool_(False), np.nan, np.inf, -np.inf, 1j, "1", [1],
    pytest.param(10 ** 400, id="unrepresentable_integer"),
])
def test_synthetic_invalid_background_is_rejected(background):
    with pytest.raises(ValueError, match="^region_partition_invalid_background$"):
        region_partition(*synthetic_arithmetic_arrays(), background=background)


@pytest.mark.parametrize("background", [None, -np.finfo(float).max])
def test_synthetic_nonfinite_region_arithmetic_is_rejected(background):
    nuclei = np.array([[1, 1, 1]], dtype=np.uint8)
    target = np.array([[True, True, False]])
    reference = np.array([[False, False, True]])
    # Finite values whose integrated sum, or background correction, overflows.
    image = np.array([[np.finfo(float).max, np.finfo(float).max, 1]])
    if background is not None:
        image[:] = 1
    with pytest.raises(ValueError, match="^region_partition_nonfinite_result$"):
        region_partition(nuclei, target, reference, image, background=background)


@pytest.mark.parametrize("values", [[1e308, 1e-308], [1e-308, 1e308]])
def test_synthetic_unrepresentable_ratio_is_missing_without_epsilon(values):
    nuclei = np.array([[1, 1]], dtype=np.uint8)
    target = np.array([[True, False]])
    row = region_partition(nuclei, target, ~target, np.array([values]), background=0)["rows"][0]
    for basis in ("raw", "corrected"):
        assert row[basis] == {"k": None, "log2_k": None, "missing_reasons": ["ratio_out_of_range"]}


def test_synthetic_small_positive_ratio_has_no_pseudocount():
    nuclei = np.array([[1, 1]], dtype=np.uint8)
    target = np.array([[True, False]])
    row = region_partition(nuclei, target, ~target, np.array([[1e-200, 1e-100]]), background=0)["rows"][0]
    assert row["raw"]["k"] == pytest.approx(1e-100, abs=0)
    assert row["raw"]["log2_k"] == pytest.approx(math.log2(1e-100))

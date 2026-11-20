"""Numeric checks of the per-nucleus signal (E-7) and region shape (E-1) calculations of genellect/cytellect#257.

All arrays here are 合成 (synthetic) minimal label and value arrays for formula checks, as docs/development-principles.md
allows: the results do not depend on how a microscope image looks, they are not the basis of any detection, threshold
or biological claim, and the expected values cannot be fixed exactly on real images (zero variance, missing values,
borders). Agreement on public real images with scikit-image is checked separately (RP-02).
"""
import math

import numpy as np
import pytest
from cytellect_analysis.nuclear_signal import nuclear_signal
from cytellect_analysis.nucleolar_shape import object_eccentricity
from cytellect_analysis.region_shape import region_shapes
from skimage.measure import perimeter_crofton
from skimage.morphology import convex_hull_image


def _labels():
    labels = np.zeros((10, 12), dtype=np.uint32)
    labels[1:5, 1:6] = 1      # 20 pixels
    labels[6:9, 7:11] = 2     # 12 pixels
    return labels


def test_cv_is_population_sd_over_mean_of_the_nucleus_pixels():
    labels = _labels()
    image = np.arange(labels.size, dtype=np.uint16).reshape(labels.shape) % 7 + 10
    result = nuclear_signal(labels, image)
    for row, nucleus in zip(result["rows"], (1, 2), strict=True):
        inside = image[labels == nucleus].astype(np.float64)
        assert row["pixels"] == inside.size
        assert row["mean"] == pytest.approx(inside.mean(), rel=1e-12)
        assert row["sd"] == pytest.approx(inside.std(ddof=0), rel=1e-12)
        assert row["cv"] == pytest.approx(inside.std(ddof=0) / inside.mean(), rel=1e-12)
    assert result["threshold"] is None
    assert all(row["positive_missing_reason"] == "threshold_not_set" for row in result["rows"])


def test_corrected_values_subtract_the_background_and_a_nonpositive_mean_has_no_cv():
    labels = _labels()
    image = np.full(labels.shape, 100, dtype=np.uint16)
    image[labels == 1] = 130
    result = nuclear_signal(labels, image, values="corrected", background=100.0)
    first, second = result["rows"]
    assert first["mean"] == pytest.approx(30.0) and first["sd"] == 0 and first["cv"] == 0
    assert second["mean"] == 0 and second["cv"] is None and second["cv_missing_reason"] == "nonpositive_mean"
    with pytest.raises(ValueError, match="nuclear_signal_background_required"):
        nuclear_signal(labels, image, values="corrected")
    with pytest.raises(ValueError, match="nuclear_signal_background_must_be_unset"):
        nuclear_signal(labels, image, background=1.0)


def test_positive_area_fraction_counts_pixels_at_or_above_the_recorded_threshold():
    labels = _labels()
    image = np.zeros(labels.shape, dtype=np.uint16)
    image[1:3, 1:6] = 50   # 10 of the first nucleus's 20 pixels
    image[3:5, 1:6] = 49
    image[6:9, 7:11] = 80  # every pixel of the second
    result = nuclear_signal(labels, image, threshold={"method": "manual", "value": 50.0})
    assert result["threshold"] == {"method": "manual", "values": "raw", "value": 50.0, "applied_to": "field", "missing_reason": None}
    first, second = result["rows"]
    assert (first["positive_pixels"], first["positive_area_fraction"]) == (10, 0.5)
    assert (second["positive_pixels"], second["positive_area_fraction"]) == (12, 1.0)
    with pytest.raises(ValueError, match="nuclear_signal_threshold_invalid"):
        nuclear_signal(labels, image, threshold={"method": "manual", "value": None})


def test_field_otsu_is_recorded_excludes_excluded_nuclei_and_is_missing_without_a_split():
    labels = _labels()
    image = np.zeros(labels.shape, dtype=np.uint16)
    image[1:3, 1:6], image[3:5, 1:6], image[6:9, 7:11] = 200, 20, 200
    result = nuclear_signal(labels, image, threshold={"method": "field_otsu", "value": None})
    assert result["threshold"]["method"] == "field_otsu" and 20 <= result["threshold"]["value"] < 200
    assert [row["positive_area_fraction"] for row in result["rows"]] == [0.5, 1.0]
    # Only the first nucleus remains, and it has two levels: the field threshold comes from it alone.
    excluded = nuclear_signal(labels, image, threshold={"method": "field_otsu", "value": None}, excluded=frozenset({2}))
    assert excluded["rows"][1]["cv_missing_reason"] == "nucleus_excluded" and excluded["rows"][1]["mean"] is None
    flat = nuclear_signal(labels, np.full(labels.shape, 5, dtype=np.uint16), threshold={"method": "field_otsu", "value": None})
    assert flat["threshold"]["value"] is None and flat["threshold"]["missing_reason"] == "threshold_not_established"
    assert all(row["positive_missing_reason"] == "threshold_not_established" for row in flat["rows"])


def test_shape_values_match_independent_calculations():
    labels = np.zeros((14, 16), dtype=np.uint32)
    labels[2:6, 2:9] = 1                                  # a rectangle
    labels[8:12, 3:11] = 2
    labels[8:10, 7:11] = 0                                 # an L: solidity below 1
    result = region_shapes(labels, minimum_area_px=4)
    assert result["perimeter_estimator"] == "crofton-4" and result["minimum_area_px"] == 4
    for row in result["rows"]:
        image = labels == row["region_id"]
        rows, columns = np.nonzero(image)
        perimeter = perimeter_crofton(image, directions=4)
        assert row["area_px"] == image.sum()
        assert row["perimeter_px"] == pytest.approx(perimeter, rel=1e-12)
        assert row["circularity"] == pytest.approx(4 * math.pi * image.sum() / perimeter ** 2, rel=1e-12)
        assert row["solidity"] == pytest.approx(image.sum() / convex_hull_image(image).sum(), rel=1e-12)
        low, high = np.linalg.eigvalsh(np.cov(np.vstack([rows, columns]).astype(float), bias=True))
        assert row["axis_ratio"] == pytest.approx(math.sqrt(high / low), rel=1e-9)
        assert row["eccentricity"] == pytest.approx(object_eccentricity(rows, columns), rel=1e-9)
    rectangle, ell = result["rows"]
    assert rectangle["solidity"] == 1 and ell["solidity"] < 1


def test_small_border_and_degenerate_objects_have_no_shape_values_never_zero():
    labels = np.zeros((10, 10), dtype=np.uint32)
    labels[0:3, 4:7] = 1       # touches the border
    labels[5:7, 5:7] = 2       # 4 pixels: below a minimum of 5
    labels[3, 1:5] = 3         # a one-pixel-wide line: minor axis 0
    rows = {row["region_id"]: row for row in region_shapes(labels, minimum_area_px=4)["rows"]}
    assert rows[1]["missing_reason"] == "touches_border" and rows[1]["touches_border"]
    assert rows[3]["missing_reason"] == "degenerate" and rows[3]["circularity"] is None
    assert region_shapes(labels, minimum_area_px=5)["rows"][1]["missing_reason"] == "below_minimum_area"
    for row in rows.values():
        if row["missing_reason"]:
            assert row["circularity"] is None and row["solidity"] is None and row["axis_ratio"] is None
    for invalid in (0, -1, 2.5, True):
        with pytest.raises(ValueError, match="region_shape_minimum_area_invalid"):
            region_shapes(labels, minimum_area_px=invalid)

"""The public nuclear circularity check (scripts/evaluate_nuclear_circularity_public.py, genellect/cytellect#257).

On the registered BBBC039 manual annotations (CC0): the Crofton perimeter the check uses agrees with an independent
count of boundary crossings, and the check's rules give a verdict that fails closed. The recorded verdict
(fixtures/public/nuclear-circularity/summary.json) is "fails", so circularity is not a statistics metric.
"""
import json
import sys
import typing
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis import nuclear_features
from cytellect_analysis.descriptive_contracts import RegionMetric, RegionSelection
from skimage.measure import regionprops

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import evaluate_nuclear_circularity_public as check  # noqa: E402


def test_crofton_perimeter_matches_independent_crossings_on_public_nuclei():
    objects = 0
    for labels in check.bbbc039_masks():
        for region in regionprops(labels):
            assert region.perimeter_crofton == pytest.approx(check.crossings_perimeter(region.image), rel=1e-12)
            objects += 1
    assert objects >= 300


def test_shapes_keep_the_shared_implementation_values_and_add_circularity():
    measured = 0
    for labels in check.bbbc039_masks():
        # Sparse, large saved IDs give the same values under the same IDs.
        sparse = np.where(labels > 0, labels * 1000 + 7, 0)
        shared = nuclear_features.nuclear_shapes(sparse, minimum_area_px=1)
        for row in check.region_shapes(sparse):
            same = shared[row["region_id"]]
            assert row["missing_reason"] == same["missing_reason"]
            for key in ("solidity", "axis_ratio", "eccentricity"):
                assert row[key] == same[key]
            if row["missing_reason"] is not None:
                assert row["circularity"] is None
                continue
            mask = sparse == row["region_id"]
            expected = 4 * np.pi * int(mask.sum()) / check.crossings_perimeter(mask) ** 2
            assert row["circularity"] == pytest.approx(expected, rel=1e-12)
            measured += 1
    assert measured >= 300


def test_minimum_area_and_verdict_rules_fail_closed():
    within = {"objects": 5, "within_tolerance": True}
    outside = {"objects": 5, "within_tolerance": False}
    empty = {"objects": 0, "within_tolerance": False}
    rows = [dict(outside, area_from_px=4), dict(within, area_from_px=8), dict(empty, area_from_px=16),
            dict(within, area_from_px=32)]
    assert check.minimum_area(rows) == 8
    # An empty bin is never the minimum: no area range passes without measured nuclei.
    assert check.minimum_area([dict(outside, area_from_px=4), dict(empty, area_from_px=8),
                               dict(within, area_from_px=16)]) == 16
    assert check.minimum_area([dict(within, area_from_px=4), dict(outside, area_from_px=8)]) is None
    assert check.minimum_area([dict(empty, area_from_px=4)]) is None


def test_recorded_verdict_fails_and_circularity_is_not_offered():
    folder = ROOT / "fixtures/public/nuclear-circularity"
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    reproduction = json.loads((folder / "reproduction-258-seed.json").read_text(encoding="utf-8"))
    # Rule 8: the #258 seed gives the #258 values, so a verdict may be drawn.
    assert reproduction["reported"]["reproduction_of_258"]["is_258_seed"] is True
    assert reproduction["reported"]["reproduction_of_258"]["matches_258"] is True
    assert summary["reported"]["reproduction_of_258"]["matches_258"] is None
    for record in (summary, reproduction):
        assert record["perimeter_estimator"] == "crofton-4" and record["tolerance"] == {"circularity": 0.05}
        assert record["tuning"]["minimum_area_used_px"] == nuclear_features.MINIMUM_AREA_PX
        assert record["evaluation"]["passed"] is False
        assert record["reported"]["evaluation_with_unmapped_masks"]["within_tolerance_from_minimum"] is False
        assert record["reported"]["crofton_agreement"]["agree"] is True
    for metric in ("circularity", "perimeter"):
        assert metric not in nuclear_features.FEATURE_METRICS
        assert metric not in typing.get_args(RegionMetric)
        with pytest.raises(ValueError):
            RegionSelection(source="region", region_set_id="nuclei", metric=metric)

"""The public nuclear circularity check (scripts/evaluate_nuclear_circularity_public.py, genellect/cytellect#257).

On the registered BBBC039 manual annotations (CC0): the Crofton perimeter the check uses agrees with an independent
count of boundary crossings, and the check's rules give a verdict that fails closed. The recorded verdict
(fixtures/public/nuclear-circularity/summary.json) is "fails", so circularity is not a statistics metric.
"""
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from cytellect_analysis import nuclear_features
from cytellect_analysis.descriptive_contracts import RegionSelection
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
    labels = check.bbbc039_masks()[0]
    shared = nuclear_features.nuclear_shapes(labels, minimum_area_px=1)
    for row in check.region_shapes(labels):
        same = shared[row["region_id"]]
        if row["missing_reason"] is not None:
            assert same["solidity"] is None
            continue
        assert row["solidity"] == pytest.approx(same["solidity"], abs=1e-12)
        assert row["axis_ratio"] == pytest.approx(same["axis_ratio"], rel=1e-12)
        mask = labels == row["region_id"]
        expected = 4 * np.pi * int(mask.sum()) / check.crossings_perimeter(mask) ** 2
        assert row["circularity"] == pytest.approx(expected, rel=1e-12)


def test_minimum_area_and_verdict_rules_fail_closed():
    within = {"objects": 5, "within_tolerance": True}
    outside = {"objects": 5, "within_tolerance": False}
    empty = {"objects": 0, "within_tolerance": False}
    rows = [dict(outside, area_from_px=4), dict(within, area_from_px=8), dict(empty, area_from_px=16),
            dict(within, area_from_px=32)]
    assert check.minimum_area(rows) == 8
    assert check.minimum_area([dict(within, area_from_px=4), dict(outside, area_from_px=8)]) is None
    assert check.minimum_area([dict(empty, area_from_px=4)]) is None


def test_recorded_verdict_fails_and_circularity_is_not_offered():
    summary = json.loads((ROOT / "fixtures/public/nuclear-circularity/summary.json").read_text(encoding="utf-8"))
    assert summary["perimeter_estimator"] == "crofton-4" and summary["tolerance"] == {"circularity": 0.05}
    assert summary["tuning"]["minimum_area_used_px"] == nuclear_features.MINIMUM_AREA_PX
    assert summary["evaluation"]["passed"] is False
    assert summary["reported"]["crofton_agreement"]["agree"] is True
    assert "circularity" not in nuclear_features.FEATURE_METRICS
    for metric in ("circularity", "perimeter"):
        with pytest.raises(ValueError):
            RegionSelection(source="region", region_set_id="nuclei", metric=metric)

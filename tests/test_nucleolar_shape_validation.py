"""Public nucleolar shape validation (scripts/validate_nucleolar_shape_public.py, genellect/cytellect#257 RP-01/02).

Two kinds of checks:
- Synthetic (合成): minimal label and number arrays that check the formulas and decision rules. They are not images
  of cells or nuclei and support no detection, threshold or biological claim.
- The committed registration and summary of the real public images agree with each other and with the rules.
"""
import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/nucleolar-shape/manifest.json"
SUMMARY = ROOT / "fixtures/public/nucleolar-shape/summary.json"


def load():
    spec = importlib.util.spec_from_file_location("validate_nucleolar_shape_public",
                                                  ROOT / "scripts/validate_nucleolar_shape_public.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["validate_nucleolar_shape_public"] = module
    spec.loader.exec_module(module)
    return module


def test_synthetic_binning_and_sampling():
    module = load()
    plane = np.array([[0, 2, 4, 4], [2, 1, 4, 5], [7, 7, 65535, 65535], [7, 8, 65535, 65534]], np.uint16)
    assert module.bin2(plane).tolist() == [[1, 4], [7, 65535]]  # 1.25 -> 1, 4.25 -> 4, 7.25 -> 7, 65534.75 -> 65535
    with pytest.raises(ValueError, match="bin2_odd_shape"):
        module.bin2(np.zeros((3, 4), np.uint16))
    labels = np.arange(16, dtype=np.uint32).reshape(4, 4)
    assert module.decimate2(labels).tolist() == [[5, 7], [13, 15]]


def test_synthetic_independent_shape_matches_pr258_formulas():
    module = load()
    labels = np.zeros((12, 14), np.uint32)
    labels[2:6, 2] = 1
    labels[5, 2:6] = 1  # L
    labels[2:9, 9] = 2
    labels[5, 7:12] = 2  # plus
    for step in range(5):
        labels[7 + step // 2, 2 + step] = 3  # staircase
    labels[9:11, 6:11] = 4  # rectangle
    shapes = module.shapes_pr258(labels)
    assert shapes["border"].tolist() == [False] * 4 and shapes["degenerate"].tolist() == [False] * 4
    for index, rid in enumerate(shapes["id"]):
        coords = np.argwhere(labels == rid)
        expected = [shapes[metric][index] for metric in module.SHAPE_METRICS]
        assert module.shape_independent(coords) == pytest.approx(expected, abs=1e-12)


def test_synthetic_otsu_and_signal_agree():
    module = load()
    values = np.array([10, 11, 12, 12, 13, 40, 41, 43, 44, 90], float)
    assert module.otsu_independent(values) == module.otsu_pr258(values)
    assert module.otsu_independent(np.full(4, 3.0)) is None and module.otsu_pr258(np.full(4, 3.0)) is None
    labels = np.array([[1, 1, 0], [2, 2, 2], [0, 3, 3]], np.uint32)
    image = np.array([[10, 30, 99], [5, 5, 50], [7, 0, 0]], np.uint16)
    ids = np.array([1, 2, 3])
    primary, other = module.signal_pr258(labels, image, ids, None), module.signal_independent(labels, image, ids)
    assert np.allclose(primary["cv"][:2], other["cv"][:2], atol=1e-12)
    assert np.isnan(primary["cv"][2]) and np.isnan(other["cv"][2])  # mean 0: no CV, never zero
    assert np.array_equal(primary["positive"], other["positive"])


def test_synthetic_matching_is_one_to_one_at_half_iou():
    module = load()
    fine = np.zeros((4, 4), np.uint32)
    fine[0:2, 0:2] = 1
    fine[2:4, 2:4] = 2
    fine[0, 3] = 3
    coarse = np.array([[5, 0], [0, 6]], np.uint32)
    fine_ids, coarse_ids, iou = module.match(fine, coarse, 2)
    assert dict(zip(fine_ids.tolist(), coarse_ids.tolist(), strict=True)) == {1: 5, 2: 6}
    assert iou.tolist() == [1.0, 1.0]


def test_synthetic_minimum_area_held_out_and_decision_rules():
    module = load()

    def row(low, objects, value):
        return {"area_from_px": low, "objects": objects, "evaluable": objects >= module.MIN_BIN_OBJECTS,
                "solidity_within": value <= module.TOLERANCE["solidity"]}

    rows = [row(4, 50, 0.20), row(8, 40, 0.04), row(12, 30, 0.06), row(16, 25, 0.03), row(24, 5, 0.50), row(32, 21, 0.01)]
    assert module.minimum_area(rows, "solidity") == 16  # 24 has too few objects; 12 fails
    assert module.held_out(rows, "solidity", 16)["passed"] is True
    assert module.held_out(rows, "solidity", 8) == {"checked_bins": 4, "failing_bins_from_px": [12], "passed": False,
                                                     "reason": "tolerance_exceeded"}
    assert module.held_out(rows, "solidity", None)["passed"] is False
    assert module.minimum_area([row(4, 50, 0.01), row(8, 30, 0.2)], "solidity") is None
    passing = module.decide({"a": [0.85, 0.90], "b": [0.95, 0.85]}, True, 16)
    assert passing["show_for_nucleoli"] is True
    assert module.decide({"a": [0.85, 0.96]}, True, 16)["show_for_nucleoli"] is False  # spread 11 points
    assert module.decide({"a": [0.79, 0.85]}, True, 16)["show_for_nucleoli"] is False
    assert module.decide({"a": [0.90, 0.90]}, False, 16)["show_for_nucleoli"] is False
    assert module.decide({}, True, 16)["show_for_nucleoli"] is False


def test_subset_rule_reads_names_only():
    module = load()
    names = [f"40x_{line}_{condition}_20220308_01_{index}.tif" for line in ("HCT116", "U2OS")
             for condition in ("Untreated", "Ox10") for index in range(20)]
    chosen = module.select_files("ds1", names)
    assert len(chosen) == 4 * module.FIELDS_PER_GROUP
    assert chosen == module.select_files("ds1", list(reversed(names)))
    first = sorted((name for name in names if "_HCT116_Ox10_" in name), key=module.subset_key)
    assert set(first[:module.FIELDS_PER_GROUP]) <= set(chosen)


@pytest.mark.skipif(not MANIFEST.is_file(), reason="registration not committed")
def test_registration_records_every_file_with_hashes():
    module = load()
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    assert manifest["protocol"] == module.PROTOCOL
    ds6b, ds1 = manifest["datasets"]["ds6b"], manifest["datasets"]["ds1"]
    assert ds6b["registered_files"] == ds6b["record_files"] == len(ds6b["files"]) == 360
    assert ds1["record_files"] == 1200 and len(ds1["files"]) == 12 * module.FIELDS_PER_GROUP
    assert [entry["name"] for entry in ds1["files"]] == module.select_files("ds1", [e["name"] for e in ds1["files"]])
    for dataset in (ds6b, ds1):
        assert dataset["license"] == "CC-BY-4.0" and dataset["record_license_id"] == "cc-by-4.0"
        for entry in dataset["files"]:
            assert len(entry["sha256"]) == 64 and len(entry["md5"]) == 32 and entry["bytes"] > 0
            assert entry["url"].startswith("https://zenodo.org/api/records/")
    assert {entry["split"] for entry in ds1["files"]} == {"evaluation"}
    assert {(entry["timepoint"], entry["split"]) for entry in ds6b["files"]} == {
        ("30min", "tuning"), ("2hrs", "tuning"), ("4hrs", "evaluation")}


@pytest.mark.skipif(not SUMMARY.is_file(), reason="summary not committed")
def test_summary_matches_registration_and_decision_rule():
    module = load()
    summary = json.loads(SUMMARY.read_text(encoding="utf-8"))
    assert summary["manifest_sha256"] == hashlib.sha256(MANIFEST.read_bytes()).hexdigest()
    assert summary["protocol"] == module.PROTOCOL
    assert summary["rules"]["tolerance"] == module.TOLERANCE
    listed = {(item["dataset"], item["name"]) for item in summary["failures"]}
    for dataset, counts in summary["fields"].items():
        assert counts["ok"] + counts["not_ok"] == counts["registered"]
        assert counts["not_ok"] == sum(1 for key in listed if key[0] == dataset)
    for metric, decision in summary["decision4"].items():
        rates: dict[str, list[float]] = {}
        minimum = summary["minimum_area"][metric]["minimum_area_px"]
        if minimum is not None:
            for dataset in ("ds6b", "ds1"):
                for row in summary["conditions"][dataset]:
                    if row["split"] == "evaluation":
                        rates.setdefault(f"{dataset}/{row['group']}", []).append(row["rates_at_minimum"][metric]["rate"])
        again = module.decide(rates, summary["minimum_area"][metric]["held_out_passed"], minimum)
        assert again["show_for_nucleoli"] == decision["show_for_nucleoli"]

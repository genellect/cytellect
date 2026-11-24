"""The check that a rebuilt demo kept every published value (scripts/compare_showcase_seed.py)."""
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("compare_showcase_seed", ROOT / "scripts/compare_showcase_seed.py")
assert spec is not None and spec.loader is not None
checker = importlib.util.module_from_spec(spec)
sys.modules["compare_showcase_seed"] = checker
spec.loader.exec_module(checker)

OLD_FIELD, NEW_FIELD = "11111111-1111-1111-1111-111111111111", "22222222-2222-2222-2222-222222222222"


def problems(old, new, tolerance=0.0):
    found: list[str] = []
    checker.kept(checker.blank(old, {OLD_FIELD: "field:a"}), checker.blank(new, {NEW_FIELD: "field:a"}), "r", found, tolerance)
    return found


def test_added_values_and_new_identifiers_are_kept_values():
    old = {"field_id": OLD_FIELD, "rows": [{"field_id": OLD_FIELD, "value": 1.5}, {"field_id": "x", "value": 2.0}],
           "units": [{"field_ids": [OLD_FIELD], "unit": "Run1"}, {"field_ids": ["x"], "unit": "Run2"}],
           "batches": {OLD_FIELD: "a"}}
    new = {"field_id": NEW_FIELD, "rows": [{"field_id": "x", "value": 2.0}, {"field_id": NEW_FIELD, "value": 1.5, "added": 3}],
           "units": [{"field_ids": ["x"], "unit": "Run2"}, {"field_ids": [NEW_FIELD], "unit": "Run1"}],
           "batches": {NEW_FIELD: "a"}, "nuclear_shape": [0.9]}
    assert problems(old, new) == []


def test_lists_not_ordered_by_identifiers_keep_their_order():
    """Groups, comparisons and pages are listed in the order the result gives them: a new order is a change."""
    old = {"groups": [{"group": "Untreated", "mean": 1.0}, {"group": "Treated", "mean": 2.0}]}
    new = {"groups": [{"group": "Treated", "mean": 2.0}, {"group": "Untreated", "mean": 1.0}]}
    assert problems(old, new)


def test_a_changed_or_missing_value_is_reported():
    assert problems({"value": 1.5}, {"value": 1.5000001}) == ["r.value: 1.5 became 1.5000001"]
    assert problems({"value": 1.5}, {"value": 1.5 * (1 + 1e-12)}, 1e-9) == []
    assert problems({"value": 1.5, "count": 3}, {"value": 1.5}) == ["r.count: missing"]
    assert problems({"rows": [{"v": 1.0}]}, {"rows": [{"v": 1.0}, {"v": 2.0}]}) == ["r.rows: list of 1 became 2"]

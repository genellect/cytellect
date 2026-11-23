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
    old = {"field_id": OLD_FIELD, "rows": [{"field": OLD_FIELD, "value": 1.5}, {"field": "x", "value": 2.0}],
           "batches": {OLD_FIELD: "a"}}
    new = {"field_id": NEW_FIELD, "rows": [{"field": "x", "value": 2.0}, {"field": NEW_FIELD, "value": 1.5, "added": 3}],
           "batches": {NEW_FIELD: "a"}, "nuclear_shape": [0.9]}
    assert problems(old, new) == []


def test_a_changed_or_missing_value_is_reported():
    assert problems({"value": 1.5}, {"value": 1.5000001}) == ["r.value: 1.5 became 1.5000001"]
    assert problems({"value": 1.5}, {"value": 1.5 * (1 + 1e-12)}, 1e-9) == []
    assert problems({"value": 1.5, "count": 3}, {"value": 1.5}) == ["r.count: missing"]
    assert problems({"rows": [{"v": 1.0}]}, {"rows": [{"v": 1.0}, {"v": 2.0}]}) == ["r.rows: list of 1 became 2"]

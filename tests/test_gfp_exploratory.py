import numpy as np
import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.descriptive_contracts import GFP_FILTER
from cytellect_analysis.gfp_gate import apply_exploratory_gate, exploratory_thresholds
from cytellect_analysis.gfp_selection import apply_gfp_gate, same_revision_nuclear_source
from pydantic import ValidationError
from test_gfp_gated_statistics import nuclear_fixture, request


def test_manual_gate_boundary_missing_and_no_date():
    rows = [{"field_id": "a", "region_id": i + 1, "gfp_mean": value} for i, value in enumerate([-1, 10, 11, None, np.nan])]
    result = apply_exploratory_gate(rows, exploratory_thresholds(rows, "manual", 10))
    assert [row["gfp_positive"] for row in result] == [False, False, True, None, None]
    assert [row["region_id"] for row in result] == [1, 2, 3, 4, 5]


def test_otsu_is_per_batch_and_missing_or_uniform_stays_unknown():
    rows = [{"acquisition_date": date, "gfp_mean": value} for date, values in
            [("a", [0, 0, 100, 100]), ("b", [1000, 1000, 2000, 2000]), ("c", [4, 4]), (None, [0, 100])]
            for value in values]
    thresholds = exploratory_thresholds(rows, "batch_otsu")
    assert 0 < thresholds["dates"]["a"]["threshold"] < 100
    assert 1000 < thresholds["dates"]["b"]["threshold"] < 2000
    assert thresholds["dates"]["c"]["missing_reason"] == "gfp_uniform_distribution"
    result = apply_exploratory_gate(rows, thresholds)
    assert [row["gfp_positive"] for row in result] == [False, False, True, True, False, False, True, True, None, None, None, None]


def test_filter_validates_methods_and_does_not_invent_controls():
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp", "method": "manual", "threshold": 10, "keep": "positive"}
    assert GFP_FILTER.validate_python(gate).control_field_ids == []
    for update in ({"threshold": None}, {"threshold": float("inf")}, {"method": "batch_otsu"}, {"control_field_ids": ["a"]}):
        with pytest.raises(ValidationError):
            GFP_FILTER.validate_python({**gate, **update})


def test_formal_selection_manual_uses_same_nuclear_ids_and_corrected_values():
    report, config = nuclear_fixture({"a": ("A", "a", None, [(10, 20), (15, 20), (20, 20)])})
    nuclear = same_revision_nuclear_source(report, config["field_snapshot"])
    observations = [{"field_id": "a", "region_id": i, "excluded": False} for i in (1, 2, 3)]
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp", "method": "manual", "threshold": 10, "values": "corrected", "keep": "positive"}
    marked, record = apply_gfp_gate(observations, config["field_snapshot"], gate, nuclear)
    # Background is 5. Corrected GFP means are 5, 10, 15; equality is negative.
    assert [row["gate_selected"] for row in marked] == [False, False, True]
    assert record["filter"]["values"] == "corrected"
    gate["keep"] = "negative"
    marked, _ = apply_gfp_gate(observations, config["field_snapshot"], gate, nuclear)
    assert [row["gate_selected"] for row in marked] == [True, True, False]


def test_exploratory_filter_flows_into_statistics_and_methods():
    from cytellect_analysis.gfp_selection import methods_sentences
    report, config = nuclear_fixture()
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp", "method": "manual", "threshold": 200, "values": "raw", "keep": "positive"}
    result = analyze_region_comparison(report, config, request(filter_=gate))
    record = result["selection"]["gfp_gate"]
    assert record["filter"] == gate
    assert "gfp_exploratory_threshold_without_negative_control" in result["warnings"]
    assert "without a negative-control reference" in " ".join(methods_sentences(record))


def test_cell_roi_gate_uses_exact_manual_object_identity():
    report, config = nuclear_fixture({"a": ("A", "a", None, [(10, 20), (15, 20), (20, 20)])})
    recipe = {"id": "region-2d", "version": "1.0.0", "source": "manual", "region_set_id": "cell", "label": "Cell ROI", "defining_channel_id": "dna"}
    report["recipe"] = recipe
    config["recipe"] = recipe
    table = report["field_tables"]["a"]
    table["region_set"].update(source="manual", region_set_id="cell", label="Cell ROI")
    for row in table["rows"]:
        row["region_set_id"] = "cell"
    source = same_revision_nuclear_source(report, config["field_snapshot"])
    observations = [{"field_id": "a", "region_id": i, "excluded": False} for i in (1, 2, 3)]
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp", "method": "manual", "threshold": 15, "values": "raw", "unit": "cell_roi", "keep": "positive"}
    marked, record = apply_gfp_gate(observations, config["field_snapshot"], gate, source)
    assert [item["gate_selected"] for item in marked] == [False, False, True]
    assert record["object_unit"] == "cell_roi"
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        apply_gfp_gate(observations, config["field_snapshot"], {**gate, "unit": "nucleus"}, source)

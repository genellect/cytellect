"""Nuclei per field compared through the existing common-statistics path.

Uses the existing minimal pixel fixture of test_region_comparison (synthetic numbers
for wiring and arithmetic only; not an image evaluation).
"""
import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from test_region_comparison import comparison_fixture, comparison_request


def count_request(**updates):
    raw = comparison_request(metric="area_px").model_dump(mode="json")
    raw["selection"] = {"source": "field-summary", "version": "1.0.0", "region_set_id": "regions", "metric": "nucleus_count"}
    return RegionComparisonRequestV2.model_validate({**raw, "version": "2.0.0", "test": "welch-t", **updates})


def excluded(report, config, items):
    rows = [{"field_id": fid, "region_id": rid, "reason": "researcher excluded"} for fid, rid in items]
    report["exclusions"] = config["exclusions"] = rows


def test_each_field_is_one_observation_and_excluded_regions_are_not_counted(tmp_path):
    report, config = comparison_fixture()
    excluded(report, config, [("A1", 19)])
    result = analyze_region_comparison(report, config, count_request(estimates="comparison-estimates/1.0.0"))
    values = {row["field_id"]: row["value"] for row in result["plot_data"]}
    assert values == {"A0": 2, "A1": 1, "B0": 2, "B1": 2}
    assert all(row["region_id"] is None for row in result["plot_data"])
    assert result["unit"] == "nuclei per field"
    # Contrast [A, B]: A is reported as the treatment.
    assert result["estimates"]["difference"]["estimate"] == pytest.approx(1.5 - 2)
    assert result["estimates"]["scale"] == "ratio"
    summary = {item["field_id"]: item["field_summary"] for item in result["source_fields"]}
    assert summary["A1"] == {"nucleus_count": 1, "border_count": 0, "excluded_region_count": 1, "field_area_mm2": None}
    figure = render_common_statistics(result, tmp_path)
    assert figure["source_files"]


def test_whole_field_exclusion_removes_the_observation_but_keeps_the_ledger():
    report, config = comparison_fixture((('A', [0, 2, 4]), ('B', [3, 5, 7])))
    excluded(report, config, [("A2", None), ("B0", 19)])
    result = analyze_region_comparison(report, config, count_request())
    assert {row["field_id"] for row in result["plot_data"]} == {"A0", "A1", "B0", "B1", "B2"}
    ledger = {row["field_id"]: row for row in result["source_field_ledger"]}
    assert ledger["A2"]["explicitly_excluded"] is True


def test_positivity_requires_a_bound_nuclear_source():
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "actin", "method": "manual",
            "threshold": 10.0, "keep": "positive"}
    report, config = comparison_fixture()
    request = count_request()
    raw = request.model_dump(mode="json")
    raw["selection"] = {**raw["selection"], "metric": "positive_fraction", "positivity": gate}
    # A manual (exploratory) threshold is described, never tested: the legacy GFP gate follows the same rule.
    with pytest.raises(ValueError, match="field_positivity_exploratory_threshold_descriptive_only"):
        analyze_region_comparison(report, config, RegionComparisonRequestV2.model_validate(raw))
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        analyze_region_comparison(report, config, RegionComparisonRequestV2.model_validate({**raw, "test": "none"}))


def test_only_nuclear_region_sources_are_counted_as_nuclei():
    report, config = comparison_fixture()
    for source in (report, config):
        source["recipe"] = {**source["recipe"], "source": "fiji_positive_regions"}
    with pytest.raises(ValueError, match="field_summary_nuclear_source_required"):
        analyze_region_comparison(report, config, count_request())


def test_legacy_gfp_positivity_counts_only_judged_nuclei(monkeypatch):
    """The recorded GFP gate's judged reasons give positive and negative; an unjudged nucleus is neither,
    and a field whose nuclei were all unjudged has no positive count (missing, never zero)."""
    from cytellect_analysis import field_summary_source as source
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "actin", "method": "manual",
            "threshold": 10.0, "keep": "positive"}
    report, config = comparison_fixture()

    def judged(report, recipe, snapshot, selector, regions, excluded, nuclear=None):
        out = []
        for row in regions:
            if row["field_id"] == "B1":
                out.append({**row, "gfp_positive": None, "gfp_gate_reason": "gfp_missing"})
                continue
            positive = row["region_id"] % 2 == 1
            out.append({**row, "gfp_positive": positive,
                        "gfp_gate_reason": "above_exploratory_threshold" if positive else "at_or_below_exploratory_threshold"})
        return out, {"control_field_ids": []}

    monkeypatch.setattr(source, "gate_source_observations", judged)
    for metric in ("positive_fraction", "positive_count"):
        selection = {"source": "field-summary", "version": "1.0.0", "region_set_id": "regions", "metric": metric,
                     "positivity": gate}
        observations, *_ = source.prepare_field_summary_observations(report, config["field_snapshot"], selection)
        rows = {row["field_id"]: row for row in observations}
        for fid, row in rows.items():
            if fid == "B1":
                assert (row["value"], row["missing_reason"], row["evaluable_count"]) == (None, "no_evaluable_nuclei", 0)
                continue
            assert row["evaluable_count"] == row["positive_count"] + row["negative_count"] > 0
            expected = row["positive_count"] if metric == "positive_count" else row["positive_count"] / row["evaluable_count"]
            assert row["value"] == pytest.approx(expected)

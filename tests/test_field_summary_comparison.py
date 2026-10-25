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


def test_positivity_is_refused_until_connected():
    gate = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "actin", "method": "manual",
            "threshold": 10.0, "keep": "positive"}
    report, config = comparison_fixture()
    request = count_request()
    raw = request.model_dump(mode="json")
    raw["selection"] = {**raw["selection"], "metric": "positive_fraction", "positivity": gate}
    with pytest.raises(ValueError, match="field_summary_positivity_not_connected"):
        analyze_region_comparison(report, config, RegionComparisonRequestV2.model_validate(raw))


def test_only_nuclear_region_sources_are_counted_as_nuclei():
    report, config = comparison_fixture()
    for source in (report, config):
        source["recipe"] = {**source["recipe"], "source": "fiji_positive_regions"}
    with pytest.raises(ValueError, match="field_summary_nuclear_source_required"):
        analyze_region_comparison(report, config, count_request())

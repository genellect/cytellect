"""Synthetic numeric cases check prose rules, never biological claims or image quality."""
import json
from pathlib import Path

import pytest
from cytellect_analysis.common_statistics import analyze_region_association, analyze_region_comparison
from cytellect_analysis.common_statistics_figures import render_common_statistics
from cytellect_analysis.figure_annotations import EXPLORATORY_WARNING, comparison_annotations
from cytellect_analysis.figure_legend import _counts, _selection_sentence, _title
from test_common_statistics import association_request, request_v2
from test_region_comparison import comparison_fixture

CASES = json.loads((Path(__file__).resolve().parents[1] / "fixtures/result-summary-cases.json").read_text(encoding="utf-8"))["cases"]
PLOT = {"preset": "nature-double", "language": "en", "kind": "superplot",
        "presentation": {"version": "1.0.0"}}


@pytest.mark.parametrize("row", CASES, ids=lambda row: row["id"])
def test_legend_and_japanese_summary_share_saved_cases(row):
    estimates = row["estimates"]
    canonical = {**row.get("source", {}), "metric": estimates["metric"], "unit": row["unit"], "estimates": estimates,
                 "comparisons": [row["comparison"]]}
    assert _title(canonical, [estimates["control"], estimates["treatment"]]) == row["expected_en"]


@pytest.mark.parametrize("test,paired,method", [
    ("paired-t", True, "t-test"), ("welch-t", False, "Welch"),
    ("wilcoxon", True, "Wilcoxon"), ("mann-whitney-u", False, "Mann–Whitney"),
])
def test_tested_legends_state_method_counts_and_independence(tmp_path, test, paired, method):
    report, config = comparison_fixture((("A", [1, 2, 3, 4, 5, 6]), ("B", [11, 12, 14, 14, 16, 16])))
    result = analyze_region_comparison(report, config, request_v2(test=test, paired=paired, plot=PLOT,
                                        estimates="comparison-estimates/1.0.0",
                                        comparison_family={"family_id": "planned", "kind": "planned", "contrasts": [["B", "A"]]}))
    render_common_statistics(result, tmp_path)
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    assert method in legend and "n = 6" in legend
    assert "→" not in legend and "Excluded runs: 0" not in legend and "Fields and fields" not in legend
    assert "independent replicates" in legend
    assert ("lines join the same run" in legend) == paired
    expected = "increased by about 10 a.u. with B" if test in ("paired-t", "welch-t") else "increased with B"
    assert legend.splitlines()[0] == f"**Cell interiors phalloidin mean intensity {expected}.**"


def test_three_groups_keep_the_planned_holm_family_in_the_legend(tmp_path):
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6]), ("C", [7, 8, 9])))
    result = analyze_region_comparison(report, config, request_v2(conditions=["A", "B", "C"], omnibus="kruskal-wallis", plot=PLOT,
        comparison_family={"family_id": "planned", "kind": "planned", "contrasts": [["A", "B"], ["A", "C"], ["B", "C"]]}))
    render_common_statistics(result, tmp_path)
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    assert legend.startswith("**") and " in A, B and C.**" in legend
    assert "Holm" in legend and "Kruskal" in legend
    assert "A" in legend and "B" in legend and "C" in legend


def test_association_legend_names_the_unit_and_method(tmp_path):
    report, config = comparison_fixture((("A", [1, 2, 3]), ("B", [4, 5, 6])))
    result = analyze_region_association(report, config, association_request(plot={"preset": "nature-double", "language": "en"}))
    render_common_statistics(result, tmp_path)
    legend = (tmp_path / "figure-legend.md").read_text(encoding="utf-8")
    assert "Each point is one independent experimental unit" in legend
    assert "Spearman" in legend and "n = 3 (A) and 3 (B)" in legend and "→" not in legend


def test_field_observations_and_unequal_counts_are_not_duplicated():
    text = _counts({"A": {"experimental_units": 3, "observations": 9, "selected_fields": 9},
                    "B": {"experimental_units": 4, "observations": 12, "selected_fields": 12}},
                   ["A", "B"], "fields", "runs")
    assert text == ("n = 3 (A) and 4 (B) runs; 9 (A) and 12 (B) fields; "
                    "individual fields are not treated as independent replicates.")


def test_exploratory_threshold_has_its_own_reason_for_no_test():
    notes = comparison_annotations({"spec": {"test": "none"}, "warnings": [EXPLORATORY_WARNING]}, ["A", "B"])
    assert notes.legend == ["No hypothesis test or confidence interval was calculated because "
                            "the positivity threshold was not set from a negative control."]


def test_legend_names_the_intensity_defined_subset_before_its_threshold_warning():
    # Contract-only wording fixture; no generated image or biological claim.
    selected = {"selection": {"channel_gate": {"filter": {"keep": "positive", "method": "otsu", "channel_id": "eu5"},
                                              "channel": {"label": "5-EU"}}}}
    assert _selection_sentence(selected) == [
        "Only 5-EU-positive nuclei were analysed. Classification used Otsu thresholding per acquisition date "
        "of mean 5-EU intensities; a value strictly above the threshold was positive and equality was negative. "
        "Unclassified objects were not selected."]


def test_log2_run_differences_name_their_scale():
    row = next(row for row in CASES if row["id"] == "log2")
    estimates = {**row["estimates"], "test": "none", "runs": [{"pair": "R1", "difference": 1.2, "ratio": None}]}
    notes = comparison_annotations({"spec": {"test": "none"}, "estimates": estimates}, ["Control", "Drug"])
    assert notes.legend[0] == "Per-run difference in log2 units (Drug − Control): +1.2 (R1)"

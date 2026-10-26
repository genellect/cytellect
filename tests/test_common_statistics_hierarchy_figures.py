"""Run-based comparison figures (requirements F-01, F-02).

Uses the minimal pixel fixture of test_region_comparison (synthetic numbers for drawing and
arithmetic only; not an image evaluation).
"""
import json

import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionComparisonRequestV2
from cytellect_analysis.common_statistics_figures import render_common_statistics
from scipy import stats
from test_region_comparison import comparison_fixture, comparison_request


def paired_result(kind, test="paired-t"):
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    raw = comparison_request(paired=True).model_dump(mode="json")
    raw["plot"] = {**raw["plot"], "kind": kind}
    return analyze_region_comparison(report, config, RegionComparisonRequestV2.model_validate(
        {**raw, "version": "2.0.0", "test": test}))


@pytest.mark.parametrize("kind", ["superplot", "unit-mean-bar"])
def test_hierarchy_figures_summarise_units_with_a_t_interval(tmp_path, kind):
    result = paired_result(kind)
    figure = render_common_statistics(result, tmp_path)
    assert "figure.svg" in figure["source_files"]
    data = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    summary = {row["condition"]: row for row in data["graphical_summary"]}
    units = [row["value"] for row in result["unit_summary"] if row["condition"] == "A"]
    mean = sum(units) / len(units)
    half = stats.t.ppf(.975, len(units) - 1) * stats.tstd(units) / len(units) ** .5
    assert summary["A"]["mean"] == pytest.approx(mean)
    assert (summary["A"]["ci_low"], summary["A"]["ci_high"]) == (pytest.approx(mean - half), pytest.approx(mean + half))
    assert summary["A"]["n_units"] == 3
    # Every independent unit is a bound point; the legend names what points and n are.
    assert len(data["unit_glyphs"]) == len(result["unit_summary"])
    caption = (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    assert "independent experimental units" in caption and "95% t interval" in caption
    assert "not fields or nuclei" in caption


def test_descriptive_superplot_draws_unit_means_without_an_interval(tmp_path):
    result = paired_result("superplot", test="none")
    render_common_statistics(result, tmp_path)
    data = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    assert all(row["ci_low"] is None and row["ci_high"] is None for row in data["graphical_summary"])
    assert len(data["unit_glyphs"]) == len(result["unit_summary"])
    caption = (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    assert "no test or interval" in caption and "95% t interval" not in caption
    assert "independent experimental units" not in caption and "independence not confirmed" in caption

"""Opt-in estimates attached to a saved two-group comparison.

Uses the existing minimal pixel fixture of test_region_comparison (synthetic numbers
for wiring and arithmetic only; not an image evaluation).
"""
import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_analysis.common_statistics_contracts import RegionComparisonRequestV2
from pydantic import ValidationError
from test_region_comparison import comparison_fixture, comparison_request

PROTOCOL = "comparison-estimates/1.0.0"


def request(**updates):
    raw = comparison_request(**{key: updates.pop(key) for key in ("paired", "metric") if key in updates}).model_dump(mode="json")
    return RegionComparisonRequestV2.model_validate({**raw, "version": "2.0.0", **updates})


def test_paired_estimates_follow_the_declared_contrast_and_saved_test():
    report, config = comparison_fixture((('A', [3, 8, 2]), ('B', [4, 10, 5])))
    result = analyze_region_comparison(report, config, request(paired=True, test="paired-t", estimates=PROTOCOL))
    estimates, test = result["estimates"], result["comparisons"][0]
    # Contrast [A, B] reports A − B, so A is the treatment and B the control.
    assert (estimates["treatment"], estimates["control"], estimates["direction"]) == ("A", "B", "treatment_minus_control")
    assert estimates["difference"]["estimate"] == pytest.approx(test["estimate"])
    assert (estimates["difference"]["ci_low"], estimates["difference"]["ci_high"]) == (
        pytest.approx(test["ci_low"]), pytest.approx(test["ci_high"]))
    assert estimates["scale"] == "difference" and estimates["ratio"]["unavailable_reason"] == "ratio_not_applicable"
    assert estimates["n_pairs"] == 3 and len(estimates["runs"]) == 3
    assert result["spec"]["estimates"] == PROTOCOL


def test_historical_requests_and_results_keep_their_bytes():
    report, config = comparison_fixture()
    result = analyze_region_comparison(report, config, request(test="welch-t"))
    assert "estimates" not in result and "estimates" not in result["spec"]


def test_estimates_need_one_declared_contrast():
    family = {"family_id": "f", "kind": "planned", "contrasts": [["A", "B"], ["A", "C"]]}
    with pytest.raises(ValidationError, match="comparison_estimates_single_contrast_required"):
        request(test="welch-t", estimates=PROTOCOL, conditions=["A", "B", "C"], comparison_family=family,
                omnibus="welch-anova")

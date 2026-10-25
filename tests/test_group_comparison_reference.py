"""WP10 reference values for the group-comparison metrics and estimates.

Written from docs/methods.md ("Group comparison contracts") before any
implementation existed. Expected values are hand-derived or computed here with
plain arithmetic; no product aggregation or statistics helper is used. Each test
is skipped while its implementation still raises NotImplementedError.
"""
import math

import numpy as np
import pytest
from cytellect_analysis.comparison_estimates import comparison_estimates
from cytellect_analysis.field_summary import field_summary_values
from cytellect_analysis.group_comparison_contracts import FieldSummarySelection
from cytellect_analysis.nucleolar_shape import nucleolar_eccentricity
from scipy import stats

T975_DF1 = math.tan(math.pi * 0.475)  # Student t, 1 df: F(t) = 1/2 + atan(t)/π
T975_DF2 = math.sqrt(2 * 0.95**2 / (1 - 0.95**2))  # 2 df: F(t) = 1/2 + t / (2 sqrt(2 + t²))


def pending(call):
    try:
        return call()
    except NotImplementedError as error:
        pytest.skip(f"implementation pending: {error}")


def mean(values):
    return sum(values) / len(values)


def sd(values):
    centre = mean(values)
    return math.sqrt(sum((value - centre) ** 2 for value in values) / (len(values) - 1))


def approx(value):
    return pytest.approx(value, rel=1e-12, abs=1e-12)


# ---------------------------------------------------------------- comparison estimates

def estimates(control, treatment, **options):
    defaults = {"control_label": "DMSO", "treatment_label": "Drug", "design": "paired", "test": "paired-t",
                "metric": "area_um2", "pairs": ["r1", "r2", "r3"][:len(control)]}
    return pending(lambda: comparison_estimates(control, treatment, **{**defaults, **options}))


def test_paired_t_difference_ratio_groups_and_runs():
    control, treatment = [100.0, 120.0, 90.0], [80.0, 90.0, 81.0]
    result = estimates(control, treatment)
    d = [t - c for c, t in zip(control, treatment, strict=True)]  # [-20, -30, -9]
    half = T975_DF2 * sd(d) / math.sqrt(3)
    assert result.direction == "treatment_minus_control" and result.scale == "ratio"
    assert (result.control, result.treatment, result.n_pairs, result.n_control, result.n_treatment) == ("DMSO", "Drug", 3, 3, 3)
    assert result.difference.estimate == approx(-59 / 3)
    assert (result.difference.ci_low, result.difference.ci_high) == (approx(-59 / 3 - half), approx(-59 / 3 + half))
    assert result.difference.unavailable_reason is None and result.difference.basis
    logs = [math.log(t / c) for c, t in zip(control, treatment, strict=True)]  # log 0.8, 0.75, 0.9
    log_half = T975_DF2 * sd(logs) / math.sqrt(3)
    assert result.ratio.estimate == approx(math.exp(mean(logs)))
    assert result.ratio.ci_low == approx(math.exp(mean(logs) - log_half))
    assert result.ratio.ci_high == approx(math.exp(mean(logs) + log_half))
    groups = {group.condition: group for group in result.groups}
    for label, values in (("DMSO", control), ("Drug", treatment)):
        group_half = T975_DF2 * sd(values) / math.sqrt(3)
        assert groups[label].n == 3 and groups[label].mean == approx(mean(values)) and groups[label].sd == approx(sd(values))
        assert (groups[label].ci_low, groups[label].ci_high) == (approx(mean(values) - group_half),
                                                                 approx(mean(values) + group_half))
    assert [(run.pair, run.control, run.treatment, run.difference) for run in result.runs] == [
        ("r1", 100.0, 80.0, -20.0), ("r2", 120.0, 90.0, -30.0), ("r3", 90.0, 81.0, -9.0)]
    assert [run.ratio for run in result.runs] == [approx(0.8), approx(0.75), approx(0.9)]


def test_welch_difference_and_ratio_of_geometric_means():
    control, treatment = [10.0, 12.0, 14.0, 16.0], [20.0, 25.0, 21.0]
    result = estimates(control, treatment, design="independent", test="welch-t", pairs=None)
    vc, vt = sd(control) ** 2 / 4, sd(treatment) ** 2 / 3
    df = (vc + vt) ** 2 / (vc**2 / 3 + vt**2 / 2)
    half = stats.t.ppf(0.975, df) * math.sqrt(vc + vt)
    assert result.difference.estimate == approx(9.0)
    assert (result.difference.ci_low, result.difference.ci_high) == (approx(9 - half), approx(9 + half))
    lc, lt = [math.log(v) for v in control], [math.log(v) for v in treatment]
    wc, wt = sd(lc) ** 2 / 4, sd(lt) ** 2 / 3
    log_df = (wc + wt) ** 2 / (wc**2 / 3 + wt**2 / 2)
    log_half = stats.t.ppf(0.975, log_df) * math.sqrt(wc + wt)
    centre = mean(lt) - mean(lc)
    assert result.ratio.estimate == approx(math.exp(centre))
    assert (result.ratio.ci_low, result.ratio.ci_high) == (approx(math.exp(centre - log_half)),
                                                           approx(math.exp(centre + log_half)))
    assert result.n_pairs is None and result.runs == [] and (result.n_control, result.n_treatment) == (4, 3)


def test_swapping_control_and_treatment_negates_difference_and_inverts_ratio():
    control, treatment = [100.0, 120.0, 90.0], [80.0, 90.0, 81.0]
    forward = estimates(control, treatment)
    reverse = estimates(treatment, control, control_label="Drug", treatment_label="DMSO")
    assert reverse.difference.estimate == approx(-forward.difference.estimate)
    assert reverse.difference.ci_low == approx(-forward.difference.ci_high)
    assert reverse.difference.ci_high == approx(-forward.difference.ci_low)
    assert reverse.ratio.estimate == approx(1 / forward.ratio.estimate)
    assert reverse.ratio.ci_low == approx(1 / forward.ratio.ci_high)


@pytest.mark.parametrize("metric, scale", [("positive_fraction", "fraction"), ("nucleolar_area_fraction", "fraction"),
                                           ("log2_nucleoplasm_over_nucleolus", "log2"),
                                           ("mean_corrected", "difference"), ("nucleolar_eccentricity", "difference")])
def test_scales_without_a_ratio_keep_the_difference(metric, scale):
    control, treatment = [0.2, 0.3, 0.25], [0.5, 0.45, 0.6]
    result = estimates(control, treatment, metric=metric)
    assert result.scale == scale
    assert result.ratio.estimate is None and result.ratio.unavailable_reason == "ratio_not_applicable"
    # A fraction's difference is in percentage points (×100); other scales keep the metric's unit.
    factor = 100 if scale == "fraction" else 1
    assert result.difference.estimate == approx(mean([0.3, 0.15, 0.35]) * factor)
    assert all(run.ratio is None for run in result.runs)


def test_nonpositive_values_have_no_ratio():
    result = estimates([0.0, 10.0, 12.0], [5.0, 8.0, 9.0], metric="mean")
    assert result.ratio.unavailable_reason == "nonpositive_values" and result.ratio.estimate is None
    assert result.runs[0].ratio is None and result.runs[1].ratio == approx(0.8)
    assert result.difference.estimate == approx(mean([5.0, -2.0, -3.0]))


@pytest.mark.parametrize("design, test", [("paired", "wilcoxon"), ("independent", "mann-whitney-u")])
def test_rank_tests_show_no_mean_difference_or_ratio_interval(design, test):
    control, treatment = [100.0, 120.0, 90.0], [80.0, 90.0, 81.0]
    result = estimates(control, treatment, design=design, test=test, pairs=["r1", "r2", "r3"] if design == "paired" else None)
    assert result.difference.unavailable_reason == "rank_test" and result.difference.estimate is None
    assert result.ratio.unavailable_reason == "rank_test" and result.ratio.estimate is None
    if design == "paired":
        assert [run.difference for run in result.runs] == [-20.0, -30.0, -9.0]
    groups = {group.condition: group for group in result.groups}
    assert groups["DMSO"].mean == approx(mean(control))


def test_too_few_pairs_and_units():
    result = estimates([100.0], [80.0], pairs=["r1"])
    assert result.difference.unavailable_reason == "too_few_pairs"
    assert result.ratio.unavailable_reason == "too_few_pairs"
    assert all(group.unavailable_reason == "too_few_units" and group.sd is None and group.ci_low is None
               for group in result.groups)
    assert result.runs[0].difference == -20.0
    welch = estimates([10.0], [20.0, 22.0], design="independent", test="welch-t", pairs=None)
    assert welch.difference.unavailable_reason == "too_few_units"


def test_zero_variance_is_not_estimable_but_other_scales_may_be():
    # Constant differences (5, 5) but different ratios (1.5, 1.25).
    result = estimates([10.0, 20.0], [15.0, 25.0], pairs=["r1", "r2"])
    assert result.difference.unavailable_reason == "zero_variance"
    logs = [math.log(1.5), math.log(1.25)]
    half = T975_DF1 * sd(logs) / math.sqrt(2)
    assert result.ratio.estimate == approx(math.exp(mean(logs)))
    assert result.ratio.ci_high == approx(math.exp(mean(logs) + half))
    welch = estimates([3.0, 3.0], [5.0, 5.0], design="independent", test="welch-t", pairs=None)
    assert welch.difference.unavailable_reason == "zero_variance"


# ---------------------------------------------------------------- field summary

def region(rid, border=False, positive=None):
    return {"region_id": rid, "touches_border": border, "positive": positive}


FIELDS = [
    {"field_id": "f1", "status": "measured", "shape": (100, 200), "pixel_size_um": 0.5,
     "regions": [region(1, True, True), region(2, False, False), region(3, False, None), region(4, False, True)],
     "excluded_region_ids": [7]},
    {"field_id": "f2", "status": "no_regions", "shape": (100, 200), "pixel_size_um": 0.5, "regions": [],
     "excluded_region_ids": []},
    {"field_id": "f3", "status": "failed", "shape": (100, 200), "pixel_size_um": 0.5, "regions": [],
     "excluded_region_ids": []},
    {"field_id": "f4", "status": "excluded", "shape": (100, 200), "pixel_size_um": 0.5, "regions": [region(1)],
     "excluded_region_ids": []},
    {"field_id": "f5", "status": "measured", "shape": (50, 50), "pixel_size_um": None,
     "regions": [region(1), region(2, True)], "excluded_region_ids": []},
]
GATE = {"version": "1.1.0", "gate_protocol": "gfp-gate/3.0.0", "gfp_channel_id": "gfp", "method": "manual",
        "threshold": 100.0, "keep": "positive"}


def summary(metric):
    selection = {"source": "field-summary", "region_set_id": "nuclei", "metric": metric}
    if metric.startswith("positive_"):
        selection["positivity"] = GATE
    fields = FIELDS if metric.startswith("positive_") else [
        {**field, "regions": [{**item, "positive": None} for item in field["regions"]]} for field in FIELDS]
    rows = pending(lambda: field_summary_values(fields, FieldSummarySelection.model_validate(selection)))
    assert [row["field_id"] for row in rows] == ["f1", "f2", "f3", "f4", "f5"]
    return {row["field_id"]: row for row in rows}


def test_nucleus_count_includes_border_nuclei_and_observed_zero():
    rows = summary("nucleus_count")
    assert rows["f1"]["value"] == 4 and rows["f1"]["border_count"] == 1 and rows["f1"]["excluded_region_count"] == 1
    assert rows["f2"]["value"] == 0 and rows["f2"]["missing_reason"] is None
    assert rows["f5"]["value"] == 2 and rows["f5"]["field_area_mm2"] is None
    assert rows["f1"]["field_area_mm2"] == approx(100 * 200 * 0.25e-6)
    assert rows["f1"]["evaluable_count"] is None and rows["f1"]["positive_count"] is None
    for fid, reason in (("f3", "field_failed"), ("f4", "field_excluded")):
        assert rows[fid]["value"] is None and rows[fid]["missing_reason"] == reason and rows[fid]["nucleus_count"] is None


def test_density_requires_calibration():
    rows = summary("nucleus_density_per_mm2")
    assert rows["f1"]["value"] == approx(4 / 0.005)
    assert rows["f2"]["value"] == 0
    assert rows["f5"]["value"] is None and rows["f5"]["missing_reason"] == "calibration_unknown"
    assert rows["f5"]["nucleus_count"] == 2


def test_positive_fraction_uses_evaluable_nuclei():
    rows = summary("positive_fraction")
    assert rows["f1"]["value"] == approx(2 / 3)
    assert (rows["f1"]["nucleus_count"], rows["f1"]["evaluable_count"], rows["f1"]["positive_count"]) == (4, 3, 2)
    assert rows["f2"]["value"] is None and rows["f2"]["missing_reason"] == "no_evaluable_nuclei"
    assert rows["f2"]["positive_count"] == 0
    assert rows["f5"]["value"] is None and rows["f5"]["missing_reason"] == "no_evaluable_nuclei"
    counts = summary("positive_count")
    assert counts["f1"]["value"] == 2 and counts["f2"]["value"] == 0


# ---------------------------------------------------------------- nucleolar eccentricity

def test_area_weighted_eccentricity_and_missing_reasons():
    nuclei = np.zeros((20, 20), dtype=np.uint32)
    nucleoli = np.zeros_like(nuclei)
    nuclei[0:6, 0:9] = 1
    nucleoli[1, 1:6] = 1          # 1×5 line: e = 1
    nucleoli[2:5, 6:9] = 2        # 3×3 square: e = 0
    nuclei[0:6, 10:16] = 2        # no nucleolus
    nuclei[8:12, 0:6] = 3
    nucleoli[9, 1] = 3            # single pixel: not measurable
    nuclei[8:14, 8:16] = 4
    nucleoli[9:11, 9:13] = 4      # 2×4 rectangle: var rows 0.25, var cols 1.25 → e = sqrt(0.8)
    nucleoli[12, 14] = 5          # single pixel, ignored
    nuclei[14:20, 0:6] = 5
    nucleoli[15, 1] = 6           # diagonal of 3 pixels: covariance rank 1 → e = 1
    nucleoli[16, 2] = 6
    nucleoli[17, 3] = 6
    shapes = pending(lambda: nucleolar_eccentricity(nuclei, nucleoli))
    assert set(shapes) == {1, 2, 3, 4, 5}
    assert shapes[1]["nucleolar_eccentricity"] == approx((5 * 1 + 9 * 0) / 14)
    assert (shapes[1]["objects"], shapes[1]["measured_objects"], shapes[1]["missing_reason"]) == (2, 2, None)
    assert shapes[2]["nucleolar_eccentricity"] is None and shapes[2]["missing_reason"] == "no_nucleolus"
    assert shapes[2]["objects"] == 0
    assert shapes[3]["nucleolar_eccentricity"] is None and shapes[3]["missing_reason"] == "degenerate_objects"
    assert (shapes[3]["objects"], shapes[3]["measured_objects"]) == (1, 0)
    assert shapes[4]["nucleolar_eccentricity"] == approx(math.sqrt(0.8))
    assert (shapes[4]["objects"], shapes[4]["measured_objects"]) == (2, 1)
    assert shapes[5]["nucleolar_eccentricity"] == approx(1.0)


def test_fraction_differences_are_percentage_points():
    # Hand calculation: per-run differences 0.20, 0.15, 0.20 → 20, 15, 20 points; mean 18.333…
    from cytellect_analysis.comparison_estimates import comparison_estimates

    result = comparison_estimates([0.2, 0.3, 0.4], [0.4, 0.45, 0.6], control_label="C", treatment_label="T",
                                  design="paired", test="paired-t", metric="positive_fraction",
                                  pairs=["r1", "r2", "r3"]).model_dump(mode="json")
    differences = [20.0, 15.0, 20.0]
    mean = sum(differences) / 3
    half = 4.303 * stats.tstd(differences) / 3 ** .5
    assert result["difference"]["estimate"] == pytest.approx(mean)
    assert result["difference"]["ci_low"] == pytest.approx(mean - half, rel=1e-3)
    assert [run["difference"] for run in result["runs"]] == pytest.approx(differences)
    assert result["groups"][0]["mean"] == pytest.approx(0.3)
    assert "percentage points" in result["difference"]["basis"]

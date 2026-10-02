import copy
import math

import numpy as np
import pandas as pd
import pytest
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.statistics import aggregate_units, analyze, analyze_sensitivity, finite_records
from scipy import stats


def rows():
    result = []
    rng = np.random.default_rng(4)
    for group, effect in (("A", 0), ("B", 2), ("C", 3)):
        for unit in range(4):
            for field in range(2):
                for cell in range(6):
                    gfp = 2 + cell + .4 * unit
                    value = effect + .3 * unit + .1 * field + np.log2(gfp) * .7 + rng.normal(0, .2)
                    result.append({"condition": group, "experimental_unit": f"{group}{unit}",
                                   "sample": f"{group}{unit}", "field_id": f"{group}{unit}-{field}",
                                   "acquisition_date": f"date{unit % 2}", "pair": f"pair{unit}",
                                   "ncl_nucleus_mean_corrected": value, "gfp_mean_corrected": gfp,
                                   "excluded": False, "gfp_positive": True,
                                   "repeat_length": None if group == "A" else (10 if group == "B" else 20)})
    return result


def request(**changes):
    return StatisticsRequest(metric="ncl_nucleus_mean_corrected", baseline="A",
                             comparisons=[("A", "B"), ("A", "C")],
                             independent_units_confirmed=True, **changes)


def test_aggregation_weights_fields_then_samples_not_cell_counts():
    data = pd.DataFrame([
        {"condition": "A", "experimental_unit": "u", "sample": "s1", "field_id": "f1", "v": 2},
        *[{"condition": "A", "experimental_unit": "u", "sample": "s1", "field_id": "f2", "v": 10}] * 100,
        {"condition": "A", "experimental_unit": "u", "sample": "s2", "field_id": "f3", "v": 20}])
    _, units = aggregate_units(data, "v")
    assert units.v.item() == 13  # ((2+10)/2 + 20)/2; not a pooled cell mean


def test_welch_matches_reference_and_holm():
    result = analyze(rows(), request())
    table = pd.DataFrame(result["unit_summary"])
    a = table[table.condition == "A"].ncl_nucleus_mean_corrected
    b = table[table.condition == "B"].ncl_nucleus_mean_corrected
    reference = stats.ttest_ind(a, b, equal_var=False)
    assert result["comparisons"][0]["p_value"] == pytest.approx(reference.pvalue)
    assert result["comparisons"][0]["ci_low"] == pytest.approx(reference.confidence_interval().low)
    p = sorted(r["p_value"] for r in result["comparisons"])
    adjusted = sorted(r["p_holm"] for r in result["comparisons"])
    assert adjusted == pytest.approx([min(1, 2*p[0]), min(1, max(2*p[0], p[1]))])
    assert all(c["experimental_units"] == 4 and c["cells"] == 48 for c in result["counts"])


def test_paired_and_incomplete_pairs():
    result = analyze(rows(), request(paired=True))
    assert all(c["n_a"] == 4 for c in result["comparisons"])
    data = [r for r in rows() if not (r["condition"] == "B" and r["pair"] == "pair0")]
    with pytest.raises(ValueError, match="incomplete_pairs"):
        analyze(data, request(paired=True))


def test_duplicate_reverse_and_mixed_families_rejected():
    spec = request()
    with pytest.raises(ValueError, match="duplicate_comparisons"):
        analyze(rows(), spec.model_copy(update={"comparisons": [("A", "B"), ("B", "A")]}))
    with pytest.raises(ValueError, match="separate_baseline"):
        analyze(rows(), spec.model_copy(update={"comparisons": [("A", "B"), ("B", "C")]}))


def test_constant_pair_differences_are_not_estimable():
    data = rows()
    for r in data:
        r["ncl_nucleus_mean_corrected"] = int(r["pair"][-1]) + (r["condition"] == "B") * 2
    with pytest.raises(ValueError, match="comparison_not_estimable"):
        analyze(data, request(paired=True))


def test_exploratory_rank_cluster_df_and_counts_after_filter():
    data = rows()
    data[0]["gfp_mean_corrected"] = 0
    result = analyze(data, request(mode="exploratory"))
    assert result["model"]["gfp_excluded_count"] == 1
    assert result["model"]["inference_df"] == 23
    assert sum(c["cells"] for c in result["counts"]) == len(data)-1
    assert len(result["plot_data"]) == len(data)-1
    assert result["model"]["trend"]["baseline_excluded"]
    assert math.isfinite(result["model"]["gfp_p_value"])
    assert "exploratory_cells_and_fields_are_not_biological_replicates" in result["warnings"]


def test_few_clusters_and_confounded_dates():
    data = rows()
    for r in data:
        r["acquisition_date"] = r["condition"]
    with pytest.raises(ValueError, match="confounded_or_rank_deficient"):
        analyze(data, request(mode="exploratory"))
    data = [r for r in rows() if r["condition"] != "C" and r["field_id"] in ("A0-0", "B0-0")]
    with pytest.raises(ValueError, match="at_least_three"):
        analyze(data, request(mode="exploratory").model_copy(update={"comparisons": [("A", "B")]}))


def test_missing_group_after_transform_and_invalid_values():
    data = rows()
    for r in data:
        if r["condition"] == "B":
            r["gfp_mean_corrected"] = 0
    with pytest.raises(ValueError, match="comparison_group_missing_after"):
        analyze(data, request(mode="exploratory"))
    assert finite_records(pd.DataFrame({"v": [np.inf, np.nan, 2]})) == [{"v": None}, {"v": None}, {"v": 2}]


def test_sensitivities_report_not_estimable_without_threshold_search():
    spec = request(sensitivity_gfp_thresholds=[0, 1e6], sensitivity_complete_dates=True)
    result = analyze_sensitivity(rows(), spec)
    assert [r["status"] for r in result["sensitivities"]] == ["succeeded", "not_estimable", "succeeded"]
    assert result["sensitivities"][0]["result"]["comparisons"] == result["comparisons"]


@pytest.mark.parametrize("primary_method", ["none", "confirmed-negative-control"])
def test_threshold_sensitivity_records_actual_gate_without_changing_primary(primary_method):
    data = rows()
    for index, row in enumerate(data):
        row.update(nucleus_id=index, gfp_gate_method=primary_method,
                   gfp_gate_threshold=6 if primary_method != "none" else None,
                   gfp_gate_maximum=7.5, gfp_gate_exploratory=False,
                   gfp_negative_control_fields=["control"] if primary_method != "none" else [],
                   gfp_positive=(primary_method == "none" or row["gfp_mean_corrected"] >= 6)
                                and row["gfp_mean_corrected"] <= 7.5)
        row["gfp_selection_reason"] = "included" if row["gfp_positive"] else "outside_gfp_gate"
    data[0].update(gfp_mean_corrected=None, gfp_positive=False, gfp_selection_reason="outside_gfp_gate")
    data[2].update(excluded=True, exclusion_reason="predeclared exclusion")
    original = copy.deepcopy(data)
    result = analyze_sensitivity(data, request(sensitivity_gfp_thresholds=[4]))
    scenario = result["sensitivities"][0]["result"]
    expected_ids = {row["nucleus_id"] for row in original
                    if not row["excluded"] and row["gfp_mean_corrected"] is not None
                    and 4 <= row["gfp_mean_corrected"] <= 7.5}
    assert {row["nucleus_id"] for row in scenario["plot_data"]} == expected_ids
    assert all(row["gfp_gate_threshold"] == 4 and row["gfp_gate_method"] == "manual"
               and row["gfp_gate_exploratory"] and row["gfp_negative_control_fields"] == []
               and row["gfp_selection_reason"] == "included" and row["gfp_gate_maximum"] == 7.5
               for row in scenario["plot_data"])
    assert scenario["selection"]["excluded"] == 1
    assert "data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation" in scenario["warnings"]
    assert all(row["gfp_gate_method"] == primary_method for row in result["plot_data"])
    assert data == original
    assert result["statistics_version"] == scenario["statistics_version"] == "1.2.1"


def test_shared_units_need_explicit_pairing():
    data = rows()
    for r in data:
        r["experimental_unit"] = r["pair"]
    with pytest.raises(ValueError, match="shared_units_require_paired"):
        analyze(data, request())
    analyze(data, request(paired=True))


def test_legacy_high_region_sensitivity_requires_measured_legacy_columns():
    data = rows()
    for row in data:
        row["recipe_id"] = "ncl-legacy-rgb"
        row["ncl_legacy_release"] = row["ncl_nucleus_mean_corrected"]
        row["ncl_legacy_top5_release"] = row["ncl_legacy_release"] * 1.1
    spec = request().model_copy(update={"metric": "ncl_legacy_release", "sensitivity_legacy_high_regions": [5]})
    result = analyze_sensitivity(data, spec)
    assert result["sensitivities"][0]["scenario"] == "legacy_high_region_top5"
    assert result["sensitivities"][0]["result"]["comparisons"][0]["estimate"] == pytest.approx(result["comparisons"][0]["estimate"] * 1.1)
    with pytest.raises(ValueError, match="legacy_high_region"):
        analyze_sensitivity(rows(), request(sensitivity_legacy_high_regions=[5]))


def test_confirmed_negative_control_gate_requires_explicit_provenance():
    from cytellect_analysis.contracts import AnalysisRequest, Recipe
    from cytellect_analysis.measurement import apply_gfp_gate
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Recipe(gfp_gate="negative-control", gfp_threshold=5)
    recipe = Recipe(gfp_gate="negative-control", gfp_threshold=5,
                    gfp_negative_control_fields=["negative-field"], gfp_negative_control_confirmed=True)
    data = [{"acquisition_date": "d", "gfp_mean_corrected": value} for value in (4, 5, 6)]
    selected = apply_gfp_gate(data, recipe)
    assert [r["gfp_positive"] for r in selected] == [False, True, True]
    assert all(r["gfp_gate_method"] == "confirmed-negative-control" and not r["gfp_gate_exploratory"] for r in selected)
    assert selected[0]["gfp_negative_control_fields"] == ["negative-field"]
    assert AnalysisRequest(field_ids=["field"]).field_ids == ["field"]
    with pytest.raises(ValidationError):
        AnalysisRequest(field_ids=[])

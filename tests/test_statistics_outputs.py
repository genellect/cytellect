"""Existing measurement columns remain selectable and exported inference stays traceable."""
import csv
import hashlib
import json
from typing import get_args

import pytest
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.figures import LABELS, export_statistical_tables, metric_label, render_figures
from cytellect_analysis.statistics import analyze, analyze_sensitivity
from test_statistics import request, rows

METRICS = get_args(StatisticsRequest.model_fields["metric"].annotation)


@pytest.mark.parametrize("metric", METRICS)
def test_each_defined_metric_is_selected_without_changing_values(metric):
    observations = [
        {"condition": group, "experimental_unit": f"{group}{i}", "sample": f"{group}{i}",
         "field_id": f"{group}{i}", "acquisition_date": "day", metric: value}
        for group, values in (("A", [1., 3.]), ("B", [5., 9.])) for i, value in enumerate(values)
    ]
    spec = StatisticsRequest(metric=metric, baseline="A", comparisons=[("A", "B")],
                             independent_units_confirmed=True)
    result = analyze(observations, spec)
    assert [row[metric] for row in result["plot_data"]] == [1., 3., 5., 9.]
    # Two units per group; mean(A)=2, mean(B)=7, SE=sqrt(1+4).
    assert result["comparisons"][0]["estimate"] == -5
    assert result["comparisons"][0]["standard_error"] == pytest.approx(5**.5)
    assert metric in LABELS


@pytest.mark.parametrize("metric", ["ncl_nucleoli_mean_corrected", "nucleoplasm_area_um2"])
def test_absent_compartment_or_calibration_is_not_zero(metric):
    data = rows()
    for row in data:
        row[metric] = None
    with pytest.raises(ValueError, match="no_valid_selected_measurements"):
        analyze(data, request().model_copy(update={"metric": metric}))


@pytest.mark.parametrize("metric", [m for m in METRICS if m.startswith("gfp_")])
def test_all_same_channel_gfp_outcomes_refuse_gfp_covariate(metric):
    data = rows()
    for row in data:
        row[metric] = row["gfp_mean_corrected"] * 3
    with pytest.raises(ValueError, match="own_gfp_covariate"):
        analyze(data, request(mode="exploratory").model_copy(update={"metric": metric}))


def test_integral_label_records_the_actual_pixel_grid():
    data = {"spec": {"metric": "ncl_nucleoli_integrated_corrected"}, "plot_data": [{"recipe_id": "ncl-native-2d"}]}
    assert "Nucleolar union" in metric_label(data, "en")
    assert "a.u. × pixel" in metric_label(data, "en")
    data["plot_data"][0]["recipe_id"] = "ncl-legacy-rgb"
    assert "High-intensity union" in metric_label(data, "en")
    assert "a.u. × scaled pixel" in metric_label(data, "en")
    assert "縮小画素" in metric_label(data, "ja")


def csv_rows(path):
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_model_and_scenario_csvs_preserve_values_counts_and_failure_reasons(tmp_path):
    result = analyze_sensitivity(rows(), request(mode="exploratory", sensitivity_gfp_thresholds=[0, 1e6]))
    render_figures(result, tmp_path)
    coefficients = csv_rows(tmp_path / "model-coefficients.csv")
    gfp = next(row for row in coefficients if row["term"] == "gfp_centered")
    assert float(gfp["estimate"]) == result["model"]["gfp_relationship"]["estimate"]
    assert float(gfp["p_value"]) == result["model"]["gfp_relationship"]["p_value"]
    assert gfp["p_adjustment"] == "none"
    trend = csv_rows(tmp_path / "repeat-trend.csv")[0]
    assert trend["status"] == "succeeded" and trend["p_adjustment"] == "none"
    assert float(trend["estimate"]) == result["model"]["trend"]["estimate"]
    scenarios = csv_rows(tmp_path / "sensitivity-status.csv")
    assert [s["status"] for s in scenarios] == ["succeeded", "not_estimable"]
    assert scenarios[1]["reason"] == "no_valid_selected_measurements"
    comparison = csv_rows(tmp_path / "sensitivity-comparisons.csv")[0]
    assert float(comparison["p_holm"]) == result["sensitivities"][0]["result"]["comparisons"][0]["p_holm"]
    count = csv_rows(tmp_path / "sensitivity-counts.csv")[0]
    assert (int(count["cells"]), int(count["fields"]), int(count["experimental_units"])) == (48, 8, 4)
    assert int(count["selection_missing_metric_selected"]) == 0
    source = json.loads((tmp_path / "figure-data.json").read_text(encoding="utf-8"))
    for name in ("model-coefficients.csv", "repeat-trend.csv", "sensitivity-comparisons.csv",
                 "sensitivity-counts.csv", "sensitivity-status.csv"):
        assert source["source_hashes"][name] == hashlib.sha256((tmp_path / name).read_bytes()).hexdigest()


def test_absent_repeat_lengths_produce_a_reason_not_a_zero_slope(tmp_path):
    data = [{**row, "repeat_length": None} for row in rows()]
    result = analyze(data, request(mode="exploratory"))
    export_statistical_tables(result, tmp_path)
    trend = csv_rows(tmp_path / "repeat-trend.csv")[0]
    assert result["model"]["trend"] is None
    assert trend["status"] == "not_available"
    assert trend["reason"] == "two_nonbaseline_repeat_lengths_required"
    assert "estimate" not in trend

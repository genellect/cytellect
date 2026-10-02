"""Versioned statistical protocol: explicit units, contrasts and cluster inference."""
from typing import Any

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from patsy import build_design_matrices
from scipy import stats
from statsmodels.stats.multitest import multipletests

from .contracts import StatisticsRequest

STATISTICS_VERSION = "1.2.0"
AGGREGATION = "field median -> mean of fields within sample -> mean of samples within independent unit"


def finite_records(frame):
    cleaned = frame.replace([np.inf, -np.inf], np.nan).astype(object)
    return cleaned.where(pd.notna(cleaned), None).to_dict("records")


def aggregate_units(frame, metric):
    keys = ["condition", "experimental_unit", "sample", "field_id"]
    fields = frame.groupby(keys, dropna=False, observed=True)[metric].median().reset_index()
    samples = fields.groupby(keys[:3], dropna=False, observed=True)[metric].mean().reset_index()
    units = samples.groupby(keys[:2], dropna=False, observed=True)[metric].mean().reset_index()
    if "pair" in frame:
        pairs = frame.groupby(keys[:2], dropna=False, observed=True).pair.agg(lambda v: v.dropna().unique().tolist())
        if any(len(v) > 1 for v in pairs):
            raise ValueError("multiple_pairs_per_unit")
        units["pair"] = [pairs.loc[(r.condition, r.experimental_unit)][0]
                         if pairs.loc[(r.condition, r.experimental_unit)] else None
                         for r in units.itertuples()]
    return fields, units


def _selected(rows, metric):
    data = pd.DataFrame(rows)
    required = {"condition", "experimental_unit", "sample", "field_id", "acquisition_date", metric}
    if data.empty or not required.issubset(data.columns):
        raise ValueError("no_measurements")
    for col in required - {metric}:
        if data[col].isna().any() or data[col].astype(str).str.strip().eq("").any():
            raise ValueError("missing_experimental_metadata")
    # A field cannot silently pool two samples, dates or conditions.
    for col in ("condition", "experimental_unit", "sample", "acquisition_date"):
        if data.groupby("field_id")[col].nunique().gt(1).any():
            raise ValueError("inconsistent_field_metadata")
    for flag, default in (("excluded", False), ("gfp_positive", True)):
        if flag not in data:
            data[flag] = default
        if not data[flag].map(lambda x: isinstance(x, (bool, np.bool_))).all():
            raise ValueError("invalid_selection_flags")
    data[metric] = pd.to_numeric(data[metric], errors="coerce")
    eligible = ~data.excluded & data.gfp_positive
    finite = np.isfinite(data[metric])
    selected = data[eligible & finite].copy()
    if selected.empty:
        raise ValueError("no_valid_selected_measurements")
    counts: dict[str, Any] = {"input_rows": len(data), "excluded": int(data.excluded.sum()),
              "gfp_unselected": int((~data.excluded & ~data.gfp_positive).sum()),
              "missing_metric_selected": int((eligible & ~finite).sum())}
    counts["by_condition"] = []
    for condition, group in data.groupby("condition", observed=True):
        adopted = selected[selected.condition == condition]
        counts["by_condition"].append({
            "condition": condition, "input_rows": len(group), "selected_rows": len(adopted),
            "excluded": int(group.excluded.sum()),
            "gfp_unselected": int((~group.excluded & ~group.gfp_positive).sum()),
            "missing_metric_selected": int((~group.excluded & group.gfp_positive & ~np.isfinite(group[metric])).sum()),
            "input_fields": int(group.field_id.nunique()), "selected_fields": int(adopted.field_id.nunique()),
            "input_units": int(group.experimental_unit.nunique()),
            "selected_units": int(adopted.experimental_unit.nunique())})
    return selected, counts


def _validate_comparisons(request, groups):
    if request.baseline not in groups or any(
        a not in groups or b not in groups or a == b for a, b in request.comparisons
    ):
        raise ValueError("comparison_group_missing")
    if len({frozenset(x) for x in request.comparisons}) != len(request.comparisons):
        raise ValueError("duplicate_comparisons")
    family = getattr(request, "comparison_family", "all")
    includes_baseline = [request.baseline in pair for pair in request.comparisons]
    if family == "baseline" and not all(includes_baseline):
        raise ValueError("comparison_family_mismatch")
    if family == "repeat" and any(includes_baseline):
        raise ValueError("comparison_family_mismatch")
    # Even an explicitly selected all-family must not mix scientifically distinct families.
    if any(includes_baseline) and not all(includes_baseline):
        raise ValueError("separate_baseline_and_repeat_families_required")


def _cluster_fit(frame, formula):
    clusters = frame.field_id.nunique()
    if clusters < 3:
        raise ValueError("at_least_three_fields_for_cluster_model")
    base = smf.ols(formula, frame, missing="raise")
    if np.linalg.matrix_rank(base.exog) < base.exog.shape[1] or len(frame) <= base.exog.shape[1]:
        raise ValueError("confounded_or_rank_deficient_model")
    fit = base.fit(cov_type="cluster", cov_kwds={
        "groups": frame.field_id, "use_correction": True, "df_correction": True}, use_t=True)
    if not np.isfinite(fit.cov_params()).all().all():
        raise ValueError("comparison_not_estimable")
    return fit


def _contrast(fit, vector):
    test = fit.t_test(vector)
    effect = float(np.asarray(test.effect).item())
    ci = np.asarray(test.conf_int())[0]
    p = float(np.asarray(test.pvalue).item())
    statistic = float(np.asarray(test.tvalue).item())
    standard_error = float(np.asarray(test.sd).item())
    if standard_error <= 0 or not np.isfinite(statistic):
        raise ValueError("comparison_not_estimable")
    if not np.isfinite([effect, *ci, p]).all():
        raise ValueError("comparison_not_estimable")
    return {"estimate": effect, "ci_low": float(ci[0]), "ci_high": float(ci[1]), "p_value": p,
            "statistic": statistic, "degrees_of_freedom": float(test.df_denom), "standard_error": standard_error,
            "alternative": "two-sided", "confidence_level": 0.95}


def _model(selected, request, groups, warnings):
    if request.paired:
        raise ValueError("paired_option_requires_experimental_unit_mode")
    if request.metric.startswith("gfp_"):
        raise ValueError("outcome_cannot_be_its_own_gfp_covariate")
    if "gfp_mean_corrected" not in selected:
        raise ValueError("gfp_required_for_exploratory_model")
    gfp = pd.to_numeric(selected.gfp_mean_corrected, errors="coerce")
    transform = getattr(request, "gfp_transform", "positive-log2")
    valid = np.isfinite(gfp)
    if transform == "positive-log2":
        valid &= gfp > 0
    removed = int((~valid).sum())
    if removed:
        warnings.append("nonpositive_or_missing_gfp_excluded_from_log_model")
    selected = selected[valid].copy()
    gfp = gfp[valid]
    if selected.empty or set(selected.condition) != set(groups):
        raise ValueError("comparison_group_missing_after_gfp_transform")
    selected["gfp_log2"] = np.log2(gfp) if transform == "positive-log2" else np.log2(np.maximum(gfp, 0) + 1)
    selected["gfp_centered"] = (selected.gfp_log2
                                - selected.groupby("acquisition_date").gfp_log2.transform("median"))
    selected["outcome"] = selected[request.metric]
    completeness = selected.groupby("acquisition_date").condition.agg(set)
    if any(set(groups) != g for g in completeness):
        warnings.append("incomplete_conditions_within_acquisition_date")
    if any(request.baseline not in g for g in completeness):
        warnings.append("baseline_missing_within_acquisition_date")
    if selected.field_id.nunique() < 3:
        raise ValueError("at_least_three_fields_for_cluster_model")
    if selected.groupby("condition", observed=True).field_id.nunique().lt(2).any():
        raise ValueError("two_fields_per_condition_for_cluster_model")
    if selected.groupby(["condition", "experimental_unit"], observed=True).field_id.nunique().gt(1).any():
        warnings.append("field_clustering_does_not_model_dependence_between_fields_from_the_same_unit")
    if selected.field_id.nunique() < 20:
        warnings.append("few_clusters_confidence_intervals_are_exploratory")
    formula = "outcome ~ C(condition) + gfp_centered"
    if selected.acquisition_date.nunique() > 1:
        formula += " + C(acquisition_date)"
    # Ordered categorical makes the declared baseline the actual model reference.
    selected["condition"] = pd.Categorical(selected.condition, categories=[
        request.baseline, *[g for g in groups if g != request.baseline]], ordered=True)
    fit = _cluster_fit(selected, formula)
    coefficient_table = []
    for index, term in enumerate(fit.params.index):
        vector = np.zeros(len(fit.params))
        vector[index] = 1
        entry: dict[str, Any] = {"term": str(term), "p_adjustment": "none", "inference": "exploratory field-clustered CRV1"}
        try:
            entry.update(status="succeeded", **_contrast(fit, vector))
        except ValueError:
            entry.update(status="not_estimable", reason="coefficient_inference_not_estimable",
                         estimate=float(fit.params.iloc[index]))
        coefficient_table.append(entry)
    dates = sorted(selected.acquisition_date.unique())
    vectors, means, comparisons, predictions = {}, [], [], []
    for group in groups:
        grid = pd.DataFrame({"condition": [group] * len(dates),
                             "gfp_centered": [0.] * len(dates), "acquisition_date": dates})
        vector = np.asarray(build_design_matrices([(getattr(fit.model.data, "design_info", None) or fit.model.data.model_spec)], grid)[0]).mean(axis=0)
        vectors[group] = vector
        value = _contrast(fit, vector)
        means.append({"condition": group, "mean": value["estimate"],
                      "ci_low": value["ci_low"], "ci_high": value["ci_high"]})
        observed = selected.loc[selected.condition == group, "gfp_centered"]
        for centered in np.linspace(float(observed.min()), float(observed.max()), 60):
            prediction_design = pd.DataFrame({"condition": [group] * len(dates),
                                              "gfp_centered": [centered] * len(dates),
                                              "acquisition_date": dates})
            prediction_vector = np.asarray(build_design_matrices([
                (getattr(fit.model.data, "design_info", None) or fit.model.data.model_spec)], prediction_design)[0]).mean(axis=0)
            prediction = _contrast(fit, prediction_vector)
            predictions.append({"condition": group, "gfp_centered": float(centered), "mean": prediction["estimate"],
                                "ci_low": prediction["ci_low"], "ci_high": prediction["ci_high"]})
    for a, b in request.comparisons:
        comparisons.append({"group_a": a, "group_b": b, **_contrast(fit, vectors[a] - vectors[b]),
                            "method": "OLS; field-clustered CRV1 SE; t with clusters-1 df",
                            "n_a": int((selected.condition == a).sum()),
                            "n_b": int((selected.condition == b).sum()), "n_unit": "cells"})
    details = {"prediction_grid": predictions, "acquisition_dates": list(dates),
               "gfp_date_medians": {str(date): float(value) for date, value in selected.groupby("acquisition_date", observed=True).gfp_log2.median().items()},
               "prediction_interval": "pointwise 95% adjusted-mean CI; field-cluster CRV1; t with fields-1 df; equal date weights",
               "formula": formula, "baseline": request.baseline, "gfp_transform": transform,
               "gfp_centering": "median within acquisition date on selected model rows",
               "gfp_excluded_count": removed,
               "adjusted_means": "GFP centered=0; equal weight across observed acquisition dates",
               "coefficients": {str(k): float(v) for k, v in fit.params.items()},
               "coefficient_table": coefficient_table,
               "gfp_relationship": next(row for row in coefficient_table if row["term"] == "gfp_centered"),
               "clusters": int(selected.field_id.nunique()), "inference_df": int(selected.field_id.nunique()) - 1,
               "gfp_coefficient": float(fit.params["gfp_centered"]),
               "gfp_p_value": float(fit.pvalues["gfp_centered"]), "trend": None,
               "trend_status": "not_available", "trend_reason": "two_nonbaseline_repeat_lengths_required"}
    if "repeat_length" in selected:
        trend = selected[(selected.condition != request.baseline) & selected.repeat_length.notna()].copy()
        trend["repeat_length"] = pd.to_numeric(trend.repeat_length, errors="coerce")
        if not trend.empty and trend.repeat_length.nunique() >= 2:
            tf = "outcome ~ repeat_length + gfp_centered"
            if trend.acquisition_date.nunique() > 1:
                tf += " + C(acquisition_date)"
            try:
                fitted = _cluster_fit(trend, tf)
                vector = np.zeros(len(fitted.params))
                vector[list(fitted.params.index).index("repeat_length")] = 1
                details["trend"] = {**_contrast(fitted, vector), "formula": tf, "baseline_excluded": True,
                                    "clusters": int(trend.field_id.nunique()), "p_adjustment": "none",
                                    "inference": "exploratory field-clustered CRV1"}
                details.update(trend_status="succeeded", trend_reason=None)
            except ValueError:
                details.update(trend_status="not_estimable", trend_reason="repeat_length_trend_not_estimable")
                warnings.append("repeat_length_trend_not_estimable")
    return selected, means, comparisons, details


def analyze(rows, request: StatisticsRequest):
    selected, selection = _selected(rows, request.metric)
    metric = request.metric
    groups = sorted(selected.condition.unique())
    _validate_comparisons(request, groups)
    warnings, comparisons, means = [], [], []
    if selection["missing_metric_selected"]:
        warnings.append("missing_outcomes_excluded_inspect_groupwise_missingness")
    if any(x["selected_units"] < x["input_units"] for x in selection["by_condition"]):
        warnings.append("some_experimental_units_have_no_selected_outcomes")
    if selected.get("gfp_gate_exploratory", pd.Series(False, index=selected.index)).any():
        warnings.append("data_derived_or_manual_gfp_selection_requires_predeclared_or_independent_validation")
    if selected.get("recipe_id", pd.Series("", index=selected.index)).isin(["ncl-native-2d", "ncl-legacy-rgb"]).any():
        warnings.append("ncl_defined_regions_can_change_with_the_measured_ncl_distribution")
    if request.paired:
        if "pair" not in selected or selected.pair.isna().any() or selected.pair.astype(str).str.strip().eq("").any():
            raise ValueError("unique_complete_pairs_required")
        if selected.groupby("experimental_unit").pair.nunique().gt(1).any():
            raise ValueError("inconsistent_pair_identity_for_shared_unit")
    model_details = None
    if request.mode == "exploratory":
        warnings.append("exploratory_cells_and_fields_are_not_biological_replicates")
        selected, means, comparisons, model_details = _model(selected, request, groups, warnings)
    fields, units = aggregate_units(selected, metric)
    if request.mode == "experimental-unit":
        if not request.independent_units_confirmed:
            raise ValueError("independent_units_must_be_confirmed")
        for a, b in request.comparisons:
            aa, bb = units[units.condition == a], units[units.condition == b]
            if request.paired:
                if ("pair" not in units or aa.pair.isna().any() or bb.pair.isna().any()
                        or aa.pair.duplicated().any() or bb.pair.duplicated().any()):
                    raise ValueError("unique_complete_pairs_required")
                pairs = aa.set_index("pair")[[metric]].join(
                    bb.set_index("pair")[[metric]], how="outer", lsuffix="_a", rsuffix="_b")
                if pairs.isna().any().any():
                    raise ValueError("incomplete_pairs")
                va, vb = pairs[f"{metric}_a"].to_numpy(), pairs[f"{metric}_b"].to_numpy()
                if len(va) < 2:
                    raise ValueError("two_pairs_required")
                if np.std(va - vb, ddof=1) <= np.finfo(float).eps * max(1., float(np.max(np.abs(va - vb)))):
                    raise ValueError("comparison_not_estimable")
                test = stats.ttest_rel(va, vb)
                method = "paired t-test"
            else:
                if set(aa.experimental_unit) & set(bb.experimental_unit):
                    raise ValueError("shared_units_require_paired_analysis")
                va, vb = aa[metric].to_numpy(), bb[metric].to_numpy()
                if min(len(va), len(vb)) < 2:
                    raise ValueError("two_independent_units_per_group_required")
                if np.var(va, ddof=1) + np.var(vb, ddof=1) == 0:
                    raise ValueError("comparison_not_estimable")
                test = stats.ttest_ind(va, vb, equal_var=False)
                method = "Welch t-test"
            ci = test.confidence_interval()
            if not np.isfinite([test.pvalue, ci.low, ci.high]).all():
                raise ValueError("comparison_not_estimable")
            comparisons.append({"group_a": a, "group_b": b, "estimate": float(va.mean() - vb.mean()),
                                "ci_low": float(ci.low), "ci_high": float(ci.high),
                                "p_value": float(test.pvalue), "method": method,
                                "statistic": float(test.statistic), "degrees_of_freedom": float(test.df),
                                "standard_error": float((ci.high - ci.low) / (2 * stats.t.ppf(.975, test.df))),
                                "alternative": "two-sided", "confidence_level": .95,
                                "n_a": len(va), "n_b": len(vb), "n_unit": "independent experimental units"})
        for group, values in units.groupby("condition", observed=True)[metric]:
            mean = float(values.mean())
            half = float(stats.t.ppf(.975, len(values)-1) * stats.sem(values)) if len(values) > 1 else None
            means.append({"condition": group, "mean": mean, "ci_low": mean-half if half is not None else None,
                          "ci_high": mean+half if half is not None else None})
    adjusted = multipletests([r["p_value"] for r in comparisons], method="holm")[1]
    for row, p in zip(comparisons, adjusted, strict=True):
        row["p_holm"] = float(p)
        row["correction_family"] = getattr(request, "comparison_family", "all")
    counts = selected.groupby("condition", observed=True).agg(
        cells=("field_id", "size"), fields=("field_id", "nunique"),
        experimental_units=("experimental_unit", "nunique")).reset_index()
    return {"spec": request.model_dump(), "statistics_version": STATISTICS_VERSION,
            "aggregation": AGGREGATION, "comparisons": comparisons, "means": means,
            "counts": finite_records(counts), "field_summary": finite_records(fields),
            "unit_summary": finite_records(units), "plot_data": finite_records(selected),
            "warnings": warnings, "model": model_details, "selection": selection,
            "missing_metric_count": selection["missing_metric_selected"]}


def analyze_sensitivity(rows, request: StatisticsRequest, alternate_rows=None):
    """User-declared alternatives, never optimize thresholds for significance.

    alternate_rows maps revision IDs to already remeasured, reviewed row lists. The caller
    must verify common input IDs/ownership/review; a metric column is not a new mask definition.
    """
    requested = set(request.sensitivity_region_revision_ids)
    if requested and set(alternate_rows or {}) != requested:
        raise ValueError("region_sensitivity_snapshots_required")
    result = analyze(rows, request)
    results = []
    options = [(f"gfp_threshold:{threshold}", [
        {**row, "gfp_positive": (row.get("gfp_mean_corrected") is not None
                                and np.isfinite(row["gfp_mean_corrected"])
                                and row["gfp_mean_corrected"] >= threshold
                                and (row.get("gfp_gate_maximum") is None or row["gfp_mean_corrected"] <= row["gfp_gate_maximum"]))}
        for row in rows]) for threshold in getattr(request, "sensitivity_gfp_thresholds", [])]
    if getattr(request, "sensitivity_complete_dates", False):
        eligible, _ = _selected(rows, request.metric)
        if request.mode == "exploratory":
            gfp = pd.to_numeric(eligible.get("gfp_mean_corrected"), errors="coerce")
            valid_gfp = np.isfinite(gfp)
            if request.gfp_transform == "positive-log2":
                valid_gfp &= gfp > 0
            eligible = eligible[valid_gfp]
        required = {request.baseline, *[group for pair in request.comparisons for group in pair]}
        complete = eligible.groupby("acquisition_date").condition.agg(set)
        dates = {date for date, present in complete.items() if required.issubset(present)}
        options.append(("complete_comparison_dates", [r for r in rows if r["acquisition_date"] in dates]))
    for percentile in getattr(request, "sensitivity_legacy_high_regions", []):
        key = f"ncl_legacy_top{percentile}_release"
        if request.metric != "ncl_legacy_release" or any(row.get("recipe_id") != "ncl-legacy-rgb" or key not in row for row in rows):
            raise ValueError("legacy_high_region_sensitivity_requires_legacy_measurements")
        options.append((f"legacy_high_region_top{percentile}", [{**row, request.metric: row[key]} for row in rows]))
    options.extend((f"region_revision:{rid}", alt) for rid, alt in (alternate_rows or {}).items())
    for label, alternative in options:
        try:
            analysis = analyze(alternative, request)
            results.append({"scenario": label, "status": "succeeded", "result": analysis})
        except ValueError as exc:
            # Error messages are fixed machine codes, not data or paths.
            results.append({"scenario": label, "status": "not_estimable", "reason": str(exc)})
    result["sensitivities"] = results
    return result

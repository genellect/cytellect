"""Experimental units and exploratory clustered models are explicitly distinct."""
import numpy as np
import pandas as pd
from scipy import stats
import statsmodels.formula.api as smf
from statsmodels.stats.multitest import multipletests
from patsy import build_design_matrices
from .contracts import StatisticsRequest

def finite_records(frame):
    return frame.replace([np.inf, -np.inf], np.nan).astype(object).where(pd.notna(frame), None).to_dict("records")

def aggregate_units(frame, metric):
    keys = ["condition", "experimental_unit", "sample", "field_id"]
    fields = frame.groupby(keys, dropna=False, observed=True)[metric].median().reset_index()
    samples = fields.groupby(keys[:3], dropna=False, observed=True)[metric].mean().reset_index()
    units = samples.groupby(keys[:2], dropna=False, observed=True)[metric].mean().reset_index()
    if "pair" in frame:
        pairs = frame.groupby(keys[:2], dropna=False).pair.agg(lambda v: v.dropna().unique().tolist())
        if any(len(v) > 1 for v in pairs):
            raise ValueError("multiple_pairs_per_unit")
        units["pair"] = [pairs.loc[(r.condition, r.experimental_unit)][0] if pairs.loc[(r.condition, r.experimental_unit)] else None for r in units.itertuples()]
    return fields, units

def analyze(rows, request: StatisticsRequest):
    data = pd.DataFrame(rows)
    metric = request.metric
    if data.empty or metric not in data:
        raise ValueError("no_measurements")
    selected = data[~data.excluded.astype(bool) & data.gfp_positive.astype(bool)].copy()
    selected = selected[np.isfinite(pd.to_numeric(selected[metric], errors="coerce"))]
    if selected.empty:
        raise ValueError("no_valid_selected_measurements")
    groups = sorted(selected.condition.unique())
    if request.baseline not in groups or any(a not in groups or b not in groups or a == b for a,b in request.comparisons):
        raise ValueError("comparison_group_missing")
    if len(set(request.comparisons)) != len(request.comparisons):
        raise ValueError("duplicate_comparisons")
    fields, units = aggregate_units(selected, metric)
    warnings, comparisons, means = [], [], []
    model_details = None
    if request.mode == "experimental-unit":
        if not request.independent_units_confirmed:
            raise ValueError("independent_units_must_be_confirmed")
        for a, b in request.comparisons:
            aa, bb = units[units.condition == a], units[units.condition == b]
            if request.paired:
                if "pair" not in units or aa.pair.isna().any() or bb.pair.isna().any() or aa.pair.duplicated().any() or bb.pair.duplicated().any():
                    raise ValueError("unique_complete_pairs_required")
                paired = aa.set_index("pair")[[metric]].join(bb.set_index("pair")[[metric]], how="outer", lsuffix="_a", rsuffix="_b")
                if paired.isna().any().any():
                    raise ValueError("incomplete_pairs")
                va, vb = paired[f"{metric}_a"].to_numpy(), paired[f"{metric}_b"].to_numpy()
                if len(va) < 2:
                    raise ValueError("two_pairs_required")
                test = stats.ttest_rel(va, vb)
                method = "paired t-test"
            else:
                va, vb = aa[metric].to_numpy(), bb[metric].to_numpy()
                if min(len(va), len(vb)) < 2:
                    raise ValueError("two_independent_units_per_group_required")
                test = stats.ttest_ind(va, vb, equal_var=False)
                method = "Welch t-test"
            if not np.isfinite(test.pvalue):
                raise ValueError("comparison_not_estimable")
            ci = test.confidence_interval()
            comparisons.append({"group_a": a, "group_b": b, "estimate": float(va.mean()-vb.mean()),
                                "ci_low": float(ci.low), "ci_high": float(ci.high), "p_value": float(test.pvalue),
                                "method": method, "n_a": len(va), "n_b": len(vb)})
        for group, values in units.groupby("condition")[metric]:
            mean = float(values.mean())
            half = float(stats.t.ppf(.975, len(values)-1) * stats.sem(values)) if len(values) > 1 else None
            means.append({"condition": group, "mean": mean, "ci_low": mean-half if half is not None else None, "ci_high": mean+half if half is not None else None})
    else:
        warnings.append("exploratory_cells_and_fields_are_not_biological_replicates")
        # Drop nonpositive GFP from a native logarithm explicitly, never clip it.
        valid = selected.gfp_mean_corrected > 0
        if not valid.all():
            warnings.append("nonpositive_gfp_excluded_from_log_model")
        selected = selected[valid].copy()
        selected["gfp_log2"] = np.log2(selected.gfp_mean_corrected)
        selected["gfp_centered"] = selected.gfp_log2 - selected.groupby("acquisition_date").gfp_log2.transform("median")
        selected["outcome"] = selected[metric]
        if len(selected.field_id.unique()) < 3:
            raise ValueError("at_least_three_fields_for_cluster_model")
        if len(selected.field_id.unique()) < 20:
            warnings.append("few_clusters_confidence_intervals_are_exploratory")
        complete = selected.groupby("acquisition_date").condition.agg(lambda g: set(g))
        if any(set(groups) != g for g in complete):
            warnings.append("incomplete_conditions_within_acquisition_date")
        formula = "outcome ~ C(condition) + gfp_centered"
        if selected.acquisition_date.nunique() > 1:
            formula += " + C(acquisition_date)"
        base = smf.ols(formula, selected)
        if np.linalg.matrix_rank(base.exog) < base.exog.shape[1] or len(selected) <= base.exog.shape[1]:
            raise ValueError("confounded_or_rank_deficient_model")
        fit = base.fit(cov_type="cluster", cov_kwds={"groups": selected.field_id, "use_correction": True}, use_t=True)
        design = fit.model.data.design_info
        dates = sorted(selected.acquisition_date.unique())
        vectors = {}
        for group in groups:
            grid = pd.DataFrame({"condition":[group]*len(dates), "gfp_centered":[0.]*len(dates), "acquisition_date":dates})
            vector = np.asarray(build_design_matrices([design], grid)[0]).mean(axis=0)
            vectors[group] = vector
            test = fit.t_test(vector)
            ci = np.asarray(test.conf_int())[0]
            means.append({"condition":group, "mean":float(np.asarray(test.effect).item()), "ci_low":float(ci[0]), "ci_high":float(ci[1])})
        for a,b in request.comparisons:
            test = fit.t_test(vectors[a]-vectors[b])
            ci = np.asarray(test.conf_int())[0]
            comparisons.append({"group_a":a,"group_b":b,"estimate":float(np.asarray(test.effect).item()),
                                "ci_low":float(ci[0]),"ci_high":float(ci[1]),"p_value":float(np.asarray(test.pvalue).item()),
                                "method":"OLS, field-clustered SE", "n_a":int((selected.condition==a).sum()),"n_b":int((selected.condition==b).sum())})
        model_details = {"formula":formula, "gfp_transform":"log2 positive background-corrected GFP; median centered within acquisition date",
                         "adjusted_means":"GFP centered=0; equal weight across observed acquisition dates",
                         "coefficients": {str(k):float(v) for k,v in fit.params.items()},
                         "gfp_p_value":float(fit.pvalues["gfp_centered"]), "trend":None}
        trend = selected[(selected.condition != request.baseline) & selected.repeat_length.notna()].copy() if "repeat_length" in selected else pd.DataFrame()
        if not trend.empty and trend.repeat_length.nunique() >= 2:
            trend_formula = "outcome ~ repeat_length + gfp_centered" + (" + C(acquisition_date)" if trend.acquisition_date.nunique()>1 else "")
            trend_base = smf.ols(trend_formula, trend)
            if np.linalg.matrix_rank(trend_base.exog) == trend_base.exog.shape[1] and trend.field_id.nunique() >= 3:
                tf = trend_base.fit(cov_type="cluster",cov_kwds={"groups":trend.field_id,"use_correction":True},use_t=True)
                model_details["trend"] = {"coefficient":float(tf.params["repeat_length"]),"p_value":float(tf.pvalues["repeat_length"]),"baseline_excluded":True}
    adjusted = multipletests([r["p_value"] for r in comparisons], method="holm")[1]
    for row, p in zip(comparisons, adjusted, strict=True):
        row["p_holm"] = float(p)
    counts = selected.groupby("condition").agg(cells=("field_id","size"), fields=("field_id","nunique"), experimental_units=("experimental_unit","nunique")).reset_index()
    return {"spec":request.model_dump(), "comparisons":comparisons, "means":means, "counts":finite_records(counts),
            "field_summary":finite_records(fields), "unit_summary":finite_records(units), "plot_data":finite_records(selected),
            "warnings":warnings, "model":model_details, "missing_metric_count":int(data[metric].isna().sum())}

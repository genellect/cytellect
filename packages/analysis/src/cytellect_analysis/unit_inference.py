"""Marker-neutral arithmetic; callers own design, selection and provenance checks."""
import numpy as np
from scipy import stats
from statsmodels.stats.multitest import multipletests

VERSION = "1.0.0"


def aggregate_unit_observations(frame, metric):
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
    return fields, samples, units


def compare_unit_arrays(va, vb, *, paired):
    va, vb = np.asarray(va), np.asarray(vb)
    if (va.ndim != 1 or vb.ndim != 1 or va.dtype.kind not in "iuf" or vb.dtype.kind not in "iuf"
            or not np.isfinite(va).all() or not np.isfinite(vb).all()):
        raise ValueError("comparison_not_estimable")
    va, vb = va.astype(float), vb.astype(float)
    if paired:
        if len(va) != len(vb):
            raise ValueError("incomplete_pairs")
        if len(va) < 2:
            raise ValueError("two_pairs_required")
        differences = va - vb
        difference_sd = float(np.std(differences, ddof=1))
        # Relative tolerance carries the measurement unit; never floor it at 1.
        if difference_sd <= np.finfo(float).eps * float(np.max(np.abs(differences))):
            raise ValueError("comparison_not_estimable")
        test = stats.ttest_rel(va, vb)
        standard_error = difference_sd / np.sqrt(len(va))
        estimate = float(differences.mean())
        method = "paired t-test"
    else:
        if min(len(va), len(vb)) < 2:
            raise ValueError("two_independent_units_per_group_required")
        if np.var(va, ddof=1) + np.var(vb, ddof=1) == 0:
            raise ValueError("comparison_not_estimable")
        test = stats.ttest_ind(va, vb, equal_var=False)
        standard_error = np.hypot(np.std(va, ddof=1) / np.sqrt(len(va)),
                                  np.std(vb, ddof=1) / np.sqrt(len(vb)))
        estimate = float(va.mean() - vb.mean())
        method = "Welch t-test"
    ci = test.confidence_interval()
    if (standard_error <= 0 or not np.isfinite([
            estimate, standard_error, test.statistic, test.df, test.pvalue, ci.low, ci.high]).all()):
        raise ValueError("comparison_not_estimable")
    return {"estimate": estimate, "ci_low": float(ci.low), "ci_high": float(ci.high),
            "p_value": float(test.pvalue), "method": method, "statistic": float(test.statistic),
            "degrees_of_freedom": float(test.df), "standard_error": float(standard_error),
            "alternative": "two-sided", "confidence_level": .95,
            "n_a": len(va), "n_b": len(vb), "n_unit": "independent experimental units"}


def apply_holm(comparisons, family_id):
    adjusted = multipletests([row["p_value"] for row in comparisons], method="holm")[1]
    for row, p in zip(comparisons, adjusted, strict=True):
        row["p_holm"] = float(p)
        row["correction_family"] = family_id
    return comparisons

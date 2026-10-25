"""Treatment − control estimates 1.0.0 for two-group comparisons.

Definitions are in docs/methods.md, "Comparison estimates 1.0.0". Inputs are the
independent-unit values already aggregated by the saved comparison
(field → sample → unit); this module never re-aggregates observations and never
chooses or replaces the declared test.
"""
from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

import numpy as np
from scipy import stats

from .group_comparison_contracts import ComparisonEstimates, metric_scale

LEVEL = 0.95


def _unavailable(reason: str) -> dict:
    return {"estimate": None, "ci_low": None, "ci_high": None, "basis": None, "unavailable_reason": reason}


def _mean_interval(values: np.ndarray, few: str) -> tuple[float, float, float] | str:
    """Mean and two-sided 95% t interval; a reason when not estimable."""
    if values.size < 2:
        return few
    spread = float(values.std(ddof=1))
    if spread == 0:
        return "zero_variance"
    half = float(stats.t.ppf(0.5 + LEVEL / 2, values.size - 1)) * spread / math.sqrt(values.size)
    centre = float(values.mean())
    return centre, centre - half, centre + half


def _welch_interval(control: np.ndarray, treatment: np.ndarray) -> tuple[float, float, float] | str:
    """Difference of means (treatment − control) with the Welch–Satterthwaite interval."""
    if control.size < 2 or treatment.size < 2:
        return "too_few_units"
    vc, vt = control.var(ddof=1) / control.size, treatment.var(ddof=1) / treatment.size
    if vc + vt == 0:
        return "zero_variance"
    df = (vc + vt) ** 2 / (vc**2 / (control.size - 1) + vt**2 / (treatment.size - 1))
    half = float(stats.t.ppf(0.5 + LEVEL / 2, df)) * math.sqrt(vc + vt)
    centre = float(treatment.mean() - control.mean())
    return centre, centre - half, centre + half


def _interval(result: tuple[float, float, float] | str, basis: str, transform=None) -> dict:
    if isinstance(result, str):
        return _unavailable(result)
    values = tuple(transform(value) for value in result) if transform else result
    return {"estimate": values[0], "ci_low": values[1], "ci_high": values[2], "basis": basis,
            "unavailable_reason": None}


def _group(label: str, values: np.ndarray) -> dict:
    mean = float(values.mean()) if values.size else None
    result = _mean_interval(values, "too_few_units")
    if values.size >= 2 and result == "zero_variance":
        return {"condition": label, "n": int(values.size), "mean": mean, "sd": 0.0, "ci_low": mean, "ci_high": mean,
                "unavailable_reason": None}
    if isinstance(result, str):
        return {"condition": label, "n": int(values.size), "mean": mean, "sd": None, "ci_low": None, "ci_high": None,
                "unavailable_reason": result}
    return {"condition": label, "n": int(values.size), "mean": mean, "sd": float(values.std(ddof=1)),
            "ci_low": result[1], "ci_high": result[2], "unavailable_reason": None}


def comparison_estimates(control: Sequence[float], treatment: Sequence[float], *, control_label: str,
                         treatment_label: str, design: Literal["independent", "paired"],
                         test: Literal["welch-t", "paired-t", "mann-whitney-u", "wilcoxon"], metric: str,
                         pairs: Sequence[str] | None = None) -> ComparisonEstimates:
    """For a paired design, control[i] and treatment[i] are the two units of pairs[i]."""
    c, t = np.asarray(control, dtype=np.float64), np.asarray(treatment, dtype=np.float64)
    if not (np.all(np.isfinite(c)) and np.all(np.isfinite(t))):
        raise ValueError("comparison_estimates_nonfinite")
    paired = design == "paired"
    if paired != (test in ("paired-t", "wilcoxon")):
        raise ValueError("comparison_estimates_test_design_mismatch")
    if paired and (pairs is None or len(pairs) != c.size or c.size != t.size):
        raise ValueError("comparison_estimates_pairs_mismatch")
    scale = metric_scale(metric)
    rank = test in ("mann-whitney-u", "wilcoxon")
    few = "too_few_pairs" if paired else "too_few_units"
    positive = bool(c.size and t.size and np.all(c > 0) and np.all(t > 0))
    # A fraction's difference is reported in percentage points (×100); its unit values stay fractions.
    points = scale == "fraction"
    to_points = (lambda value: value * 100) if points else None
    unit = " in percentage points" if points else ""
    if rank:
        difference = ratio = _unavailable("rank_test")
    else:
        if paired:
            difference = _interval(_mean_interval(t - c, few),
                                   f"mean of per-run differences (treatment - control){unit}", to_points)
        else:
            difference = _interval(_welch_interval(c, t),
                                   f"difference of group means (treatment - control), Welch{unit}", to_points)
        if scale != "ratio":
            ratio = _unavailable("ratio_not_applicable")
        elif not positive:
            ratio = _unavailable("nonpositive_values")
        elif paired:
            ratio = _interval(_mean_interval(np.log(t / c), few),
                              "geometric mean of per-run ratios (treatment / control)", math.exp)
        else:
            ratio = _interval(_welch_interval(np.log(c), np.log(t)),
                              "ratio of geometric means (treatment / control), Welch on log values", math.exp)
    runs = []
    if paired:
        for pair, before, after in zip(pairs or [], c, t, strict=True):
            runs.append({"pair": pair, "control": float(before), "treatment": float(after),
                         "difference": float((after - before) * (100 if points else 1)),
                         "ratio": float(after / before) if scale == "ratio" and before > 0 and after > 0 else None})
    return ComparisonEstimates.model_validate({
        "control": control_label, "treatment": treatment_label, "design": design, "test": test, "metric": metric,
        "scale": scale, "n_control": int(c.size), "n_treatment": int(t.size), "n_pairs": int(c.size) if paired else None,
        "difference": difference, "ratio": ratio,
        "groups": [_group(control_label, c), _group(treatment_label, t)], "runs": runs})

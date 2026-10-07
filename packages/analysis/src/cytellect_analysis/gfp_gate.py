"""GFP-positive nucleus gate derived from negative-control nuclei (protocol gfp-gate/2.0.0).

The threshold is a high percentile of the per-nucleus GFP means of nuclei the
researcher designated as GFP-negative controls (untransfected cells or GFP-
negative cells imaged under the same conditions), computed separately for each
acquisition date. This follows the control-distribution practice used for
per-nucleus immunofluorescence gates (e.g. Sutton & DeRose, J Biol Chem 2021,
doi:10.1016/j.jbc.2021.100633: threshold at the 90th percentile of untreated
controls). Otsu on the pooled population is not used: its threshold moves with
the transfected fraction, which differs between conditions.

GFP is a covariate/selection, never a denominator. A date without enough control
nuclei gets no threshold and its nuclei are unselected with a reason, never
silently treated as positive.
"""
from __future__ import annotations

import math
from collections import defaultdict

import numpy as np

PROTOCOL = "gfp-gate/2.0.0"
MINIMUM_CONTROL_NUCLEI = 20
EXPLORATORY_PROTOCOL = "gfp-gate/3.0.0"


def control_thresholds(rows: list[dict], percentile: float = 99.0) -> dict:
    """rows: dicts with acquisition_date, gfp_mean and control (bool). Returns per-date thresholds."""
    if not 50 <= percentile < 100:
        raise ValueError("gfp_control_percentile_invalid")
    by_date: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        value = row.get("gfp_mean")
        if row.get("control") and value is not None and math.isfinite(value):
            by_date[str(row.get("acquisition_date"))].append(float(value))
    result: dict[str, dict] = {}
    for date in sorted({str(row.get("acquisition_date")) for row in rows}):
        values = by_date.get(date, [])
        if len(values) < MINIMUM_CONTROL_NUCLEI:
            result[date] = {"threshold": None, "control_nuclei": len(values),
                            "missing_reason": "too_few_control_nuclei"}
        else:
            result[date] = {"threshold": float(np.percentile(values, percentile, method="linear")),
                            "control_nuclei": len(values), "missing_reason": None}
    return {"protocol": PROTOCOL, "percentile": percentile, "minimum_control_nuclei": MINIMUM_CONTROL_NUCLEI,
            "dates": result}


def apply_control_gate(rows: list[dict], thresholds: dict) -> list[dict]:
    """Label each non-control nucleus positive/negative against its date's control threshold."""
    gated = []
    for row in rows:
        date = thresholds["dates"].get(str(row.get("acquisition_date")), {})
        threshold, value = date.get("threshold"), row.get("gfp_mean")
        if row.get("control"):
            reason, positive = "negative_control", False
        elif threshold is None:
            reason, positive = date.get("missing_reason") or "no_control_threshold", False
        elif value is None or not math.isfinite(value):
            reason, positive = "gfp_missing", False
        else:
            positive = value > threshold
            reason = "above_control_threshold" if positive else "within_control_range"
        gated.append({**row, "gfp_positive": bool(positive), "gfp_gate_threshold": threshold,
                      "gfp_gate_reason": reason, "gfp_gate_protocol": PROTOCOL})
    return gated


def exploratory_thresholds(rows: list[dict], method: str, threshold: float | None = None) -> dict:
    """Explicit manual threshold or batch Otsu of nuclear means (256 bins, first maximum).

    Batch/date is required only for Otsu. Uniform or insufficient distributions
    remain unclassified. Missing corrected means never fall back to raw values.
    """
    from skimage.filters import threshold_otsu

    if method not in ("manual", "batch_otsu") or ((method == "manual") != (threshold is not None)):
        raise ValueError("gfp_exploratory_threshold_invalid")
    if threshold is not None and not math.isfinite(threshold):
        raise ValueError("gfp_exploratory_threshold_invalid")
    dates: dict[str, dict] = {}
    if method == "manual":
        dates = {"all": {"threshold": threshold, "control_nuclei": 0, "missing_reason": None}}
    else:
        by_date: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            date = row.get("acquisition_date")
            key = date if isinstance(date, str) and date.strip() else ""
            values = by_date[key]
            value = row.get("gfp_mean")
            if value is not None and math.isfinite(value):
                values.append(float(value))
        dates = {}
        for key, values in sorted(by_date.items()):
            reason = "gfp_gate_acquisition_date_required" if not key else (
                "gfp_too_few_nuclei" if len(values) < 2 else "gfp_uniform_distribution"
                if min(values) == max(values) else None)
            dates[key] = {"threshold": None if reason else float(threshold_otsu(np.asarray(values), nbins=256)),
                          "control_nuclei": 0, "measured_nuclei": len(values), "missing_reason": reason}
    return {"protocol": EXPLORATORY_PROTOCOL, "method": method, "dates": dates,
            "exploratory": True, "threshold_population": "per-nucleus arithmetic means",
            "histogram_bins": 256 if method == "batch_otsu" else None}


def apply_exploratory_gate(rows: list[dict], thresholds: dict) -> list[dict]:
    gated = []
    for row in rows:
        date = row.get("acquisition_date")
        key = "all" if thresholds["method"] == "manual" else (date if isinstance(date, str) and date.strip() else "")
        settings = thresholds["dates"].get(key, {})
        threshold, value = settings.get("threshold"), row.get("gfp_mean")
        if value is None or not math.isfinite(value):
            positive, reason = None, "gfp_missing"
        elif threshold is None:
            positive, reason = None, settings.get("missing_reason") or "gfp_threshold_missing"
        else:
            positive = bool(value > threshold)
            reason = "above_exploratory_threshold" if positive else "at_or_below_exploratory_threshold"
        gated.append({**row, "gfp_positive": positive, "gfp_gate_threshold": threshold,
                      "gfp_gate_reason": reason, "gfp_gate_protocol": EXPLORATORY_PROTOCOL})
    return gated

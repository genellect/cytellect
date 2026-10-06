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

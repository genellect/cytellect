"""Per-nucleus pixel statistics of one channel: heterogeneity and positive area (genellect/cytellect#257 E-7).

Definitions are in docs/methods.md, "Per-nucleus signal heterogeneity and positive area 1.0.0". The module reads the
original pixels inside saved nuclear labels and never changes them. It needs no nucleolar boundary: the coefficient of
variation and the positive-area fraction are defined on the whole nucleus.

- Coefficient of variation (CV): population standard deviation / mean of the nucleus's pixels, in the chosen value basis
  (raw, or background-corrected by subtracting the confirmed background median). The mean and standard deviation are
  kept beside it. A nucleus whose mean is not positive has no CV (``nonpositive_mean``); there is no smoothing, epsilon
  or clipping.
- Positive-area fraction: pixels at or above a threshold / pixels of the nucleus. The threshold is either a value the
  researcher records (``manual``) or Otsu's threshold of all adopted nuclear pixels of the field (``field_otsu``); its
  method, value basis, value and the unit it was applied to are returned with the rows. No threshold is borrowed from
  another image or publication.
"""
from __future__ import annotations

import math
from typing import Literal, TypedDict

import numpy as np

from .masks import validate_label_array

PROTOCOL: Literal["nuclear-signal/1.0.0"] = "nuclear-signal/1.0.0"
Values = Literal["raw", "corrected"]


class ThresholdRule(TypedDict):
    method: Literal["manual", "field_otsu"]
    value: float | None


class AppliedThreshold(TypedDict):
    method: Literal["manual", "field_otsu"]
    values: Values
    value: float | None
    applied_to: Literal["field"]
    missing_reason: str | None


class NuclearSignalRow(TypedDict):
    nucleus_id: int
    pixels: int
    mean: float | None
    sd: float | None
    cv: float | None
    cv_missing_reason: str | None
    positive_pixels: int | None
    positive_area_fraction: float | None
    positive_missing_reason: str | None


class NuclearSignal(TypedDict):
    protocol: Literal["nuclear-signal/1.0.0"]
    values: Values
    background: float | None
    threshold: AppliedThreshold | None
    rows: list[NuclearSignalRow]


def _otsu(values: np.ndarray) -> float | None:
    """Otsu's threshold of the pooled nuclear pixels; None when they are all equal (no split exists)."""
    if values.size < 2 or float(values.min()) == float(values.max()):
        return None
    from skimage.filters import threshold_otsu
    return float(threshold_otsu(values))


def nuclear_signal(nuclei: np.ndarray, image: np.ndarray, *, values: Values = "raw", background: float | None = None,
                   threshold: ThresholdRule | None = None, excluded: frozenset[int] = frozenset()) -> NuclearSignal:
    """One row per nucleus label in ``nuclei`` (ascending), measured on ``image`` at the same original coordinates.

    ``excluded`` nucleus IDs keep their rows with every value missing (``nucleus_excluded``) and do not enter a
    field-level Otsu threshold. ``background`` is required for corrected values and refused for raw ones.
    """
    validate_label_array(nuclei)
    if image.shape != nuclei.shape or image.ndim != 2:
        raise ValueError("nuclear_signal_shape_mismatch")
    if values == "corrected" and (background is None or not math.isfinite(background)):
        raise ValueError("nuclear_signal_background_required")
    if values == "raw" and background is not None:
        raise ValueError("nuclear_signal_background_must_be_unset")
    if threshold is not None and threshold["method"] == "manual" and (threshold["value"] is None or not math.isfinite(threshold["value"])):
        raise ValueError("nuclear_signal_threshold_invalid")
    offset = float(background) if values == "corrected" and background is not None else 0.0
    pixels = image.astype(np.float64) - offset
    ids = [int(value) for value in np.unique(nuclei) if value]
    applied: AppliedThreshold | None = None
    if threshold is not None:
        if threshold["method"] == "manual":
            value: float | None = threshold["value"]
        else:
            kept = (nuclei > 0) & ~np.isin(nuclei, sorted(excluded))
            value = _otsu(pixels[kept])
        applied = AppliedThreshold(method=threshold["method"], values=values, value=value, applied_to="field",
                                   missing_reason=None if value is not None else "threshold_not_established")
    rows: list[NuclearSignalRow] = []
    for nucleus_id in ids:
        inside = pixels[nuclei == nucleus_id]
        count = int(inside.size)
        if nucleus_id in excluded:
            rows.append({"nucleus_id": nucleus_id, "pixels": count, "mean": None, "sd": None, "cv": None,
                         "cv_missing_reason": "nucleus_excluded", "positive_pixels": None,
                         "positive_area_fraction": None, "positive_missing_reason": "nucleus_excluded"})
            continue
        mean = float(inside.mean())
        sd = float(inside.std(ddof=0))
        cv = sd / mean if mean > 0 else None
        positive: int | None = None
        fraction: float | None = None
        reason: str | None = "threshold_not_set"
        if applied is not None:
            reason = applied["missing_reason"]
            if applied["value"] is not None:
                positive = int(np.count_nonzero(inside >= applied["value"]))
                fraction, reason = positive / count, None
        rows.append({"nucleus_id": nucleus_id, "pixels": count, "mean": mean, "sd": sd, "cv": cv,
                     "cv_missing_reason": None if cv is not None else "nonpositive_mean",
                     "positive_pixels": positive, "positive_area_fraction": fraction, "positive_missing_reason": reason})
    return {"protocol": PROTOCOL, "values": values, "background": offset if values == "corrected" else None,
            "threshold": applied, "rows": rows}

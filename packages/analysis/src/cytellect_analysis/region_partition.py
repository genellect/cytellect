"""Channel-neutral partition arithmetic on original-coordinate, adopted masks.

This primitive measures a supplied target and selected reference within each
exact nuclear label. It does not identify structures, adopt masks, establish
biological validity, or verify source ownership/status. The caller must establish
those facts and retain the nuclear/target/reference sources, measurement channel,
and confirmed measurement-background provenance. A reference is never inferred
from the unassigned pixels or called nucleoplasm by this module.

Nonzero target/reference values mean membership only; their independent object
labels are not parent IDs. Parent IDs come exclusively from the nuclear labels
at the same original coordinates. The two memberships must be disjoint and wholly
inside nuclei; unassigned nuclear pixels are allowed. Labels are limited to the
repository's original-coordinate mask range, 0 through uint32 maximum.

Raw and background-corrected measurements are retained separately. Background is
a confirmed measurement-channel background supplied by the caller, not detection
preprocessing. No correction, clipping, epsilon, or raw fallback is implicit.
Empty memberships are missing, including their area, rather than measured zero.
K is target mean / reference mean; the historical inverse compartment-summary
metric is independent and unchanged.
"""
from __future__ import annotations

import math
from numbers import Real
from typing import Literal, TypedDict

import numpy as np

PROTOCOL: Literal["region-partition/1.0.0"] = "region-partition/1.0.0"

RegionMissingReason = Literal["empty_target", "empty_reference", "background_not_confirmed"]
PartitionMissingReason = Literal[
    "empty_target", "empty_reference", "background_not_confirmed",
    "nonpositive_target_mean", "nonpositive_reference_mean", "ratio_out_of_range",
]


class RegionPartitionValues(TypedDict):
    area_px: int | None
    raw_mean: float | None
    raw_integrated: float | None
    corrected_mean: float | None
    corrected_integrated: float | None
    raw_missing_reason: RegionMissingReason | None
    corrected_missing_reason: RegionMissingReason | None


class PartitionValues(TypedDict):
    k: float | None
    log2_k: float | None
    missing_reasons: list[PartitionMissingReason]


class RegionPartitionRow(TypedDict):
    nucleus_id: int
    nucleus_area_px: int
    target: RegionPartitionValues
    reference: RegionPartitionValues
    raw: PartitionValues
    corrected: PartitionValues


class RegionPartitionResult(TypedDict):
    protocol: Literal["region-partition/1.0.0"]
    background: float | None
    rows: list[RegionPartitionRow]


def _validate_labels(labels: np.ndarray, name: str, *, membership: bool = False) -> None:
    # Match the mask-contract dimension, nonempty and uint32-range invariants
    # without importing detector/image dependencies into this numerical primitive.
    kinds = "bu" if membership else "u"
    if (not isinstance(labels, np.ndarray) or labels.ndim != 2 or not labels.size
            or labels.dtype.kind not in kinds or int(labels.max()) > np.iinfo(np.uint32).max):
        raise ValueError(f"region_partition_invalid_{name}")


def _region_values(area: int, integrated: float, background: float | None,
                   empty_reason: Literal["empty_target", "empty_reference"]) -> RegionPartitionValues:
    if not area:
        return {
            "area_px": None, "raw_mean": None, "raw_integrated": None,
            "corrected_mean": None, "corrected_integrated": None,
            "raw_missing_reason": empty_reason, "corrected_missing_reason": empty_reason,
        }
    mean = integrated / area
    corrected_mean = mean - background if background is not None else None
    corrected_integrated = integrated - area * background if background is not None else None
    if any(value is not None and not math.isfinite(value)
           for value in (integrated, mean, corrected_mean, corrected_integrated)):
        raise ValueError("region_partition_nonfinite_result")
    return {
        "area_px": area, "raw_mean": mean, "raw_integrated": integrated,
        "corrected_mean": corrected_mean, "corrected_integrated": corrected_integrated,
        "raw_missing_reason": None,
        "corrected_missing_reason": "background_not_confirmed" if background is None else None,
    }


def _partition_values(target: RegionPartitionValues, reference: RegionPartitionValues,
                      *, corrected: bool, background: float | None) -> PartitionValues:
    reasons: list[PartitionMissingReason] = []
    if target["area_px"] is None:
        reasons.append("empty_target")
    if reference["area_px"] is None:
        reasons.append("empty_reference")
    if corrected and background is None:
        reasons.append("background_not_confirmed")
    target_mean = target["corrected_mean"] if corrected else target["raw_mean"]
    reference_mean = reference["corrected_mean"] if corrected else reference["raw_mean"]
    if target_mean is not None and target_mean <= 0:
        reasons.append("nonpositive_target_mean")
    if reference_mean is not None and reference_mean <= 0:
        reasons.append("nonpositive_reference_mean")
    if reasons:
        return {"k": None, "log2_k": None, "missing_reasons": reasons}
    # The empty/background cases above exhaust all causes of absent means.
    assert target_mean is not None and reference_mean is not None
    ratio = target_mean / reference_mean
    if not math.isfinite(ratio) or ratio <= 0:
        return {"k": None, "log2_k": None, "missing_reasons": ["ratio_out_of_range"]}
    return {"k": ratio, "log2_k": math.log2(ratio), "missing_reasons": []}


def region_partition(nuclei: np.ndarray, target: np.ndarray, reference: np.ndarray,
                     image: np.ndarray, background: float | None = None) -> RegionPartitionResult:
    """Return one row per exact parent label, sorted by label, without mutating inputs.

    ``nuclei`` is a nonempty 2D unsigned integer label array. ``target`` and
    ``reference`` are same-shape bool memberships or unsigned label arrays, with
    nonzero values denoting included pixels. Integer labels must fit uint32.
    ``image`` is one same-shape, finite, real numeric original intensity plane;
    arithmetic uses float64. Every input pixel must be finite, including pixels
    outside the memberships. A finite real scalar ``background`` means the caller
    has confirmed it for this measurement channel; None leaves corrected values
    missing. Bool/complex/object intensities and bool backgrounds are rejected.

    Per region, mean = sum(original pixels) / pixel count; corrected mean = mean
    - background and corrected integrated = sum - count * background. Signed
    corrected values are preserved. Each value basis has K = target mean /
    reference mean and log2(K) only when both means are positive. Missing reasons
    identify both sides independently; corrected output never falls back to raw.
    Arithmetic that cannot produce finite region measurements is rejected;
    ratio overflow/underflow is missing with ``ratio_out_of_range``.
    """
    _validate_labels(nuclei, "nuclei")
    _validate_labels(target, "target", membership=True)
    _validate_labels(reference, "reference", membership=True)
    if (target.shape != nuclei.shape or reference.shape != nuclei.shape
            or not isinstance(image, np.ndarray) or image.shape != nuclei.shape):
        raise ValueError("region_partition_shape_mismatch")
    if image.dtype.kind not in "uif":
        raise ValueError("region_partition_invalid_image")
    if not np.isfinite(image).all():
        raise ValueError("region_partition_nonfinite_image")
    if background is not None:
        if isinstance(background, (bool, np.bool_)) or not isinstance(background, Real):
            raise ValueError("region_partition_invalid_background")
        try:
            background = float(background)
        except OverflowError:
            raise ValueError("region_partition_invalid_background") from None
        if not math.isfinite(background):
            raise ValueError("region_partition_invalid_background")

    nuclear_members = nuclei > 0
    target_members = target > 0
    reference_members = reference > 0
    if (target_members & ~nuclear_members).any():
        raise ValueError("region_partition_target_outside_nuclei")
    if (reference_members & ~nuclear_members).any():
        raise ValueError("region_partition_reference_outside_nuclei")
    if (target_members & reference_members).any():
        raise ValueError("region_partition_overlap")

    with np.errstate(over="ignore", invalid="ignore"):
        pixels = image.astype(np.float64)
    if not np.isfinite(pixels).all():
        raise ValueError("region_partition_nonfinite_result")
    parents, inverse, nuclear_areas = np.unique(
        nuclei[nuclear_members], return_inverse=True, return_counts=True,
    )
    # Compact indices avoid an allocation proportional to a sparse maximum label.
    nuclear_pixels = pixels[nuclear_members]
    areas = []
    sums = []
    for membership in (target_members, reference_members):
        selected = membership[nuclear_members]
        indices = inverse[selected]
        areas.append(np.bincount(indices, minlength=len(parents)))
        sums.append(np.bincount(indices, weights=nuclear_pixels[selected], minlength=len(parents)))
    rows: list[RegionPartitionRow] = []
    for index, parent in enumerate(parents):
        target_values = _region_values(int(areas[0][index]), float(sums[0][index]), background, "empty_target")
        reference_values = _region_values(
            int(areas[1][index]), float(sums[1][index]), background, "empty_reference",
        )
        rows.append({
            "nucleus_id": int(parent), "nucleus_area_px": int(nuclear_areas[index]),
            "target": target_values, "reference": reference_values,
            "raw": _partition_values(target_values, reference_values, corrected=False, background=background),
            "corrected": _partition_values(target_values, reference_values, corrected=True, background=background),
        })
    return {"protocol": PROTOCOL, "background": background, "rows": rows}

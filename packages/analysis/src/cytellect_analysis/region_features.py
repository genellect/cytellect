"""Per-region shape and pixel-signal features for statistics: region-features/1.0.0 (genellect/cytellect#257 E-1, E-3, E-7).

The values come from the two calculation modules and are bound to one saved region measurement:

- shape (``region_shape.py``, region-shape/1.0.0): solidity, axis ratio and eccentricity of each adopted region, with
  the protocol's minimum area. They read no stain.
- signal (``nuclear_signal.py``, nuclear-signal/1.0.0): the coefficient of variation of a region's pixels of one
  channel, raw (``cv``) or after subtracting the measurement's own background median (``cv_corrected``), and the
  fraction of a region's pixels at or above Otsu's threshold of all adopted regions' pixels of the field
  (``positive_area_fraction``).

Definitions are in docs/methods.md, "Region features 1.0.0". Nothing here changes pixels, and nothing is stored in
the measurement table: the worker recomputes the values from the saved labels and original channel and binds them
to the measured regions by region identity and pixel area. A region without a value keeps its reason; it is never
zero.
"""
from __future__ import annotations

import math
from typing import Any, Literal

import numpy as np

from .masks import validate_label_array
from .nuclear_signal import PROTOCOL as SIGNAL_PROTOCOL
from .nuclear_signal import nuclear_signal
from .region_shape import MINIMUM_AREA_PX, PERIMETER_ESTIMATOR, region_shapes
from .region_shape import PROTOCOL as SHAPE_PROTOCOL

PROTOCOL: Literal["region-features/1.0.0"] = "region-features/1.0.0"
SHAPE_METRICS = ("solidity", "axis_ratio", "eccentricity")
SIGNAL_METRICS = ("cv", "cv_corrected", "positive_area_fraction")
FEATURE_METRICS = (*SHAPE_METRICS, *SIGNAL_METRICS)
UNITS = {metric: "dimensionless" for metric in FEATURE_METRICS}
DEFINITIONS = {
    "solidity": f"region pixel area / convex-hull pixel area; regions below {MINIMUM_AREA_PX} px or touching the image "
                f"border have no value ({SHAPE_PROTOCOL})",
    "axis_ratio": f"major / minor axis of the ellipse with the region's second moments; regions below {MINIMUM_AREA_PX} px "
                  f"or touching the image border have no value ({SHAPE_PROTOCOL})",
    "eccentricity": f"sqrt(1 − λmin/λmax) of the region's pixel-centre covariance; regions below {MINIMUM_AREA_PX} px or "
                    f"touching the image border have no value ({SHAPE_PROTOCOL})",
    "cv": f"population SD / mean of the region's raw original pixels of the channel; no value for a non-positive mean "
          f"({SIGNAL_PROTOCOL})",
    "cv_corrected": f"population SD / mean of the region's pixels after subtracting the measurement's automatic background "
                    f"median of the channel; no value for a non-positive corrected mean or without an established "
                    f"background ({SIGNAL_PROTOCOL})",
    "positive_area_fraction": f"region pixels at or above Otsu's threshold of all adopted regions' raw pixels of the field "
                              f"/ region pixels; the threshold value is recorded per field ({SIGNAL_PROTOCOL})",
}
LABELS = {"solidity": ("Solidity", "ソリディティ"), "axis_ratio": ("Axis ratio", "長短軸比"),
          "eccentricity": ("Eccentricity", "離心率"), "cv": ("Pixel CV", "画素の変動係数（CV）"),
          "cv_corrected": ("Pixel CV, background-corrected", "画素の変動係数（CV、背景補正）"),
          "positive_area_fraction": ("Positive-area fraction", "陽性面積率")}
SAFE_ERROR_CODES = frozenset({"region_features_unavailable", "region_features_mismatch"})


def is_feature(metric: str) -> bool:
    return metric in FEATURE_METRICS


def reads_no_stain(metric: str) -> bool:
    """Area and shape read no channel; every other region metric reads the chosen channel."""
    return metric.startswith("area_") or metric in SHAPE_METRICS


def field_features(labels: np.ndarray, metric: str, *, image: np.ndarray | None = None, background: float | None = None,
                   background_reason: str | None = None, excluded: frozenset[int] = frozenset()) -> dict[str, Any]:
    """One field's values of ``metric`` for every region of ``labels``.

    ``image`` is the original channel (signal metrics only). ``cv_corrected`` takes the measurement's background median
    of that channel, or ``background_reason`` when it was not established (every region is then missing with it).
    ``excluded`` region IDs do not enter the field threshold of the positive-area fraction.
    """
    validate_label_array(labels)
    if metric not in FEATURE_METRICS:
        raise ValueError("region_features_unavailable")
    record: dict[str, Any] = {"protocol": PROTOCOL, "metric": metric}
    values: dict[int, dict[str, Any]] = {}
    if metric in SHAPE_METRICS:
        if image is not None:
            raise ValueError("region_features_unavailable")
        shapes = region_shapes(labels)
        record.update(source_protocol=SHAPE_PROTOCOL, minimum_area_px=shapes["minimum_area_px"],
                      perimeter_estimator=PERIMETER_ESTIMATOR)
        for shape in shapes["rows"]:
            values[shape["region_id"]] = {"area_px": shape["area_px"], "value": dict(shape)[metric],
                                          "missing_reason": shape["missing_reason"]}
    else:
        if image is None or image.shape != labels.shape:
            raise ValueError("region_features_unavailable")
        record["source_protocol"] = SIGNAL_PROTOCOL
        if metric == "cv_corrected" and background is None:
            if background_reason is None:
                raise ValueError("region_features_unavailable")
            record.update(values="corrected", background=None, background_missing_reason=background_reason)
            for rid in (int(value) for value in np.unique(labels) if value):
                values[rid] = {"area_px": int(np.count_nonzero(labels == rid)), "value": None,
                               "missing_reason": background_reason}
        else:
            corrected = metric == "cv_corrected"
            if corrected and (background is None or not math.isfinite(background)):
                raise ValueError("region_features_unavailable")
            signal = nuclear_signal(labels, image, values="corrected" if corrected else "raw",
                                    background=background if corrected else None,
                                    threshold={"method": "field_otsu", "value": None} if metric == "positive_area_fraction" else None,
                                    excluded=excluded)
            record.update(values=signal["values"], background=signal["background"])
            if metric == "positive_area_fraction":
                record["threshold"] = signal["threshold"]
            for measured in signal["rows"]:
                if metric == "positive_area_fraction":
                    value, reason = measured["positive_area_fraction"], measured["positive_missing_reason"]
                else:
                    value, reason = measured["cv"], measured["cv_missing_reason"]
                values[measured["nucleus_id"]] = {"area_px": measured["pixels"], "value": value, "missing_reason": reason}
    record["values"] = values
    return record


def bind(record: dict[str, Any], metric: str, areas: dict[int, int]) -> dict[int, dict[str, Any]]:
    """The record's values for exactly the measured regions (region ID -> pixel area), or an error."""
    if not isinstance(record, dict) or record.get("protocol") != PROTOCOL or record.get("metric") != metric:
        raise ValueError("region_features_mismatch")
    values = record.get("values") or {}
    if set(values) != set(areas) or any(values[rid]["area_px"] != area for rid, area in areas.items()):
        raise ValueError("region_features_mismatch")
    return values


def provenance(record: dict[str, Any]) -> dict[str, Any]:
    """What a result records about how a field's values were made (no per-region values)."""
    return {key: value for key, value in record.items() if key != "values"}


def methods_lines(fields: list[dict[str, Any]], metric: str) -> list[str]:
    """Methods sentences from the provenance the result saved per field (``source_fields[*].region_features``)."""
    records = [field.get("region_features") for field in fields]
    if not records or any(not isinstance(record, dict) or record.get("protocol") != PROTOCOL
                          or record.get("metric") != metric for record in records):
        raise ValueError("region_features_mismatch")
    lines = [f"The outcome is {DEFINITIONS[metric]}, region-features/1.0.0, recomputed from the saved original-coordinate "
             "labels and bound to the measured regions by region identity and pixel area. A region without a value keeps "
             "its recorded reason and was not replaced with zero."]
    if metric in SHAPE_METRICS:
        lines.append(f"Shape values are 2D pixel-grid values ({PERIMETER_ESTIMATOR} perimeter estimator recorded); the minimum "
                     f"area of {MINIMUM_AREA_PX} px was set from the digitisation error measured on public real images. "
                     "Regions without shape values still count in region numbers and areas. They are not volumes or "
                     "sphericities.")
    elif metric == "positive_area_fraction":
        thresholds = [(record or {}).get("threshold") or {} for record in records]
        values = [float(item["value"]) for item in thresholds if item.get("value") is not None]
        lines.append("The threshold was Otsu's threshold of all adopted, not excluded regions' raw pixels of each field, "
                     "applied within that field only; no threshold was taken from another image or publication. "
                     + (f"Field thresholds ranged {min(values):.6g}–{max(values):.6g} (raw values). " if values else "")
                     + "Exposure and overall brightness also change the fraction; groups are comparable only under the "
                     "same acquisition.")
    else:
        lines.append("The coefficient of variation uses the population standard deviation without smoothing, epsilon or "
                     "clipping; a non-positive mean has no value. It depends on staining, exposure and focus, and is "
                     "compared within the same acquisition only.")
    return lines


def selections_of(spec: dict[str, Any] | None) -> set[tuple[str, str | None]]:
    """(metric, channel ID) of every shape or pixel-signal region selection in a saved or requested spec."""
    keys: set[tuple[str, str | None]] = set()
    for name in ("selection", "x_selection", "y_selection"):
        selection = (spec or {}).get(name) if isinstance(spec, dict) else getattr(spec, name, None)
        if selection is None:
            continue
        get = selection.get if isinstance(selection, dict) else (lambda key, s=selection: getattr(s, key, None))
        metric = get("metric")
        if get("source") == "region" and isinstance(metric, str) and is_feature(metric):
            keys.add((metric, get("channel_id")))
    return keys


def _background(table: dict[str, Any], channel_id: str | None, metric: str) -> tuple[float | None, str | None]:
    if metric != "cv_corrected":
        return None, None
    provenance = next((item for item in table.get("channel_provenance", [])
                       if item["channel"]["channel_id"] == channel_id), None)
    record = (provenance or {}).get("background") or {}
    if record.get("background_source") != "automatic_candidate":
        raise ValueError("region_metric_not_measured")
    if record.get("status") == "established":
        return float(record["background_median"]), None
    return None, record.get("reason") or "background_not_established"


def compute_features(keys, report: dict[str, Any], labels_of, channel_of) -> dict | None:
    """(metric, channel ID) -> field -> record for ``keys``, from ``labels_of(field)`` (the adopted labels, already bound
    to the report's mask identity) and ``channel_of(field, channel)`` (the original channel array)."""
    keys = set(keys)
    if not keys:
        return None
    excluded: dict[str, set[int]] = {}
    for item in report.get("exclusions", []):
        if item.get("region_id") is not None:
            excluded.setdefault(item["field_id"], set()).add(int(item["region_id"]))
    features: dict = {key: {} for key in keys}
    for fid, table in sorted(report["field_tables"].items()):
        labels = np.asarray(labels_of(fid))
        for metric, channel_id in keys:
            image = None
            if metric not in SHAPE_METRICS:
                image = np.asarray(channel_of(fid, channel_id))
                if image.shape != labels.shape or image.dtype not in (np.uint8, np.uint16):
                    raise ValueError("region_features_mismatch")
            background, reason = _background(table, channel_id, metric)
            features[metric, channel_id][fid] = field_features(
                labels, metric, image=image, background=background, background_reason=reason,
                excluded=frozenset(excluded.get(fid, ())))
    return features

"""Per-nucleus shape and pixel-signal features: nuclear-features/1.0.0 (genellect/cytellect#257 E-1, E-3, E-7).

Definitions are in docs/methods.md, "Per-nucleus features 1.0.0". The values are computed from a field's saved
original-coordinate nucleus labels and, for a signal metric, its original channel; nothing here changes pixels and
nothing is stored in the measurement table. Statistics recompute the values and bind them to the measured nuclei by
region identity and pixel area. A nucleus without a value keeps its reason; it is never zero.

The features describe nuclei only (StarDist nuclear region sets). Nucleolar shape failed the public-image check
(docs/public-nucleolar-shape-validation.md) and is read through the per-nucleus nucleolar summaries instead.

- Shape (any measurement mode): solidity, axis ratio and eccentricity of each nucleus. A nucleus below
  ``MINIMUM_AREA_PX``, touching the image border, or with a zero minor axis has no value. Circularity 4πA/P²
  (4-direction Crofton perimeter) failed the same public decimation check on DS6a nuclei and is not a feature
  (docs/public-nuclear-circularity-validation.md).
- Signal (automatic-background measurement only), on the background-corrected pixels ``I - b`` of one channel, where
  ``b`` is the field's automatic background median of that channel:
  - pixel CV: population standard deviation / mean of the nucleus's corrected pixels, no smoothing, epsilon or
    clipping. The raw CV, corrected mean and corrected SD are kept beside it.
  - positive-area fraction: corrected pixels strictly above the acquisition date's Otsu threshold / nucleus pixels.
    The threshold is Otsu's threshold (the nucleus gates' arithmetic, 256 bins) of the corrected pixels of every
    measurable, not excluded nucleus of the revision's fields with that acquisition date. No threshold is taken
    from another image, date or publication.
  A nucleus has no signal value when the background was not established, it touches the image border, any of its
  pixels is saturated (at the acquisition limit when one was recorded, else at the storage maximum), its corrected
  mean is not positive, or its signal is below the background spread: corrected mean / (1.4826 x MAD of the
  background pixels) below ``MINIMUM_SIGNAL_TO_BACKGROUND`` (the Signal QC 1.0.0 ratio).
"""
from __future__ import annotations

import math
from collections import defaultdict
from typing import Any, Callable, Literal

import numpy as np

from .background_candidate import MAD_SCALE, automatic_background
from .gfp_gate import batch_otsu
from .masks import validate_label_array
from .regions import _array_hash

PROTOCOL: Literal["nuclear-features/1.0.0"] = "nuclear-features/1.0.0"
SHAPE_METRICS = ("solidity", "axis_ratio", "eccentricity")
SIGNAL_METRICS = ("cv_corrected", "positive_area_fraction")
FEATURE_METRICS = (*SHAPE_METRICS, *SIGNAL_METRICS)
# Set from digitisation error on public nucleus masks (#258, scripts/evaluate_shape_minimum_area.py on JUMP and DS6a).
MINIMUM_AREA_PX = 96
# The Signal QC 1.0.0 ratio below which a nucleus's signal is not distinguished from the background spread. Chosen on
# the tuning split of the public check (docs/public-nuclear-signal-validation.md, fixtures/public/nuclear-signal/tuning.json):
# no candidate separated the unlabelled 5-EU control, so the rule fell back to 1 (one background spread).
MINIMUM_SIGNAL_TO_BACKGROUND: float | None = 1.0
NUCLEAR_SOURCE = "stardist_nuclear"
UNITS = {metric: "dimensionless" for metric in FEATURE_METRICS}
LABELS = {"solidity": ("Nuclear solidity", "核のソリディティ"), "axis_ratio": ("Nuclear axis ratio", "核の長短軸比"),
          "eccentricity": ("Nuclear eccentricity", "核の離心率"),
          "cv_corrected": ("Nuclear pixel CV", "核の画素の変動係数"),
          "positive_area_fraction": ("Nuclear positive-area fraction", "核の陽性面積率")}
DEFINITIONS = {
    "solidity": f"nucleus pixel area / convex-hull pixel area; nuclei below {MINIMUM_AREA_PX} px or touching the image "
                f"border have no value ({PROTOCOL})",
    "axis_ratio": f"major / minor axis of the ellipse with the nucleus's second moments; nuclei below {MINIMUM_AREA_PX} px "
                  f"or touching the image border have no value ({PROTOCOL})",
    "eccentricity": f"sqrt(1 - lambda_min/lambda_max) of the nucleus's pixel-centre covariance; nuclei below "
                    f"{MINIMUM_AREA_PX} px or touching the image border have no value ({PROTOCOL})",
    "cv_corrected": "population SD / mean of the nucleus's background-corrected pixels of the channel (automatic "
                    f"background median subtracted, no smoothing) ({PROTOCOL})",
    "positive_area_fraction": "nucleus pixels whose background-corrected value is strictly above the acquisition "
                              "date's Otsu threshold / nucleus pixels; the threshold pools the corrected pixels of "
                              f"every measurable, not excluded nucleus of that date ({PROTOCOL})",
}
SAFE_ERROR_CODES = frozenset({"nuclear_features_unavailable", "nuclear_features_mismatch", "nuclear_features_nuclei_only",
                              "nuclear_features_unsupported_request"})
SignalReason = Literal["background_not_established", "touches_border", "saturated_pixels", "nonpositive_mean",
                       "background_spread_zero", "below_background_spread"]


def is_feature(metric: str) -> bool:
    return metric in FEATURE_METRICS


def reads_no_stain(metric: str) -> bool:
    """Area and shape read no channel; every other region metric reads the chosen channel."""
    return metric.startswith("area_") or metric in SHAPE_METRICS


def samples_space(metric: str) -> bool:
    """Values that change with the pixel grid: compared only with one confirmed spatial sampling."""
    return metric == "area_px" or "integrated" in metric or metric in FEATURE_METRICS


def _border_ids(labels: np.ndarray) -> set[int]:
    edge = np.concatenate((labels[0], labels[-1], labels[:, 0], labels[:, -1]))
    return {int(value) for value in np.unique(edge) if value}


def nuclear_shapes(labels: np.ndarray, *, minimum_area_px: int = MINIMUM_AREA_PX) -> dict[int, dict[str, Any]]:
    """Solidity, axis ratio and eccentricity of every nucleus label (ascending), with the reason a nucleus has none.

    ``minimum_area_px`` (>= 1) other than the protocol's is for evaluating the digitisation error only.
    """
    validate_label_array(labels)
    if isinstance(minimum_area_px, bool) or not isinstance(minimum_area_px, int) or minimum_area_px < 1:
        raise ValueError("nuclear_features_minimum_area_invalid")
    from skimage.measure import regionprops

    touching = _border_ids(labels)
    rows: dict[int, dict[str, Any]] = {}
    # regionprops makes one slot per label value: compact sparse saved IDs first.
    present = np.unique(labels[labels > 0])
    compact = np.zeros(labels.shape, np.int64)
    compact[labels > 0] = np.searchsorted(present, labels[labels > 0]) + 1
    for region in regionprops(compact):
        rid, area = int(present[region.label - 1]), int(region.area)
        row: dict[str, Any] = {"area_px": area, "solidity": None, "axis_ratio": None, "eccentricity": None,
                               "missing_reason": None}
        if rid in touching:
            row["missing_reason"] = "touches_border"
        elif area < minimum_area_px:
            row["missing_reason"] = "below_minimum_area"
        else:
            major, minor = float(region.axis_major_length), float(region.axis_minor_length)
            if not minor > 0 or not math.isfinite(major):
                row["missing_reason"] = "degenerate"
            else:
                row.update(solidity=area / float(region.area_convex), axis_ratio=major / minor,
                           eccentricity=float(region.eccentricity))
        rows[rid] = row
    return rows


def background_spread(image: np.ndarray, labels: np.ndarray, record: dict[str, Any] | None = None
                      ) -> tuple[float | None, float | None, str | None]:
    """(median, 1.4826 x MAD, reason) of the automatic background pixels of one channel.

    The background pixels are recomputed with the measurement's own algorithm (every labelled nucleus excluded). With
    the measurement's saved provenance ``record``, the recomputed mask and median must be the saved ones.
    """
    if record is not None:
        if record.get("background_source") != "automatic_candidate":
            raise ValueError("nuclear_features_unavailable")
        if record.get("status") != "established":
            return None, None, "background_not_established"
        if record.get("additional_exclusion"):
            # A compartment recipe's extra exclusion is not part of a nuclear set; it cannot be recomputed here.
            raise ValueError("nuclear_features_unavailable")
    mask, _ = automatic_background(image, labels)
    if mask is None:
        if record is not None:
            raise ValueError("nuclear_features_mismatch")
        return None, None, "background_not_established"
    pixels = image[mask].astype(np.float64)
    median = float(np.median(pixels))
    if record is not None and (_array_hash(mask, "|u1") != record.get("background_mask_sha256")
                               or median != record.get("background_median")):
        raise ValueError("nuclear_features_mismatch")
    return median, MAD_SCALE * float(np.median(np.abs(pixels - median))), None


def nuclear_signal(labels: np.ndarray, image: np.ndarray, *, background: float | None, spread: float | None,
                   background_reason: str | None = None, saturation_value: int | None = None,
                   minimum_ratio: float | None = None, keep_pixels: bool = False) -> dict[int, dict[str, Any]]:
    """Corrected pixel statistics of every nucleus label, and the reason a nucleus is not measurable.

    ``background`` and ``spread`` come from :func:`background_spread`; without a background every nucleus keeps
    ``background_reason``. ``minimum_ratio`` defaults to the protocol's MINIMUM_SIGNAL_TO_BACKGROUND. With
    ``keep_pixels`` each row also holds the nucleus's raw pixels (``pixels``) for a date's pooled threshold.
    """
    validate_label_array(labels)
    if image.shape != labels.shape or image.ndim != 2 or image.dtype not in (np.uint8, np.uint16):
        raise ValueError("nuclear_features_unavailable")
    ratio_floor = MINIMUM_SIGNAL_TO_BACKGROUND if minimum_ratio is None else minimum_ratio
    if ratio_floor is None or not math.isfinite(ratio_floor) or ratio_floor < 0:
        raise ValueError("nuclear_features_unavailable")
    if (background is None) != (spread is None) or (background is None and background_reason is None):
        raise ValueError("nuclear_features_unavailable")
    limit = int(np.iinfo(image.dtype).max) if saturation_value is None else int(saturation_value)
    touching = _border_ids(labels)
    from scipy import ndimage as ndi

    rows: dict[int, dict[str, Any]] = {}
    # Compact the labels first: find_objects makes one slot per label value, and saved IDs can be large and sparse.
    present = np.unique(labels[labels > 0])
    compact = np.zeros(labels.shape, np.int64)
    inside = labels > 0
    compact[inside] = np.searchsorted(present, labels[inside]) + 1
    for index, window in enumerate(ndi.find_objects(compact)):
        if window is None:
            continue
        rid = int(present[index])
        original = image[window][compact[window] == index + 1]
        raw = original.astype(np.float64)
        mean_raw, sd_raw = float(raw.mean()), float(raw.std(ddof=0))
        row: dict[str, Any] = {"area_px": int(raw.size), "mean_raw": mean_raw, "sd_raw": sd_raw,
                               "cv_raw": sd_raw / mean_raw if mean_raw > 0 else None, "mean_corrected": None,
                               "sd_corrected": None, "cv_corrected": None, "signal_to_background": None,
                               "missing_reason": None}
        if keep_pixels:
            row["pixels"] = original
        if background is None or spread is None:
            row["missing_reason"] = background_reason
        elif rid in touching:
            row["missing_reason"] = "touches_border"
        elif bool((raw >= limit).any()):
            row["missing_reason"] = "saturated_pixels"
        else:
            corrected = raw - background
            mean, sd = float(corrected.mean()), float(corrected.std(ddof=0))
            row.update(mean_corrected=mean, sd_corrected=sd)
            if not mean > 0:
                row["missing_reason"] = "nonpositive_mean"
            elif not spread > 0:
                row["missing_reason"] = "background_spread_zero"
            else:
                ratio = mean / spread
                row["signal_to_background"] = ratio
                if ratio < ratio_floor:
                    row["missing_reason"] = "below_background_spread"
                else:
                    row["cv_corrected"] = sd / mean
        rows[rid] = row
    return rows


def date_threshold(pools: list[np.ndarray], date: str | None) -> dict[str, Any]:
    """Otsu's threshold of one acquisition date's pooled corrected pixels, or the reason there is none."""
    values = np.concatenate(pools) if pools else np.zeros(0)
    reason = None
    if date is None:
        reason = "acquisition_date_required"
    elif values.size < 2:
        reason = "too_few_nuclei"
    elif float(values.min()) == float(values.max()):
        reason = "uniform_distribution"
    return {"acquisition_date": date, "value": None if reason else batch_otsu(values), "pixels": int(values.size),
            "nuclei": len(pools), "missing_reason": reason, "pixel_basis": "background-corrected", "histogram_bins": 256}


def positive_fraction(corrected: np.ndarray, threshold: float) -> float:
    """Corrected nucleus pixels strictly above the date's threshold / nucleus pixels (equality is not positive)."""
    return int(np.count_nonzero(corrected > threshold)) / int(corrected.size)


def _date(snapshot: dict[str, Any], fid: str) -> str | None:
    value = (snapshot.get(fid) or {}).get("metadata", {}).get("acquisition_date")
    return value if isinstance(value, str) and value.strip() else None


def _channel_record(table: dict[str, Any], channel_id: str) -> dict[str, Any]:
    record = next((item for item in table.get("channel_provenance", [])
                   if item["channel"]["channel_id"] == channel_id), None)
    if record is None:
        raise ValueError("nuclear_features_unavailable")
    return record


def compute_features(keys, report: dict[str, Any], field_snapshot: dict[str, Any],
                     labels_of: Callable[[str], np.ndarray], channel_of: Callable[[str, str], np.ndarray]) -> dict | None:
    """(metric, channel ID) -> field -> record for ``keys``, from ``labels_of(field)`` (the adopted nucleus labels,
    bound to the report's mask identity) and ``channel_of(field, channel)`` (the original channel)."""
    keys = set(keys)
    if not keys:
        return None
    tables = report["field_tables"]
    for table in tables.values():
        region_set = table.get("region_set") or {}
        if region_set.get("source") != NUCLEAR_SOURCE:
            raise ValueError("nuclear_features_nuclei_only")
    excluded: dict[str, set[int]] = defaultdict(set)
    whole: set[str] = set()
    for item in report.get("exclusions", []):
        if item.get("region_id") is None:
            whole.add(item["field_id"])
        else:
            excluded[item["field_id"]].add(int(item["region_id"]))
    labels = {fid: np.asarray(labels_of(fid)) for fid in sorted(tables)}
    features: dict = {key: {} for key in keys}
    for metric, channel_id in sorted(keys, key=lambda key: (key[0], key[1] or "")):
        if metric in SHAPE_METRICS:
            for fid, field_labels in labels.items():
                shapes = nuclear_shapes(field_labels)
                features[metric, channel_id][fid] = {
                    "protocol": PROTOCOL, "metric": metric, "minimum_area_px": MINIMUM_AREA_PX,
                    "values": {rid: {"area_px": row["area_px"], "value": row[metric], "missing_reason": row["missing_reason"]}
                               for rid, row in shapes.items()}}
            continue
        if metric not in SIGNAL_METRICS or channel_id is None:
            raise ValueError("nuclear_features_unavailable")
        signals, backgrounds = {}, {}
        for fid, field_labels in labels.items():
            image = np.asarray(channel_of(fid, channel_id))
            if image.shape != field_labels.shape or image.dtype not in (np.uint8, np.uint16):
                raise ValueError("nuclear_features_mismatch")
            provenance_record = _channel_record(tables[fid], channel_id)
            median, spread, reason = background_spread(image, field_labels, provenance_record["background"])
            limit = provenance_record["channel"].get("acquisition_saturation_value")
            signals[fid] = nuclear_signal(field_labels, image, background=median, spread=spread,
                                          background_reason=reason, saturation_value=limit,
                                          keep_pixels=metric == "positive_area_fraction")
            backgrounds[fid] = (median, spread)
        thresholds: dict[str | None, dict[str, Any]] = {}
        if metric == "positive_area_fraction":
            pools: dict[str | None, list[np.ndarray]] = defaultdict(list)
            for fid, rows in signals.items():
                date = _date(field_snapshot, fid)
                pools.setdefault(date, [])
                if fid in whole or backgrounds[fid][0] is None:
                    continue
                for rid, row in rows.items():
                    if row["missing_reason"] is None and rid not in excluded[fid]:
                        pools[date].append(row["pixels"].astype(np.float64) - backgrounds[fid][0])
            thresholds = {date: date_threshold(pool, date) for date, pool in pools.items()}
        for fid, rows in signals.items():
            median, spread = backgrounds[fid]
            record: dict[str, Any] = {"protocol": PROTOCOL, "metric": metric, "channel_id": channel_id,
                                      "pixel_basis": "background-corrected", "background_median": median,
                                      "background_spread": spread,
                                      "minimum_signal_to_background": MINIMUM_SIGNAL_TO_BACKGROUND}
            values: dict[int, dict[str, Any]] = {}
            threshold = thresholds.get(_date(field_snapshot, fid)) if metric == "positive_area_fraction" else None
            if threshold is not None:
                record["threshold"] = threshold
            for rid, row in rows.items():
                value, reason = row["cv_corrected"], row["missing_reason"]
                entry: dict[str, Any] = {"area_px": row["area_px"]}
                if metric == "positive_area_fraction":
                    value = None
                    if reason is None and threshold is not None:
                        reason = threshold["missing_reason"]
                        if threshold["value"] is not None:
                            value = positive_fraction(row["pixels"].astype(np.float64) - median, threshold["value"])
                else:
                    entry.update(mean_corrected=row["mean_corrected"], sd_corrected=row["sd_corrected"],
                                 cv_raw=row["cv_raw"])
                entry.update(value=value, missing_reason=None if value is not None else reason)
                values[rid] = entry
            record["values"] = values
            features[metric, channel_id][fid] = record
    return features


def bind(record: dict[str, Any], metric: str, areas: dict[int, int]) -> dict[int, dict[str, Any]]:
    """The record's values for exactly the measured nuclei (region ID -> pixel area), or an error."""
    if not isinstance(record, dict) or record.get("protocol") != PROTOCOL or record.get("metric") != metric:
        raise ValueError("nuclear_features_mismatch")
    values = record.get("values") or {}
    if set(values) != set(areas) or any(values[rid]["area_px"] != area for rid, area in areas.items()):
        raise ValueError("nuclear_features_mismatch")
    return values


def provenance(record: dict[str, Any]) -> dict[str, Any]:
    """What a result records about how a field's values were made (no per-nucleus values)."""
    kept = {key: value for key, value in record.items() if key != "values"}
    counts: dict[str, int] = defaultdict(int)
    for value in (record.get("values") or {}).values():
        counts[value["missing_reason"] or "measured"] += 1
    kept["nuclei_by_status"] = dict(sorted(counts.items()))
    return kept


def selections_of(spec: dict[str, Any] | None) -> set[tuple[str, str | None]]:
    """(metric, channel ID) of every nuclear feature selection in a saved or requested spec."""
    keys: set[tuple[str, str | None]] = set()
    for name in ("selection", "x_selection", "y_selection"):
        selection = (spec or {}).get(name) if isinstance(spec, dict) else getattr(spec, name, None)
        if selection is None:
            continue
        get = selection.get if isinstance(selection, dict) else (lambda key, s=selection: getattr(s, key, None))
        metric = get("metric")
        if get("source") == "region" and isinstance(metric, str) and is_feature(metric):
            keys.add((metric, None if metric in SHAPE_METRICS else get("channel_id")))
    return keys


def methods_lines(fields: list[dict[str, Any]], metric: str) -> list[str]:
    """Methods sentences from the provenance a result saved per field (``source_fields[*].nuclear_features``)."""
    records = [field.get("nuclear_features") for field in fields]
    if not records or any(not isinstance(record, dict) or record.get("protocol") != PROTOCOL
                          or record.get("metric") != metric for record in records):
        raise ValueError("nuclear_features_mismatch")
    lines = [f"The outcome is the {DEFINITIONS[metric]}, recomputed from the saved original-coordinate nucleus labels "
             "and bound to the measured nuclei by region identity and pixel area. A nucleus without a value keeps its "
             "recorded reason and was not replaced with zero."]
    if metric in SHAPE_METRICS:
        lines.append(f"Shape values are 2D pixel-grid values of nuclei; the minimum area of {MINIMUM_AREA_PX} px was set "
                     "from the digitisation error of public nucleus masks. Nuclei without shape values still count in "
                     "nucleus numbers and areas. They are not volumes or sphericities.")
        return lines
    saved = [record for record in records if isinstance(record, dict)]
    ratios = {record.get("minimum_signal_to_background") for record in saved}
    ratio = next(iter(ratios)) if len(ratios) == 1 else None
    lines.append("The background was the field's automatic background candidate median of the channel. A nucleus had "
                 "no value when the background was not established, it touched the image border, any pixel was "
                 "saturated, its corrected mean was not positive, or its corrected mean was below "
                 + (f"{ratio:g} times " if ratio is not None else "the recorded multiple of ")
                 + "the background spread (1.4826 x MAD of the background pixels; Signal QC 1.0.0 ratio).")
    if metric == "positive_area_fraction":
        dates = {}
        for record in saved:
            threshold = record.get("threshold") or {}
            dates[threshold.get("acquisition_date")] = threshold
        values = [item["value"] for item in dates.values() if item.get("value") is not None]
        lines.append("The threshold was Otsu's threshold (256 bins) of the corrected pixels of every measurable, not "
                     "excluded nucleus of the same acquisition date, applied within that date only; no threshold was "
                     "taken from another image, date or publication. "
                     + (f"Date thresholds ranged {min(values):.6g} to {max(values):.6g} (corrected values). " if values else "")
                     + "Exposure and staining also change the fraction; groups are comparable only within the same "
                     "acquisition conditions and runs.")
    else:
        lines.append("The coefficient of variation uses the population standard deviation without smoothing, epsilon "
                     "or clipping. It depends on staining, exposure, focus and pixel size, and is compared within the "
                     "same acquisition conditions and runs only.")
    return lines

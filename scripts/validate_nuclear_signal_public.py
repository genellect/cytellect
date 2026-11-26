"""Per-nucleus pixel-signal metrics on public real images (genellect/cytellect#257 E-7, plan PR 6).

Checks whether the per-nucleus pixel coefficient of variation (CV) and positive-area fraction of the shared
implementation (``cytellect_analysis.nuclear_features``, nuclear-features/1.0.0) can be offered, on the DS6b fields
registered by ``scripts/validate_nucleolar_shape_public.py`` (fixtures/public/nucleolar-shape/manifest.json).
Results are in docs/public-nuclear-signal-validation.md.

Commands (originals and work data stay outside the checkout):

    uv run python -I scripts/validate_nuclear_signal_public.py detect --data-dir DIR --work DIR --fiji FIJI [--workers 3]
    uv run python -I scripts/validate_nuclear_signal_public.py tune --data-dir DIR --work DIR [--workers 3]
    uv run python -I scripts/validate_nuclear_signal_public.py evaluate --data-dir DIR --work DIR [--workers 3]

``detect`` runs the product's nuclear detection (Fiji StarDist 2D with the automatic scale) on every registered DS6b
field, at the original resolution and again after 2 x 2 binning, and keeps the label images. It computes no metric.
``tune`` reads the tuning split only and writes fixtures/public/nuclear-signal/tuning.json. ``evaluate`` refuses to
run until that file is committed unchanged, then reads the evaluation split and writes evaluation.json.

Rules, fixed before any metric value was computed (the commit that adds this text):

1. Material. DS6b, all 360 fields: 30 min and 2 h = tuning, 4 h = evaluation (decision 4, as the nucleolar check).
   Channels NucBlue, NPM1, FBL and 5-EU. Nuclei are the product's StarDist detection; nothing is tuned for this check.
   Fields where the detection failed (#272 found 11 tuning fields with a field-sized "nucleus") are kept and counted.
   ``tune`` and ``evaluate`` refuse to run unless every field of the split has a detection; a field that then fails
   to measure is recorded with its reason, and the verdict fails when a compared condition has no field.
2. Unit of the verdict: metric x channel, for the pixel CV (cv_corrected) and the positive-area fraction.
3. Runs. Each time point is analysed as one revision of the product: the positive-area threshold pools that time
   point's fields (every condition), as Otsu per acquisition date pools one date. The control is UntreatedWithEU.
4. Values come from the shared implementation (background_spread, nuclear_signal, date_threshold, positive_fraction).
   A nucleus is measurable for a metric when that metric has a finite value under the product's rules.
5. Signal-to-background floor R (the Signal QC 1.0.0 ratio, MINIMUM_SIGNAL_TO_BACKGROUND), chosen on tuning only,
   on the 2 h time point (at 30 min the labelled control has taken up little 5-EU): candidates 1, 2, 3, 5, 10. On the
   5-EU channel, F_noEU(R) is the fraction of UntreatedNoEU nuclei (the unlabelled negative control) whose ratio is
   below R, and F_withEU(R) the same for UntreatedWithEU, among nuclei that reach the ratio check. R is the smallest
   candidate with F_noEU >= 0.95 and F_withEU <= 0.20. If none qualifies, the ratio does not separate the unlabelled
   control, R = 1 (the corrected mean below one background spread) and the report says the floor then removes
   little beyond a signal at background level.
6. Measurability (decision 4 form), evaluation split, per metric x channel: the measurable fraction of all detected
   nuclei (border-touching nuclei included in the denominator) is >= 0.80 in every condition and the largest minus
   smallest condition fraction is <= 0.10 (10 points). The fraction among nuclei not touching the border is reported
   only. For 5-EU, UntreatedNoEU (no label) is not one of the compared conditions and is reported only.
7. 2 x 2 binning, paired on the same nucleus: the image is 2 x 2 averaged and the nucleus labels are decimated
   (every second pixel), and the metric is recomputed on the binned field with the product's rules (its own
   background, spread, floor and time-point threshold). The re-detected binned nuclei are reported as facts only.
   a. Ranking: Spearman rho of native and binned values over the nuclei measurable at both, per field with at least
      10 such nuclei; the condition statistic is the median rho over its fields. From tuning: rho_min is the smallest
      condition statistic of both time points, and rho_crit = min(rho_min - 0.05, 0.90). If rho_min - 0.05 < 0.80 the
      metric x channel is not offered. Evaluation passes when every compared condition has a statistic (at least one
      field with 10 paired nuclei) and every statistic is >= rho_crit.
   b. Condition differences: per condition the mean of field medians (native and binned), the difference from the
      control, and its standard error sqrt(s1^2/n1 + s2^2/n2) over field medians. A contrast is evaluated when
      |difference_native| > 2 x SE_native (the dead band). For an evaluated contrast the binned difference has the
      same sign and its ratio q = difference_binned / difference_native lies in [q_lo, q_hi]. From tuning: at least 3
      contrasts are evaluated, every one keeps its sign, and the tuning q range lies within [0.5, 2.0]; otherwise the
      metric x channel is not offered. q_lo = min(min q - 0.1, 0.75) and q_hi = max(max q + 0.1, 1.25), so the band
      always holds +-25 % of the native difference. Evaluation passes when at least one contrast is evaluated and
      every evaluated contrast keeps its sign with q in [q_lo, q_hi].
8. A metric is offered in the product only when it passes for every channel (the product cannot tell stains apart).
   Paper-direction effects are not a pass condition. Failures are reported with their numbers.
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import subprocess
import sys
import time
import traceback
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import validate_nucleolar_shape_public as registered  # noqa: E402

PROTOCOL = "nuclear-signal-validation/1.0.0"
DATASET = "ds6b"
OUTPUT = ROOT / "fixtures/public/nuclear-signal"
TUNING = OUTPUT / "tuning.json"
EVALUATION = OUTPUT / "evaluation.json"
CHANNELS = ("nuclear", "npm1", "fbl", "eu5")
METRICS = ("cv_corrected", "positive_area_fraction")
CONTROL = "UntreatedWithEU"
UNLABELLED = "UntreatedNoEU"
RATIO_CANDIDATES = (1.0, 2.0, 3.0, 5.0, 10.0)
NOEU_FLAGGED = 0.95
WITHEU_FLAGGED = 0.20
RATIO_FALLBACK = 1.0
RATE_MINIMUM = 0.80
RATE_SPREAD = 0.10
MIN_FIELD_NUCLEI = 10
RHO_MARGIN = 0.05
RHO_FLOOR = 0.80
RHO_CEILING = 0.90
MIN_TUNING_CONTRASTS = 3
Q_BAND = (0.75, 1.25)
RATIO_TIMEPOINT = "2hrs"
DEAD_BAND_SE = 2.0
Q_MARGIN = 0.1
Q_RANGE = (0.5, 2.0)
RESOLUTIONS = ("native", "binned", "redetected")


# --------------------------------------------------------------------------------------------------------------
# Detection
# --------------------------------------------------------------------------------------------------------------
def detect_field(task: dict[str, Any]) -> dict[str, Any]:
    import tifffile

    entry, work, fiji = task["entry"], Path(task["work"]), task["fiji"]
    stem = entry["name"].removesuffix(".tif")
    target = work / "labels"
    target.mkdir(parents=True, exist_ok=True)
    info_path, arrays_path = target / f"{stem}.json", target / f"{stem}.npz"
    settings = registered.detectors_sha256(task["detectors"])
    if info_path.is_file() and arrays_path.is_file():
        previous = json.loads(info_path.read_text(encoding="utf-8"))
        if (previous.get("protocol") == PROTOCOL and previous.get("sha256") == entry["sha256"]
                and previous.get("detectors_sha256") == settings and previous.get("status") == "ok"):
            return previous
    info: dict[str, Any] = {"protocol": PROTOCOL, "name": entry["name"], "sha256": entry["sha256"],
                            "detectors_sha256": settings, "split": entry["split"], "group": entry["group"],
                            "condition": entry["condition"], "status": "failed", "stage": "verify"}
    started = time.perf_counter()
    try:
        path = Path(task["data_dir"]) / DATASET / entry["name"]
        data = path.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("public_original_hash_mismatch")
        del data
        registered.check_ome(DATASET, registered.ome_record(path))
        stack = tifffile.imread(path)
        nuclear = np.ascontiguousarray(stack[0])
        scratch = work / "tmp" / stem
        info["stage"] = "nuclei"
        native, scale = registered.detect_nuclei_auto(nuclear, task["detectors"]["nuclear"], scratch / "n1", fiji)
        info["stage"] = "nuclei-binned"
        binned, scale2 = registered.detect_nuclei_auto(registered.bin2(nuclear), task["detectors"]["nuclear"],
                                                       scratch / "n2", fiji)
        np.savez_compressed(arrays_path, native=native.astype(np.uint32), binned=binned.astype(np.uint32))
        info.update(status="ok", stage="done", native={**scale, "nuclei": int(len(np.unique(native)) - 1)},
                    binned={**scale2, "nuclei": int(len(np.unique(binned)) - 1)})
    except Exception as exc:  # recorded with its reason, never dropped
        info["error"] = registered.redact(f"{type(exc).__name__}: {exc}")
        info["traceback"] = registered.redact(traceback.format_exc(limit=3))
    info["seconds"] = round(time.perf_counter() - started, 1)
    info_path.write_text(json.dumps(info, indent=1) + "\n", encoding="utf-8")
    return info


def detect(data_dir: Path, work: Path, fiji: str, workers: int) -> None:
    data_dir, work = registered.outside_checkout(data_dir), registered.outside_checkout(work)
    manifest = json.loads(registered.MANIFEST.read_text(encoding="utf-8"))
    detectors = registered.product_detectors()
    work.mkdir(parents=True, exist_ok=True)
    (work / "detectors.json").write_text(json.dumps(detectors, indent=1) + "\n", encoding="utf-8")
    tasks = [{"entry": entry, "work": str(work), "fiji": fiji, "data_dir": str(data_dir), "detectors": detectors}
             for entry in manifest["datasets"][DATASET]["files"]]
    context = multiprocessing.get_context("spawn")
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        for done, info in enumerate(pool.map(detect_field, tasks), 1):
            print(f"[{done}/{len(tasks)}] {info['name']} {info['status']} {info.get('seconds')}s", flush=True)


# --------------------------------------------------------------------------------------------------------------
# Per-field measurement with the shared implementation (no floor: the floor is applied per candidate)
# --------------------------------------------------------------------------------------------------------------
def _signal(labels: np.ndarray, image: np.ndarray) -> dict[str, Any]:
    from cytellect_analysis.nuclear_features import _border_ids, background_spread, nuclear_signal

    median, spread, reason = background_spread(image, labels)
    rows = nuclear_signal(labels, image, background=median, spread=spread, background_reason=reason,
                          minimum_ratio=0.0, keep_pixels=True)
    ids = np.asarray(sorted(rows), np.int64)

    def column(key, dtype=np.float64):
        return np.asarray([np.nan if rows[i][key] is None else rows[i][key] for i in ids], dtype)

    return {"ids": ids, "background": median, "spread": spread, "background_reason": reason,
            "border": np.isin(ids, sorted(_border_ids(labels))),
            "reason": [rows[i]["missing_reason"] for i in ids], "ratio": column("signal_to_background"),
            "cv": column("cv_corrected"), "pixels": [rows[i]["pixels"] for i in ids]}


def measure_field(task: dict[str, Any]) -> dict[str, Any]:
    import tifffile

    entry = task["entry"]
    stem = entry["name"].removesuffix(".tif")
    out: dict[str, Any] = {"name": entry["name"], "group": entry["group"], "condition": entry["condition"],
                           "split": entry["split"], "status": "failed"}
    try:
        if entry["split"] != task["split"]:
            raise ValueError("split_mismatch")
        path = Path(task["data_dir"]) / DATASET / entry["name"]
        data = path.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("public_original_hash_mismatch")
        del data
        info = json.loads((Path(task["work"]) / "labels" / f"{stem}.json").read_text(encoding="utf-8"))
        if info.get("status") != "ok" or info.get("sha256") != entry["sha256"]:
            raise ValueError("detection_missing")
        labels = np.load(Path(task["work"]) / "labels" / f"{stem}.npz")
        native, redetected = labels["native"], labels["binned"]
        decimated = registered.decimate2(native)
        fine_ids, coarse_ids, _ = registered.match(registered.decimate2(native), redetected, 1)
        stack = tifffile.imread(path)
        spec = registered.DATASETS[DATASET]
        planes = {channel["id"]: np.ascontiguousarray(stack[channel["index"]]) for channel in spec["channels"]}
        out["nuclei"] = int(len(np.unique(native)) - 1)
        out["detection"] = {"diameter_px": info["native"].get("diameter_px"), "nuclei_redetected": int(len(np.unique(redetected)) - 1),
                            "redetected_matched": int(len(fine_ids))}
        out["redetected_match"] = {"native": fine_ids, "redetected": coarse_ids}
        for channel in CHANNELS:
            binned = registered.bin2(planes[channel])
            out[channel] = {"native": _signal(native, planes[channel]), "binned": _signal(decimated, binned),
                            "redetected": _signal(redetected, binned)}
        out["status"] = "ok"
    except Exception as exc:  # recorded with its reason, never dropped
        out["error"] = registered.redact(f"{type(exc).__name__}: {exc}")
    return out


def measure_split(data_dir: Path, work: Path, split: str, workers: int) -> list[dict[str, Any]]:
    data_dir, work = registered.outside_checkout(data_dir), registered.outside_checkout(work)
    manifest = json.loads(registered.MANIFEST.read_text(encoding="utf-8"))
    entries = [entry for entry in manifest["datasets"][DATASET]["files"] if entry["split"] == split]
    missing = []
    for entry in entries:
        info = work / "labels" / f"{entry['name'].removesuffix('.tif')}.json"
        record = json.loads(info.read_text(encoding="utf-8")) if info.is_file() else {}
        if record.get("status") != "ok" or record.get("sha256") != entry["sha256"]:
            missing.append(entry["name"])
    if missing:
        raise SystemExit(f"{split}_refused: {len(missing)} fields have no detection")
    tasks = [{"entry": entry, "work": str(work), "data_dir": str(data_dir), "split": split} for entry in entries]
    context = multiprocessing.get_context("spawn")
    fields = []
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        for done, field in enumerate(pool.map(measure_field, tasks), 1):
            fields.append(field)
            if done % 20 == 0 or done == len(tasks):
                print(f"[{split} {done}/{len(tasks)}]", flush=True)
    return fields


# --------------------------------------------------------------------------------------------------------------
# Values under one floor R: measurability, CV and the time point's positive-area threshold
# --------------------------------------------------------------------------------------------------------------
def values_at(fields: list[dict[str, Any]], channel: str, resolution: str, ratio: float) -> dict[str, Any]:
    """Per field: (ids, measurable mask, cv, positive-area fraction) under floor ``ratio``, with the product's rules."""
    from cytellect_analysis.nuclear_features import date_threshold, positive_fraction

    pools: dict[str, list[np.ndarray]] = defaultdict(list)
    states = []
    for field in fields:
        if field["status"] != "ok":
            continue
        signal = field[channel][resolution]
        reasons = [reason if reason is not None else ("below_background_spread" if not signal["ratio"][index] >= ratio
                                                      else None) for index, reason in enumerate(signal["reason"])]
        measurable = np.asarray([reason is None for reason in reasons], bool)
        for index in np.flatnonzero(measurable):
            pools[field["group"]].append(signal["pixels"][index].astype(np.float64) - signal["background"])
        states.append((field, signal, reasons, measurable))
    thresholds = {group: date_threshold(pool, group) for group, pool in pools.items()}
    out = {}
    for field, signal, reasons, measurable in states:
        threshold = thresholds.get(field["group"], {"value": None})
        fraction = np.full(len(signal["ids"]), np.nan)
        if threshold["value"] is not None:
            for index in np.flatnonzero(measurable):
                fraction[index] = positive_fraction(signal["pixels"][index].astype(np.float64) - signal["background"],
                                                    threshold["value"])
        cv = np.where(measurable, signal["cv"], np.nan)
        # A measurable nucleus without a time-point threshold has no positive-area fraction.
        fraction_reasons = [reason if reason is not None or np.isfinite(fraction[index])
                            else threshold.get("missing_reason") or "threshold_not_established"
                            for index, reason in enumerate(reasons)]
        out[field["name"]] = {"ids": signal["ids"], "reasons": {"cv_corrected": reasons,
                                                                "positive_area_fraction": fraction_reasons},
                              "border": signal["border"],
                              "cv_corrected": cv, "positive_area_fraction": fraction}
    return {"fields": out, "thresholds": {group: {key: value for key, value in item.items()}
                                          for group, item in thresholds.items()}}


# --------------------------------------------------------------------------------------------------------------
# Statistics
# --------------------------------------------------------------------------------------------------------------
def _spearman(a: np.ndarray, b: np.ndarray) -> float | None:
    from scipy.stats import spearmanr

    if len(a) < MIN_FIELD_NUCLEI or np.all(a == a[0]) or np.all(b == b[0]):
        return None
    return float(spearmanr(a, b).statistic)


def compared_conditions(conditions: list[str], channel: str) -> list[str]:
    return [condition for condition in conditions if not (channel == "eu5" and condition == UNLABELLED)]


def metric_statistics(fields: list[dict[str, Any]], channel: str, metric: str, native: dict[str, Any],
                      binned: dict[str, Any], redetected: dict[str, Any]) -> dict[str, Any]:
    by_condition: dict[str, dict[str, list]] = defaultdict(lambda: defaultdict(list))
    groups = sorted({field["group"] for field in fields if field["status"] == "ok"})
    result: dict[str, Any] = {"by_group": {}}
    for group in groups:
        chosen = [field for field in fields if field["status"] == "ok" and field["group"] == group]
        conditions = sorted({field["condition"] for field in chosen})
        rows = {}
        medians: dict[str, dict[str, list[float]]] = {key: defaultdict(list) for key in ("native", "binned")}
        rhos: dict[str, list[float]] = defaultdict(list)
        rhos_redetected: dict[str, list[float]] = defaultdict(list)
        for field in chosen:
            name, condition = field["name"], field["condition"]
            n, b = native["fields"][name], binned["fields"][name]
            values_n, values_b = n[metric], b[metric]
            stats = by_condition[f"{group}/{condition}"]
            stats["nuclei"].append(len(n["ids"]))
            stats["measurable"].append(int(np.isfinite(values_n).sum()))
            stats["inner"].append(int((~n["border"]).sum()))
            stats["inner_measurable"].append(int((np.isfinite(values_n) & ~n["border"]).sum()))
            for reason in n["reasons"][metric]:
                stats["reasons"].append(reason or "measured")
            if np.isfinite(values_n).any():
                medians["native"][condition].append(float(np.nanmedian(values_n)))
            if np.isfinite(values_b).any():
                medians["binned"][condition].append(float(np.nanmedian(values_b)))
            both = np.isfinite(values_n) & np.isfinite(values_b)
            rho = _spearman(values_n[both], values_b[both])
            if rho is not None:
                rhos[condition].append(rho)
            r = redetected["fields"][name]
            match = field["redetected_match"]
            position_n = {int(i): k for k, i in enumerate(n["ids"])}
            position_r = {int(i): k for k, i in enumerate(r["ids"])}
            pairs = [(position_n[int(a)], position_r[int(c)]) for a, c in zip(match["native"], match["redetected"],
                                                                                strict=True)
                     if int(a) in position_n and int(c) in position_r]
            if pairs:
                left = np.asarray([values_n[i] for i, _ in pairs])
                right = np.asarray([r[metric][j] for _, j in pairs])
                keep = np.isfinite(left) & np.isfinite(right)
                rho = _spearman(left[keep], right[keep])
                if rho is not None:
                    rhos_redetected[condition].append(rho)
        for condition in conditions:
            stats = by_condition[f"{group}/{condition}"]
            reasons: dict[str, int] = defaultdict(int)
            for reason in stats["reasons"]:
                reasons[reason] += 1
            nuclei = int(sum(stats["nuclei"]))
            rows[condition] = {"fields": len(stats["nuclei"]), "nuclei": nuclei,
                               "measurable_fraction": (sum(stats["measurable"]) / nuclei) if nuclei else None,
                               "measurable_fraction_not_border": (sum(stats["inner_measurable"]) / sum(stats["inner"])
                                                                  if sum(stats["inner"]) else None),
                               "reasons": dict(sorted(reasons.items())),
                               "rho_fields": len(rhos[condition]),
                               "rho_median": float(np.median(rhos[condition])) if rhos[condition] else None,
                               "rho_redetected_median": (float(np.median(rhos_redetected[condition]))
                                                         if rhos_redetected[condition] else None)}
        contrasts = {}
        for condition in conditions:
            if condition == CONTROL:
                continue
            entry: dict[str, Any] = {}
            for resolution in ("native", "binned"):
                treated, control = medians[resolution][condition], medians[resolution][CONTROL]
                if len(treated) < 2 or len(control) < 2:
                    entry[resolution] = None
                    continue
                difference = float(np.mean(treated) - np.mean(control))
                se = math.sqrt(np.var(treated, ddof=1) / len(treated) + np.var(control, ddof=1) / len(control))
                entry[resolution] = {"difference": difference, "se": se, "fields": [len(treated), len(control)]}
            if entry.get("native") and entry.get("binned"):
                native_d, binned_d = entry["native"]["difference"], entry["binned"]["difference"]
                evaluated = abs(native_d) > DEAD_BAND_SE * entry["native"]["se"]
                entry.update(evaluated=evaluated,
                             same_sign=bool(np.sign(native_d) == np.sign(binned_d)) if evaluated else None,
                             q=(binned_d / native_d) if evaluated else None)
            else:
                entry.update(evaluated=False, same_sign=None, q=None)
            contrasts[condition] = entry
        result["by_group"][group] = {"conditions": rows, "contrasts": contrasts,
                                     "threshold_native": native["thresholds"].get(group),
                                     "threshold_binned": binned["thresholds"].get(group)}
    return result


def choose_ratio(fields: list[dict[str, Any]]) -> dict[str, Any]:
    """Rule 5 on the tuning split's 5-EU channel at the 2 h time point."""
    fields = [field for field in fields if field["group"] == RATIO_TIMEPOINT]

    def flagged(condition: str, ratio: float) -> float | None:
        values = [value for field in fields if field["status"] == "ok" and field["condition"] == condition
                  for value, reason in zip(field["eu5"]["native"]["ratio"], field["eu5"]["native"]["reason"],
                                           strict=True) if reason is None]
        return float(np.mean(np.asarray(values) < ratio)) if values else None

    table = [{"ratio": ratio, "flagged_no_eu": flagged(UNLABELLED, ratio), "flagged_with_eu": flagged(CONTROL, ratio)}
             for ratio in RATIO_CANDIDATES]
    chosen = next((row["ratio"] for row in table if row["flagged_no_eu"] is not None and row["flagged_with_eu"] is not None
                   and row["flagged_no_eu"] >= NOEU_FLAGGED and row["flagged_with_eu"] <= WITHEU_FLAGGED), None)
    ratios = [value for field in fields if field["status"] == "ok" for condition in (UNLABELLED, CONTROL)
              if field["condition"] == condition for value in field["eu5"]["native"]["ratio"] if np.isfinite(value)]
    return {"candidates": table, "chosen": chosen if chosen is not None else RATIO_FALLBACK,
            "separates_unlabelled_control": chosen is not None,
            "ratio_quantiles_controls": [float(q) for q in np.quantile(ratios, (0.05, 0.5, 0.95))] if ratios else None}


def criteria_from_tuning(statistics: dict[str, Any]) -> dict[str, Any]:
    """Rule 7 a and b: rho_crit and [q_lo, q_hi] per metric x channel, and whether tuning itself allows offering."""
    out = {}
    for key, value in statistics.items():
        channel = key.split("/")[1]
        rhos, qs, signs, evaluated = [], [], [], 0
        for group in value["by_group"].values():
            for condition, row in group["conditions"].items():
                if condition in compared_conditions([condition], channel) and row["rho_median"] is not None:
                    rhos.append(row["rho_median"])
            for condition, contrast in group["contrasts"].items():
                if condition not in compared_conditions([condition], channel) or not contrast.get("evaluated"):
                    continue
                evaluated += 1
                signs.append(contrast["same_sign"])
                qs.append(contrast["q"])
        rho_bar = (min(rhos) - RHO_MARGIN) if rhos else None
        rho_crit = min(rho_bar, RHO_CEILING) if rho_bar is not None else None
        q_range = (min(min(qs) - Q_MARGIN, Q_BAND[0]), max(max(qs) + Q_MARGIN, Q_BAND[1])) if qs else None
        reasons = []
        if rho_bar is None or rho_bar < RHO_FLOOR:
            reasons.append("tuning_rank_below_floor")
        if evaluated < MIN_TUNING_CONTRASTS:
            reasons.append("tuning_too_few_evaluated_contrasts")
        if not all(signs):
            reasons.append("tuning_sign_changed")
        if qs and (min(qs) < Q_RANGE[0] or max(qs) > Q_RANGE[1]):
            reasons.append("tuning_size_outside_range")
        out[key] = {"rho_min": min(rhos) if rhos else None, "rho_crit": rho_crit, "q_tuning": [min(qs), max(qs)] if qs else None,
                    "q_range": list(q_range) if q_range else None, "evaluated_contrasts": evaluated,
                    "tuning_allows": not reasons, "tuning_failures": reasons}
    return out


def verdict(statistics: dict[str, Any], criteria: dict[str, Any], expected: dict[str, set[str]]) -> dict[str, Any]:
    """Rules 6 and 7 on the evaluation split; ``expected`` is the registered conditions of each time point."""
    out = {}
    for key, value in statistics.items():
        channel = key.split("/")[1]
        criterion = criteria[key]
        failures = list(criterion["tuning_failures"])
        rates, evaluated = [], 0
        for group, conditions in sorted(expected.items()):
            present = set((value["by_group"].get(group) or {}).get("conditions", {}))
            failures.extend(f"missing:{group}/{condition}"
                            for condition in sorted(set(compared_conditions(sorted(conditions), channel)) - present))
        for group in value["by_group"].values():
            for condition, row in group["conditions"].items():
                if condition not in compared_conditions([condition], channel):
                    continue
                rates.append(row["measurable_fraction"] or 0.0)
                if criterion["rho_crit"] is not None and (row["rho_median"] is None or row["rho_median"] < criterion["rho_crit"]):
                    failures.append(f"rank:{condition}")
            for condition, contrast in group["contrasts"].items():
                if condition not in compared_conditions([condition], channel) or not contrast.get("evaluated"):
                    continue
                evaluated += 1
                if not contrast["same_sign"]:
                    failures.append(f"sign:{condition}")
                elif criterion["q_range"] and not criterion["q_range"][0] <= contrast["q"] <= criterion["q_range"][1]:
                    failures.append(f"size:{condition}")
        if not rates or min(rates) < RATE_MINIMUM:
            failures.append("measurability_below_80")
        if rates and max(rates) - min(rates) > RATE_SPREAD:
            failures.append("measurability_spread_above_10")
        if not evaluated:
            failures.append("no_evaluated_contrast")
        out[key] = {"passes": not failures, "failures": failures,
                    "measurable_min": min(rates) if rates else None, "measurable_max": max(rates) if rates else None,
                    "evaluated_contrasts": evaluated}
    return out


def summarize(fields: list[dict[str, Any]], ratio: float) -> dict[str, Any]:
    statistics = {}
    thresholds = {}
    for channel in CHANNELS:
        tables = {resolution: values_at(fields, channel, resolution, ratio) for resolution in RESOLUTIONS}
        thresholds[channel] = {resolution: table["thresholds"] for resolution, table in tables.items()}
        for metric in METRICS:
            statistics[f"{metric}/{channel}"] = metric_statistics(fields, channel, metric, tables["native"],
                                                                  tables["binned"], tables["redetected"])
    failed = [{"name": field["name"], "error": field.get("error")} for field in fields if field["status"] != "ok"]
    return {"statistics": statistics, "failed_fields": failed,
            "fields": len(fields), "nuclei": int(sum(field.get("nuclei", 0) for field in fields))}


def _committed_unchanged(path: Path) -> bool:
    try:
        tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(path)], cwd=ROOT, capture_output=True,
                                 timeout=30).returncode == 0
        clean = subprocess.run(["git", "status", "--porcelain", "--", str(path)], cwd=ROOT, capture_output=True,
                               text=True, timeout=30).stdout.strip() == ""
    except (OSError, subprocess.SubprocessError):
        return False
    return tracked and clean


def _script_commit() -> str | None:
    """The last commit of this script, which holds the rules; None when the working copy differs from it."""
    script = Path(__file__).resolve()
    if not _committed_unchanged(script):
        return None
    done = subprocess.run(["git", "log", "-1", "--format=%H", "--", str(script)], cwd=ROOT, capture_output=True,
                          text=True, timeout=30)
    return done.stdout.strip() or None


def _write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=1, ensure_ascii=False, allow_nan=False) + "\n", encoding="utf-8")


def _jsonable(value: Any) -> Any:
    """NaN-free JSON values (a missing statistic is null)."""
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def tune(data_dir: Path, work: Path, workers: int) -> None:
    fields = measure_split(data_dir, work, "tuning", workers)
    ratio = choose_ratio(fields)
    summary = summarize(fields, ratio["chosen"])
    criteria = criteria_from_tuning(summary["statistics"])
    _write(TUNING, _jsonable({"protocol": PROTOCOL, "split": "tuning", "rules": "scripts/validate_nuclear_signal_public.py",
                              "rules_commit": _script_commit(), "minimum_signal_to_background": ratio,
                              "criteria": criteria, **summary}))
    print(json.dumps({"ratio": ratio, "criteria": criteria}, indent=1))


def evaluate(data_dir: Path, work: Path, workers: int) -> None:
    if not _committed_unchanged(TUNING):
        raise SystemExit("evaluation_refused: commit the tuning values first")
    tuning = json.loads(TUNING.read_text(encoding="utf-8"))
    from cytellect_analysis import nuclear_features

    ratio = tuning["minimum_signal_to_background"]["chosen"]
    if nuclear_features.MINIMUM_SIGNAL_TO_BACKGROUND != ratio:
        raise SystemExit("evaluation_refused: the product floor differs from the tuning choice")
    fields = measure_split(data_dir, work, "evaluation", workers)
    summary = summarize(fields, ratio)
    manifest = json.loads(registered.MANIFEST.read_text(encoding="utf-8"))
    expected: dict[str, set[str]] = defaultdict(set)
    for entry in manifest["datasets"][DATASET]["files"]:
        if entry["split"] == "evaluation":
            expected[entry["group"]].add(entry["condition"])
    result = verdict(summary["statistics"], tuning["criteria"], expected)
    offered = {metric: all(result[f"{metric}/{channel}"]["passes"] for channel in CHANNELS) for metric in METRICS}
    _write(EVALUATION, _jsonable({"protocol": PROTOCOL, "split": "evaluation", "rules_commit": _script_commit(),
                                  "tuning_commit": tuning.get("rules_commit"), "minimum_signal_to_background": ratio,
                                  "verdict": result, "offered": offered, **summary}))
    print(json.dumps({"verdict": result, "offered": offered}, indent=1))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("detect", help="detect nuclei on every registered DS6b field")
    one.add_argument("--data-dir", type=Path, required=True)
    one.add_argument("--work", type=Path, required=True)
    one.add_argument("--fiji", required=True)
    one.add_argument("--workers", type=int, default=1)
    for name in ("tune", "evaluate"):
        sub = commands.add_parser(name)
        sub.add_argument("--data-dir", type=Path, required=True)
        sub.add_argument("--work", type=Path, required=True)
        sub.add_argument("--workers", type=int, default=1)
    args = parser.parse_args(argv)
    if args.command == "detect":
        detect(args.data_dir, args.work, args.fiji, args.workers)
    elif args.command == "tune":
        tune(args.data_dir, args.work, args.workers)
    else:
        evaluate(args.data_dir, args.work, args.workers)


if __name__ == "__main__":
    main()

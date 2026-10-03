"""Experimental-unit inference over reviewed, source-bound region measurements."""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter, defaultdict
from typing import Any

import pandas as pd
from scipy import stats

from .descriptive import SAFE_ERROR_CODES as DESCRIPTIVE_ERRORS
from .descriptive import _finite, prepare_region_observations, region_report_measurement_policy
from .region_comparison_contracts import RegionComparisonRequest, RegionComparisonResult
from .region_measurement_v2 import RegionMeasurementPolicy
from .statistics import finite_records
from .unit_inference import VERSION, aggregate_unit_observations, apply_holm, compare_unit_arrays

SAFE_ERROR_CODES = DESCRIPTIVE_ERRORS | frozenset({
    "region_comparison_review_required", "region_comparison_source_mismatch",
    "region_comparison_metadata_required", "region_comparison_sample_identity_mismatch",
    "region_comparison_condition_scope_mismatch", "region_comparison_unit_without_values",
    "region_comparison_acquisition_review_required", "region_comparison_acquisition_batch_required",
    "region_comparison_condition_batch_confounded", "region_comparison_paired_acquisition_mismatch",
    "region_comparison_incompatible_sampling", "region_comparison_incompatible_intensity_scale",
    "region_comparison_saturated_signal", "region_comparison_invalid_family",
    "region_comparison_invalid_text", "region_comparison_pairing_basis_required",
    "unique_complete_pairs_required", "inconsistent_pair_identity_for_shared_unit",
    "incomplete_pairs", "two_pairs_required", "shared_units_require_paired_analysis",
    "two_independent_units_per_group_required", "comparison_not_estimable",
    "group_order_must_match_groups", "paired_plot_requires_paired_inference",
    "explicit_confirmation_required", "region_comparison_result_required",
})


def source_fingerprint(report, config):
    measurement = _measurement_policy(report, config)
    source = {key: config.get(key) for key in (
        "recipe", "field_ids", "field_snapshot", "backgrounds", "exclusions", "review_record")}
    if measurement is not None:
        source["measurement"] = measurement.model_dump(mode="json")
    return hashlib.sha256(json.dumps({"report": report, "source": source}, sort_keys=True,
                                    separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode()).hexdigest()


def _measurement_policy(report, config):
    measurement = region_report_measurement_policy(report)
    recorded = config.get("measurement")
    try:
        actual = RegionMeasurementPolicy.model_validate(recorded) if recorded is not None else None
    except ValueError:
        raise ValueError("region_measurement_protocol_mismatch") from None
    if actual != measurement:
        raise ValueError("region_measurement_protocol_mismatch")
    return measurement


def _source(report, config, request):
    _measurement_policy(report, config)
    confirmed = (config.get("review_record") or {}).get("confirmed_at")
    if isinstance(confirmed, bool) or not isinstance(confirmed, (int, float)):
        raise ValueError("region_comparison_review_required")
    if not math.isfinite(confirmed) or confirmed <= 0 or report.get("field_failures"):
        raise ValueError("region_comparison_review_required")
    snapshot = config.get("field_snapshot", {})
    ids = config.get("field_ids", [])
    if (report.get("analysis_kind") != "region-2d" or not report.get("revision_id")
            or report.get("recipe") != config.get("recipe") or len(ids) != len(set(ids))
            or set(ids) != set(snapshot) or report.get("exclusions", []) != config.get("exclusions", [])):
        raise ValueError("region_comparison_source_mismatch")
    observations, sources, unit, failed = prepare_region_observations(report, snapshot, request.selection)
    return snapshot, observations, sources, unit, failed


def _design_ledger(snapshot, observations, report, request):
    excluded = {row["field_id"]: row["reason"] for row in report.get("exclusions", [])
                if row.get("region_id") is None}
    excluded.update({row["field_id"]: row["reason"] for row in report.get("excluded_failed_fields", [])})
    ledger = []
    units: dict[tuple[str, str], dict[str, Any]] = {}
    sample_units: dict[tuple[str, str], str] = {}
    paired = request.design.kind == "paired"
    for fid, field in sorted(snapshot.items()):
        md = field.get("metadata", {})
        condition = md.get("condition")
        if not isinstance(condition, str) or not condition.strip():
            raise ValueError("region_comparison_metadata_required")
        scope = condition in request.conditions
        item = {"field_id": fid, **{key: md.get(key) for key in (
            "condition", "sample", "experimental_unit", "pair", "acquisition_date")},
            "in_scope": scope, "explicitly_excluded": fid in excluded, "exclusion_reason": excluded.get(fid)}
        ledger.append(item)
        if not scope:
            continue
        required = ("sample", "experimental_unit", "pair") if paired else ("sample", "experimental_unit")
        if any(not isinstance(md.get(key), str) or not md[key].strip() for key in required):
            raise ValueError("region_comparison_metadata_required")
        sample_key = (condition, md["sample"])
        if sample_key in sample_units and sample_units[sample_key] != md["experimental_unit"]:
            raise ValueError("region_comparison_sample_identity_mismatch")
        sample_units[sample_key] = md["experimental_unit"]
        key = (condition, md["experimental_unit"])
        record = units.setdefault(key, {"condition": condition, "experimental_unit": md["experimental_unit"],
                                       "pair": md.get("pair") if paired else None, "field_ids": [],
                                       "excluded_fields": [], "selected_observations": 0})
        if paired and record["pair"] != md["pair"]:
            raise ValueError("inconsistent_pair_identity_for_shared_unit")
        record["field_ids"].append(fid)
        if fid in excluded:
            record["excluded_fields"].append(fid)
    if set(request.conditions) != {key[0] for key in units}:
        raise ValueError("region_comparison_condition_scope_mismatch")
    by_unit = defaultdict(set)
    pairs: dict[str, dict[str, Any]] = defaultdict(dict)
    for (condition, uid), record in units.items():
        by_unit[uid].add(record["pair"] if paired else condition)
        if paired:
            if condition in pairs[record["pair"]]:
                raise ValueError("unique_complete_pairs_required")
            pairs[record["pair"]][condition] = record
    if any(len(values) > 1 for values in by_unit.values()):
        raise ValueError("inconsistent_pair_identity_for_shared_unit" if paired else "shared_units_require_paired_analysis")
    if paired and any(set(groups) != set(request.conditions) for groups in pairs.values()):
        raise ValueError("incomplete_pairs")
    selected, missing, observation_ledger = [], [], []
    counts: Counter[str] = Counter()
    for row in observations:
        value = _finite(row["value"])
        scope = row["condition"] in request.conditions
        reason = "out_of_scope" if not scope else "excluded" if row["excluded"] else "missing" if value is None else "selected"
        entry = {**row, "value": value, "selection_status": reason}
        observation_ledger.append(entry)
        counts[reason] += 1
        if reason == "selected":
            selected.append(entry)
            units[row["condition"], row["experimental_unit"]]["selected_observations"] += 1
        elif reason == "missing":
            missing.append({"observation_id": row["observation_id"], "field_id": row["field_id"],
                            "reason": row.get("missing_reason") or "metric_unavailable"})
    for field in ledger:
        status_counts = Counter(row["selection_status"] for row in observation_ledger if row["field_id"] == field["field_id"])
        field.update(input_observations=sum(status_counts.values()), selected_observations=status_counts["selected"],
                     excluded_observations=status_counts["excluded"], missing_observations=status_counts["missing"])
        field["status"] = ("out_of_scope" if not field["in_scope"] else "excluded" if field["explicitly_excluded"]
                           else "no_regions" if not status_counts else "selected" if status_counts["selected"]
                           else "no_selected_values")
    for record in units.values():
        explicitly_excluded = set(record["field_ids"]) == set(record["excluded_fields"])
        record["status"] = "excluded" if explicitly_excluded else "selected" if record["selected_observations"] else "no_values"
        if record["status"] == "no_values":
            raise ValueError("region_comparison_unit_without_values")
    pair_ledger = []
    for pair, groups in sorted(pairs.items()):
        statuses = {record["status"] for record in groups.values()}
        if len(statuses) != 1:
            raise ValueError("incomplete_pairs")
        pair_ledger.append({"pair": pair, "status": next(iter(statuses)),
                            "units": {condition: groups[condition]["experimental_unit"] for condition in request.conditions}})
    if not selected:
        raise ValueError("no_valid_selected_measurements")
    return ledger, list(units.values()), pair_ledger, selected, observation_ledger, missing, dict(counts)


def _acquisition(sources, snapshot, selected, field_ledger, request):
    review, metric = request.acquisition_review, request.selection.metric
    area = metric.startswith("area_")
    if set(review.field_batches) - set(snapshot):
        raise ValueError("region_comparison_acquisition_review_required")
    if review.basis == "calibrated-area" and metric != "area_um2":
        raise ValueError("region_comparison_acquisition_review_required")
    if (metric == "area_px" or "integrated" in metric) and not review.spatial_sampling_confirmed:
        raise ValueError("region_comparison_incompatible_sampling")
    if metric == "area_um2":
        eligible_fields = {field["field_id"] for field in field_ledger
                           if field["in_scope"] and not field["explicitly_excluded"]}
        if any(field["calibration"] is None for field in sources if field["field_id"] in eligible_fields):
            raise ValueError("region_comparison_incompatible_sampling")
    selected_fields = {row["field_id"] for row in selected}
    sources = [field for field in sources if field["field_id"] in selected_fields]
    calibration = {json.dumps(field["calibration"], sort_keys=True) for field in sources}
    if metric == "area_um2" and any(field["calibration"] is None for field in sources):
        raise ValueError("region_comparison_incompatible_sampling")
    if metric == "area_um2" and len(calibration) > 1 and review.basis != "calibrated-area":
        raise ValueError("region_comparison_acquisition_review_required")
    if metric == "area_px" or "integrated" in metric:
        if len(calibration) > 1:
            raise ValueError("region_comparison_incompatible_sampling")
    batches, dtypes = {}, set()
    for field in sources:
        fid = field["field_id"]
        batch = review.field_batches.get(fid) or snapshot[fid]["metadata"].get("acquisition_date")
        if not area and not batch:
            raise ValueError("region_comparison_acquisition_batch_required")
        batches[fid] = batch
        if not area:
            provenance = next(p for p in field["channel_provenance"]
                              if p["channel"]["channel_id"] == request.selection.channel_id)
            dtypes.add(provenance["dtype"])
    if len(dtypes) > 1:
        raise ValueError("region_comparison_incompatible_intensity_scale")
    warnings = []
    if not area:
        group_batches = {condition: {batches[row["field_id"]] for row in selected if row["condition"] == condition}
                         for condition in request.conditions}
        if any(not (group_batches[a] & group_batches[b]) for a, b in request.comparison_family.contrasts):
            raise ValueError("region_comparison_condition_batch_confounded")
        if any(group_batches[a] != group_batches[b] for a, b in request.comparison_family.contrasts):
            warnings.append("acquisition_batches_partially_unbalanced_no_batch_adjustment")
        if request.design.kind == "paired":
            paired_batches: dict[str, dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
            for row in selected:
                paired_batches[row["pair"]][row["condition"]].add(batches[row["field_id"]])
            if any(len({tuple(sorted(values)) for values in groups.values()}) > 1 for groups in paired_batches.values()):
                raise ValueError("region_comparison_paired_acquisition_mismatch")
    return {"review": review.model_dump(mode="json"), "field_batches": batches,
            "machine_verified_acquisition_equivalence": False,
            "note": "User-confirmed acquisition basis; no intensity normalization or batch adjustment."}, warnings


def compare_regions(report, config, request):
    request = RegionComparisonRequest.model_validate(request)
    snapshot, observations, sources, unit, failed = _source(report, config, request)
    ledger, unit_ledger, pairs, selected, observation_ledger, missing, selection_counts = _design_ledger(
        snapshot, observations, report, request)
    acquisition, warnings = _acquisition(sources, snapshot, selected, ledger, request)
    if not request.selection.metric.startswith("area_"):
        selected_ids = {(row["field_id"], row["region_id"]) for row in selected}
        for fid, table in report["field_tables"].items():
            for row in table["rows"]:
                if ((fid, row["region_id"]) in selected_ids and row["channel_id"] == request.selection.channel_id
                        and (row["storage_limit_fraction"] > 0 or (row["acquisition_saturation_fraction"] or 0) > 0)):
                    raise ValueError("region_comparison_saturated_signal")
    frame = pd.DataFrame(selected)
    field_summary, sample_summary, units = aggregate_unit_observations(frame, "value")
    comparisons, means, counts = [], [], []
    paired = request.design.kind == "paired"
    for a, b in request.comparison_family.contrasts:
        aa, bb = units[units.condition == a], units[units.condition == b]
        if paired:
            matched = aa.set_index("pair")[["value"]].join(bb.set_index("pair")[["value"]],
                                                          how="outer", lsuffix="_a", rsuffix="_b")
            if matched.isna().any().any():
                raise ValueError("incomplete_pairs")
            va, vb = matched.value_a.to_numpy(), matched.value_b.to_numpy()
        else:
            va, vb = aa.value.to_numpy(), bb.value.to_numpy()
        entry = {"group_a": a, "group_b": b, **compare_unit_arrays(va, vb, paired=paired)}
        if paired:
            entry["complete_pairs"] = len(va)
        comparisons.append(entry)
    apply_holm(comparisons, request.comparison_family.family_id)
    for condition in request.conditions:
        values = units[units.condition == condition].value
        mean = float(values.mean())
        half = float(stats.t.ppf(.975, len(values) - 1) * stats.sem(values))
        means.append({"condition": condition, "mean": mean, "ci_low": mean - half, "ci_high": mean + half,
                      "confidence_level": .95, "interval": "pointwise independent-unit mean CI"})
        all_units = [row for row in unit_ledger if row["condition"] == condition]
        sf = frame[frame.condition == condition]
        lf = [row for row in ledger if row["condition"] == condition]
        counts.append({"condition": condition, "observations": len(sf), "input_fields": len(lf),
                       "selected_fields": sf.field_id.nunique(), "samples": sf["sample"].nunique(),
                       "input_units": len(all_units), "experimental_units": len(values),
                       "explicitly_excluded_units": sum(row["status"] == "excluded" for row in all_units),
                       "complete_pairs": len(values) if paired else None})
    if any(row["experimental_units"] < 5 for row in counts):
        warnings.append("few_independent_units_model_assumptions_and_power_require_review")
    if missing:
        warnings.append("missing_outcomes_excluded_not_assumed_missing_at_random")
    if failed:
        warnings.append("explicitly_excluded_failed_fields_have_unknown_observation_counts")
    warnings += ["acquisition_comparability_user_confirmed_not_machine_verified",
                 "pointwise_confidence_intervals_are_not_holm_adjusted"]
    source = sources[0]
    channel = (next(p["channel"] for p in source["channel_provenance"]
                    if p["channel"]["channel_id"] == request.selection.channel_id)
               if request.selection.channel_id is not None else None)
    return RegionComparisonResult(
        inference_version=VERSION, revision_id=report["revision_id"], source_fingerprint=source_fingerprint(report, config),
        spec=request, metric=request.selection.metric, unit=unit, region=source["region_set"], channel=channel,
        source_fields=sources, source_field_ledger=ledger, observation_ledger=observation_ledger,
        plot_data=selected, field_summary=finite_records(field_summary), sample_summary=finite_records(sample_summary),
        unit_summary=finite_records(units), unit_ledger=unit_ledger, pair_ledger=pairs,
        counts=counts, selection={"input_rows": len(observations), **selection_counts}, missingness=missing,
        excluded_failed_fields=failed, acquisition=acquisition, comparisons=comparisons, means=means, warnings=warnings,
    ).model_dump(mode="json")

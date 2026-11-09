"""Channel-neutral classification of saved nuclear means, bound by exact nucleus identity.

No pixels are read and no stain is inferred. The percentile and Otsu arithmetic is
shared with the historical gate, using neutral value keys and a separate protocol.
"""
from __future__ import annotations

import hashlib
import json
from collections import Counter

from .channel_gate_contracts import PROTOCOL, ChannelGateFilter
from .gfp_gate import MINIMUM_CONTROL_NUCLEI, control_thresholds, exploratory_thresholds
from .gfp_selection import _channel, _nuclear_rows, binding_kind, same_revision_nuclear_source

GATE_KEYS = ("channel_mean", "channel_positive", "channel_gate_threshold", "channel_gate_reason",
             "channel_control_field", "channel_gate_status")
SAFE_ERROR_CODES = frozenset({f"channel_gate_{suffix}" for suffix in (
    "nuclear_source_unbound", "nuclear_source_invalid", "nuclear_identity_mismatch", "channel_unknown",
    "channel_identity_mismatch", "unknown_control_field", "control_field_excluded", "intensity_not_measured",
    "threshold_invalid", "control_percentile_invalid", "control_fields_invalid", "duplicate_control_field",
    "duplicate_field", "conflicting_filters", "unsupported_request", "preview_unsupported",
    "condition_only_control_fields", "unit_without_selected_nuclei", "requires_nuclear_revision",
    "source_invalid", "acquisition_date_required", "too_few_nuclei", "uniform_distribution",
    "record_mismatch", "record_required",
)})


def channel_filter(selection):
    gate = getattr(selection, "channel_gate", None) or getattr(selection, "positivity", None)
    return gate if isinstance(gate, ChannelGateFilter) else None


def uses_channel_gate(spec):
    if not isinstance(spec, dict):
        return False
    return any(isinstance(item, dict) and (
        item.get("channel_gate") is not None
        or (item.get("positivity") or {}).get("gate_protocol") == PROTOCOL)
        for item in (spec.get("selection"), spec.get("x_selection"), spec.get("y_selection")))


def _date(snapshot, fid):
    value = snapshot[fid].get("metadata", {}).get("acquisition_date")
    return value if isinstance(value, str) and value.strip() else None


def _thresholds(rows, gate, dates):
    eligible = [row for row in rows if not row["channel_excluded"]]
    if gate.method == "negative_control":
        result = control_thresholds(eligible, gate.percentile, value_key="channel_mean", protocol=PROTOCOL,
                                    invalid_reason="channel_gate_control_percentile_invalid")
        for date in dates:
            result["dates"].setdefault(date, {"threshold": None, "control_nuclei": 0,
                                             "missing_reason": "too_few_control_nuclei"})
    else:
        result = exploratory_thresholds(
            eligible, gate.method, gate.threshold, value_key="channel_mean", protocol=PROTOCOL,
            invalid_reason="channel_gate_threshold_invalid", date_reason="channel_gate_acquisition_date_required",
            few_reason="channel_gate_too_few_nuclei", uniform_reason="channel_gate_uniform_distribution")
        if gate.method == "batch_otsu":
            for date in dates:
                result["dates"].setdefault(date, {"threshold": None, "control_nuclei": 0,
                                                 "measured_nuclei": 0, "missing_reason": "channel_gate_too_few_nuclei"})
    if gate.method != "manual" and "" in result["dates"]:
        result["dates"][""] = {**result["dates"][""], "threshold": None,
                                  "missing_reason": "channel_gate_acquisition_date_required"}
    result["method"] = gate.method
    return result


def apply_channel_gate(observations, snapshot, gate, nuclear, *, failed_fields=(), field_exclusions=(),
                       exact_nuclear_area=None, smaller_than_nucleus=None, target_exclusions=()):
    """Return marked observations and the complete, pre-selection nucleus decision record."""
    gate = ChannelGateFilter.model_validate(gate)
    controls, failed, excluded_fields = set(gate.control_field_ids), set(failed_fields), set(field_exclusions)
    target_reasons = {(item["field_id"], item.get("region_id")): item["reason"] for item in target_exclusions}
    excluded_fields |= {fid for fid, rid in target_reasons if rid is None}
    if controls - set(snapshot):
        raise ValueError("channel_gate_unknown_control_field")
    if controls & (failed | excluded_fields):
        raise ValueError("channel_gate_control_field_excluded")
    measured = set(snapshot) - failed
    rows, nuclear_excluded, sources = _nuclear_rows(
        nuclear, snapshot, gate, measured, channel_id=gate.channel_id, value_key="channel_mean",
        saturation_key="channel_saturated", error_prefix="channel_gate", include_excluded=True)
    if controls & nuclear_excluded:
        raise ValueError("channel_gate_control_field_excluded")
    excluded_fields |= nuclear_excluded
    channels = {fid: _channel(value.get("image_info"), gate.channel_id) for fid, value in snapshot.items()}
    if any(value is None for value in channels.values()):
        raise ValueError("channel_gate_channel_unknown")
    identities = [{key: value.get(key) for key in ("channel_id", "label", "stain")}
                  for value in channels.values()]
    if not identities or any(value != identities[0] for value in identities):
        raise ValueError("channel_gate_channel_identity_mismatch")
    dates = {fid: _date(snapshot, fid) for fid in snapshot}
    population = []
    for (fid, nid), row in sorted(rows.items()):
        reason = row.get("exclusion_reason") or target_reasons.get((fid, None)) or target_reasons.get((fid, nid))
        population.append({**row, "acquisition_date": dates[fid] or "", "control": fid in controls,
                           "channel_excluded": row["channel_excluded"] or fid in excluded_fields or reason is not None,
                           "exclusion_reason": reason})
    thresholds = _thresholds(population, gate, {dates[fid] or "" for fid in measured})
    classified = {}
    for row in population:
        fid, nid = row["field_id"], row["region_id"]
        setting = thresholds["dates"].get("all" if gate.method == "manual" else dates[fid] or "", {})
        threshold, value = setting.get("threshold"), row["channel_mean"]
        positive = None
        if row["channel_excluded"]:
            status, reason = "excluded", "field_excluded" if fid in excluded_fields else "nucleus_excluded"
        elif row["control"]:
            status, reason = "control", "negative_control"
        elif value is None:
            status, reason = "unclassified", row.get("channel_missing_reason") or "channel_intensity_missing"
        elif threshold is None:
            status, reason = "unclassified", setting.get("missing_reason") or "channel_threshold_missing"
        else:
            positive = bool(value > threshold)
            status, reason = ("positive", "above_threshold") if positive else ("negative", "at_or_below_threshold")
        classified[fid, nid] = {
            "field_id": fid, "region_id": nid, "acquisition_date": dates[fid], "channel_mean": value,
            "positive": positive, "status": status, "reason": reason, "threshold": threshold,
            "exclusion_reason": row.get("exclusion_reason")}
    marked = []
    for item in observations:
        key = item["field_id"], item.get("nucleus_id", item.get("region_id"))
        if type(key[1]) is not int:
            raise ValueError("channel_gate_nuclear_identity_mismatch")
        row, origin = classified.get(key), rows.get(key)
        if row is None and not item["excluded"]:
            raise ValueError("channel_gate_nuclear_identity_mismatch")
        if origin is not None:
            area = (exact_nuclear_area or {}).get(key)
            inner = (smaller_than_nucleus or {}).get(key)
            if ((area is not None and area != origin["area_px"])
                    or (inner is not None and not 0 < inner < origin["area_px"])):
                raise ValueError("channel_gate_nuclear_identity_mismatch")
        row = row or {"channel_mean": None, "positive": None, "threshold": None,
                      "reason": "nucleus_excluded", "status": "excluded"}
        keep = row["positive"] is (gate.keep == "positive")
        marked.append({**item, "channel_mean": row["channel_mean"], "channel_positive": row["positive"],
                       "channel_gate_threshold": row["threshold"], "channel_gate_reason": row["reason"],
                       "channel_gate_status": row["status"], "channel_control_field": key[0] in controls,
                       "gate_selected": keep and row["status"] in ("positive", "negative") and not item["excluded"]})
    field_counts = {}
    for fid in sorted(snapshot):
        outcomes = [row for row in classified.values() if row["field_id"] == fid]
        counts = Counter(row["status"] for row in outcomes)
        field_counts[fid] = {
            "status": "failed" if fid in failed else "excluded" if fid in excluded_fields
                      else "measured" if outcomes else "no_regions",
            "nuclei": None if fid in failed else len(outcomes),
            **{key: counts[key] for key in ("positive", "negative", "unclassified", "control", "excluded")},
            "evaluable": counts["positive"] + counts["negative"]}
    recorded_dates = {}
    for date, setting in thresholds["dates"].items():
        recorded_dates[date] = {**setting, "control_field_ids": sorted(
            fid for fid in controls if (dates[fid] or "") == date)}
    for fid, entry in sources.items():
        entry["exclusions"] = nuclear["fields"][fid].get("exclusions", [])
    # Cohort assembly changes analysis revision IDs, but not the adopted mask IDs,
    # original measurements or decisions. Bind precisely those stable inputs.
    decisions = [({key: value for key, value in row.items() if key != "acquisition_date"}
                  if gate.method == "manual" else row) for row in classified.values()]
    reference = {"filter": gate.model_dump(mode="json", exclude={"reference_sha256"}),
                 "channels": channels, "dates": recorded_dates, "decisions": decisions,
                 "metadata": {fid: value.get("metadata", {}) for fid, value in snapshot.items()},
                 "target_exclusions": sorted(target_exclusions, key=lambda value: json.dumps(value, sort_keys=True)),
                 "masks": {fid: {key: value.get(key) for key in ("mask_revision_id", "mask_sha256", "excluded_nuclei")}
                           for fid, value in sources.items()}}
    digest = hashlib.sha256(json.dumps(reference, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    if gate.reference_sha256 is not None and gate.reference_sha256 != digest:
        raise ValueError("channel_gate_record_mismatch")
    record = {
        "filter_version": gate.version, "gate_protocol": PROTOCOL, "filter": gate.model_dump(mode="json"),
        "decision_sha256": digest,
        "field_metadata": {fid: value.get("metadata", {}) for fid, value in snapshot.items()},
        "target_exclusions": sorted(target_exclusions, key=lambda value: json.dumps(value, sort_keys=True)),
        "channel": identities[0], "channels_by_field": channels, "values": gate.values,
        "statistic": f"arithmetic mean of {gate.values} channel intensity within each adopted nucleus",
        "threshold_rule": "mean strictly greater than threshold; equality is negative",
        "thresholds": thresholds, "dates": recorded_dates, "control_field_ids": sorted(controls),
        "minimum_control_nuclei": MINIMUM_CONTROL_NUCLEI if controls else None,
        "nuclear_binding": nuclear["binding"], "nuclear_sources": sources,
        "nuclei": list(classified.values()), "field_counts": field_counts,
        "saturated_nuclei": sum(bool(row["channel_saturated"]) for row in population if not row["channel_excluded"]),
        "observations": len(marked), "kept_observations": sum(row["gate_selected"] for row in marked),
        "by_field": [{"field_id": fid, "acquisition_date": dates[fid],
                      "role": "negative_control" if fid in controls else "measured", **counts}
                     for fid, counts in field_counts.items()]}
    return marked, record


def gate_source_observations(report, recipe, snapshot, selection, observations, failed, summaries=None, nuclear=None):
    gate = channel_filter(selection)
    if gate is None or gate.reference_sha256 is None:
        raise ValueError("channel_gate_record_required")
    binding = binding_kind(recipe, error_prefix="channel_gate")
    if recipe.get("source") in ("manual", "cellpose_cell") or report.get("recipe") != recipe:
        raise ValueError("channel_gate_nuclear_source_invalid")
    if nuclear is None:
        if binding != "same_revision":
            raise ValueError("channel_gate_nuclear_source_unbound")
        nuclear = same_revision_nuclear_source(report, snapshot, error_prefix="channel_gate")
    if not isinstance(nuclear, dict) or nuclear.get("binding") != binding:
        raise ValueError("channel_gate_nuclear_source_unbound")
    exact, inner = {}, {}
    if selection.source == "compartment-summary":
        for fid, document in (summaries or {}).items():
            values = next(iter(document["channels"].values()))
            exact.update({(fid, row["nucleus_id"]): row["nucleus_area_px"] for row in values["rows"]})
    elif binding == "parent_nucleus":
        for fid, table in report["field_tables"].items():
            inner.update({(fid, row["region_id"]): row["area_px"] for row in table["rows"]})
    field_exclusions = {item["field_id"] for item in report.get("exclusions", []) if item.get("region_id") is None}
    return apply_channel_gate(observations, snapshot, gate, nuclear,
                              failed_fields=[row["field_id"] for row in failed], field_exclusions=field_exclusions,
                              exact_nuclear_area=exact, smaller_than_nucleus=inner,
                              target_exclusions=report.get("exclusions", []))


def gate_warnings(record):
    warnings = ["channel_gated_subset_selected_by_expression_level_not_randomized"]
    if record["filter"]["method"] != "negative_control":
        warnings.append("channel_gate_exploratory_threshold_without_negative_control")
    if any(row["status"] == "unclassified" for row in record["nuclei"]):
        warnings.append("channel_gate_unclassified_nuclei_not_selected")
    if record["saturated_nuclei"]:
        warnings.append("channel_gate_saturated_nuclei_present")
    return warnings


def finish_gated_description(result, record):
    result["selection"]["channel_gate"] = record
    for rows in (result["field_summary"], result["selection"]["by_field"]):
        for row in rows:
            if row["field_id"] in record["control_field_ids"]:
                row["status"] = "channel_negative_control"
    result["warnings"].extend(gate_warnings(record))
    return result


def methods_sentences(record):
    gate, channel = record["filter"], record["channel"]
    label = channel.get("stain") or channel.get("label") or channel["channel_id"]
    method = (f"the {gate['percentile']:g}th percentile (linear interpolation) of designated negative-control nuclei per acquisition date"
              if gate["method"] == "negative_control" else "a researcher-specified threshold"
              if gate["method"] == "manual" else "Otsu of nuclear means per acquisition date (256 bins, first maximum)")
    dates = "; ".join(f"{date or 'unknown date'}: {setting['threshold'] if setting['threshold'] is not None else setting['missing_reason']}"
                      + (f" from {setting['control_nuclei']} control nuclei" if gate["method"] == "negative_control" else "")
                      for date, setting in sorted(record["dates"].items()))
    positivity = record.get("purpose") == "field_positivity"
    return [
        f"Channel gate {record['gate_protocol']}, filter {record['filter_version']}: channel {channel['channel_id']} "
        f"(label {channel.get('label') or 'not recorded'}; declared stain {channel.get('stain') or 'not recorded'}).",
        f"{label} was the arithmetic mean of {gate['values']} intensities within the saved nuclear masks, bound by exact nucleus identity. "
        "Corrected means never fell back to raw values.",
        f"Classification used {method}. A mean strictly greater than its threshold was positive; equality was negative. Thresholds: {dates}.",
        (f"At least {MINIMUM_CONTROL_NUCLEI} control nuclei were required per acquisition date; dates without a threshold remained unclassified."
         if gate["method"] == "negative_control" else "Missing values or thresholds remained unclassified."),
        ("Field positivity used all evaluable positive and negative nuclei before subset selection; unclassified, excluded and control nuclei were outside the denominator."
         if positivity else f"Only {gate['keep']} nuclei were selected; unclassified, excluded and control nuclei were not selected."),
        f"Negative-control fields ({', '.join(record['control_field_ids']) or 'none'}) supplied thresholds only and were not compared. "
        "Manual and Otsu gates are exploratory. Classification does not establish biological identity or randomized groups."]

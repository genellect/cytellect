"""GFP-gated nucleus selection (filter 1.0.0) for common statistics 2.0.0 and descriptions.

Applies the negative-control gate (``gfp-gate/2.0.0``) to the observation records
that the region and compartment-summary selections already produce, so the
unchanged aggregation (field median -> sample mean -> unit mean), tests and
per-field descriptions consume only the nuclei the researcher chose to keep.

- GFP values are the raw per-nucleus GFP means of the adopted nuclear
  (``stardist_nuclear``) revision rows of the same fields. A nuclear revision is
  its own source; a nucleoplasm revision is bound to the nuclear revision recorded
  per field in its provenance by mask revision and canonical mask hash. Measured
  observations join nuclei by exact region / parent-nucleus identity; nothing is
  matched by order or position. Any other region source is refused.
- Thresholds are computed per acquisition date from the nuclei of the
  researcher-designated control fields (minimum 20 control nuclei per date).
- Control fields are never compared observations. Unselected nuclei remain in the
  ledgers with their gate reason; a missing GFP value or threshold is never
  treated as positive and never as zero.
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from typing import Any

from .descriptive_contracts import GfpGateFilter
from .gfp_gate import MINIMUM_CONTROL_NUCLEI, PROTOCOL, apply_control_gate, control_thresholds
from .region_measurement_v2 import region_table_from_json, require_region_metric

FILTER_VERSION = "1.0.0"
GATE_KEYS = ("gfp_mean", "gfp_gate_threshold", "gfp_gate_reason", "gfp_positive", "gfp_control_field")
SAFE_ERROR_CODES = frozenset({
    "gfp_gate_nuclear_source_unbound", "gfp_gate_nuclear_source_invalid", "gfp_gate_nuclear_identity_mismatch",
    "gfp_gate_channel_unknown", "gfp_gate_unknown_control_field", "gfp_gate_control_field_excluded",
    "gfp_gate_acquisition_date_required", "gfp_gate_intensity_not_measured",
    "gfp_gate_condition_only_control_fields", "gfp_gate_unit_without_selected_nuclei",
    "gfp_gate_unsupported_request", "gfp_gate_duplicate_control_field", "gfp_gate_preview_unsupported",
    "region_export_gfp_gate_unsupported",
})
NUCLEAR_SOURCES = ("stardist_nuclear",)


def gate_of(selection) -> GfpGateFilter | None:
    return getattr(selection, "gfp_gate", None)


def uses_gfp_gate(spec) -> bool:
    """Saved job payload or result spec carries a GFP nucleus filter."""
    if not isinstance(spec, dict):
        return False
    selections = [spec.get("selection"), spec.get("x_selection"), spec.get("y_selection")]
    return any(isinstance(item, dict) and item.get("gfp_gate") is not None for item in selections)


def binding_kind(recipe) -> str:
    """How measured observations map to nuclei for this revision recipe, or refuse."""
    recipe = recipe if isinstance(recipe, dict) else {}
    if recipe.get("source") in NUCLEAR_SOURCES:
        return "same_revision"
    if recipe.get("source") == "fiji_nuclear_compartment" and recipe.get("compartment") == "nucleoplasm":
        # Nucleoplasm labels keep the parent nucleus ID (compartment engine
        # ``nucleoplasm_label_identity = parent_nucleus_id``).
        return "parent_nucleus"
    raise ValueError("gfp_gate_nuclear_source_unbound")


def same_revision_nuclear_source(report, snapshot):
    """The measured revision itself holds the adopted nuclear masks and GFP rows."""
    if binding_kind(report.get("recipe")) != "same_revision":
        raise ValueError("gfp_gate_nuclear_source_unbound")
    fields = {}
    for fid, table in report.get("field_tables", {}).items():
        try:
            region_set, digest = table["region_set"], table["mask_sha256"]
            image_info = snapshot[fid]["image_info"]
        except (KeyError, TypeError):
            raise ValueError("gfp_gate_nuclear_source_invalid") from None
        fields[fid] = {"revision_id": report.get("revision_id"), "table": table,
                       "mask_revision_id": region_set.get("mask_revision_id"), "mask_sha256": digest,
                       "exclusions": [item for item in report.get("exclusions", []) if item.get("field_id") == fid],
                       "image_info": image_info}
    return {"binding": "same_revision", "fields": fields}


def _channel(image_info, channel_id):
    return next((item for item in (image_info or {}).get("channels", []) if item.get("channel_id") == channel_id), None)


def _nuclear_rows(nuclear, snapshot, gate, measured_fields):
    """Validated raw GFP means per (field, nucleus) from the bound nuclear tables."""
    if not isinstance(nuclear, dict) or nuclear.get("binding") not in ("same_revision", "parent_nucleus"):
        raise ValueError("gfp_gate_nuclear_source_unbound")
    sources = nuclear.get("fields") or {}
    rows: dict[tuple[str, int], dict[str, Any]] = {}
    excluded_fields: set[str] = set()
    records: dict[str, dict[str, Any]] = {}
    for fid in sorted(measured_fields):
        entry = sources.get(fid)
        if not isinstance(entry, dict):
            raise ValueError("gfp_gate_nuclear_source_unbound")
        try:
            table = region_table_from_json(json.dumps(entry["table"]))
        except (KeyError, TypeError, ValueError):
            raise ValueError("gfp_gate_nuclear_source_invalid") from None
        if (table.field_id != fid or table.region_set.mask_revision_id != entry.get("mask_revision_id")
                or table.mask_sha256 != entry.get("mask_sha256") or entry.get("image_info") != snapshot[fid].get("image_info")
                or table.region_set.source != "stardist_nuclear"):
            raise ValueError("gfp_gate_nuclear_identity_mismatch")
        try:
            require_region_metric(getattr(table, "measurement", None), "mean")
        except ValueError:
            raise ValueError("gfp_gate_intensity_not_measured") from None
        declared = _channel(snapshot[fid].get("image_info"), gate.gfp_channel_id)
        provenance = next((item for item in table.channel_provenance if item.channel.channel_id == gate.gfp_channel_id), None)
        if declared is None or provenance is None or provenance.channel.model_dump(mode="json") != declared:
            raise ValueError("gfp_gate_channel_unknown")
        exclusions = entry.get("exclusions") or []
        if any(item.get("field_id") != fid for item in exclusions):
            raise ValueError("gfp_gate_nuclear_source_invalid")
        if any(item.get("region_id") is None for item in exclusions):
            excluded_fields.add(fid)
        excluded = {item.get("region_id") for item in exclusions}
        for row in table.rows:
            if row.channel_id != gate.gfp_channel_id:
                continue
            if (row.field_id != fid or row.mask_revision_id != table.region_set.mask_revision_id
                    or row.region_id <= 0 or (fid, row.region_id) in rows):
                raise ValueError("gfp_gate_nuclear_identity_mismatch")
            if row.region_id in excluded:
                continue
            value = row.mean
            saturated = (row.storage_limit_fraction or 0) > 0 or (row.acquisition_saturation_fraction or 0) > 0
            rows[fid, row.region_id] = {"field_id": fid, "region_id": row.region_id, "area_px": row.area_px,
                                        "gfp_mean": None if value is None or not math.isfinite(value) else float(value),
                                        "gfp_saturated": saturated}
        records[fid] = {"revision_id": entry.get("revision_id"), "mask_revision_id": entry.get("mask_revision_id"),
                        "mask_sha256": entry.get("mask_sha256"),
                        "excluded_nuclei": sorted(i for i in excluded if i is not None)}
        if entry.get("report_sha256") is not None:
            records[fid]["report_sha256"] = entry["report_sha256"]
    return rows, excluded_fields, records


def apply_gfp_gate(observations, snapshot, gate, nuclear, *, failed_fields=(), field_exclusions=(),
                   exact_nuclear_area=None, smaller_than_nucleus=None):
    """Mark each observation with its gate outcome; return ``(observations, record)``.

    ``exact_nuclear_area`` maps (field, nucleus) to the nucleus area recorded by the
    measured source (compartment summary); ``smaller_than_nucleus`` maps (field,
    nucleus) to a nucleoplasm region area that must be strictly inside its parent.
    """
    gate = GfpGateFilter.model_validate(gate)
    controls = set(gate.control_field_ids)
    if controls - set(snapshot):
        raise ValueError("gfp_gate_unknown_control_field")
    failed, field_excluded = set(failed_fields), set(field_exclusions)
    if controls & (failed | field_excluded):
        raise ValueError("gfp_gate_control_field_excluded")
    measured = set(snapshot) - failed
    rows, nuclear_excluded_fields, source_records = _nuclear_rows(nuclear, snapshot, gate, measured)
    if controls & nuclear_excluded_fields:
        raise ValueError("gfp_gate_control_field_excluded")
    dates = {}
    for fid in measured:
        date = snapshot[fid].get("metadata", {}).get("acquisition_date")
        if not isinstance(date, str) or not date.strip():
            raise ValueError("gfp_gate_acquisition_date_required")
        dates[fid] = date
    eligible = measured - field_excluded - nuclear_excluded_fields
    gate_rows = [{**row, "acquisition_date": dates[row["field_id"]], "control": row["field_id"] in controls}
                 for _, row in sorted(rows.items()) if row["field_id"] in eligible]
    thresholds = control_thresholds(gate_rows, gate.percentile)
    gated = {(row["field_id"], row["region_id"]): row for row in apply_control_gate(gate_rows, thresholds)}
    marked = []
    for item in observations:
        fid = item["field_id"]
        nid = item.get("nucleus_id", item.get("region_id"))
        if type(nid) is not int:
            raise ValueError("gfp_gate_nuclear_identity_mismatch")
        row = gated.get((fid, nid))
        if row is None and not item["excluded"]:
            # Every unexcluded measured nucleus must exist in the bound nuclear table.
            raise ValueError("gfp_gate_nuclear_identity_mismatch")
        if row is not None:
            area = (exact_nuclear_area or {}).get((fid, nid))
            if area is not None and area != row["area_px"]:
                raise ValueError("gfp_gate_nuclear_identity_mismatch")
            inner = (smaller_than_nucleus or {}).get((fid, nid))
            if inner is not None and not 0 < inner < row["area_px"]:
                raise ValueError("gfp_gate_nuclear_identity_mismatch")
        control = fid in controls
        if row is None:
            values = {"gfp_mean": None, "gfp_gate_threshold": None,
                      "gfp_gate_reason": "negative_control" if control else "nucleus_excluded", "gfp_positive": False}
        else:
            values = {key: row[key] for key in ("gfp_mean", "gfp_gate_threshold", "gfp_gate_reason", "gfp_positive")}
        keep = (values["gfp_positive"] if gate.keep == "positive"
                else values["gfp_gate_reason"] == "within_control_range")
        marked.append({**item, **values, "gfp_control_field": control,
                       "gate_selected": bool(keep) and not control and row is not None})
    return marked, _record(gate, thresholds, gate_rows, gated, marked, dates, controls, nuclear["binding"],
                           source_records, snapshot)


def _record(gate, thresholds, gate_rows, gated, marked, dates, controls, binding, sources, snapshot):
    control_fields = defaultdict(list)
    for fid in sorted(controls):
        control_fields[dates[fid]].append(fid)
    reasons = Counter(row["gfp_gate_reason"] for row in gated.values())
    by_field = []
    for fid in sorted(dates):
        rows = [row for row in gated.values() if row["field_id"] == fid]
        observed = [row for row in marked if row["field_id"] == fid]
        by_field.append({"field_id": fid, "role": "negative_control" if fid in controls else "measured",
                         "acquisition_date": dates[fid], "threshold": thresholds["dates"].get(dates[fid], {}).get("threshold"),
                         "nuclei": len(rows), "reasons": dict(sorted(Counter(r["gfp_gate_reason"] for r in rows).items())),
                         "observations": len(observed), "kept_observations": sum(r["gate_selected"] for r in observed)})
    channel = _channel(snapshot[sorted(dates)[0]].get("image_info"), gate.gfp_channel_id) if dates else None
    return {
        "filter_version": FILTER_VERSION, "gate_protocol": PROTOCOL, "filter": gate.model_dump(mode="json"),
        "gfp_channel": channel, "values": "raw",
        "statistic": "arithmetic mean of raw original GFP pixels within each adopted nucleus",
        "threshold_rule": (f"{gate.percentile:g}th percentile (linear interpolation) of control-nucleus GFP means "
                           "per acquisition date; a nucleus is positive when its mean is strictly greater"),
        "minimum_control_nuclei": MINIMUM_CONTROL_NUCLEI, "nuclear_binding": binding, "nuclear_sources": sources,
        "control_field_ids": sorted(controls),
        "dates": {date: {**value, "control_field_ids": control_fields.get(date, [])}
                  for date, value in thresholds["dates"].items()},
        "nuclei": dict(sorted(reasons.items())),
        "saturated_gfp_nuclei": sum(bool(row.get("gfp_saturated")) for row in gate_rows),
        "observations": len(marked), "kept_observations": sum(row["gate_selected"] for row in marked),
        "by_field": by_field,
    }


def gate_source_observations(report, recipe, snapshot, selection, observations, failed, summaries=None, nuclear=None):
    """Bind the measured selection to nuclei and apply its GFP filter."""
    binding = binding_kind(recipe)
    if report.get("recipe") != recipe:
        raise ValueError("gfp_gate_nuclear_source_unbound")
    if nuclear is None:
        if binding != "same_revision":
            raise ValueError("gfp_gate_nuclear_source_unbound")
        nuclear = same_revision_nuclear_source(report, snapshot)
    if not isinstance(nuclear, dict) or nuclear.get("binding") != binding:
        raise ValueError("gfp_gate_nuclear_source_unbound")
    exact, inner = {}, {}
    if selection.source == "compartment-summary":
        for fid, document in (summaries or {}).items():
            table = next(iter(document["channels"].values()))
            exact.update({(fid, row["nucleus_id"]): row["nucleus_area_px"] for row in table["rows"]})
    elif binding == "parent_nucleus":
        for fid, table in report["field_tables"].items():
            inner.update({(fid, row["region_id"]): row["area_px"] for row in table["rows"]})
    field_exclusions = {row["field_id"] for row in report.get("exclusions", []) if row.get("region_id") is None}
    return apply_gfp_gate(observations, snapshot, gate_of(selection), nuclear,
                          failed_fields=[row["field_id"] for row in failed], field_exclusions=field_exclusions,
                          exact_nuclear_area=exact, smaller_than_nucleus=inner)


def finish_gated_description(result, record):
    """Record the gate in a per-field description; control fields are labelled, not compared."""
    controls = set(record["control_field_ids"])
    result["selection"]["gfp_gate"] = record
    for rows in (result["field_summary"], result["selection"]["by_field"]):
        for row in rows:
            if row["field_id"] in controls:
                row["status"] = "gfp_negative_control"
    result["warnings"].extend(gate_warnings(record))
    return result


def gate_warnings(record):
    warnings = ["gfp_gated_subset_selected_by_expression_level_not_randomized"]
    compared = {row["acquisition_date"] for row in record["by_field"] if row["role"] == "measured"}
    if any(record["dates"].get(date, {}).get("threshold") is None for date in compared):
        warnings.append("gfp_gate_dates_without_control_threshold_unselected")
    if record["saturated_gfp_nuclei"]:
        warnings.append("gfp_gate_saturated_gfp_nuclei_present")
    return warnings


def recorded_gate_lines(selection):
    """Methods/caption lines for a saved result ``selection``; empty when ungated."""
    gate = (selection or {}).get("gfp_gate")
    return [] if gate is None else methods_sentences(gate)


def methods_sentences(record):
    """English Methods / caption text recorded from the saved gate."""
    gate = record["filter"]
    channel = record.get("gfp_channel") or {}
    kept = "GFP-positive" if gate["keep"] == "positive" else "GFP-negative (within the control range)"
    dates = "; ".join(
        f"{date}: threshold {('%.8g' % value['threshold']) if value['threshold'] is not None else 'not defined'} "
        f"from {value['control_nuclei']} control nuclei"
        + (f" ({value['missing_reason']})" if value.get("missing_reason") else "")
        for date, value in sorted(record["dates"].items()))
    return [
        f"Nucleus filter: GFP gate filter {record['filter_version']} with protocol {record['gate_protocol']}. "
        f"Only {kept} nuclei were analysed.",
        f"GFP was the per-nucleus arithmetic mean of raw original pixels of channel {gate['gfp_channel_id']} "
        f"(label {channel.get('label') or 'not recorded'}; declared stain {channel.get('stain') or 'not recorded'}) "
        f"within the adopted nuclear masks ({record['nuclear_binding'].replace('_', ' ')} binding by exact nucleus identity).",
        f"For each acquisition date, the threshold was the {gate['percentile']:g}th percentile (linear interpolation) of the "
        "GFP means of nuclei in the researcher-designated negative-control fields "
        f"({', '.join(record['control_field_ids'])}); a nucleus was positive when its mean was strictly greater. "
        f"Dates with fewer than {record['minimum_control_nuclei']} control nuclei had no threshold and their nuclei were not selected.",
        f"Thresholds: {dates}.",
        f"Control fields supplied thresholds only and were not compared. Of {record['observations']} measured observations, "
        f"{record['kept_observations']} were kept; the rest remain in the ledgers with their gate reason. "
        "The percentile was the researcher's recorded choice and was not tuned to the outcome. GFP was a selection, not a denominator.",
    ]

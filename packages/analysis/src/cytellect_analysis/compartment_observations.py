"""Per-nucleus compartment-summary observations (selection 1.0.0).

Turns the saved ``compartment-summary.json`` of a nucleoplasm revision derived from
adopted nucleoli into the same observation records the region adapters produce,
so the unchanged descriptive (per-field) and experimental-unit (field median ->
sample mean -> unit mean) protocols can consume them. Nothing is remeasured here:
the summary is bound to the reviewed nucleoplasm mask by exact region identity and
area, and every row is checked for internal arithmetic consistency. A row with a
missing reason is a missing observation with that reason, never zero.
"""
from __future__ import annotations

import hashlib
import json
import math
from types import SimpleNamespace
from typing import Any

from .compartment_summary import PROTOCOL as SUMMARY_PROTOCOL
from .descriptive import _metadata, prepare_region_observations
from .descriptive_contracts import CompartmentSummarySelection, RegionSelection
from .gfp_selection import GATE_KEYS, finish_gated_description, gate_source_observations

SELECTION_VERSION = "1.0.0"
LOG2 = "log2_nucleoplasm_over_nucleolus"
GEOMETRY_KEYS = ("nucleus_area_px", "nucleolar_count", "nucleolar_area_px", "nucleoplasm_area_px")
SUMMARY_REASONS = frozenset({"no_nucleolus", "no_nucleoplasm", "nonpositive_signal"})
UNITS = {LOG2: "log2 ratio", "nucleolar_area_fraction": "dimensionless",
         "nucleolar_count": "count"}
DEFINITIONS = {
    LOG2: ("log2(mean nucleoplasm intensity / mean nucleolar-union intensity) per parent nucleus, "
           "raw original pixels, no pseudocount (compartment-summary/1.0.0)"),
    "nucleolar_area_fraction": ("adopted nucleolar-union area / parent nucleus area per nucleus with at least one "
                                "adopted nucleolus (compartment-summary/1.0.0)"),
    "nucleolar_count": ("number of adopted nucleoli per nucleus with at least one adopted nucleolus "
                        "(compartment-summary/1.0.0)"),
}
SAFE_ERROR_CODES = frozenset({
    "compartment_summary_source_required", "compartment_summary_unavailable",
    "compartment_summary_coverage_mismatch", "compartment_summary_protocol_mismatch",
    "compartment_summary_channel_mismatch", "compartment_summary_background_unsupported",
    "compartment_summary_inconsistent", "compartment_summary_mask_mismatch",
    "compartment_summary_channel_required", "compartment_summary_channel_must_be_unset",
    "region_export_compartment_summary_unsupported",
})


def summary_sha256(document):
    data = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def require_compartment_source(recipe, region_set_id=None):
    if (not isinstance(recipe, dict) or recipe.get("source") != "fiji_nuclear_compartment"
            or recipe.get("compartment") != "nucleoplasm" or not recipe.get("nucleolar_revision_id")
            or (region_set_id is not None and recipe.get("region_set_id") != region_set_id)):
        raise ValueError("compartment_summary_source_required")


def _integer(value, minimum=0):
    return type(value) is int and value >= minimum


def _validated_rows(document, channel_ids):
    if not isinstance(document, dict) or not isinstance(document.get("channels"), dict):
        raise ValueError("compartment_summary_inconsistent")
    if set(document["channels"]) != set(channel_ids):
        raise ValueError("compartment_summary_channel_mismatch")
    tables: dict[str, dict[int, dict[str, Any]]] = {}
    for channel_id, summary in document["channels"].items():
        if not isinstance(summary, dict) or summary.get("protocol") != SUMMARY_PROTOCOL:
            raise ValueError("compartment_summary_protocol_mismatch")
        rows: dict[int, dict[str, Any]] = {}
        for row in summary.get("rows", []):
            if row.get("values") != "raw" or row.get("background") is not None:
                raise ValueError("compartment_summary_background_unsupported")
            nid = row.get("nucleus_id")
            if not _integer(nid, 1) or nid in rows or not all(_integer(row.get(key)) for key in GEOMETRY_KEYS):
                raise ValueError("compartment_summary_inconsistent")
            nucleus, union, plasm = row["nucleus_area_px"], row["nucleolar_area_px"], row["nucleoplasm_area_px"]
            reason = row.get("missing_reason")
            # A candidate parent is split exactly; a candidate-free parent has no nucleoplasm (protocol 1.0.1).
            if (nucleus <= 0 or (union + plasm != nucleus if union else plasm != 0)
                    or (union == 0) != (row["nucleolar_count"] == 0)
                    or row.get("nucleolar_area_fraction") != union / nucleus
                    or (reason is not None and reason not in SUMMARY_REASONS)
                    or (reason == "no_nucleolus") != (union == 0)
                    or (reason == "no_nucleoplasm") != (union > 0 and plasm == 0)):
                raise ValueError("compartment_summary_inconsistent")
            log2 = row.get(LOG2)
            if reason is None:
                plasm_mean, nucleolar_mean = row.get("nucleoplasm_mean"), row.get("nucleolar_mean")
                if (any(isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
                        for v in (plasm_mean, nucleolar_mean, log2))
                        or plasm_mean <= 0 or nucleolar_mean <= 0
                        or log2 != math.log2(plasm_mean / nucleolar_mean)):
                    raise ValueError("compartment_summary_inconsistent")
            elif log2 is not None:
                raise ValueError("compartment_summary_inconsistent")
            rows[nid] = row
        tables[channel_id] = rows
    geometry = {json.dumps({nid: [row[key] for key in GEOMETRY_KEYS] for nid, row in sorted(rows.items())})
                for rows in tables.values()}
    if len(geometry) > 1:
        raise ValueError("compartment_summary_channel_mismatch")
    return tables


def prepare_compartment_observations(report, field_snapshot, selector, summaries):
    """Validate the reviewed nucleoplasm source and bind each field's summary to its mask.

    ``summaries`` maps every measured field to its saved compartment-summary.json.
    Returns ``(observations, source_fields, unit, excluded_failed_fields)`` with the
    same record shape as :func:`prepare_region_observations`.
    """
    selector = CompartmentSummarySelection.model_validate(selector)
    require_compartment_source(report.get("recipe"), selector.region_set_id)
    regions, fields, _, excluded = prepare_region_observations(report, field_snapshot, RegionSelection(
        source="region", region_set_id=selector.region_set_id, channel_id=None, metric="area_px"))
    summaries = summaries or {}
    if set(summaries) != {field["field_id"] for field in fields}:
        raise ValueError("compartment_summary_unavailable" if not summaries else "compartment_summary_coverage_mismatch")
    by_region = {(row["field_id"], row["region_id"]): row for row in regions}
    field_exclusions = {item["field_id"]: item["reason"] for item in report.get("exclusions", [])
                        if item.get("region_id") is None}
    observations = []
    for field in fields:
        fid = field["field_id"]
        channel_ids = [item["channel"]["channel_id"] for item in field["channel_provenance"]]
        if selector.channel_id is not None and selector.channel_id not in channel_ids:
            raise ValueError("descriptive_channel_identity_mismatch")
        document = summaries[fid]
        tables = _validated_rows(document, channel_ids)
        rows = tables[selector.channel_id if selector.channel_id is not None else sorted(tables)[0]]
        plasm = {nid: row["nucleoplasm_area_px"] for nid, row in rows.items() if row["nucleoplasm_area_px"] > 0}
        measured = {rid: int(row["value"]) for (f, rid), row in by_region.items() if f == fid}
        if plasm != measured:
            raise ValueError("compartment_summary_mask_mismatch")
        field["compartment_summary"] = {
            "protocol": SUMMARY_PROTOCOL, "selection_version": SELECTION_VERSION,
            "sha256": summary_sha256(document), "nucleolar_revision": document.get("nucleolar_revision"),
            "nuclei": len(rows)}
        for nid, row in sorted(rows.items()):
            if selector.metric == LOG2:
                value, reason = row[LOG2], row.get("missing_reason")
            elif row["nucleolar_area_px"] == 0:
                # A candidate-free parent does not establish zero nucleoli (protocol 1.0.1).
                value, reason = None, "no_nucleolus"
            else:
                value, reason = float(row[selector.metric]), None
            base = by_region.get((fid, nid))
            exclusion = base["exclusion_reason"] if base is not None else field_exclusions.get(fid)
            observations.append({
                "observation_id": json.dumps([fid, selector.region_set_id, nid], separators=(",", ":")),
                "field_id": fid, "region_id": nid, "nucleus_id": nid, "region_set_id": selector.region_set_id,
                "mask_revision_id": field["region_set"]["mask_revision_id"],
                "analysis_revision_id": field["analysis_revision_id"], "channel_id": selector.channel_id,
                **_metadata(field_snapshot[fid]), "value": value, "excluded": bool(exclusion),
                "exclusion_reason": exclusion, "gate_selected": True,
                "missing_reason": reason if value is None else None})
    return observations, fields, UNITS[selector.metric], excluded


def compartment_comparison_source(report, config, selection, summaries):
    """Same review/source gates as region comparisons, then compartment observations."""
    from .region_comparison import _source

    area = RegionSelection(source="region", region_set_id=selection.region_set_id, channel_id=None, metric="area_px")
    snapshot, *_ = _source(report, config, SimpleNamespace(selection=area))
    require_compartment_source(config.get("recipe"), selection.region_set_id)
    observations, sources, unit, failed = prepare_compartment_observations(report, snapshot, selection, summaries)
    return snapshot, observations, sources, unit, failed


def acquisition_proxy(request):
    """Acquisition review semantics: the ratio is an intensity outcome (batches, one
    dtype, no condition-confounded batches); count and fraction depend on sampling
    like pixel area (explicit equal-sampling confirmation, one calibration)."""
    proxy = "mean" if request.selection.metric == LOG2 else "area_px"
    return SimpleNamespace(acquisition_review=request.acquisition_review, design=request.design,
                           conditions=request.conditions, comparison_family=request.comparison_family,
                           selection=SimpleNamespace(metric=proxy, channel_id=request.selection.channel_id))


def describe_compartment_summary(report, field_snapshot, request, summaries, nuclear=None):
    """``nuclear`` is the adopted nuclear source required by a GFP nucleus filter."""
    from .descriptive import _finish, _request

    request = _request(request, "compartment-summary")
    observations, fields, unit, excluded = prepare_compartment_observations(
        report, field_snapshot, request.selection, summaries)
    record = None
    if request.selection.gfp_gate is not None:
        observations, record = gate_source_observations(report, report.get("recipe"), field_snapshot, request.selection,
                                                        observations, excluded, summaries, nuclear)
    result = _finish(observations, fields, request, "region-2d", "nuclei", unit, excluded,
                     () if record is None else GATE_KEYS)
    result["metric_definition"] = f"{DEFINITIONS[request.selection.metric]}; per-field observed values"
    if request.selection.metric == LOG2:
        result["warnings"].append("nucleolar_union_saturation_not_assessed")
    if record is not None:
        finish_gated_description(result, record)
    return result

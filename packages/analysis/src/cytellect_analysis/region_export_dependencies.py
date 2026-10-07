"""Pinned parent masks for original-pixel replay of compartment/GFP measurements."""
import json
from copy import deepcopy

import numpy as np

from .compartment_summary import compartment_summary
from .masks import polygon_mask, validate_label_array
from .region_contracts import (
    RegionAnalysisRequest,
    RegionImageInfo,
    region_report_from_json,
    scientific_specification,
    validate_region_report_policy,
)
from .region_measurement_v2 import measure_regions_versioned
from .regions import _array_hash


def checked_parent(entry, kind, shape):
    record = entry[kind]
    labels = entry[kind + "_labels"]
    validate_label_array(labels)
    identity = record["identity"]
    if list(labels.shape) != shape or _array_hash(labels, "<u4") != identity["mask_sha256"]:
        raise ValueError("region_bundle_parent_mask_mismatch")
    effective = labels.copy()
    exclusions = identity["exclusions"]
    if any(item["region_id"] is None for item in exclusions):
        raise ValueError("region_bundle_parent_excluded")
    effective[np.isin(labels, [item["region_id"] for item in exclusions])] = 0
    if _array_hash(effective, "<u4") != identity["effective_mask_sha256"]:
        raise ValueError("region_bundle_parent_mask_mismatch")
    return labels, effective


def inputs(dependencies, report, config):
    """Validate dependency identity before using its table or automatic exclusion."""
    nuclear, summaries, exclusions = {}, {}, {}
    for fid, entry in dependencies.items():
        if fid not in report["field_tables"]:
            raise ValueError("region_bundle_parent_field_mismatch")
        shape = config["field_snapshot"][fid]["image_info"]["shape"]
        labels, _ = checked_parent(entry, "nuclear", shape)
        source = entry["nuclear"]
        validate_region_report_policy(region_report_from_json(json.dumps(source["report"])), source["config"])
        original = source["config"]["field_snapshot"][fid]["image_info"]
        if original != config["field_snapshot"][fid]["image_info"]:
            raise ValueError("region_bundle_parent_image_mismatch")
        identity, table = source["identity"], source["report"]["field_tables"][fid]
        mask = source["report"]["field_masks"][fid]
        if (source["report"]["revision_id"] != identity["revision_id"]
                or mask["mask_revision_id"] != identity["mask_revision_id"]
                or mask["mask_sha256"] != identity["mask_sha256"]
                or [row for row in source["report"]["exclusions"] if row["field_id"] == fid] != identity["exclusions"]):
            raise ValueError("region_bundle_parent_identity_mismatch")
        nuclear[fid] = {"revision_id": identity["revision_id"], "report_sha256": source["report_sha256"],
                        "mask_revision_id": identity["mask_revision_id"], "mask_sha256": identity["mask_sha256"],
                        "table": table, "exclusions": identity["exclusions"], "image_info": original}
        exclusions[fid] = labels
        if "summary" in entry:
            checked_parent(entry, "nucleolar", shape)
            if entry["summary"].get("nucleolar_revision") != entry["nucleolar"]["identity"]:
                raise ValueError("region_bundle_parent_identity_mismatch")
            summaries[fid] = entry["summary"]
    return ({"binding": "parent_nucleus", "fields": nuclear} if nuclear else None), summaries, exclusions


def replay_field(entry, fid, channels, labels, measured):
    """Recalculate every numerical dependency; saved source tables are assertions only."""
    result = deepcopy(entry)
    original = result["nuclear"]
    config, report = original["config"], original["report"]
    request = RegionAnalysisRequest.model_validate({key: config[key] for key in
        ("field_ids", "recipe", "backgrounds", "exclusions", "measurement") if key in config})
    info = RegionImageInfo.model_validate(config["field_snapshot"][fid]["image_info"])
    raw_nuclei, nuclei = checked_parent(result, "nuclear", list(labels.shape))
    backgrounds = {cid: polygon_mask(labels.shape, bg.polygon) for cid, bg in request.backgrounds.get(fid, {}).items()}
    table = measure_regions_versioned(channels, raw_nuclei, backgrounds, scientific_specification(
        field_id=fid, revision_id=report["revision_id"], mask_revision_id=original["identity"]["mask_revision_id"],
        recipe=request.recipe, image_info=info, measurement=request.measurement)).model_dump(mode="json")
    if table != report["field_tables"][fid]:
        raise ValueError("region_bundle_parent_measurement_mismatch")
    report["field_tables"][fid] = table
    if "summary" in result:
        _, nucleoli = checked_parent(result, "nucleolar", list(labels.shape))
        summary = {"nucleolar_revision": result["nucleolar"]["identity"],
                   "channels": {cid: compartment_summary(nuclei, nucleoli, labels, pixels)
                                for cid, pixels in channels.items()}}
        if measured.protocol_version == "4.0.0":
            summary["corrected_channels"] = {item.channel.channel_id:
                compartment_summary(nuclei, nucleoli, labels, channels[item.channel.channel_id], item.background.background_median)
                if item.background.status == "established" else
                {"protocol": "compartment-summary/1.0.0", "rows": [], "missing_reason": item.background.reason}
                for item in measured.channel_provenance}
            summary["background"] = "automatic_candidate"
        if summary != result["summary"]:
            raise ValueError("region_bundle_compartment_summary_mismatch")
        result["summary"] = summary
    return result

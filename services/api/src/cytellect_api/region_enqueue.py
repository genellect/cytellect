"""Shared validated region submission for HTTP and persistent workspace orchestration."""
import time
from contextlib import nullcontext
from copy import deepcopy

from cytellect_analysis.engine import nuclear_detection_shape
from cytellect_analysis.masks import polygon_mask
from cytellect_analysis.region_contracts import (
    RegionCellposeRecipe,
    RegionCompartmentRecipe,
    RegionImageInfo,
    region_request_config,
    validate_nuclear_role_evidence,
)
from fastapi import HTTPException
from sqlalchemy import func, select, update

from .channel_assignments import (
    apply_channel_assignments,
    assignments_at,
    effective_assignments,
    validate_assigned_roles,
)
from .db import fields, jobs, revisions, uid, workspaces
from .mask_dependencies import can_rebind_compartment
from .planning import bind_revision_plan, inherit_plan_resolution
from .storage import read_json


def enqueue_region_job(conn, settings, wid, rid):
    count = conn.execute(select(func.count()).select_from(jobs).where(jobs.c.state.in_(["queued", "running"]))).scalar_one()
    if count >= 10:
        raise HTTPException(429, "queue_full")
    jid = uid()
    conn.execute(jobs.insert().values(id=jid, workspace_id=wid, revision_id=rid, kind="analysis", state="queued", payload={}, created=time.time(), attempts=0))
    conn.execute(update(workspaces).where(workspaces.c.id == wid).values(expires=time.time() + settings.retention_seconds))
    return jid


def validate_region_request(store, body, selected, reused_masks=()):
    ids = {f["id"] for f in selected}
    if not ids:
        raise HTTPException(422, "images_required")
    if set(body.backgrounds) - ids or any(e.field_id not in ids for e in body.exclusions):
        raise HTTPException(422, "unknown_region_field")
    excluded = {e.field_id for e in body.exclusions if e.region_id is None}
    for f in selected:
        info = RegionImageInfo.model_validate(f["image_info"])
        try:
            validate_nuclear_role_evidence(body.recipe, info)
        except ValueError as error:
            raise HTTPException(422, str(error)) from None
        channels = {c.channel_id for c in info.channels}
        if body.recipe.defining_channel_id is not None and body.recipe.defining_channel_id not in channels:
            raise HTTPException(422, "unknown_defining_channel")
        if body.recipe.source == "imported" and info.labels_array is None:
            raise HTTPException(422, "region_labels_required")
        if body.recipe.source == "manual" and info.labels_array is not None:
            raise HTTPException(422, "manual_region_source_requires_no_imported_labels")
        if isinstance(body.recipe, RegionCompartmentRecipe) or (isinstance(body.recipe, RegionCellposeRecipe) and body.recipe.nuclear_revision_id is not None):
            source = store.one(revisions, id=body.recipe.nuclear_revision_id)
            if (not source or source["workspace_id"] != f["workspace_id"] or source["state"] != "succeeded"
                    or not source["result_dir"] or source["config"].get("analysis_kind") != "region-2d"
                    or source["config"].get("recipe", {}).get("source") != "stardist_nuclear"
                    or source["config"]["recipe"].get("defining_channel_id") != body.recipe.nuclear_channel_id):
                raise HTTPException(422, "compartment_nuclear_source_invalid")
            original = source["config"].get("field_snapshot", {}).get(f["id"])
            if original is None or original["image_info"] != f["image_info"]:
                raise HTTPException(422, "compartment_source_image_mismatch")
            report = read_json(store.safe_path(source["result_dir"], "measurements.json"))
            if f["id"] not in report.get("field_tables", {}) or f["id"] not in report.get("field_masks", {}):
                raise HTTPException(422, "compartment_nuclear_source_invalid")
        if body.recipe.source == "fiji_positive_regions" and info.labels_array is not None:
            raise HTTPException(422, "signal_source_requires_no_imported_labels")
        if body.recipe.source == "cellpose_cell" and info.labels_array is not None:
            raise HTTPException(422, "cellpose_source_requires_no_imported_labels")
        if body.recipe.source == "stardist_nuclear":
            if info.labels_array is not None:
                raise HTTPException(422, "nuclear_source_requires_no_imported_labels")
            if f["id"] not in reused_masks:
                # Only detection is bounded; saved labels and measurement
                # pixels retain the original coordinates and resolution.
                nuclear_detection_shape((info.shape[0], info.shape[1]))
        if f["id"] in excluded:
            continue
        if body.measurement is not None:
            # The request model requires exactly {} for area-only; absence
            # of background is never converted into a zero-valued ROI.
            continue
        if any(channel.get("identity_confirmed") is not True for channel in f["image_info"]["channels"]):
            raise HTTPException(422, "confirmed_channels_required_for_corrected_protocol")
        backgrounds = body.backgrounds.get(f["id"], {})
        if set(backgrounds) != channels:
            raise HTTPException(422, "confirm_background_for_every_channel")
        for bg in backgrounds.values():
            polygon_mask(info.shape, bg.polygon)

def enqueue_region(store, settings, wid, body, *, conn=None, activate=True):
    workspace_record = store.one(workspaces, id=wid)
    if not workspace_record or workspace_record["deleted"] or workspace_record["expires"] <= time.time():
        raise HTTPException(404, "workspace_not_found")
    selected = [dict(f) for f in store.rows(fields, workspace_id=wid) if f["image_info"].get("kind") == "region-2d"]
    if body.field_ids is not None:
        if set(body.field_ids) - {f["id"] for f in selected}:
            raise HTTPException(422, "unknown_region_field")
        selected = [f for f in selected if f["id"] in body.field_ids]
    with store.engine.connect() as read_conn:
        assignment_snapshot = assignments_at(read_conn, wid)
    for field in selected:
        validate_assigned_roles(body.recipe, effective_assignments(assignment_snapshot, field["id"]))
    selected = apply_channel_assignments(store, wid, selected, assignment_snapshot=assignment_snapshot)
    parent = None
    reused_masks = ()
    if body.reuse_revision:
        parent = store.one(revisions, id=body.reuse_revision)
        if not parent or parent["state"] != "succeeded" or not parent["result_dir"]:
            raise HTTPException(409, "parent_revision_unavailable")
        if parent["workspace_id"] != wid:
            raise HTTPException(404, "revision_not_found")
        root = store.safe_path(parent["result_dir"])
        if not set(parent["config"]["field_ids"]).issubset({f["id"] for f in selected}):
            raise HTTPException(409, "batch_must_include_reused_fields")
        if (parent["config"]["recipe"] != body.recipe.model_dump(mode="json")
                and not can_rebind_compartment(store, parent["config"]["recipe"], body.recipe.model_dump(mode="json"),
                                               wid, [f["id"] for f in selected])):
            raise HTTPException(409, "batch_reuse_requires_unchanged_recipe")
        # Experimental metadata is versioned in snapshots, not rewritten on
        # the original upload row. Expanding a trial retains its adopted data.
        previous = parent["config"]["field_snapshot"]
        def same_channels(current, prior):
            if current == prior:
                return True
            if not body.confirmed_channel_ids and not all(channel.get("identity_confirmed") is True for channel in prior):
                return False
            # A deliberate background save confirms identity evidence, not different pixels/stains.
            def identity(values):
                return [{key: value for key, value in channel.items() if key not in ("identity_confirmed", "identity_source")} for channel in values]
            return identity(current) == identity(prior)
        if any(f["id"] in previous and not same_channels(f["image_info"]["channels"], previous[f["id"]]["image_info"]["channels"]) for f in selected):
            raise HTTPException(409, "batch_reuse_channel_assignments_changed")
        selected = [deepcopy(previous[f["id"]]) if f["id"] in previous else f for f in selected]
        reused_masks = read_json(root / "measurements.json").get("field_masks", {})
    if body.confirmed_channel_ids:
        for field in selected:
            declared = {entry["channel_id"]: entry for entry in effective_assignments(assignment_snapshot, field["id"])["assignments"]}
            registered_ids = {channel["channel_id"] for channel in field["image_info"]["channels"]}
            field_backgrounds = body.backgrounds.get(field["id"], {})
            # Saving a polygon against an existing channel image confirms that
            # image/ROI association; it does not identify its unknown stain.
            if any(cid not in registered_ids or cid not in field_backgrounds
                   or not field_backgrounds[cid].confirmed
                   or declared.get(cid, {}).get("role") == "unused"
                   for cid in body.confirmed_channel_ids):
                raise HTTPException(422, "background_channel_identity_required")
            for channel in field["image_info"]["channels"]:
                if channel["channel_id"] in body.confirmed_channel_ids:
                    channel.pop("identity_source", None)
                    channel["identity_confirmed"] = True
    validate_region_request(store, body, selected, reused_masks)
    rid = uid()
    config = {**region_request_config(body), "analysis_kind": "region-2d",
              "field_ids": [f["id"] for f in selected], "field_snapshot": {f["id"]: f for f in selected}}
    if assignment_snapshot["version"]:
        config["channel_assignments"] = assignment_snapshot
    if parent is not None and "plan_resolution" not in body.model_fields_set:
        inherit_plan_resolution(config, parent["config"])
    bind_revision_plan(config, workspace_record.get("analysis_plan"),
                       parent_config=parent["config"] if parent is not None else None)
    with (store.transaction() if conn is None else nullcontext(conn)) as conn:
        if assignments_at(conn, wid) != assignment_snapshot:
            raise HTTPException(409, "channel_assignments_changed")
        w = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
        if activate and parent is not None and w["active_revision"] != parent["id"]:
            raise HTTPException(409, "stale_revision")
        jid = enqueue_region_job(conn, settings, wid, rid)
        conn.execute(revisions.insert().values(id=rid, workspace_id=wid, parent_id=w["active_revision"],
                     config=config, state="queued", reviewed=False, created=time.time()))
        if activate:
            conn.execute(update(workspaces).where(workspaces.c.id == wid).values(active_revision=rid))
    return {"revision_id": rid, "job_id": jid}

"""Assemble explicit saved field results into an unreviewed immutable cohort."""
import hashlib
import json
import time
from copy import deepcopy
from typing import Annotated

from cytellect_analysis.compartment_review import assert_complete_compartments, comparable_region_recipe
from cytellect_analysis.images import sha256
from cytellect_analysis.region_contracts import (
    RegionAnalysisRequest,
    RegionFieldMetadata,
    region_report_from_json,
    region_request_config,
    validate_region_report_policy,
)
from cytellect_analysis.regions import Id, RegionModel
from fastapi import Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, update

from .db import fields, jobs, revisions, uid, workspace_selections, workspaces
from .regions import is_region
from .storage import read_json
from .workspace_selection import WorkspaceSelection, assert_selection


class CohortSource(RegionModel):
    field_id: Id
    revision_id: Id


class RegionCohortRequest(RegionModel):
    sources: Annotated[list[CohortSource], Field(min_length=1, max_length=100)]
    metadata: Annotated[dict[Id, RegionFieldMetadata], Field(min_length=1, max_length=100)]
    expected_active_revision_id: Id | None
    workspace_selection: WorkspaceSelection | None = None

    @model_validator(mode="after")
    def complete_metadata(self):
        ids = [source.field_id for source in self.sources]
        if len(set(ids)) != len(ids) or set(ids) != set(self.metadata):
            raise ValueError("cohort_field_metadata_mismatch")
        return self


def register_region_cohort_routes(api, store, owner, workspace, revision, result_root, queue):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/revisions/{rid}/workspace-selection", response_model=WorkspaceSelection)
    def saved_selection(rid: str, who: Owner):
        saved = revision(rid, who)
        adoption = saved["config"].get("workspace_selection")
        if not adoption:
            raise HTTPException(404, "workspace_selection_not_found")
        return adoption

    @api.post("/v1/workspaces/{wid}/region-cohorts", status_code=202)
    def assemble(wid: str, body: RegionCohortRequest, who: Owner):
        workspace(wid, who)
        registered = {row["id"]: row for row in store.rows(fields, workspace_id=wid)}
        ids = {source.field_id for source in body.sources}
        adoption = body.workspace_selection.model_dump(mode="json") if body.workspace_selection else None
        excluded_ids = {entry["field_id"] for entry in adoption["entries"] if entry["exclusion_reason"] and entry["field_id"]} if adoption else set()
        if adoption:
            included = {entry["field_id"]: entry["revision_id"] for entry in adoption["entries"] if not entry["exclusion_reason"]}
            if included != {source.field_id: source.revision_id for source in body.sources} or None in included:
                raise HTTPException(409, "workspace_selection_incomplete")
        if ids | excluded_ids != set(registered) or ids & excluded_ids or any(not is_region(row) for row in registered.values()):
            raise HTTPException(409, "cohort_all_workspace_fields_required")
        snapshot, pins, source_records = {}, {}, {}
        exclusions: list[dict] = []
        recipe = policy = None
        for source in sorted(body.sources, key=lambda item: item.field_id):
            saved = revision(source.revision_id, who)
            if saved["workspace_id"] != wid or not is_region(saved):
                raise HTTPException(404, "revision_not_found")
            root = result_root(saved)
            config = saved["config"]
            fid = source.field_id
            if fid not in config.get("field_snapshot", {}):
                raise HTTPException(409, "cohort_source_field_missing")
            if config.get("measurement") != {"version": "1.1.0", "mode": "raw_intensity"} or config.get("backgrounds"):
                raise HTTPException(409, "cohort_raw_measurement_required")
            if recipe is not None and (comparable_region_recipe(config["recipe"]) != comparable_region_recipe(recipe) or config["measurement"] != policy):
                raise HTTPException(409, "cohort_recipe_mismatch")
            recipe, policy = config["recipe"], config["measurement"]
            try:
                report = read_json(root / "measurements.json")
                validate_region_report_policy(region_report_from_json(json.dumps(report)), config)
                if config["recipe"].get("source") == "fiji_nuclear_compartment":
                    assert_complete_compartments(config, report, read_json(root / "provenance.json"), [fid])
            except (ValueError, OSError):
                raise HTTPException(409, "cohort_source_invalid") from None
            if fid not in report["field_tables"] or fid not in report["field_masks"]:
                raise HTTPException(409, "cohort_source_field_not_measured")
            original = config["field_snapshot"][fid]
            if original["image_info"] != registered[fid]["image_info"]:
                raise HTTPException(409, "cohort_source_image_changed")
            mask = report["field_masks"][fid]
            pins[fid] = {"revision_id": saved["id"], "mask_revision_id": mask["mask_revision_id"],
                         "mask_sha256": mask["mask_sha256"], "report_sha256": sha256(root / "measurements.json"),
                         "provenance_sha256": sha256(root / "provenance.json")}
            source_records[saved["id"]] = saved
            snapshot[fid] = {**deepcopy(original), "metadata": body.metadata[fid].model_dump(mode="json")}
            exclusions.extend(item for item in config.get("exclusions", []) if item["field_id"] == fid)
        request = RegionAnalysisRequest.model_validate({"field_ids": sorted(ids), "recipe": recipe, "measurement": policy,
                                                       "backgrounds": {}, "exclusions": exclusions})
        config = {**region_request_config(request), "analysis_kind": "region-2d",
                  "field_snapshot": snapshot, "cohort_sources": pins, "cohort_version": "1.0.0"}
        if adoption:
            config["workspace_selection"] = adoption
        fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        config["cohort_request_sha256"] = fingerprint
        with store.transaction() as conn:
            live = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
            if live["deleted"] or live["expires"] <= time.time() or live["owner"] != who:
                raise HTTPException(404, "workspace_not_found")
            if adoption:
                assert_selection(conn, wid, adoption)
            elif conn.execute(select(workspace_selections.c.workspace_id).where(workspace_selections.c.workspace_id == wid)).first():
                raise HTTPException(409, "workspace_selection_required")
            # Same request after response loss can recover its queued/completed job.
            existing = conn.execute(select(revisions).where(revisions.c.workspace_id == wid,
                revisions.c.state.in_(["queued", "running", "succeeded"]))).mappings().all()
            for item in existing:
                if (item["config"].get("cohort_request_sha256") == fingerprint and not item["config"].get("reuse_revision")
                        and live["active_revision"] in (body.expected_active_revision_id, item["id"])):
                    job = conn.execute(select(jobs).where(jobs.c.revision_id == item["id"], jobs.c.kind == "analysis")).mappings().first()
                    if job:
                        return {"revision_id": item["id"], "job_id": job["id"]}
            if live["active_revision"] != body.expected_active_revision_id:
                raise HTTPException(409, "stale_revision")
            if set(conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars()) != ids | excluded_ids:
                raise HTTPException(409, "cohort_all_workspace_fields_required")
            # Recheck immutable source identity under the same write lock as enqueue.
            for sid, expected in source_records.items():
                current = conn.execute(select(revisions).where(revisions.c.id == sid)).mappings().first()
                if (not current or current["workspace_id"] != wid or current["state"] != "succeeded"
                        or current["result_dir"] != expected["result_dir"] or current["config"] != expected["config"]):
                    raise HTTPException(409, "cohort_source_changed")
            rid = uid()
            conn.execute(revisions.insert().values(id=rid, workspace_id=wid, parent_id=live["active_revision"],
                         config=config, state="queued", reviewed=False, created=time.time()))
            jid = queue(conn, wid, rid, "analysis", {})
            conn.execute(update(workspaces).where(workspaces.c.id == wid).values(active_revision=rid))
        return {"revision_id": rid, "job_id": jid}

"""Assemble explicit saved field results into an unreviewed immutable cohort."""
import hashlib
import json
import time
from copy import deepcopy
from typing import Annotated, Literal

from cytellect_analysis.compartment_review import assert_complete_compartments, comparable_region_recipe
from cytellect_analysis.experiment_strata import CohortStratum, check_cohort_stratum, design_sha256
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

from .analysis_spec import saved_experiment
from .channel_assignments import apply_channel_assignments, effective_assignments
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
    # Unresolved-nucleoli policy (Q-05): nuclei without an established nucleolus stay as missing;
    # the review then confirms the per-field list. Absent: every parent must be resolved, as before.
    compartment_missing: Literal["unresolved-as-missing/1.0.0"] | None = None
    # Experiment design 1.1.0: the one declared stratum this cohort holds (required for such a design).
    stratum: CohortStratum | None = None

    @model_validator(mode="after")
    def complete_metadata(self):
        ids = [source.field_id for source in self.sources]
        if len(set(ids)) != len(ids) or set(ids) != set(self.metadata):
            raise ValueError("cohort_field_metadata_mismatch")
        return self


def image_identity(info):
    """Confirmation evidence may evolve; pixels and acquisition identity may not."""
    return {**info, "channels": [{key: value for key, value in channel.items()
                                  if key not in ("identity_source", "identity_confirmed")}
                                 for channel in info["channels"]]}


def channel_meanings(config, fid):
    info = config["field_snapshot"][fid]["image_info"]
    assignment = config.get("channel_assignments", {"version": 0, "assignments": []})
    roles = {item["channel_id"]: item["role"] for item in effective_assignments(assignment, fid)["assignments"]}
    channels = {channel["channel_id"]: {**{key: value for key, value in channel.items()
                if key not in ("label", "identity_source", "identity_confirmed")},
                "role": roles.get(channel["channel_id"])} for channel in info["channels"]}
    return {"input_mode": info.get("input_mode", "native"), "channels": channels}


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
        # An image that never became a field (failed upload) must carry a reason, whichever fields the
        # cohort holds: it is checked before the entries are narrowed to a stratum.
        if adoption and any(entry["field_id"] is None and not entry["exclusion_reason"] for entry in adoption["entries"]):
            raise HTTPException(409, "workspace_selection_incomplete")
        with store.engine.connect() as conn:
            design = saved_experiment(conn, wid)
        try:
            reasons = {entry["field_id"]: entry["exclusion_reason"] for entry in (adoption or {}).get("entries", [])
                       if entry["field_id"] and entry["exclusion_reason"]}
            stratum = check_cohort_stratum(design, body.stratum, ids, excluded_ids,
                                           {fid: value.model_dump(mode="json") for fid, value in body.metadata.items()},
                                           exclusion_reasons=reasons, registered_ids=set(registered))
        except ValueError as exc:
            raise HTTPException(409, str(exc)) from None
        # A stratified cohort holds exactly one declared stratum; otherwise every workspace field, as before.
        scope = set(stratum["field_ids"]) if stratum else set(registered)
        if adoption:
            included = {entry["field_id"]: entry["revision_id"] for entry in adoption["entries"]
                        if not entry["exclusion_reason"] and entry["field_id"] in scope}
            if included != {source.field_id: source.revision_id for source in body.sources}:
                raise HTTPException(409, "workspace_selection_incomplete")
        if (ids | (excluded_ids & scope) != scope or not scope <= set(registered) or ids & excluded_ids
                or any(not is_region(registered[fid]) for fid in scope)):
            raise HTTPException(409, "cohort_all_workspace_fields_required")
        snapshot, pins, source_records, backgrounds = {}, {}, {}, {}
        exclusions: list[dict] = []
        recipe = policy = meanings = None
        for source in sorted(body.sources, key=lambda item: item.field_id):
            saved = revision(source.revision_id, who)
            if saved["workspace_id"] != wid or not is_region(saved):
                raise HTTPException(404, "revision_not_found")
            root = result_root(saved)
            config = saved["config"]
            fid = source.field_id
            if fid not in config.get("field_snapshot", {}):
                raise HTTPException(409, "cohort_source_field_missing")
            if recipe is not None and (comparable_region_recipe(config["recipe"]) != comparable_region_recipe(recipe) or config.get("measurement") != policy):
                raise HTTPException(409, "cohort_recipe_mismatch")
            recipe, policy = config["recipe"], config.get("measurement")
            current_meanings = channel_meanings(config, fid)
            if meanings is not None and current_meanings != meanings:
                raise HTTPException(409, "cohort_channel_identity_mismatch")
            meanings = current_meanings
            try:
                report = read_json(root / "measurements.json")
                validate_region_report_policy(region_report_from_json(json.dumps(report)), config)
                provenance = read_json(root / "provenance.json") if config["recipe"].get("source") == "fiji_nuclear_compartment" else None
            except (ValueError, OSError):
                raise HTTPException(409, "cohort_source_invalid") from None
            if provenance is not None:
                # A nucleus whose nucleolus was not found (or not resolved) leaves the compartment
                # incomplete; the researcher has to see which condition blocks the statistics.
                try:
                    assert_complete_compartments(config, report, provenance, [fid], policy=body.compartment_missing)
                except ValueError as exc:
                    # Under the policy a state that cannot be kept as missing keeps its own reason.
                    raise HTTPException(409, str(exc) if body.compartment_missing else "cohort_compartments_unresolved") from None
            if fid not in report["field_tables"] or fid not in report["field_masks"]:
                raise HTTPException(409, "cohort_source_field_not_measured")
            original = config["field_snapshot"][fid]
            registered_source = apply_channel_assignments(store, wid, [registered[fid]],
                assignment_snapshot=config.get("channel_assignments", {"version": 0, "assignments": []}))[0]
            if image_identity(original["image_info"]) != image_identity(registered_source["image_info"]):
                raise HTTPException(409, "cohort_source_image_changed")
            mask = report["field_masks"][fid]
            pins[fid] = {"revision_id": saved["id"], "mask_revision_id": mask["mask_revision_id"],
                         "mask_sha256": mask["mask_sha256"], "report_sha256": sha256(root / "measurements.json"),
                         "provenance_sha256": sha256(root / "provenance.json")}
            source_records[saved["id"]] = saved
            snapshot[fid] = {**deepcopy(original), "metadata": body.metadata[fid].model_dump(mode="json")}
            exclusions.extend(item for item in config.get("exclusions", []) if item["field_id"] == fid)
            if fid in config.get("backgrounds", {}):
                backgrounds[fid] = deepcopy(config["backgrounds"][fid])
        request = RegionAnalysisRequest.model_validate({"field_ids": sorted(ids), "recipe": recipe, "measurement": policy,
                                                       "backgrounds": backgrounds, "exclusions": exclusions})
        config = {**region_request_config(request), "analysis_kind": "region-2d",
                  "field_snapshot": snapshot, "cohort_sources": pins,
                  "cohort_version": "1.0.0" if policy == {"version": "1.1.0", "mode": "raw_intensity"} else "1.1.0"}
        if adoption:
            config["workspace_selection"] = adoption
        if body.compartment_missing is not None:
            config["compartment_missing"] = body.compartment_missing
        if stratum is not None:
            config["stratum"] = stratum
        fingerprint = hashlib.sha256(json.dumps(config, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        config["cohort_request_sha256"] = fingerprint
        with store.transaction() as conn:
            live = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
            if not store.workspace_is_live(live) or live["owner"] != who:
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
            present = set(conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars())
            if (not scope <= present) if stratum else present != ids | excluded_ids:
                raise HTTPException(409, "cohort_all_workspace_fields_required")
            # The saved design must still be the one the stratum was read from.
            current = saved_experiment(conn, wid)
            if stratum is not None and (current is None or design_sha256(current) != stratum["design_sha256"]):
                raise HTTPException(409, "cohort_stratum_design_changed")
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

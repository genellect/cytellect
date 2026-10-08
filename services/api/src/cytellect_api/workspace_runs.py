"""Durable workspace runs: queue dependencies on the worker and adopt only explicitly."""

import hashlib
import json
import time
from copy import deepcopy
from typing import Annotated, Any, Literal

from cytellect_analysis.regions import Id, RegionModel
from fastapi import Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, update

from .analysis_spec import analysis_spec_at
from .channel_assignments import assignments_at, effective_assignments
from .db import fields, jobs, revisions, uid, workspace_analysis_runs, workspace_selections, workspaces
from .mask_dependencies import can_rebind_compartment
from .region_enqueue import enqueue_region
from .storage import read_json
from .workspace_selection import revision_target, selection_at, update_target_adoption

Target = Literal["nuclei", "nucleoli", "nucleoplasm", "cell"]
DONE = {"succeeded", "reused", "failed", "blocked"}


class WorkspaceRunRequest(RegionModel):
    request_id: Id
    spec_version: int = Field(ge=1)
    target: Target
    purpose: Literal["preview", "measurement"] = "measurement"
    field_ids: list[Id] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len(set(self.field_ids)) != len(self.field_ids):
            raise ValueError("analysis_run_duplicate_field")
        return self


def run_view(row):
    return {
        key: row[key]
        for key in ("id", "workspace_id", "spec_version", "target", "state", "steps", "created", "updated")
    }


def request_fingerprint(body):
    return hashlib.sha256(
        json.dumps(body.model_dump(), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def adopted_for(conn, wid, fid, selection):
    entry: dict[str, Any] = next((value for value in selection["entries"] if value.get("field_id") == fid), {})
    targets = dict(entry.get("target_revisions", {}))
    if entry.get("revision_id"):
        rev = conn.execute(select(revisions).where(revisions.c.id == entry["revision_id"])).mappings().first()
        if rev and revision_target(rev):
            targets.setdefault(revision_target(rev), rev["id"])
    result = {}
    for target, rid in targets.items():
        row = conn.execute(select(revisions).where(revisions.c.id == rid)).mappings().first()
        if (
            row
            and row["workspace_id"] == wid
            and row["state"] == "succeeded"
            and row["config"].get("field_ids") == [fid]
        ):
            result[target] = dict(row)
    return result


def same_recipe(a, b):
    # Defaults are normalized by the same scientific request model before comparing.
    from cytellect_analysis.region_contracts import RegionAnalysisRequest
    from cytellect_analysis.region_policy import RawIntensityPolicy

    try:
        previous = RegionAnalysisRequest(
            recipe=a,
            field_ids=["comparison"],
            backgrounds={},
            measurement=RawIntensityPolicy(version="1.1.0", mode="raw_intensity"),
        )
        return previous.recipe.model_dump(mode="json") == b.model_dump(mode="json")
    except ValueError:
        return False


def advance_workspace_runs(store, settings):
    """One SQLite write lock fences step selection, job creation and step publication.

    No in-memory lease is needed: after a restart, committed queued jobs resume via
    the existing worker leases; uncommitted jobs and steps roll back together.
    """
    from .run_recipes import build_run_request

    progressed = False
    with store.transaction() as conn:
        active = (
            conn.execute(
                select(workspace_analysis_runs)
                .where(workspace_analysis_runs.c.state.in_(["queued", "running"]))
                .order_by(workspace_analysis_runs.c.created)
            )
            .mappings()
            .all()
        )
        for record in active:
            run = dict(record)
            wid = run["workspace_id"]
            steps = deepcopy(run["steps"])
            workspace = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().first()
            if not workspace or workspace["deleted"] or workspace["expires"] <= time.time():
                conn.execute(
                    update(workspace_analysis_runs)
                    .where(workspace_analysis_runs.c.id == run["id"])
                    .values(state="cancelled", updated=time.time())
                )
                continue
            changed = False
            for step in steps:
                if step["state"] == "queued":
                    job = conn.execute(select(jobs).where(jobs.c.id == step["job_id"])).mappings().first()
                    if job and job["state"] in ("succeeded", "failed", "cancelled"):
                        step["state"] = "failed" if job["state"] == "cancelled" else job["state"]
                        step["error"] = job.get("error") or (
                            "analysis_run_cancelled" if job["state"] == "cancelled" else None
                        )
                        if job["state"] == "succeeded":
                            report = read_json(store.safe_path(job["result_dir"], "measurements.json"))
                            if step["field_id"] not in report.get("field_tables", {}):
                                failure: dict[str, Any] = next(
                                    (value for value in report.get("field_failures", [])
                                     if value.get("field_id") == step["field_id"]), {}
                                )
                                step["state"], step["error"] = (
                                    "failed", failure.get("reason") or "analysis_run_field_failed"
                                )
                        changed = True
                if step["state"] != "pending":
                    continue
                preceding = [
                    value for value in steps[: steps.index(step)] if value["field_id"] == step["field_id"]
                ]
                if any(value["state"] in ("failed", "blocked") for value in preceding):
                    step.update(state="blocked", error="analysis_run_dependency_failed")
                    changed = True
                    continue
                if any(value["state"] not in ("reused", "succeeded") for value in preceding):
                    continue
                if assignments_at(conn, wid) != run["assignments_snapshot"]:
                    step.update(state="failed", error="channel_assignments_changed")
                    changed = True
                    continue
                parents = adopted_for(conn, wid, step["field_id"], run["selection_snapshot"])
                for earlier in preceding:
                    parents[earlier["target"]] = dict(
                        conn.execute(select(revisions).where(revisions.c.id == earlier["revision_id"]))
                        .mappings()
                        .one()
                    )
                try:
                    specification = run["spec_snapshot"]
                    source_field = (
                        conn.execute(select(fields).where(fields.c.id == step["field_id"])).mappings().one()
                    )
                    channel_ids = {value["channel_id"] for value in source_field["image_info"]["channels"]}
                    background_ids = set(specification.get("backgrounds", {}).get(step["field_id"], {}))
                    pending_background = specification["settings"]["background"] == "confirmed_roi" and (
                        not channel_ids.issubset(background_ids)
                        or not channel_ids.issubset(set(specification.get("confirmed_channel_ids", [])))
                    )
                    if step.get("purpose") == "preview" and pending_background:
                        specification = deepcopy(specification)
                        specification["settings"]["background"] = "raw"
                        specification["measurement"] = {"version": "1.1.0", "mode": "raw_intensity"}
                        specification["backgrounds"] = {}
                        specification["confirmed_channel_ids"] = []
                        step["background_pending"] = True
                    request = build_run_request(
                        specification,
                        step["target"],
                        step["field_id"],
                        parents,
                        effective_assignments(run["assignments_snapshot"], step["field_id"]),
                    )
                    existing = parents.get(step["target"])
                    def reusable_recipe(candidate):
                        return same_recipe(candidate["config"]["recipe"], request.recipe) or can_rebind_compartment(
                            store, candidate["config"]["recipe"], request.recipe.model_dump(mode="json"),
                            wid, [step["field_id"]],
                        )
                    # A selected-field preview can supply the same candidate to a later
                    # batch. An unchanged adopted mask (including corrections) wins.
                    if not existing or not reusable_recipe(existing):
                        previous_runs = (
                            conn.execute(
                                select(workspace_analysis_runs)
                                .where(
                                    workspace_analysis_runs.c.workspace_id == wid,
                                    workspace_analysis_runs.c.spec_version == run["spec_version"],
                                    workspace_analysis_runs.c.state == "succeeded",
                                    workspace_analysis_runs.c.id != run["id"],
                                )
                                .order_by(workspace_analysis_runs.c.created.desc())
                            )
                            .mappings()
                            .all()
                        )
                        for previous in previous_runs:
                            if (
                                previous["selection_snapshot"] != run["selection_snapshot"]
                                or previous["assignments_snapshot"] != run["assignments_snapshot"]
                            ):
                                continue
                            pin = next(
                                (
                                    value
                                    for value in previous["steps"]
                                    if value["field_id"] == step["field_id"]
                                    and value["target"] == step["target"]
                                    and value["state"] in ("succeeded", "reused")
                                    and (
                                        not value.get("background_pending") or step.get("background_pending")
                                    )
                                ),
                                None,
                            )
                            candidate = (
                                conn.execute(select(revisions).where(revisions.c.id == pin["revision_id"]))
                                .mappings()
                                .first()
                                if pin
                                else None
                            )
                            if (
                                candidate
                                and candidate["state"] == "succeeded"
                                and same_recipe(candidate["config"]["recipe"], request.recipe)
                            ):
                                existing = dict(candidate)
                                break
                    if (
                        existing
                        and reusable_recipe(existing)
                        and effective_assignments(
                            existing["config"].get("channel_assignments", {"version": 0, "assignments": []}),
                            step["field_id"],
                        )["assignments"]
                        == effective_assignments(run["assignments_snapshot"], step["field_id"])["assignments"]
                    ):
                        old_policy = existing["config"].get("measurement")
                        requested_policy = (
                            request.measurement.model_dump(mode="json") if request.measurement else None
                        )
                        if (
                            same_recipe(existing["config"]["recipe"], request.recipe)
                            and old_policy == requested_policy
                            and existing["config"].get("backgrounds", {})
                            == request.model_dump(mode="json")["backgrounds"]
                        ):
                            step.update(
                                state="reused",
                                revision_id=existing["id"],
                                recipe=existing["config"]["recipe"],
                                error=None,
                            )
                            changed = True
                            continue
                        request = type(request).model_validate(
                            {
                                **request.model_dump(mode="json"),
                                "reuse_revision": existing["id"],
                                "exclusions": existing["config"].get("exclusions", []),
                            }
                        )
                    submitted = enqueue_region(store, settings, wid, request, conn=conn, activate=False)
                    step.update(
                        state="queued", **submitted, recipe=request.recipe.model_dump(mode="json"), error=None
                    )
                    changed = True
                except HTTPException as error:
                    if error.status_code == 429:
                        continue
                    step.update(state="failed", error=str(error.detail))
                    changed = True
                except ValueError as error:
                    allowed = {"analysis_run_nuclear_parent_required", "analysis_run_nucleolar_marker_required",
                               "analysis_run_nucleolar_marker_unknown", "analysis_run_nucleolar_parent_required",
                               "analysis_run_background_confirmation_required"}
                    allowed.update({"analysis_run_cell_channel_required", "analysis_run_cell_channel_unknown"})
                    code = str(error)
                    step.update(state="failed", error=code if code in allowed else "analysis_run_settings_invalid")
                    changed = True
            terminal = all(step["state"] in DONE for step in steps)
            state = (
                ("failed" if any(step["state"] in ("failed", "blocked") for step in steps) else "succeeded")
                if terminal
                else "running"
            )
            if changed or state != run["state"]:
                conn.execute(
                    update(workspace_analysis_runs)
                    .where(workspace_analysis_runs.c.id == run["id"])
                    .values(steps=steps, state=state, updated=time.time())
                )
                progressed = True
    return progressed


def register_workspace_run_routes(api, store, owner, workspace, touch):
    Owner = Annotated[str, Depends(owner)]

    def owned_run(wid, run_id, who):
        workspace(wid, who)
        row = store.one(workspace_analysis_runs, id=run_id, workspace_id=wid)
        if not row:
            raise HTTPException(404, "analysis_run_not_found")
        return row

    @api.get("/v1/workspaces/{wid}/runs")
    def list_runs(wid: str, who: Owner):
        workspace(wid, who)
        return [run_view(row) for row in store.rows(workspace_analysis_runs, workspace_id=wid)]

    @api.get("/v1/workspaces/{wid}/runs/{run_id}")
    def get_run(wid: str, run_id: str, who: Owner):
        return run_view(owned_run(wid, run_id, who))

    @api.post("/v1/workspaces/{wid}/runs", status_code=202)
    def start_run(wid: str, body: WorkspaceRunRequest, who: Owner):
        workspace(wid, who)
        with store.transaction() as conn:
            previous = (
                conn.execute(
                    select(workspace_analysis_runs).where(
                        workspace_analysis_runs.c.workspace_id == wid,
                        workspace_analysis_runs.c.request_id == body.request_id,
                    )
                )
                .mappings()
                .first()
            )
            fingerprint = request_fingerprint(body)
            if previous:
                if previous["request_fingerprint"] != fingerprint:
                    raise HTTPException(409, "analysis_run_request_id_conflict")
                return run_view(previous)
            spec = analysis_spec_at(conn, wid)
            if spec["version"] != body.spec_version or not spec["spec"]:
                raise HTTPException(409, "analysis_spec_changed")
            if spec["spec"]["target"] != body.target:
                raise HTTPException(409, "analysis_run_target_mismatch")
            assignments = assignments_at(conn, wid)
            if assignments["version"] != spec["spec"]["channel_assignment_version"]:
                raise HTTPException(409, "channel_assignments_changed")
            selection = selection_at(conn, wid)
            if not conn.execute(
                select(workspace_selections.c.workspace_id).where(workspace_selections.c.workspace_id == wid)
            ).first():
                conn.execute(workspace_selections.insert().values(workspace_id=wid, **selection))
            registered = set(conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars())
            if set(body.field_ids) - registered:
                raise HTTPException(422, "analysis_run_unknown_field")
            entries = {value.get("field_id"): value for value in selection["entries"]}
            if any(fid not in entries or entries[fid].get("exclusion_reason") for fid in body.field_ids):
                raise HTTPException(409, "analysis_run_unselected_field")
            cell = spec["spec"]["settings"].get("cellDefinition", {})
            if body.target == "cell" and cell.get("source") == "cellpose":
                if not cell.get("channel"):
                    raise HTTPException(422, "analysis_run_cell_channel_required")
                if any(cell["channel"] not in {a["channel_id"] for a in effective_assignments(assignments, fid)["assignments"] if a["role"] != "unused"}
                       for fid in body.field_ids):
                    raise HTTPException(422, "analysis_run_cell_channel_unknown")
            if body.target in ("nucleoli", "nucleoplasm"):
                definition = spec["spec"]["settings"]["nucleolarDefinition"]
                if definition["source"] != "dapi_poor" and not definition["marker"]:
                    raise HTTPException(422, "analysis_run_nucleolar_marker_required")
                for fid in body.field_ids:
                    mapped = effective_assignments(assignments, fid)["assignments"]
                    nuclear = [a["channel_id"] for a in mapped if a["role"] == "nuclear"]
                    if len(nuclear) != 1:
                        raise HTTPException(422, "analysis_run_nuclear_parent_required")
                    if definition["source"] != "dapi_poor" and definition["marker"] not in {a["channel_id"] for a in mapped if a["role"] == "measure"}:
                        raise HTTPException(422, "analysis_run_nucleolar_marker_unknown")
                    if definition["source"] == "ncl" and ((spec["spec"].get("processing") or {}).get("nucleoli") or {}).get("detector", {}).get("engine") != "fiji-nucleolar-compartments":
                        from .run_recipes import build_run_request
                        parents = adopted_for(conn, wid, fid, selection)
                        parent = parents.get("nuclei")
                        if not parent:
                            raise HTTPException(422, "analysis_run_nuclear_parent_required")
                        requested = build_run_request(spec["spec"], "nuclei", fid, parents, effective_assignments(assignments, fid))
                        if not same_recipe(parent["config"]["recipe"], requested.recipe):
                            raise HTTPException(422, "analysis_run_nuclear_parent_required")
            order = (
                ["cell"]
                if body.target == "cell"
                else ["nuclei", "nucleoli", "nucleoplasm"][
                    : ["nuclei", "nucleoli", "nucleoplasm"].index(body.target) + 1
                ]
            )
            steps = [
                {
                    "field_id": fid,
                    "target": target,
                    "purpose": body.purpose,
                    "background_pending": False,
                    "state": "pending",
                    "revision_id": None,
                    "job_id": None,
                    "recipe": None,
                    "error": None,
                }
                for fid in body.field_ids
                for target in order
            ]
            now = time.time()
            row = dict(
                id=uid(),
                workspace_id=wid,
                request_id=body.request_id,
                request_fingerprint=fingerprint,
                spec_version=body.spec_version,
                spec_snapshot=spec["spec"],
                selection_snapshot=selection,
                assignments_snapshot=assignments,
                target=body.target,
                state="queued",
                steps=steps,
                created=now,
                updated=now,
            )
            conn.execute(workspace_analysis_runs.insert().values(**row))
            touch(conn, wid)
            return run_view(row)

    @api.post("/v1/workspaces/{wid}/runs/{run_id}/accept")
    def accept_run(wid: str, run_id: str, who: Owner):
        owned_run(wid, run_id, who)
        with store.transaction() as conn:
            run = (
                conn.execute(select(workspace_analysis_runs).where(workspace_analysis_runs.c.id == run_id))
                .mappings()
                .one()
            )
            if run["state"] == "adopted":
                return run_view(run)
            if any(step.get("background_pending") for step in run["steps"]):
                raise HTTPException(409, "analysis_run_background_required")
            if run["state"] != "succeeded":
                raise HTTPException(409, "analysis_run_not_complete")
            if analysis_spec_at(conn, wid)["version"] != run["spec_version"]:
                raise HTTPException(409, "analysis_spec_changed")
            if assignments_at(conn, wid) != run["assignments_snapshot"]:
                raise HTTPException(409, "channel_assignments_changed")
            current = selection_at(conn, wid)
            if current != run["selection_snapshot"]:
                raise HTTPException(409, "workspace_selection_changed")
            entries = deepcopy(current["entries"])
            for step in run["steps"]:
                entry = next(value for value in entries if value.get("field_id") == step["field_id"])
                before = deepcopy(entry)
                entry["revision_id"] = step["revision_id"]
                update_target_adoption(conn, wid, entry, before)
            values = {"version": current["version"] + 1, "entries": entries}
            conn.execute(
                update(workspace_selections)
                .where(workspace_selections.c.workspace_id == wid)
                .values(**values)
            )
            conn.execute(
                update(workspace_analysis_runs)
                .where(workspace_analysis_runs.c.id == run_id)
                .values(state="adopted", updated=time.time())
            )
            touch(conn, wid)
            return run_view({**dict(run), "state": "adopted"})

    @api.post("/v1/workspaces/{wid}/runs/{run_id}/cancel")
    def cancel_run(wid: str, run_id: str, who: Owner):
        owned_run(wid, run_id, who)
        with store.transaction() as conn:
            run = (
                conn.execute(select(workspace_analysis_runs).where(workspace_analysis_runs.c.id == run_id))
                .mappings()
                .one()
            )
            if run["state"] in ("queued", "running"):
                for step in run["steps"]:
                    if step.get("job_id"):
                        cancelled = conn.execute(
                            update(jobs)
                            .where(jobs.c.id == step["job_id"], jobs.c.state.in_(["queued", "running"]))
                            .values(state="cancelled")
                        )
                        if cancelled.rowcount:
                            conn.execute(
                                update(revisions)
                                .where(revisions.c.id == step["revision_id"])
                                .values(state="cancelled")
                            )
                conn.execute(
                    update(workspace_analysis_runs)
                    .where(workspace_analysis_runs.c.id == run_id)
                    .values(state="cancelled", updated=time.time())
                )
                return run_view({**dict(run), "state": "cancelled"})
            return run_view(run)

"""Persisted field adoption; whole-ledger CAS prevents stale tabs changing cohorts."""
from typing import Annotated, Literal

from cytellect_analysis.regions import Id, RegionModel
from fastapi import Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select

from .db import fields, revisions, workspace_selections, workspaces

Target = Literal["nuclei", "gfp", "ncl", "nucleoli", "nucleoplasm"]


class WorkspaceSelectionEntry(RegionModel):
    id: Id
    field_id: Id | None = None
    revision_id: Id | None = None
    exclusion_reason: str | None = Field(default=None, min_length=1, max_length=300)
    target_revisions: dict[Target, Id] | None = Field(default=None, max_length=5, exclude_if=lambda value: value is None)

    @model_validator(mode="after")
    def coherent(self):
        if (self.revision_id or self.target_revisions) and not self.field_id:
            raise ValueError("field_required")
        if self.exclusion_reason is not None and not self.exclusion_reason.strip():
            raise ValueError("exclusion_reason_required")
        return self


class WorkspaceSelection(RegionModel):
    version: int = Field(ge=0)
    entries: list[WorkspaceSelectionEntry] = Field(max_length=100)

    @model_validator(mode="after")
    def unique(self):
        ids = [entry.id for entry in self.entries]
        fids = [entry.field_id for entry in self.entries if entry.field_id]
        if len(ids) != len(set(ids)) or len(fids) != len(set(fids)):
            raise ValueError("duplicate_selection")
        return self


def revision_target(revision):
    recipe = revision["config"].get("recipe", {})
    if recipe.get("source") == "stardist_nuclear":
        return "nuclei"
    if recipe.get("source") == "fiji_nuclear_compartment":
        return recipe.get("compartment")
    if recipe.get("source") == "fiji_positive_regions":
        return {"gfp_positive": "gfp", "ncl_positive": "ncl"}.get(recipe.get("region_set_id"))
    return None


def selected_revision(conn, wid, fid, rid):
    rev = conn.execute(select(revisions).where(revisions.c.id == rid)).mappings().first()
    if (not rev or rev["workspace_id"] != wid or rev["state"] != "succeeded"
            or rev["config"].get("field_ids") != [fid] or rev["config"].get("cohort_sources")):
        raise HTTPException(409, "workspace_selection_invalid_revision")
    return rev


def update_target_adoption(conn, wid, entry, before):
    # Omitted maps from older clients preserve previously adopted targets.
    targets = dict(entry.get("target_revisions", (before or {}).get("target_revisions", {})))
    if before and "target_revisions" not in before and before.get("revision_id"):
        previous = selected_revision(conn, wid, entry["field_id"], before["revision_id"])
        previous_target = revision_target(previous)
        if previous_target:
            targets.setdefault(previous_target, previous["id"])
    active = selected_revision(conn, wid, entry["field_id"], entry["revision_id"]) if entry["revision_id"] else None
    active_target = revision_target(active) if active else None
    if active_target and active is not None:
        targets[active_target] = active["id"]
    resolved = {}
    for target, rid in targets.items():
        rev = selected_revision(conn, wid, entry["field_id"], rid)
        if revision_target(rev) != target:
            raise HTTPException(409, "workspace_target_revision_mismatch")
        resolved[target] = rev
    nucleus = resolved.get("nuclei")
    for target in ("nucleoli", "nucleoplasm"):
        derived = resolved.get(target)
        if not derived:
            continue
        recipe = derived["config"]["recipe"]
        if (not nucleus or recipe.get("nuclear_revision_id") != nucleus["id"]
                or recipe.get("nuclear_channel_id") != nucleus["config"]["recipe"].get("defining_channel_id")):
            if active_target == target:
                raise HTTPException(409, "workspace_derived_revision_stale")
            targets.pop(target)
    plasm = resolved.get("nucleoplasm") if "nucleoplasm" in targets else None
    source = plasm["config"]["recipe"].get("nucleolar_revision_id") if plasm else None
    # Nucleoplasm derived from adopted nucleoli is current only for those nucleoli.
    if source is not None and targets.get("nucleoli") != source:
        if active_target == "nucleoplasm":
            raise HTTPException(409, "workspace_derived_revision_stale")
        targets.pop("nucleoplasm")
    if targets or "target_revisions" in entry or "target_revisions" in (before or {}):
        entry["target_revisions"] = targets


def selection_at(conn, wid):
    saved = conn.execute(select(workspace_selections).where(workspace_selections.c.workspace_id == wid)).mappings().first()
    if saved:
        entries = [dict(entry) for entry in saved["entries"]]
        registered = conn.execute(select(fields).where(fields.c.workspace_id == wid)).mappings().all()
        for row in registered:
            if any(entry["field_id"] == row["id"] for entry in entries):
                continue
            interrupted = next((entry for entry in entries if entry["id"] == row["client_upload_id"] and not entry["field_id"]), None)
            if interrupted:
                interrupted["field_id"] = row["id"]
            else:
                entries.append({"id": row["id"], "field_id": row["id"], "revision_id": None, "exclusion_reason": None})
        return {"version": saved["version"], "entries": entries}
    # Old workspaces have no per-field adoption history. Preserve the current
    # revision where available. Ambiguous old field histories require adoption.
    active = conn.execute(select(workspaces.c.active_revision).where(workspaces.c.id == wid)).scalar_one()
    rows = conn.execute(select(revisions).where(revisions.c.workspace_id == wid,
        revisions.c.state == "succeeded").order_by(revisions.c.created.desc())).mappings().all()
    entries = []
    for fid in conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars():
        choices = [row for row in rows if row["config"].get("field_ids") == [fid] and not row["config"].get("cohort_sources")]
        chosen = next((row for row in choices if row["id"] == active), choices[0] if len(choices) == 1 else None)
        entries.append({"id": fid, "field_id": fid, "revision_id": chosen["id"] if chosen else None, "exclusion_reason": None})
    return {"version": 0, "entries": entries}


def assert_selection(conn, wid, expected):
    if selection_at(conn, wid) != expected:
        raise HTTPException(409, "workspace_selection_changed")


def register_workspace_selection_routes(api, store, owner, workspace, touch):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/workspaces/{wid}/selection", response_model=WorkspaceSelection)
    def get_selection(wid: str, who: Owner):
        workspace(wid, who)
        with store.transaction() as conn:
            return selection_at(conn, wid)

    @api.post("/v1/workspaces/{wid}/selection", response_model=WorkspaceSelection)
    def save_selection(wid: str, body: WorkspaceSelection, who: Owner):
        workspace(wid, who)
        entries = [entry.model_dump(mode="json") for entry in body.entries]
        with store.transaction() as conn:
            touch(conn, wid)
            previous = selection_at(conn, wid)
            if previous["version"] != body.version:
                raise HTTPException(409, "workspace_selection_changed")
            old = {entry["id"]: entry for entry in previous["entries"]}
            current = {entry["id"]: entry for entry in entries}
            if set(old) - set(current):
                raise HTTPException(409, "workspace_entries_cannot_disappear")
            registered = set(conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars())
            if {entry["field_id"] for entry in entries if entry["field_id"]} != registered:
                raise HTTPException(409, "workspace_all_fields_required")
            for entry in entries:
                before = old.get(entry["id"])
                if before and before["field_id"] and before["field_id"] != entry["field_id"]:
                    raise HTTPException(409, "workspace_field_identity_changed")
                update_target_adoption(conn, wid, entry, before)
            updated = {"version": body.version + 1, "entries": entries}
            if conn.execute(select(workspace_selections.c.workspace_id).where(workspace_selections.c.workspace_id == wid)).first():
                conn.execute(workspace_selections.update().where(workspace_selections.c.workspace_id == wid).values(**updated))
            else:
                conn.execute(workspace_selections.insert().values(workspace_id=wid, **updated))
            return updated

"""Explicit current channel identities, separate from immutable upload/revision records."""
from copy import deepcopy
from typing import Annotated, Literal

from cytellect_analysis.regions import Id, Label, RegionModel
from fastapi import Depends, HTTPException
from pydantic import Field, field_validator, model_validator
from sqlalchemy import select

from .db import fields, uid, workspace_channel_assignments


class ChannelAssignment(RegionModel):
    channel_id: Id
    stain: Label | None
    role: Literal["nuclear", "measure", "unused"]

    @field_validator("stain")
    @classmethod
    def descriptive_stain(cls, value):
        if value is not None and (not value.strip() or any(ord(char) < 32 for char in value)):
            raise ValueError("channel_stain_invalid")
        return value.strip() if value is not None else None


class ChannelAssignmentGroup(RegionModel):
    id: Id
    field_ids: list[Id] = Field(max_length=100)
    channel_ids: list[Id] = Field(max_length=6)
    assignments: list[ChannelAssignment] = Field(max_length=6)


class ChannelAssignments(RegionModel):
    version: int = Field(ge=0)
    assignments: list[ChannelAssignment] = Field(max_length=6)
    global_field_ids: list[Id] = Field(default_factory=list, max_length=100)
    groups: list[ChannelAssignmentGroup] = Field(default_factory=list, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        if len({item.channel_id for item in self.assignments}) != len(self.assignments):
            raise ValueError("duplicate_channel_assignment")
        if sum(item.role == "nuclear" for item in self.assignments) > 1:
            raise ValueError("single_nuclear_channel_required")
        return self


class ChannelAssignmentsWrite(RegionModel):
    version: int = Field(ge=0)
    assignments: list[ChannelAssignment] = Field(max_length=6)
    field_ids: list[Id] | None = Field(default=None, max_length=100)

    @model_validator(mode="after")
    def unique(self):
        ChannelAssignments(version=self.version, assignments=self.assignments)
        if self.field_ids is not None and (not self.field_ids or len(set(self.field_ids)) != len(self.field_ids)):
            raise ValueError("channel_assignment_field_selection_invalid")
        return self


def assignments_at(conn, wid):
    row = conn.execute(select(workspace_channel_assignments).where(
        workspace_channel_assignments.c.workspace_id == wid)).mappings().first()
    return {"version": row["version"], "assignments": row["assignments"], "global_field_ids": row["global_field_ids"], "groups": row["groups"]} if row else {"version": 0, "assignments": [], "global_field_ids": [], "groups": []}


def effective_assignments(snapshot, field_id):
    for group in snapshot.get("groups", []):
        if field_id in group["field_ids"]:
            return {"version": snapshot["version"], "assignments": group["assignments"]}
    # Pre-migration saved revision snapshots retain their historical meanings.
    entries = snapshot["assignments"] if "global_field_ids" not in snapshot or field_id in snapshot["global_field_ids"] else []
    return {"version": snapshot["version"], "assignments": entries}


def apply_channel_assignments(store, wid, rows, *, include_roles=False, assignment_snapshot=None):
    if assignment_snapshot is None:
        with store.engine.connect() as conn:
            assignment_snapshot = assignments_at(conn, wid)
    result = deepcopy([dict(row) for row in rows])
    for row in result:
        assigned = {entry["channel_id"]: entry for entry in effective_assignments(assignment_snapshot, row["id"])["assignments"]}
        for channel in row["image_info"].get("channels", []):
            entry = assigned.get(channel["channel_id"])
            if entry is None:
                continue
            channel.update(stain=entry["stain"], label=entry["stain"] or channel["channel_id"])
            channel.pop("identity_confirmed", None)
            channel["identity_source"] = "user_entered" if entry["stain"] is not None else "unresolved"
            if include_roles:
                channel["assignment_role"] = entry["role"]
    return result


def validate_assigned_roles(recipe, snapshot):
    assigned = {entry["channel_id"]: entry for entry in snapshot["assignments"]}
    defining = getattr(recipe, "defining_channel_id", None)
    nuclear = defining if recipe.source == "stardist_nuclear" else getattr(recipe, "nuclear_channel_id", None)
    if defining in assigned and assigned[defining]["role"] == "unused":
        raise HTTPException(422, "channel_assignment_unused")
    if nuclear in assigned and assigned[nuclear]["role"] != "nuclear":
        raise HTTPException(422, "channel_assignment_nuclear_role_required")

def register_channel_assignment_routes(api, store, owner, workspace, touch):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/workspaces/{wid}/channel-assignments", response_model=ChannelAssignments)
    def get_assignments(wid: str, who: Owner):
        workspace(wid, who)
        with store.engine.connect() as conn:
            return assignments_at(conn, wid)

    @api.put("/v1/workspaces/{wid}/channel-assignments", response_model=ChannelAssignments)
    def save_assignments(wid: str, body: ChannelAssignmentsWrite, who: Owner):
        workspace(wid, who)
        with store.transaction() as conn:
            touch(conn, wid)
            previous = assignments_at(conn, wid)
            if previous["version"] != body.version:
                raise HTTPException(409, "channel_assignments_changed")
            registered = conn.execute(select(fields).where(fields.c.workspace_id == wid)).mappings().all()
            registered_ids = {row["id"] for row in registered}
            selected_ids = set(body.field_ids) if body.field_ids is not None else registered_ids
            if selected_ids - registered_ids:
                raise HTTPException(422, "channel_assignment_unknown_field")
            selected = [row for row in registered if row["id"] in selected_ids]
            configurations = {tuple(sorted(channel["channel_id"] for channel in row["image_info"].get("channels", []))) for row in selected}
            if body.field_ids is not None and len(configurations) != 1:
                raise HTTPException(422, "channel_assignment_mixed_configuration")
            ids = {channel["channel_id"] for row in selected for channel in row["image_info"].get("channels", [])}
            supplied = {entry.channel_id for entry in body.assignments}
            if supplied - ids:
                raise HTTPException(422, "channel_assignment_unknown_channel")
            if ids != supplied:
                raise HTTPException(422, "channel_assignments_all_channels_required")
            entries = [entry.model_dump() for entry in body.assignments]
            if body.field_ids is None:
                updated = {"version": body.version + 1, "assignments": entries, "global_field_ids": sorted(selected_ids), "groups": []}
            else:
                groups = [{**group, "field_ids": [fid for fid in group["field_ids"] if fid not in selected_ids]}
                          for group in previous["groups"]]
                groups = [group for group in groups if group["field_ids"]]
                groups.append({"id": uid(), "field_ids": sorted(selected_ids), "channel_ids": sorted(ids), "assignments": entries})
                updated = {"version": body.version + 1, "assignments": previous["assignments"],
                           "global_field_ids": [fid for fid in previous["global_field_ids"] if fid not in selected_ids], "groups": groups}
            if previous["version"]:
                conn.execute(workspace_channel_assignments.update().where(
                    workspace_channel_assignments.c.workspace_id == wid).values(**updated))
            else:
                conn.execute(workspace_channel_assignments.insert().values(workspace_id=wid, **updated))
            return updated

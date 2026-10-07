"""Non-destructive analysis/reference image relationships and explicit exclusions."""

from copy import deepcopy
from typing import Annotated, Literal

from cytellect_analysis.regions import Id, RegionModel
from fastapi import Depends, HTTPException
from pydantic import Field, model_validator
from sqlalchemy import select, update

from .db import fields, workspace_field_links, workspace_selections
from .workspace_selection import selection_at


class FieldLinkWrite(RegionModel):
    version: int = Field(ge=0)
    selection_version: int = Field(ge=0)
    kind: Literal["analysis", "reference"]
    reference_for_field_id: Id | None = None

    @model_validator(mode="after")
    def analysis_has_no_parent(self):
        if self.kind == "analysis" and self.reference_for_field_id is not None:
            raise ValueError("analysis_field_has_no_reference_parent")
        return self


def field_links_at(conn, wid):
    row = (
        conn.execute(select(workspace_field_links).where(workspace_field_links.c.workspace_id == wid))
        .mappings()
        .first()
    )
    return {"version": row["version"], "entries": row["entries"]} if row else {"version": 0, "entries": []}


def register_field_link_routes(api, store, owner, workspace, touch):
    Owner = Annotated[str, Depends(owner)]

    @api.get("/v1/workspaces/{wid}/field-links")
    def get_links(wid: str, who: Owner):
        workspace(wid, who)
        with store.engine.connect() as conn:
            return field_links_at(conn, wid)

    @api.put("/v1/workspaces/{wid}/field-links/{fid}")
    def save_link(wid: str, fid: str, body: FieldLinkWrite, who: Owner):
        workspace(wid, who)
        with store.transaction() as conn:
            previous = field_links_at(conn, wid)
            if previous["version"] != body.version:
                raise HTTPException(409, "field_links_changed")
            selection = selection_at(conn, wid)
            if selection["version"] != body.selection_version:
                raise HTTPException(409, "workspace_selection_changed")
            registered = set(conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars())
            if (
                fid not in registered
                or body.reference_for_field_id
                and body.reference_for_field_id not in registered
            ):
                raise HTTPException(404, "field_not_found")
            if body.reference_for_field_id == fid:
                raise HTTPException(422, "field_cannot_reference_itself")
            links = deepcopy(previous["entries"])
            if body.kind == "reference":
                if any(item.get("reference_for_field_id") == fid for item in links):
                    raise HTTPException(409, "field_link_target_has_references")
                if any(
                    item["field_id"] == body.reference_for_field_id and item["kind"] == "reference"
                    for item in links
                ):
                    raise HTTPException(422, "reference_target_must_be_analysis")
            entries = deepcopy(selection["entries"])
            entry = next((item for item in entries if item.get("field_id") == fid), None)
            if entry is None:
                raise HTTPException(409, "field_selection_required")
            before = next((item for item in links if item["field_id"] == fid), None)
            reference_reason = "補助参照画像として解析対象から除外"
            preserved_exclusion = (
                before.get("previous_exclusion")
                if before and before["kind"] == "reference"
                else entry.get("exclusion_reason")
            )
            if body.kind == "reference":
                entry["exclusion_reason"] = reference_reason
            elif (
                before and before["kind"] == "reference" and entry.get("exclusion_reason") == reference_reason
            ):
                entry["exclusion_reason"] = preserved_exclusion
            link = {
                "field_id": fid,
                "kind": body.kind,
                "reference_for_field_id": body.reference_for_field_id,
                "previous_exclusion": preserved_exclusion,
            }
            links = [item for item in links if item["field_id"] != fid] + [link]
            values = {"version": body.version + 1, "entries": links}
            if previous["version"]:
                conn.execute(
                    update(workspace_field_links)
                    .where(workspace_field_links.c.workspace_id == wid)
                    .values(**values)
                )
            else:
                conn.execute(workspace_field_links.insert().values(workspace_id=wid, **values))
            selected = {"version": selection["version"] + 1, "entries": entries}
            if conn.execute(
                select(workspace_selections.c.workspace_id).where(workspace_selections.c.workspace_id == wid)
            ).first():
                conn.execute(
                    update(workspace_selections)
                    .where(workspace_selections.c.workspace_id == wid)
                    .values(**selected)
                )
            else:
                conn.execute(workspace_selections.insert().values(workspace_id=wid, **selected))
            touch(conn, wid)
            return values

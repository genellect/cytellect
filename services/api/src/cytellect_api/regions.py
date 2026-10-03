"""Additive, owned generic-region endpoints sharing the existing job lifecycle."""

import json
import shutil
import time
from typing import Annotated

import numpy as np
from cytellect_analysis.images import read_tiff, render_preview, sha256
from cytellect_analysis.masks import contours, polygon_mask
from cytellect_analysis.region_contracts import (
    RegionAnalysisRequest,
    RegionFieldInput,
    RegionFieldMetadata,
    RegionImageInfo,
    RegionMaskEdit,
    RegionReport,
)
from fastapi import Depends, File, Form, HTTPException, Response, UploadFile
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, update

from .db import fields, revisions, uid, workspaces
from .region_inputs import read_label_tiff
from .storage import read_json


class RegionFieldView(BaseModel):
    id: str
    workspace_id: str
    metadata: RegionFieldMetadata
    image_info: RegionImageInfo
    synthetic: bool


def is_region(value):
    return value.get("config", value.get("image_info", {})).get("analysis_kind",
           value.get("image_info", {}).get("kind")) == "region-2d"


def register_region_routes(api, store, settings, owner, workspace, revision,
                           field_record, result_root, queue, touch, child_revision):
    Owner = Annotated[str, Depends(owner)]

    def region_revision(rid, who):
        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(409, "region_analysis_required")
        return rev

    def validate_request(body, selected):
        ids = {f["id"] for f in selected}
        if not ids:
            raise HTTPException(422, "images_required")
        if set(body.backgrounds) - ids or any(e.field_id not in ids for e in body.exclusions):
            raise HTTPException(422, "unknown_region_field")
        excluded = {e.field_id for e in body.exclusions if e.region_id is None}
        for f in selected:
            info = RegionImageInfo.model_validate(f["image_info"])
            channels = {c.channel_id for c in info.channels}
            if body.recipe.defining_channel_id is not None and body.recipe.defining_channel_id not in channels:
                raise HTTPException(422, "unknown_defining_channel")
            if body.recipe.source == "imported" and info.labels_array is None:
                raise HTTPException(422, "region_labels_required")
            if body.recipe.source == "manual" and info.labels_array is not None:
                raise HTTPException(422, "manual_region_source_requires_no_imported_labels")
            if f["id"] in excluded:
                continue
            backgrounds = body.backgrounds.get(f["id"], {})
            if set(backgrounds) != channels:
                raise HTTPException(422, "confirm_background_for_every_channel")
            for bg in backgrounds.values():
                polygon_mask(info.shape, bg.polygon)

    @api.get("/v1/workspaces/{wid}/region-fields", response_model=list[RegionFieldView])
    def list_region_fields(wid: str, who: Owner):
        workspace(wid, who)
        return [dict(f) for f in store.rows(fields, workspace_id=wid) if is_region(f)]

    @api.post("/v1/workspaces/{wid}/region-fields", status_code=201, response_model=RegionFieldView)
    async def upload_region_field(wid: str, who: Owner, specification: str = Form(...),
                                  ch0: UploadFile = File(...), ch1: UploadFile | None = File(None),
                                  ch2: UploadFile | None = File(None), labels: UploadFile | None = File(None)):
        workspace(wid, who)
        try:
            spec = RegionFieldInput.model_validate_json(specification)
        except ValidationError:
            raise HTTPException(422, "invalid_region_field_specification") from None
        channel_files = [ch0, ch1, ch2]
        if any((file is not None) != (i < len(spec.channels)) for i, file in enumerate(channel_files)):
            raise HTTPException(422, "region_channel_file_count_mismatch")
        fid = uid()
        folder = store.safe_path("workspaces", wid, "fields", fid)
        folder.mkdir(parents=True)
        uploads = {f"ch{i}": f for i, f in enumerate(channel_files) if f is not None}
        if labels is not None:
            uploads["labels"] = labels
        total = 0
        try:
            inputs = {}
            for slot, file in uploads.items():
                path = folder / f"{slot}.tif"
                with path.open("wb") as stream:
                    while chunk := await file.read(1024 * 1024):
                        total += len(chunk)
                        if total > 256 * 1024**2:
                            raise HTTPException(413, "field_upload_limit")
                        stream.write(chunk)
                inputs[slot] = {"sha256": sha256(path), "bytes": path.stat().st_size}
            shape = None
            arrays = {}
            for i, channel in enumerate(spec.channels):
                pixels = read_tiff(folder / f"ch{i}.tif")
                if shape is not None and pixels.shape != shape:
                    raise ValueError("channel_dimensions_mismatch")
                shape = pixels.shape
                path = folder / f"channel-{channel.channel_id}.npy"
                np.save(path, pixels, allow_pickle=False)
                arrays[channel.channel_id] = {"sha256": sha256(path), "bytes": path.stat().st_size}
            label_info = None
            if labels is not None:
                plane = read_label_tiff(folder / "labels.tif", shape)
                path = folder / "labels.npy"
                np.save(path, plane, allow_pickle=False)
                label_info = {"sha256": sha256(path), "bytes": path.stat().st_size}
            if shape is None:
                raise ValueError("region_channels_required")
            info = RegionImageInfo.model_validate({"shape": list(shape), "channels": spec.channels,
                                   "inputs": inputs, "channel_arrays": arrays, "labels_array": label_info,
                                   "calibration": spec.calibration})
            with store.transaction() as conn:
                touch(conn, wid)
                w = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
                count = conn.execute(select(func.count()).select_from(fields).where(fields.c.workspace_id == wid)).scalar_one()
                if count >= settings.max_fields or w["bytes"] + total > settings.max_upload_bytes:
                    raise HTTPException(413, "workspace_limit")
                identity = {(c.channel_id, c.label, c.stain) for c in spec.channels}
                for existing in conn.execute(select(fields).where(fields.c.workspace_id == wid)).mappings():
                    if not is_region(existing):
                        raise HTTPException(409, "workflow_kind_mismatch")
                    existing_info = RegionImageInfo.model_validate(existing["image_info"])
                    if identity != {(c.channel_id, c.label, c.stain) for c in existing_info.channels}:
                        raise HTTPException(409, "region_workspace_channel_identity_mismatch")
                conn.execute(fields.insert().values(id=fid, workspace_id=wid,
                             metadata=spec.metadata.model_dump(mode="json"),
                             image_info=info.model_dump(mode="json"), synthetic=False))
                conn.execute(update(workspaces).where(workspaces.c.id == wid).values(bytes=w["bytes"] + total))
            return dict(store.one(fields, id=fid))
        except HTTPException:
            shutil.rmtree(folder)
            raise
        except Exception:
            shutil.rmtree(folder)
            raise HTTPException(422, "unsupported_or_invalid_region_image") from None
        finally:
            for file in uploads.values():
                await file.close()

    @api.get("/v1/region-fields/{fid}/preview")
    def preview(fid: str, channel_id: str, who: Owner, low: float = 0, high: float = 100, gain: float = 1):
        f = field_record(fid, who)
        if not is_region(f):
            raise HTTPException(404, "field_not_found")
        info = RegionImageInfo.model_validate(f["image_info"])
        if (channel_id not in info.channel_arrays or not 0 <= low < high <= 100 or not 0.1 <= gain <= 10):
            raise HTTPException(422, "invalid_display_settings")
        path = store.safe_path("workspaces", f["workspace_id"], "fields", fid, f"channel-{channel_id}.npy")
        pixels = np.load(path, allow_pickle=False)
        return Response(render_preview({channel_id: pixels}, channel_id, low, high, gain), media_type="image/png")

    @api.post("/v1/workspaces/{wid}/region-analyses", status_code=202)
    def start(wid: str, body: RegionAnalysisRequest, who: Owner):
        workspace(wid, who)
        selected = [dict(f) for f in store.rows(fields, workspace_id=wid) if is_region(f)]
        if body.field_ids is not None:
            if set(body.field_ids) - {f["id"] for f in selected}:
                raise HTTPException(422, "unknown_region_field")
            selected = [f for f in selected if f["id"] in body.field_ids]
        validate_request(body, selected)
        parent = None
        if body.reuse_revision:
            parent = region_revision(body.reuse_revision, who)
            if parent["workspace_id"] != wid:
                raise HTTPException(404, "revision_not_found")
            result_root(parent)
            if not set(parent["config"]["field_ids"]).issubset({f["id"] for f in selected}):
                raise HTTPException(409, "batch_must_include_reused_fields")
            if parent["config"]["recipe"] != body.recipe.model_dump(mode="json"):
                raise HTTPException(409, "batch_reuse_requires_unchanged_recipe")
        rid = uid()
        config = {**body.model_dump(mode="json"), "analysis_kind": "region-2d",
                  "field_ids": [f["id"] for f in selected], "field_snapshot": {f["id"]: f for f in selected}}
        with store.transaction() as conn:
            w = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
            if parent is not None and w["active_revision"] != parent["id"]:
                raise HTTPException(409, "stale_revision")
            conn.execute(revisions.insert().values(id=rid, workspace_id=wid, parent_id=w["active_revision"],
                         config=config, state="queued", reviewed=False, created=time.time()))
            jid = queue(conn, wid, rid, "analysis", {})
            conn.execute(update(workspaces).where(workspaces.c.id == wid).values(active_revision=rid))
        return {"revision_id": rid, "job_id": jid}

    @api.get("/v1/revisions/{rid}/region-measurements", response_model=RegionReport)
    def measurements(rid: str, who: Owner):
        rev = region_revision(rid, who)
        report = read_json(result_root(rev) / "measurements.json")
        return RegionReport.model_validate_json(json.dumps(report))

    @api.get("/v1/revisions/{rid}/region-masks")
    def masks(rid: str, field_id: str, who: Owner):
        rev = region_revision(rid, who)
        if field_id not in rev["config"]["field_ids"]:
            raise HTTPException(404, "field_not_found")
        root = result_root(rev)
        path = root / field_id / "labels.npy"
        if not path.is_file():
            raise HTTPException(409, "field_failed")
        report = read_json(root / "measurements.json")
        return {"regions": contours(np.load(path, allow_pickle=False)),
                "metadata": report.get("field_masks", {}).get(field_id)}

    @api.post("/v1/revisions/{rid}/region-edits", status_code=202)
    def edit(rid: str, body: RegionMaskEdit, who: Owner):
        parent = region_revision(rid, who)
        root = result_root(parent)
        if body.field_id not in parent["config"]["field_ids"]:
            raise HTTPException(404, "field_not_found")
        if body.region_set_id != parent["config"]["recipe"]["region_set_id"]:
            raise HTTPException(422, "region_set_mismatch")
        if not (root / body.field_id / "labels.npy").is_file():
            raise HTTPException(409, "field_failed")
        if body.expected_mask_revision_id is not None:
            metadata = read_json(root / "measurements.json").get("field_masks", {}).get(body.field_id, {})
            if metadata.get("mask_revision_id") != body.expected_mask_revision_id:
                raise HTTPException(409, "stale_region_mask")
        config = {k: v for k, v in parent["config"].items() if k != "region_edit"}
        config.update(reuse_revision=rid, region_edit=body.model_dump(mode="json"))
        return child_revision(parent, config)

    @api.post("/v1/revisions/{rid}/region-reconfigure", status_code=202)
    def reconfigure(rid: str, body: RegionAnalysisRequest, who: Owner):
        parent = region_revision(rid, who)
        result_root(parent)
        if body.recipe.model_dump(mode="json") != parent["config"]["recipe"]:
            raise HTTPException(409, "region_definition_requires_new_analysis")
        if body.field_ids is not None and set(body.field_ids) != set(parent["config"]["field_ids"]):
            raise HTTPException(409, "field_selection_requires_new_analysis")
        selected = list(parent["config"]["field_snapshot"].values())
        validate_request(body, selected)
        config = {k: v for k, v in parent["config"].items() if k != "region_edit"}
        config.update(body.model_dump(mode="json", exclude={"field_ids"}), reuse_revision=rid)
        return child_revision(parent, config)

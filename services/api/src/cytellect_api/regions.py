"""Additive, owned generic-region endpoints sharing the existing job lifecycle."""

import hashlib
import io
import json
import shutil
import time
from copy import deepcopy
from typing import Annotated

import numpy as np
import tifffile
from cytellect_analysis.display_contracts import (
    PREVIEW_DISPLAY_HEADER,
    REGION_PREVIEW_PNG_RESPONSE,
    OriginalRgbPreviewMetadata,
    RegionPreviewDisplayMetadata,
)
from cytellect_analysis.engine import nuclear_detection_shape
from cytellect_analysis.images import read_tiff, render_preview_with_display, sha256
from cytellect_analysis.masks import contours, polygon_mask
from cytellect_analysis.region_contracts import (
    RegionAnalysisRequest,
    RegionCompartmentRecipe,
    RegionFieldInput,
    RegionFieldMetadata,
    RegionImageInfo,
    RegionMaskEdit,
    RegionMetadataEdit,
    RegionReportType,
    region_report_from_json,
    region_request_config,
    validate_nuclear_role_evidence,
    validate_region_report_policy,
)
from cytellect_analysis.region_metadata import region_metadata_child_config
from fastapi import Depends, File, Form, HTTPException, Response, UploadFile
from PIL import Image
from pydantic import BaseModel, ValidationError
from sqlalchemy import func, select, update

from .db import fields, revisions, uid, workspaces
from .openapi import register_contract_schemas
from .planning import bind_revision_plan, inherit_plan_resolution
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
    register_contract_schemas(api, RegionPreviewDisplayMetadata)

    def region_revision(rid, who):
        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(409, "region_analysis_required")
        return rev

    def validate_request(body, selected, reused_masks=()):
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
            if isinstance(body.recipe, RegionCompartmentRecipe):
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
                                  ch2: UploadFile | None = File(None), ch3: UploadFile | None = File(None),
                                  labels: UploadFile | None = File(None)):
        workspace(wid, who)
        try:
            spec = RegionFieldInput.model_validate_json(specification)
        except ValidationError:
            raise HTTPException(422, "invalid_region_field_specification") from None
        channel_files = [ch0, ch1, ch2, ch3]
        if any((file is not None) != (i < len(spec.channels)) for i, file in enumerate(channel_files)):
            raise HTTPException(422, "region_channel_file_count_mismatch")
        fid = uid()
        folder = store.safe_path("workspaces", wid, "fields", fid)
        folder.mkdir(parents=True)
        uploads = {f"ch{i}": f for i, f in enumerate(channel_files) if f is not None}
        if labels is not None:
            uploads["labels"] = labels
        total = 0
        keep_folder = False
        fingerprint = None

        def existing_upload(conn):
            if spec.client_upload_id is None:
                return None
            existing = conn.execute(select(fields).where(
                fields.c.workspace_id == wid,
                fields.c.client_upload_id == spec.client_upload_id,
            )).mappings().first()
            if existing is not None:
                if existing["upload_fingerprint"] != fingerprint:
                    raise HTTPException(409, "region_upload_id_conflict")
                return dict(existing)
            # Browser reloads regenerate client keys. Identical source bytes and
            # scientific metadata still represent the same field in this workspace.
            equivalent = conn.execute(select(fields).where(
                fields.c.workspace_id == wid,
                fields.c.upload_fingerprint == fingerprint,
            ).order_by(fields.c.id)).mappings().first()
            if equivalent is not None:
                return dict(equivalent)
            # Selecting a detector role can change only the evidence-source tag.
            # It must not duplicate unchanged images or rewrite saved provenance.
            requested_channels = [{key: value for key, value in channel.model_dump(mode="json").items()
                                   if key != "identity_source"} for channel in spec.channels]
            for candidate in conn.execute(select(fields).where(fields.c.workspace_id == wid).order_by(fields.c.id)).mappings():
                info = candidate["image_info"]
                if (not is_region(candidate) or info.get("inputs") != inputs
                        or info.get("input_mode", "native") != spec.input_mode
                        or info.get("calibration") != (spec.calibration.model_dump(mode="json") if spec.calibration else None)
                        or candidate["metadata"] != spec.metadata.model_dump(mode="json")):
                    continue
                channels = [{key: value for key, value in channel.items() if key != "identity_source"}
                            for channel in info["channels"]]
                if channels == requested_channels:
                    return dict(candidate)
            return None

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
            if spec.client_upload_id is not None:
                canonical = json.dumps({
                    "specification": spec.model_dump(mode="json", exclude={"client_upload_id"}),
                    "inputs": inputs,
                }, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                fingerprint = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
                # A known key is resolved before decoding and quota checks. A
                # changed/corrupt resend must not replace the accepted input.
                with store.transaction() as conn:
                    touch(conn, wid)
                    existing = existing_upload(conn)
                    if existing is not None:
                        return existing
            shape = None
            arrays = {}
            for i, channel in enumerate(spec.channels):
                pixels = read_tiff(folder / f"ch{i}.tif", legacy=spec.input_mode == "display-rgb")
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
                                   "calibration": spec.calibration, "input_mode": spec.input_mode})
            with store.transaction() as conn:
                touch(conn, wid)
                # Decode outside the write lock, then recheck within the same
                # transaction as quota accounting and insert for racing sends.
                existing = existing_upload(conn)
                if existing is not None:
                    return existing
                w = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
                count = conn.execute(select(func.count()).select_from(fields).where(fields.c.workspace_id == wid)).scalar_one()
                if count >= settings.max_fields or w["bytes"] + total > settings.max_upload_bytes:
                    raise HTTPException(413, "workspace_limit")
                identity = {c.channel_id.casefold(): (c.channel_id, c.label, c.stain) for c in spec.channels}
                for existing in conn.execute(select(fields).where(fields.c.workspace_id == wid)).mappings():
                    if not is_region(existing):
                        raise HTTPException(409, "workflow_kind_mismatch")
                    existing_info = RegionImageInfo.model_validate(existing["image_info"])
                    existing_identity = {c.channel_id.casefold(): (c.channel_id, c.label, c.stain)
                                         for c in existing_info.channels}
                    # Incomplete acquisitions remain registrable; only shared
                    # channel IDs must have the same scientific identity.
                    if any(identity[cid] != existing_identity[cid]
                           for cid in identity.keys() & existing_identity.keys()):
                        raise HTTPException(409, "region_workspace_channel_identity_mismatch")
                conn.execute(fields.insert().values(id=fid, workspace_id=wid,
                             metadata=spec.metadata.model_dump(mode="json"),
                             image_info=info.model_dump(mode="json"), synthetic=False,
                             client_upload_id=spec.client_upload_id, upload_fingerprint=fingerprint))
                conn.execute(update(workspaces).where(workspaces.c.id == wid).values(bytes=w["bytes"] + total))
                result = dict(conn.execute(select(fields).where(fields.c.id == fid)).mappings().one())
            keep_folder = True
            return result
        except HTTPException:
            raise
        except Exception:
            raise HTTPException(422, "unsupported_or_invalid_region_image") from None
        finally:
            if not keep_folder:
                shutil.rmtree(folder)
            for file in uploads.values():
                await file.close()

    @api.get("/v1/region-fields/{fid}/preview", response_class=Response, responses=REGION_PREVIEW_PNG_RESPONSE)
    def preview(fid: str, channel_id: str, who: Owner, low: float = 0, high: float = 100, gain: float = 1):
        f = field_record(fid, who)
        if not is_region(f):
            raise HTTPException(404, "field_not_found")
        info = RegionImageInfo.model_validate(f["image_info"])
        if (channel_id not in info.channel_arrays or not 0 <= low < high <= 100 or not 0.1 <= gain <= 10):
            raise HTTPException(422, "invalid_display_settings")
        if info.input_mode == "display-rgb":
            slot = next(i for i, channel in enumerate(info.channels) if channel.channel_id == channel_id)
            original = store.safe_path("workspaces", f["workspace_id"], "fields", fid, f"ch{slot}.tif")
            recorded = info.inputs[f"ch{slot}"]
            if (not original.is_file() or original.stat().st_size != recorded.bytes
                    or sha256(original) != recorded.sha256):
                raise HTTPException(409, "region_original_image_mismatch")
            with tifffile.TiffFile(original, _multifile=False) as tif:
                series = tif.series[0]
                if series.axes in ("YXS", "SYX"):
                    if (len(tif.series) != 1 or series.dtype != np.uint8 or len(series.shape) != 3
                            or series.shape[series.axes.index("S")] not in (3, 4)):
                        raise HTTPException(422, "unsupported_original_rgb_preview")
                    shape = tuple(series.shape[series.axes.index(axis)] for axis in "YX")
                    if shape != tuple(info.shape):
                        raise HTTPException(409, "region_original_image_mismatch")
                    if (low, high, gain) != (0, 100, 1):
                        raise HTTPException(422, "original_rgb_preview_has_no_contrast_adjustment")
                    if series.shape[series.axes.index("S")] == 4 and tuple(getattr(tif.pages[0], "extrasamples", ())) != (2,):
                        # Premultiplied/unspecified alpha cannot be represented as
                        # unchanged straight-alpha PNG samples without guessing.
                        raise HTTPException(422, "unsupported_original_rgb_alpha")
                    rgb = np.moveaxis(series.asarray(), series.axes.index("S"), -1)
                    output = io.BytesIO()
                    Image.fromarray(rgb).save(output, format="PNG")
                    original_display = OriginalRgbPreviewMetadata(
                        field_id=fid, requested_channel=channel_id,
                        source_axes="YXS" if series.axes == "YXS" else "SYX", source_shape=series.shape,
                        rendered_shape=rgb.shape, color_mode="RGBA" if rgb.shape[2] == 4 else "RGB",
                        alpha_preserved=rgb.shape[2] == 4, source_file_sha256=recorded.sha256,
                    )
                    return Response(output.getvalue(), media_type="image/png", headers={
                        PREVIEW_DISPLAY_HEADER: original_display.model_dump_json(),
                    })
        path = store.safe_path("workspaces", f["workspace_id"], "fields", fid, f"channel-{channel_id}.npy")
        pixels = np.load(path, allow_pickle=False)
        png, display = render_preview_with_display(
            {channel_id: pixels}, channel_id, low, high, gain, field_id=fid, composite=False,
        )
        return Response(png, media_type="image/png", headers={
            PREVIEW_DISPLAY_HEADER: json.dumps(display.model_dump(), ensure_ascii=True, separators=(",", ":")),
        })

    @api.post("/v1/workspaces/{wid}/region-analyses", status_code=202)
    def start(wid: str, body: RegionAnalysisRequest, who: Owner):
        workspace_record = workspace(wid, who)
        selected = [dict(f) for f in store.rows(fields, workspace_id=wid) if is_region(f)]
        if body.field_ids is not None:
            if set(body.field_ids) - {f["id"] for f in selected}:
                raise HTTPException(422, "unknown_region_field")
            selected = [f for f in selected if f["id"] in body.field_ids]
        parent = None
        reused_masks = ()
        if body.reuse_revision:
            parent = region_revision(body.reuse_revision, who)
            if parent["workspace_id"] != wid:
                raise HTTPException(404, "revision_not_found")
            root = result_root(parent)
            if not set(parent["config"]["field_ids"]).issubset({f["id"] for f in selected}):
                raise HTTPException(409, "batch_must_include_reused_fields")
            if parent["config"]["recipe"] != body.recipe.model_dump(mode="json"):
                raise HTTPException(409, "batch_reuse_requires_unchanged_recipe")
            # Experimental metadata is versioned in snapshots, not rewritten on
            # the original upload row. Expanding a trial retains its adopted data.
            previous = parent["config"]["field_snapshot"]
            selected = [deepcopy(previous[f["id"]]) if f["id"] in previous else f for f in selected]
            reused_masks = read_json(root / "measurements.json").get("field_masks", {})
        validate_request(body, selected, reused_masks)
        rid = uid()
        config = {**region_request_config(body), "analysis_kind": "region-2d",
                  "field_ids": [f["id"] for f in selected], "field_snapshot": {f["id"]: f for f in selected}}
        if parent is not None and "plan_resolution" not in body.model_fields_set:
            inherit_plan_resolution(config, parent["config"])
        bind_revision_plan(config, workspace_record.get("analysis_plan"),
                           parent_config=parent["config"] if parent is not None else None)
        with store.transaction() as conn:
            w = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
            if parent is not None and w["active_revision"] != parent["id"]:
                raise HTTPException(409, "stale_revision")
            conn.execute(revisions.insert().values(id=rid, workspace_id=wid, parent_id=w["active_revision"],
                         config=config, state="queued", reviewed=False, created=time.time()))
            jid = queue(conn, wid, rid, "analysis", {})
            conn.execute(update(workspaces).where(workspaces.c.id == wid).values(active_revision=rid))
        return {"revision_id": rid, "job_id": jid}

    @api.get("/v1/revisions/{rid}/region-compartment-status")
    def compartment_status(rid: str, who: Owner):
        rev = region_revision(rid, who)
        root = result_root(rev)
        if rev["config"].get("recipe", {}).get("source") != "fiji_nuclear_compartment":
            raise HTTPException(409, "compartment_revision_required")
        provenance = read_json(root / "provenance.json")
        return {"revision_id": rid, "fields": {
            fid: {"nuclear_source": value.get("nuclear_source"),
                  **{key: value.get("detector", {}).get("engine", {}).get(key) for key in (
                      "nucleolar_states", "parent_ids", "eligible_nucleus_ids", "excluded_nucleus_ids",
                      "missing_parent_count", "missing_parent_reasons", "nucleoplasm_missing_reasons", "compartment_missing_parent_count")}}
            for fid, value in provenance.get("fields", {}).items()}}

    @api.get("/v1/revisions/{rid}/region-measurements", response_model=RegionReportType)
    def measurements(rid: str, who: Owner):
        rev = region_revision(rid, who)
        report = read_json(result_root(rev) / "measurements.json")
        typed = region_report_from_json(json.dumps(report))
        validate_region_report_policy(typed, rev["config"])
        return typed

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
        config = {k: v for k, v in parent["config"].items() if k not in ("region_edit", "region_metadata_edit")}
        config.update(reuse_revision=rid, region_edit=body.model_dump(mode="json"))
        return child_revision(parent, config)

    @api.post("/v1/revisions/{rid}/region-reconfigure", status_code=202)
    def reconfigure(rid: str, body: RegionAnalysisRequest, who: Owner):
        parent = region_revision(rid, who)
        root = result_root(parent)
        if body.recipe.model_dump(mode="json") != parent["config"]["recipe"]:
            raise HTTPException(409, "region_definition_requires_new_analysis")
        if body.field_ids is not None and set(body.field_ids) != set(parent["config"]["field_ids"]):
            raise HTTPException(409, "field_selection_requires_new_analysis")
        selected = list(parent["config"]["field_snapshot"].values())
        validate_request(body, selected, read_json(root / "measurements.json").get("field_masks", {}))
        config = {k: v for k, v in parent["config"].items() if k not in ("region_edit", "region_metadata_edit")}
        # Returning to v1 removes the v2 policy instead of retaining it through
        # an update of the old revision dictionary. Other v1 defaults stay exact.
        config.pop("measurement", None)
        request_config = region_request_config(body)
        request_config.pop("field_ids", None)
        config.update(request_config, reuse_revision=rid)
        if "plan_resolution" not in body.model_fields_set:
            inherit_plan_resolution(config, parent["config"])
        bind_revision_plan(config, workspace(parent["workspace_id"], who).get("analysis_plan"),
                           parent_config=parent["config"])
        return child_revision(parent, config)

    @api.post("/v1/revisions/{rid}/region-metadata", status_code=202)
    def metadata(rid: str, body: RegionMetadataEdit, who: Owner):
        parent = region_revision(rid, who)
        result_root(parent)
        try:
            config = region_metadata_child_config(parent, body)
        except ValueError:
            raise HTTPException(422, "unknown_region_metadata_field") from None
        return child_revision(parent, config)

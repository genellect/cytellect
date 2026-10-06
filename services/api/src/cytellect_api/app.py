"""Private API. No patient/research content is logged or externally transmitted."""

import json
import secrets
import shutil
import time
from typing import Annotated

import numpy as np
import tifffile
from cytellect_analysis.contracts import (
    AnalysisRequest,
    FieldMetadata,
    MaskEdit,
    Recipe,
    ResegmentInput,
    ReviewInput,
    StatisticsRequest,
    required_channel_roles,
)
from cytellect_analysis.descriptive_contracts import PagedDescriptiveOutput, PagedDescriptiveResult
from cytellect_analysis.display_contracts import (
    PREVIEW_DISPLAY_HEADER,
    PREVIEW_PNG_RESPONSE,
    PreviewDisplayMetadata,
)
from cytellect_analysis.images import read_tiff, render_preview_with_display, sha256
from cytellect_analysis.masks import contours
from cytellect_analysis.plan_adoption import adopt_plan
from cytellect_analysis.planning import CandidateId, PlanInput
from cytellect_analysis.review import unresolved_nucleolar_failures
from cytellect_analysis.synthetic import synthetic_field
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator
from sqlalchemy import func, select, update

from .common_statistics import register_common_statistics_routes
from .config import Settings, configure_private_tmp
from .db import Store, digest, fields, invitations, jobs, revisions, sessions, tables, uid, workspaces
from .descriptive import register_descriptive_routes
from .openapi import register_contract_schemas
from .planning import bind_revision_plan, inherit_plan_resolution, register_planning_routes
from .proposals import register_proposal_routes
from .region_cohorts import register_region_cohort_routes
from .region_comparisons import register_region_comparison_routes
from .regions import is_region, register_region_routes
from .storage import read_json, write_json
from .upload_guard import UploadGuardMiddleware
from .views import FieldView, JobView, MasksView, RevisionView, WorkspaceView
from .workspace_selection import register_workspace_selection_routes


class InviteInput(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class WorkspaceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(default="Untitled experiment", min_length=1, max_length=100)
    plan: PlanInput | None = None
    plan_candidate_id: CandidateId | None = None

    @model_validator(mode="after")
    def explicit_plan_choice(self):
        if (self.plan is None) != (self.plan_candidate_id is None):
            raise ValueError("planning_candidate_unavailable")
        return self


class RevisionInput(BaseModel):
    revision_id: str


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    configure_private_tmp(settings)
    store = Store(settings.data_dir)
    api = FastAPI(title="Cytellect private API", version="0.1.0", docs_url=None, redoc_url=None)
    api.state.store, api.state.settings = store, settings
    if settings.desktop_owner:
        from .desktop import install_owner_session

        install_owner_session(api, settings, store)
    api.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.app_origin],
        allow_credentials=True,
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["Content-Type", "X-Cytellect-Request"],
        expose_headers=[PREVIEW_DISPLAY_HEADER],
    )
    api.add_middleware(UploadGuardMiddleware, store=store, settings=settings)
    attempts: dict[str, list[float]] = {}

    @api.middleware("http")
    async def security(request: Request, call_next):
        if request.method not in ("GET", "HEAD", "OPTIONS"):
            if (
                request.headers.get("origin") != settings.app_origin
                or request.headers.get("x-cytellect-request") != "1"
            ):
                return JSONResponse(
                    {"detail": "origin_or_csrf_invalid"},
                    status_code=403,
                    headers={"Cache-Control": "no-store"},
                )
        try:
            response = await call_next(request)
        except Exception:
            # Never send exception details or request payloads to public logs.
            response = JSONResponse({"detail": "internal_error"}, status_code=500)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["X-Frame-Options"] = "DENY"
        return response

    @api.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        return JSONResponse({"detail": "invalid_request_parameters"}, status_code=422)

    @api.exception_handler(ValueError)
    async def invalid_input(_request, _error):
        return JSONResponse({"detail": "invalid_analysis_input"}, status_code=422)

    def owner(request: Request):
        token = request.cookies.get(settings.cookie_name)
        session = store.one(sessions, digest=digest(token)) if token else None
        if not session or session["revoked"] or session["expires"] <= time.time():
            raise HTTPException(401, "session_required")
        return session["owner"]

    Owner = Annotated[str, Depends(owner)]

    def workspace(wid, who):
        value = store.one(workspaces, id=wid)
        if not value or value["owner"] != who or value["deleted"] or value["expires"] <= time.time():
            raise HTTPException(404, "workspace_not_found")
        return value

    def revision(rid, who):
        value = store.one(revisions, id=rid)
        if not value:
            raise HTTPException(404, "revision_not_found")
        workspace(value["workspace_id"], who)
        return value

    def legacy_revision(rid, who):
        value = revision(rid, who)
        if is_region(value):
            raise HTTPException(409, "legacy_analysis_required")
        return value

    def touch(conn, wid):
        current = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().first()
        if not current or current["deleted"] or current["expires"] <= time.time():
            raise HTTPException(404, "workspace_not_found")
        conn.execute(
            update(workspaces)
            .where(workspaces.c.id == wid)
            .values(expires=time.time() + settings.retention_seconds)
        )

    def queue(conn, wid, rid, kind, payload):
        count = conn.execute(
            select(func.count()).select_from(jobs).where(jobs.c.state.in_(["queued", "running"]))
        ).scalar_one()
        if count >= 10:
            raise HTTPException(429, "queue_full")
        jid = uid()
        conn.execute(
            jobs.insert().values(
                id=jid,
                workspace_id=wid,
                revision_id=rid,
                kind=kind,
                state="queued",
                payload=payload,
                created=time.time(),
                attempts=0,
            )
        )
        touch(conn, wid)
        return jid

    def field_record(fid, who):
        f = store.one(fields, id=fid)
        if not f:
            raise HTTPException(404, "field_not_found")
        workspace(f["workspace_id"], who)
        return f

    def result_root(rev):
        if rev["state"] != "succeeded" or not rev["result_dir"]:
            raise HTTPException(409, "analysis_not_ready")
        return store.safe_path(rev["result_dir"])

    def public_revision(rev):
        return {
            k: rev[k] for k in ("id", "workspace_id", "parent_id", "config", "state", "reviewed", "created")
        }

    @api.get("/v1/health")
    def health():
        return {
            "status": "ok",
            "version": "0.1.0",
            "demo": settings.demo,
            "fiji_configured": bool(settings.fiji_executable),
        }

    @api.post("/v1/invitations/redeem")
    def redeem(body: InviteInput, request: Request, response: Response):
        key = digest(request.client.host if request.client else "unknown")
        now = time.time()
        recent = [t for t in attempts.get(key, []) if t > now - 60]
        if len(recent) >= 10:
            raise HTTPException(429, "too_many_attempts")
        attempts[key] = [*recent, now]
        if len(attempts) > 1000:
            for old in list(attempts):
                if not any(t > now - 60 for t in attempts[old]):
                    attempts.pop(old, None)
        token = secrets.token_urlsafe(32)
        principal = uid()
        with store.transaction() as c:
            invitation = (
                c.execute(select(invitations).where(invitations.c.digest == digest(body.token)))
                .mappings()
                .first()
            )
            if not invitation or invitation["used"] or invitation["expires"] <= now:
                raise HTTPException(401, "invitation_invalid")
            c.execute(update(invitations).where(invitations.c.digest == digest(body.token)).values(used=True))
            c.execute(
                sessions.insert().values(
                    digest=digest(token), owner=principal, expires=now + 7 * 86400, revoked=False
                )
            )
        response.set_cookie(
            settings.cookie_name,
            token,
            httponly=True,
            secure=settings.secure_cookies,
            samesite="strict",
            max_age=7 * 86400,
            path="/",
        )
        return {"authenticated": True}

    @api.get("/v1/session")
    def session(who: Owner):
        return {"authenticated": True, "retention_hours": 24, "demo": settings.demo}

    @api.delete("/v1/session")
    def logout(request: Request, response: Response, who: Owner):
        with store.transaction() as c:
            c.execute(
                update(sessions)
                .where(sessions.c.digest == digest(request.cookies[settings.cookie_name]))
                .values(revoked=True)
            )
        response.delete_cookie(
            settings.cookie_name, path="/", secure=settings.secure_cookies, httponly=True, samesite="strict"
        )
        return {"revoked": True}

    @api.get("/v1/workspaces", response_model=list[WorkspaceView])
    def list_workspaces(who: Owner):
        return [
            dict(r)
            for r in store.rows(workspaces, owner=who)
            if not r["deleted"] and r["expires"] > time.time()
        ]

    @api.post("/v1/workspaces", status_code=201, response_model=WorkspaceView)
    def new_workspace(body: WorkspaceInput, who: Owner):
        wid = uid()
        selected_plan = None
        if body.plan is not None and body.plan_candidate_id is not None:
            try:
                selected_plan = adopt_plan(body.plan, body.plan_candidate_id, time.time()).model_dump(mode="json")
            except ValueError:
                raise HTTPException(422, "planning_candidate_unavailable") from None
        with store.transaction() as c:
            c.execute(
                workspaces.insert().values(
                    id=wid,
                    owner=who,
                    title=body.title,
                    created=time.time(),
                    expires=time.time() + settings.retention_seconds,
                    deleted=False,
                    bytes=0,
                    analysis_plan=selected_plan,
                )
            )
        return dict(store.one(workspaces, id=wid))

    @api.get("/v1/workspaces/{wid}", response_model=WorkspaceView)
    def get_workspace(wid: str, who: Owner):
        return dict(workspace(wid, who))

    @api.delete("/v1/workspaces/{wid}")
    def delete_workspace(wid: str, who: Owner):
        workspace(wid, who)
        with store.transaction() as c:
            c.execute(update(workspaces).where(workspaces.c.id == wid).values(deleted=True))
            c.execute(
                update(jobs)
                .where(jobs.c.workspace_id == wid, jobs.c.state.in_(["queued", "running"]))
                .values(state="cancelled")
            )
        return {"access_revoked": True, "files": "cleanup_pending"}

    @api.post("/v1/workspaces/{wid}/touch")
    def keep_alive(wid: str, who: Owner):
        workspace(wid, who)
        with store.transaction() as c:
            touch(c, wid)
        return {"expires": store.one(workspaces, id=wid)["expires"]}

    @api.get("/v1/workspaces/{wid}/fields", response_model=list[FieldView])
    def list_fields(wid: str, who: Owner):
        workspace(wid, who)
        return [dict(r) for r in store.rows(fields, workspace_id=wid) if not is_region(r)]

    @api.post("/v1/workspaces/{wid}/fields", status_code=201, response_model=FieldView)
    async def upload_field(
        wid: str,
        who: Owner,
        metadata: str = Form(...),
        legacy: bool = Form(False),
        dapi: UploadFile | None = File(None),
        ncl: UploadFile | None = File(None),
        gfp: UploadFile | None = File(None),
        ome: UploadFile | None = File(None),
        mapping: str = Form("[0,1,2]"),
        channel_roles: str = Form('["dapi","ncl","gfp"]'),
    ):
        workspace(wid, who)
        if settings.demo:
            raise HTTPException(403, "demo_accepts_synthetic_only")
        try:
            md = FieldMetadata.model_validate_json(metadata)
        except ValidationError:
            raise HTTPException(422, "invalid_field_metadata") from None
        if (ome is None and (dapi is None or (ncl is None and gfp is None))) or (
            ome is not None and any(f is not None for f in (dapi, ncl, gfp))
        ):
            raise HTTPException(422, "provide_dapi_and_ncl_or_gfp_or_one_ome")
        fid = uid()
        folder = store.safe_path("workspaces", wid, "fields", fid)
        folder.mkdir(parents=True)
        uploads = {"ome": ome} if ome else {r: f for r, f in {"dapi": dapi, "ncl": ncl, "gfp": gfp}.items() if f is not None}
        total = 0
        try:
            input_info = {}
            for role, file in uploads.items():
                if file is None:
                    raise HTTPException(422, "missing_upload")
                path = folder / f"{role}.tif"
                with path.open("wb") as output:
                    while chunk := await file.read(1024 * 1024):
                        total += len(chunk)
                        if total > 256 * 1024**2:
                            raise HTTPException(413, "field_upload_limit")
                        output.write(chunk)
                input_info[role] = {"sha256": sha256(path), "bytes": path.stat().st_size}
            if ome:
                indices = json.loads(mapping)
                if not isinstance(indices, list) or any(type(v) is not int for v in indices):
                    raise ValueError("invalid_mapping")
                stack = read_tiff(folder / "ome.tif", channel_indices=indices)
                roles = json.loads(channel_roles)
                if (not isinstance(roles, list) or any(r not in ("dapi", "ncl", "gfp") for r in roles)
                        or len(roles) != len(set(roles)) or "dapi" not in roles or len(roles) not in (2, 3)):
                    raise ValueError("invalid_channel_roles")
                channels = dict(zip(roles, stack, strict=True))
            else:
                channels = {c: read_tiff(folder / f"{c}.tif", legacy=legacy) for c in uploads}
            if legacy and set(channels) != {"dapi", "ncl", "gfp"}:
                raise ValueError("legacy_requires_three_channels")
            if len({a.shape for a in channels.values()}) != 1:
                raise ValueError("channel_dimensions_mismatch")
            for role, array in channels.items():
                np.save(folder / f"{role}.npy", array, allow_pickle=False)
            info = {
                "shape": list(channels["dapi"].shape),
                "dtype": str(channels["dapi"].dtype),
                "legacy": legacy,
                "inputs": input_info,
                "axes": "YX",
                "channel_mapping": json.loads(mapping) if ome else list(channels),
                "channel_roles": list(channels),
                "channel_dtypes": {role: str(array.dtype) for role, array in channels.items()},
            }
            with store.transaction() as c:
                w = c.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
                count = c.execute(
                    select(func.count()).select_from(fields).where(fields.c.workspace_id == wid)
                ).scalar_one()
                if w["deleted"] or w["expires"] <= time.time():
                    raise HTTPException(404, "workspace_not_found")
                if any(is_region(existing) for existing in c.execute(
                    select(fields).where(fields.c.workspace_id == wid)
                ).mappings()):
                    raise HTTPException(409, "workflow_kind_mismatch")
                if count >= settings.max_fields or w["bytes"] + total > settings.max_upload_bytes:
                    raise HTTPException(413, "workspace_limit")
                c.execute(
                    fields.insert().values(
                        id=fid, workspace_id=wid, metadata=md.model_dump(), image_info=info, synthetic=False
                    )
                )
                c.execute(update(workspaces).where(workspaces.c.id == wid).values(bytes=w["bytes"] + total))
                touch(c, wid)
            return dict(store.one(fields, id=fid))
        except HTTPException:
            shutil.rmtree(folder)
            raise
        except Exception:
            shutil.rmtree(folder)
            raise HTTPException(422, "unsupported_or_invalid_image") from None
        finally:
            for file in uploads.values():
                if file:
                    await file.close()

    @api.post("/v1/workspaces/{wid}/synthetic", status_code=201)
    def synthetic(wid: str, who: Owner):
        workspace(wid, who)
        ids = []
        generated_bytes = 0
        created_folders = []
        try:
            with store.transaction() as c:
                current = c.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
                touch(c, wid)
                count = c.execute(
                    select(func.count()).select_from(fields).where(fields.c.workspace_id == wid)
                ).scalar_one()
                if any(is_region(existing) for existing in c.execute(
                    select(fields).where(fields.c.workspace_id == wid)
                ).mappings()):
                    raise HTTPException(409, "workflow_kind_mismatch")
                if count + 6 > settings.max_fields:
                    raise HTTPException(413, "field_limit")
                for i in range(6):
                    fid = uid()
                    folder = store.safe_path("workspaces", wid, "fields", fid)
                    created_folders.append(folder)
                    folder.mkdir(parents=True)
                    channels, nuclei, nucleoli = synthetic_field(i)
                    inputs = {}
                    for role, array in channels.items():
                        np.save(folder / f"{role}.npy", array, allow_pickle=False)
                        tifffile.imwrite(folder / f"{role}.tif", array)
                        inputs[role] = {
                            "sha256": sha256(folder / f"{role}.tif"),
                            "bytes": (folder / f"{role}.tif").stat().st_size,
                        }
                        generated_bytes += inputs[role]["bytes"]
                    np.savez_compressed(folder / "synthetic-truth.npz", nuclei=nuclei, nucleoli=nucleoli)
                    md = FieldMetadata(
                        condition="Control" if i % 2 == 0 else "Treatment",
                        experimental_unit=f"replicate-{i // 2 + 1}",
                        sample=f"sample-{i}",
                        acquisition_date=f"batch-{i // 2 + 1}",
                        pair=f"pair-{i // 2 + 1}",
                        pixel_size_um=0.25,
                    )
                    info = {
                        "shape": [256, 256],
                        "dtype": "uint16",
                        "legacy": False,
                        "inputs": inputs,
                        "axes": "YX",
                        "channel_mapping": ["dapi", "ncl", "gfp"],
                        "channel_roles": ["dapi", "ncl", "gfp"],
                    }
                    c.execute(
                        fields.insert().values(
                            id=fid,
                            workspace_id=wid,
                            metadata=md.model_dump(),
                            image_info=info,
                            synthetic=True,
                        )
                    )
                    ids.append(fid)
                if current["bytes"] + generated_bytes > settings.max_upload_bytes:
                    raise HTTPException(413, "workspace_limit")
                c.execute(
                    update(workspaces)
                    .where(workspaces.c.id == wid)
                    .values(bytes=current["bytes"] + generated_bytes)
                )
                touch(c, wid)
        except Exception:
            for folder in created_folders:
                if folder.exists():
                    shutil.rmtree(folder)
            raise
        return {
            "field_ids": ids,
            "synthetic": True,
            "background_polygon": [[0, 0], [15, 0], [15, 15], [0, 15]],
        }

    @api.get("/v1/fields/{fid}/preview", response_class=Response, responses=PREVIEW_PNG_RESPONSE)
    def preview(
        fid: str, who: Owner, channel: str = "merge", low: float = 0, high: float = 100, gain: float = 1
    ):
        f = field_record(fid, who)
        if is_region(f):
            raise HTTPException(404, "field_not_found")
        if (
            channel not in ("dapi", "ncl", "gfp", "merge")
            or not 0 <= low < high <= 100
            or not 0.1 <= gain <= 10
        ):
            raise HTTPException(422, "invalid_display_settings")
        folder = store.safe_path("workspaces", f["workspace_id"], "fields", fid)
        roles = f["image_info"].get("channel_roles", ["dapi", "ncl", "gfp"])
        if channel != "merge" and channel not in roles:
            raise HTTPException(422, "channel_not_acquired")
        channels = {c: np.load(folder / f"{c}.npy", allow_pickle=False) for c in roles}
        png, display = render_preview_with_display(
            channels, channel, low, high, gain, field_id=fid, legacy=bool(f["image_info"].get("legacy", False)),
        )
        return Response(png, media_type="image/png", headers={
            PREVIEW_DISPLAY_HEADER: json.dumps(display.model_dump(), ensure_ascii=True, separators=(",", ":")),
        })

    @api.post("/v1/workspaces/{wid}/analyses", status_code=202)
    def start_analysis(wid: str, body: AnalysisRequest, who: Owner):
        selected_workspace = workspace(wid, who)
        selected = [f for f in store.rows(fields, workspace_id=wid) if not is_region(f)]
        if body.field_ids is not None:
            requested = set(body.field_ids)
            if len(requested) != len(body.field_ids) or not requested.issubset({f["id"] for f in selected}):
                raise HTTPException(422, "invalid_trial_fields")
            selected = [f for f in selected if f["id"] in requested]
        if not selected:
            raise HTTPException(422, "images_required")
        selected_ids = {f["id"] for f in selected}
        parent = None
        if body.reuse_revision:
            parent = legacy_revision(body.reuse_revision, who)
            if parent["workspace_id"] != wid:
                raise HTTPException(404, "revision_not_found")
            result_root(parent)
            if not set(parent["config"]["field_ids"]).issubset(selected_ids):
                raise HTTPException(409, "batch_must_include_reused_fields")
            if Recipe.model_validate(parent["config"]["recipe"]) != body.recipe:
                raise HTTPException(409, "batch_reuse_requires_unchanged_recipe")
        if not set(body.recipe.gfp_negative_control_fields).issubset(selected_ids):
            raise HTTPException(422, "negative_control_fields_must_be_in_analysis")
        if any(e.field_id not in selected_ids for e in body.exclusions):
            raise HTTPException(422, "unknown_exclusion_field")
        for f in selected:
            bg = body.backgrounds.get(f["id"])
            if body.recipe.id != "ncl-legacy-rgb" and (not bg or not bg.confirmed):
                raise HTTPException(422, "confirm_background_for_every_field")
            if not required_channel_roles(body.recipe).issubset(f["image_info"].get("channel_roles", ["dapi", "ncl", "gfp"])):
                raise HTTPException(422, "recipe_required_channels_missing")
            if f["image_info"]["legacy"] != (body.recipe.id == "ncl-legacy-rgb"):
                raise HTTPException(422, "recipe_input_mode_mismatch")
        rid = uid()
        config = body.model_dump()
        config["field_ids"] = [f["id"] for f in selected]
        config["field_snapshot"] = {f["id"]: dict(f) for f in selected}
        if parent is not None and "plan_resolution" not in body.model_fields_set:
            inherit_plan_resolution(config, parent["config"])
        bind_revision_plan(config, selected_workspace["analysis_plan"],
                           parent_config=parent["config"] if parent is not None else None)
        with store.transaction() as c:
            w = c.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
            if parent is not None and w["active_revision"] != parent["id"]:
                raise HTTPException(409, "stale_revision")
            c.execute(
                revisions.insert().values(
                    id=rid,
                    workspace_id=wid,
                    parent_id=w["active_revision"],
                    config=config,
                    state="queued",
                    reviewed=False,
                    created=time.time(),
                )
            )
            jid = queue(c, wid, rid, "analysis", {})
            c.execute(update(workspaces).where(workspaces.c.id == wid).values(active_revision=rid))
        return {"revision_id": rid, "job_id": jid}

    @api.get("/v1/workspaces/{wid}/revisions", response_model=list[RevisionView])
    def list_revisions(wid: str, who: Owner):
        workspace(wid, who)
        return [public_revision(r) for r in store.rows(revisions, workspace_id=wid)]

    @api.get("/v1/revisions/{rid}", response_model=RevisionView)
    def get_revision(rid: str, who: Owner):
        return public_revision(revision(rid, who))

    @api.get("/v1/revisions/{rid}/measurements")
    def measurements(rid: str, who: Owner):
        rev = revision(rid, who)
        return read_json(result_root(rev) / "measurements.json")

    @api.get("/v1/revisions/{rid}/fields/{fid}/masks", response_model=MasksView)
    def get_masks(rid: str, fid: str, who: Owner):
        rev = legacy_revision(rid, who)
        if fid not in rev["config"]["field_ids"]:
            raise HTTPException(404, "field_not_found")
        path = result_root(rev) / fid / "masks.npz"
        if not path.exists():
            raise HTTPException(409, "field_failed")
        with np.load(path, allow_pickle=False) as masks:
            return {
                "nuclei": contours(masks["nuclei"]),
                "nucleoli": contours(masks["nucleoli"]),
                "manual": contours(masks["manual"]),
            }

    @api.post("/v1/revisions/{rid}/edits", status_code=202)
    def edit(rid: str, body: MaskEdit, who: Owner):
        parent = legacy_revision(rid, who)
        result_root(parent)
        if body.field_id not in parent["config"]["field_ids"]:
            raise HTTPException(404, "field_not_found")
        child = uid()
        config = {k: v for k, v in parent["config"].items() if k not in {"edit", "resegment_fields"}}
        config["edit"] = body.model_dump()
        config["reuse_revision"] = rid
        with store.transaction() as c:
            w = (
                c.execute(select(workspaces).where(workspaces.c.id == parent["workspace_id"]))
                .mappings()
                .one()
            )
            if w["active_revision"] != rid:
                raise HTTPException(409, "stale_revision")
            c.execute(
                revisions.insert().values(
                    id=child,
                    workspace_id=w["id"],
                    parent_id=rid,
                    config=config,
                    state="queued",
                    reviewed=False,
                    created=time.time(),
                )
            )
            jid = queue(c, w["id"], child, "analysis", {})
            c.execute(update(workspaces).where(workspaces.c.id == w["id"]).values(active_revision=child))
        return {"revision_id": child, "job_id": jid}

    @api.post("/v1/workspaces/{wid}/current")
    def choose_revision(wid: str, body: RevisionInput, who: Owner):
        workspace(wid, who)
        rev = revision(body.revision_id, who)
        if rev["workspace_id"] != wid or rev["state"] != "succeeded":
            raise HTTPException(409, "invalid_revision")
        with store.transaction() as c:
            c.execute(update(workspaces).where(workspaces.c.id == wid).values(active_revision=rev["id"]))
            touch(c, wid)
        return public_revision(rev)

    @api.post("/v1/revisions/{rid}/review")
    def review(rid: str, who: Owner, body: ReviewInput = ReviewInput()):
        rev = revision(rid, who)
        root = result_root(rev)
        report = read_json(root / "measurements.json")
        if report["field_failures"]:
            raise HTTPException(409, "resolve_or_explicitly_exclude_failed_fields")
        if not is_region(rev) and unresolved_nucleolar_failures(report, rev["config"]):
            raise HTTPException(409, "resolve_or_explicitly_exclude_failed_nucleoli")
        if rev["config"].get("recipe", {}).get("source") == "fiji_nuclear_compartment":
            from cytellect_analysis.compartment_review import assert_complete_compartments
            try:
                assert_complete_compartments(rev["config"], report, read_json(result_root(rev) / "provenance.json"))
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
        invalidated = set(report.get("invalidated_nucleoli", []))
        if invalidated != set(body.accept_invalidated_fields):
            raise HTTPException(409, "explicit_review_of_invalidated_nucleoli_required")
        with store.transaction() as c:
            c.execute(
                update(revisions)
                # Immutable scientific inputs are reviewed once. A retried or
                # concurrent confirmation must not invalidate source-bound jobs.
                .where(revisions.c.id == rid, revisions.c.reviewed.is_(False))
                .values(
                    reviewed=True,
                    review_record={
                        "confirmed_at": time.time(),
                        "accepted_invalidated_fields": body.accept_invalidated_fields,
                    },
                )
            )
            touch(c, rev["workspace_id"])
        return {"reviewed": True}

    @api.post("/v1/revisions/{rid}/statistics", status_code=202)
    def statistics(rid: str, body: StatisticsRequest, who: Owner):
        rev = legacy_revision(rid, who)
        if rev["state"] != "succeeded" or not rev["reviewed"]:
            raise HTTPException(409, "review_required")
        if unresolved_nucleolar_failures(read_json(result_root(rev) / "measurements.json"), rev["config"]):
            raise HTTPException(409, "resolve_or_explicitly_exclude_failed_nucleoli")
        from .region_sensitivity import validate_region_revision

        for alternate_id in body.sensitivity_region_revision_ids:
            alternate = revision(alternate_id, who)
            try:
                validate_region_revision(store, rev, alternate)
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
        with store.transaction() as c:
            jid = queue(c, rev["workspace_id"], rid, "statistics", body.model_dump())
        return {"job_id": jid}

    @api.post("/v1/revisions/{rid}/export", status_code=202)
    def export(rid: str, who: Owner, include_raw: bool = False):
        rev = revision(rid, who)
        result_root(rev)
        with store.transaction() as c:
            jid = queue(c, rev["workspace_id"], rid, "export", {"include_raw": include_raw})
        return {"job_id": jid}

    def child_revision(parent, config):
        rid = uid()
        with store.transaction() as conn:
            w = (
                conn.execute(select(workspaces).where(workspaces.c.id == parent["workspace_id"]))
                .mappings()
                .one()
            )
            if w["active_revision"] != parent["id"]:
                raise HTTPException(409, "stale_revision")
            touch(conn, w["id"])
            conn.execute(
                revisions.insert().values(
                    id=rid,
                    workspace_id=w["id"],
                    parent_id=parent["id"],
                    config=config,
                    state="queued",
                    reviewed=False,
                    created=time.time(),
                )
            )
            jid = queue(conn, w["id"], rid, "analysis", {})
            conn.execute(update(workspaces).where(workspaces.c.id == w["id"]).values(active_revision=rid))
        return {"revision_id": rid, "job_id": jid}

    @api.post("/v1/revisions/{rid}/reconfigure", status_code=202)
    def reconfigure(rid: str, body: AnalysisRequest, who: Owner):
        parent = legacy_revision(rid, who)
        result_root(parent)
        previous = Recipe.model_validate(parent["config"]["recipe"])
        detection_keys = {
            "probability",
            "nms",
            "percentile_low",
            "percentile_high",
            "nucleolar_method",
            "smoothing_sigma_px",
            "minimum_area_px",
            "split_touching",
            "dapi_low_percentile",
            "id",
            "version",
        }
        if any(getattr(previous, k) != getattr(body.recipe, k) for k in detection_keys):
            raise HTTPException(409, "detection_parameters_require_explicit_resegmentation")
        selected = set(parent["config"]["field_ids"])
        if body.field_ids is not None and set(body.field_ids) != selected:
            raise HTTPException(409, "field_selection_requires_new_analysis")
        if not set(body.recipe.gfp_negative_control_fields).issubset(selected):
            raise HTTPException(422, "negative_control_fields_must_be_in_analysis")
        if previous.legacy.target_long_dimension_px != body.recipe.legacy.target_long_dimension_px:
            raise HTTPException(409, "detection_parameters_require_explicit_resegmentation")
        if any(e.field_id not in selected for e in body.exclusions):
            raise HTTPException(422, "unknown_exclusion_field")
        excluded_fields = {e.field_id for e in body.exclusions if e.nucleus_id is None}
        for fid in selected - excluded_fields:
            roles = parent["config"]["field_snapshot"][fid]["image_info"].get("channel_roles", ["dapi", "ncl", "gfp"])
            if not required_channel_roles(body.recipe).issubset(roles):
                raise HTTPException(422, "recipe_required_channels_missing")
            if body.recipe.id != "ncl-legacy-rgb" and (
                fid not in body.backgrounds or not body.backgrounds[fid].confirmed
            ):
                raise HTTPException(422, "confirm_background_for_every_field")
        config = {k: v for k, v in parent["config"].items() if k not in {"edit", "resegment_fields"}}
        config.update(body.model_dump(exclude={"field_ids"}))
        if "plan_resolution" not in body.model_fields_set:
            inherit_plan_resolution(config, parent["config"])
        config["reuse_revision"] = rid
        bind_revision_plan(config, workspace(parent["workspace_id"], who)["analysis_plan"],
                           parent_config=parent["config"])
        return child_revision(parent, config)

    @api.post("/v1/revisions/{rid}/resegment", status_code=202)
    def resegment(rid: str, body: ResegmentInput, who: Owner):
        parent = legacy_revision(rid, who)
        result_root(parent)
        if not set(body.field_ids).issubset(parent["config"]["field_ids"]):
            raise HTTPException(422, "unknown_resegmentation_field")
        config = {k: v for k, v in parent["config"].items() if k not in {"edit", "resegment_fields"}}
        config.update(reuse_revision=rid, resegment_fields=body.field_ids)
        if body.recipe:
            old = Recipe.model_validate(config["recipe"])
            if old != body.recipe and set(body.field_ids) != set(config["field_ids"]):
                raise HTTPException(409, "resegment_changed_recipe_requires_all_fields")
            if old.legacy.target_long_dimension_px != body.recipe.legacy.target_long_dimension_px:
                raise HTTPException(409, "nucleus_parameters_require_new_analysis")
            if not set(body.recipe.gfp_negative_control_fields).issubset(config["field_ids"]):
                raise HTTPException(422, "negative_control_fields_must_be_in_analysis")
            for key in ("id", "version", "probability", "nms", "percentile_low", "percentile_high"):
                if getattr(old, key) != getattr(body.recipe, key):
                    raise HTTPException(409, "nucleus_parameters_require_new_analysis")
            for snapshot in config["field_snapshot"].values():
                if not required_channel_roles(body.recipe).issubset(snapshot["image_info"].get("channel_roles", ["dapi", "ncl", "gfp"])):
                    raise HTTPException(422, "recipe_required_channels_missing")
            config["recipe"] = body.recipe.model_dump()
        if body.backgrounds is not None:
            if not set(body.backgrounds).issubset(config["field_ids"]):
                raise HTTPException(422, "unknown_background_field")
            config["backgrounds"] = {fid: background.model_dump() for fid, background in body.backgrounds.items()}
        if body.exclusions is not None:
            if any(entry.field_id not in config["field_ids"] for entry in body.exclusions):
                raise HTTPException(422, "unknown_exclusion_field")
            config["exclusions"] = [entry.model_dump() for entry in body.exclusions]
        excluded = {entry["field_id"] for entry in config["exclusions"] if entry["nucleus_id"] is None}
        if config["recipe"]["id"] != "ncl-legacy-rgb":
            for fid in set(config["field_ids"]) - excluded:
                if not config["backgrounds"].get(fid, {}).get("confirmed"):
                    raise HTTPException(422, "confirm_background_for_every_field")
        if "plan_resolution" in body.model_fields_set:
            config["plan_resolution"] = body.plan_resolution.model_dump(mode="json") if body.plan_resolution else None
        else:
            inherit_plan_resolution(config, parent["config"])
        bind_revision_plan(config, workspace(parent["workspace_id"], who)["analysis_plan"],
                           parent_config=parent["config"])
        return child_revision(parent, config)

    @api.post("/v1/jobs/{jid}/retry", status_code=202)
    def retry(jid: str, who: Owner):
        original = job_record(jid, who)
        if original["state"] not in ("failed", "cancelled"):
            raise HTTPException(409, "only_failed_or_cancelled_jobs_can_retry")
        with store.transaction() as conn:
            current = conn.execute(select(jobs).where(jobs.c.id == jid)).mappings().one()
            if current["lease_until"] and current["lease_until"] > time.time():
                raise HTTPException(409, "worker_still_stopping")
            if original["kind"] == "analysis":
                rev = (
                    conn.execute(select(revisions).where(revisions.c.id == original["revision_id"]))
                    .mappings()
                    .one()
                )
                if rev["state"] not in ("failed", "cancelled"):
                    raise HTTPException(409, "revision_already_retried")
                conn.execute(update(revisions).where(revisions.c.id == rev["id"]).values(state="queued"))
            new_id = queue(
                conn, original["workspace_id"], original["revision_id"], original["kind"], original["payload"]
            )
        return {"job_id": new_id, "revision_id": original["revision_id"]}

    @api.post("/v1/workspaces/{wid}/tables", status_code=201)
    async def import_table(wid: str, who: Owner, file: UploadFile = File(...)):
        from cytellect_analysis.numerical_csv import parse_numeric_csv

        workspace(wid, who)
        if settings.demo:
            raise HTTPException(403, "demo_accepts_synthetic_only")
        content = await file.read(8 * 1024**2 + 1)
        await file.close()
        if len(content) > 8 * 1024**2:
            raise HTTPException(413, "table_size_limit")
        parsed = parse_numeric_csv(content)
        tid = uid()
        folder = store.safe_path("workspaces", wid, "tables", tid)
        try:
            with store.transaction() as conn:
                touch(conn, wid)
                current = conn.execute(select(workspaces).where(workspaces.c.id == wid)).mappings().one()
                if current["bytes"] + len(content) > settings.max_upload_bytes:
                    raise HTTPException(413, "workspace_limit")
                folder.mkdir(parents=True)
                (folder / "input.csv").write_bytes(content)
                write_json(folder / "table.json", parsed)
                conn.execute(
                    tables.insert().values(
                        id=tid,
                        workspace_id=wid,
                        metadata=parsed["metadata"],
                        row_count=len(parsed["rows"]),
                        created=time.time(),
                    )
                )
                conn.execute(
                    update(workspaces)
                    .where(workspaces.c.id == wid)
                    .values(bytes=current["bytes"] + len(content))
                )
        except Exception:
            if folder.exists():
                shutil.rmtree(folder)
            raise
        return {"table_id": tid, "row_count": len(parsed["rows"]), "metadata": parsed["metadata"]}

    @api.get("/v1/workspaces/{wid}/tables")
    def list_tables(wid: str, who: Owner):
        workspace(wid, who)
        return [dict(r) for r in store.rows(tables, workspace_id=wid)]

    @api.post("/v1/tables/{tid}/statistics", status_code=202)
    def table_statistics(tid: str, body: StatisticsRequest, who: Owner):
        table = store.one(tables, id=tid)
        if table is None:
            raise HTTPException(404, "table_not_found")
        workspace(table["workspace_id"], who)
        if body.metric != "value" or body.mode != "experimental-unit":
            raise HTTPException(422, "numeric_tables_require_unit_value_analysis")
        with store.transaction() as conn:
            jid = queue(conn, table["workspace_id"], tid, "table-statistics", body.model_dump())
        return {"job_id": jid}

    @api.get("/v1/workspaces/{wid}/jobs", response_model=list[JobView])
    def list_jobs(wid: str, who: Owner):
        workspace(wid, who)
        return [
            {**{k: r[k] for k in ("id", "revision_id", "kind", "state", "created", "error", "attempts")},
             "analysis_mode": r["payload"].get("mode") if r["kind"] in ("statistics", "table-statistics") else None,
             "analysis_version": r["payload"].get("version") if r["kind"] in ("statistics", "table-statistics") else None}
            for r in store.rows(jobs, workspace_id=wid)
        ]

    def job_record(jid, who):
        j = store.one(jobs, id=jid)
        if not j:
            raise HTTPException(404, "job_not_found")
        workspace(j["workspace_id"], who)
        return j

    @api.get("/v1/jobs/{jid}", response_model=JobView)
    def get_job(jid: str, who: Owner):
        j = job_record(jid, who)
        return {**{k: j[k] for k in ("id", "revision_id", "kind", "state", "created", "error", "attempts")},
                "analysis_mode": j["payload"].get("mode") if j["kind"] in ("statistics", "table-statistics") else None,
                "analysis_version": j["payload"].get("version") if j["kind"] in ("statistics", "table-statistics") else None}

    @api.post("/v1/jobs/{jid}/cancel")
    def cancel(jid: str, who: Owner):
        j = job_record(jid, who)
        with store.transaction() as c:
            result = c.execute(
                update(jobs)
                .where(jobs.c.id == jid, jobs.c.state.in_(["queued", "running"]))
                .values(state="cancelled")
            )
            if result.rowcount and j["kind"] == "analysis":
                c.execute(
                    update(revisions).where(revisions.c.id == j["revision_id"]).values(state="cancelled")
                )
        return {"cancelled": bool(result.rowcount)}

    @api.get("/v1/jobs/{jid}/result")
    def job_result(jid: str, who: Owner):
        j = job_record(jid, who)
        if j["state"] != "succeeded" or not j["result_dir"]:
            raise HTTPException(409, "job_not_ready")
        path = store.safe_path(j["result_dir"]) / "result.json"
        return read_json(path) if path.exists() else {"files": ["analysis.zip"]}

    @api.get("/v1/jobs/{jid}/files/{name}")
    def job_file(jid: str, name: str, who: Owner):
        j = job_record(jid, who)
        allowed = {
            "figure.png": "image/png",
            "figure.svg": "image/svg+xml",
            "figure-caption.md": "text/markdown; charset=utf-8",
            "figure-data.json": "application/json",
            "model-predictions.csv": "text/csv",
            "figure.pdf": "application/pdf",
            "plot-data.csv": "text/csv",
            "comparisons.csv": "text/csv",
            "associations.csv": "text/csv",
            "omnibus.csv": "text/csv",
            "counts.csv": "text/csv",
            "graphical-summary.csv": "text/csv",
            "unit-summary.csv": "text/csv",
            **{f"{axis}-{table}.csv": "text/csv"
               for axis in ("x", "y")
               for table in ("plot-data", "observations", "source-fields", "field-summary",
                             "sample-summary", "unit-summary", "pair-ledger", "excluded-failed-fields")},
            "experimental-units.csv": "text/csv",
            "field-summary.csv": "text/csv",
            "sample-summary.csv": "text/csv",
            "observations.csv": "text/csv",
            "pair-ledger.csv": "text/csv",
            "unit-ledger.csv": "text/csv",
            "source-fields.csv": "text/csv",
            "excluded-failed-fields.csv": "text/csv",
            "source-review.json": "application/json",
            "selection.csv": "text/csv",
            "missingness.csv": "text/csv",
            "model-coefficients.csv": "text/csv",
            "repeat-trend.csv": "text/csv",
            "sensitivity-comparisons.csv": "text/csv",
            "sensitivity-counts.csv": "text/csv",
            "sensitivity-status.csv": "text/csv",
            "analysis.zip": "application/zip",
            "methods.md": "text/markdown",
        }
        if j["state"] != "succeeded" or not j["result_dir"]:
            raise HTTPException(404, "artifact_not_found")
        root = store.safe_path(j["result_dir"])
        if name == "figure.zip":
            path = root / name
            record_path = root / "figure-archive.json"
            if path.is_symlink() or not path.is_file() or not record_path.is_file():
                raise HTTPException(404, "artifact_not_found")
            record = read_json(record_path)
            if path.stat().st_size != record.get("bytes") or sha256(path) != record.get("sha256"):
                raise HTTPException(404, "artifact_not_found")
            return FileResponse(path, media_type="application/zip", filename=name)
        index = root / "descriptive-output.json"
        if index.exists() or "figure_policy" in (j.get("payload") or {}):
            from cytellect_analysis.descriptive_output import (
                descriptive_output_file,
                read_descriptive_output_index,
            )

            try:
                artifact = descriptive_output_file(read_descriptive_output_index(index), name)
            except (ValueError, KeyError, TypeError, OSError, RecursionError):
                raise HTTPException(404, "artifact_not_found") from None
            path = root / name
            if (path.is_symlink() or not path.is_file() or path.stat().st_size != artifact.bytes
                    or sha256(path) != artifact.sha256):
                raise HTTPException(404, "artifact_not_found")
            media = allowed.get(name) or {"svg": "image/svg+xml", "pdf": "application/pdf", "png": "image/png"}[name.rsplit(".", 1)[-1]]
            return FileResponse(path, media_type=media, filename=name)
        if name not in allowed:
            raise HTTPException(404, "artifact_not_found")
        path = root / name
        if not path.is_file():
            raise HTTPException(404, "artifact_not_found")
        return FileResponse(path, media_type=allowed[name], filename=name)

    register_region_routes(api, store, settings, owner, workspace, revision,
                           field_record, result_root, queue, touch, child_revision)
    register_descriptive_routes(api, store, owner, revision, result_root, queue)
    register_region_comparison_routes(api, store, owner, revision, result_root, queue, job_record)
    register_common_statistics_routes(api, store, owner, revision, result_root, queue, job_record)
    register_planning_routes(api, owner)
    register_proposal_routes(api, store, settings, owner, workspace)
    register_workspace_selection_routes(api, store, owner, workspace, touch)
    register_region_cohort_routes(api, store, owner, workspace, revision, result_root, queue)
    register_contract_schemas(api, PreviewDisplayMetadata, PagedDescriptiveOutput, PagedDescriptiveResult)
    return api

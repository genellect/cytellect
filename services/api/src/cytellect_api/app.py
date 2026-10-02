"""Private API. No patient/research content is logged or externally transmitted."""
import io
import json
import secrets
import shutil
import time
from pathlib import Path
from typing import Annotated
import numpy as np
import tifffile
from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import func, select, update
from cytellect_analysis.contracts import AnalysisRequest, FieldMetadata, MaskEdit, StatisticsRequest
from cytellect_analysis.images import read_tiff, render_preview, sha256
from cytellect_analysis.masks import contours
from cytellect_analysis.synthetic import synthetic_field
from .config import Settings
from .db import Store, digest, fields, invitations, jobs, revisions, sessions, uid, workspaces
from .storage import read_json, write_json

class InviteInput(BaseModel):
    token: str = Field(min_length=20,max_length=200)

class WorkspaceInput(BaseModel):
    title: str = Field(default="Untitled experiment",min_length=1,max_length=100)

class RevisionInput(BaseModel):
    revision_id: str

def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    store = Store(settings.data_dir)
    api = FastAPI(title="Cytellect private API",version="0.1.0",docs_url=None,redoc_url=None)
    api.state.store, api.state.settings = store, settings
    api.add_middleware(CORSMiddleware,allow_origins=[settings.app_origin],allow_credentials=True,
                       allow_methods=["GET","POST","DELETE"],allow_headers=["Content-Type","X-Cytellect-Request"])
    attempts = {}

    @api.middleware("http")
    async def security(request: Request, call_next):
        if request.method not in ("GET","HEAD","OPTIONS"):
            if request.headers.get("origin") != settings.app_origin or request.headers.get("x-cytellect-request") != "1":
                return JSONResponse({"detail":"origin_or_csrf_invalid"},status_code=403,headers={"Cache-Control":"no-store"})
        response=await call_next(request)
        response.headers["Cache-Control"]="no-store"
        response.headers["X-Content-Type-Options"]="nosniff"
        response.headers["Referrer-Policy"]="no-referrer"
        response.headers["X-Frame-Options"]="DENY"
        return response

    @api.exception_handler(ValueError)
    async def invalid_input(_request, _error):
        return JSONResponse({"detail":"invalid_analysis_input"},status_code=422)

    def owner(request: Request):
        token=request.cookies.get(settings.cookie_name)
        session=store.one(sessions,digest=digest(token)) if token else None
        if not session or session["revoked"] or session["expires"]<=time.time():
            raise HTTPException(401,"session_required")
        return session["owner"]

    Owner=Annotated[str,Depends(owner)]

    def workspace(wid, who):
        value=store.one(workspaces,id=wid)
        if not value or value["owner"]!=who or value["deleted"] or value["expires"]<=time.time():
            raise HTTPException(404,"workspace_not_found")
        return value

    def revision(rid,who):
        value=store.one(revisions,id=rid)
        if not value:
            raise HTTPException(404,"revision_not_found")
        workspace(value["workspace_id"],who)
        return value

    def touch(conn,wid):
        conn.execute(update(workspaces).where(workspaces.c.id==wid).values(expires=time.time()+settings.retention_seconds))

    def queue(conn,wid,rid,kind,payload):
        count=conn.execute(select(func.count()).select_from(jobs).where(jobs.c.state.in_(["queued","running"]))).scalar_one()
        if count>=10:
            raise HTTPException(429,"queue_full")
        jid=uid()
        conn.execute(jobs.insert().values(id=jid,workspace_id=wid,revision_id=rid,kind=kind,state="queued",
                                         payload=payload,created=time.time(),attempts=0))
        touch(conn,wid)
        return jid

    def field_record(fid,who):
        f=store.one(fields,id=fid)
        if not f:
            raise HTTPException(404,"field_not_found")
        workspace(f["workspace_id"],who)
        return f

    def result_root(rev):
        if rev["state"]!="succeeded" or not rev["result_dir"]:
            raise HTTPException(409,"analysis_not_ready")
        return store.safe_path(rev["result_dir"])

    def public_revision(rev):
        return {k:rev[k] for k in ("id","workspace_id","parent_id","config","state","reviewed","created")}

    @api.get("/v1/health")
    def health():
        return {"status":"ok","version":"0.1.0","demo":settings.demo,"fiji_configured":bool(settings.fiji_executable)}

    @api.post("/v1/invitations/redeem")
    def redeem(body: InviteInput, request: Request, response: Response):
        key=digest(request.client.host if request.client else "unknown")
        now=time.time()
        recent=[t for t in attempts.get(key,[]) if t>now-60]
        if len(recent)>=10:
            raise HTTPException(429,"too_many_attempts")
        attempts[key]=[*recent,now]
        if len(attempts)>1000:
            for old in list(attempts):
                if not any(t>now-60 for t in attempts[old]):
                    attempts.pop(old,None)
        token=secrets.token_urlsafe(32)
        principal=uid()
        with store.transaction() as c:
            invitation=c.execute(select(invitations).where(invitations.c.digest==digest(body.token))).mappings().first()
            if not invitation or invitation["used"] or invitation["expires"]<=now:
                raise HTTPException(401,"invitation_invalid")
            c.execute(update(invitations).where(invitations.c.digest==digest(body.token)).values(used=True))
            c.execute(sessions.insert().values(digest=digest(token),owner=principal,expires=now+7*86400,revoked=False))
        response.set_cookie(settings.cookie_name,token,httponly=True,secure=settings.secure_cookies,samesite="strict",max_age=7*86400,path="/")
        return {"authenticated":True}

    @api.get("/v1/session")
    def session(who:Owner):
        return {"authenticated":True,"retention_hours":24,"demo":settings.demo}

    @api.delete("/v1/session")
    def logout(request:Request,response:Response,who:Owner):
        with store.transaction() as c:
            c.execute(update(sessions).where(sessions.c.digest==digest(request.cookies[settings.cookie_name])).values(revoked=True))
        response.delete_cookie(settings.cookie_name,path="/",secure=settings.secure_cookies,httponly=True,samesite="strict")
        return {"revoked":True}

    @api.get("/v1/workspaces")
    def list_workspaces(who:Owner):
        return [dict(r) for r in store.rows(workspaces,owner=who) if not r["deleted"] and r["expires"]>time.time()]

    @api.post("/v1/workspaces",status_code=201)
    def new_workspace(body:WorkspaceInput,who:Owner):
        wid=uid()
        with store.transaction() as c:
            c.execute(workspaces.insert().values(id=wid,owner=who,title=body.title,created=time.time(),
                     expires=time.time()+settings.retention_seconds,deleted=False,bytes=0))
        return dict(store.one(workspaces,id=wid))

    @api.get("/v1/workspaces/{wid}")
    def get_workspace(wid:str,who:Owner):
        return dict(workspace(wid,who))

    @api.delete("/v1/workspaces/{wid}")
    def delete_workspace(wid:str,who:Owner):
        workspace(wid,who)
        with store.transaction() as c:
            c.execute(update(workspaces).where(workspaces.c.id==wid).values(deleted=True))
            c.execute(update(jobs).where(jobs.c.workspace_id==wid,jobs.c.state.in_(["queued","running"])).values(state="cancelled"))
        return {"access_revoked":True,"files":"cleanup_pending"}

    @api.post("/v1/workspaces/{wid}/touch")
    def keep_alive(wid:str,who:Owner):
        workspace(wid,who)
        with store.transaction() as c:
            touch(c,wid)
        return {"expires":store.one(workspaces,id=wid)["expires"]}

    @api.get("/v1/workspaces/{wid}/fields")
    def list_fields(wid:str,who:Owner):
        workspace(wid,who)
        return [dict(r) for r in store.rows(fields,workspace_id=wid)]

    @api.post("/v1/workspaces/{wid}/fields",status_code=201)
    async def upload_field(wid:str,who:Owner,metadata:str=Form(...),legacy:bool=Form(False),
                           dapi:UploadFile|None=File(None),ncl:UploadFile|None=File(None),gfp:UploadFile|None=File(None),
                           ome:UploadFile|None=File(None),mapping:str=Form("[0,1,2]")):
        workspace(wid,who)
        if settings.demo:
            raise HTTPException(403,"demo_accepts_synthetic_only")
        try:
            md=FieldMetadata.model_validate_json(metadata)
        except ValidationError:
            raise HTTPException(422,"invalid_field_metadata") from None
        if (ome is None and any(f is None for f in (dapi,ncl,gfp))) or (ome is not None and any(f is not None for f in (dapi,ncl,gfp))):
            raise HTTPException(422,"provide_three_channels_or_one_ome")
        fid=uid()
        folder=store.safe_path("workspaces",wid,"fields",fid)
        folder.mkdir(parents=True)
        uploads={"ome":ome} if ome else {"dapi":dapi,"ncl":ncl,"gfp":gfp}
        total=0
        try:
            input_info={}
            for role,file in uploads.items():
                path=folder/f"{role}.tif"
                with path.open("wb") as output:
                    while chunk:=await file.read(1024*1024):
                        total+=len(chunk)
                        if total>256*1024**2:
                            raise HTTPException(413,"field_upload_limit")
                        output.write(chunk)
                input_info[role]={"sha256":sha256(path),"bytes":path.stat().st_size}
            if ome:
                indices=json.loads(mapping)
                if not isinstance(indices,list) or any(type(v) is not int for v in indices):
                    raise ValueError("invalid_mapping")
                stack=read_tiff(folder/"ome.tif",channel_indices=indices)
                channels=dict(zip(("dapi","ncl","gfp"),stack,strict=True))
            else:
                channels={c:read_tiff(folder/f"{c}.tif",legacy=legacy) for c in ("dapi","ncl","gfp")}
            if len({a.shape for a in channels.values()})!=1:
                raise ValueError("channel_dimensions_mismatch")
            for role,array in channels.items():
                np.save(folder/f"{role}.npy",array,allow_pickle=False)
            info={"shape":list(channels["dapi"].shape),"dtype":str(channels["dapi"].dtype),"legacy":legacy,"inputs":input_info,"axes":"YX",
                  "channel_mapping":json.loads(mapping) if ome else ["dapi","ncl","gfp"]}
            with store.transaction() as c:
                w=c.execute(select(workspaces).where(workspaces.c.id==wid)).mappings().one()
                count=c.execute(select(func.count()).select_from(fields).where(fields.c.workspace_id==wid)).scalar_one()
                if w["deleted"] or w["expires"]<=time.time():
                    raise HTTPException(404,"workspace_not_found")
                if count>=settings.max_fields or w["bytes"]+total>settings.max_upload_bytes:
                    raise HTTPException(413,"workspace_limit")
                c.execute(fields.insert().values(id=fid,workspace_id=wid,metadata=md.model_dump(),image_info=info,synthetic=False))
                c.execute(update(workspaces).where(workspaces.c.id==wid).values(bytes=w["bytes"]+total))
                touch(c,wid)
            return dict(store.one(fields,id=fid))
        except HTTPException:
            shutil.rmtree(folder)
            raise
        except Exception:
            shutil.rmtree(folder)
            raise HTTPException(422,"unsupported_or_invalid_image") from None
        finally:
            for file in uploads.values():
                if file:
                    await file.close()

    @api.post("/v1/workspaces/{wid}/synthetic",status_code=201)
    def synthetic(wid:str,who:Owner):
        workspace(wid,who)
        ids=[]
        with store.transaction() as c:
            count=c.execute(select(func.count()).select_from(fields).where(fields.c.workspace_id==wid)).scalar_one()
            if count+6>settings.max_fields:
                raise HTTPException(413,"field_limit")
            for i in range(6):
                fid=uid()
                folder=store.safe_path("workspaces",wid,"fields",fid)
                folder.mkdir(parents=True)
                channels,nuclei,nucleoli=synthetic_field(i)
                inputs={}
                for role,array in channels.items():
                    np.save(folder/f"{role}.npy",array,allow_pickle=False)
                    tifffile.imwrite(folder/f"{role}.tif",array)
                    inputs[role]={"sha256":sha256(folder/f"{role}.tif"),"bytes":(folder/f"{role}.tif").stat().st_size}
                np.savez_compressed(folder/"synthetic-truth.npz",nuclei=nuclei,nucleoli=nucleoli)
                md=FieldMetadata(condition="Control" if i%2==0 else "Treatment",experimental_unit=f"replicate-{i//2+1}",
                                 sample=f"sample-{i}",acquisition_date=f"batch-{i//2+1}",pair=f"pair-{i//2+1}",pixel_size_um=.25)
                info={"shape":[256,256],"dtype":"uint16","legacy":False,"inputs":inputs,"axes":"YX","channel_mapping":["dapi","ncl","gfp"]}
                c.execute(fields.insert().values(id=fid,workspace_id=wid,metadata=md.model_dump(),image_info=info,synthetic=True))
                ids.append(fid)
            touch(c,wid)
        return {"field_ids":ids,"synthetic":True,"background_polygon":[[0,0],[15,0],[15,15],[0,15]]}

    @api.get("/v1/fields/{fid}/preview")
    def preview(fid:str,who:Owner,channel:str="merge",low:float=0,high:float=100,gain:float=1):
        f=field_record(fid,who)
        if channel not in ("dapi","ncl","gfp","merge") or not 0<=low<high<=100 or not .1<=gain<=10:
            raise HTTPException(422,"invalid_display_settings")
        folder=store.safe_path("workspaces",f["workspace_id"],"fields",fid)
        channels={c:np.load(folder/f"{c}.npy",allow_pickle=False) for c in ("dapi","ncl","gfp")}
        return Response(render_preview(channels,channel,low,high,gain),media_type="image/png")

    @api.post("/v1/workspaces/{wid}/analyses",status_code=202)
    def start_analysis(wid:str,body:AnalysisRequest,who:Owner):
        workspace(wid,who)
        selected=store.rows(fields,workspace_id=wid)
        if not selected:
            raise HTTPException(422,"images_required")
        for f in selected:
            bg=body.backgrounds.get(f["id"])
            if body.recipe.id=="ncl-native-2d" and (not bg or not bg.confirmed):
                raise HTTPException(422,"confirm_background_for_every_field")
            if f["image_info"]["legacy"] != (body.recipe.id=="ncl-legacy-rgb"):
                raise HTTPException(422,"recipe_input_mode_mismatch")
        rid=uid()
        config=body.model_dump()
        config["field_ids"]=[f["id"] for f in selected]
        config["field_snapshot"]={f["id"]:dict(f) for f in selected}
        with store.transaction() as c:
            w=c.execute(select(workspaces).where(workspaces.c.id==wid)).mappings().one()
            c.execute(revisions.insert().values(id=rid,workspace_id=wid,parent_id=w["active_revision"],config=config,
                     state="queued",reviewed=False,created=time.time()))
            jid=queue(c,wid,rid,"analysis",{})
            c.execute(update(workspaces).where(workspaces.c.id==wid).values(active_revision=rid))
        return {"revision_id":rid,"job_id":jid}

    @api.get("/v1/workspaces/{wid}/revisions")
    def list_revisions(wid:str,who:Owner):
        workspace(wid,who)
        return [public_revision(r) for r in store.rows(revisions,workspace_id=wid)]

    @api.get("/v1/revisions/{rid}")
    def get_revision(rid:str,who:Owner):
        return public_revision(revision(rid,who))

    @api.get("/v1/revisions/{rid}/measurements")
    def measurements(rid:str,who:Owner):
        rev=revision(rid,who)
        return read_json(result_root(rev)/"measurements.json")

    @api.get("/v1/revisions/{rid}/fields/{fid}/masks")
    def get_masks(rid:str,fid:str,who:Owner):
        rev=revision(rid,who)
        if fid not in rev["config"]["field_ids"]:
            raise HTTPException(404,"field_not_found")
        path=result_root(rev)/fid/"masks.npz"
        if not path.exists():
            raise HTTPException(409,"field_failed")
        with np.load(path,allow_pickle=False) as masks:
            return {"nuclei":contours(masks["nuclei"]),"nucleoli":contours(masks["nucleoli"]),"manual":contours(masks["manual"])}

    @api.post("/v1/revisions/{rid}/edits",status_code=202)
    def edit(rid:str,body:MaskEdit,who:Owner):
        parent=revision(rid,who)
        result_root(parent)
        if body.field_id not in parent["config"]["field_ids"]:
            raise HTTPException(404,"field_not_found")
        child=uid()
        config=dict(parent["config"])
        config["edit"]=body.model_dump()
        config["reuse_revision"]=rid
        with store.transaction() as c:
            w=c.execute(select(workspaces).where(workspaces.c.id==parent["workspace_id"])).mappings().one()
            if w["active_revision"]!=rid:
                raise HTTPException(409,"stale_revision")
            c.execute(revisions.insert().values(id=child,workspace_id=w["id"],parent_id=rid,config=config,state="queued",reviewed=False,created=time.time()))
            jid=queue(c,w["id"],child,"analysis",{})
            c.execute(update(workspaces).where(workspaces.c.id==w["id"]).values(active_revision=child))
        return {"revision_id":child,"job_id":jid}

    @api.post("/v1/workspaces/{wid}/current")
    def choose_revision(wid:str,body:RevisionInput,who:Owner):
        workspace(wid,who)
        rev=revision(body.revision_id,who)
        if rev["workspace_id"]!=wid or rev["state"]!="succeeded":
            raise HTTPException(409,"invalid_revision")
        with store.transaction() as c:
            c.execute(update(workspaces).where(workspaces.c.id==wid).values(active_revision=rev["id"]))
            touch(c,wid)
        return public_revision(rev)

    @api.post("/v1/revisions/{rid}/review")
    def review(rid:str,who:Owner):
        rev=revision(rid,who)
        root=result_root(rev)
        report=read_json(root/"measurements.json")
        if report["field_failures"]:
            raise HTTPException(409,"resolve_or_explicitly_exclude_failed_fields")
        if report.get("invalidated_nucleoli"):
            raise HTTPException(409,"nucleolar_resegmentation_required")
        with store.transaction() as c:
            c.execute(update(revisions).where(revisions.c.id==rid).values(reviewed=True))
            touch(c,rev["workspace_id"])
        return {"reviewed":True}

    @api.post("/v1/revisions/{rid}/statistics",status_code=202)
    def statistics(rid:str,body:StatisticsRequest,who:Owner):
        rev=revision(rid,who)
        if rev["state"]!="succeeded" or not rev["reviewed"]:
            raise HTTPException(409,"review_required")
        with store.transaction() as c:
            jid=queue(c,rev["workspace_id"],rid,"statistics",body.model_dump())
        return {"job_id":jid}

    @api.post("/v1/revisions/{rid}/export",status_code=202)
    def export(rid:str,who:Owner,include_raw:bool=False):
        rev=revision(rid,who)
        result_root(rev)
        with store.transaction() as c:
            jid=queue(c,rev["workspace_id"],rid,"export",{"include_raw":include_raw})
        return {"job_id":jid}

    @api.get("/v1/workspaces/{wid}/jobs")
    def list_jobs(wid:str,who:Owner):
        workspace(wid,who)
        return [{k:r[k] for k in ("id","revision_id","kind","state","created","error","attempts")} for r in store.rows(jobs,workspace_id=wid)]

    def job_record(jid,who):
        j=store.one(jobs,id=jid)
        if not j:
            raise HTTPException(404,"job_not_found")
        workspace(j["workspace_id"],who)
        return j

    @api.get("/v1/jobs/{jid}")
    def get_job(jid:str,who:Owner):
        j=job_record(jid,who)
        return {k:j[k] for k in ("id","revision_id","kind","state","created","error","attempts")}

    @api.post("/v1/jobs/{jid}/cancel")
    def cancel(jid:str,who:Owner):
        j=job_record(jid,who)
        with store.transaction() as c:
            result=c.execute(update(jobs).where(jobs.c.id==jid,jobs.c.state.in_(["queued","running"])).values(state="cancelled"))
            if result.rowcount and j["kind"]=="analysis":
                c.execute(update(revisions).where(revisions.c.id==j["revision_id"]).values(state="cancelled"))
        return {"cancelled":bool(result.rowcount)}

    @api.get("/v1/jobs/{jid}/result")
    def job_result(jid:str,who:Owner):
        j=job_record(jid,who)
        if j["state"]!="succeeded" or not j["result_dir"]:
            raise HTTPException(409,"job_not_ready")
        path=store.safe_path(j["result_dir"])/"result.json"
        return read_json(path) if path.exists() else {"files":["analysis.zip"]}

    @api.get("/v1/jobs/{jid}/files/{name}")
    def job_file(jid:str,name:str,who:Owner):
        j=job_record(jid,who)
        allowed={"figure.png":"image/png","figure.svg":"image/svg+xml","figure.pdf":"application/pdf",
                 "plot-data.csv":"text/csv","comparisons.csv":"text/csv","experimental-units.csv":"text/csv",
                 "analysis.zip":"application/zip","methods.md":"text/markdown"}
        if name not in allowed or j["state"]!="succeeded" or not j["result_dir"]:
            raise HTTPException(404,"artifact_not_found")
        path=store.safe_path(j["result_dir"])/name
        if not path.is_file():
            raise HTTPException(404,"artifact_not_found")
        return FileResponse(path,media_type=allowed[name],filename=name)

    return api

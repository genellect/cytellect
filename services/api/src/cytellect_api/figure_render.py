"""Re-render an immutable result without recalculating observations or tests."""
from typing import Annotated, Any

from cytellect_analysis.common_statistics_contracts import AssociationPlot, CommonComparisonPlot
from cytellect_analysis.contracts import PlotSpec, StrictModel
from cytellect_analysis.descriptive_contracts import DescriptivePlot
from cytellect_analysis.figures import figure_settings
from fastapi import Depends, HTTPException
from pydantic import Field, ValidationError

from .db import jobs
from .storage import read_json


class FigureRenderRequest(StrictModel):
    plot: dict[str, Any]
    request_id: str = Field(min_length=1, max_length=100)


class PublicationPackageRequest(StrictModel):
    analysis_job_id: str = Field(min_length=1, max_length=100)
    request_id: str = Field(min_length=1, max_length=100)


def validated_plot(result, proposed):
    current = result.get("spec", {}).get("plot", {})
    kind = result.get("analysis_kind")
    model: type[AssociationPlot] | type[CommonComparisonPlot] | type[PlotSpec] | type[DescriptivePlot]
    if kind == "region-association":
        model = AssociationPlot
    elif result.get("region_comparison_version") == "2.0.0":
        model = CommonComparisonPlot
    elif kind == "region-comparison":
        model = PlotSpec
    elif result.get("spec", {}).get("mode") == "descriptive":
        model = DescriptivePlot
    elif result.get("source_kind") == "measured-numerical-assay":
        model = PlotSpec
    else:
        raise ValueError("figure_source_unsupported")
    value = model.model_validate({**current, **proposed})
    if value.language != "en":
        raise ValueError("figure_english_labels_required")
    figure_settings(value.model_dump(mode="json"))
    return value.model_dump(mode="json")


def register_figure_render_routes(api, store, owner, job_record, queue):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/jobs/{jid}/publication-package", status_code=202)
    def publication_package(jid: str, body: PublicationPackageRequest, who: Owner):
        figure = job_record(jid, who)
        analysis = job_record(body.analysis_job_id, who)
        if any(record["state"] != "succeeded" or not record["result_dir"] for record in (figure, analysis)):
            raise HTTPException(409, "job_not_ready")
        if figure["workspace_id"] != analysis["workspace_id"] or figure["revision_id"] != analysis["revision_id"]:
            raise HTTPException(409, "figure_source_mismatch")
        result = read_json(store.safe_path(figure["result_dir"], "result.json"))
        if not result.get("figure") or not store.safe_path(analysis["result_dir"], "analysis.zip").is_file():
            raise HTTPException(409, "publication_source_unavailable")
        payload = {"figure_job_id": jid, "analysis_job_id": body.analysis_job_id, "request_id": body.request_id}
        with store.transaction() as conn:
            from sqlalchemy import select
            previous = conn.execute(select(jobs).where(jobs.c.workspace_id == figure["workspace_id"],
                jobs.c.kind == "publication-package")).mappings().all()
            for item in previous:
                if item["payload"].get("request_id") == body.request_id:
                    if item["payload"] != payload:
                        raise HTTPException(409, "request_id_conflict")
                    return {"job_id": item["id"]}
            created = queue(conn, figure["workspace_id"], figure["revision_id"], "publication-package", payload)
        return {"job_id": created}

    @api.post("/v1/jobs/{jid}/figure-render", status_code=202)
    def render(jid: str, body: FigureRenderRequest, who: Owner):
        source = job_record(jid, who)
        if source["state"] != "succeeded" or not source["result_dir"]:
            raise HTTPException(409, "job_not_ready")
        result = read_json(store.safe_path(source["result_dir"], "result.json"))
        source_id = result.get("table_id") if result.get("source_kind") == "measured-numerical-assay" else result.get("revision_id")
        if source_id != source["revision_id"]:
            raise HTTPException(409, "figure_source_mismatch")
        try:
            plot = validated_plot(result, body.plot)
        except (ValidationError, ValueError):
            raise HTTPException(422, "figure_settings_invalid") from None
        payload = {"source_job_id": jid, "plot": plot, "request_id": body.request_id}
        with store.transaction() as conn:
            from sqlalchemy import select
            previous = conn.execute(select(jobs).where(
                jobs.c.workspace_id == source["workspace_id"], jobs.c.kind == "figure-render"
            )).mappings().all()
            for item in previous:
                if item["payload"].get("request_id") == body.request_id:
                    if item["payload"] != payload:
                        raise HTTPException(409, "request_id_conflict")
                    return {"job_id": item["id"]}
            created = queue(conn, source["workspace_id"], source["revision_id"], "figure-render", payload)
        return {"job_id": created}

    @api.get("/v1/jobs/{jid}/figure-render")
    def rendered(jid: str, who: Owner):
        job = job_record(jid, who)
        if job["kind"] != "figure-render" or job["state"] != "succeeded" or not job["result_dir"]:
            raise HTTPException(409, "job_not_ready")
        return read_json(store.safe_path(job["result_dir"], "result.json"))

"""Explicit common statistics on an owned, reviewed region revision."""
import time
from typing import Annotated, Any

from cytellect_analysis.common_statistics_contracts import (
    CommonStatisticsRequest,
    RegionAssociationResult,
    RegionComparisonResultV2,
)
from fastapi import Depends, HTTPException
from pydantic import Field, TypeAdapter

from .regions import is_region, require_compartment_revision, require_gfp_gate_source
from .storage import read_json
from .workspace_selection import assert_selection


class CommonComparisonView(RegionComparisonResultV2):
    figure: dict[str, Any]


class AssociationView(RegionAssociationResult):
    figure: dict[str, Any]


CommonStatisticsView = Annotated[
    CommonComparisonView | AssociationView, Field(discriminator="analysis_kind")
]


def register_common_statistics_routes(api, store, owner, revision, result_root, queue, job_record):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/revisions/{rid}/common-statistics", status_code=202)
    def calculate(rid: str, body: CommonStatisticsRequest, who: Owner):
        from cytellect_analysis.region_comparison import source_fingerprint

        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(422, "region_analysis_required")
        if rev["state"] != "succeeded" or not rev["reviewed"]:
            raise HTTPException(409, "review_required")
        if getattr(getattr(body, "selection", None), "source", None) == "compartment-summary":
            require_compartment_revision(rev)
        require_gfp_gate_source(rev, getattr(body, "selection", None))
        require_gfp_gate_source(rev, getattr(body, "x_selection", None))
        require_gfp_gate_source(rev, getattr(body, "y_selection", None))
        report = read_json(result_root(rev) / "measurements.json")
        if report["field_failures"]:
            raise HTTPException(409, "review_required")
        if rev["config"].get("recipe", {}).get("source") == "fiji_nuclear_compartment":
            from cytellect_analysis.compartment_review import assert_complete_compartments
            try:
                assert_complete_compartments(rev["config"], report, read_json(result_root(rev) / "provenance.json"))
            except ValueError as exc:
                raise HTTPException(409, str(exc)) from None
        config = {**rev["config"], "review_record": rev["review_record"] or {}}
        accepted = {
            "revision_id": rid,
            "confirmed_at": time.time(),
            "reviewed_at": config["review_record"].get("confirmed_at"),
            "source_fingerprint": source_fingerprint(report, config),
        }
        with store.transaction() as conn:
            if config.get("workspace_selection"):
                assert_selection(conn, rev["workspace_id"], config["workspace_selection"])
            jid = queue(conn, rev["workspace_id"], rid, "statistics",
                        {**body.model_dump(mode="json"), "_source_review": accepted})
        return {"job_id": jid}

    @api.get("/v1/jobs/{jid}/common-statistics", response_model=CommonStatisticsView)
    def result(jid: str, who: Owner):
        job = job_record(jid, who)
        payload = job["payload"]
        supported = (
            payload.get("mode") == "region-association" and payload.get("version") in ("1.0.0", "1.1.0")
        ) or (
            payload.get("mode") == "region-experimental-unit" and payload.get("version") == "2.0.0"
        )
        if job["kind"] != "statistics" or not supported or job["state"] != "succeeded" or not job["result_dir"]:
            raise HTTPException(404, "artifact_not_found")
        value: CommonComparisonView | AssociationView = TypeAdapter(CommonStatisticsView).validate_json(
            store.safe_path(job["result_dir"], "result.json").read_text(encoding="utf-8")
        )
        if value.revision_id != job["revision_id"]:
            raise HTTPException(409, "region_comparison_source_review_mismatch")
        return value

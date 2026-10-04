"""Queue explicit unit-level comparisons against a reviewed immutable source."""
import time
from typing import Annotated, Any

from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest, RegionComparisonResult
from fastapi import Depends, HTTPException

from .regions import is_region
from .storage import read_json


class RegionComparisonView(RegionComparisonResult):
    figure: dict[str, Any]


def register_region_comparison_routes(api, store, owner, revision, result_root, queue, job_record):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/revisions/{rid}/region-comparisons", status_code=202)
    def compare(rid: str, body: RegionComparisonRequest, who: Owner):
        from cytellect_analysis.region_comparison import source_fingerprint

        rev = revision(rid, who)
        if not is_region(rev):
            raise HTTPException(422, "region_analysis_required")
        if rev["state"] != "succeeded" or not rev["reviewed"]:
            raise HTTPException(409, "review_required")
        report = read_json(result_root(rev) / "measurements.json")
        if report["field_failures"]:
            raise HTTPException(409, "review_required")
        config = {**rev["config"], "review_record": rev["review_record"] or {}}
        source_review = {"revision_id": rid, "confirmed_at": time.time(),
                         "reviewed_at": config["review_record"].get("confirmed_at"),
                         "source_fingerprint": source_fingerprint(report, config)}
        with store.transaction() as conn:
            jid = queue(conn, rev["workspace_id"], rid, "statistics",
                        {**body.model_dump(mode="json"), "_source_review": source_review})
        return {"job_id": jid}

    @api.get("/v1/jobs/{jid}/region-comparison", response_model=RegionComparisonView)
    def result(jid: str, who: Owner):
        job = job_record(jid, who)
        if (job["kind"] != "statistics" or job["payload"].get("mode") != "region-experimental-unit"
                or job["payload"].get("version", "1.0.0") != "1.0.0"
                or job["state"] != "succeeded" or not job["result_dir"]):
            raise HTTPException(404, "artifact_not_found")
        value = RegionComparisonView.model_validate_json(
            store.safe_path(job["result_dir"], "result.json").read_text(encoding="utf-8"))
        if value.revision_id != job["revision_id"]:
            raise HTTPException(409, "region_comparison_source_review_mismatch")
        return value

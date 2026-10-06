"""Descriptive output retains the same ownership and scientific review gates."""

from typing import Annotated

from cytellect_analysis.descriptive_contracts import DescriptiveRequestType
from cytellect_analysis.review import unresolved_nucleolar_failures
from fastapi import Depends, HTTPException

from .regions import is_region
from .storage import read_json


def register_descriptive_routes(api, store, owner, revision, result_root, queue):
    Owner = Annotated[str, Depends(owner)]

    @api.post("/v1/revisions/{rid}/descriptive-preview", status_code=202)
    def descriptive_preview(rid: str, body: DescriptiveRequestType, who: Owner):
        rev = revision(rid, who)
        if (rev["state"] != "succeeded" or not is_region(rev)
                or rev["config"].get("recipe", {}).get("version") not in ("1.2.0", "1.3.0")):
            raise HTTPException(409, "workspace_measurements_required")
        if body.selection.source != "region":
            raise HTTPException(422, "descriptive_source_mismatch")
        report = read_json(result_root(rev) / "measurements.json")
        if report["field_failures"]:
            raise HTTPException(409, "resolve_failed_fields")
        payload = body.model_dump(mode="json")
        payload["_automatic_preview"] = True
        with store.transaction() as conn:
            jid = queue(conn, rev["workspace_id"], rid, "statistics", payload)
        return {"job_id": jid}

    @api.post("/v1/revisions/{rid}/descriptive", status_code=202)
    def descriptive(rid: str, body: DescriptiveRequestType, who: Owner):
        rev = revision(rid, who)
        if rev["state"] != "succeeded" or not rev["reviewed"]:
            raise HTTPException(409, "review_required")
        report = read_json(result_root(rev) / "measurements.json")
        accepted = set((rev["review_record"] or {}).get("accepted_invalidated_fields", []))
        if report["field_failures"] or set(report.get("invalidated_nucleoli", [])) - accepted:
            raise HTTPException(409, "review_required")
        if not is_region(rev) and unresolved_nucleolar_failures(report, rev["config"]):
            raise HTTPException(409, "resolve_or_explicitly_exclude_failed_nucleoli")
        expected_source = "region" if is_region(rev) else "legacy-cell"
        if body.selection.source != expected_source:
            raise HTTPException(422, "descriptive_source_mismatch")
        with store.transaction() as conn:
            jid = queue(conn, rev["workspace_id"], rid, "statistics", body.model_dump(mode="json"))
        return {"job_id": jid}

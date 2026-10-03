"""Source-bound, non-inferential statistics inside the supervised worker."""

from cytellect_analysis.descriptive import describe_legacy, describe_regions
from cytellect_analysis.descriptive_contracts import DescriptiveRequest
from cytellect_analysis.descriptive_figures import descriptive_methods, render_descriptive
from cytellect_analysis.review import unresolved_nucleolar_failures
from cytellect_api.db import revisions
from cytellect_api.storage import read_json, write_json


def run_descriptive(store, job, output):
    rev = store.one(revisions, id=job["revision_id"])
    if (rev is None or rev["workspace_id"] != job["workspace_id"]
            or rev["state"] != "succeeded" or not rev["reviewed"]):
        raise ValueError("review_required")
    report = read_json(store.safe_path(rev["result_dir"], "measurements.json"))
    accepted = set((rev["review_record"] or {}).get("accepted_invalidated_fields", []))
    if report["field_failures"] or set(report.get("invalidated_nucleoli", [])) - accepted:
        raise ValueError("review_required")
    request = DescriptiveRequest.model_validate(job["payload"])
    generic = rev["config"].get("analysis_kind") == "region-2d"
    if not generic and unresolved_nucleolar_failures(report, rev["config"]):
        raise ValueError("nucleolar_processing_failed")
    snapshot = rev["config"]["field_snapshot"]
    if set(snapshot) != set(rev["config"]["field_ids"]):
        raise ValueError("descriptive_field_snapshot_mismatch")
    result = (describe_regions if generic else describe_legacy)(report, snapshot, request)
    result["revision_id"] = rev["id"]
    result["figure"] = render_descriptive(result, output)
    (output / "methods.md").write_text(descriptive_methods(result), encoding="utf-8")
    write_json(output / "result.json", result)
    return output

"""Source-bound, non-inferential statistics inside the supervised worker."""

from cytellect_analysis.descriptive import describe_legacy, describe_regions
from cytellect_analysis.descriptive_contracts import parse_descriptive_request
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.review import unresolved_nucleolar_failures
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from cytellect_api.db import revisions
from cytellect_api.storage import read_json, write_json


def run_descriptive(store, job, output):
    rev = store.one(revisions, id=job["revision_id"])
    preview = job["payload"].get("_automatic_preview") is True
    preview_allowed = (preview and rev is not None
                       and rev["config"].get("analysis_kind") == "region-2d"
                       and rev["config"].get("recipe", {}).get("version") in ("1.2.0", "1.3.0"))
    if (rev is None or rev["workspace_id"] != job["workspace_id"]
            or rev["state"] != "succeeded" or (not rev["reviewed"] and not preview_allowed)):
        raise ValueError("review_required")
    report = read_json(store.safe_path(rev["result_dir"], "measurements.json"))
    accepted = set((rev["review_record"] or {}).get("accepted_invalidated_fields", []))
    if report["field_failures"] or set(report.get("invalidated_nucleoli", [])) - accepted:
        raise ValueError("review_required")
    payload = {key: value for key, value in job["payload"].items() if key != "_automatic_preview"}
    request = parse_descriptive_request(payload)
    generic = rev["config"].get("analysis_kind") == "region-2d"
    if not generic and unresolved_nucleolar_failures(report, rev["config"]):
        raise ValueError("nucleolar_processing_failed")
    snapshot = rev["config"]["field_snapshot"]
    if set(snapshot) != set(rev["config"]["field_ids"]):
        raise ValueError("descriptive_field_snapshot_mismatch")
    result = (describe_regions if generic else describe_legacy)(report, snapshot, request)
    result["revision_id"] = rev["id"]
    if preview:
        result["source_review"] = "automatic_unreviewed"
    result["figure"] = render_descriptive_output(result, output, methods_template=CURRENT_METHODS_TEMPLATE)
    write_json(output / "result.json", result)
    return output

"""Supervised comparisons retain the accepted source and design confirmation."""
import math

from cytellect_analysis.region_comparison_contracts import RegionComparisonRequest
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from cytellect_api.db import revisions
from cytellect_api.storage import read_json, write_json


def run_region_comparison(store, job, output):
    from cytellect_analysis.region_comparison import compare_regions, source_fingerprint
    from cytellect_analysis.region_comparison_figures import (
        render_region_comparison,
    )

    rev = store.one(revisions, id=job["revision_id"])
    if (rev is None or rev["workspace_id"] != job["workspace_id"]
            or rev["state"] != "succeeded" or not rev["reviewed"]
            or rev["config"].get("analysis_kind") != "region-2d"):
        raise ValueError("review_required")
    report = read_json(store.safe_path(rev["result_dir"], "measurements.json"))
    if report["field_failures"]:
        raise ValueError("review_required")
    config = {**rev["config"], "review_record": rev["review_record"] or {}}
    payload = dict(job["payload"])
    accepted = payload.pop("_source_review", {})
    timestamp = accepted.get("confirmed_at")
    if (set(accepted) != {"revision_id", "confirmed_at", "reviewed_at", "source_fingerprint"}
            or isinstance(timestamp, bool) or not isinstance(timestamp, (int, float))
            or not math.isfinite(timestamp) or timestamp <= 0
            or accepted["revision_id"] != rev["id"]
            or accepted["reviewed_at"] != config["review_record"].get("confirmed_at")
            or accepted["source_fingerprint"] != source_fingerprint(report, config)):
        raise ValueError("region_comparison_source_review_mismatch")
    request = RegionComparisonRequest.model_validate(payload)
    result = compare_regions(report, config, request)
    result["figure"] = render_region_comparison(result, output, methods_template=CURRENT_METHODS_TEMPLATE)
    write_json(output / "source-review.json", accepted)
    write_json(output / "result.json", result)
    return output

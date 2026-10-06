"""Run versioned common statistics without changing the reviewed source."""
import math
from typing import Any

from cytellect_analysis.common_statistics_contracts import (
    CommonStatisticsRequest,
    CommonStatisticsResult,
    RegionAssociationRequest,
    RegionComparisonRequestV2,
)
from cytellect_api.db import revisions
from cytellect_api.storage import read_json, write_json
from cytellect_api.workspace_selection import selection_at
from pydantic import TypeAdapter


def run_common_statistics(store, job, output):
    from cytellect_analysis.common_statistics import analyze_region_association, analyze_region_comparison
    from cytellect_analysis.common_statistics_figures import render_common_statistics
    from cytellect_analysis.region_comparison import source_fingerprint

    rev = store.one(revisions, id=job["revision_id"])
    if (rev is None or rev["workspace_id"] != job["workspace_id"]
            or rev["state"] != "succeeded" or not rev["reviewed"]
            or rev["config"].get("analysis_kind") != "region-2d"):
        raise ValueError("review_required")
    if rev["config"].get("workspace_selection"):
        with store.transaction() as conn:
            if selection_at(conn, job["workspace_id"]) != rev["config"]["workspace_selection"]:
                raise ValueError("workspace_selection_changed")
    report = read_json(store.safe_path(rev["result_dir"], "measurements.json"))
    if report["field_failures"]:
        raise ValueError("review_required")
    if rev["config"].get("recipe", {}).get("source") == "fiji_nuclear_compartment":
        from cytellect_analysis.compartment_review import assert_complete_compartments
        assert_complete_compartments(rev["config"], report, read_json(store.safe_path(rev["result_dir"], "provenance.json")))
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
    request: RegionComparisonRequestV2 | RegionAssociationRequest = TypeAdapter(CommonStatisticsRequest).validate_python(payload)
    if isinstance(request, RegionComparisonRequestV2) and (
            request.selection.source == "compartment-summary" or request.selection.gfp_gate is not None):
        from .compartment_sources import load_compartment_summaries
        from .gfp_sources import load_gfp_nuclear_source

        summaries = (load_compartment_summaries(store, rev, report)
                     if request.selection.source == "compartment-summary" else None)
        nuclear = load_gfp_nuclear_source(store, rev, report) if request.selection.gfp_gate is not None else None
        value = analyze_region_comparison(report, config, request, summaries=summaries, nuclear=nuclear)
    else:
        calculate = analyze_region_association if request.mode == "region-association" else analyze_region_comparison
        value = calculate(report, config, request)
    result: dict[str, Any] = TypeAdapter(CommonStatisticsResult).validate_python(value).model_dump(mode="json")
    result["figure"] = render_common_statistics(result, output)
    write_json(output / "source-review.json", accepted)
    write_json(output / "result.json", result)
    return output

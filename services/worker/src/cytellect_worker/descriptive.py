"""Source-bound, non-inferential statistics inside the supervised worker."""

import zipfile
from pathlib import Path

from cytellect_analysis.descriptive import describe_legacy, describe_regions
from cytellect_analysis.descriptive_contracts import parse_descriptive_request
from cytellect_analysis.descriptive_output import render_descriptive_output
from cytellect_analysis.images import sha256
from cytellect_analysis.review import unresolved_nucleolar_failures
from cytellect_analysis.statistical_methods import CURRENT_METHODS_TEMPLATE
from cytellect_api.db import revisions
from cytellect_api.storage import read_json, write_json


def _gfp_source(store, rev, report, request):
    if getattr(request.selection, "gfp_gate", None) is None:
        return None
    from .gfp_sources import load_gfp_nuclear_source

    return load_gfp_nuclear_source(store, rev, report)


def run_descriptive(store, job, output):
    rev = store.one(revisions, id=job["revision_id"])
    preview = job["payload"].get("_automatic_preview") is True
    preview_allowed = (preview and rev is not None
                       and rev["config"].get("analysis_kind") == "region-2d"
                       and rev["config"].get("recipe", {}).get("version") in ("1.2.0", "1.3.0", "1.4.0", "1.5.0", "1.7.0"))
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
    if request.selection.source == "compartment-summary":
        from cytellect_analysis.compartment_observations import describe_compartment_summary

        from .compartment_sources import load_compartment_summaries

        if not generic or preview:
            raise ValueError("descriptive_source_mismatch")
        result = describe_compartment_summary(report, snapshot, request, load_compartment_summaries(store, rev, report),
                                              nuclear=_gfp_source(store, rev, report, request))
    elif generic:
        if preview and getattr(request.selection, "gfp_gate", None) is not None:
            raise ValueError("gfp_gate_preview_unsupported")
        result = describe_regions(report, snapshot, request, nuclear=_gfp_source(store, rev, report, request))
    else:
        result = describe_legacy(report, snapshot, request)
    result["revision_id"] = rev["id"]
    if preview:
        result["source_review"] = "automatic_unreviewed"
    result["figure"] = render_descriptive_output(result, output, methods_template=CURRENT_METHODS_TEMPLATE)
    write_json(output / "result.json", result)
    if result["figure"].get("status", "ready") == "ready":
        files = result["figure"]["source_files"]
        if not files or any(Path(name).name != name or (output / name).is_symlink()
                            or not (output / name).is_file() for name in files):
            raise ValueError("descriptive_output_artifact_mismatch")
        archive = output / "figure.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            for name in files:
                bundle.write(output / name, arcname=name)
        write_json(output / "figure-archive.json", {"sha256": sha256(archive), "bytes": archive.stat().st_size})
    return output

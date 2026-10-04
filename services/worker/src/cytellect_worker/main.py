"""Allowlisted scientific jobs. Parent supervises children; only fenced DB commit publishes."""

import argparse
import shutil
import time

import numpy as np
from cytellect_analysis.contracts import MaskEdit, Recipe, StatisticsRequest
from cytellect_analysis.exports import build_export_bundle
from cytellect_analysis.figures import render_figures
from cytellect_analysis.masks import apply_edit, detect_nucleoli, polygon_mask
from cytellect_analysis.measurement import apply_gfp_gate, measure, normalize_nucleolar_states
from cytellect_analysis.numeric_export import build_numeric_bundle
from cytellect_analysis.numerical_csv import analyze_numeric
from cytellect_analysis.plan_adoption import validate_revision_plan
from cytellect_analysis.statistics import analyze_sensitivity
from cytellect_api.config import Settings
from cytellect_api.db import Store, attempts, fields, jobs, revisions, sessions, tables, workspaces
from cytellect_api.storage import read_json, write_json
from sqlalchemy import delete, select, update

from .errors import SAFE_ERRORS
from .provenance import software_identity

FIELD_ERRORS = {
    "fiji_not_configured",
    "fiji_adapter_not_installed",
    "background_missing",
    "parent_revision_unavailable",
    "unknown_label",
    "overlap_requires_explicit_merge",
    "nucleolus_outside_parent",
    "nucleolus_requires_single_parent",
    "invalid_polygon",
    "empty_polygon",
    "polygon_outside_image",
    "split_requires_partial_region",
    "unknown_excluded_nucleus",
}


def _load_channels(folder, image_info):
    return {name: np.load(folder / f"{name}.npy", allow_pickle=False)
            for name in image_info.get("channel_roles", ("dapi", "ncl", "gfp"))}


def _initial_masks(field, folder, channels, recipe, settings, destination, nuclei=None):
    if settings.fiji_executable:
        from cytellect_analysis.engine import detect

        result = detect(channels, recipe, destination / "engine", settings.fiji_executable, nuclei=nuclei,
                        scratch_root=destination.parent.parent)
        return *result[:2], np.zeros_like(result[0]), result[2]
    if field["synthetic"]:
        if nuclei is not None:
            if recipe.id == "gfp-nuclear-2d":
                nucleoli, statuses = np.zeros_like(nuclei), {}
            else:
                nucleoli, statuses = detect_nucleoli(nuclei, channels["ncl"], channels["dapi"], recipe)
            return (
                nuclei,
                nucleoli,
                np.zeros_like(nuclei),
                {"engine": "synthetic-python-reference", "candidate_status": statuses},
            )
        with np.load(folder / "synthetic-truth.npz", allow_pickle=False) as truth:
            return (
                truth["nuclei"],
                np.zeros_like(truth["nuclei"]) if recipe.id == "gfp-nuclear-2d" else truth["nucleoli"],
                np.zeros_like(truth["nuclei"]),
                {"engine": "synthetic-truth"},
            )
    raise ValueError("fiji_not_configured")


def run_analysis(store, settings, job, output):
    revision = store.one(revisions, id=job["revision_id"])
    if revision is None:
        raise ValueError("revision_not_found")
    config = revision["config"]
    validate_revision_plan(config)
    if config.get("analysis_kind") == "region-2d":
        from .regions import run_region_analysis

        return run_region_analysis(store, settings, job, output)
    if config.get("analysis_kind") is not None:
        raise ValueError("unknown_analysis_kind")
    recipe = Recipe.model_validate(config["recipe"])
    output.mkdir(parents=True, exist_ok=False)
    parent = None
    previous_report = {}
    previous_provenance = {}
    if config.get("reuse_revision"):
        parent = store.one(revisions, id=config["reuse_revision"])
        if (
            parent is None
            or parent["workspace_id"] != revision["workspace_id"]
            or parent["state"] != "succeeded"
        ):
            raise ValueError("parent_revision_unavailable")
        previous_report = read_json(store.safe_path(parent["result_dir"], "measurements.json"))
        previous_provenance = read_json(store.safe_path(parent["result_dir"], "provenance.json"))
    invalidated = set(previous_report.get("invalidated_nucleoli", []))
    accepted = (
        set((parent["review_record"] or {}).get("accepted_invalidated_fields", [])) if parent else set()
    )
    invalidated -= accepted
    edit = MaskEdit.model_validate(config["edit"]) if config.get("edit") else None
    cells, objects, manual_rows, failures, excluded_failures = [], [], [], [], []
    engine_provenance = {}
    for field_id in config["field_ids"]:
        exclusion = next(
            (
                e["reason"]
                for e in config["exclusions"]
                if e["field_id"] == field_id and e["nucleus_id"] is None
            ),
            None,
        )
        try:
            field = store.one(fields, id=field_id)
            if field is None or field["workspace_id"] != revision["workspace_id"]:
                raise ValueError("field_snapshot_missing")
            snapshot = config["field_snapshot"][field_id]
            folder = store.safe_path("workspaces", revision["workspace_id"], "fields", field_id)
            channels = _load_channels(folder, snapshot["image_info"])
            destination = output / field_id
            destination.mkdir()
            old_path = store.safe_path(parent["result_dir"], field_id, "masks.npz") if parent else None
            nucleolar_states = {}
            if old_path and old_path.is_file():
                assert parent is not None
                with np.load(old_path, allow_pickle=False) as old:
                    nuclei, nucleoli, manual = old["nuclei"], old["nucleoli"], old["manual"]
                engine_provenance[field_id] = {
                    "engine": "reused-reviewed-labels",
                    "source_revision": parent["id"],
                    "source_provenance": previous_provenance.get("fields", {}).get(field_id, {}),
                }
                nucleolar_states = {row["nucleus_id"]: row["nucleolar_status"]
                                     for row in previous_report.get("cells", [])
                                     if row["field_id"] == field_id and row.get("nucleolar_status")
                                     not in (None, "none_or_indeterminate")}
                if edit and edit.field_id == field_id:
                    before_nuclei, before_nucleoli = nuclei, nucleoli
                    nuclei, nucleoli, manual = apply_edit(nuclei, nucleoli, manual, edit)
                    if edit.layer == "nuclei" and recipe.id != "gfp-nuclear-2d":
                        invalidated.add(field_id)
                        changed = before_nuclei != nuclei
                        affected = set(np.unique(before_nuclei[changed])) | set(np.unique(nuclei[changed]))
                        failed_parents = [label for label, state in nucleolar_states.items()
                                          if state == "processing_failed"]
                        failed_pixels = np.isin(before_nuclei, failed_parents)
                        for label in affected - {0}:
                            # Changing a nuclear outline alone cannot turn a
                            # failed candidate operation into a reviewable absence.
                            nucleolar_states[int(label)] = (
                                "processing_failed" if np.any(failed_pixels & (nuclei == label))
                                else "review_required")
                    elif edit.layer == "nucleoli":
                        for label in np.unique(nuclei[before_nucleoli != nucleoli]):
                            if label:
                                nucleolar_states[int(label)] = (
                                    "candidate" if np.any(nucleoli[nuclei == label]) else "no_candidate")
                if field_id in config.get("resegment_fields", []):
                    nuclei, nucleoli, _, provenance = _initial_masks(
                        field, folder, channels, recipe, settings, destination, nuclei=nuclei
                    )
                    engine_provenance[field_id] = provenance
                    nucleolar_states = normalize_nucleolar_states(provenance)
                    invalidated.discard(field_id)
            else:
                nuclei, nucleoli, manual, provenance = _initial_masks(
                    field, folder, channels, recipe, settings, destination
                )
                engine_provenance[field_id] = provenance
                nucleolar_states = normalize_nucleolar_states(provenance)
            background = config["backgrounds"].get(field_id)
            if recipe.id == "ncl-legacy-rgb":
                background_mask = np.zeros(nuclei.shape, dtype=bool)
            else:
                if not background:
                    raise ValueError("background_missing")
                background_mask = polygon_mask(nuclei.shape, background["polygon"])
            fc, fo, fm = measure(
                channels, nuclei, nucleoli, background_mask, recipe, snapshot["metadata"], field_id, manual,
                nucleolar_states=nucleolar_states,
            )
            engine_provenance[field_id]["nucleolar_states"] = {
                row["nucleus_id"]: row["nucleolar_status"] for row in fc}
            excluded = {
                e["nucleus_id"]: e["reason"] for e in config["exclusions"] if e["field_id"] == field_id
            }
            known_nuclei = {r["nucleus_id"] for r in fc}
            if any(key is not None and key not in known_nuclei for key in excluded):
                raise ValueError("unknown_excluded_nucleus")
            for row in fc:
                reason = exclusion or excluded.get(row["nucleus_id"])
                if reason:
                    row.update(excluded=True, exclusion_reason=reason)
            np.savez_compressed(destination / "masks.npz", nuclei=nuclei, nucleoli=nucleoli, manual=manual)
            cells.extend(fc)
            objects.extend(fo)
            manual_rows.extend(fm)
        except Exception as exc:
            if exclusion:
                excluded_failures.append({"field_id": field_id, "reason": exclusion})
                invalidated.discard(field_id)
            else:
                failures.append(
                    {
                        "field_id": field_id,
                        "reason": str(exc)
                        if str(exc) in FIELD_ERRORS | SAFE_ERRORS
                        else "field_analysis_failed",
                        "category": type(exc).__name__,
                    }
                )
    cells = apply_gfp_gate(cells, recipe)
    report = {
        "revision_id": revision["id"],
        "recipe": recipe.model_dump(),
        "engine_provenance": engine_provenance,
        "cells": cells,
        "nucleoli": objects,
        "nucleolar_failures": [{"field_id": row["field_id"], "nucleus_id": row["nucleus_id"]}
                               for row in cells if row["nucleolar_status"] == "processing_failed"],
        "manual_rois": manual_rows,
        "field_failures": failures,
        "excluded_failed_fields": excluded_failures,
        "invalidated_nucleoli": sorted(invalidated),
    }
    write_json(output / "measurements.json", report)
    write_json(
        output / "provenance.json",
        {
            "fields": engine_provenance,
            "software": software_identity(),
            "revision_id": revision["id"],
            "recipe": recipe.model_dump(),
            "seed": recipe.seed,
            "input_hashes": {fid: f["image_info"]["inputs"] for fid, f in config["field_snapshot"].items()},
        },
    )
    return output


def run_statistics(store, job, output):
    source = store.one(revisions, id=job["revision_id"])
    if source is None or source["workspace_id"] != job["workspace_id"]:
        raise ValueError("revision_not_found")
    validate_revision_plan(source["config"])
    if job["payload"].get("mode") == "descriptive":
        from .descriptive import run_descriptive

        return run_descriptive(store, job, output)
    if (job["payload"].get("mode") == "region-association"
            or (job["payload"].get("mode") == "region-experimental-unit"
                and job["payload"].get("version") == "2.0.0")):
        from .common_statistics import run_common_statistics

        return run_common_statistics(store, job, output)
    if job["payload"].get("mode") == "region-experimental-unit":
        from .region_comparisons import run_region_comparison

        return run_region_comparison(store, job, output)
    from cytellect_analysis.region_sensitivity import DEFINITION_KEYS
    from cytellect_analysis.review import unresolved_nucleolar_failures
    from cytellect_api.region_sensitivity import validate_region_revision

    revision = store.one(revisions, id=job["revision_id"])
    root = store.safe_path(revision["result_dir"])
    report = read_json(root / "measurements.json")
    accepted = set((revision["review_record"] or {}).get("accepted_invalidated_fields", []))
    if (
        not revision["reviewed"]
        or report["field_failures"]
        or set(report.get("invalidated_nucleoli", [])) - accepted
    ):
        raise ValueError("review_required")
    if unresolved_nucleolar_failures(report, revision["config"]):
        raise ValueError("nucleolar_processing_failed")
    request = StatisticsRequest.model_validate(job["payload"])
    alternate_rows = {}
    alternate_sources: list[dict] = []
    for rid in request.sensitivity_region_revision_ids:
        alternate = store.one(revisions, id=rid)
        if alternate is None:
            raise ValueError("region_sensitivity_revision_unavailable")
        alternate_report = validate_region_revision(store, revision, alternate, check_masks=True)
        alternate_rows[rid] = alternate_report["cells"]
        relative_path = f"alternatives/{len(alternate_sources)}"
        destination = output / relative_path
        destination.mkdir(parents=True, exist_ok=False)
        write_json(destination / "revision.json", {"id": rid, "config": {
            **alternate["config"], "review_record": alternate["review_record"] or {}}})
        write_json(destination / "measurements.json", alternate_report)
        shutil.copyfile(store.safe_path(alternate["result_dir"], "provenance.json"), destination / "provenance.json")
        for fid in alternate["config"]["field_ids"]:
            target = destination / "masks" / fid / "labels.npz"
            target.parent.mkdir(parents=True)
            shutil.copyfile(store.safe_path(alternate["result_dir"], fid, "masks.npz"), target)
        alternate_sources.append({"revision_id": rid, "relative_path": relative_path,
                                  "reviewed": True, "nucleolar_definition": {
                                      key: alternate["config"]["recipe"][key] for key in sorted(DEFINITION_KEYS)}})
    result = analyze_sensitivity(report["cells"], request, alternate_rows=alternate_rows)
    result["region_sensitivity_sources"] = alternate_sources
    result["revision_id"] = revision["id"]
    result["figure"] = render_figures(result, output)
    write_json(output / "result.json", result)
    return output


def run_table_statistics(store, job, output):
    table = store.one(tables, id=job["revision_id"])
    if table is None or table["workspace_id"] != job["workspace_id"]:
        raise ValueError("table_not_found")
    data = read_json(store.safe_path("workspaces", job["workspace_id"], "tables", table["id"], "table.json"))
    result = analyze_numeric(data["rows"], StatisticsRequest.model_validate(job["payload"]))
    result["table_id"] = table["id"]
    result["figure"] = render_figures(result, output)
    build_numeric_bundle(
        output,
        content=store.safe_path("workspaces", job["workspace_id"], "tables", table["id"], "input.csv").read_bytes(),
        table_id=table["id"], result=result, provenance={"software": software_identity()},
    )
    write_json(output / "result.json", result)
    return output


def run_export(store, job, output):
    revision = store.one(revisions, id=job["revision_id"])
    if revision["config"].get("analysis_kind") == "region-2d":
        from .regions import run_region_export

        return run_region_export(store, job, output)
    root = store.safe_path(revision["result_dir"])
    def masks():
        # Decode only one field while the bundle writer consumes it.
        for file in sorted(root.glob("*/masks.npz")):
            with np.load(file, allow_pickle=False) as data:
                yield file.parent.name, {k: data[k] for k in ("nuclei", "nucleoli", "manual")}
    raw = []
    if job["payload"].get("include_raw", False):
        for fid, snapshot in revision["config"]["field_snapshot"].items():
            for role in snapshot["image_info"]["inputs"]:
                raw.append(
                    (
                        f"{fid}/{role}.tif",
                        store.safe_path("workspaces", revision["workspace_id"], "fields", fid, f"{role}.tif"),
                    )
                )
    statistics_results: list[dict] = []
    statistics_roots = []
    for record in store.rows(jobs, revision_id=revision["id"], kind="statistics", state="succeeded"):
        statistics_roots.append((len(statistics_results), store.safe_path(record["result_dir"])))
        statistics_results.append(read_json(store.safe_path(record["result_dir"], "result.json")))
    build_export_bundle(
        output,
        report=read_json(root / "measurements.json"),
        config={**revision["config"], "review_record": revision["review_record"] or {}},
        provenance=read_json(root / "provenance.json"),
        field_masks=masks(),
        raw_files=raw,
        statistics_results=statistics_results,
        statistics_roots=statistics_roots,
        include_raw=bool(job["payload"].get("include_raw", False)),
    )
    write_json(
        output / "result.json",
        {"files": ["analysis.zip", "methods.md"], "raw_included": bool(raw), "revision_id": revision["id"]},
    )
    return output


def process_one(store, settings):
    from .supervision import execute

    job = store.claim()
    if job is None:
        return False
    execute(store, settings, job)
    return True


def cleanup(store):
    now = time.time()
    removed = 0
    with store.transaction() as conn:
        expired = (
            conn.execute(
                select(workspaces).where(workspaces.c.deleted.is_(True) | (workspaces.c.expires <= now))
            )
            .mappings()
            .all()
        )
        for workspace in expired:
            wid = workspace["id"]
            if conn.execute(
                select(jobs.c.id).where(jobs.c.workspace_id == wid, jobs.c.lease_until > now)
            ).first():
                continue
            folder = store.safe_path("workspaces", wid)
            legacy_paths = [
                r[0]
                for r in conn.execute(select(revisions.c.result_dir).where(revisions.c.workspace_id == wid))
                if r[0]
            ]
            legacy_paths += [
                r[0]
                for r in conn.execute(select(jobs.c.result_dir).where(jobs.c.workspace_id == wid))
                if r[0]
            ]
            for value in legacy_paths:
                target = store.safe_path(value)
                if (
                    target != store.root
                    and target.parts[len(store.root.parts)] in {"artifacts", "results"}
                    and target.exists()
                ):
                    shutil.rmtree(target)
            if folder.exists():
                shutil.rmtree(folder)
                removed += 1
            for record in conn.execute(select(attempts).where(attempts.c.workspace_id == wid)).mappings():
                run = store.safe_path("runs", record["id"])
                if run.exists():
                    shutil.rmtree(run)
            for table in (attempts, tables, fields, revisions, jobs):
                conn.execute(delete(table).where(table.c.workspace_id == wid))
            conn.execute(
                update(workspaces)
                .where(workspaces.c.id == wid)
                .values(deleted=True, title="", bytes=0, active_revision=None)
            )
        conn.execute(delete(sessions).where(sessions.c.revoked.is_(True) | (sessions.c.expires <= now)))
    return {"workspaces_removed": removed}


def main():
    parser = argparse.ArgumentParser(prog="cytellect-worker")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--poll-seconds", type=float, default=2)
    args = parser.parse_args()
    settings = Settings.from_env()
    store = Store(settings.data_dir)
    while True:
        cleanup(store)
        worked = process_one(store, settings)
        if args.once:
            return
        if not worked:
            time.sleep(max(args.poll_seconds, 0.1))


if __name__ == "__main__":
    main()

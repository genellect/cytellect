"""One request script for both runners: Pyodide (harness.mjs) and CPython (here).

The script format is documented in services/showcase/pyodide/harness.mjs. The
CPython runner has the same semantics so browser outputs can be compared with
the server implementation on identical requests.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import re

import pytest
from cytellect_showcase import runtime

PROPOSAL_MISS = "記録していない目的"


def workflow_steps(info: dict, goal: str) -> list[dict]:
    wid, fid = info["workspace_id"], info["field_ids"][0]
    adopted = {entry["field_id"]: entry["revision_id"] for entry in info["selection"]["entries"]}
    selection = json.loads(json.dumps(info["selection"]))
    for entry in selection["entries"]:
        if entry["field_id"] == fid:
            entry["revision_id"] = "{edit.revision_id}"
            if entry.get("target_revisions"):
                entry["target_revisions"]["nuclei"] = "{edit.revision_id}"
    sources = [{"field_id": e["field_id"], "revision_id": e["revision_id"]} for e in selection["entries"]]
    region = {"source": "region", "region_set_id": "nuclei", "channel_id": "gfp", "metric": "mean"}

    def job(name: str) -> dict:
        return {"poll": f"/v1/jobs/{{{name}.job_id}}", "until": "state", "in": ["succeeded", "failed"],
                "label": f"job:{name}", "print": True}

    return [
        {"url": "/v1/session"},
        {"url": "/v1/workspaces"},
        {"url": f"/v1/workspaces/{wid}/region-fields"},
        {"url": f"/v1/region-fields/{fid}/preview?channel_id=gfp", "label": "preview"},
        {"url": f"/v1/revisions/{adopted[fid]}/region-measurements", "save": "before"},
        {"url": f"/v1/revisions/{adopted[fid]}/region-masks?field_id={fid}", "save": "masks"},
        {"method": "POST", "url": f"/v1/workspaces/{wid}/current", "body": {"revision_id": adopted[fid]}},
        {"method": "POST", "url": f"/v1/revisions/{adopted[fid]}/region-edits", "save": "edit", "body": {
            "field_id": fid, "region_set_id": "nuclei", "operation": "delete", "ids": ["{masks.regions.0.id}"],
            "expected_mask_revision_id": f"{{before.field_masks.{fid}.mask_revision_id}}"}},
        job("edit"),
        {"url": "/v1/revisions/{edit.revision_id}/region-measurements", "label": "edited-measurements", "print": True},
        {"method": "POST", "url": f"/v1/workspaces/{wid}/selection", "body": selection, "save": "selection"},
        {"url": f"/v1/workspaces/{wid}", "save": "workspace"},
        {"method": "POST", "url": f"/v1/workspaces/{wid}/region-cohorts", "save": "cohort", "body": {
            "sources": sources, "metadata": info["metadata"], "workspace_selection": "{selection}",
            "expected_active_revision_id": "{workspace.active_revision}"}},
        job("cohort"),
        {"method": "POST", "url": "/v1/revisions/{cohort.revision_id}/review", "body": {}},
        {"method": "POST", "url": "/v1/revisions/{cohort.revision_id}/descriptive", "save": "described", "body": {
            "mode": "descriptive", "selection": region, "plot": {"preset": "nature-double", "language": "ja"},
            "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}},
        job("described"),
        {"url": "/v1/jobs/{described.job_id}/result", "label": "descriptive", "print": True},
        {"method": "POST", "url": "/v1/revisions/{cohort.revision_id}/common-statistics", "save": "statistics",
         "body": {
             "mode": "region-experimental-unit", "version": "2.0.0", "selection": region,
             "design": {"kind": "independent", "confirmed": True, "unit_definition": "Separate crops (test only)"},
             "conditions": ["A01", "A12"],
             "comparison_family": {"family_id": "planned-1", "kind": "control", "control": "A01",
                                   "contrasts": [["A01", "A12"]]},
             "acquisition_review": {"confirmed": True, "basis": "same-settings"}, "missingness_confirmed": True,
             "test": "mann-whitney-u", "plot": {"kind": "box", "language": "en", "y_label": "GFP"}}},
        job("statistics"),
        {"url": "/v1/jobs/{statistics.job_id}/common-statistics", "label": "common-statistics", "print": True},
        {"url": "/v1/jobs/{statistics.job_id}/files/figure.svg", "label": "figure.svg"},
        {"method": "POST", "url": "/v1/revisions/{cohort.revision_id}/export", "save": "export"},
        job("export"),
        {"method": "POST", "url": "/v1/jobs/{statistics.job_id}/figure-render", "save": "render",
         "body": {"request_id": "showcase-render", "plot": {"y_label": "GFP mean"}}},
        job("render"),
        {"method": "POST", "url": "/v1/jobs/{render.job_id}/publication-package", "save": "package",
         "body": {"analysis_job_id": "{export.job_id}", "request_id": "showcase-package"}},
        job("package"),
        {"url": "/v1/jobs/{package.job_id}/files/publication.zip", "label": "publication.zip"},
        {"method": "POST", "url": f"/v1/workspaces/{wid}/proposal-drafts", "label": "proposal-hit", "print": True,
         "body": {"goal": goal, "transmission_confirmed": True}},
        {"method": "POST", "url": f"/v1/workspaces/{wid}/proposal-drafts", "label": "proposal-miss",
         "body": {"goal": PROPOSAL_MISS, "transmission_confirmed": True}},
        {"url": f"/v1/workspaces/{wid}/jobs", "label": "jobs", "print": True},
    ]


def _lookup(saved: dict, expression: str):
    value: object = saved
    for key in expression.split("."):
        value = value[int(key)] if isinstance(value, list) else value[key]  # type: ignore[index]
    return value


def _fill(saved: dict, value):
    if isinstance(value, str):
        if re.fullmatch(r"\{[A-Za-z0-9_.-]+\}", value):
            return _lookup(saved, value[1:-1])
        return re.sub(r"\{([A-Za-z0-9_.-]+)\}", lambda m: str(_lookup(saved, m.group(1))), value)
    if isinstance(value, list):
        return [_fill(saved, v) for v in value]
    if isinstance(value, dict):
        return {k: _fill(saved, v) for k, v in value.items()}
    return value


async def run_steps_in_cpython(steps: list[dict]) -> list[dict]:
    saved: dict = {}

    async def request(method, url, body):
        headers = [["x-cytellect-request", "1"]] if method not in ("GET", "HEAD") else []
        payload = None
        if body is not None:
            payload = json.dumps(_fill(saved, body)).encode()
            headers.append(["content-type", "application/json"])
        response = await runtime.handle(method, _fill(saved, url), headers, payload)
        kind = next((v for k, v in response["headers"] if k.lower() == "content-type"), "")
        value = json.loads(response["body"]) if kind.startswith("application/json") else None
        return {"status": response["status"], "type": kind, "bytes": len(response["body"]),
                "sha256": hashlib.sha256(response["body"]).hexdigest(), "json": value}

    lines = []
    for step in steps:
        if step.get("settle"):
            await runtime.settle()
            continue
        if step.get("poll"):
            for _ in range(600):
                result = await request("GET", step["poll"], None)
                if result["status"] != 200 or result["json"].get(step["until"]) in step["in"]:
                    break
                await asyncio.sleep(0.01)
        else:
            result = await request(step.get("method", "GET"), step["url"], step.get("body"))
        if step.get("save"):
            saved[step["save"]] = result["json"]
        lines.append({"step": step.get("label") or step.get("url") or step.get("poll"), **result})
    return lines


def assert_workflow(lines: list[dict], info: dict, recipe: str) -> None:
    labelled = {line["step"]: line for line in lines}
    failures = [(line["step"], line["status"], line.get("json")) for line in lines
                if line["status"] >= 400 and line["step"] != "proposal-miss"]
    assert not failures, failures
    assert labelled["proposal-miss"]["status"] == 409
    assert labelled["proposal-miss"]["json"]["detail"] == "showcase_proposal_not_recorded"
    assert labelled["proposal-hit"]["json"]["proposal"]["draft"]["recipe"] == recipe
    jobs = [line["json"] for line in lines if line["step"].startswith("job:")]
    assert len(jobs) == 7 and all(job["state"] == "succeeded" for job in jobs), [
        (job["kind"], job.get("error")) for job in jobs]
    assert all(job["state"] == "succeeded" for job in labelled["jobs"]["json"])
    assert labelled["preview"]["type"] == "image/png"
    before = labelled[f"/v1/revisions/{_adopted(info)}/region-measurements"]["json"]
    fid = info["field_ids"][0]
    edited = labelled["edited-measurements"]["json"]["field_tables"][fid]["rows"]
    assert len(edited) < len(before["field_tables"][fid]["rows"])
    assert labelled["descriptive"]["json"]["figure"]["status"] == "ready"
    assert [row["experimental_units"] for row in labelled["common-statistics"]["json"]["counts"]] == [2, 2]
    assert labelled["publication.zip"]["bytes"] > 0 and labelled["figure.svg"]["bytes"] > 0


def _adopted(info: dict) -> str:
    fid = info["field_ids"][0]
    return next(e["revision_id"] for e in info["selection"]["entries"] if e["field_id"] == fid)


def _without_versions(value):
    """Library versions legitimately differ (Pyodide vs uv.lock); results must not."""
    if isinstance(value, dict):
        return {k: _without_versions(v) for k, v in value.items() if not k.endswith("_version")}
    if isinstance(value, list):
        return [_without_versions(v) for v in value]
    return value


def numeric_view(lines: list[dict]) -> dict:
    """Measurements, statistics and figure source data without run-specific identifiers."""
    labelled = {line["step"]: line for line in lines}
    rows = [{k: v for k, v in row.items() if isinstance(v, (int, float)) and not isinstance(v, bool)}
            for _, table in sorted(labelled["edited-measurements"]["json"]["field_tables"].items())
            for row in table["rows"]]
    statistics = labelled["common-statistics"]["json"]
    return {"rows": rows, "comparisons": _without_versions(statistics["comparisons"]), "counts": statistics["counts"],
            "plot_data": [{k: v for k, v in row.items() if k in ("value", "condition")}
                          for row in labelled["descriptive"]["json"]["plot_data"]]}


def assert_close(left, right, path: str = "value") -> None:
    if isinstance(left, dict):
        assert isinstance(right, dict) and set(left) == set(right), path
        for key in left:
            assert_close(left[key], right[key], f"{path}.{key}")
    elif isinstance(left, list):
        assert isinstance(right, list) and len(left) == len(right), path
        for index, (a, b) in enumerate(zip(left, right, strict=True)):
            assert_close(a, b, f"{path}[{index}]")
    elif isinstance(left, float) or isinstance(right, float):
        assert left == pytest.approx(right, rel=1e-9, abs=1e-12, nan_ok=True), path
    else:
        assert left == right, path

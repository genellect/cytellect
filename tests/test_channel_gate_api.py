"""Owned API/worker/replay on the committed, registered public JUMP/DS6a seed.

The saved source is chosen by the existing public fixture before reading values.
A fixed manual zero threshold checks software wiring only, not biological positivity.
No model is run and no detector/threshold is fitted to these public images.
"""
import copy
import hashlib
import json
import time
import zipfile
from pathlib import Path

import pytest
from cytellect_analysis.region_exports import _recompute_statistics
from cytellect_api.db import jobs, revisions, workspaces
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from cytellect_worker.region_export_sources import collect_dependencies
from sqlalchemy import select, update
from test_api_worker import HEADERS, authenticated


@pytest.fixture(scope="module")
def public_store(tmp_path_factory):
    """Restore only one preselected public nuclear source and its exact input dependencies."""
    root = Path(__file__).resolve().parents[1] / "apps/web/public/showcase"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf8"))
    with (root / "seed.zip").open("rb") as stream:
        assert hashlib.file_digest(stream, "sha256").hexdigest() == manifest["files"]["seed.zip"]["sha256"]
    folder = tmp_path_factory.mktemp("public-channel-source")
    with zipfile.ZipFile(root / "seed.zip") as archive:
        archive.extract("cytellect.sqlite", folder)
        client, app, settings = authenticated(folder)
        store = app.state.store
        wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Public channel software test"}).json()["id"]
        owner = store.one(workspaces, id=wid)["owner"]
        with store.transaction() as conn:
            conn.execute(update(workspaces).values(owner=owner, expires=time.time() + 3600))
            saved = [dict(row) for row in conn.execute(select(revisions).order_by(revisions.c.id)).mappings()]
        # Select by stable revision identity before opening any measurements.
        source = next(rev for rev in saved if rev["state"] == "succeeded"
                      and len(rev["config"].get("field_ids", [])) == 1
                      and rev["config"].get("recipe", {}).get("source") == "stardist_nuclear")
        fid = source["config"]["field_ids"][0]
        field_prefix = f"workspaces/{source['workspace_id']}/fields/{fid}/"
        result_prefix = source["result_dir"].replace("\\", "/").rstrip("/") + "/"
        seed = json.loads(archive.read("showcase.json"))
        regenerations = {entry["path"]: entry for entry in seed.get("regenerate", [])}
        available, needed, regenerate = set(archive.namelist()), set(), set()

        def require(name):
            if name in needed or name in regenerate:
                return
            if name in available:
                needed.add(name)
            else:
                entry = regenerations[name]
                regenerate.add(name)
                require(entry.get("copy_of", entry.get("decode_tiff")))

        for name in available | set(regenerations):
            if name.startswith(field_prefix):
                require(name)
        for name in ("measurements.json", "provenance.json", f"{fid}/labels.npy"):
            require(result_prefix + name)
        for name in sorted(needed):
            archive.extract(name, folder)
        seed["regenerate"] = [entry for entry in seed.get("regenerate", []) if entry["path"] in regenerate]
        (folder / "showcase.json").write_text(json.dumps(seed), encoding="utf8")
    from cytellect_showcase.seed import restore

    restore(folder)  # every restored array is checked against the registered SHA-256
    yield client, store, settings, {"field": source}
    client.close()
    store.engine.dispose()


def cohort(public_store, *, metadata_update=None):
    client, store, settings, selected = public_store
    source = selected["field"]
    fid, wid = source["config"]["field_ids"][0], source["workspace_id"]
    metadata = {**source["config"]["field_snapshot"][fid]["metadata"], **(metadata_update or {})}
    # The fixture deliberately tests one preselected field. Every other field is
    # explicitly outside this software test's scope, with a reason in the ledger.
    selection = client.get(f"/v1/workspaces/{wid}/selection").json()
    for entry in selection["entries"]:
        entry["exclusion_reason"] = None if entry["field_id"] == fid else "Outside single-field software test scope"
        if entry["field_id"] == fid:
            entry["revision_id"] = source["id"]
            entry["target_revisions"] = {"nuclei": source["id"]}
    adopted = client.post(f"/v1/workspaces/{wid}/selection", headers=HEADERS, json=selection)
    assert adopted.status_code == 200, adopted.text
    current = client.get(f"/v1/workspaces/{wid}").json()
    created = client.post(f"/v1/workspaces/{wid}/region-cohorts", headers=HEADERS, json={
        "sources": [{"field_id": fid, "revision_id": source["id"]}], "metadata": {fid: metadata},
        "expected_active_revision_id": current["active_revision"], "workspace_selection": adopted.json()})
    assert created.status_code == 202, created.text
    assert process_one(store, settings)
    rev = store.one(revisions, id=created.json()["revision_id"])
    assert rev["state"] == "succeeded", rev
    return rev, fid


def preview(client, rev, fid, filter_=None):
    channels = rev["config"]["field_snapshot"][fid]["image_info"]["channels"]
    nuclear = rev["config"]["recipe"]["defining_channel_id"]
    # Select the first recorded non-nuclear stain before looking at any measurements.
    channel = next((item for item in channels if item["channel_id"] != nuclear), channels[0])
    filter_ = filter_ or {"version": "1.0.0", "gate_protocol": "channel-gate/1.0.0", "channel_id": channel["channel_id"],
                         "method": "manual", "values": "raw", "threshold": 0.0, "keep": "negative"}
    response = client.post(f"/v1/workspaces/{rev['workspace_id']}/channel-gate", headers=HEADERS,
                           json={"filter": filter_, "fields": [{"field_id": fid, "revision_id": rev["id"]}]})
    return response, channel


@pytest.mark.parametrize("metric", ["positive_count", "positive_fraction"])
def test_public_preview_review_boundary_worker_export_and_replay(public_store, metric):
    client, store, settings, _ = public_store
    rev, fid = cohort(public_store)
    response, channel = preview(client, rev, fid)
    assert response.status_code == 200, response.text
    classified = response.json()
    assert classified["channel"] == {key: channel.get(key) for key in ("channel_id", "label", "stain")}
    report = read_json(store.safe_path(rev["result_dir"], "measurements.json"))
    saved = {row["region_id"]: row["mean"] for row in report["field_tables"][fid]["rows"]
             if row["channel_id"] == channel["channel_id"]}
    assert saved, "The preselected public field has no nuclei; this would not exercise classification."
    assert {row["region_id"]: row["channel_mean"] for row in classified["nuclei"]} == saved
    assert all("gfp_mean" not in row and "gfp_positive" not in row for row in classified["nuclei"])
    filter_ = {**classified["filter"], "reference_sha256": classified["record"]["decision_sha256"]}
    body = {"mode": "descriptive", "selection": {"source": "field-summary", "version": "1.0.0",
            "region_set_id": rev["config"]["recipe"]["region_set_id"], "metric": metric, "positivity": filter_},
            "plot": {"preset": "nature-double", "language": "en"},
            "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}
    url = f"/v1/revisions/{rev['id']}/descriptive"
    assert client.post(url, headers=HEADERS, json=body).status_code == 409  # preview did not review the source
    assert client.post(f"/v1/revisions/{rev['id']}/review", headers=HEADERS).status_code == 200
    unrecorded = copy.deepcopy(body)
    unrecorded["selection"]["positivity"]["reference_sha256"] = None
    refused = client.post(url, headers=HEADERS, json=unrecorded)
    assert refused.status_code == 422 and refused.json()["detail"] == "channel_gate_record_required"
    accepted = client.post(url, headers=HEADERS, json=body)
    assert accepted.status_code == 202, accepted.text
    assert process_one(store, settings)
    job = store.one(jobs, id=accepted.json()["job_id"])
    assert job["state"] == "succeeded", job.get("error")
    result = client.get(f"/v1/jobs/{job['id']}/result").json()
    outcomes = [row for row in classified["nuclei"] if row["positive"] is not None]
    count = sum(row["positive"] for row in outcomes)
    expected = count if metric == "positive_count" else count / len(outcomes)
    assert [row["value"] for row in result["plot_data"]] == pytest.approx([expected])
    assert result["selection"]["channel_gate"]["decision_sha256"] == classified["record"]["decision_sha256"]
    assert result["selection"]["channel_gate"]["nuclei"] == classified["nuclei"]
    assert result["spec"]["selection"]["positivity"]["keep"] == "negative"  # did not shrink the positivity denominator
    assert result["counts"]["experimental_units"] is None
    fresh = store.one(revisions, id=rev["id"])
    provenance = read_json(store.safe_path(rev["result_dir"], "provenance.json"))
    replayed = _recompute_statistics(report, {**fresh["config"], "review_record": fresh["review_record"]}, result,
                                     collect_dependencies(store, fresh, report, provenance), provenance)
    assert replayed == {key: value for key, value in result.items() if key != "figure"}
    root = store.safe_path(job["result_dir"])
    methods = "\n".join((root / name).read_text(encoding="utf8") for name in result["figure"]["source_files"] if name.endswith("methods.md"))
    assert "channel-gate/1.0.0" in methods and "before subset selection" in methods
    assert client.get(f"/v1/jobs/{job['id']}/files/figure.zip").status_code == 200


def test_public_changed_metadata_refuses_the_old_record(public_store):
    client, _, _, _ = public_store
    rev, fid = cohort(public_store)
    response, _ = preview(client, rev, fid)
    assert response.status_code == 200, response.text
    saved = response.json()
    filter_ = {**saved["filter"], "reference_sha256": saved["record"]["decision_sha256"]}
    changed, changed_fid = cohort(public_store, metadata_update={"condition": "changed public test metadata"})
    stale, _ = preview(client, changed, changed_fid, filter_)
    assert stale.status_code == 422 and stale.json()["detail"] == "channel_gate_record_mismatch"
    fresh, _ = preview(client, changed, changed_fid, {**filter_, "reference_sha256": None})
    assert fresh.status_code == 200, fresh.text
    assert fresh.json()["record"]["decision_sha256"] != filter_["reference_sha256"]

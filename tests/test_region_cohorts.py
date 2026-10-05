"""Cohorts remeasure pinned masks without inventing review or independent units."""
import copy
import json

import numpy as np
import pytest
from cytellect_api.db import jobs, revisions
from cytellect_api.storage import read_json
from cytellect_worker.regions import run_region_analysis
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, region_request, tiff_bytes


def finish_analysis(app, settings):
    store = app.state.store
    claimed = store.claim()
    assert claimed is not None and claimed["kind"] == "analysis"
    output = store.safe_path("results", claimed["id"])
    run_region_analysis(store, settings, claimed, output)
    assert store.finish(claimed, store.relative_path(output))
    return read_json(output / "measurements.json")


def setup_cohort(tmp_path, *, nuclear=False, monkeypatch=None):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={"title": "cohort"}, headers=HEADERS).json()["id"]
    sources, originals, metadata = [], {}, {}
    if nuclear:
        labels = np.zeros((12, 12), np.uint32)
        labels[4:6, 4:6] = 17
        monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", lambda *a, **kw: (labels, {"engine": "test-fixture"}))
    for index in range(2):
        if nuclear:
            upload = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                data={"specification": json.dumps({"version": "1.1.0", "channels": [{
                    "channel_id": "ch1", "label": "DAPI", "stain": "DAPI", "identity_source": "filename"}]})},
                files={"ch0": ("fixture.tif", tiff_bytes(np.arange(144, dtype=np.uint16).reshape(12, 12)), "image/tiff")})
            assert upload.status_code == 201, upload.text
            fid = upload.json()["id"]
            request = {"field_ids": [fid], "recipe": {"version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei",
                "source": "stardist_nuclear", "defining_channel_id": "ch1", "nuclear_role_source": "recorded_stain"}}
        else:
            fid = make_field(client, wid).json()["id"]
            request = region_request(fid)
        request.update(measurement={"version": "1.1.0", "mode": "raw_intensity"}, backgrounds={})
        if index == 0:
            request["exclusions"] = [{"field_id": fid, "region_id": 17, "reason": "manual quality exclusion"}]
        queued = client.post(f"/v1/workspaces/{wid}/region-analyses", json=request, headers=HEADERS)
        assert queued.status_code == 202, queued.text
        report = finish_analysis(app, settings)
        assert report["field_failures"] == []
        originals[fid] = report
        sources.append({"field_id": fid, "revision_id": queued.json()["revision_id"]})
        metadata[fid] = {"condition": "A" if index == 0 else "B", "experimental_unit": None,
                         "sample": None, "acquisition_date": None, "pair": None}
    body = {"sources": sources, "metadata": metadata, "expected_active_revision_id": sources[-1]["revision_id"]}
    return client, app, settings, wid, body, originals


def test_cohort_preserves_masks_exclusions_and_values_but_never_auto_reviews(tmp_path, monkeypatch):
    client, app, settings, wid, body, originals = setup_cohort(tmp_path)
    def forbid_detection(*args, **kwargs):
        raise AssertionError("cohort must reuse original masks")
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", forbid_detection)
    path = f"/v1/workspaces/{wid}/region-cohorts"
    queued = client.post(path, json=body, headers=HEADERS)
    assert queued.status_code == 202, queued.text
    assert client.post(path, json=body, headers=HEADERS).json() == queued.json()
    report = finish_analysis(app, settings)
    assert report["field_failures"] == []
    rid = queued.json()["revision_id"]
    saved = app.state.store.one(revisions, id=rid)
    assert saved["reviewed"] is False and saved["review_record"] is None
    for fid, original in originals.items():
        assert report["field_masks"][fid]["mask_sha256"] == original["field_masks"][fid]["mask_sha256"]
        assert report["field_masks"][fid]["mask_revision_id"] == original["field_masks"][fid]["mask_revision_id"]
        for current, previous in zip(report["field_tables"][fid]["rows"], original["field_tables"][fid]["rows"], strict=True):
            assert current == {**previous, "analysis_revision_id": rid}
        assert saved["config"]["field_snapshot"][fid]["metadata"]["experimental_unit"] is None
        assert saved["config"]["cohort_sources"][fid]["revision_id"] == original["revision_id"]
    assert report["exclusions"] == originals[body["sources"][0]["field_id"]]["exclusions"]
    provenance = read_json(app.state.store.safe_path(saved["result_dir"], "provenance.json"))
    assert provenance["detector_executed"] is False and provenance["cohort_sources"] == saved["config"]["cohort_sources"]
    for entry in provenance["fields"].values():
        assert entry["history"][-1]["operation"] == "cohort_assembly"
    assert client.post(f"/v1/revisions/{rid}/review", json={}, headers=HEADERS).status_code == 200
    assert app.state.store.one(revisions, id=rid)["reviewed"] is True


def test_cohort_cannot_omit_fields_or_use_stale_metadata_or_cross_ownership(tmp_path):
    client, app, _, wid, body, _ = setup_cohort(tmp_path)
    path = f"/v1/workspaces/{wid}/region-cohorts"
    missing = copy.deepcopy(body)
    removed = missing["sources"].pop()["field_id"]
    del missing["metadata"][removed]
    assert client.post(path, json=missing, headers=HEADERS).json()["detail"] == "cohort_all_workspace_fields_required"
    assert client.post(path, json={**body, "metadata": {}}, headers=HEADERS).status_code == 422
    stale = {**body, "expected_active_revision_id": body["sources"][0]["revision_id"]}
    assert client.post(path, json=stale, headers=HEADERS).json()["detail"] == "stale_revision"
    stranger = TestClient(app)
    stranger.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS)
    assert stranger.post(path, json=body, headers=HEADERS).status_code == 404
    assert len(app.state.store.rows(jobs, workspace_id=wid)) == 2


def test_cohort_refuses_mismatched_source_recipes(tmp_path):
    client, app, _, wid, body, _ = setup_cohort(tmp_path)
    source = app.state.store.one(revisions, id=body["sources"][0]["revision_id"])
    config = copy.deepcopy(source["config"])
    config["recipe"]["label"] = "Different biological region definition"
    with app.state.store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == source["id"]).values(config=config))
    response = client.post(f"/v1/workspaces/{wid}/region-cohorts", json=body, headers=HEADERS)
    assert response.status_code == 409 and response.json()["detail"] == "cohort_recipe_mismatch"


def test_cohort_source_change_after_queue_is_visible_failure_and_blocks_review(tmp_path):
    client, app, settings, wid, body, _ = setup_cohort(tmp_path)
    queued = client.post(f"/v1/workspaces/{wid}/region-cohorts", json=body, headers=HEADERS)
    assert queued.status_code == 202, queued.text
    source = app.state.store.one(revisions, id=body["sources"][0]["revision_id"])
    path = app.state.store.safe_path(source["result_dir"], "measurements.json")
    path.write_text(path.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    report = finish_analysis(app, settings)
    assert report["field_failures"] == [{"field_id": body["sources"][0]["field_id"], "reason": "cohort_source_changed"}]
    assert client.post(f"/v1/revisions/{queued.json()['revision_id']}/review", json={}, headers=HEADERS).status_code == 409


@pytest.mark.parametrize("nuclear", [False, True])
def test_cohort_bundle_replays_pinned_masks_and_preserves_sources_without_redetection(tmp_path, monkeypatch, nuclear):
    from cytellect_analysis.region_exports import build_region_bundle, replay_region_bundle
    client, app, settings, wid, body, _ = setup_cohort(tmp_path, nuclear=nuclear, monkeypatch=monkeypatch)
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", lambda *a, **kw: pytest.fail("cohort reran detector"))
    queued = client.post(f"/v1/workspaces/{wid}/region-cohorts", json=body, headers=HEADERS)
    report = finish_analysis(app, settings)
    store = app.state.store
    saved = store.one(revisions, id=queued.json()["revision_id"])
    assert report["field_failures"] == []
    root = store.safe_path(saved["result_dir"])
    output = tmp_path / "export"
    build_region_bundle(output, config=saved["config"], report=report,
        provenance=read_json(root / "provenance.json"),
        mask_files={fid: root / fid / "labels.npy" for fid in report["field_masks"]},
        raw_files=[(f"{fid}/{slot}.tif", store.safe_path("workspaces", wid, "fields", fid, f"{slot}.tif"))
                   for fid, field in saved["config"]["field_snapshot"].items()
                   for slot in field["image_info"]["inputs"]], include_raw=True)
    def forbid_detection(*args, **kwargs):
        raise AssertionError("cohort replay must use canonical masks")
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", forbid_detection)
    bundle = output / "bundle"
    result = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay")
    assert result["matched_saved_measurements"]
    assert read_json(tmp_path / "replay" / "measurements.json")["field_tables"] == report["field_tables"]
    assert read_json(bundle / "revision.json")["config"]["cohort_sources"] == saved["config"]["cohort_sources"]
    assert read_json(bundle / "provenance.json")["cohort_sources"] == saved["config"]["cohort_sources"]


def test_cohort_metadata_child_reuses_all_masks_and_source_history(tmp_path):
    client, app, settings, wid, body, _ = setup_cohort(tmp_path)
    queued = client.post(f"/v1/workspaces/{wid}/region-cohorts", json=body, headers=HEADERS)
    before = finish_analysis(app, settings)
    fid = body["sources"][0]["field_id"]
    changed = {**body["metadata"][fid], "experimental_unit": "explicit-unit", "sample": "explicit-sample"}
    response = client.post(f"/v1/revisions/{queued.json()['revision_id']}/region-metadata",
                           json={"fields": {fid: changed}}, headers=HEADERS)
    assert response.status_code == 202, response.text
    after = finish_analysis(app, settings)
    assert after["field_failures"] == [] and after["field_masks"] == before["field_masks"]
    saved = app.state.store.one(revisions, id=response.json()["revision_id"])
    assert saved["reviewed"] is False
    assert saved["config"]["cohort_sources"]
    assert saved["config"]["field_snapshot"][fid]["metadata"]["experimental_unit"] == "explicit-unit"
    history = read_json(app.state.store.safe_path(saved["result_dir"], "provenance.json"))["fields"][fid]["history"]
    assert [item["operation"] for item in history][-2:] == ["cohort_assembly", "metadata"]

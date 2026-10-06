"""Cross-tab adoption, no silent omission and immutable comparison provenance."""
import copy

from cytellect_api.db import revisions
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS
from test_common_statistics_api import common_request
from test_region_api import make_field
from test_region_cohorts import finish_analysis, setup_cohort


def save(client, wid, value):
    response = client.post(f"/v1/workspaces/{wid}/selection", headers=HEADERS, json=value)
    assert response.status_code == 200, response.text
    return response.json()


def test_undo_is_shared_and_stale_tab_cannot_overwrite_or_compare(tmp_path):
    client, app, settings, wid, body, _ = setup_cohort(tmp_path)
    path = f"/v1/workspaces/{wid}/selection"
    selection = save(client, wid, client.get(path).json())
    before = copy.deepcopy(selection)
    fid = body["sources"][0]["field_id"]
    original = body["sources"][0]["revision_id"]
    client.post(f"/v1/workspaces/{wid}/current", headers=HEADERS, json={"revision_id": original})
    config = app.state.store.one(revisions, id=original)["config"]
    queued = client.post(f"/v1/revisions/{original}/region-reconfigure", headers=HEADERS,
        json={key: config[key] for key in ("field_ids", "recipe", "measurement", "backgrounds")} | {"exclusions": []})
    assert queued.status_code == 202, queued.text
    finish_analysis(app, settings)
    changed = queued.json()["revision_id"]
    selection["entries"][0]["revision_id"] = changed
    selection = save(client, wid, selection)
    # Undo is an adoption change, not a sessionStorage-only pointer.
    selection["entries"][0]["revision_id"] = original
    selection = save(client, wid, selection)
    second = TestClient(app)
    second.cookies.update(client.cookies)
    assert second.get(path).json() == selection
    assert second.post(path, headers=HEADERS, json=before).status_code == 409
    # A new cohort cannot submit stale selections even after refreshing active_revision.
    before["entries"][0]["revision_id"] = changed
    request = {**body, "expected_active_revision_id": changed, "workspace_selection": before}
    request["sources"] = [{"field_id": entry["field_id"], "revision_id": entry["revision_id"]} for entry in before["entries"]]
    assert client.post(f"/v1/workspaces/{wid}/region-cohorts", headers=HEADERS, json=request).json()["detail"] == "workspace_selection_changed"
    assert client.get(path).json()["entries"][0] == {"id": fid, "field_id": fid, "revision_id": original, "exclusion_reason": None}
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.get(path).status_code == 404


def test_failed_upload_and_analysis_require_reasoned_exclusions_and_are_saved(tmp_path):
    client, app, settings, wid, body, _ = setup_cohort(tmp_path)
    failed_field = make_field(client, wid).json()["id"]
    path = f"/v1/workspaces/{wid}/selection"
    selection = client.get(path).json()
    selection["entries"].append({"id": "interrupted-upload", "field_id": None, "revision_id": None, "exclusion_reason": None})
    selection = save(client, wid, selection)
    request = {**body, "workspace_selection": selection}
    assert client.post(f"/v1/workspaces/{wid}/region-cohorts", json=request, headers=HEADERS).status_code == 409
    invalid = copy.deepcopy(selection)
    invalid["entries"][-1]["exclusion_reason"] = " "
    assert client.post(path, headers=HEADERS, json=invalid).status_code == 422
    for entry in selection["entries"]:
        if not entry["revision_id"]:
            entry["exclusion_reason"] = "Acquisition file incomplete; excluded before comparison"
    selection = save(client, wid, selection)
    dropped = {**selection, "entries": selection["entries"][:-1]}
    assert client.post(path, headers=HEADERS, json=dropped).status_code == 409
    queued = client.post(f"/v1/workspaces/{wid}/region-cohorts", headers=HEADERS, json={**body, "workspace_selection": selection})
    assert queued.status_code == 202, queued.text
    report = finish_analysis(app, settings)
    assert report["field_failures"] == [] and failed_field not in report["field_tables"]
    rid = queued.json()["revision_id"]
    saved = app.state.store.one(revisions, id=rid)
    assert saved["config"]["workspace_selection"] == selection
    assert client.get(f"/v1/revisions/{rid}/workspace-selection").json() == selection
    # Changing adoption after preparation also invalidates inference submission.
    client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={})
    selection["entries"][-1]["exclusion_reason"] = None
    save(client, wid, selection)
    request = common_request()
    request["selection"].update(metric="area_px", channel_id=None)
    response = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=request)
    assert response.status_code == 409 and response.json()["detail"] == "workspace_selection_changed"


def test_selection_rejects_foreign_revision_and_migrates_existing_database(tmp_path):
    client, app, _, wid, body, _ = setup_cohort(tmp_path)
    path = f"/v1/workspaces/{wid}/selection"
    selection = client.get(path).json()
    selection["entries"][0]["revision_id"] = body["sources"][1]["revision_id"]
    assert client.post(path, headers=HEADERS, json=selection).status_code == 409
    selection = client.get(path).json()
    with app.state.store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == selection["entries"][0]["revision_id"]).values(state="failed"))
    assert client.post(path, headers=HEADERS, json=selection).status_code == 409


def test_legacy_ambiguous_revision_is_not_silently_adopted(tmp_path):
    client, app, _, wid, body, _ = setup_cohort(tmp_path)
    original = dict(app.state.store.one(revisions, id=body["sources"][0]["revision_id"]))
    original.update(id="other-saved-field-version", created=original["created"] + 1)
    with app.state.store.transaction() as conn:
        conn.execute(revisions.insert().values(**original))
    state = client.get(f"/v1/workspaces/{wid}/selection").json()
    first = next(entry for entry in state["entries"] if entry["field_id"] == body["sources"][0]["field_id"])
    assert first["revision_id"] is None
    first["revision_id"] = body["sources"][0]["revision_id"]
    assert save(client, wid, state)["version"] == 1


def selected_four_field_comparison(tmp_path):
    from test_api_worker import authenticated
    from test_region_api import region_request

    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={}, headers=HEADERS).json()["id"]
    sources, metadata = [], {}
    for index in range(4):
        fid = make_field(client, wid).json()["id"]
        spec = region_request(fid)
        spec.update(backgrounds={}, measurement={"version": "1.1.0", "mode": "raw_intensity"})
        job = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=spec).json()
        finish_analysis(app, settings)
        sources.append({"field_id": fid, "revision_id": job["revision_id"]})
        metadata[fid] = {"condition": "A" if index < 2 else "B", "sample": f"sample-{index}", "experimental_unit": f"unit-{index}", "acquisition_date": "one-batch"}
    selection = save(client, wid, client.get(f"/v1/workspaces/{wid}/selection").json())
    cohort = client.post(f"/v1/workspaces/{wid}/region-cohorts", headers=HEADERS, json={"sources": sources, "metadata": metadata, "expected_active_revision_id": sources[-1]["revision_id"], "workspace_selection": selection})
    assert cohort.status_code == 202, cohort.text
    rid = cohort.json()["revision_id"]
    finish_analysis(app, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    spec = common_request()
    spec["selection"].update(metric="area_px", channel_id=None)
    spec["acquisition_review"]["spatial_sampling_confirmed"] = True
    return client, app, wid, rid, selection, spec


def test_selection_change_after_enqueue_stops_worker_before_calculation(tmp_path, monkeypatch):
    import pytest
    from cytellect_api.db import jobs
    from cytellect_worker.common_statistics import run_common_statistics

    client, app, wid, rid, selection, spec = selected_four_field_comparison(tmp_path)
    queued = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=spec)
    assert queued.status_code == 202, queued.text
    job = app.state.store.claim()
    selection["entries"][0]["exclusion_reason"] = "Changed selection in second tab"
    save(client, wid, selection)
    monkeypatch.setattr("cytellect_analysis.common_statistics.analyze_region_comparison", lambda *args: pytest.fail("stale job must not calculate"))
    with pytest.raises(ValueError, match="workspace_selection_changed"):
        run_common_statistics(app.state.store, job, tmp_path / "stale-output")
    assert app.state.store.finish(job, error="workspace_selection_changed")
    assert app.state.store.one(jobs, id=job["id"])["state"] == "failed"
    assert client.get(f"/v1/jobs/{job['id']}/common-statistics").status_code == 404


def test_selection_change_during_calculation_is_fenced_without_removing_prior_artifact(tmp_path, monkeypatch):
    from cytellect_analysis import common_statistics
    from cytellect_api.db import jobs
    from cytellect_worker.common_statistics import run_common_statistics

    client, app, wid, rid, selection, spec = selected_four_field_comparison(tmp_path)
    store = app.state.store
    first = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=spec)
    assert first.status_code == 202, first.text
    previous = store.claim()
    first_output = store.safe_path("results", previous["id"])
    run_common_statistics(store, previous, first_output)
    assert store.finish(previous, store.relative_path(first_output))
    original_file = client.get(f"/v1/jobs/{previous['id']}/files/figure.svg").content
    assert original_file.startswith(b"<?xml")
    queued = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=spec)
    assert queued.status_code == 202, queued.text
    running = store.claim()
    original_calculate = common_statistics.analyze_region_comparison
    def change_during_calculation(*args):
        value = original_calculate(*args)
        selection["entries"][0]["exclusion_reason"] = "Changed while another tab calculated"
        save(client, wid, selection)
        return value
    monkeypatch.setattr(common_statistics, "analyze_region_comparison", change_during_calculation)
    output = store.safe_path("results", running["id"])
    run_common_statistics(store, running, output)
    assert (output / "result.json").exists()
    assert store.finish(running, store.relative_path(output))
    rejected = store.one(jobs, id=running["id"])
    assert rejected["state"] == "failed" and rejected["error"] == "workspace_selection_changed"
    assert rejected["result_dir"] is None
    assert client.get(f"/v1/jobs/{running['id']}/files/figure.svg").status_code == 404
    assert client.get(f"/v1/jobs/{previous['id']}/files/figure.svg").content == original_file
    # A stale second completion must not overwrite the finished rejection.
    assert not store.finish(running, store.relative_path(output))

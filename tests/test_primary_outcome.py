"""The primary measure is declared with the server's time, and a result's time is its statistics' (#257 RP-04).

#258's defect: the browser compared the declaration with the creation time of a figure re-render job, so the path
解析 -> 宣言 -> 図の描き直し -> 開き直す showed a result calculated before the declaration as if it came after it.
The job list now gives every result the time its statistics were calculated (calculated_at), followed through
re-renders; the browser compares that time only. The numeric fixture is the registered CSV transport of
tests/test_csv.py (no image values are involved).
"""
import time

import pytest
from cytellect_api.analysis_spec import AnalysisSpec, PrimaryOutcome
from cytellect_api.db import jobs
from cytellect_worker.main import process_one
from pydantic import ValidationError
from test_api_worker import HEADERS, authenticated
from test_csv import content
from test_numeric_export import specification


def _jobs(client, wid):
    return {job["id"]: job for job in client.get(f"/v1/workspaces/{wid}/jobs", headers=HEADERS).json()}


def test_declaration_time_is_the_servers_and_kept_while_the_measure_is_unchanged(tmp_path, monkeypatch):
    import cytellect_api.analysis_spec as module

    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "primary"}).json()["id"]
    path = f"/v1/workspaces/{wid}/analysis-spec"
    clock = iter([1000.0, 2000.0])
    monkeypatch.setattr(module, "_now", lambda: next(clock))
    primary = {"metric": "solidity", "region_set_id": "nuclei", "channel_id": None, "declared_at": 1.0}
    saved = client.put(path, headers=HEADERS, json={"version": 0, "spec": {"channel_assignment_version": 0,
                                                                          "primary_outcome": primary}})
    assert saved.status_code == 200, saved.text
    assert saved.json()["spec"]["primary_outcome"] == {**primary, "version": "1.0.0", "declared_at": 1000.0}
    again = client.put(path, headers=HEADERS, json={"version": 1, "spec": {**saved.json()["spec"], "target": "nucleoli"}})
    assert again.json()["spec"]["primary_outcome"]["declared_at"] == 1000.0
    changed = {**again.json()["spec"], "primary_outcome": {**primary, "metric": "eccentricity"}}
    assert client.put(path, headers=HEADERS, json={"version": 2, "spec": changed}).json()["spec"]["primary_outcome"][
        "declared_at"] == 2000.0
    assert "primary_outcome" not in AnalysisSpec(channel_assignment_version=0).model_dump(mode="json")
    with pytest.raises(ValidationError, match="nuclear_features_nuclei_only"):
        PrimaryOutcome(metric="solidity", region_set_id="nucleoli")


def test_a_redrawn_figure_keeps_the_time_of_its_statistics(tmp_path, monkeypatch):
    """解析 -> 宣言 -> 図の描き直し -> 開き直す: the result stays calculated before the declaration."""
    import cytellect_api.analysis_spec as module

    client, app, settings = authenticated(tmp_path)
    store = app.state.store
    wid = client.post("/v1/workspaces", json={"title": "Primary timing"}, headers=HEADERS).json()["id"]
    tid = client.post(f"/v1/workspaces/{wid}/tables", headers=HEADERS,
                      files={"file": ("test.csv", content(), "text/csv")}).json()["table_id"]
    # 1. 解析
    statistics = client.post(f"/v1/tables/{tid}/statistics", json=specification().model_dump(), headers=HEADERS).json()["job_id"]
    assert process_one(store, settings)
    calculated = store.one(jobs, id=statistics)["created"]
    # 2. 宣言 (the server's time, after the calculation)
    monkeypatch.setattr(module, "_now", lambda: calculated + 0.001)
    primary = {"metric": "area_px", "region_set_id": "nuclei", "channel_id": None}
    response = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                          json={"version": 0, "spec": {"channel_assignment_version": 0, "primary_outcome": primary}})
    declared = response.json()["spec"]["primary_outcome"]["declared_at"]
    assert calculated < declared
    time.sleep(0.01)
    # 3. 図の描き直し, twice (the second re-draws the first re-draw)
    body = {"request_id": "after-declaration", "plot": {"y_label": "Expression", "preset": "custom", "font_size": 8}}
    first = client.post(f"/v1/jobs/{statistics}/figure-render", json=body, headers=HEADERS).json()["job_id"]
    assert process_one(store, settings)
    second = client.post(f"/v1/jobs/{first}/figure-render", json={**body, "request_id": "again"}, headers=HEADERS).json()["job_id"]
    assert process_one(store, settings)
    # 4. 開き直す: the job list a reopened workspace reads.
    listed = _jobs(client, wid)
    for job in (first, second):
        assert listed[job]["kind"] == "figure-render" and listed[job]["state"] == "succeeded"
        assert listed[job]["created"] > declared  # the defect compared this time
        assert listed[job]["calculated_at"] == calculated < declared
        assert client.get(f"/v1/jobs/{job}", headers=HEADERS).json()["calculated_at"] == calculated
    assert listed[statistics]["calculated_at"] == calculated
    # A calculation after the declaration is after it; other jobs have no calculation time.
    later = client.post(f"/v1/tables/{tid}/statistics", json=specification().model_dump(), headers=HEADERS).json()["job_id"]
    assert process_one(store, settings)
    assert _jobs(client, wid)[later]["calculated_at"] > declared
    assert all(job["calculated_at"] is None for job in _jobs(client, wid).values()
               if job["kind"] not in ("statistics", "table-statistics", "figure-render"))

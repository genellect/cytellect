"""Presentation changes preserve saved numeric results and never call inference."""
import copy
import time

import pytest
from cytellect_analysis.common_statistics import analyze_region_comparison
from cytellect_api.db import Store, jobs
from cytellect_api.figure_render import validated_plot
from cytellect_api.storage import read_json, write_json
from cytellect_worker.figure_render import run_figure_render
from test_common_statistics import request_v2
from test_region_comparison import comparison_fixture


def test_render_saved_result_preserves_comparisons(tmp_path, monkeypatch):
    report, config = comparison_fixture()
    original = analyze_region_comparison(report, config, request_v2())
    original["revision_id"] = "revision"
    untouched = copy.deepcopy(original)
    store = Store(tmp_path / "data")
    source_dir = store.safe_path("workspaces", "workspace", "figures", "original")
    source_dir.mkdir(parents=True)
    write_json(source_dir / "result.json", original)
    with store.transaction() as conn:
        conn.execute(jobs.insert().values(id="source", workspace_id="workspace", revision_id="revision",
            kind="statistics", state="succeeded", payload={}, created=time.time(),
            result_dir=str(source_dir.relative_to(store.root))))
    def forbidden(*args, **kwargs):
        raise AssertionError("statistics must not rerun")
    monkeypatch.setattr("cytellect_analysis.common_statistics.analyze_region_comparison", forbidden)
    output = tmp_path / "render"
    run_figure_render(store, {"workspace_id": "workspace", "revision_id": "revision",
        "payload": {"source_job_id": "source", "plot": {"y_label": "Intensity", "font_size": 7}}}, output)
    rendered = read_json(output / "result.json")
    assert rendered["comparisons"] == original["comparisons"]
    assert rendered["unit_summary"] == original["unit_summary"]
    assert rendered["plot_data"] == original["plot_data"]
    assert rendered["spec"]["plot"]["y_label"] == "Intensity"
    assert read_json(source_dir / "result.json") == untouched
    assert (output / "figure.zip").is_file()
    assert (output / "figure.pdf").is_file()


def test_render_rejects_unknown_style_and_invalid_axis():
    report, config = comparison_fixture()
    result = analyze_region_comparison(report, config, request_v2())
    for change in ({"test": "welch-t"}, {"y_min": 2, "y_max": 1}, {"language": "ja"}):
        with pytest.raises(ValueError):
            validated_plot(result, change)


def test_numeric_figure_render_is_private_idempotent_and_keeps_statistics(tmp_path, monkeypatch):
    from cytellect_worker.main import process_one
    from fastapi.testclient import TestClient
    from test_api_worker import HEADERS, authenticated
    from test_csv import content
    from test_numeric_export import specification

    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={"title": "Numeric render"}, headers=HEADERS).json()["id"]
    tid = client.post(f"/v1/workspaces/{wid}/tables", headers=HEADERS,
                     files={"file": ("test.csv", content(), "text/csv")}).json()["table_id"]
    jid = client.post(f"/v1/tables/{tid}/statistics", json=specification().model_dump(), headers=HEADERS).json()["job_id"]
    assert process_one(app.state.store, settings)
    source = app.state.store.one(jobs, id=jid)
    original = read_json(app.state.store.safe_path(source["result_dir"], "result.json"))
    route = f"/v1/jobs/{jid}/figure-render"
    body = {"request_id": "numeric-figure", "plot": {"y_label": "Expression", "preset": "custom", "font_size": 8}}
    accepted = client.post(route, json=body, headers=HEADERS)
    assert accepted.status_code == 202, accepted.text
    assert client.post(route, json=body, headers=HEADERS).json() == accepted.json()
    changed = {**body, "plot": {**body["plot"], "y_label": "Other"}}
    assert client.post(route, json=changed, headers=HEADERS).status_code == 409
    other = TestClient(app)
    other.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS)
    assert other.post(route, json=body, headers=HEADERS).status_code == 404
    def forbidden(*args, **kwargs):
        raise AssertionError("inference rerun")
    monkeypatch.setattr("cytellect_analysis.numerical_csv.analyze_numeric", forbidden)
    assert process_one(app.state.store, settings)
    rendered_id = accepted.json()["job_id"]
    response = client.get(f"/v1/jobs/{rendered_id}/figure-render")
    assert response.status_code == 200, response.text
    rendered = response.json()
    assert rendered["table_id"] == tid
    assert rendered["comparisons"] == original["comparisons"]
    assert rendered["plot_data"] == original["plot_data"]
    assert rendered["spec"]["plot"]["y_label"] == "Expression"
    assert client.get(f"/v1/jobs/{rendered_id}/files/figure.zip").status_code == 200
    assert other.get(f"/v1/jobs/{rendered_id}/files/figure.zip").status_code == 404

    package_route = f"/v1/jobs/{rendered_id}/publication-package"
    package_body = {"analysis_job_id": jid, "request_id": "numeric-publication"}
    packaged = client.post(package_route, json=package_body, headers=HEADERS)
    assert packaged.status_code == 202, packaged.text
    assert client.post(package_route, json=package_body, headers=HEADERS).json() == packaged.json()
    assert other.post(package_route, json=package_body, headers=HEADERS).status_code == 404
    assert process_one(app.state.store, settings)
    package_id = packaged.json()["job_id"]
    response = client.get(f"/v1/jobs/{package_id}/files/publication.zip")
    assert response.status_code == 200, response.text
    assert other.get(f"/v1/jobs/{package_id}/files/publication.zip").status_code == 404
    import io
    import json
    import zipfile
    with zipfile.ZipFile(io.BytesIO(response.content)) as bundle:
        assert {"analysis.zip", "edited-figure/figure.svg", "edited-figure/figure.pdf", "replay-figure.py", "manifest.json"} <= set(bundle.namelist())
        saved_figure = json.loads(bundle.read("figure-result.json"))
        assert saved_figure["comparisons"] == original["comparisons"]
        assert saved_figure["spec"]["plot"]["y_label"] == "Expression"
        assert bundle.read("analysis.zip") == app.state.store.safe_path(source["result_dir"], "analysis.zip").read_bytes()

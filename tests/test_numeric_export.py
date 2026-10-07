import json
import zipfile

import pytest
from cytellect_analysis.contracts import StatisticsRequest
from cytellect_analysis.descriptive import describe_numeric
from cytellect_analysis.descriptive_contracts import parse_descriptive_request
from cytellect_analysis.descriptive_output import read_descriptive_output_index, render_descriptive_output
from cytellect_analysis.figures import render_figures
from cytellect_analysis.numeric_export import build_numeric_bundle, replay_numeric
from cytellect_analysis.numerical_csv import analyze_numeric, parse_numeric_csv
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_csv import content


def specification():
    return StatisticsRequest(metric="value", baseline="A", comparisons=[("A", "B")],
                             independent_units_confirmed=True)


def test_numeric_bundle_replays_exact_input_and_preserves_source_identity(tmp_path):
    raw = content()
    original = tmp_path / "original.csv"
    original.write_bytes(raw)
    result = analyze_numeric(parse_numeric_csv(raw)["rows"], specification())
    result["table_id"] = "test-table"
    destination = tmp_path / "export"
    result["figure"] = render_figures(result, destination)
    archive = build_numeric_bundle(destination, content=raw, table_id="test-table", result=result,
                                   provenance={"software": {"source_sha256": "test-code"}})
    with zipfile.ZipFile(archive) as bundle:
        assert "input.csv" not in bundle.namelist()
        assert {"source.json", "table.json", "statistics.json", "methods.md", "environment.json",
                "provenance.json", "replay.py", "figure.pdf", "figure.svg"} <= set(bundle.namelist())
        manifest = json.loads(bundle.read("manifest.json"))
        assert manifest["format"] == "cytellect-numerical-reproducibility/1"
        assert manifest["raw_included"] is False
    fresh = replay_numeric(destination / "bundle", original, tmp_path / "replayed")
    assert fresh["comparisons"] == result["comparisons"]
    assert fresh["counts"] == result["counts"]
    assert fresh["table_id"] == "test-table"
    figure_data = json.loads((tmp_path / "replayed" / "figure-data.json").read_text())
    assert figure_data["table_id"] == "test-table"
    assert "observations" in fresh["counts"][0] and "cells" not in fresh["counts"][0]
    original.write_bytes(raw + b"\n")
    with pytest.raises(ValueError, match="replay_original_hash_mismatch"):
        replay_numeric(destination / "bundle", original, tmp_path / "wrong-original")
    original.write_bytes(raw)
    (destination / "bundle" / "statistics.json").write_text("{}")
    with pytest.raises(ValueError, match="replay_bundle_hash_mismatch"):
        replay_numeric(destination / "bundle", original, tmp_path / "tampered")


def test_numeric_job_exports_private_package_and_revokes_download(tmp_path):
    client, app, settings = authenticated(tmp_path)
    workspace = client.post("/v1/workspaces", json={"title": "Numerical test"}, headers=HEADERS).json()
    imported = client.post(f"/v1/workspaces/{workspace['id']}/tables", headers=HEADERS,
                           files={"file": ("unretained-name.csv", content(), "text/csv")})
    assert imported.status_code == 201
    tid = imported.json()["table_id"]
    queued = client.post(f"/v1/tables/{tid}/statistics", json=specification().model_dump(), headers=HEADERS)
    assert queued.status_code == 202
    jid = queued.json()["job_id"]
    assert process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{jid}").json()["state"] == "succeeded"
    routes = [f"/v1/jobs/{jid}/files/{name}" for name in ("analysis.zip", "methods.md", "figure.pdf")]
    for route in routes:
        response = client.get(route)
        assert response.status_code == 200
        assert response.headers["cache-control"] == "no-store"
    second = TestClient(app)
    second.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS)
    for route in routes:
        assert second.get(route).status_code == 404
    client.delete(f"/v1/workspaces/{workspace['id']}", headers=HEADERS)
    for route in routes:
        assert client.get(route).status_code == 404


def descriptive_specification():
    return parse_descriptive_request({"mode": "descriptive", "selection": {"source": "numerical"},
        "figure_policy": {"version": "2.0.0", "layout": "field-pages"},
        "plot": {"preset": "nature-single", "language": "en"}})


def test_descriptive_numeric_bundle_preserves_renderer_methods_and_replays(tmp_path):
    raw = b"field_id,value,unit\nfield-a,-2,ng\nfield-a,0,ng\nfield-b,4,ng\n"
    original = tmp_path / "source.csv"
    original.write_bytes(raw)
    result = describe_numeric(parse_numeric_csv(raw, mode="descriptive")["rows"], descriptive_specification())
    result["table_id"] = "descriptive-table"
    destination = tmp_path / "export"
    result["figure"] = render_descriptive_output(result, destination)
    methods = (destination / "methods.md").read_bytes()
    build_numeric_bundle(destination, content=raw, table_id=result["table_id"], result=result,
                         provenance={"software": {"source_sha256": "test-code"}})
    assert (destination / "methods.md").read_bytes() == methods
    assert (destination / "bundle" / "methods.md").read_bytes() == methods
    index = read_descriptive_output_index(destination / "descriptive-output.json")
    assert "methods.md" in index["files"]
    with zipfile.ZipFile(destination / "analysis.zip") as bundle:
        assert json.loads(bundle.read("manifest.json"))["format"] == "cytellect-numerical-reproducibility/2"
        assert {"figure-001.svg", "figure-001.pdf", "plot-data.csv", "selection.csv"} <= set(bundle.namelist())
    fresh = replay_numeric(destination / "bundle", original, tmp_path / "replayed")
    assert {key: value for key, value in fresh.items() if key != "figure"} == {
        key: value for key, value in result.items() if key != "figure"}
    assert (tmp_path / "replayed" / "methods.md").read_bytes() == methods


def test_descriptive_numeric_api_exports_edits_and_ownership(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", json={}, headers=HEADERS).json()["id"]
    raw = b"field_id,value\nfield-a,-2\nfield-a,0\nfield-b,4\n"
    imported = client.post(f"/v1/workspaces/{wid}/tables", data={"mode": "descriptive"},
                           files={"file": ("table.csv", raw, "text/csv")}, headers=HEADERS)
    assert imported.status_code == 201
    tid = imported.json()["table_id"]
    rejected = client.post(f"/v1/tables/{tid}/statistics", json=specification().model_dump(), headers=HEADERS)
    assert rejected.status_code == 422
    assert rejected.json()["detail"] == "numeric_csv_metadata_invalid"
    queued = client.post(f"/v1/tables/{tid}/descriptive", json=descriptive_specification().model_dump(mode="json"),
                         headers=HEADERS)
    assert queued.status_code == 202
    jid = queued.json()["job_id"]
    assert process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{jid}").json()["state"] == "succeeded"
    result = client.get(f"/v1/jobs/{jid}/result").json()
    assert result["counts"]["experimental_units"] is None
    assert result["table_id"] == tid
    assert client.get(f"/v1/jobs/{jid}/files/analysis.zip").status_code == 200
    assert client.get(f"/v1/jobs/{jid}/files/figure-001.svg").status_code == 200
    render = client.post(f"/v1/jobs/{jid}/figure-render", json={"request_id": "edit-table-axis",
        "plot": {"y_label": "Measured value"}}, headers=HEADERS)
    assert render.status_code == 202
    assert process_one(app.state.store, settings)
    figure_id = render.json()["job_id"]
    edited = client.get(f"/v1/jobs/{figure_id}/figure-render").json()
    assert edited["plot_data"] == result["plot_data"]
    package = client.post(f"/v1/jobs/{figure_id}/publication-package", json={"analysis_job_id": jid,
        "request_id": "save-table-axis"}, headers=HEADERS)
    assert package.status_code == 202
    assert process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{package.json()['job_id']}/files/publication.zip").status_code == 200
    second = TestClient(app)
    second.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS)
    assert second.post(f"/v1/tables/{tid}/descriptive", json=descriptive_specification().model_dump(mode="json"),
                       headers=HEADERS).status_code == 404

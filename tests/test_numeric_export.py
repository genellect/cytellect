import json
import zipfile

import pytest
from cytellect_analysis.contracts import StatisticsRequest
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

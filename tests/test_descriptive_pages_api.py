"""Real API/worker output, full tables and private hash-verified page downloads."""
import io
import zipfile

from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import jobs
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, region_request


def test_paged_and_tables_only_jobs_remain_private_complete_and_exportable(tmp_path):
    client, app, settings = authenticated(tmp_path)
    store = app.state.store
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Pages"}).json()["id"]
    fids = [make_field(client, wid).json()["id"] for _ in range(9)]
    config = region_request(fids[0])
    config["field_ids"] = fids
    config["backgrounds"] = {fid: region_request(fid)["backgrounds"][fid] for fid in fids}
    rid = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=config).json()["revision_id"]
    assert process_one(store, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects",
            "channel_id": "actin", "metric": "mean_corrected"},
            "plot": {"preset": "nature-double", "language": "en"},
            "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}
    jid = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body).json()["job_id"]
    assert process_one(store, settings)
    assert client.get(f"/v1/jobs/{jid}").json()["state"] == "succeeded"
    result = client.get(f"/v1/jobs/{jid}/result").json()
    assert result["figure"]["status"] == "ready" and len(result["figure"]["pages"]) == 2
    assert len(result["plot_data"]) == 9 and {row["value"] for row in result["plot_data"]} == {25}
    assert result["counts"]["experimental_units"] is None
    assert client.get(f"/v1/jobs/{jid}/files/figure-002.svg").status_code == 200
    package = client.get(f"/v1/jobs/{jid}/files/figure.zip")
    assert package.status_code == 200 and package.headers["cache-control"] == "no-store"
    with zipfile.ZipFile(io.BytesIO(package.content)) as archive:
        assert set(archive.namelist()) == set(result["figure"]["source_files"])
        assert archive.read("figure-002.svg") == client.get(f"/v1/jobs/{jid}/files/figure-002.svg").content
        assert archive.read("figure-002.pdf") == client.get(f"/v1/jobs/{jid}/files/figure-002.pdf").content
        assert "plot-data.csv" in archive.namelist()
    assert client.get(f"/v1/jobs/{jid}/files/figure-003.svg").status_code == 404
    assert client.get(f"/v1/jobs/{jid}/files/descriptive-output.json").status_code == 404
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": store.invite()})
    assert foreign.get(f"/v1/jobs/{jid}/files/figure-002.svg").status_code == 404
    assert foreign.get(f"/v1/jobs/{jid}/files/figure.zip").status_code == 404
    body["plot"]["y_label"] = "Unavailable \u0378"
    unavailable = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body).json()["job_id"]
    assert process_one(store, settings)
    assert client.get(f"/v1/jobs/{unavailable}").json()["state"] == "succeeded"
    tables = client.get(f"/v1/jobs/{unavailable}/result").json()
    assert tables["figure"]["status"] == "tables_only"
    assert client.get(f"/v1/jobs/{unavailable}/files/figure.zip").status_code == 404
    assert tables["plot_data"] == result["plot_data"]
    csv = client.get(f"/v1/jobs/{unavailable}/files/plot-data.csv")
    assert csv.status_code == 200 and csv.headers["cache-control"] == "no-store"
    assert len(csv.content.decode("utf-8-sig").splitlines()) == 10
    assert client.get(f"/v1/jobs/{unavailable}/files/figure-001.svg").status_code == 404
    export = client.post(f"/v1/revisions/{rid}/export", headers=HEADERS).json()["job_id"]
    assert process_one(store, settings)
    assert client.get(f"/v1/jobs/{export}").json()["state"] == "succeeded"
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(tmp_path / "bundle")
    replayed = replay_region_bundle(tmp_path / "bundle", store.safe_path("workspaces", wid, "fields"), tmp_path / "replay")
    assert replayed["matched_saved_measurements"] and replayed["matched_saved_descriptions"]
    assert replayed["descriptive_figures_ready"] is False
    folder = store.safe_path(store.one(jobs, id=jid)["result_dir"])
    archive = folder / "figure.zip"
    archive.write_bytes(archive.read_bytes() + b"tampered")
    assert client.get(f"/v1/jobs/{jid}/files/figure.zip").status_code == 404
    page = folder / "figure-002.svg"
    page.write_bytes(page.read_bytes() + b"changed")
    assert client.get(f"/v1/jobs/{jid}/files/figure-002.svg").status_code == 404
    index = folder / "descriptive-output.json"
    index.write_text(" " * (1024 * 1024 + 1), encoding="utf-8")
    assert client.get(f"/v1/jobs/{jid}/files/plot-data.csv").status_code == 404
    index.unlink()
    assert client.get(f"/v1/jobs/{jid}/files/plot-data.csv").status_code == 404
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/jobs/{unavailable}/files/plot-data.csv").status_code == 404
    assert client.get(f"/v1/jobs/{export}/files/analysis.zip").status_code == 404

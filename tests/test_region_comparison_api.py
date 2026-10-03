"""Known pixels exercise the owned comparison job, figure and replay boundaries."""
import io
import json
import math
import zipfile
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from cytellect_analysis.images import sha256
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import jobs, revisions
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from cytellect_worker.region_comparisons import run_region_comparison
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import region_request, tiff_bytes


def reviewed_units(client, app, settings):
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Arithmetic fixture"}).json()["id"]
    fids = []
    for index, value in enumerate([2, 4, 5, 7]):
        pixels = np.full((12, 12), 10, np.uint16)
        pixels[4:6, 4:6] = 10 + value
        labels = np.zeros((12, 12), np.uint32)
        labels[4:6, 4:6] = 1
        specification = {"channels": [{"channel_id": "marker", "label": "Measured marker",
                                         "stain": "Fixture fluorescence", "identity_confirmed": True}],
                         "metadata": {"condition": "A" if index < 2 else "B", "sample": f"sample-{index}",
                                      "experimental_unit": f"culture-{index}", "acquisition_date": "batch-1"}}
        response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                               data={"specification": json.dumps(specification)}, files={
                                   "ch0": ("image.tif", tiff_bytes(pixels), "image/tiff"),
                                   "labels": ("labels.tif", tiff_bytes(labels), "image/tiff")})
        assert response.status_code == 201, response.text
        fids.append(response.json()["id"])
    body = region_request(fids[0])
    background = body["backgrounds"][fids[0]]["actin"]
    body.update(field_ids=fids, backgrounds={fid: {"marker": background} for fid in fids})
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body)
    assert response.status_code == 202, response.text
    rid = response.json()["revision_id"]
    process_one(app.state.store, settings)
    assert app.state.store.one(revisions, id=rid)["state"] == "succeeded"
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    return wid, rid, fids


def comparison_request():
    return {"mode": "region-experimental-unit",
            "selection": {"source": "region", "region_set_id": "objects", "channel_id": "marker",
                          "metric": "mean_corrected"},
            "design": {"kind": "independent", "confirmed": True, "unit_definition": "Independently allocated cultures"},
            "conditions": ["A", "B"],
            "comparison_family": {"family_id": "planned-1", "kind": "control", "control": "A", "contrasts": [["A", "B"]]},
            "acquisition_review": {"confirmed": True, "basis": "same-settings"},
            "missingness_confirmed": True, "plot": {"kind": "distribution", "language": "en"}}


def test_comparison_pixels_to_figure_and_hash_verified_replay(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, rid, fids = reviewed_units(client, app, settings)
    response = client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS, json=comparison_request())
    assert response.status_code == 202, response.text
    jid = response.json()["job_id"]
    process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{jid}").json()
    assert job["state"] == "succeeded", job
    assert job["analysis_mode"] == "region-experimental-unit"
    result = client.get(f"/v1/jobs/{jid}/region-comparison")
    assert result.status_code == 200, result.text
    result = result.json()
    assert result["channel"]["channel_id"] == "marker"
    contrast = result["comparisons"][0]
    assert contrast["estimate"] == pytest.approx(-3)
    assert contrast["standard_error"] == pytest.approx(math.sqrt(2))
    assert contrast["degrees_of_freedom"] == pytest.approx(2)
    assert contrast["p_holm"] == pytest.approx(1 - 3 / math.sqrt(13))
    assert [row["experimental_units"] for row in result["counts"]] == [2, 2]
    for artifact in ["figure.svg", "figure.pdf", "sample-summary.csv", "experimental-units.csv", "source-review.json"]:
        downloaded = client.get(f"/v1/jobs/{jid}/files/{artifact}")
        assert downloaded.status_code == 200, (artifact, downloaded.text)
        assert downloaded.headers["cache-control"] == "no-store"
    second = TestClient(app)
    second.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert second.get(f"/v1/jobs/{jid}/region-comparison").status_code == 404
    assert second.get(f"/v1/jobs/{jid}/files/figure.svg").status_code == 404
    altered = dict(app.state.store.one(jobs, id=jid))
    altered["payload"] = {**altered["payload"], "_source_review": {"revision_id": rid}}
    with pytest.raises(ValueError, match="region_comparison_source_review_mismatch"):
        run_region_comparison(app.state.store, altered, tmp_path / "bad-adoption")
    # Retried quality confirmation must preserve the immutable source adopted
    # by completed statistics; otherwise every later export of this version fails.
    review_record = app.state.store.one(revisions, id=rid)["review_record"]
    retry_clients = [TestClient(app), TestClient(app)]
    for retry_client in retry_clients:
        retry_client.cookies.update(client.cookies)
    with ThreadPoolExecutor(max_workers=2) as pool:
        retries = [pool.submit(retry_client.post, f"/v1/revisions/{rid}/review", headers=HEADERS, json={})
                   for retry_client in retry_clients]
        assert [retry.result(timeout=15).status_code for retry in retries] == [200, 200]
    assert app.state.store.one(revisions, id=rid)["review_record"] == review_record
    export = client.post(f"/v1/revisions/{rid}/export?include_raw=true", headers=HEADERS).json()["job_id"]
    process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{export}").json()["state"] == "succeeded"
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    bundle = tmp_path / "bundle"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        assert "statistics/0/sample-summary.csv" in opened.namelist()
        assert "statistics/0/methods.md" in opened.namelist()
        opened.extractall(bundle)
    verification = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay")
    assert verification["matched_saved_measurements"] and verification["matched_saved_comparisons"]
    changed = bundle / "statistics/0/result.json"
    record = read_json(changed)
    record["comparisons"][0]["estimate"] = 999
    changed.write_text(json.dumps(record), encoding="utf-8")
    manifest_path = bundle / "manifest.json"
    manifest = read_json(manifest_path)
    manifest["files"]["statistics/0/result.json"] = sha256(changed)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    assert not replay_region_bundle(bundle, bundle / "raw", tmp_path / "tampered")["matched_saved_comparisons"]
    metadata = client.post(f"/v1/revisions/{rid}/region-metadata", headers=HEADERS,
                           json={"fields": {fids[0]: {"condition": "A"}}}).json()
    process_one(app.state.store, settings)
    assert client.post(f"/v1/revisions/{metadata['revision_id']}/region-comparisons", headers=HEADERS,
                       json=comparison_request()).status_code == 409
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/jobs/{jid}/region-comparison").status_code == 404
    assert client.get(f"/v1/jobs/{jid}/files/source-review.json").status_code == 404


def test_comparison_requires_actual_review_and_confirmation(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, rid, _ = reviewed_units(client, app, settings)
    for value in [False, 1, "true"]:
        request = comparison_request()
        request["missingness_confirmed"] = value
        assert client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS,
                           json=request).status_code == 422
    assert app.state.store.rows(jobs, revision_id=rid, kind="statistics") == []

"""Real pixels, owned jobs, editable figures and versioned statistical replay."""
import io
import json
import zipfile

import pytest
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import jobs
from cytellect_worker.common_statistics import run_common_statistics
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_comparison_api import comparison_request, reviewed_units


def common_request(association=False):
    request = comparison_request()
    if not association:
        return {**request, "version": "2.0.0", "test": "mann-whitney-u",
                "plot": {"kind": "box", "language": "en", "y_label": "Measured signal"}}
    return {key: value for key, value in {
        **request, "mode": "region-association", "version": "1.0.0",
        "x_selection": request["selection"],
        "y_selection": {**request["selection"], "metric": "integrated_corrected"},
        "acquisition_review": {**request["acquisition_review"], "spatial_sampling_confirmed": True},
        "method": "pearson", "scope": "pooled", "pooling_confirmed": True,
        "plot": {"kind": "scatter", "language": "en", "x_label": "Mean signal", "y_label": "Total signal"},
    }.items() if key not in {"selection", "comparison_family"}}


@pytest.mark.parametrize("association", [False, True])
def test_common_statistics_pixel_job_download_and_replay(tmp_path, association):
    client, app, settings = authenticated(tmp_path)
    wid, rid, _ = reviewed_units(client, app, settings)
    response = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS,
                           json=common_request(association))
    assert response.status_code == 202, response.text
    jid = response.json()["job_id"]
    process_one(app.state.store, settings)
    job_response = client.get(f"/v1/jobs/{jid}")
    assert job_response.status_code == 200, job_response.text
    job = job_response.json()
    assert job["analysis_version"] == ("1.0.0" if association else "2.0.0")
    assert job["state"] == "succeeded", job
    response = client.get(f"/v1/jobs/{jid}/common-statistics")
    assert response.status_code == 200, response.text
    value = response.json()
    if association:
        assert value["associations"][0]["coefficient"] == pytest.approx(1)
    else:
        assert value["comparisons"][0]["p_holm"] == pytest.approx(1 / 3)
    assert value["figure"]["common_statistics_methods"] == {"kind": "common-statistics", "version": "1.0.0"}
    assert client.get(f"/v1/jobs/{jid}/region-comparison").status_code == 404
    for filename in value["figure"]["source_files"]:
        downloaded = client.get(f"/v1/jobs/{jid}/files/{filename}")
        assert downloaded.status_code == 200, (filename, downloaded.text)
        assert downloaded.headers["cache-control"] == "no-store"
    assert "<text" in client.get(f"/v1/jobs/{jid}/files/figure.svg").text
    assert client.get(f"/v1/jobs/{jid}/files/figure.pdf").content.startswith(b"%PDF")
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.get(f"/v1/jobs/{jid}/common-statistics").status_code == 404
    assert foreign.get(f"/v1/jobs/{jid}/files/figure.pdf").status_code == 404
    altered = dict(app.state.store.one(jobs, id=jid))
    altered["payload"] = {**altered["payload"], "_source_review": {"revision_id": rid}}
    with pytest.raises(ValueError, match="region_comparison_source_review_mismatch"):
        run_common_statistics(app.state.store, altered, tmp_path / "bad-review")
    response = client.post(f"/v1/revisions/{rid}/export?include_raw=true", headers=HEADERS)
    export = response.json()["job_id"]
    process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{export}").json()["state"] == "succeeded"
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    bundle = tmp_path / "bundle"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(bundle)
    verification = replay_region_bundle(bundle, bundle / "raw", tmp_path / "replay")
    key = "matched_saved_associations" if association else "matched_saved_comparisons"
    assert verification["matched_saved_measurements"] and verification[key]
    replayed = json.loads((tmp_path / "replay/statistics/0/result.json").read_text(encoding="utf-8"))
    assert replayed == value
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/jobs/{jid}/common-statistics").status_code == 404
    assert client.get(f"/v1/jobs/{jid}/files/figure.pdf").status_code == 404

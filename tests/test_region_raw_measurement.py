"""Hand-calculated raw pixel values, missing corrections and version isolation."""
import json

import numpy as np
import pytest
from cytellect_analysis.region_measurement_v2 import (
    RegionMeasurementSpecV3,
    measure_regions_versioned,
    region_table_from_json,
    require_region_metric,
)
from cytellect_analysis.region_policy import RawIntensityPolicy
from cytellect_analysis.regions import ObservedChannelSpec, RegionSetSpec
from cytellect_api.db import jobs, revisions
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from cytellect_worker.regions import run_region_analysis
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes


def test_raw_values_keep_unknown_background_and_original_pixels():
    image = np.array([[0, 100, 200], [300, 400, 65535]], dtype=np.uint16)
    labels = np.array([[1, 1, 0], [2, 2, 2]], dtype=np.uint32)
    original = image.copy()
    policy = RawIntensityPolicy(version="1.1.0", mode="raw_intensity")
    spec = RegionMeasurementSpecV3(
        measurement=policy, field_id="f1", analysis_revision_id="r1",
        region_set=RegionSetSpec(region_set_id="nuclei", label="Nuclei", mask_revision_id="m1", source="imported"),
        channels=(ObservedChannelSpec(channel_id="ch1", label="Channel1", identity_source="unresolved"),),
    )
    table = measure_regions_versioned({"ch1": image}, labels, {}, spec)
    a, b = table.rows
    assert (a.area_px, a.mean, a.median, a.integrated) == (2, 50, 50, 100)
    assert (b.area_px, b.mean, b.median, b.integrated) == (3, 66235 / 3, 400, 66235)
    assert b.storage_limit_fraction == pytest.approx(1 / 3)
    assert b.mean_corrected is None and b.correction_missing_reason == "background_not_established"
    assert b.acquisition_saturation_fraction is None
    assert table.channel_provenance[0].background.status == "not_established"
    np.testing.assert_array_equal(image, original)
    assert region_table_from_json(table.model_dump_json()) == table
    for metric in ("area_px", "mean", "median", "integrated"):
        require_region_metric(policy, metric)
    with pytest.raises(ValueError, match="region_metric_not_measured"):
        require_region_metric(policy, "mean_corrected")
    with pytest.raises(ValueError):
        region_table_from_json(table.model_dump_json().replace('"protocol_version":"3.0.0"', '"protocol_version":"2.0.0"'))
    with pytest.raises(ValueError, match="backgrounds_forbidden"):
        measure_regions_versioned({"ch1": image}, labels, {"ch1": labels == 0}, spec)


def test_workspace_raw_api_preserves_evidence_and_automatic_review_state(tmp_path, monkeypatch):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Public fixture test"}).json()["id"]
    image = np.arange(144, dtype=np.uint16).reshape(12, 12)
    spec = {"version": "1.1.0", "channels": [{"channel_id": "ch1", "label": "DAPI", "stain": "DAPI", "identity_source": "filename"}]}
    uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(spec)},
                           files={"ch0": ("public.tif", tiff_bytes(image), "image/tiff")})
    assert uploaded.status_code == 201, uploaded.text
    assert "identity_confirmed" not in uploaded.json()["image_info"]["channels"][0]
    # This is a numerical/API test; the fake detector never claims actual Fiji acceptance.
    labels = np.zeros(image.shape, np.uint32)
    labels[4:6, 4:6] = 1
    def detector(*args, **kwargs):
        return labels, {"engine": "test-fixture"}
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", detector)
    response = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json={
        "field_ids": [uploaded.json()["id"]],
        "recipe": {"version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei",
                   "source": "stardist_nuclear", "defining_channel_id": "ch1", "nuclear_role_source": "recorded_stain"},
        "measurement": {"version": "1.1.0", "mode": "raw_intensity"}, "backgrounds": {}})
    assert response.status_code == 202, response.text
    claimed = app.state.store.claim()
    output = app.state.store.safe_path("results", claimed["id"])
    run_region_analysis(app.state.store, settings, claimed, output)
    assert app.state.store.finish(claimed, app.state.store.relative_path(output))
    job = client.get(f"/v1/jobs/{response.json()['job_id']}").json()
    assert job["state"] == "succeeded", job
    rid = response.json()["revision_id"]
    measured = client.get(f"/v1/revisions/{rid}/region-measurements")
    assert measured.status_code == 200, measured.text
    assert measured.json()["protocol_version"] == "3.0.0"
    assert measured.json()["field_failures"] == []
    assert measured.json()["field_tables"][uploaded.json()["id"]]["rows"][0]["mean"] == 58.5
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "nuclei", "channel_id": "ch1", "metric": "mean"}}
    assert client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body).status_code == 409
    preview = client.post(f"/v1/revisions/{rid}/descriptive-preview", headers=HEADERS, json=body)
    assert preview.status_code == 202, preview.text
    process_one(app.state.store, settings)
    state = client.get(f"/v1/jobs/{preview.json()['job_id']}").json()
    assert state["state"] == "succeeded", state
    record = app.state.store.one(jobs, id=preview.json()["job_id"])
    result = read_json(app.state.store.safe_path(record["result_dir"], "result.json"))
    assert result["source_review"] == "automatic_unreviewed"
    assert not app.state.store.one(revisions, id=rid)["reviewed"]
    assert app.state.store.safe_path(record["result_dir"], "figure.svg").is_file()
    assert app.state.store.safe_path(record["result_dir"], "figure.pdf").is_file()
    assert "Regions have not completed visual review" in app.state.store.safe_path(
        record["result_dir"], "methods.md").read_text(encoding="utf-8")
    client.close()
    app.state.store.engine.dispose()

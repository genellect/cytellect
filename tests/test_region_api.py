"""Private generic 2D ingestion and API boundaries, with exact small pixel fixtures."""

import io
import json
import zipfile

import numpy as np
import pytest
import tifffile
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated


def tiff_bytes(array):
    out = io.BytesIO()
    tifffile.imwrite(out, array, photometric="minisblack")
    return out.getvalue()


def make_field(client, wid, *, labels=True):
    spec = {"channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}],
            "metadata": {"condition": "control"}}
    pixels = np.full((12, 12), 10, np.uint16)
    pixels[4:6, 4:6] = np.array([[20, 30], [40, 50]], dtype=np.uint16)
    files = {"ch0": ("untrusted-original-name.tif", tiff_bytes(pixels), "image/tiff")}
    if labels:
        plane = np.zeros((12, 12), np.uint32)
        plane[4:6, 4:6] = 17
        files["labels"] = ("labels.tif", tiff_bytes(plane), "image/tiff")
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                       data={"specification": json.dumps(spec)}, files=files)


def region_request(fid, *, source="imported"):
    return {"field_ids": [fid], "recipe": {"region_set_id": "objects", "label": "Reviewed regions", "source": source},
            "backgrounds": {fid: {"actin": {"confirmed": True, "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]}}}}


def test_generic_upload_keeps_identity_unknown_replication_and_private_preview(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "regions"}).json()["id"]
    response = make_field(client, wid)
    assert response.status_code == 201, response.text
    field = response.json()
    assert field["metadata"]["experimental_unit"] is None
    assert field["image_info"]["channels"][0]["label"] == "Actin"
    assert field["image_info"]["channels"][0]["stain"] is None
    assert field["image_info"]["calibration"] is None
    assert "untrusted-original-name" not in response.text
    assert client.get(f"/v1/workspaces/{wid}/fields").json() == []
    assert len(client.get(f"/v1/workspaces/{wid}/region-fields").json()) == 1
    fid = field["id"]
    preview = client.get(f"/v1/region-fields/{fid}/preview?channel_id=actin")
    assert preview.status_code == 200 and preview.headers["cache-control"] == "no-store"
    assert client.get(f"/v1/fields/{fid}/preview").status_code == 404
    assert client.get(f"/v1/region-fields/{fid}/preview?channel_id=gfp").status_code == 422
    assert client.post(f"/v1/workspaces/{wid}/analyses", headers=HEADERS, json={"field_ids": [fid]}).status_code == 422
    second = TestClient(app)
    second.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert second.get(f"/v1/region-fields/{fid}/preview?channel_id=actin").status_code == 404
    assert second.get(f"/v1/workspaces/{wid}/region-fields").status_code == 404
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/region-fields/{fid}/preview?channel_id=actin").status_code == 404


@pytest.mark.parametrize("kind", ["rgb", "float", "wrong-shape", "label-float", "unconfirmed", "partial-calibration"])
def test_generic_rejects_unsupported_input_without_leaving_field(tmp_path, kind):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "invalid"}).json()["id"]
    spec = {"channels": [{"channel_id": "marker", "label": "Marker", "identity_confirmed": True}]}
    image = np.zeros((12, 12), np.uint16)
    labels = np.zeros((12, 12), np.uint32)
    if kind == "rgb":
        image = np.zeros((12, 12, 3), np.uint8)
    if kind == "float":
        image = image.astype(np.float32)
    if kind == "wrong-shape":
        labels = np.zeros((10, 10), np.uint32)
    if kind == "label-float":
        labels = labels.astype(np.float32)
    if kind == "unconfirmed":
        spec["channels"][0]["identity_confirmed"] = False
    if kind == "partial-calibration":
        spec["calibration"] = {"pixel_size_x_um": 0.5, "confirmed": True}
    response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(spec)}, files={
                               "ch0": ("image.tif", tiff_bytes(image), "image/tiff"),
                               "labels": ("labels.tif", tiff_bytes(labels), "image/tiff")})
    assert response.status_code == 422, response.text
    assert client.get(f"/v1/workspaces/{wid}/region-fields").json() == []
    folder = app.state.store.safe_path("workspaces", wid, "fields")
    assert not folder.exists() or not list(folder.iterdir())


def test_generic_manual_initialization_needs_no_labels_but_import_does(tmp_path):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "manual"}).json()["id"]
    field = make_field(client, wid, labels=False)
    assert field.status_code == 201
    fid = field.json()["id"]
    imported = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=region_request(fid))
    assert imported.status_code == 422 and imported.json()["detail"] == "region_labels_required"
    manual = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                         json=region_request(fid, source="manual"))
    assert manual.status_code == 202


def test_import_measure_edit_background_recovery_and_review(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "region workflow"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    config = region_request(fid)
    queued = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=config)
    assert queued.status_code == 202
    rid = queued.json()["revision_id"]
    assert process_one(app.state.store, settings)
    original = client.get(f"/v1/revisions/{rid}/measurements").json()
    assert original["field_failures"] == []
    row = original["field_tables"][fid]["rows"][0]
    assert row["area_px"] == 4 and row["mean"] == 35 and row["mean_corrected"] == 25
    assert row["integrated"] == 140 and row["integrated_corrected"] == 100
    assert row["area_um2"] is None
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/revisions/{rid}/fields/{fid}/masks").status_code == 409
    assert client.get(f"/v1/revisions/{rid}/region-masks?field_id={fid}").json()["regions"][0]["id"] == 17
    edit = {"field_id": fid, "region_set_id": "objects", "operation": "add",
            "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]], "expected_mask_revision_id": rid}
    stale_mask = client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS,
                             json={**edit, "expected_mask_revision_id": "previous-mask"})
    assert stale_mask.status_code == 409 and stale_mask.json()["detail"] == "stale_region_mask"
    assert client.get(f"/v1/workspaces/{wid}").json()["active_revision"] == rid
    response = client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS, json=edit)
    assert response.status_code == 202
    newer = response.json()["revision_id"]
    assert client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS, json=edit).status_code == 409
    assert process_one(app.state.store, settings)
    failed = client.get(f"/v1/revisions/{newer}/measurements").json()
    assert failed["field_failures"][0]["reason"] == "region_background_overlaps_measured_regions"
    assert client.post(f"/v1/revisions/{newer}/review", headers=HEADERS).status_code == 409
    assert len(client.get(f"/v1/revisions/{newer}/region-masks?field_id={fid}").json()["regions"]) == 2
    config["backgrounds"][fid]["actin"]["polygon"] = [[9, 9], [11, 9], [11, 11], [9, 11]]
    response = client.post(f"/v1/revisions/{newer}/region-reconfigure", headers=HEADERS, json=config)
    assert response.status_code == 202
    latest = response.json()["revision_id"]
    assert process_one(app.state.store, settings)
    report = client.get(f"/v1/revisions/{latest}/measurements").json()
    assert report["field_failures"] == []
    assert report["field_masks"][fid]["mask_revision_id"] == newer
    assert len(report["field_tables"][fid]["rows"]) == 2
    assert client.post(f"/v1/revisions/{latest}/review", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/revisions/{rid}/measurements").json() == original


def test_one_field_descriptive_export_replay_and_ownership(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "description"}).json()["id"]
    fid = make_field(client, wid).json()["id"]
    rid = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                      json=region_request(fid)).json()["revision_id"]
    assert process_one(app.state.store, settings)
    typed = client.get(f"/v1/revisions/{rid}/region-measurements")
    assert typed.status_code == 200 and typed.json()["field_tables"][fid]["rows"][0]["mean"] == 35
    body = {"mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects",
            "channel_id": "actin", "metric": "mean_corrected"},
            "plot": {"preset": "nature-double", "language": "en"}}
    assert client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body).status_code == 409
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    wrong = {**body, "selection": {"source": "legacy-cell", "metric": "gfp_mean"}}
    assert client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=wrong).status_code == 422
    queued = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=body)
    assert queued.status_code == 202
    jid = queued.json()["job_id"]
    assert process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{jid}").json()
    assert job["state"] == "succeeded", job
    assert job["analysis_mode"] == "descriptive"
    result = client.get(f"/v1/jobs/{jid}/result").json()
    assert result["counts"]["observations"] == 1 and result["counts"]["input_fields"] == 1
    assert result["counts"]["experimental_units"] is None
    assert result["plot_data"][0]["value"] == 25
    assert not {"comparisons", "model", "pvalue"}.intersection(result)
    assert client.get(f"/v1/jobs/{jid}/files/figure.svg").status_code == 200
    assert client.get(f"/v1/jobs/{jid}/files/selection.csv").status_code == 200
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert foreign.get(f"/v1/jobs/{jid}/files/figure.svg").status_code == 404
    assert foreign.get(f"/v1/revisions/{rid}/region-measurements").status_code == 404
    export = client.post(f"/v1/revisions/{rid}/export", headers=HEADERS).json()["job_id"]
    assert process_one(app.state.store, settings)
    export_job = client.get(f"/v1/jobs/{export}").json()
    assert export_job["state"] == "succeeded", export_job
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    assert archive.status_code == 200 and archive.headers["cache-control"] == "no-store"
    extracted = tmp_path / "downloaded-bundle"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        assert not any(name.startswith("raw/") for name in opened.namelist())
        assert any(name.endswith("figure.svg") for name in opened.namelist())
        opened.extractall(extracted)
    replay = replay_region_bundle(extracted, app.state.store.safe_path("workspaces", wid, "fields"),
                                  tmp_path / "replayed")
    assert replay["matched_saved_measurements"] and replay["matched_saved_descriptions"]
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/jobs/{export}/files/analysis.zip").status_code == 404


def test_same_workspace_preserves_separate_acquisition_channel_identities(tmp_path):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "identity"}).json()["id"]
    assert make_field(client, wid).status_code == 201
    changed = {"channels": [{"channel_id": "actin", "label": "DNA", "identity_confirmed": True}]}
    response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(changed)}, files={
                               "ch0": ("image.tif", tiff_bytes(np.ones((12, 12), np.uint16)), "image/tiff")})
    assert response.status_code == 201
    imported = client.get(f"/v1/workspaces/{wid}/region-fields").json()
    assert len(imported) == 2
    assert {field["image_info"]["channels"][0]["label"] for field in imported} == {"Actin", "DNA"}


@pytest.mark.parametrize("order", [(1, 4), (4, 1)])
def test_workspace_accepts_channel_subsets_without_discarding_or_renaming(tmp_path, order):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "partial fields"}).json()["id"]
    for count in order:
        spec = {"channels": [{"channel_id": f"c{i}", "label": f"Channel {i}",
                              "identity_confirmed": True} for i in range(count)]}
        files = {f"ch{i}": ("arbitrary.tif", tiff_bytes(np.full((12, 12), i + 1, np.uint16)), "image/tiff")
                 for i in range(count)}
        result = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                             data={"specification": json.dumps(spec)}, files=files)
        assert result.status_code == 201, result.text
        assert [c["channel_id"] for c in result.json()["image_info"]["channels"]] == [f"c{i}" for i in range(count)]
    stored = client.get(f"/v1/workspaces/{wid}/region-fields").json()
    assert len(stored) == 2
    assert sorted(len(f["image_info"]["channels"]) for f in stored) == [1, 4]
    changed = {"channels": [{"channel_id": "c0", "label": "Unchanged", "stain": "different",
                             "identity_confirmed": True}]}
    separate = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(changed)},
                           files={"ch0": ("x.tif", tiff_bytes(np.ones((12, 12), np.uint16)), "image/tiff")})
    assert separate.status_code == 201
    assert separate.json()["image_info"]["channels"][0]["stain"] == "different"
    assert len(client.get(f"/v1/workspaces/{wid}/region-fields").json()) == 3

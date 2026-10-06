"""Public synthetic RGB input: exact planes, four channels, export and replay."""
import io
import json
import zipfile

import numpy as np
import tifffile
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_worker.main import process_one
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes


def test_four_display_rgb_channels_keep_original_resolution_and_replay(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "RGB"}).json()["id"]
    spec = {"input_mode": "display-rgb", "channels": [
        {"channel_id": f"c{i}", "label": f"Channel {i}", "identity_confirmed": True} for i in range(4)]}
    files = {}
    for i in range(4):
        rgb = np.zeros((12, 12, 3), np.uint8)
        rgb[4:6, 4:6] = [10 + i, 20 + i, 30 + i]
        stream = io.BytesIO()
        tifffile.imwrite(stream, rgb, photometric="rgb")
        files[f"ch{i}"] = ("arbitrary.tif", stream.getvalue(), "image/tiff")
    labels = np.zeros((12, 12), np.uint32)
    labels[4:6, 4:6] = 1
    files["labels"] = ("labels.tif", tiff_bytes(labels), "image/tiff")
    response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                           data={"specification": json.dumps(spec)}, files=files)
    assert response.status_code == 201, response.text
    field = response.json()
    assert field["image_info"]["input_mode"] == "display-rgb"
    assert field["image_info"]["shape"] == [12, 12]
    fid = field["id"]
    request = {"field_ids": [fid], "recipe": {"region_set_id": "objects", "label": "Objects", "source": "imported"},
               "measurement": {"version": "1.1.0", "mode": "raw_intensity"}}
    started = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request)
    assert started.status_code == 202, started.text
    rid = started.json()["revision_id"]
    assert process_one(app.state.store, settings)
    report = client.get(f"/v1/revisions/{rid}/region-measurements").json()
    assert report["field_failures"] == []
    rows = report["field_tables"][fid]["rows"]
    assert len(rows) == 4
    for row in rows:
        expected = 30 + int(row["channel_id"][1:])
        assert row["area_px"] == 4 and row["mean"] == expected and row["integrated"] == expected * 4
    export = client.post(f"/v1/revisions/{rid}/export", headers=HEADERS).json()["job_id"]
    assert process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{export}").json()
    assert job["state"] == "succeeded", job
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    bundle = tmp_path / "bundle"
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(bundle)
    methods = (bundle / "methods.md").read_text(encoding="utf-8")
    assert "not acquired raw fluorescence" in methods
    assert "Display-RGB input transform 1.0.0" in methods
    assert "display_code_max_rgb" in (bundle / "regions.csv").read_text(encoding="utf-8")
    replay = replay_region_bundle(bundle, app.state.store.safe_path("workspaces", wid, "fields"), tmp_path / "replay")
    assert replay["matched_saved_measurements"]

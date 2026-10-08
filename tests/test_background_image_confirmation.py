"""An explicit image/ROI save does not require an invented stain identity."""
import json

import numpy as np
from cytellect_api.db import fields, revisions
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes
from test_region_cohorts import finish_analysis


def test_unknown_channel_background_save_keeps_stain_null_and_reuses_manual_mask(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "background"}).json()["id"]
    uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
        data={"specification": json.dumps({"version": "1.1.0", "channels": [
            {"channel_id": "c1", "label": "c1", "identity_source": "unresolved"}]})},
        files={"ch0": ("plane.tif", tiff_bytes(np.full((12, 12), 10, np.uint16)), "image/tiff")})
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()["id"]
    recipe = {"version": "1.0.0", "source": "manual", "region_set_id": "cell", "label": "Cell"}
    queued = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
        json={"field_ids": [fid], "recipe": recipe, "measurement": {"version": "1.1.0", "mode": "raw_intensity"}})
    assert queued.status_code == 202, queued.text
    rid = queued.json()["revision_id"]
    finish_analysis(app, settings)
    edited = client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS,
        json={"field_id": fid, "region_set_id": "cell", "operation": "add", "expected_mask_revision_id": rid,
              "polygon": [[4, 4], [7, 4], [7, 7], [4, 7]]})
    assert edited.status_code == 202, edited.text
    original = finish_analysis(app, settings)
    bg = {"polygon": [[0, 0], [2, 0], [2, 2], [0, 2]], "confirmed": True}
    body = {"field_ids": [fid], "recipe": recipe, "reuse_revision": edited.json()["revision_id"],
            "backgrounds": {fid: {"c1": bg}}, "confirmed_channel_ids": ["c1"]}
    unknown = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                         json={**body, "confirmed_channel_ids": ["missing"]})
    assert unknown.status_code == 422
    corrected = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body)
    assert corrected.status_code == 202, corrected.text
    result = finish_analysis(app, settings)
    assert not result["field_failures"]
    assert result["field_masks"] == original["field_masks"]
    assert result["field_tables"][fid]["rows"][0]["mean_corrected"] == 0
    snapshot = app.state.store.one(revisions, id=corrected.json()["revision_id"])["config"]["field_snapshot"][fid]
    assert snapshot["image_info"]["channels"][0]["stain"] is None
    original_channel = app.state.store.one(fields, id=fid)["image_info"]["channels"][0]
    assert original_channel["stain"] is None and original_channel["identity_source"] == "unresolved"

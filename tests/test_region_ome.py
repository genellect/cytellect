import io

import numpy as np
import pytest
import tifffile
from cytellect_analysis.images import read_tiff
from cytellect_api.db import fields, workspaces
from fastapi.testclient import TestClient
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated
from test_region_cohorts import finish_analysis


def image_bytes(dtype="uint16", count=4, axes="CYX", names=None):
    shape = (count, 12, 16) if axes == "CYX" else (2, count, 12, 16)
    pixels = np.arange(np.prod(shape), dtype=np.uint16).reshape(shape).astype(dtype)
    metadata = {"axes": axes}
    if names is not None:
        metadata["Channel"] = {"Name": names}
    stream = io.BytesIO()
    tifffile.imwrite(stream, pixels, ome=True, photometric="minisblack", metadata=metadata)
    return stream.getvalue(), pixels


def upload(client, wid, content, key="10000000-0000-0000-0000-000000000001", headers=HEADERS):
    return client.post(f"/v1/workspaces/{wid}/region-fields/ome", headers=headers,
        data={"client_upload_id": key}, files={"ome": ("private-name.ome.tif", content, "image/tiff")})


@pytest.mark.parametrize("dtype", ["uint8", "uint16"])
def test_four_channel_ome_retains_exact_planes_names_and_idempotent_retry(tmp_path, dtype):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "ome"}).json()["id"]
    content, pixels = image_bytes(dtype, names=["NCL", "unknown dye", "GFP", "DAPI"])
    response = upload(client, wid, content)
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["image_info"]["shape"] == [12, 16]
    channels = result["image_info"]["channels"]
    assert [item["stain"] for item in channels] == ["NCL", "unknown dye", "GFP", "DAPI"]
    assert all(item["identity_source"] == "ome_metadata" and "role" not in item for item in channels)
    for index, channel in enumerate(channels):
        array = np.load(app.state.store.safe_path("workspaces", wid, "fields", result["id"], f"channel-{channel['channel_id']}.npy"))
        np.testing.assert_array_equal(array, pixels[index])
        assert array.dtype == pixels.dtype
    assert "private-name" not in response.text
    assert upload(client, wid, content).json() == result
    assert len(app.state.store.rows(fields, workspace_id=wid)) == 1
    assert len(list(app.state.store.safe_path("workspaces", wid, "fields").iterdir())) == 1
    changed, _ = image_bytes(dtype, names=["changed", "b", "c", "d"])
    assert upload(client, wid, changed).status_code == 409
    assert upload(client, wid, content, headers={}).status_code == 403
    foreign = TestClient(app)
    foreign.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    assert upload(foreign, wid, content).status_code == 404
    # The legacy fixed-role parser still accepts at most three channels.
    original = app.state.store.safe_path("workspaces", wid, "fields", result["id"], "ome.tif")
    with pytest.raises(ValueError):
        read_tiff(original, channel_indices=[0, 1, 2, 3])


@pytest.mark.parametrize("count", [1, 2, 3])
def test_unnamed_ome_channels_do_not_invent_stains_or_nuclear_roles(tmp_path, count):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "unknown"}).json()["id"]
    content, _ = image_bytes(count=count)
    response = upload(client, wid, content)
    assert response.status_code == 201, response.text
    channels = response.json()["image_info"]["channels"]
    assert len(channels) == count
    assert all(channel["stain"] is None and channel["identity_source"] == "unresolved" for channel in channels)


@pytest.mark.parametrize("kind", ["ZCYX", "TCYX", "many_channels", "float", "multiple_series", "corrupt"])
def test_unsupported_ome_is_rejected_and_temporary_images_are_removed(tmp_path, kind):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "bad"}).json()["id"]
    if kind in ("ZCYX", "TCYX"):
        content, _ = image_bytes(count=2, axes=kind)
    elif kind == "multiple_series":
        stream = io.BytesIO()
        with tifffile.TiffWriter(stream, ome=True) as writer:
            for _ in range(2):
                writer.write(np.zeros((12, 16), np.uint16), photometric="minisblack", metadata={"axes": "YX"})
        content = stream.getvalue()
    elif kind == "corrupt":
        content = b"invalid"
    else:
        content, _ = image_bytes(dtype="float32" if kind == "float" else "uint16", count=5 if kind == "many_channels" else 2)
    response = upload(client, wid, content)
    assert response.status_code == 422, response.text
    assert not app.state.store.rows(fields, workspace_id=wid)
    assert not list(app.state.store.safe_path("workspaces", wid, "fields").iterdir())


def test_ome_respects_workspace_byte_cap_without_retaining_failed_upload(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "cap"}).json()["id"]
    with app.state.store.transaction() as conn:
        conn.execute(update(workspaces).where(workspaces.c.id == wid).values(bytes=settings.max_upload_bytes - 1))
    response = upload(client, wid, image_bytes()[0])
    assert response.status_code == 413
    assert not list(app.state.store.safe_path("workspaces", wid, "fields").iterdir())


def test_ome_manual_region_worker_measures_all_four_original_planes(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "measure"}).json()["id"]
    content, pixels = image_bytes()
    fid = upload(client, wid, content).json()["id"]
    queued = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
        json={"field_ids": [fid], "recipe": {"source": "manual", "region_set_id": "cell", "label": "Cell"},
              "measurement": {"version": "1.1.0", "mode": "raw_intensity"}})
    assert queued.status_code == 202, queued.text
    rid = queued.json()["revision_id"]
    assert not finish_analysis(app, settings)["field_failures"]
    edited = client.post(f"/v1/revisions/{rid}/region-edits", headers=HEADERS,
        json={"field_id": fid, "region_set_id": "cell", "operation": "add", "expected_mask_revision_id": rid,
              "polygon": [[4, 4], [7, 4], [7, 7], [4, 7]]})
    assert edited.status_code == 202, edited.text
    report = finish_analysis(app, settings)
    assert not report["field_failures"]
    rows = report["field_tables"][fid]["rows"]
    assert {row["channel_id"] for row in rows} == {"c1", "c2", "c3", "c4"}
    from cytellect_analysis.masks import polygon_mask
    roi = polygon_mask(pixels.shape[1:], [[4, 4], [7, 4], [7, 7], [4, 7]])
    for index in range(4):
        row = next(value for value in rows if value["channel_id"] == f"c{index + 1}")
        assert row["mean"] == float(pixels[index][roi].mean())

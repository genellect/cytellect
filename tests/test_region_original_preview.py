"""Original display RGB stays separate from unchanged max-RGB measurement planes."""
import hashlib
import io
import json

import numpy as np
import pytest
import tifffile
from cytellect_analysis.display_contracts import (
    PREVIEW_DISPLAY_HEADER,
    OriginalRgbPreviewMetadata,
    RegionPreviewDisplayMetadata,
)
from cytellect_api.db import workspaces
from fastapi.testclient import TestClient
from PIL import Image
from test_api_worker import HEADERS, authenticated


def upload_rgb(client, *, planar=False, alpha=False):
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Display fixture"}).json()["id"]
    rgb = np.zeros((4, 7, 4 if alpha else 3), np.uint8)
    rgb[..., :3] = [11, 23, 37]
    rgb[1, 2, :3] = [91, 52, 18]
    rgb[3, 5, :3] = [22, 77, 66]
    if alpha:
        rgb[..., 3] = 255
        rgb[1, 2, 3] = 129
    stored = np.moveaxis(rgb, -1, 0) if planar else rgb
    stream = io.BytesIO()
    tifffile.imwrite(stream, stored, photometric="rgb", planarconfig="separate" if planar else "contig")
    original = stream.getvalue()
    response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
        data={"specification": json.dumps({"input_mode": "display-rgb", "channels": [
            {"channel_id": "signal", "label": "Display signal", "identity_confirmed": True}]})},
        files={"ch0": ("not-a-channel-name.tif", original, "image/tiff")})
    assert response.status_code == 201, response.text
    return wid, response.json()["id"], rgb, original


@pytest.mark.parametrize(("planar", "alpha"), [(False, False), (True, False), (False, True)])
def test_original_rgb_samples_size_and_alpha_survive_preview(tmp_path, planar, alpha):
    client, app, _ = authenticated(tmp_path)
    wid, fid, rgb, original = upload_rgb(client, planar=planar, alpha=alpha)
    folder = app.state.store.safe_path("workspaces", wid, "fields", fid)
    measured_before = (folder / "channel-signal.npy").read_bytes()
    assert np.array_equal(np.load(io.BytesIO(measured_before)), rgb[..., :3].max(axis=-1))
    expires = app.state.store.one(workspaces, id=wid)["expires"]
    response = client.get(f"/v1/region-fields/{fid}/preview?channel_id=signal", headers={"origin": "http://test"})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    assert np.array_equal(np.asarray(Image.open(io.BytesIO(response.content))), rgb)
    header = response.headers[PREVIEW_DISPLAY_HEADER]
    assert header.isascii() and PREVIEW_DISPLAY_HEADER in response.headers["access-control-expose-headers"]
    display = RegionPreviewDisplayMetadata.model_validate_json(header).root
    assert isinstance(display, OriginalRgbPreviewMetadata)
    assert display.mode == "original-display-rgb" and display.value_basis == "display-rgb-code"
    assert display.source_axes == ("SYX" if planar else "YXS")
    assert display.rendered_shape == rgb.shape and display.alpha_preserved is alpha
    assert display.source_file_sha256 == hashlib.sha256(original).hexdigest()
    assert not display.contrast_applied and display.sample_values_unchanged
    assert (folder / "ch0.tif").read_bytes() == original
    assert (folder / "channel-signal.npy").read_bytes() == measured_before
    assert app.state.store.one(workspaces, id=wid)["expires"] == expires


@pytest.mark.parametrize("query", ["gain=2", "low=1", "high=99"])
def test_original_preview_does_not_silently_ignore_contrast_request(tmp_path, query):
    client, _, _ = authenticated(tmp_path)
    _, fid, _, _ = upload_rgb(client)
    response = client.get(f"/v1/region-fields/{fid}/preview?channel_id=signal&{query}")
    assert response.status_code == 422
    assert response.json()["detail"] == "original_rgb_preview_has_no_contrast_adjustment"
    assert PREVIEW_DISPLAY_HEADER not in response.headers


@pytest.mark.parametrize("change", ["modified", "missing"])
def test_original_preview_fails_closed_without_using_measurement_fallback(tmp_path, change):
    client, app, _ = authenticated(tmp_path)
    wid, fid, _, original = upload_rgb(client)
    path = app.state.store.safe_path("workspaces", wid, "fields", fid, "ch0.tif")
    if change == "modified":
        path.write_bytes(original[:-1] + bytes([original[-1] ^ 1]))
    else:
        path.unlink()
    response = client.get(f"/v1/region-fields/{fid}/preview?channel_id=signal")
    assert response.status_code == 409 and response.json()["detail"] == "region_original_image_mismatch"
    assert PREVIEW_DISPLAY_HEADER not in response.headers


def test_original_preview_uses_live_owner_and_exposes_truthful_union(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid, fid, _, _ = upload_rgb(client)
    other = TestClient(app)
    other.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    response = other.get(f"/v1/region-fields/{fid}/preview?channel_id=signal")
    assert response.status_code == 404 and PREVIEW_DISPLAY_HEADER not in response.headers
    document = app.openapi()
    schema = document["components"]["schemas"]["RegionPreviewDisplayMetadata"]
    assert {item["$ref"].rsplit("/", 1)[1] for item in schema["anyOf"]} == {
        "PreviewDisplayMetadata", "OriginalRgbPreviewMetadata"}
    assert client.delete(f"/v1/workspaces/{wid}", headers=HEADERS).status_code == 200
    assert client.get(f"/v1/region-fields/{fid}/preview?channel_id=signal").status_code == 404

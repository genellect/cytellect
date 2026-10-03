"""Display receipts correspond to exact pixels, never authoritative measurements."""
import io
import json

import numpy as np
import pytest
import tifffile
from cytellect_analysis.display_contracts import PREVIEW_DISPLAY_HEADER, PreviewDisplayMetadata
from cytellect_analysis.images import read_tiff, render_preview, render_preview_with_display
from cytellect_api.db import workspaces
from cytellect_worker.main import process_one
from fastapi.testclient import TestClient
from PIL import Image
from test_api_optional_channels import metadata
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes


def pixels(png):
    return np.asarray(Image.open(io.BytesIO(png)))


@pytest.mark.parametrize("gain", [0.1, 1, 2, 10])
def test_exact_16_bit_render_and_effective_range_do_not_modify_input(gain):
    original = np.array([[100, 1100, 2100], [3100, 4100, 5100]], np.uint16)
    preserved = original.copy()
    png, display = render_preview_with_display({"signal": original}, "signal", 20, 80, gain, field_id="f")
    plane = display.planes[0]
    assert (plane.source_min, plane.source_max) == (100, 5100)
    assert (plane.percentile_low_value, plane.percentile_high_value) == (1100, 4100)
    assert plane.normalization_span == 3000 and plane.dtype == "uint16"
    assert (plane.display_black_value, plane.display_white_value) == (1100, 1100 + 3000 / gain)
    expected = (np.clip((original.astype(float) - 1100) / 3000 * gain, 0, 1) * 255).astype(np.uint8)
    np.testing.assert_array_equal(pixels(png), np.repeat(expected[..., None], 3, axis=2))
    np.testing.assert_array_equal(original, preserved)
    assert render_preview({"signal": original}, "signal", 20, 80, gain) == png


@pytest.mark.parametrize("value", [0, 4095])
def test_constant_plane_keeps_source_value_and_explicit_span(value):
    png, display = render_preview_with_display({"x": np.full((3, 3), value, np.uint16)}, "x")
    plane = display.planes[0]
    assert plane.constant_plane and plane.source_min == plane.source_max == value
    assert (plane.display_black_value, plane.display_white_value) == (value, value + 1)
    assert not pixels(png).any()


def test_percentile_collapse_is_distinct_from_constant_and_legacy_float_is_supported():
    a = np.zeros((100, 100), np.uint16)
    a[-1, -1] = 99
    _, display = render_preview_with_display({"x": a}, "x", 1, 99)
    plane = display.planes[0]
    assert not plane.constant_plane and plane.normalization_span == 1
    assert plane.percentile_low_value == plane.percentile_high_value == 0
    _, legacy = render_preview_with_display({"x": np.array([[-2.5, 0., 7.5]])}, "x", legacy=True)
    assert legacy.planes[0].dtype == "float64" and legacy.planes[0].source_min == -2.5
    assert legacy.planes[0].value_basis == "legacy-imported"


def test_native_merge_omits_unacquired_plane_but_preserves_rgb_formula():
    channels = {"dapi": np.array([[0, 100]], np.uint8), "gfp": np.array([[10, 20]], np.uint16)}
    png, display = render_preview_with_display(channels)
    assert display.composite and [p.channel_id for p in display.planes] == ["gfp", "dapi"]
    np.testing.assert_array_equal(pixels(png), [[[0, 0, 0], [0, 255, 255]]])


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_nonfinite_pixels_or_settings_fail_closed(value):
    with pytest.raises(ValueError, match="invalid_display_pixels"):
        render_preview_with_display({"x": np.array([[value]])}, "x")
    with pytest.raises(ValueError, match="invalid_display_settings"):
        render_preview_with_display({"x": np.zeros((1, 1))}, "x", gain=value)


def test_rgb_legacy_receipt_describes_imported_pixels_without_claiming_native_stain(tmp_path):
    rgba = np.array([[[10, 20, 30, 255], [40, 2, 3, 255]]], np.uint8)
    path = tmp_path / "rgba.tif"
    tifffile.imwrite(path, rgba, photometric="rgb")
    with pytest.raises(ValueError):
        read_tiff(path)
    converted = read_tiff(path, legacy=True)
    np.testing.assert_array_equal(converted, [[30, 40]])
    _, display = render_preview_with_display({"x": converted}, "x", legacy=True)
    assert display.planes[0].source_min == 30 and display.planes[0].source_max == 40
    assert display.planes[0].value_basis == "legacy-imported"


def test_generic_named_merge_is_a_real_plane_and_preview_preserves_reviewed_measurements(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "display"}).json()["id"]
    image = np.full((12, 12), 100, np.uint16)
    image[4:6, 4:6] = [[1100, 2100], [3100, 4100]]
    labels = np.zeros((12, 12), np.uint32)
    labels[4:6, 4:6] = 17
    uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
        data={"specification": json.dumps({"channels": [{"channel_id": "merge", "label": "測定信号", "identity_confirmed": True}]})},
        files={"ch0": ("image.tif", tiff_bytes(image)), "labels": ("labels.tif", tiff_bytes(labels))})
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()["id"]
    request = {"field_ids": [fid], "recipe": {"region_set_id": "objects", "label": "Regions", "source": "imported"},
               "backgrounds": {fid: {"merge": {"confirmed": True, "polygon": [[0, 0], [2, 0], [2, 2], [0, 2]]}}}}
    queued = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=request)
    assert queued.status_code == 202, queued.text
    rid = queued.json()["revision_id"]
    assert process_one(app.state.store, settings)
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS).status_code == 200
    before = {suffix: client.get(f"/v1/revisions/{rid}{suffix}").json()
              for suffix in ("", "/measurements", f"/region-masks?field_id={fid}")}
    assert before["/measurements"]["field_tables"][fid]["rows"][0]["mean"] == 2600
    expires = app.state.store.one(workspaces, id=wid)["expires"]
    response = client.get(f"/v1/region-fields/{fid}/preview?channel_id=merge&gain=2", headers={"origin": "http://test"})
    assert response.status_code == 200 and response.headers["cache-control"] == "no-store"
    header = response.headers[PREVIEW_DISPLAY_HEADER]
    assert header.isascii() and PREVIEW_DISPLAY_HEADER in response.headers["access-control-expose-headers"]
    display = PreviewDisplayMetadata.model_validate_json(header)
    assert not display.composite and display.field_id == fid and display.requested_channel == "merge"
    assert display.planes[0].display_white_value == 2100 and pixels(response.content).max() == 255
    assert before == {suffix: client.get(f"/v1/revisions/{rid}{suffix}").json() for suffix in before}
    assert app.state.store.one(workspaces, id=wid)["expires"] == expires
    second = TestClient(app)
    second.post("/v1/invitations/redeem", headers=HEADERS, json={"token": app.state.store.invite()})
    denied = second.get(f"/v1/region-fields/{fid}/preview?channel_id=merge")
    assert denied.status_code == 404 and PREVIEW_DISPLAY_HEADER not in denied.headers


def test_native_header_actual_plane_dtypes_and_openapi(tmp_path):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "native"}).json()["id"]
    uploaded = client.post(f"/v1/workspaces/{wid}/fields", headers=HEADERS,
        data={"metadata": json.dumps(metadata())}, files={
            "dapi": ("nuclear.tif", tiff_bytes(np.array([[0, 255]], np.uint8))),
            "gfp": ("signal.tif", tiff_bytes(np.array([[100, 4095]], np.uint16)))})
    assert uploaded.status_code == 201, uploaded.text
    fid = uploaded.json()["id"]
    response = client.get(f"/v1/fields/{fid}/preview")
    display = PreviewDisplayMetadata.model_validate_json(response.headers[PREVIEW_DISPLAY_HEADER])
    assert [(p.channel_id, p.dtype, p.source_max) for p in display.planes] == [("gfp", "uint16", 4095), ("dapi", "uint8", 255)]
    document = app.openapi()
    assert "PreviewPlaneDisplay" in document["components"]["schemas"]
    for path in ("/v1/fields/{fid}/preview", "/v1/region-fields/{fid}/preview"):
        contract = document["paths"][path]["get"]["responses"]["200"]
        assert list(contract["content"]) == ["image/png"]
        assert contract["headers"][PREVIEW_DISPLAY_HEADER]["content"]["application/json"]["schema"]["$ref"].endswith("PreviewDisplayMetadata")

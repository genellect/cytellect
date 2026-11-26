"""The intake inspection judges one file as registration would and stores nothing (#284 W4).

Images are the registered public BBBC013 and BBBC039 files, the RGB and OME containers are written from their
pixels, and the truncated file is the first 32 bytes of A01-dapi.tif (the Issue's damaged sample). The 32-bit label
image is a synthetic array: the role depends only on the type and shape, so its content does not matter.
"""

import base64
import hashlib
import io
import json
import sys
from pathlib import Path

import numpy as np
import pytest
import tifffile
from cytellect_api import intake
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import fields, workspaces
from cytellect_api.public_uploads import load_allowlist
from fastapi.testclient import TestClient
from PIL import Image
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from public_bbbc039 import FIXTURE, decode_ground_truth, verify  # noqa: E402

BBBC013 = ROOT / "fixtures/public/bbbc013"
DAPI = (BBBC013 / "A01-dapi.tif").read_bytes()
GFP = (BBBC013 / "A01-gfp.tif").read_bytes()
TRUNCATED = DAPI[:32]
ROUTE = "/v1/intake/inspect"


def synthetic_label(shape=(640, 640), dtype=np.uint32, byteorder="<"):
    labels = np.zeros(shape, dtype)
    labels[100:200, 100:220] = 1
    labels[300:420, 350:500] = 2
    out = io.BytesIO()
    tifffile.imwrite(out, labels, photometric="minisblack", byteorder=byteorder)
    return out.getvalue()


def rgb_from_public():
    dapi, gfp = tifffile.imread(io.BytesIO(DAPI)), tifffile.imread(io.BytesIO(GFP))
    out = io.BytesIO()
    tifffile.imwrite(out, np.stack([dapi, gfp, np.zeros_like(dapi)], axis=-1), photometric="rgb")
    return out.getvalue()


def ome_from_public(names=("DAPI", "GFP")):
    stack = np.stack([tifffile.imread(io.BytesIO(DAPI)), tifffile.imread(io.BytesIO(GFP))])
    out = io.BytesIO()
    tifffile.imwrite(out, stack, ome=True, photometric="minisblack", metadata={"axes": "CYX", "Channel": {"Name": list(names)}})
    return out.getvalue()


@pytest.fixture(scope="module")
def bbbc039():
    field = verify()["images"][0]
    image = (FIXTURE / field["image"]["path"]).read_bytes()
    mask = decode_ground_truth(FIXTURE / field["mask"]["path"])
    return image, mask


def inspect(client, content, kind="native", headers=HEADERS):
    return client.post(ROUTE, headers=headers, data={"kind": kind},
                       files={"file": ("private-name.tif", content, "image/tiff")})


def judged(response):
    assert response.status_code == 200, response.text
    assert "private-name" not in response.text
    return response.json()


def register(client, wid, content, kind):
    if kind == "ome":
        return client.post(f"/v1/workspaces/{wid}/region-fields/ome", headers=HEADERS,
                           files={"ome": ("private-name.tif", content, "image/tiff")})
    spec = {"channels": [{"channel_id": "c1", "label": "c1", "identity_confirmed": True}], "metadata": {},
            "input_mode": kind}
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS, data={"specification": json.dumps(spec)},
                       files={"ch0": ("private-name.tif", content, "image/tiff")})


def stored(app, root):
    store = app.state.store
    files = sorted(str(path.relative_to(root)) for path in root.rglob("*")
                   if path.is_file() and path.suffix not in (".db", ".db-wal", ".db-shm", ".sqlite", ".sqlite3"))
    with store.transaction() as conn:
        counts = (conn.execute(workspaces.select()).all(), conn.execute(fields.select()).all())
    return files, [len(rows) for rows in counts]


def test_input_five_four_public_images_and_one_synthetic_32_bit_label(tmp_path):
    client, _, _ = authenticated(tmp_path)
    names = ["A01-dapi", "A01-gfp", "A06-dapi", "A06-gfp"]
    results = [judged(inspect(client, (BBBC013 / f"{name}.tif").read_bytes())) for name in names]
    label = judged(inspect(client, synthetic_label()))
    assert [item["role"] for item in results] == ["image"] * 4 and label["role"] == "label"
    for name, item in zip(names, results, strict=True):
        content = (BBBC013 / f"{name}.tif").read_bytes()
        assert item | {"thumbnail_png": None} == {
            "kind": "native", "role": "image", "code": None, "sha256": hashlib.sha256(content).hexdigest(),
            "bytes": len(content), "shape": [640, 640], "dtype": "uint8", "channel_names": None, "thumbnail_png": None}
        thumbnail = Image.open(io.BytesIO(base64.b64decode(item["thumbnail_png"])))
        assert thumbnail.format == "PNG" and max(thumbnail.size) <= 256 and thumbnail.mode == "L"
    assert label | {"thumbnail_png": None, "sha256": None, "bytes": None} == {
        "kind": "native", "role": "label", "code": "region_image_bit_depth_unsupported", "sha256": None, "bytes": None,
        "shape": [640, 640], "dtype": "uint32", "channel_names": None, "thumbnail_png": None}
    mask = np.asarray(Image.open(io.BytesIO(base64.b64decode(label["thumbnail_png"]))))
    assert set(np.unique(mask)) == {0, 255}


def test_truncated_public_file_and_other_types_are_named_by_registration_codes(tmp_path, bbbc039):
    client, _, _ = authenticated(tmp_path)
    truncated = judged(inspect(client, TRUNCATED))
    assert truncated["role"] == "unreadable" and truncated["code"] == "unsupported_or_invalid_region_image"
    assert truncated["sha256"] == hashlib.sha256(TRUNCATED).hexdigest() and truncated["bytes"] == 32
    assert truncated["shape"] is None and truncated["thumbnail_png"] is None
    # A signed 32-bit label image is a label too; a 32-bit float image is refused for its bit depth, not a label.
    assert judged(inspect(client, synthetic_label(dtype=np.int32)))["role"] == "label"
    big_endian = judged(inspect(client, synthetic_label(byteorder=">")))
    assert big_endian["role"] == "label" and big_endian["dtype"] == "uint32"
    image, _ = bbbc039
    floating = tiff_bytes(tifffile.imread(io.BytesIO(image)).astype(np.float32))
    assert judged(inspect(client, floating)) | {"sha256": None, "bytes": None} == {
        "kind": "native", "role": "unreadable", "code": "region_image_bit_depth_unsupported", "sha256": None,
        "bytes": None, "shape": None, "dtype": None, "channel_names": None, "thumbnail_png": None}
    stack = tifffile.imread(io.BytesIO(DAPI))
    assert judged(inspect(client, tiff_bytes(np.stack([stack, stack]))))["code"] == "region_image_not_grayscale"


def test_8_and_16_bit_masks_are_images_because_use_is_not_inferred_from_content(tmp_path, bbbc039):
    client, _, _ = authenticated(tmp_path)
    image, mask = bbbc039
    assert judged(inspect(client, image))["dtype"] == "uint16"
    for dtype in (np.uint8, np.uint16):
        found = judged(inspect(client, tiff_bytes(mask.astype(dtype))))
        assert found["role"] == "image" and found["code"] is None and found["dtype"] == np.dtype(dtype).name


def test_the_three_routings_read_as_registration_would(tmp_path):
    client, _, _ = authenticated(tmp_path)
    rgb = rgb_from_public()
    assert judged(inspect(client, rgb, "native"))["code"] == "region_image_not_grayscale"
    shown = judged(inspect(client, rgb, "display-rgb"))
    assert shown["role"] == "image" and shown["shape"] == [640, 640] and shown["dtype"] == "uint8"
    assert judged(inspect(client, rgb, "ome"))["code"] == "unsupported_or_invalid_region_ome"
    ome = ome_from_public()
    found = judged(inspect(client, ome, "ome"))
    assert found | {"thumbnail_png": None, "sha256": None, "bytes": None} == {
        "kind": "ome", "role": "image", "code": None, "sha256": None, "bytes": None, "shape": [640, 640],
        "dtype": "uint8", "channel_names": ["DAPI", "GFP"], "thumbnail_png": None}
    assert found["thumbnail_png"]
    assert judged(inspect(client, ome_from_public(names=("", "")), "ome"))["channel_names"] == [None, None]
    assert judged(inspect(client, ome_from_public(names=("x" * 121, "GFP")), "ome"))["code"] == "unsupported_or_invalid_region_ome"
    assert judged(inspect(client, ome, "native"))["role"] == "unreadable"
    assert judged(inspect(client, DAPI, "ome"))["code"] == "unsupported_or_invalid_region_ome"
    assert judged(inspect(client, TRUNCATED, "ome"))["code"] == "unsupported_or_invalid_region_ome"
    assert inspect(client, DAPI, "tiff").status_code == 422


def test_inspection_and_registration_agree_for_every_routing(tmp_path, bbbc039):
    client, _, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "agreement"}).json()["id"]
    image, mask = bbbc039
    samples = [DAPI, GFP, image, TRUNCATED, synthetic_label(), synthetic_label(dtype=np.int32), tiff_bytes(mask.astype(np.uint16)),
               tiff_bytes(tifffile.imread(io.BytesIO(image)).astype(np.float32)), rgb_from_public(), ome_from_public(),
               # An OME channel name longer than a stored label (120 characters) is refused by both.
               ome_from_public(names=("x" * 121, "GFP")), synthetic_label(byteorder=">")]
    for kind in ("native", "display-rgb", "ome"):
        for content in samples:
            found = judged(inspect(client, content, kind))
            registered = register(client, wid, content, kind)
            assert registered.status_code in (201, 422), registered.text
            assert (found["role"] == "image") == (registered.status_code == 201), (kind, found, registered.text)
            if registered.status_code == 422:
                assert found["code"] == registered.json()["detail"]
            else:
                assert registered.json()["image_info"]["shape"] == found["shape"]
                assert all(item["sha256"] == found["sha256"] for item in registered.json()["image_info"]["inputs"].values())


def test_inspection_stores_nothing_and_removes_its_temporary_files(tmp_path, monkeypatch):
    client, app, _ = authenticated(tmp_path)
    client.post("/v1/workspaces", headers=HEADERS, json={"title": "existing"})
    before = stored(app, tmp_path)
    for content, kind in [(DAPI, "native"), (TRUNCATED, "native"), (synthetic_label(), "native"),
                          (ome_from_public(), "ome"), (rgb_from_public(), "display-rgb")]:
        judged(inspect(client, content, kind))
    monkeypatch.setattr(intake, "FILE_LIMIT", 1000)
    refused = inspect(client, DAPI)
    assert refused.status_code == 413 and refused.json()["detail"] == "field_upload_limit"
    assert stored(app, tmp_path) == before
    assert not list((tmp_path / "tmp").glob("intake-*"))


def test_shared_environment_inspects_only_registered_public_files(tmp_path, bbbc039):
    app = create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False,
                              upload_allowlist=load_allowlist(ROOT / "fixtures/public/uploads.json")))
    client = TestClient(app)
    assert client.post("/v1/invitations/redeem", json={"token": app.state.store.invite()}, headers=HEADERS).status_code == 200
    assert judged(inspect(client, DAPI))["role"] == "image"
    image, _ = bbbc039
    for content in (image, TRUNCATED):
        refused = inspect(client, content)
        assert refused.status_code == 403 and refused.json()["detail"] == "unregistered_upload"
    assert not list((tmp_path / "tmp").glob("intake-*"))


def test_inspection_requires_a_session_and_the_request_headers(tmp_path):
    client, app, _ = authenticated(tmp_path)
    assert inspect(client, DAPI, headers={}).json()["detail"] == "origin_or_csrf_invalid"
    stranger = TestClient(app)
    refused = inspect(stranger, DAPI)
    assert refused.status_code == 401 and refused.json()["detail"] == "session_required"
    assert not list((tmp_path / "tmp").glob("intake-*"))

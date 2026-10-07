"""Retry identity, atomic quota accounting and non-destructive SQLite upgrades."""

import asyncio
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from pathlib import Path
from threading import Barrier
from uuid import uuid4

import numpy as np
import pytest
from alembic import command
from alembic.config import Config
from cytellect_analysis.region_contracts import RegionFieldInput
from cytellect_api import regions as region_api
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import Store, digest, fields, sessions, workspaces
from cytellect_api.upload_guard import UploadGuardMiddleware
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine, inspect, select, update
from sqlalchemy.exc import IntegrityError
from starlette.requests import Request
from starlette.responses import JSONResponse
from test_api_worker import HEADERS
from test_region_api import tiff_bytes
from test_upload_guard import AuthStore, context, invoke, settings, status


def setup_upload(tmp_path, **limits):
    app = create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False, **limits))
    client = TestClient(app)
    assert client.post("/v1/invitations/redeem", headers=HEADERS,
                       json={"token": app.state.store.invite()}).status_code == 200
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Retry fixture"}).json()["id"]
    return client, app.state.store, wid


def upload_input():
    pixels = np.arange(144, dtype=np.uint16).reshape(12, 12)
    plane = np.zeros_like(pixels)
    plane[4:6, 4:6] = 17
    spec = {"client_upload_id": str(uuid4()),
            "channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}],
            "metadata": {"condition": "control"}}
    images = {"ch0": tiff_bytes(pixels), "labels": tiff_bytes(plane)}
    return spec, images


def upload(client, wid, spec, images, *, filename="fixture.tif"):
    return client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                       data={"specification": json.dumps(spec)},
                       files={slot: (filename, content, "image/tiff") for slot, content in images.items()})


def assert_single_upload(store, wid, field, images):
    assert [row["id"] for row in store.rows(fields, workspace_id=wid)] == [field["id"]]
    assert store.one(workspaces, id=wid)["bytes"] == sum(map(len, images.values()))
    root = store.safe_path("workspaces", wid, "fields")
    assert {folder.name for folder in root.iterdir()} == {field["id"]}
    for slot, raw in images.items():
        assert (root / field["id"] / f"{slot}.tif").read_bytes() == raw


@pytest.mark.parametrize("key", ["bad", "00000000000000000000000000000000",
                                "00112233-4455-6677-8899-AABBCCDDEEFF",
                                "{00112233-4455-6677-8899-aabbccddeeff}",
                                "urn:uuid:00112233-4455-6677-8899-aabbccddeeff",
                                "00112233-4455-6677-8899-aabbccddeeff\n", True, 123])
def test_client_upload_id_must_be_canonical_uuid(key):
    spec, _ = upload_input()
    spec["client_upload_id"] = key
    with pytest.raises(ValidationError):
        RegionFieldInput.model_validate_json(json.dumps(spec))


def test_retry_after_response_loss_ignores_filename_and_normalizes_defaults(tmp_path):
    spec, images = upload_input()
    client, store, wid = setup_upload(tmp_path, max_fields=1, max_upload_bytes=sum(map(len, images.values())))
    first = upload(client, wid, spec, images)
    assert first.status_code == 201, first.text
    normalized = RegionFieldInput.model_validate_json(json.dumps(spec)).model_dump(mode="json")
    retry = upload(client, wid, normalized, images, filename="renamed-untrusted-original.tif")
    assert retry.status_code == 201, retry.text
    assert retry.json() == first.json()
    assert retry.headers["cache-control"] == "no-store"
    assert_single_upload(store, wid, first.json(), images)
    saved = store.one(fields, id=first.json()["id"])
    assert saved["client_upload_id"] == spec["client_upload_id"]
    descriptor = {"specification": {key: value for key, value in normalized.items() if key != "client_upload_id"},
                  "inputs": {slot: {"bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()}
                             for slot, raw in images.items()}}
    expected = hashlib.sha256(json.dumps(descriptor, sort_keys=True, separators=(",", ":"),
                                        ensure_ascii=False, allow_nan=False).encode()).hexdigest()
    assert saved["upload_fingerprint"] == expected
    # A new key is a new field even for identical bytes (never silently merged);
    # here it exceeds the one-field limit instead of reusing the first field.
    new_spec = {**spec, "client_upload_id": str(uuid4())}
    separate = upload(client, wid, new_spec, images)
    assert separate.status_code == 413 and separate.json()["detail"] == "workspace_limit"
    assert_single_upload(store, wid, first.json(), images)


@pytest.mark.parametrize("change", ["metadata", "channel", "stain", "calibration", "pixels",
                                   "labels", "missing-labels", "invalid-image"])
def test_key_collision_is_fixed_conflict_and_preserves_original(tmp_path, change):
    client, store, wid = setup_upload(tmp_path, max_fields=1)
    spec, images = upload_input()
    first = upload(client, wid, spec, images)
    assert first.status_code == 201, first.text
    changed_spec, changed_images = deepcopy(spec), dict(images)
    if change == "metadata":
        changed_spec["metadata"]["condition"] = "other"
    elif change == "channel":
        changed_spec["channels"][0]["channel_id"] = "marker"
    elif change == "stain":
        changed_spec["channels"][0]["stain"] = "Phalloidin"
    elif change == "calibration":
        changed_spec["calibration"] = {"pixel_size_x_um": 0.2, "pixel_size_y_um": 0.4, "confirmed": True}
    elif change in ("pixels", "labels"):
        changed_images["ch0" if change == "pixels" else "labels"] = tiff_bytes(np.ones((12, 12), np.uint16))
    elif change == "missing-labels":
        del changed_images["labels"]
    else:
        changed_images["ch0"] = b"invalid TIFF, never decoded for this already accepted key"
    response = upload(client, wid, changed_spec, changed_images)
    assert response.status_code == 409
    assert response.json() == {"detail": "region_upload_id_conflict"}
    assert_single_upload(store, wid, first.json(), images)
    assert store.one(fields, id=first.json()["id"])["metadata"]["condition"] == "control"


@pytest.mark.parametrize("different", [False, True])
def test_simultaneous_requests_commit_one_field_and_one_quota_charge(tmp_path, monkeypatch, different):
    client, store, wid = setup_upload(tmp_path, max_fields=1)
    spec, images = upload_input()
    second_spec = deepcopy(spec)
    if different:
        second_spec["metadata"]["condition"] = "other"
    rendezvous = []
    barrier = Barrier(2, action=lambda: rendezvous.append(True))
    original = region_api.read_tiff

    def synchronized_decode(path, **kwargs):
        barrier.wait(timeout=15)  # Both passed the pre-decode lookup with no committed field.
        return original(path, **kwargs)

    monkeypatch.setattr(region_api, "read_tiff", synchronized_decode)
    # Start both ASGI portals before synchronizing requests. Cold portal startup
    # is not part of the upload race and must not consume its barrier deadline.
    with client, TestClient(client.app) as other:
        other.cookies.update(client.cookies)
        with ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(upload, client, wid, spec, images)
            b = pool.submit(upload, other, wid, second_spec, images)
            responses = [a.result(timeout=30), b.result(timeout=30)]
    diagnostics = [(response.status_code, response.json().get("detail")) for response in responses]
    assert not barrier.broken, ("Concurrent upload requests did not reach the decode barrier", diagnostics)
    assert rendezvous == [True], "Both requests must overlap at exactly one decode boundary"
    statuses = sorted(response.status_code for response in responses)
    assert statuses == ([201, 409] if different else [201, 201]), diagnostics
    successful = [response.json() for response in responses if response.status_code == 201]
    assert all(value == successful[0] for value in successful)
    if different:
        assert next(response for response in responses if response.status_code == 409).json() == {
            "detail": "region_upload_id_conflict"}
    assert_single_upload(store, wid, successful[0], images)


def test_key_is_workspace_scoped_and_omitted_keys_keep_legacy_behavior(tmp_path):
    client, store, wid = setup_upload(tmp_path)
    spec, images = upload_input()
    second_wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Other"}).json()["id"]
    first = upload(client, wid, spec, images)
    second = upload(client, second_wid, spec, images)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert_single_upload(store, wid, first.json(), images)
    assert_single_upload(store, second_wid, second.json(), images)
    del spec["client_upload_id"]
    a, b = upload(client, wid, spec, images), upload(client, wid, spec, images)
    assert a.status_code == b.status_code == 201
    assert a.json()["id"] != b.json()["id"]
    for response in (a, b):
        row = store.one(fields, id=response.json()["id"])
        assert row["client_upload_id"] is row["upload_fingerprint"] is None
    assert store.one(workspaces, id=wid)["bytes"] == 3 * sum(map(len, images.values()))


def test_owner_expiry_revocation_and_csrf_precede_resend_lookup(tmp_path):
    client, store, wid = setup_upload(tmp_path)
    spec, images = upload_input()
    first = upload(client, wid, spec, images)
    assert first.status_code == 201
    other = TestClient(client.app)
    assert other.post("/v1/invitations/redeem", headers=HEADERS,
                      json={"token": store.invite()}).status_code == 200
    assert upload(other, wid, spec, images).status_code == 404
    assert upload(TestClient(client.app), wid, spec, images).status_code == 401
    assert client.post(f"/v1/workspaces/{wid}/region-fields", data={"specification": json.dumps(spec)},
                       files={"ch0": ("fixture.tif", images["ch0"], "image/tiff")}).status_code == 403
    with store.transaction() as conn:
        conn.execute(update(workspaces).where(workspaces.c.id == wid).values(expires=time.time() - 1))
    assert upload(client, wid, spec, images).status_code == 404
    assert_single_upload(store, wid, first.json(), images)
    with store.transaction() as conn:
        conn.execute(update(workspaces).where(workspaces.c.id == wid).values(expires=time.time() + 100))
        token = client.cookies.get("cytellect_dev")
        conn.execute(update(sessions).where(sessions.c.digest == digest(token)).values(revoked=True))
    assert upload(client, wid, spec, images).status_code == 401
    assert_single_upload(store, wid, first.json(), images)


def test_expiry_during_upload_rejects_before_key_resolution_and_cleans_temporary_folder(tmp_path, monkeypatch):
    client, store, wid = setup_upload(tmp_path)
    spec, images = upload_input()
    first = upload(client, wid, spec, images)
    assert first.status_code == 201
    original = region_api.sha256

    def expire_after_transfer(path):
        if path.name == "ch0.tif":
            with store.transaction() as conn:
                conn.execute(update(workspaces).where(workspaces.c.id == wid).values(expires=time.time() - 1))
        return original(path)

    monkeypatch.setattr(region_api, "sha256", expire_after_transfer)
    result = upload(client, wid, spec, images)
    assert result.status_code == 404
    assert_single_upload(store, wid, first.json(), images)


def test_failed_upload_leaves_key_available_and_no_files_or_quota(tmp_path):
    client, store, wid = setup_upload(tmp_path)
    spec, images = upload_input()
    failed = upload(client, wid, spec, {**images, "ch0": b"broken"})
    assert failed.status_code == 422
    assert store.rows(fields, workspace_id=wid) == []
    assert store.one(workspaces, id=wid)["bytes"] == 0
    assert list(store.safe_path("workspaces", wid, "fields").iterdir()) == []
    first = upload(client, wid, spec, images)
    assert first.status_code == 201, first.text
    assert_single_upload(store, wid, first.json(), images)


@pytest.mark.parametrize("with_key", [False, True])
def test_new_upload_over_byte_quota_is_rejected_and_cleaned_after_transfer(tmp_path, with_key):
    client, store, wid = setup_upload(tmp_path, max_upload_bytes=100)
    spec, images = upload_input()
    if not with_key:
        del spec["client_upload_id"]
    result = upload(client, wid, spec, images)
    assert result.status_code == 413 and result.json() == {"detail": "workspace_limit"}
    assert store.rows(fields, workspace_id=wid) == []
    assert store.one(workspaces, id=wid)["bytes"] == 0
    assert list(store.safe_path("workspaces", wid, "fields").iterdir()) == []


def test_generic_retry_guard_keeps_stream_cap_and_closes_spools_even_at_quota(monkeypatch):
    import starlette.formparsers as parsers

    opened = []
    original = parsers.SpooledTemporaryFile

    def track(*args, **kwargs):
        file = original(*args, **kwargs)
        opened.append(file)
        return file

    monkeypatch.setattr(parsers, "SpooledTemporaryFile", track)

    async def parse(scope, receive, send):
        async with Request(scope, receive).form():
            await JSONResponse({"parsed": True})(scope, receive, send)

    store = AuthStore()
    configuration = settings()
    store.workspace["bytes"] = configuration.max_upload_bytes
    guard = UploadGuardMiddleware(parse, store, configuration, field_body_limit=1000)
    prefix = b'--BOUNDARY\r\nContent-Disposition: form-data; name="ch0"; filename="fixture.tif"\r\n\r\n'
    messages, reads = asyncio.run(invoke(guard, context(route="region-fields"),
                                        [(prefix, True), (b"x" * 1200, True)]))
    assert status(messages) == 413 and reads == 2
    assert opened and all(file.closed for file in opened)
    assert guard.active == 0


@pytest.mark.parametrize("legacy", [False, True])
def test_migration_preserves_rows_and_adds_scoped_unique_identity(tmp_path, legacy):
    original_workspaces = []
    original_fields = []
    if legacy:
        engine = create_engine("sqlite:///" + (tmp_path / "cytellect.sqlite").as_posix())
        migration = Config()
        migration.set_main_option("script_location", str(Path(region_api.__file__).parent / "migrations"))
        with engine.begin() as conn:
            migration.attributes["connection"] = conn
            command.upgrade(migration, "0001")
            conn.exec_driver_sql("INSERT INTO workspaces VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                                 ("existing", "owner", "Original", 1.0, 100.0, 0, "revision", 2048))
            for fid in ("old-a", "old-b"):
                conn.exec_driver_sql("INSERT INTO fields VALUES (?, ?, ?, ?, ?)",
                                     (fid, "existing", '{"condition":"kept"}', '{"original":true}', 0))
            original_workspaces = list(conn.exec_driver_sql("SELECT * FROM workspaces").mappings())
            original_fields = list(conn.exec_driver_sql("SELECT * FROM fields ORDER BY id").mappings())
        engine.dispose()
    store = Store(tmp_path)
    # Reopening performs no destructive rewrite or double migration.
    reopened = Store(tmp_path)
    with reopened.engine.connect() as conn:
        assert conn.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one() == "0009"
        schema = inspect(conn)
        columns = {column["name"]: column for column in schema.get_columns("fields")}
        assert columns["client_upload_id"]["nullable"] and columns["upload_fingerprint"]["nullable"]
        assert next(column for column in schema.get_columns("workspaces") if column["name"] == "analysis_plan")["nullable"]
        index = next(index for index in schema.get_indexes("fields") if index["name"] == "uq_fields_workspace_client_upload_id")
        assert index["unique"] and index["column_names"] == ["workspace_id", "client_upload_id"]
        # Adding durable proposal storage must not rewrite the original upload
        # rows or populate research drafts on either a fresh or upgraded store.
        assert conn.exec_driver_sql("SELECT count(*) FROM proposal_drafts").scalar_one() == 0
        proposal_index = next(index for index in schema.get_indexes("proposal_drafts")
                              if index["name"] == "uq_proposal_workspace_key")
        assert proposal_index["unique"] and proposal_index["column_names"] == ["workspace_id", "cache_key"]
        if legacy:
            after_workspaces = list(conn.exec_driver_sql("SELECT * FROM workspaces").mappings())
            after_fields = list(conn.exec_driver_sql("SELECT * FROM fields ORDER BY id").mappings())
            for before, after in zip(original_workspaces, after_workspaces, strict=True):
                assert {key: after[key] for key in before} == dict(before)
                assert after["analysis_plan"] is None
            for before, after in zip(original_fields, after_fields, strict=True):
                assert {key: after[key] for key in before} == dict(before)
                assert after["client_upload_id"] is after["upload_fingerprint"] is None
    key = str(uuid4())
    with store.transaction() as conn:
        for fid, wid, upload_id in [("new-a", "w1", key), ("new-b", "w2", key),
                                    ("no-key-a", "w1", None), ("no-key-b", "w1", None)]:
            conn.execute(fields.insert().values(id=fid, workspace_id=wid, metadata={}, image_info={},
                                                synthetic=False, client_upload_id=upload_id))
    with pytest.raises(IntegrityError), store.transaction() as conn:
        conn.execute(fields.insert().values(id="conflict", workspace_id="w1", metadata={}, image_info={},
                                            synthetic=False, client_upload_id=key))
    assert store.one(fields, id="conflict") is None
    with store.engine.connect() as conn:
        assert len(conn.execute(select(fields).where(fields.c.workspace_id == "w1")).all()) == 3
    store.engine.dispose()
    reopened.engine.dispose()


def test_new_key_same_images_but_changed_metadata_is_a_distinct_field(tmp_path):
    client, store, wid = setup_upload(tmp_path)
    spec, images = upload_input()
    first = upload(client, wid, spec, images)
    changed = {**spec, "client_upload_id": str(uuid4()), "metadata": {"condition": "treated"}}
    second = upload(client, wid, changed, images)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert len(store.rows(fields, workspace_id=wid)) == 2
    assert store.one(workspaces, id=wid)["bytes"] == 2 * sum(map(len, images.values()))


def test_different_client_keys_with_identical_uploads_are_separate_fields(tmp_path, monkeypatch):
    # Owner policy 2026-10-06: identical bytes under different client keys are
    # kept as two fields; the browser warns and the researcher decides.
    client, store, wid = setup_upload(tmp_path, max_fields=2)
    spec, images = upload_input()
    second_spec = {**spec, "client_upload_id": str(uuid4())}
    first = upload(client, wid, spec, images)
    second = upload(client, wid, second_spec, images)
    assert first.status_code == second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert first.json()["image_info"]["inputs"] == second.json()["image_info"]["inputs"]
    assert len(store.rows(fields, workspace_id=wid)) == 2
    # The same key still resolves idempotently.
    again = upload(client, wid, spec, images)
    assert again.json()["id"] == first.json()["id"]
    assert len(store.rows(fields, workspace_id=wid)) == 2


def test_detector_role_evidence_change_does_not_duplicate_field_or_rewrite_provenance(tmp_path):
    spec, images = upload_input()
    spec["version"] = "1.1.0"
    del spec["channels"][0]["identity_confirmed"]
    spec["channels"][0]["identity_source"] = "filename"
    client, store, wid = setup_upload(tmp_path, max_fields=1)
    first = upload(client, wid, spec, images)
    assert first.status_code == 201, first.text
    changed = deepcopy(spec)
    changed["client_upload_id"] = str(uuid4())
    changed["channels"][0]["identity_source"] = "user_entered"
    recovered = upload(client, wid, changed, images)
    assert recovered.status_code == 201, recovered.text
    assert recovered.json() == first.json()
    assert recovered.json()["image_info"]["channels"][0]["identity_source"] == "filename"
    assert_single_upload(store, wid, first.json(), images)
    # Existing key conflicts must still win over normalized content recovery.
    changed["client_upload_id"] = spec["client_upload_id"]
    assert upload(client, wid, changed, images).status_code == 409

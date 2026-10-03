"""Upload commits cannot create a mixed legacy/generic workspace, including races."""

import contextlib
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest
from cytellect_api.db import fields, workspaces
from cytellect_api.regions import is_region
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_api import make_field, tiff_bytes


def submit(client, wid, kind):
    if kind == "region":
        return make_field(client, wid)
    if kind == "synthetic":
        return client.post(f"/v1/workspaces/{wid}/synthetic", headers=HEADERS)
    pixels = tiff_bytes(np.full((12, 12), 10, np.uint16))
    return client.post(f"/v1/workspaces/{wid}/fields", headers=HEADERS,
                       data={"metadata": json.dumps({"condition": "control", "experimental_unit": "unit",
                                                    "sample": "sample", "acquisition_date": "date"})},
                       files={role: ("image.tif", pixels, "image/tiff") for role in ("dapi", "gfp")})


def assert_disk_and_accounting_match(store, wid):
    stored = store.rows(fields, workspace_id=wid)
    assert {p.name for p in store.safe_path("workspaces", wid, "fields").iterdir()} == {f["id"] for f in stored}
    assert store.one(workspaces, id=wid)["bytes"] == sum(
        source["bytes"] for field in stored for source in field["image_info"]["inputs"].values()
    )


@pytest.mark.parametrize("first,second", [
    ("legacy", "region"), ("synthetic", "region"), ("region", "legacy"), ("region", "synthetic"),
])
def test_mixed_workflow_upload_is_rejected_without_mutating_existing_work(tmp_path, first, second):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "workflow"}).json()["id"]
    assert submit(client, wid, first).status_code == 201
    before = dict(app.state.store.one(workspaces, id=wid))
    ids = {f["id"] for f in app.state.store.rows(fields, workspace_id=wid)}
    rejected = submit(client, wid, second)
    assert rejected.status_code == 409
    assert rejected.json()["detail"] == "workflow_kind_mismatch"
    assert dict(app.state.store.one(workspaces, id=wid)) == before
    assert {f["id"] for f in app.state.store.rows(fields, workspace_id=wid)} == ids
    assert_disk_and_accounting_match(app.state.store, wid)
    # Rejection does not poison the workspace or prevent another valid image.
    assert submit(client, wid, first).status_code == 201
    assert_disk_and_accounting_match(app.state.store, wid)


@pytest.mark.parametrize("nuclear_kind", ["legacy", "synthetic"])
def test_concurrent_first_uploads_commit_exactly_one_workflow(tmp_path, monkeypatch, nuclear_kind):
    client, app, _ = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "race"}).json()["id"]
    # Both HTTP requests finish their preflight and reach the commit boundary while
    # the workspace is empty. BEGIN IMMEDIATE must serialize the identity decision.
    rendezvous = []
    barrier = threading.Barrier(2, action=lambda: rendezvous.append(True), timeout=10)
    original_transaction = app.state.store.transaction

    @contextlib.contextmanager
    def synchronized_transaction():
        barrier.wait()
        with original_transaction() as connection:
            yield connection

    monkeypatch.setattr(app.state.store, "transaction", synchronized_transaction)
    # Start the independent ASGI portals before measuring the commit race.
    with TestClient(app) as region_client, TestClient(app) as nuclear_client:
        region_client.cookies.update(client.cookies)
        nuclear_client.cookies.update(client.cookies)
        with ThreadPoolExecutor(max_workers=2) as executor:
            region = executor.submit(submit, region_client, wid, "region")
            nuclear = executor.submit(submit, nuclear_client, wid, nuclear_kind)
            responses = [region.result(timeout=20), nuclear.result(timeout=20)]
    diagnostics = [(response.status_code, response.json().get("detail")) for response in responses]
    assert not barrier.broken, ("Concurrent uploads did not reach the transaction barrier", diagnostics)
    assert rendezvous == [True], "Both requests must overlap at exactly one commit boundary"
    assert sorted(response.status_code for response in responses) == [201, 409], diagnostics
    assert next(response for response in responses if response.status_code == 409).json()["detail"] == "workflow_kind_mismatch"
    stored = app.state.store.rows(fields, workspace_id=wid)
    assert len({is_region(field) for field in stored}) == 1
    assert len(stored) == (6 if responses[1].status_code == 201 and nuclear_kind == "synthetic" else 1)
    assert_disk_and_accounting_match(app.state.store, wid)

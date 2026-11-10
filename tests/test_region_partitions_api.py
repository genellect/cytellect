"""Synthetic arithmetic/source-binding tests, not detector or biological acceptance.

The tiny numeric/label arrays have hand-checkable joins and failure cases. Saved
source records stand in for saved detector/manual outputs; no cell images or
biological ground truth are generated. Real-image pipeline acceptance is separate.
"""
import copy
import csv
import io
import json
import time

import numpy as np
import pytest
import tifffile
from cytellect_analysis.images import sha256
from cytellect_analysis.region_contracts import (
    RegionImageInfo,
    RegionNuclearRecipe,
    RegionRecipe,
    scientific_specification,
)
from cytellect_analysis.region_measurement_v2 import measure_regions_versioned
from cytellect_analysis.region_partition_table import RegionPartitionTable, partition_table_csv
from cytellect_analysis.region_policy import AutomaticBackgroundPolicy, RawIntensityPolicy
from cytellect_analysis.regions import (
    BackgroundSpec,
    RegionMeasurementSpec,
    RegionSetSpec,
    _array_hash,
    measure_regions,
)
from cytellect_api.db import Store, fields, revisions, workspace_selections, workspaces
from cytellect_api.region_partitions import register_region_partition_routes
from cytellect_api.storage import read_json, write_json
from fastapi import FastAPI, HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy import update

PARAMS = {"field_id": "f", "target_revision_id": "target", "reference_revision_id": "reference", "channel_id": "dna"}
JSON_ROUTE = "/v1/revisions/nuclear/region-partition"
CSV_ROUTE = JSON_ROUTE + ".csv"


def _record(path):
    return {"sha256": sha256(path), "bytes": path.stat().st_size}


@pytest.fixture
def partition_api(tmp_path):
    store = Store(tmp_path / "data")
    now = time.time()
    with store.transaction() as conn:
        conn.execute(workspaces.insert().values(id="w", owner="owner", title="arithmetic", created=now,
                                                expires=now + 3600, deleted=False, bytes=0))
    pixel = np.array([[2, 2, 2, 2], [10, 6, 20, 4], [8, 4, 16, 2]], dtype=np.uint16)
    labels = {
        "nuclear": np.array([[0, 0, 0, 0], [7, 7, 19, 19], [7, 7, 19, 19]], dtype=np.uint32),
        "target": np.array([[0, 0, 0, 0], [91, 0, 92, 0], [91, 0, 92, 0]], dtype=np.uint32),
        "reference": np.array([[0, 0, 0, 0], [0, 31, 0, 32], [0, 31, 0, 32]], dtype=np.uint32),
    }
    folder = store.safe_path("workspaces", "w", "fields", "f")
    folder.mkdir(parents=True)
    tifffile.imwrite(folder / "ch0.tif", pixel, photometric="minisblack")
    np.save(folder / "channel-dna.npy", pixel, allow_pickle=False)
    info = RegionImageInfo.model_validate({
        "shape": [3, 4], "channels": [{"channel_id": "dna", "label": "Measured channel", "stain": "DAPI", "identity_confirmed": True}],
        "inputs": {"ch0": _record(folder / "ch0.tif")}, "channel_arrays": {"dna": _record(folder / "channel-dna.npy")},
        "calibration": {"pixel_size_x_um": 0.2, "pixel_size_y_um": 0.5, "confirmed": True},
    })
    field = {"id": "f", "workspace_id": "w", "metadata": {}, "image_info": info.model_dump(mode="json"), "synthetic": True}
    with store.transaction() as conn:
        conn.execute(fields.insert().values(**field))
    roi = {"polygon": [[0, 0], [4, 0], [4, 1], [0, 1]], "confirmed": True}
    background = np.zeros(pixel.shape, dtype=bool)
    background[0] = True
    for rid, array in labels.items():
        recipe = (RegionNuclearRecipe(region_set_id="nuclei", label="Nuclei", defining_channel_id="dna", nuclear_stain_confirmed=True)
                  if rid == "nuclear" else RegionRecipe(region_set_id=rid, label=rid.title(), source="manual"))
        specification = RegionMeasurementSpec(
            field_id="f", analysis_revision_id=rid,
            region_set=RegionSetSpec(region_set_id=recipe.region_set_id, label=recipe.label, mask_revision_id=rid,
                                     source=recipe.source, defining_channel_id=recipe.defining_channel_id),
            channels=tuple(info.channels), backgrounds=(BackgroundSpec(channel_id="dna", roi_revision_id=rid, confirmed=True),),
            calibration=info.calibration,
        )
        table = measure_regions({"dna": pixel}, array, {"dna": background}, specification)
        root = store.safe_path("results", rid)
        (root / "f").mkdir(parents=True)
        np.save(root / "f" / "labels.npy", array, allow_pickle=False)
        np.save(root / "f" / "background-dna.npy", background, allow_pickle=False)
        config = {"analysis_kind": "region-2d", "recipe": recipe.model_dump(mode="json"),
                  "field_ids": ["f"], "field_snapshot": {"f": copy.deepcopy(field)}, "backgrounds": {"f": {"dna": roi}}, "exclusions": []}
        with store.transaction() as conn:
            conn.execute(revisions.insert().values(id=rid, workspace_id="w", config=config, state="succeeded", reviewed=True,
                                                  created=now, result_dir=f"results/{rid}"))
        write_json(root / "measurements.json", {
            "analysis_kind": "region-2d", "protocol_version": "1.0.0", "revision_id": rid,
            "recipe": config["recipe"], "field_tables": {"f": table.model_dump(mode="json")},
            "field_masks": {"f": {"mask_revision_id": rid, "mask_sha256": _array_hash(array, "<u4"),
                                      "region_set_id": recipe.region_set_id, "source": recipe.source,
                                      "shape": [3, 4], "file": _record(root / "f" / "labels.npy")}},
            "field_outcomes": {"f": "measured"}, "field_failures": [], "excluded_failed_fields": [], "exclusions": [],
        })
        write_json(root / "provenance.json", {"analysis_kind": "region-2d", "revision_id": rid, "recipe": config["recipe"],
                                              "fields": {"f": {"inputs": config["field_snapshot"]["f"]["image_info"]["inputs"]}}})
    api = FastAPI()

    def owner(request: Request):
        who = request.headers.get("x-test-owner")
        if who is None:
            raise HTTPException(401, "session_required")
        return who

    def owned_workspace(wid, who):
        value = store.one(workspaces, id=wid)
        if not value or value["owner"] != who:
            raise HTTPException(404, "workspace_not_found")

    def revision(rid, who):
        value = store.one(revisions, id=rid)
        if not value:
            raise HTTPException(404, "revision_not_found")
        owned_workspace(value["workspace_id"], who)
        return value

    def field_record(fid, who):
        value = store.one(fields, id=fid)
        if not value:
            raise HTTPException(404, "field_not_found")
        owned_workspace(value["workspace_id"], who)
        return value

    register_region_partition_routes(api, store, owner, revision, lambda rev: store.safe_path(rev["result_dir"]), field_record)
    return TestClient(api, headers={"x-test-owner": "owner"}), store, labels


def _edit_source(store, rid, *, config_edit=None, report_edit=None, provenance_edit=None):
    rev = store.one(revisions, id=rid)
    config = copy.deepcopy(rev["config"])
    if config_edit:
        config_edit(config)
        with store.transaction() as conn:
            conn.execute(update(revisions).where(revisions.c.id == rid).values(config=config))
    for filename, edit in (("measurements.json", report_edit), ("provenance.json", provenance_edit)):
        if edit:
            path = store.safe_path(rev["result_dir"], filename)
            value = read_json(path)
            edit(value)
            write_json(path, value)


def test_synthetic_readonly_table_and_csv_share_values_provenance_and_units(partition_api):
    client, store, _ = partition_api
    before = {path: sha256(path) for path in store.root.rglob("*") if path.is_file() and path.suffix in (".json", ".npy", ".tif")}
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    table = response.json()
    assert table["protocol"] == "region-partition-table/1.0.0"
    assert table["review_status"] == "reviewed"
    assert all(table[f"{role}_source"]["reviewed"] is True for role in ("nuclear", "target", "reference"))
    # Ambiguous legacy selection has no adopted source; review never invents adoption.
    assert all(table[f"{role}_source"]["adopted"] is False for role in ("nuclear", "target", "reference"))
    first, second = table["rows"]
    assert (first["nucleus_id"], second["nucleus_id"]) == (7, 19)
    assert first["target"]["raw_mean"] == 9 and first["reference"]["raw_mean"] == 5
    assert first["raw"]["k"] == pytest.approx(9 / 5)
    assert first["corrected"]["k"] == pytest.approx(7 / 3)
    assert second["corrected"]["k"] == 16
    assert first["target"]["area_um2"] == pytest.approx(0.2)
    assert table["background"]["median"] == 2 and table["background"]["status"] == "confirmed"
    assert table["pixel_source"]["channel"]["stain"] == "DAPI"
    assert len(table["nuclear_source"]["label_file"]["sha256"]) == 64
    assert str(store.root) not in response.text
    exported = client.get(CSV_ROUTE, params=PARAMS)
    assert exported.status_code == 200
    assert exported.content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    assert float(rows[0]["raw_k"]) == first["raw"]["k"]
    assert float(rows[0]["target_corrected_integrated"]) == first["target"]["corrected_integrated"]
    assert json.loads(rows[0]["provenance_json"])["pixel_source"] == table["pixel_source"]
    assert rows[0]["methods"] == table["methods"]
    assert {path: sha256(path) for path in before} == before


@pytest.mark.parametrize("route", [JSON_ROUTE, CSV_ROUTE])
@pytest.mark.parametrize("unreviewed", ["nuclear", "target", "reference"])
def test_synthetic_owner_guard_and_actual_preview_review_flags_apply_to_both_formats(partition_api, route, unreviewed):
    client, store, _ = partition_api
    assert client.get(route, params=PARAMS, headers={"x-test-owner": "other"}).status_code == 404
    with store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == unreviewed).values(reviewed=False))
    response = client.get(route, params=PARAMS)
    assert response.status_code == 200, response.text
    if route == JSON_ROUTE:
        data = response.json()
        assert data["rows"][0]["raw"]["k"] == pytest.approx(9 / 5)
    else:
        exported = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
        data = json.loads(exported[0]["provenance_json"])
        assert exported[0]["review_status"] == "preview"
        assert exported[0][f"{unreviewed}_reviewed"] == "False"
        assert exported[0]["nuclear_adopted"] == "False"
    assert data["review_status"] == "preview"
    assert "Source review status: preview" in data["methods"]
    for role in ("nuclear", "target", "reference"):
        assert data[f"{role}_source"]["reviewed"] is (role != unreviewed)
        assert data[f"{role}_source"]["adopted"] is False
    assert store.one(revisions, id=unreviewed)["reviewed"] is False


def test_synthetic_unreviewed_sources_still_require_frozen_mask_integrity(partition_api):
    client, store, _ = partition_api
    with store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == "nuclear").values(reviewed=False))
    path = store.safe_path("results", "target", "f", "labels.npy")
    path.write_bytes(path.read_bytes() + b"x")
    for route in (JSON_ROUTE, CSV_ROUTE):
        response = client.get(route, params=PARAMS)
        assert response.status_code == 409 and response.json()["detail"] == "partition_source_file_size_mismatch"


def test_synthetic_preview_status_cannot_claim_all_sources_reviewed(partition_api):
    client, _, _ = partition_api
    data = client.get(JSON_ROUTE, params=PARAMS).json()
    data["nuclear_source"]["reviewed"] = False
    with pytest.raises(ValueError, match="partition_review_status_mismatch"):
        RegionPartitionTable.model_validate_json(json.dumps(data))


def test_synthetic_unauthenticated_request_is_refused(partition_api):
    client, _, _ = partition_api
    del client.headers["x-test-owner"]
    assert client.get(JSON_ROUTE, params=PARAMS).status_code == 401
    assert client.get(CSV_ROUTE, params=PARAMS).status_code == 401


def test_synthetic_result_path_escape_is_refused_without_leaking_path(partition_api):
    client, store, _ = partition_api
    with store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == "target").values(result_dir="../outside"))
    for route in (JSON_ROUTE, CSV_ROUTE):
        response = client.get(route, params=PARAMS)
        assert response.status_code == 409 and response.json()["detail"] == "partition_source_invalid"
        assert "outside" not in response.text and str(store.root) not in response.text


def test_synthetic_empty_csv_keeps_provenance_without_fabricated_zero_nucleus(partition_api):
    client, _, _ = partition_api
    data = client.get(JSON_ROUTE, params=PARAMS).json()
    data["rows"] = []
    table = RegionPartitionTable.model_validate_json(json.dumps(data))
    rows = list(csv.DictReader(io.StringIO(partition_table_csv(table).decode("utf-8-sig"))))
    assert len(rows) == 1 and rows[0]["record_type"] == "report"
    assert rows[0]["nucleus_id"] == "" and rows[0]["raw_k"] == ""
    assert json.loads(rows[0]["provenance_json"])["nuclear_source"] == data["nuclear_source"]


@pytest.mark.parametrize("state", ["queued", "running", "failed"])
def test_synthetic_unsucceeded_source_is_rejected(partition_api, state):
    client, store, _ = partition_api
    with store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == "reference").values(state=state))
    assert client.get(JSON_ROUTE, params=PARAMS).json()["detail"] == "partition_source_not_succeeded"


@pytest.mark.parametrize("which", ["snapshot", "current"])
def test_synthetic_original_pixel_identity_mismatch_is_rejected(partition_api, which):
    client, store, _ = partition_api
    if which == "snapshot":
        _edit_source(store, "target", config_edit=lambda value: value["field_snapshot"]["f"]["image_info"]["channel_arrays"]["dna"].update(sha256="0" * 64))
    else:
        field = store.one(fields, id="f")
        info = copy.deepcopy(field["image_info"])
        info["channel_arrays"]["dna"]["sha256"] = "0" * 64
        with store.transaction() as conn:
            conn.execute(update(fields).where(fields.c.id == "f").values(image_info=info))
    assert client.get(JSON_ROUTE, params=PARAMS).status_code == 409


@pytest.mark.parametrize("artifact", ["mask_bytes", "mask_shape", "mask_dtype", "pixels", "original", "background"])
def test_synthetic_file_hash_shape_dtype_and_background_guards(partition_api, artifact):
    client, store, _ = partition_api
    if artifact.startswith("mask"):
        path = store.safe_path("results", "target", "f", "labels.npy")
        if artifact == "mask_bytes":
            path.write_bytes(path.read_bytes() + b"x")
        else:
            value = np.load(path)
            np.save(path, value[:, :-1] if artifact == "mask_shape" else value.astype(float), allow_pickle=False)
            _edit_source(store, "target", report_edit=lambda report: report["field_masks"]["f"].update(file=_record(path)))
    elif artifact == "pixels":
        path = store.safe_path("workspaces", "w", "fields", "f", "channel-dna.npy")
        value = np.load(path)
        value[1, 0] += 1
        np.save(path, value, allow_pickle=False)
    elif artifact == "original":
        path = store.safe_path("workspaces", "w", "fields", "f", "ch0.tif")
        path.write_bytes(path.read_bytes() + b"x")
    else:
        path = store.safe_path("results", "nuclear", "f", "background-dna.npy")
        value = np.load(path)
        value[1, 0] = True
        np.save(path, value, allow_pickle=False)
    assert client.get(JSON_ROUTE, params=PARAMS).status_code == 409
    assert client.get(CSV_ROUTE, params=PARAMS).status_code == 409


def test_synthetic_source_symlink_is_rejected_even_inside_storage(partition_api):
    client, store, _ = partition_api
    original = store.safe_path("results", "target", "f", "labels.npy")
    moved = original.with_name("copied.npy")
    original.rename(moved)
    original.symlink_to(moved)
    assert client.get(JSON_ROUTE, params=PARAMS).json()["detail"] == "partition_source_link_forbidden"


def test_synthetic_exclusions_preserve_parent_and_object_reasons(partition_api):
    client, store, _ = partition_api
    for rid, region in (("target", 91), ("nuclear", 19)):
        exclusions = [{"field_id": "f", "region_id": region, "reason": "reviewed exclusion"}]
        _edit_source(store, rid, config_edit=lambda value: value.update(exclusions=exclusions),
                     report_edit=lambda value: value.update(exclusions=exclusions))
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    first, second = response.json()["rows"]
    assert first["nucleus_id"] == 7 and first["excluded"] is False
    assert first["target"]["area_px"] is None and first["raw"]["missing_reasons"] == ["empty_target"]
    assert first["exclusions"] == [{"source": "target", "region_id": 91, "reason": "reviewed exclusion"}]
    assert second["nucleus_id"] == 19 and second["excluded"] is True
    assert second["target"]["raw_mean"] is None and second["raw"]["missing_reasons"] == ["source_excluded"]


@pytest.mark.parametrize("source", ["nuclear", "target", "reference"])
def test_synthetic_whole_field_exclusion_retains_all_parents(partition_api, source):
    client, store, _ = partition_api
    exclusions = [{"field_id": "f", "region_id": None, "reason": "field decision"}]
    _edit_source(store, source, config_edit=lambda value: value.update(exclusions=exclusions),
                 report_edit=lambda value: value.update(exclusions=exclusions))
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    assert [row["nucleus_id"] for row in response.json()["rows"]] == [7, 19]
    for row in response.json()["rows"]:
        assert row["excluded"] is True
        assert row["target"]["area_px"] is None and row["reference"]["raw_mean"] is None
        assert row["raw"]["missing_reasons"] == ["source_excluded"]
        assert row["exclusions"][0]["reason"] == "field decision"


def test_synthetic_nuclear_source_semantics_cannot_be_relabelled_cells(partition_api):
    client, store, _ = partition_api
    recipe = RegionRecipe(region_set_id="cell", label="Cells", source="manual").model_dump(mode="json")
    def edit_report(value):
        value["recipe"] = recipe
        value["field_masks"]["f"].update(source="manual", region_set_id="cell")
        table = value["field_tables"]["f"]
        table["region_set"].update(source="manual", defining_channel_id=None, region_set_id="cell", label="Cells")
        for row in table["rows"]:
            row["region_set_id"] = "cell"
    _edit_source(store, "nuclear", config_edit=lambda value: value.update(recipe=recipe), report_edit=edit_report,
                 provenance_edit=lambda value: value.update(recipe=recipe))
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 409 and response.json()["detail"] == "partition_nuclear_source_required"


def test_synthetic_cross_workspace_sources_are_refused(partition_api):
    client, store, _ = partition_api
    with store.transaction() as conn:
        conn.execute(workspaces.insert().values(id="other", owner="owner", title="other", created=time.time(),
                                                expires=time.time() + 3600, deleted=False, bytes=0))
        conn.execute(update(revisions).where(revisions.c.id == "reference").values(workspace_id="other"))
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 409 and response.json()["detail"] == "partition_workspace_mismatch"


def test_synthetic_display_rgb_cannot_supply_native_partition_intensity(partition_api):
    client, store, _ = partition_api
    current = copy.deepcopy(store.one(fields, id="f")["image_info"])
    current["input_mode"] = "display-rgb"
    with store.transaction() as conn:
        conn.execute(update(fields).where(fields.c.id == "f").values(image_info=current))
    for rid in ("nuclear", "target", "reference"):
        _edit_source(store, rid, config_edit=lambda value: value["field_snapshot"]["f"].update(image_info=current))
    assert client.get(JSON_ROUTE, params=PARAMS).status_code == 409


def test_synthetic_selected_memberships_cannot_overlap(partition_api):
    client, store, labels = partition_api
    path = store.safe_path("results", "reference", "f", "labels.npy")
    overlapping = np.where(labels["target"] == 91, 31, np.where(labels["target"] == 92, 32, 0)).astype(np.uint32)
    np.save(path, overlapping, allow_pickle=False)
    digest = _array_hash(overlapping, "<u4")
    def edit_report(value):
        value["field_masks"]["f"].update(file=_record(path), mask_sha256=digest)
        value["field_tables"]["f"]["mask_sha256"] = digest
    _edit_source(store, "reference", report_edit=edit_report)
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 409 and response.json()["detail"] == "partition_memberships_overlap"


def test_synthetic_manual_membership_label_can_span_exact_parents_without_order_matching(partition_api):
    client, store, labels = partition_api
    path = store.safe_path("results", "target", "f", "labels.npy")
    shared = (labels["target"] > 0).astype(np.uint32)
    np.save(path, shared, allow_pickle=False)
    digest = _array_hash(shared, "<u4")
    def edit_report(value):
        value["field_masks"]["f"].update(file=_record(path), mask_sha256=digest)
        table = value["field_tables"]["f"]
        table["mask_sha256"] = digest
        combined = table["rows"][0]
        combined.update(region_id=1, area_px=4, area_um2=0.4, mean=13.5, median=13, integrated=54,
                        mean_corrected=11.5, median_corrected=11, integrated_corrected=46)
        table["rows"] = [combined]
    _edit_source(store, "target", report_edit=edit_report)
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    first, second = response.json()["rows"]
    assert first["nucleus_id"] == 7 and first["target"]["raw_mean"] == 9
    assert second["nucleus_id"] == 19 and second["target"]["raw_mean"] == 18
    exclusions = [{"field_id": "f", "region_id": 1, "reason": "shared membership excluded"}]
    _edit_source(store, "target", config_edit=lambda value: value.update(exclusions=exclusions),
                 report_edit=lambda value: value.update(exclusions=exclusions))
    excluded = client.get(JSON_ROUTE, params=PARAMS)
    assert excluded.status_code == 200, excluded.text
    for row in excluded.json()["rows"]:
        assert row["target"]["raw_mean"] is None
        assert row["exclusions"] == [{"source": "target", "region_id": 1, "reason": "shared membership excluded"}]


@pytest.mark.parametrize("policy", [RawIntensityPolicy(version="1.1.0", mode="raw_intensity"),
                                   AutomaticBackgroundPolicy(version="1.2.0", mode="automatic_background")])
def test_synthetic_raw_or_automatic_source_never_supplies_confirmed_roi_background(partition_api, policy):
    client, store, labels = partition_api
    revision = store.one(revisions, id="nuclear")
    info = RegionImageInfo.model_validate(revision["config"]["field_snapshot"]["f"]["image_info"])
    recipe = RegionNuclearRecipe.model_validate(revision["config"]["recipe"])
    specification = scientific_specification(field_id="f", revision_id="nuclear", mask_revision_id="nuclear",
                                             recipe=recipe, image_info=info, measurement=policy)
    pixels = np.load(store.safe_path("workspaces", "w", "fields", "f", "channel-dna.npy"))
    measured = measure_regions_versioned({"dna": pixels}, labels["nuclear"], {}, specification,
                                         background_exclusion=labels["nuclear"] > 0 if policy.mode == "automatic_background" else None)
    def edit_report(value):
        value.update(protocol_version=measured.protocol_version, measurement=policy.model_dump(mode="json"))
        value["field_tables"]["f"] = measured.model_dump(mode="json")
    _edit_source(store, "nuclear", config_edit=lambda value: value.update(measurement=policy.model_dump(mode="json"), backgrounds={}),
                 report_edit=edit_report)
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    table = response.json()
    assert table["background"]["status"] == "missing" and table["background"]["median"] is None
    for row in table["rows"]:
        assert row["raw"]["k"] is not None and row["corrected"]["k"] is None
        assert row["corrected"]["missing_reasons"] == ["background_not_confirmed"]


def _make_target_compartment(store, states):
    nuclear = read_json(store.safe_path("results", "nuclear", "measurements.json"))["field_masks"]["f"]
    target = store.one(revisions, id="target")
    recipe = {"id": "region-2d", "version": "1.4.0", "region_set_id": "target", "label": "Target",
              "source": "fiji_nuclear_compartment", "compartment": "nucleoli", "nuclear_revision_id": "nuclear",
              "nuclear_channel_id": "dna", "defining_channel_id": "dna", "detector": {
                  "engine": "cytellect-nucleolar-v2", "protocol_version": "2.0.0", "source": "dapi_poor",
              }, "nucleolar_revision_id": None}
    # Obtain the canonical versioned defaults rather than inventing a detector contract.
    from cytellect_analysis.region_contracts import RegionCompartmentRecipe
    recipe = RegionCompartmentRecipe.model_validate(recipe).model_dump(mode="json")
    def report_edit(value):
        value["recipe"] = recipe
        value["field_masks"]["f"]["source"] = "fiji_nuclear_compartment"
        value["field_tables"]["f"]["region_set"].update(source="fiji_nuclear_compartment", defining_channel_id="dna")
    def provenance_edit(value):
        value["recipe"] = recipe
        value["fields"]["f"].update(
            nuclear_source={"revision_id": "nuclear", "mask_revision_id": nuclear["mask_revision_id"], "mask_sha256": nuclear["mask_sha256"],
                            "effective_mask_sha256": nuclear["mask_sha256"], "exclusions": []},
            detector={"engine": {"nucleolar_states": states}},
        )
    _edit_source(store, target["id"], config_edit=lambda value: value.update(recipe=recipe), report_edit=report_edit, provenance_edit=provenance_edit)


@pytest.mark.parametrize("state", ["review_required", "indeterminate", "no_candidate", "processing_failed"])
def test_synthetic_unresolved_state_remains_missing_despite_saved_labels(partition_api, state):
    client, store, _ = partition_api
    _make_target_compartment(store, {"7": state, "19": "candidate"})
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    first, second = response.json()["rows"]
    assert first["target_state"] == state
    assert first["target"]["raw_mean"] is None
    assert first["raw"]["missing_reasons"] == [f"target_{state}"]
    assert second["raw"]["k"] == 6


def test_synthetic_compartment_exact_nuclear_binding_is_required(partition_api):
    client, store, _ = partition_api
    _make_target_compartment(store, {"7": "candidate", "19": "candidate"})
    _edit_source(store, "target", provenance_edit=lambda value: value["fields"]["f"]["nuclear_source"].update(mask_sha256="0" * 64))
    assert client.get(JSON_ROUTE, params=PARAMS).json()["detail"] == "partition_compartment_nuclear_binding_mismatch"


def test_synthetic_adoption_is_resolved_from_server_selection_independently_of_review(partition_api):
    client, store, _ = partition_api
    _make_target_compartment(store, {"7": "candidate", "19": "candidate"})
    with store.transaction() as conn:
        conn.execute(workspace_selections.insert().values(workspace_id="w", version=1, entries=[{
            "id": "f", "field_id": "f", "revision_id": "target", "exclusion_reason": None,
            "target_revisions": {"nuclei": "nuclear", "nucleoli": "target"},
        }]))
        conn.execute(update(revisions).where(revisions.c.id.in_(["nuclear", "target"])).values(reviewed=False))
    response = client.get(JSON_ROUTE, params={**PARAMS, "adopted": "false", "reviewed": "true"})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["review_status"] == "preview"
    assert data["nuclear_source"]["adopted"] is True and data["nuclear_source"]["reviewed"] is False
    assert data["target_source"]["adopted"] is True and data["target_source"]["reviewed"] is False
    # The generic manual source is readable, with unknown adoption semantics recorded as false.
    assert data["reference_source"]["adopted"] is False and data["reference_source"]["reviewed"] is True
    assert "nuclear source adopted=true, reviewed=false" in data["methods"]
    exported = client.get(CSV_ROUTE, params=PARAMS)
    assert exported.status_code == 200
    rows = list(csv.DictReader(io.StringIO(exported.content.decode("utf-8-sig"))))
    provenance = json.loads(rows[0]["provenance_json"])
    assert provenance["nuclear_source"] == data["nuclear_source"]
    assert rows[0]["nuclear_adopted"] == "True" and rows[0]["nuclear_reviewed"] == "False"
    # The reads neither review a source nor alter the saved selection.
    assert store.one(revisions, id="nuclear")["reviewed"] is False
    assert store.one(workspace_selections, workspace_id="w")["version"] == 1


def test_synthetic_unlisted_compartment_parent_stays_unclassified_and_missing(partition_api):
    client, store, _ = partition_api
    _make_target_compartment(store, {"19": "candidate"})
    response = client.get(JSON_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    first = response.json()["rows"][0]
    assert first["target_state"] == "unclassified"
    assert first["target"]["area_px"] is None
    assert first["raw"]["missing_reasons"] == ["target_unclassified"]


def test_synthetic_csv_escapes_human_text_and_preserves_signed_numbers(partition_api):
    client, store, _ = partition_api
    # A confirmed background higher than the reference retains a signed correction.
    pixels = store.safe_path("workspaces", "w", "fields", "f", "channel-dna.npy")
    array = np.load(pixels)
    array[0] = 7
    np.save(pixels, array, allow_pickle=False)
    original = pixels.with_name("ch0.tif")
    tifffile.imwrite(original, array, photometric="minisblack")
    current = copy.deepcopy(store.one(fields, id="f")["image_info"])
    current["channel_arrays"]["dna"] = _record(pixels)
    current["inputs"]["ch0"] = _record(original)
    current["channels"][0]["label"] = "=formula"
    with store.transaction() as conn:
        conn.execute(update(fields).where(fields.c.id == "f").values(image_info=current))
    for rid in ("nuclear", "target", "reference"):
        def report_edit(value):
            entry = value["field_tables"]["f"]["channel_provenance"][0]
            entry.update(pixel_sha256=_array_hash(array, "<u2"), background_median=7)
            entry["channel"]["label"] = "=formula"
        _edit_source(store, rid, config_edit=lambda value: value["field_snapshot"]["f"].update(image_info=current),
                     report_edit=report_edit, provenance_edit=lambda value: value["fields"]["f"].update(inputs=current["inputs"]))
    response = client.get(CSV_ROUTE, params=PARAMS)
    assert response.status_code == 200, response.text
    rows = list(csv.DictReader(io.StringIO(response.content.decode("utf-8-sig"))))
    assert rows[0]["channel_label"] == "'=formula"
    assert rows[0]["reference_corrected_mean"] == "-2.0"
    assert rows[0]["reference_corrected_integrated"] == "-4.0"

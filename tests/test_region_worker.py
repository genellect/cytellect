"""Direct scientific worker acceptance; API CAS/ownership have separate tests."""
from __future__ import annotations

import copy
import json
import time

import numpy as np
import pytest
import tifffile
from cytellect_analysis.images import sha256
from cytellect_analysis.region_contracts import RegionFieldMetadata, RegionImageInfo, RegionReport
from cytellect_api.config import Settings
from cytellect_api.db import Store, fields, revisions, workspaces
from cytellect_api.storage import read_json
from cytellect_worker.regions import run_region_analysis
from sqlalchemy import update

BACKGROUND = {"polygon": [[0, 0], [8, 0], [8, 1], [0, 1]], "confirmed": True}
RECIPE = {"id": "region-2d", "version": "1.0.0", "region_set_id": "reviewed",
          "label": "Reviewed regions", "source": "imported", "defining_channel_id": None}


def _record(path):
    return {"sha256": sha256(path), "bytes": path.stat().st_size}


def setup_fields(tmp_path, *, count=1, imported=True):
    settings = Settings(tmp_path / "private", fiji_executable=None)
    store = Store(settings.data_dir)
    with store.transaction() as conn:
        conn.execute(workspaces.insert().values(id="w", owner="o", title="test", created=time.time(),
                                                expires=time.time() + 3600, deleted=False, bytes=0))
    snapshots = {}
    for i in range(count):
        fid = f"f{i + 1}"
        folder = store.safe_path("workspaces", "w", "fields", fid)
        folder.mkdir(parents=True)
        image = np.full((8, 8), 11, dtype=np.uint16)
        image[2:4, 2:4] = [[2, 6], [10, 6]]
        image[4:6, 4:6] = 20
        labels = np.zeros((8, 8), dtype=np.uint32)
        labels[2:4, 2:4], labels[4:6, 4:6] = 7, 19
        tifffile.imwrite(folder / "ch0.tif", image, photometric="minisblack")
        np.save(folder / "channel-actin.npy", image, allow_pickle=False)
        inputs = {"ch0": _record(folder / "ch0.tif")}
        labels_array = None
        if imported:
            tifffile.imwrite(folder / "labels.tif", labels, photometric="minisblack")
            inputs["labels"] = _record(folder / "labels.tif")
            np.save(folder / "labels.npy", labels, allow_pickle=False)
            labels_array = _record(folder / "labels.npy")
        info = RegionImageInfo.model_validate({
            "shape": [8, 8], "channels": [{"channel_id": "actin", "label": "Actin", "identity_confirmed": True}],
            "inputs": inputs, "channel_arrays": {"actin": _record(folder / "channel-actin.npy")},
            "labels_array": labels_array,
            "calibration": {"pixel_size_x_um": 0.2, "pixel_size_y_um": 0.5, "confirmed": True},
        })
        record = {"id": fid, "workspace_id": "w", "metadata": RegionFieldMetadata().model_dump(mode="json"),
                  "image_info": info.model_dump(mode="json"), "synthetic": False}
        with store.transaction() as conn:
            conn.execute(fields.insert().values(**record))
        snapshots[fid] = record
    config = {"analysis_kind": "region-2d", "recipe": {**RECIPE, "source": "imported" if imported else "manual"},
              "field_ids": list(snapshots), "field_snapshot": snapshots,
              "backgrounds": {fid: {"actin": copy.deepcopy(BACKGROUND)} for fid in snapshots}, "exclusions": []}
    return store, settings, config


def execute(store, settings, config, rid="r1"):
    with store.transaction() as conn:
        conn.execute(revisions.insert().values(id=rid, workspace_id="w", config=config, state="running",
                                              reviewed=False, created=time.time(), parent_id=config.get("reuse_revision")))
    output = store.safe_path("results", rid)
    run_region_analysis(store, settings, {"revision_id": rid, "workspace_id": "w"}, output)
    # A direct worker test does not bypass fencing in production: Store.finish,
    # watchdog and API CAS are exercised by the lifecycle/API integration suites.
    with store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == rid).values(
            state="succeeded", result_dir=str(output.relative_to(store.root))))
    report = read_json(output / "measurements.json")
    assert RegionReport.model_validate_json(json.dumps(report)).model_dump(mode="json") == report
    return report


def test_imported_regions_measure_original_actin_without_fiji_or_replicates(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    report = execute(store, settings, config)
    assert report["field_failures"] == []
    assert report["field_outcomes"] == {"f1": "measured"}
    table = report["field_tables"]["f1"]
    row = table["rows"][0]
    assert (row["region_id"], row["channel_id"], row["area_px"]) == (7, "actin", 4)
    assert row["area_um2"] == pytest.approx(0.4)
    assert (row["mean"], row["median"], row["integrated"]) == (6, 6, 24)
    assert (row["mean_corrected"], row["median_corrected"], row["integrated_corrected"]) == (-5, -5, -20)
    assert "experimental_unit" not in row and "gfp_positive" not in row
    assert table["channel_provenance"][0]["channel"]["stain"] is None
    assert config["field_snapshot"]["f1"]["metadata"]["experimental_unit"] is None
    provenance = read_json(store.safe_path("results", "r1", "provenance.json"))
    assert provenance["detector_executed"] is False


def test_empty_manual_mask_is_editable_and_not_zero_observation(tmp_path):
    store, settings, config = setup_fields(tmp_path, imported=False)
    first = execute(store, settings, config)
    assert first["field_outcomes"] == {"f1": "no_regions"}
    assert first["field_tables"]["f1"]["rows"] == []
    assert first["field_masks"]["f1"]["mask_revision_id"] == "r1"
    child = {**config, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": "add",
        "polygon": [[2, 2], [4, 2], [4, 4], [2, 4]], "expected_mask_revision_id": "r1",
    }}
    result = execute(store, settings, child, "r2")
    row = result["field_tables"]["f1"]["rows"][0]
    assert row["region_id"] == 1 and row["integrated"] == 24
    assert result["field_masks"]["f1"]["mask_revision_id"] == "r2"
    assert not np.load(store.safe_path("results", "r1", "f1", "labels.npy")).any()


@pytest.mark.parametrize("operation,ids,polygon,expected", [
    ("merge", [7, 19], [], {7: 8}),
    ("split", [7], [[2, 2], [3, 2], [3, 4], [2, 4]], {7: 2, 19: 4, 20: 2}),
    ("delete", [19], [], {7: 4}),
    ("replace", [19], [[4, 4], [5, 4], [5, 6], [4, 6]], {7: 4, 19: 2}),
])
def test_edits_remeasure_exact_pixels_preserving_parent(tmp_path, operation, ids, polygon, expected):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    original = np.load(store.safe_path("results", "r1", "f1", "labels.npy")).copy()
    result = execute(store, settings, {**config, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": operation, "ids": ids,
        "polygon": polygon, "expected_mask_revision_id": "r1",
    }}, "r2")
    assert result["field_failures"] == []
    assert {row["region_id"]: row["area_px"] for row in result["field_tables"]["f1"]["rows"]} == expected
    np.testing.assert_array_equal(np.load(store.safe_path("results", "r1", "f1", "labels.npy")), original)


def test_failed_background_measurement_keeps_edited_mask_and_reconfigure_recovers_it(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    edited = {**config, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": "add",
        "polygon": [[0, 0], [1, 0], [1, 1], [0, 1]],
    }}
    failed = execute(store, settings, edited, "r2")
    assert failed["field_failures"] == [{"field_id": "f1", "reason": "region_background_overlaps_measured_regions"}]
    assert failed["field_tables"] == {}
    assert failed["field_masks"]["f1"]["mask_revision_id"] == "r2"
    labels = np.load(store.safe_path("results", "r2", "f1", "labels.npy"))
    assert labels[0, 0] == 20
    repaired = {**config, "reuse_revision": "r2", "backgrounds": {"f1": {"actin": {
        "polygon": [[0, 7], [8, 7], [8, 8], [0, 8]], "confirmed": True,
    }}}}
    result = execute(store, settings, repaired, "r3")
    assert result["field_failures"] == []
    assert result["field_masks"]["f1"]["mask_revision_id"] == "r2"
    assert {row["region_id"] for row in result["field_tables"]["f1"]["rows"]} == {7, 19, 20}
    np.testing.assert_array_equal(np.load(store.safe_path("results", "r3", "f1", "labels.npy")), labels)


def test_partial_failure_preserved_and_explicit_field_exclusion_retains_diagnostic(tmp_path):
    store, settings, config = setup_fields(tmp_path, count=2)
    config["backgrounds"]["f2"]["actin"]["polygon"] = [[2, 2], [4, 2], [4, 4], [2, 4]]
    report = execute(store, settings, config)
    assert set(report["field_tables"]) == {"f1"}
    assert report["field_outcomes"] == {"f1": "measured", "f2": "failed"}
    excluded = [{"field_id": "f2", "region_id": None, "reason": "Background cannot be established"}]
    result = execute(store, settings, {**config, "reuse_revision": "r1", "exclusions": excluded}, "r2")
    assert result["field_failures"] == []
    assert result["excluded_failed_fields"] == [{"field_id": "f2", "reason": excluded[0]["reason"],
                                                  "error": "region_background_overlaps_measured_regions"}]
    assert result["field_masks"]["f2"]["mask_revision_id"] == "r1"


def test_object_exclusion_is_annotation_not_deleted_or_changed_measurement(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    config["exclusions"] = [{"field_id": "f1", "region_id": 7, "reason": "Boundary ambiguous"}]
    report = execute(store, settings, config)
    assert len(report["field_tables"]["f1"]["rows"]) == 2
    assert report["field_tables"]["f1"]["rows"][0]["integrated_corrected"] == -20
    assert report["exclusions"] == config["exclusions"]


@pytest.mark.parametrize("name", ["channel-actin.npy", "ch0.tif", "labels.npy"])
def test_changed_source_bytes_are_rejected_without_leaking_paths(tmp_path, name):
    store, settings, config = setup_fields(tmp_path)
    path = store.safe_path("workspaces", "w", "fields", "f1", name)
    data = path.read_bytes()
    path.write_bytes(data[:-1] + bytes([data[-1] ^ 1]))
    report = execute(store, settings, config)
    assert report["field_failures"] == [{"field_id": "f1", "reason": "region_input_file_hash_mismatch"}]
    assert report["field_tables"] == {} and report["field_masks"] == {}


def test_stale_mask_revision_is_visible_failure_and_parent_mask_is_unchanged(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    first = execute(store, settings, config)
    result = execute(store, settings, {**config, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": "delete", "ids": [7],
        "expected_mask_revision_id": "old",
    }}, "r2")
    assert result["field_failures"] == [{"field_id": "f1", "reason": "region_stale_mask_revision"}]
    assert read_json(store.safe_path("results", "r1", "measurements.json")) == first


def test_unknown_exclusion_does_not_silently_select_different_object(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    config["exclusions"] = [{"field_id": "f1", "region_id": 999, "reason": "Mistyped ID"}]
    report = execute(store, settings, config)
    assert report["field_failures"] == [{"field_id": "f1", "reason": "region_unknown_excluded_object"}]
    assert "f1" in report["field_masks"]


def test_parent_definition_cannot_change_while_reusing_masks(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    execute(store, settings, config)
    changed = {**config, "reuse_revision": "r1", "recipe": {**config["recipe"], "region_set_id": "other"}}
    with pytest.raises(ValueError, match="region_parent_definition_changed"):
        execute(store, settings, changed, "r2")


def test_trial_to_batch_reuses_edited_fields_and_initializes_only_new_fields(tmp_path):
    store, settings, all_fields = setup_fields(tmp_path, count=2)
    trial = {**all_fields, "field_ids": ["f1"], "field_snapshot": {"f1": all_fields["field_snapshot"]["f1"]},
             "backgrounds": {"f1": all_fields["backgrounds"]["f1"]}}
    execute(store, settings, trial)
    correction = {**trial, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": "add",
        "polygon": [[6, 6], [8, 6], [8, 8], [6, 8]], "expected_mask_revision_id": "r1",
    }}
    corrected = execute(store, settings, correction, "r2")
    batch = execute(store, settings, {**all_fields, "reuse_revision": "r2"}, "r3")
    assert batch["field_failures"] == []
    assert batch["field_masks"]["f1"] == corrected["field_masks"]["f1"]
    assert batch["field_masks"]["f2"]["mask_revision_id"] == "r3"
    assert {row["region_id"] for row in batch["field_tables"]["f1"]["rows"]} == {7, 19, 20}
    assert {row["region_id"] for row in batch["field_tables"]["f2"]["rows"]} == {7, 19}
    assert batch["field_tables"]["f1"]["analysis_revision_id"] == "r3"
    subset = {**all_fields, "field_ids": ["f2"], "field_snapshot": {"f2": all_fields["field_snapshot"]["f2"]},
              "backgrounds": {"f2": all_fields["backgrounds"]["f2"]}, "reuse_revision": "r3"}
    with pytest.raises(ValueError, match="region_parent_fields_must_be_retained"):
        execute(store, settings, subset, "r4")


def test_batch_cannot_replace_an_existing_field_snapshot(tmp_path):
    store, settings, all_fields = setup_fields(tmp_path, count=2)
    trial = {**all_fields, "field_ids": ["f1"], "field_snapshot": {"f1": all_fields["field_snapshot"]["f1"]},
             "backgrounds": {"f1": all_fields["backgrounds"]["f1"]}}
    execute(store, settings, trial)
    changed = copy.deepcopy(all_fields)
    changed["reuse_revision"] = "r1"
    changed["field_snapshot"]["f1"]["metadata"]["experimental_unit"] = "invented"
    with pytest.raises(ValueError, match="region_parent_definition_changed"):
        execute(store, settings, changed, "r2")

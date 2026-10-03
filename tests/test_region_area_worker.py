"""Area-only lifecycle uses original masks and never fabricates fluorescence."""
from __future__ import annotations

import copy
import json
import time

import numpy as np
import pytest
from cytellect_analysis.region_contracts import region_report_from_json
from cytellect_api.db import revisions
from cytellect_api.storage import read_json, write_json
from cytellect_worker import regions
from pydantic import ValidationError
from sqlalchemy import update
from test_region_nuclear_worker import install_detector, nuclear_fields
from test_region_worker import execute, setup_fields

POLICY = {"version": "1.0.0", "mode": "area_only"}


def area_config(config):
    return {**copy.deepcopy(config), "measurement": POLICY.copy(), "backgrounds": {}}


def execute_versioned(store, settings, config, rid="r1"):
    with store.transaction() as connection:
        connection.execute(revisions.insert().values(
            id=rid, workspace_id="w", config=config, state="running", reviewed=False,
            created=time.time(), parent_id=config.get("reuse_revision"),
        ))
    output = store.safe_path("results", rid)
    regions.run_region_analysis(store, settings, {"revision_id": rid, "workspace_id": "w"}, output)
    with store.transaction() as connection:
        connection.execute(update(revisions).where(revisions.c.id == rid).values(
            state="succeeded", result_dir=str(output.relative_to(store.root)),
        ))
    result = read_json(output / "measurements.json")
    assert region_report_from_json(json.dumps(result)).model_dump(mode="json") == result
    return result


def test_area_worker_has_exact_native_area_null_signals_and_no_background_files(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    config = area_config(config)
    original = store.safe_path("workspaces", "w", "fields", "f1", "channel-actin.npy").read_bytes()
    report = execute_versioned(store, settings, config)
    assert report["protocol_version"] == "2.0.0" and report["measurement"] == POLICY
    assert report["field_failures"] == []
    table = report["field_tables"]["f1"]
    assert [(row["region_id"], row["area_px"]) for row in table["rows"]] == [(7, 4), (19, 4)]
    for row in table["rows"]:
        assert row["area_um2"] == pytest.approx(0.4)
        assert row["intensity_missing_reason"] == "not_requested"
        assert all(row[name] is None for name in (
            "mean", "median", "integrated", "mean_corrected", "median_corrected", "integrated_corrected",
            "storage_limit_fraction", "acquisition_saturation_fraction",
        ))
    channel = table["channel_provenance"][0]
    assert channel["channel"]["channel_id"] == "actin"
    assert channel["background"] == {"status": "not_measured", "reason": "not_required_for_area"}
    assert not list(store.safe_path("results", "r1").rglob("background-*.npy"))
    assert store.safe_path("workspaces", "w", "fields", "f1", "channel-actin.npy").read_bytes() == original
    provenance = read_json(store.safe_path("results", "r1", "provenance.json"))
    assert provenance["measurement_protocol"] == "2.0.0" and provenance["measurement"] == POLICY
    assert provenance["detector_executed"] is False


def test_area_manual_full_image_needs_no_spare_background_and_keeps_empty_initial_state(tmp_path):
    store, settings, config = setup_fields(tmp_path, imported=False)
    config = area_config(config)
    first = execute_versioned(store, settings, config)
    assert first["field_outcomes"] == {"f1": "no_regions"}
    assert first["field_tables"]["f1"]["rows"] == []
    child = {**config, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "reviewed", "operation": "add",
        "polygon": [[0, 0], [8, 0], [8, 8], [0, 8]], "expected_mask_revision_id": "r1",
    }}
    second = execute_versioned(store, settings, child, "r2")
    assert second["field_failures"] == []
    assert second["field_tables"]["f1"]["rows"][0]["area_px"] == 64
    assert second["field_tables"]["f1"]["rows"][0]["touches_border"] is True
    assert not np.load(store.safe_path("results", "r1", "f1", "labels.npy")).any()


def test_policy_changes_preserve_masks_and_v1_signed_background_results(tmp_path):
    store, settings, original_config = setup_fields(tmp_path)
    original = execute(store, settings, original_config)
    area = execute_versioned(store, settings, {**area_config(original_config), "reuse_revision": "r1"}, "r2")
    restored = execute(store, settings, {**original_config, "reuse_revision": "r2"}, "r3")
    assert original["field_masks"] == area["field_masks"] == restored["field_masks"]
    assert "measurement" not in original and "measurement" not in restored
    assert restored["field_tables"]["f1"]["rows"][0]["integrated_corrected"] == -20
    assert read_json(store.safe_path("results", "r1", "measurements.json")) == original


def test_area_nuclear_reuse_keeps_detector_identity_without_running_again(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    config = area_config(config)
    first = execute_versioned(store, settings, config)
    second = execute_versioned(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert len(calls) == 1 and first["field_masks"] == second["field_masks"]
    for table in second["field_tables"].values():
        assert {row["channel_id"] for row in table["rows"]} == {"dna", "actin"}
        assert [row["area_px"] for row in table["rows"]] == [4, 4, 4, 4]
    provenance = read_json(store.safe_path("results", "r2", "provenance.json"))
    assert provenance["fields"]["f1"]["detector"]["origin_revision_id"] == "r1"
    assert provenance["fields"]["f1"]["detector"]["executed_this_attempt"] is False


def test_area_failure_and_reasoned_field_exclusion_remain_diagnostic(tmp_path):
    store, settings, config = setup_fields(tmp_path, count=2)
    config = area_config(config)
    broken = store.safe_path("workspaces", "w", "fields", "f2", "ch0.tif")
    raw = broken.read_bytes()
    broken.write_bytes(raw[:-1] + bytes([raw[-1] ^ 1]))
    first = execute_versioned(store, settings, config)
    assert first["field_failures"] == [{"field_id": "f2", "reason": "region_input_file_hash_mismatch"}]
    assert set(first["field_tables"]) == {"f1"}
    excluded = [{"field_id": "f2", "region_id": None, "reason": "Source identity could not be verified"}]
    second = execute_versioned(store, settings, {**config, "reuse_revision": "r1", "exclusions": excluded}, "r2")
    assert second["field_failures"] == []
    assert second["field_outcomes"]["f2"] == "excluded_failed"
    assert second["excluded_failed_fields"] == [{"field_id": "f2", "reason": excluded[0]["reason"],
                                                  "error": "region_input_file_hash_mismatch"}]


def test_area_invalid_acquisition_limit_preserves_editable_mask_and_safe_error(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    config = area_config(config)
    descriptor = config["field_snapshot"]["f1"]["image_info"]["channels"][0]
    descriptor.update(acquisition_saturation_value=5, acquisition_saturation_confirmed=True)
    report = execute_versioned(store, settings, config)
    assert report["field_failures"] == [{"field_id": "f1", "reason": "acquisition_limit_inconsistent_with_source"}]
    assert report["field_tables"] == {} and "f1" in report["field_masks"]


@pytest.mark.parametrize("change", ["background", "nested_empty_background", "unknown_mode", "unknown_version"])
def test_area_worker_rejects_invalid_policy_before_publishing_any_output(tmp_path, change):
    store, settings, config = setup_fields(tmp_path)
    invalid = area_config(config)
    if change == "background":
        invalid["backgrounds"] = config["backgrounds"]
    elif change == "nested_empty_background":
        invalid["backgrounds"] = {"f1": {}}
    elif change == "unknown_mode":
        invalid["measurement"]["mode"] = "area_and_raw"
    else:
        invalid["measurement"]["version"] = "2.0.0"
    with pytest.raises(ValidationError):
        execute_versioned(store, settings, invalid)
    assert not store.safe_path("results", "r1").exists()


def test_area_parent_report_cannot_hide_or_replace_its_measurement_policy(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    config = area_config(config)
    execute_versioned(store, settings, config)
    with store.transaction() as connection:
        connection.execute(update(revisions).where(revisions.c.id == "r1").values(
            config={key: value for key, value in config.items() if key != "measurement"},
        ))
    with pytest.raises(ValueError, match="region_measurement_protocol_mismatch"):
        execute_versioned(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert not store.safe_path("results", "r2").exists()


def test_mixed_saved_table_protocol_is_rejected_before_mask_reuse(tmp_path):
    store, settings, config = setup_fields(tmp_path)
    first = execute_versioned(store, settings, area_config(config))
    first["field_tables"]["f1"]["protocol_version"] = "1.0.0"
    write_json(store.safe_path("results", "r1", "measurements.json"), first)
    with pytest.raises(ValidationError):
        execute_versioned(store, settings, {**area_config(config), "reuse_revision": "r1"}, "r2")
    assert not store.safe_path("results", "r2").exists()

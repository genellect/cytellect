"""Nuclear-region worker lifecycle; real model equivalence is tested separately."""
from __future__ import annotations

import copy

import numpy as np
import pytest
import tifffile
from cytellect_analysis.engine import EngineUnavailable
from cytellect_analysis.region_contracts import RegionNuclearRecipe
from cytellect_api.db import fields
from cytellect_api.storage import read_json
from cytellect_worker import regions
from sqlalchemy import update
from test_region_worker import _record, execute, setup_fields


def nuclear_fields(tmp_path, *, count=1):
    store, settings, config = setup_fields(tmp_path, count=count, imported=False)
    for fid, snapshot in config["field_snapshot"].items():
        folder = store.safe_path("workspaces", "w", "fields", fid)
        old = folder / "channel-actin.npy"
        image = np.load(old)
        np.save(folder / "channel-dna.npy", image, allow_pickle=False)
        np.save(old, image + 20, allow_pickle=False)
        tifffile.imwrite(folder / "ch1.tif", image + 20, photometric="minisblack")
        info = snapshot["image_info"]
        info["channels"] = [
            {"channel_id": "dna", "label": "DNA", "stain": "Hoechst", "identity_confirmed": True,
             "acquisition_saturation_value": None, "acquisition_saturation_confirmed": False},
            {"channel_id": "actin", "label": "Actin", "stain": "phalloidin", "identity_confirmed": True,
             "acquisition_saturation_value": None, "acquisition_saturation_confirmed": False},
        ]
        info["inputs"]["ch1"] = _record(folder / "ch1.tif")
        info["channel_arrays"] = {cid: _record(folder / f"channel-{cid}.npy") for cid in ("dna", "actin")}
        config["backgrounds"][fid]["dna"] = copy.deepcopy(config["backgrounds"][fid]["actin"])
        with store.transaction() as conn:
            conn.execute(update(fields).where(fields.c.id == fid).values(image_info=info))
    config["recipe"] = RegionNuclearRecipe(
        region_set_id="nuclei", label="Nuclei", defining_channel_id="dna", nuclear_stain_confirmed=True,
    ).model_dump(mode="json")
    return store, settings, config


def detected_labels():
    labels = np.zeros((8, 8), dtype=np.uint32)
    labels[2:4, 2:4], labels[4:6, 4:6] = 7, 19
    return labels


def install_detector(monkeypatch, *, labels=None):
    calls = []

    def detector(image, parameters, destination, executable, scratch_root=None):
        calls.append({"pixels": image.copy(), "parameters": parameters.model_dump(mode="json"),
                      "destination": destination, "scratch": scratch_root})
        assert not image.flags.writeable
        return (detected_labels() if labels is None else labels.copy()), {
            "nuclear_detector_protocol_version": "1.0.0", "model": parameters.model,
            "model_sha256": "a" * 64, "parameters": parameters.model_dump(mode="json"),
        }

    monkeypatch.setattr(regions, "detect_nuclei", detector)
    return calls


def test_first_automatic_run_uses_only_confirmed_dna_and_measures_actual_channels(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    report = execute(store, settings, config)
    assert report["field_failures"] == [] and len(calls) == 1
    folder = store.safe_path("workspaces", "w", "fields", "f1")
    np.testing.assert_array_equal(calls[0]["pixels"], np.load(folder / "channel-dna.npy"))
    assert calls[0]["parameters"] == config["recipe"]["detector"]
    assert calls[0]["scratch"] == store.safe_path("results")
    rows = report["field_tables"]["f1"]["rows"]
    assert {(row["region_id"], row["channel_id"], row["mean"]) for row in rows} == {
        (7, "dna", 6), (7, "actin", 26), (19, "dna", 20), (19, "actin", 40),
    }
    assert report["field_masks"]["f1"]["source"] == "stardist_nuclear"
    provenance = read_json(store.safe_path("results", "r1", "provenance.json"))
    record = provenance["fields"]["f1"]["detector"]
    assert record["origin_revision_id"] == "r1" and record["executed_this_attempt"] is True
    assert record["protocol_version"] == "1.0.0"
    assert record["defining_channel"]["stain"] == "Hoechst"
    assert record["parameters"] == config["recipe"]["detector"] and len(record["input_sha256"]) == 64
    assert provenance["detector_executed"] is True
    assert report["protocol_version"] == "1.0.0" and config["recipe"]["version"] == "1.1.0"


def test_corrected_masks_and_background_only_remeasurement_do_not_run_fiji(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    execute(store, settings, config)
    edited = {**config, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "nuclei", "operation": "delete", "ids": [19],
        "expected_mask_revision_id": "r1",
    }}
    second = execute(store, settings, edited, "r2")
    third = execute(store, settings, {**config, "reuse_revision": "r2"}, "r3")
    assert len(calls) == 1
    assert second["field_failures"] == third["field_failures"] == []
    assert third["field_masks"]["f1"]["mask_revision_id"] == "r2"
    assert {row["region_id"] for row in third["field_tables"]["f1"]["rows"]} == {7}
    original = read_json(store.safe_path("results", "r1", "provenance.json"))["fields"]["f1"]["detector"]
    provenance = read_json(store.safe_path("results", "r3", "provenance.json"))
    assert provenance["fields"]["f1"]["detector"] == {**original, "executed_this_attempt": False}
    assert provenance["detector_executed"] is False
    assert np.load(store.safe_path("results", "r1", "f1", "labels.npy"))[4, 4] == 19


def test_background_collision_preserves_detected_mask_and_engine_for_recovery(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    bad = copy.deepcopy(config)
    bad["backgrounds"]["f1"]["actin"]["polygon"] = [[2, 2], [4, 2], [4, 4], [2, 4]]
    failed = execute(store, settings, bad)
    assert failed["field_tables"] == {}
    assert failed["field_failures"] == [{"field_id": "f1", "reason": "region_background_overlaps_measured_regions"}]
    assert "f1" in failed["field_masks"]
    fixed = execute(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert fixed["field_failures"] == [] and len(calls) == 1
    assert fixed["field_masks"]["f1"]["mask_revision_id"] == "r1"
    assert read_json(store.safe_path("results", "r2", "provenance.json"))["fields"]["f1"]["detector"]["origin_revision_id"] == "r1"


def test_trial_to_batch_initializes_new_fields_only_and_retains_edits(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path, count=2)
    calls = install_detector(monkeypatch)
    trial = {**config, "field_ids": ["f1"], "field_snapshot": {"f1": config["field_snapshot"]["f1"]},
             "backgrounds": {"f1": config["backgrounds"]["f1"]}}
    execute(store, settings, trial)
    execute(store, settings, {**trial, "reuse_revision": "r1", "region_edit": {
        "field_id": "f1", "region_set_id": "nuclei", "operation": "delete", "ids": [19],
    }}, "r2")
    final = execute(store, settings, {**config, "reuse_revision": "r2"}, "r3")
    assert len(calls) == 2 and final["field_failures"] == []
    assert {row["region_id"] for row in final["field_tables"]["f1"]["rows"]} == {7}
    assert {row["region_id"] for row in final["field_tables"]["f2"]["rows"]} == {7, 19}
    provenance = read_json(store.safe_path("results", "r3", "provenance.json"))["fields"]
    assert provenance["f1"]["detector"]["executed_this_attempt"] is False
    assert provenance["f2"]["detector"]["origin_revision_id"] == "r3"


def test_zero_detected_regions_is_not_a_failed_field(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch, labels=np.zeros((8, 8), dtype=np.uint32))
    report = execute(store, settings, config)
    assert report["field_outcomes"] == {"f1": "no_regions"} and report["field_failures"] == []
    assert report["field_tables"]["f1"]["rows"] == []


@pytest.mark.parametrize("error", ["fiji_timeout", "fiji_not_configured", "fiji_detection_capacity_exceeded",
                                   "fiji_invalid_output_provenance", "private filename must not escape"])
def test_detector_failure_and_retry_are_not_no_regions(tmp_path, monkeypatch, error):
    store, settings, config = nuclear_fields(tmp_path)

    def fail(*args, **kwargs):
        raise EngineUnavailable(error)

    monkeypatch.setattr(regions, "detect_nuclei", fail)
    first = execute(store, settings, config)
    code = error if error in regions.REGION_FIELD_ERRORS else "region_field_analysis_failed"
    assert first["field_masks"] == first["field_tables"] == {}
    assert first["field_failures"] == [{"field_id": "f1", "reason": code}]
    prior = read_json(store.safe_path("results", "r1", "provenance.json"))
    assert "detector" not in prior["fields"]["f1"]
    assert prior["fields"]["f1"]["history"][-1]["error"] == code
    calls = install_detector(monkeypatch)
    second = execute(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert len(calls) == 1 and second["field_failures"] == []
    history = read_json(store.safe_path("results", "r2", "provenance.json"))["fields"]["f1"]["history"]
    assert history[0]["operation"] == "detection_failed" and history[-1]["operation"] == "initialize"


def test_modified_detector_parameters_cannot_reuse_old_masks(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    execute(store, settings, config)
    changed = copy.deepcopy(config)
    changed["reuse_revision"] = "r1"
    changed["recipe"]["detector"]["probability"] = 0.6
    with pytest.raises(ValueError, match="region_parent_definition_changed"):
        execute(store, settings, changed, "r2")
    assert len(calls) == 1


def test_missing_origin_provenance_does_not_silently_reuse_auto_masks(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    execute(store, settings, config)
    path = store.safe_path("results", "r1", "provenance.json")
    path.write_text('{}', encoding="utf-8")
    result = execute(store, settings, {**config, "reuse_revision": "r1"}, "r2")
    assert result["field_failures"] == [{"field_id": "f1", "reason": "region_parent_detector_provenance_invalid"}]
    assert len(calls) == 1


def test_automatic_source_cannot_override_uploaded_labels(tmp_path, monkeypatch):
    store, settings, config = setup_fields(tmp_path, imported=True)
    config["recipe"] = RegionNuclearRecipe(
        region_set_id="nuclei", label="Nuclei", defining_channel_id="actin", nuclear_stain_confirmed=True,
    ).model_dump(mode="json")
    calls = install_detector(monkeypatch)
    report = execute(store, settings, config)
    assert report["field_failures"] == [{"field_id": "f1", "reason": "region_automatic_source_has_imported_labels"}]
    assert not calls


def test_partial_detector_failure_preserves_success_and_explicit_exclusion(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path, count=2)
    count = 0

    def detect(image, parameters, destination, executable, scratch_root=None):
        nonlocal count
        count += 1
        if count == 2:
            raise EngineUnavailable("fiji_timeout")
        return detected_labels(), {"model": parameters.model}

    monkeypatch.setattr(regions, "detect_nuclei", detect)
    report = execute(store, settings, config)
    assert set(report["field_tables"]) == {"f1"} and set(report["field_masks"]) == {"f1"}
    assert report["field_outcomes"] == {"f1": "measured", "f2": "failed"}
    calls = install_detector(monkeypatch)
    child = {**config, "reuse_revision": "r1", "exclusions": [
        {"field_id": "f2", "region_id": None, "reason": "Instrument problem"},
    ]}
    result = execute(store, settings, child, "r2")
    assert len(calls) == 1 and result["field_failures"] == []
    assert result["exclusions"] == child["exclusions"]
    assert result["field_masks"]["f1"]["mask_revision_id"] == "r1"

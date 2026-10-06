"""Compartment revisions pin immutable canonical nuclei, never infer a whole cell."""
import json

import numpy as np
from cytellect_analysis.region_contracts import RegionCompartmentRecipe, region_report_from_json
from cytellect_api.db import revisions
from cytellect_api.storage import read_json
from cytellect_worker import regions
from sqlalchemy import update
from test_region_nuclear_worker import detected_labels, install_detector, nuclear_fields
from test_region_worker import execute


def compartment_config(base, source="nuclear"):
    return {**base, "recipe": RegionCompartmentRecipe(region_set_id="nucleoli", label="NCL-enriched candidates", compartment="nucleoli", nuclear_revision_id=source, nuclear_channel_id="dna", defining_channel_id="actin").model_dump(mode="json")}


def test_compartment_uses_canonical_parent_masks_and_preserves_parent(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    calls = install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    received = []
    def detect(*, channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        received.append(nuclei.copy())
        children = np.zeros_like(nuclei)
        children[2, 2] = 1
        return {"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)}, {"parent_ids": {"1": 7}, "nucleolar_states": {"7": "candidate", "19": "no_candidate"}, "missing_parent_count": 1}
    monkeypatch.setattr(regions, "detect_compartments", detect)
    child = compartment_config(config)
    report = execute(store, settings, child, "child")
    assert report["field_failures"] == [] and len(calls) == 1
    np.testing.assert_array_equal(received[0], detected_labels())
    record = read_json(store.safe_path("results", "child", "provenance.json"))["fields"]["f1"]
    assert record["nuclear_source"]["revision_id"] == "nuclear"
    assert record["detector"]["engine"]["missing_parent_count"] == 1
    assert {row["area_px"] for row in report["field_tables"]["f1"]["rows"]} == {1}
    again = execute(store, settings, {**child, "reuse_revision": "child"}, "again")
    assert again["field_failures"] == [] and len(received) == 1
    np.testing.assert_array_equal(np.load(store.safe_path("results", "nuclear", "f1", "labels.npy")), detected_labels())


def test_cross_workspace_parent_is_rejected_before_compartment_engine(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    with store.transaction() as connection:
        connection.execute(update(revisions).where(revisions.c.id == "nuclear").values(workspace_id="different"))
    monkeypatch.setattr(regions, "detect_compartments", lambda **kwargs: (_ for _ in ()).throw(AssertionError("must not run")))
    report = execute(store, settings, compartment_config(config), "child")
    assert report["field_tables"] == {}
    assert report["field_failures"][0]["reason"] == "compartment_nuclear_source_invalid"


def test_modified_nuclear_mask_fails_hash_check(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    np.save(store.safe_path("results", "nuclear", "f1", "labels.npy"), np.zeros((8,8), dtype=np.uint32))
    report = execute(store, settings, compartment_config(config), "child")
    assert report["field_tables"] == {} and report["field_failures"]


def test_nucleoplasm_from_adopted_nucleoli_skips_the_detector_and_saves_the_ratio_summary(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    calls = []
    def detect(*, channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        calls.append(1)
        children = np.zeros_like(nuclei)
        children[2, 2] = 1
        return {"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)}, {"nucleolar_states": {"7": "candidate", "19": "candidate"}}
    monkeypatch.setattr(regions, "detect_compartments", detect)
    execute(store, settings, compartment_config(config), "nucleoli")
    plasm = {**config, "recipe": RegionCompartmentRecipe(region_set_id="nucleoplasm", label="Nucleoplasm", compartment="nucleoplasm", nuclear_revision_id="nuclear", nuclear_channel_id="dna", defining_channel_id="actin", nucleolar_revision_id="nucleoli").model_dump(mode="json")}
    report = execute(store, settings, plasm, "plasm")
    assert report["field_failures"] == [] and len(calls) == 1
    summary = read_json(store.safe_path("results", "plasm", "f1", "compartment-summary.json"))
    assert summary["nucleolar_revision"]["revision_id"] == "nucleoli"
    rows = {row["nucleus_id"]: row for row in summary["channels"]["actin"]["rows"]}
    assert rows[7]["nucleolar_area_px"] == 1 and rows[19]["missing_reason"] == "no_nucleolus"
    record = read_json(store.safe_path("results", "plasm", "provenance.json"))["fields"]["f1"]
    assert record["nucleolar_source"]["revision_id"] == "nucleoli"


def test_automatic_background_adds_corrected_ratio_summaries_without_replacing_raw_values(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    def detect(*, channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        children = np.zeros_like(nuclei)
        children[2, 2] = 1
        return {"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)}, {"nucleolar_states": {"7": "candidate", "19": "candidate"}}
    monkeypatch.setattr(regions, "detect_compartments", detect)
    execute(store, settings, compartment_config(config), "nucleoli")
    plasm = {**config, "backgrounds": {}, "measurement": {"version": "1.2.0", "mode": "automatic_background"},
             "recipe": RegionCompartmentRecipe(region_set_id="nucleoplasm", label="Nucleoplasm", compartment="nucleoplasm", nuclear_revision_id="nuclear", nuclear_channel_id="dna", defining_channel_id="actin", nucleolar_revision_id="nucleoli").model_dump(mode="json")}
    with store.transaction() as conn:
        conn.execute(revisions.insert().values(id="plasm", workspace_id="w", config=plasm, state="running",
                                              reviewed=False, created=0.0, parent_id=None))
    regions.run_region_analysis(store, settings, {"revision_id": "plasm", "workspace_id": "w"}, store.safe_path("results", "plasm"))
    report = read_json(store.safe_path("results", "plasm", "measurements.json"))
    assert region_report_from_json(json.dumps(report)).protocol_version == "4.0.0"
    assert report["field_failures"] == []
    summary = read_json(store.safe_path("results", "plasm", "f1", "compartment-summary.json"))
    provenance = {item["channel"]["channel_id"]: item["background"]
                  for item in report["field_tables"]["f1"]["channel_provenance"]}
    assert summary["background"] == "automatic_candidate" and set(summary["corrected_channels"]) == set(provenance)
    for cid, background in provenance.items():
        corrected, raw = summary["corrected_channels"][cid], summary["channels"][cid]
        assert all(row["values"] == "raw" for row in raw["rows"])
        if background["status"] == "established":
            pairs = zip(raw["rows"], corrected["rows"], strict=True)
            for before, after in pairs:
                if before["nucleolar_mean"] is not None and after["nucleolar_mean"] is not None:
                    assert after["nucleolar_mean"] == before["nucleolar_mean"] - background["background_median"]
        else:
            assert corrected == {"protocol": "compartment-summary/1.0.0", "rows": [], "missing_reason": background["reason"]}


def test_established_automatic_background_is_subtracted_once_from_both_compartments():
    from types import SimpleNamespace
    nuclei = np.zeros((6, 6), np.uint32)
    nuclei[1:5, 1:5] = 1
    nucleoli = np.zeros_like(nuclei)
    nucleoli[2, 2] = 1
    plasm = np.where(nucleoli, 0, nuclei).astype(np.uint32)
    image = np.full(nuclei.shape, 30, np.uint16)
    image[2, 2] = 90
    channel = SimpleNamespace(channel=SimpleNamespace(channel_id="ncl"),
                              background=SimpleNamespace(status="established", background_median=10.0, reason=None))
    table = SimpleNamespace(protocol_version="4.0.0", channel_provenance=(channel,))
    report = regions._compartment_summary_report((nuclei, nucleoli, {"revision_id": "n"}), plasm, {"ncl": image}, table)
    raw, corrected = report["channels"]["ncl"]["rows"][0], report["corrected_channels"]["ncl"]["rows"][0]
    assert raw["ratio_nucleoplasm_over_nucleolus"] == 30 / 90
    assert corrected["ratio_nucleoplasm_over_nucleolus"] == 20 / 80 and corrected["values"] == "background_corrected"

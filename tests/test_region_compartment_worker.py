"""Compartment revisions pin immutable canonical nuclei, never infer a whole cell."""
import numpy as np
from cytellect_analysis.region_contracts import RegionCompartmentRecipe
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

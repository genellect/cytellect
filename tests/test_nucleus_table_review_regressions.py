"""Independent review regressions using synthetic minimum labels and saved-value joins.

These test arithmetic/state ledgers, not detection, image quality, or biology.
The unresolved/adopted and excluded states cannot have fixed expected outcomes
on a real image without fabricating a review decision.
"""
import json

import numpy as np
from cytellect_analysis.compartment_engine import derive_compartment_masks
from cytellect_analysis.nucleus_table import nucleolar_morphology, nucleus_table
from cytellect_analysis.region_contracts import region_report_from_json
from cytellect_api.storage import read_json
from test_region_nuclear_worker import install_detector, nuclear_fields
from test_region_worker import execute


def test_retained_partial_candidates_never_establish_a_measured_parent():
    nuclei = np.ones((4, 4), dtype=np.uint32)
    children = np.zeros_like(nuclei)
    children[1:3, 1:3] = 2
    masks, evidence = derive_compartment_masks(
        nuclei, children, {1: "review_required"}, retain_review_candidates=True,
    )
    assert evidence["compartment_status"] == "incomplete"
    assert evidence["incomplete_nucleolar_parent_ids"] == [1]
    assert np.any(masks["nucleoli"])
    result = nucleolar_morphology(nuclei, masks["nucleoli"], {1: "review_required"}, None)[1]
    assert result.status == "missing"
    assert result.reason == "review_required"
    assert result.count is None and result.union_area_px is None


def test_whole_field_exclusion_keeps_its_reason_on_every_nucleus(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    root = store.safe_path("results", "nuclear")
    report = region_report_from_json(json.dumps(read_json(root / "measurements.json")))
    mask = report.field_masks["f1"].model_dump(mode="json")
    table = nucleus_table(
        field_id="f1", nuclear_revision_id="nuclear", nuclear_mask=mask,
        nuclear_table=report.field_tables["f1"],
        nuclear_labels=np.load(root / "f1" / "labels.npy", allow_pickle=False),
        exclusions=[{"field_id": "f1", "region_id": None, "reason": "quality_review"}],
        nuclear_channel_id="dna",
        nuclear_adopted=True,
    )
    assert table.field_excluded and table.rows
    assert all(row.excluded and row.exclusion_reason == "quality_review" for row in table.rows)
    assert all(row.nucleoli.status == "not_measured" for row in table.rows)
    assert all(row.nucleoli.reason in {"nucleus_excluded", "field_excluded"} for row in table.rows)

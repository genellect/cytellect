"""Nucleus table 1.0.0 joins saved rows and adopted nucleoli by nucleus label (synthetic label arrays:
the expected joins, ledgers and missing reasons cannot be fixed on a real image)."""
import numpy as np
import pytest
from cytellect_analysis.masks import validate_labels
from cytellect_analysis.nucleolar_shape import nucleolar_eccentricity, object_eccentricity
from cytellect_analysis.nucleus_table import nucleolar_morphology
from cytellect_api.db import revisions, workspaces
from cytellect_api.storage import read_json
from cytellect_worker import regions
from sqlalchemy import select, update
from test_api_worker import HEADERS, authenticated
from test_region_compartment_worker import compartment_config
from test_region_nuclear_worker import install_detector, nuclear_fields
from test_region_worker import execute


def _reference_eccentricity(nuclei, nucleoli):
    """The definition before vectorisation: one full-image scan per nucleus and object."""
    shapes = {}
    for parent in (int(value) for value in np.unique(nuclei) if value):
        objects = [int(value) for value in np.unique(nucleoli[nuclei == parent]) if value]
        weighted, weight, measured = 0.0, 0, 0
        for label in objects:
            rows, columns = np.nonzero(nucleoli == label)
            value = object_eccentricity(rows, columns)
            if value is None:
                continue
            weighted += value * rows.size
            weight += rows.size
            measured += 1
        shapes[parent] = (weighted / weight if measured else None, len(objects), measured)
    return shapes


def test_vectorised_eccentricity_and_parent_check_keep_the_definition():
    rng = np.random.default_rng(7)
    nuclei = np.zeros((40, 40), np.uint32)
    nuclei[2:18, 2:18], nuclei[20:38, 4:30], nuclei[5:15, 25:35] = 3, 4000000000, 9
    nucleoli = np.where(nuclei > 0, rng.integers(0, 6, nuclei.shape), 0).astype(np.uint32)
    nucleoli[nucleoli > 0] += (nuclei[nucleoli > 0] % 1000).astype(np.uint32) * 10  # unique per parent
    shapes = nucleolar_eccentricity(nuclei, nucleoli)
    assert {key: (value["nucleolar_eccentricity"], value["objects"], value["measured_objects"])
            for key, value in shapes.items()} == _reference_eccentricity(nuclei, nucleoli)
    straddling = nucleoli.copy()
    straddling[2, 2] = straddling[20, 4]  # one object in two nuclei
    with pytest.raises(ValueError, match="nucleolus_requires_single_parent"):
        validate_labels(nuclei, straddling)
    outside = nucleoli.copy()
    outside[0, 0] = nucleoli[2, 3] or 1
    with pytest.raises(ValueError, match="nucleolus_requires_single_parent"):
        validate_labels(nuclei, outside)


def test_morphology_reports_largest_object_and_keeps_unresolved_nuclei_missing():
    nuclei = np.zeros((10, 10), np.uint32)
    nuclei[0:5, 0:5], nuclei[5:10, 5:10], nuclei[0:3, 6:9] = 1, 2, 3
    nucleoli = np.zeros_like(nuclei)
    nucleoli[1:3, 1:3], nucleoli[3, 3] = 11, 12  # 4 px and 1 px in nucleus 1
    result = nucleolar_morphology(nuclei, nucleoli, {1: "candidate", 2: "no_candidate"}, 0.25)
    first = result[1]
    assert (first.status, first.count, first.union_area_px, first.largest_object_area_px) == ("measured", 2, 5, 4)
    assert first.area_fraction == 5 / 25 and first.largest_object_fraction == 4 / 5
    assert first.union_area_um2 == 5 * 0.25
    assert (result[2].status, result[2].reason, result[2].count) == ("missing", "no_candidate", None)
    assert (result[3].status, result[3].reason) == ("missing", "no_adopted_nucleolus")


def _nucleoli_detector(monkeypatch):
    def detect(*, channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        children = np.zeros_like(nuclei)
        children[2, 2:4] = 1  # two pixels in nucleus 7
        return ({"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)},
                {"parent_ids": {"1": 7}, "nucleolar_states": {"7": "candidate", "19": "no_candidate"},
                 "missing_parent_count": 1})
    monkeypatch.setattr(regions, "detect_compartments", detect)


def test_api_returns_one_row_per_nucleus_with_every_channel_and_its_nucleoli(tmp_path, monkeypatch):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    _nucleoli_detector(monkeypatch)
    execute(store, settings, compartment_config(config), "nucleoli")
    client, app, _ = authenticated(tmp_path / "private")  # the API over the worker's data directory
    mine = client.post("/v1/workspaces", headers=HEADERS, json={"title": "owner"}).json()["id"]
    api_store = app.state.store
    with api_store.transaction() as conn:
        owner = conn.execute(select(workspaces.c.owner).where(workspaces.c.id == mine)).scalar_one()
        conn.execute(update(workspaces).where(workspaces.c.id == "w").values(owner=owner))

    response = client.get("/v1/revisions/nuclear/nucleus-table", headers=HEADERS,
                          params={"field_id": "f1", "nucleolar_revision_id": "nucleoli"})
    assert response.status_code == 200, response.text
    table = response.json()
    assert table["protocol"] == "nucleus-table/1.0.0" and table["nuclear_channel_id"] == "dna"
    assert table["nucleolar_source"]["revision_id"] == "nucleoli"
    saved = read_json(api_store.safe_path("results", "nuclear", "measurements.json"))["field_tables"]["f1"]["rows"]
    rows = {row["nucleus_id"]: row for row in table["rows"]}
    assert set(rows) == {7, 19}
    first = rows[7]
    assert first["nucleus_area_px"] == 4 and first["nucleus_area_um2"] == pytest.approx(4 * 0.2 * 0.5)
    assert [(item["channel_id"], item["role"]) for item in first["channels"]] == [("dna", "nuclear_stain"), ("actin", "measure")]
    expected = {(row["region_id"], row["channel_id"]): row["integrated"] for row in saved}
    assert all(item["integrated"] == expected[(7, item["channel_id"])] for item in first["channels"])
    assert first["nucleoli"] | {"eccentricity": None} == {
        "status": "measured", "reason": None, "count": 1, "union_area_px": 2,
        "union_area_um2": pytest.approx(2 * 0.1), "area_fraction": 0.5, "largest_object_area_px": 2,
        "largest_object_fraction": 1.0, "eccentricity": None, "eccentricity_missing_reason": None}
    assert first["nucleoli"]["eccentricity"] == 1.0  # a horizontal line of two pixels
    assert rows[19]["nucleoli"]["status"] == "missing" and rows[19]["nucleoli"]["reason"] == "no_candidate"

    alone = client.get("/v1/revisions/nuclear/nucleus-table", headers=HEADERS, params={"field_id": "f1"}).json()
    assert {row["nucleoli"]["reason"] for row in alone["rows"]} == {"nucleolar_revision_not_selected"}

    with api_store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == "nucleoli").values(
            config={**compartment_config(config, source="other")}))
    wrong = client.get("/v1/revisions/nuclear/nucleus-table", headers=HEADERS,
                       params={"field_id": "f1", "nucleolar_revision_id": "nucleoli"})
    assert wrong.status_code == 422 and wrong.json()["detail"] == "nucleus_table_nucleolar_source_invalid"

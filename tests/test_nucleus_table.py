"""Nucleus table 1.0.0 joins saved rows and confirmed nucleoli by nucleus label (synthetic label arrays:
the expected joins, ledgers and missing reasons cannot be fixed on a real image)."""
import csv
import io
import json
import zipfile
from types import SimpleNamespace

import numpy as np
import pytest
from cytellect_analysis.masks import validate_labels
from cytellect_analysis.nucleolar_shape import nucleolar_eccentricity, object_eccentricity
from cytellect_analysis.nucleus_table import nucleolar_morphology, nucleus_table, nucleus_table_files
from cytellect_analysis.regions import Calibration2D
from cytellect_api.db import workspaces
from cytellect_api.storage import read_json, write_json
from cytellect_worker import regions
from sqlalchemy import select, update
from test_api_worker import HEADERS, authenticated
from test_region_compartment_worker import compartment_config
from test_region_nuclear_worker import install_detector, nuclear_fields
from test_region_worker import execute

SHA = "a" * 64


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


def _field():
    """Nuclei 1–4 (25 px each); nucleus 1 has objects 11 (4 px) and 12 (1 px), nucleus 2 keeps a
    retained review candidate 21, nucleus 3 has none, nucleus 4 has object 41."""
    nuclei = np.zeros((10, 10), np.uint32)
    nuclei[0:5, 0:5], nuclei[5:10, 5:10], nuclei[0:5, 5:10], nuclei[5:10, 0:5] = 1, 2, 3, 4
    nucleoli = np.zeros_like(nuclei)
    nucleoli[1:3, 1:3], nucleoli[3, 3], nucleoli[6:8, 6:8], nucleoli[6, 1] = 11, 12, 21, 41
    return nuclei, nucleoli


def test_only_candidate_parents_with_objects_are_confirmed():
    nuclei, nucleoli = _field()
    states = {1: "candidate", 2: "review_required", 3: "no_candidate"}  # nucleus 4 has no recorded state
    result = nucleolar_morphology(nuclei, nucleoli, states, 0.25)
    first = result[1]
    assert (first.status, first.count, first.union_area_px, first.largest_object_area_px) == ("measured", 2, 5, 4)
    assert first.area_fraction == 5 / 25 and first.largest_object_fraction == 4 / 5 and first.union_area_um2 == 1.25
    # A parent awaiting review keeps its candidate in the mask but is not confirmed.
    assert (result[2].status, result[2].reason, result[2].count) == ("missing", "review_required", None)
    assert (result[3].status, result[3].reason) == ("missing", "no_candidate")
    assert (result[4].status, result[4].reason) == ("missing", "nucleolar_state_unknown")
    emptied = nucleolar_morphology(nuclei, np.where(nuclei == 1, 0, nucleoli).astype(np.uint32), {1: "candidate"}, None)
    assert (emptied[1].status, emptied[1].reason) == ("missing", "no_adopted_nucleolus")


def _saved_rows(nuclei, *, channels=("dna", "npm1")):
    rows = []
    for nucleus in (int(value) for value in np.unique(nuclei) if value):
        area = int((nuclei == nucleus).sum())
        for cid in channels:
            rows.append(SimpleNamespace(region_id=nucleus, channel_id=cid, area_px=area, area_um2=area * 0.25,
                                        area_missing_reason=None, touches_border=False, mean=10.0 * nucleus,
                                        integrated=10.0 * nucleus * area, mean_corrected=None, integrated_corrected=None,
                                        intensity_missing_reason=None, correction_missing_reason="background_not_established",
                                        storage_limit_fraction=0.0, acquisition_saturation_fraction=None,
                                        acquisition_saturation_missing_reason="acquisition_limit_unknown"))
    return SimpleNamespace(shape_yx=nuclei.shape, mask_sha256=SHA, protocol_version="3.0.0",
                           calibration=Calibration2D(pixel_size_x_um=0.5, pixel_size_y_um=0.5, confirmed=True),
                           channel_provenance=[SimpleNamespace(channel=SimpleNamespace(channel_id=c)) for c in channels],
                           rows=tuple(rows))


def _table(**changes):
    nuclei, nucleoli = _field()
    arguments = dict(field_id="f1", nuclear_revision_id="n", nuclear_mask={"mask_revision_id": "n", "mask_sha256": SHA},
                     nuclear_table=_saved_rows(nuclei), nuclear_labels=nuclei, exclusions=[], nuclear_channel_id="dna",
                     nuclear_adopted=True, nucleoli=nucleoli,
                     nucleolar_states={"1": "candidate", "2": "review_required", "3": "no_candidate", "4": "candidate"},
                     nucleolar_exclusions=[], nucleolar_source={"revision_id": "c", "mask_revision_id": "c",
                                                                "mask_sha256": "b" * 64, "adopted": True})
    arguments.update(changes)
    table = nucleus_table(**arguments)
    return {row.nucleus_id: row for row in table.rows}, table


def test_exclusions_adoption_and_field_exclusions_never_confirm_nucleoli():
    rows, table = _table()
    assert [rows[n].nucleoli.status for n in (1, 2, 3, 4)] == ["measured", "missing", "missing", "measured"]
    assert [item.role for item in rows[1].channels] == ["nuclear_stain", "measure"]
    # One nucleolus of nucleus 1 excluded: the rest stay confirmed and the exclusion is counted.
    rows, _ = _table(nucleolar_exclusions=[{"field_id": "f1", "region_id": 12, "reason": "debris"}])
    assert (rows[1].nucleoli.count, rows[1].nucleoli.union_area_px, rows[1].nucleoli.excluded_objects) == (1, 4, 1)
    # Its only nucleolus excluded: nucleus 4 is missing, never zero.
    rows, _ = _table(nucleolar_exclusions=[{"field_id": "f1", "region_id": 41, "reason": "debris"}])
    assert (rows[4].nucleoli.status, rows[4].nucleoli.reason, rows[4].nucleoli.excluded_objects) == ("missing", "no_adopted_nucleolus", 1)
    rows, table = _table(nucleolar_exclusions=[{"field_id": "f1", "region_id": None, "reason": "out of focus"}])
    assert table.nucleolar_source.field_excluded and {row.nucleoli.reason for row in rows.values()} == {"nucleolar_field_excluded"}
    rows, _ = _table(nucleolar_source={"revision_id": "c", "mask_revision_id": "c", "mask_sha256": "b" * 64, "adopted": False})
    assert {(row.nucleoli.status, row.nucleoli.reason) for row in rows.values()} == {("missing", "nucleolar_revision_not_adopted")}
    rows, table = _table(exclusions=[{"field_id": "f1", "region_id": None, "reason": "out of focus"}])
    assert table.field_excluded and all(row.excluded and row.nucleoli.reason == "nucleus_excluded" for row in rows.values())
    rows, _ = _table(exclusions=[{"field_id": "f1", "region_id": 1, "reason": "mitotic"}])
    assert (rows[1].excluded, rows[1].exclusion_reason, rows[1].nucleoli.status) == (True, "mitotic", "not_measured")
    with pytest.raises(ValueError, match="nucleolar_state_invalid"):
        _table(nucleolar_states={"1": "adopted_by_hand"})


def test_csv_copies_the_table_with_units_definitions_and_escaped_text():
    _, table = _table(exclusions=[{"field_id": "f1", "region_id": 3, "reason": "=HYPERLINK(1)"}])
    files = nucleus_table_files(table)
    rows = list(csv.DictReader(io.StringIO(files["nucleus-table.csv"].decode("utf-8-sig"))))
    assert [row["nucleus_id"] for row in rows] == ["1", "2", "3", "4"]
    first = rows[0]
    assert (first["nucleolar_status"], first["nucleolar_count"], first["nucleolar_area_px"], first["nucleolar_area_um2"]) == ("measured", "2", "5", "1.25")
    assert first["dna__role"] == "nuclear_stain" and first["npm1__mean"] == "10.0" and first["npm1__mean_corrected"] == ""
    assert first["npm1__correction_missing_reason"] == "background_not_established"
    assert (rows[1]["nucleolar_status"], rows[1]["nucleolar_reason"], rows[1]["nucleolar_count"]) == ("missing", "review_required", "")
    assert rows[2]["exclusion_reason"] == "'=HYPERLINK(1)"
    assert {row["nuclear_mask_sha256"] for row in rows} == {SHA} and rows[0]["nucleolar_revision_id"] == "c"
    definitions = {row["column"]: row for row in csv.DictReader(io.StringIO(files["columns.csv"].decode("utf-8-sig")))}
    assert set(definitions) == set(rows[0]) and definitions["nucleolar_area_um2"]["unit"] == "µm²"
    assert json.loads(files["nucleus-table.json"])["rows"][1]["nucleoli"]["reason"] == "review_required"


def _nucleoli_detector(monkeypatch, states):
    def detect(*, channels, nuclei, parameters, output_dir, executable, scratch_root=None):
        children = np.zeros_like(nuclei)
        children[2, 2:4] = 1  # two pixels in nucleus 7
        children[4, 4] = 2    # a retained candidate in nucleus 19
        return ({"nucleoli": children, "nucleoplasm": np.where(children, 0, nuclei)},
                {"parent_ids": {"1": 7, "2": 19}, "nucleolar_states": states, "missing_parent_count": 1})
    monkeypatch.setattr(regions, "detect_compartments", detect)


def _api(tmp_path, monkeypatch, states):
    store, settings, config = nuclear_fields(tmp_path)
    install_detector(monkeypatch)
    execute(store, settings, config, "nuclear")
    _nucleoli_detector(monkeypatch, states)
    execute(store, settings, compartment_config(config), "nucleoli")
    client, app, _ = authenticated(tmp_path / "private")  # the API over the worker's data directory
    mine = client.post("/v1/workspaces", headers=HEADERS, json={"title": "owner"}).json()["id"]
    with app.state.store.transaction() as conn:
        owner = conn.execute(select(workspaces.c.owner).where(workspaces.c.id == mine)).scalar_one()
        conn.execute(update(workspaces).where(workspaces.c.id == "w").values(owner=owner))
    return client, app.state.store, config


def _get(client, rid="nuclear", **params):
    return client.get(f"/v1/revisions/{rid}/nucleus-table", headers=HEADERS, params={"field_id": "f1", **params})


def test_api_confirms_only_adopted_candidate_nucleoli_and_downloads_the_same_table(tmp_path, monkeypatch):
    client, store, config = _api(tmp_path, monkeypatch, {"7": "candidate", "19": "review_required"})
    unadopted = _get(client, nucleolar_revision_id="nucleoli")
    assert unadopted.status_code == 200, unadopted.text
    assert not unadopted.json()["nuclear_adopted"]
    assert {row["nucleoli"]["reason"] for row in unadopted.json()["rows"]} == {"nucleolar_revision_not_adopted"}

    selection = client.get("/v1/workspaces/w/selection", headers=HEADERS).json()
    entries = [{**entry, "target_revisions": {"nuclei": "nuclear", "nucleoli": "nucleoli"}} if entry["field_id"] == "f1" else entry
               for entry in selection["entries"]] or [{"id": "e1", "field_id": "f1", "target_revisions": {"nuclei": "nuclear", "nucleoli": "nucleoli"}}]
    adopted = client.post("/v1/workspaces/w/selection", headers=HEADERS, json={"version": selection["version"], "entries": entries})
    assert adopted.status_code == 200, adopted.text
    table = _get(client, nucleolar_revision_id="nucleoli").json()
    assert table["nuclear_adopted"] and table["nucleolar_source"]["adopted"] and table["nuclear_channel_id"] == "dna"
    saved = read_json(store.safe_path("results", "nuclear", "measurements.json"))["field_tables"]["f1"]["rows"]
    rows = {row["nucleus_id"]: row for row in table["rows"]}
    first = rows[7]
    assert first["nucleus_area_px"] == 4 and first["nucleus_area_um2"] == pytest.approx(4 * 0.2 * 0.5)
    assert [(item["channel_id"], item["role"]) for item in first["channels"]] == [("dna", "nuclear_stain"), ("actin", "measure")]
    expected = {(row["region_id"], row["channel_id"]): row["integrated"] for row in saved}
    assert all(item["integrated"] == expected[(7, item["channel_id"])] for item in first["channels"])
    assert first["nucleoli"] == {
        "status": "measured", "reason": None, "count": 1, "union_area_px": 2,
        "union_area_um2": pytest.approx(2 * 0.1), "area_fraction": 0.5, "largest_object_area_px": 2,
        "largest_object_fraction": 1.0, "eccentricity": 1.0, "eccentricity_missing_reason": None, "excluded_objects": 0}
    # The retained review candidate stays in the mask but the nucleus is not confirmed.
    assert (rows[19]["nucleoli"]["status"], rows[19]["nucleoli"]["reason"], rows[19]["nucleoli"]["count"]) == ("missing", "review_required", None)

    download = client.get("/v1/revisions/nuclear/nucleus-table.zip", headers=HEADERS,
                          params={"field_id": "f1", "nucleolar_revision_id": "nucleoli"})
    assert download.status_code == 200 and download.headers["content-type"] == "application/zip"
    archive = zipfile.ZipFile(io.BytesIO(download.content))
    assert sorted(archive.namelist()) == ["columns.csv", "nucleus-table.csv", "nucleus-table.json"]
    assert json.loads(archive.read("nucleus-table.json")) == table
    csv_rows = {row["nucleus_id"]: row for row in csv.DictReader(io.StringIO(archive.read("nucleus-table.csv").decode("utf-8-sig")))}
    assert (csv_rows["7"]["nucleolar_status"], csv_rows["19"]["nucleolar_status"], csv_rows["19"]["nucleolar_reason"]) == ("measured", "missing", "review_required")

    alone = _get(client).json()
    assert {row["nucleoli"]["reason"] for row in alone["rows"]} == {"nucleolar_revision_not_selected"}


def test_api_reads_only_detected_nuclei_and_nucleoli_derived_from_them(tmp_path, monkeypatch):
    client, store, config = _api(tmp_path, monkeypatch, {"7": "candidate", "19": "candidate"})
    # Another region set (here the nucleoli themselves) is never returned as nuclei with a DNA signal.
    wrong = _get(client, rid="nucleoli")
    assert wrong.status_code == 422 and wrong.json()["detail"] == "nucleus_table_nuclear_source_required"
    path = store.safe_path("results", "nucleoli", "provenance.json")
    provenance = read_json(path)
    provenance["fields"]["f1"]["nuclear_source"]["mask_sha256"] = "0" * 64
    write_json(path, provenance)
    mismatch = _get(client, nucleolar_revision_id="nucleoli")
    assert mismatch.status_code == 409 and mismatch.json()["detail"] == "nucleus_table_nucleolar_source_mismatch"
    with store.transaction() as conn:
        from cytellect_api.db import revisions
        conn.execute(update(revisions).where(revisions.c.id == "nucleoli").values(config=compartment_config(config, source="other")))
    invalid = _get(client, nucleolar_revision_id="nucleoli")
    assert invalid.status_code == 422 and invalid.json()["detail"] == "nucleus_table_nucleolar_source_invalid"

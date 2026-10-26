"""API and worker on committed public JUMP/DS6a images and adopted masks.

The archive is copied to an isolated store; nothing in the public demo is edited.
Selection is first succeeded single-field revision by ID, before reading values.
No detector or measurement parameter is fitted in this test.
"""
import hashlib
import json
import time
import zipfile
from pathlib import Path

import pytest
from cytellect_analysis.region_exports import _recompute_statistics
from cytellect_api.db import jobs, revisions, workspaces
from cytellect_api.storage import read_json
from cytellect_worker.compartment_sources import load_compartment_summaries, load_nucleolar_shapes
from cytellect_worker.main import process_one
from cytellect_worker.region_export_sources import collect_dependencies
from sqlalchemy import select, update
from test_api_worker import HEADERS, authenticated


@pytest.fixture(scope="module")
def public_store(tmp_path_factory):
    root = Path(__file__).resolve().parents[1] / "apps/web/public/showcase"
    archive = root / "seed.zip"
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf8"))
    # Seed is already registered, publicly redistributable and hash-bound by its manifest.
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest["files"]["seed.zip"]["sha256"]
    folder = tmp_path_factory.mktemp("public-summary-store")
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(folder)
    from cytellect_showcase.seed import restore
    restore(folder)
    client, app, settings = authenticated(folder)
    store = app.state.store
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title":"Public summary test"}).json()["id"]
    owner = store.one(workspaces, id=wid)["owner"]
    with store.transaction() as conn:
        # Only this copied public seed is bound to the temporary test session.
        conn.execute(update(workspaces).values(owner=owner, expires=time.time()+3600))
        saved = [dict(row) for row in conn.execute(select(revisions).order_by(revisions.c.id)).mappings()]
    selected = {}
    for rev in saved:
        if rev["state"] != "succeeded" or len(rev["config"].get("field_ids", [])) != 1:
            continue
        recipe = rev["config"].get("recipe", {})
        key = "compartment" if recipe.get("compartment") == "nucleoplasm" else "field" if recipe.get("source") == "stardist_nuclear" else None
        if key and key not in selected:
            selected[key] = rev
    assert set(selected) == {"field", "compartment"}
    # Exercise the ordinary review transition for this software test; it is not
    # a biological validation of segmentation or an independence confirmation.
    for rev in selected.values():
        response = client.post(f"/v1/revisions/{rev['id']}/review", headers=HEADERS)
        assert response.status_code == 200, response.text
    yield client, store, settings, selected
    client.close()
    store.engine.dispose()


@pytest.mark.parametrize("metric, kind", [
    ("nucleus_count","field"), ("nucleus_density_per_mm2","field"),
    ("nucleolar_area_px","compartment"), ("nucleolar_area_um2","compartment"), ("nucleolar_eccentricity","compartment")])
def test_public_api_worker_saved_values(public_store, metric, kind):
    client, store, settings, selected = public_store
    rev = selected[kind]
    report = read_json(store.safe_path(rev["result_dir"], "measurements.json"))
    request = {"mode":"descriptive", "selection":{"source":"field-summary" if kind == "field" else "compartment-summary",
        "version":"1.0.0" if kind == "field" else "1.1.0", "region_set_id":rev["config"]["recipe"]["region_set_id"], "metric":metric},
        "plot":{"preset":"nature-double", "language":"en"}, "figure_policy":{"version":"2.0.0", "layout":"field-pages"}}
    response = client.post(f"/v1/revisions/{rev['id']}/descriptive", headers=HEADERS, json=request)
    assert response.status_code == 202, response.text
    jid = response.json()["job_id"]
    assert process_one(store, settings)
    job = store.one(jobs, id=jid)
    assert job["state"] == "succeeded", job.get("error")
    result = client.get(f"/v1/jobs/{jid}/result").json()
    assert result["figure"]["status"] == "ready"
    fid = rev["config"]["field_ids"][0]
    if kind == "field":
        count = len({row["region_id"] for row in report["field_tables"][fid]["rows"]})
        calibration = rev["config"]["field_snapshot"][fid]["image_info"]["calibration"]
        shape = rev["config"]["field_snapshot"][fid]["image_info"]["shape"]
        expected = count if metric == "nucleus_count" else count / (shape[0]*shape[1]*calibration["pixel_size_x_um"]*calibration["pixel_size_y_um"]/1e6)
        assert [row["value"] for row in result["plot_data"]] == pytest.approx([expected])
    else:
        summaries = load_compartment_summaries(store, rev, report)
        rows = next(iter(summaries[fid]["channels"].values()))["rows"]
        calibration = rev["config"]["field_snapshot"][fid]["image_info"]["calibration"]
        shapes = load_nucleolar_shapes(store, rev, report, summaries) if metric == "nucleolar_eccentricity" else None
        expected = {row["nucleus_id"]:(shapes[fid][row["nucleus_id"]][metric] if shapes is not None else
                    row["nucleolar_area_px"] * (calibration["pixel_size_x_um"]*calibration["pixel_size_y_um"] if metric.endswith("um2") else 1))
                    for row in rows if row["nucleolar_count"]}
        assert {row["nucleus_id"]:row["value"] for row in result["plot_data"]} == pytest.approx(expected)
    fresh = store.one(revisions, id=rev["id"])
    provenance = read_json(store.safe_path(rev["result_dir"], "provenance.json"))
    dependencies = collect_dependencies(store, fresh, report, provenance)
    replayed = _recompute_statistics(report, {**fresh["config"], "review_record":fresh["review_record"]}, result, dependencies)
    assert replayed == {key:value for key,value in result.items() if key != "figure"}
    assert client.get(f"/v1/jobs/{jid}/files/figure.zip").status_code == 200
    assert "comparisons" not in result
    assert result["counts"]["experimental_units"] is None

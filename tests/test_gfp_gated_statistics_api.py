"""GFP nucleus filter through the owned API, worker jobs, figures and export (synthetic pixels)."""
import json

import numpy as np
import pytest
from cytellect_worker.main import process_one
from cytellect_worker.regions import run_region_analysis
from scipy import stats
from test_api_worker import HEADERS, authenticated
from test_region_api import tiff_bytes

RECIPE = {"version": "1.2.0", "region_set_id": "nuclei", "label": "Nuclei", "source": "stardist_nuclear",
          "defining_channel_id": "dna", "nuclear_role_source": "recorded_stain"}
RAW = {"version": "1.1.0", "mode": "raw_intensity"}
CHANNELS = [{"channel_id": "dna", "label": "DNA", "stain": "Hoechst 33342", "identity_source": "filename"},
            {"channel_id": "gfp", "label": "GFP", "stain": "EGFP", "identity_source": "filename"},
            {"channel_id": "ncl", "label": "NCL", "stain": "anti-nucleolin", "identity_source": "filename"}]
# field -> (condition, unit, [(gfp, ncl), ...]) on one acquisition date.
FIELDS = {"control": ("untransfected", "u0", [(100 + i, 1) for i in range(25)]),
          "a1": ("A", "a1", [(300, 10), (300, 14), (50, 100)]), "a2": ("A", "a2", [(400, 20), (60, 200)]),
          "a3": ("A", "a3", [(500, 30), (500, 34)]), "b1": ("B", "b1", [(300, 40), (300, 44), (70, 500)]),
          "b2": ("B", "b2", [(250, 50), (80, 600)]), "b3": ("B", "b3", [(300, 60), (300, 62)])}
POSITIVE_UNITS = {"a1": 12.0, "a2": 20.0, "a3": 32.0, "b1": 42.0, "b2": 50.0, "b3": 61.0}


def detected(image, *args, **kwargs):
    # Nucleus identity is carried by the synthetic DNA plane: value 1000 + nucleus ID.
    return np.where(image >= 1000, image.astype(np.int64) - 1000, 0).astype(np.uint32), {"engine": "test-fixture"}


def reviewed_nuclei(client, app, settings, monkeypatch):
    monkeypatch.setattr("cytellect_worker.regions.detect_nuclei", detected)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Synthetic GFP fixture"}).json()["id"]
    ids = {}
    for name, (condition, unit, nuclei) in FIELDS.items():
        planes = {key: np.full((5, 2 * len(nuclei) + 3), 5, np.uint16) for key in ("dna", "gfp", "ncl")}
        for index, (gfp, ncl) in enumerate(nuclei):
            planes["dna"][2, 2 * index + 1] = 1001 + index
            planes["gfp"][2, 2 * index + 1] = gfp
            planes["ncl"][2, 2 * index + 1] = ncl
        spec = {"version": "1.1.0", "channels": CHANNELS,
                "metadata": {"condition": condition, "experimental_unit": unit, "sample": f"s-{unit}",
                             "acquisition_date": "d1"}}
        uploaded = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                               data={"specification": json.dumps(spec)},
                               files={f"ch{i}": (f"{key}.tif", tiff_bytes(planes[key]), "image/tiff")
                                      for i, key in enumerate(("dna", "gfp", "ncl"))})
        assert uploaded.status_code == 201, uploaded.text
        ids[name] = uploaded.json()["id"]
    accepted = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS,
                           json={"field_ids": list(ids.values()), "recipe": RECIPE, "measurement": RAW, "backgrounds": {}})
    assert accepted.status_code == 202, accepted.text
    rid = accepted.json()["revision_id"]
    claimed = app.state.store.claim()
    output = app.state.store.safe_path("results", claimed["id"])
    run_region_analysis(app.state.store, settings, claimed, output)
    assert app.state.store.finish(claimed, app.state.store.relative_path(output))
    reviewed = client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={})
    assert reviewed.status_code == 200, reviewed.text
    return wid, rid, ids


def gate(ids, **changes):
    return {"version": "1.0.0", "gate_protocol": "gfp-gate/2.0.0", "gfp_channel_id": "gfp", "percentile": 99,
            "control_field_ids": [ids["control"]], "keep": "positive", **changes}


def comparison(selection):
    return {"mode": "region-experimental-unit", "version": "2.0.0", "test": "welch-t", "selection": selection,
            "design": {"kind": "independent", "confirmed": True, "unit_definition": "Independently transfected cultures"},
            "conditions": ["A", "B"], "comparison_family": {"family_id": "primary", "kind": "control", "control": "A",
                                                            "contrasts": [["A", "B"]]},
            "acquisition_review": {"confirmed": True, "basis": "same-settings"}, "missingness_confirmed": True,
            "plot": {"kind": "box", "language": "en", "y_label": "NCL mean"}}


def selection(ids, **changes):
    return {"source": "region", "region_set_id": "nuclei", "channel_id": "ncl", "metric": "mean",
            "gfp_gate": gate(ids, **changes)}


def test_gated_comparison_description_and_export_through_jobs(tmp_path, monkeypatch):
    client, app, settings = authenticated(tmp_path)
    wid, rid, ids = reviewed_nuclei(client, app, settings, monkeypatch)
    response = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=comparison(selection(ids)))
    assert response.status_code == 202, response.text
    jid = response.json()["job_id"]
    process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{jid}").json()
    assert job["state"] == "succeeded", job
    value = client.get(f"/v1/jobs/{jid}/common-statistics").json()
    record = value["selection"]["gfp_gate"]
    assert record["dates"]["d1"]["threshold"] == pytest.approx(123.76, abs=1e-12)
    assert record["dates"]["d1"]["control_nuclei"] == 25 and record["nuclear_binding"] == "same_revision"
    assert record["control_field_ids"] == [ids["control"]]
    assert value["spec"]["selection"]["gfp_gate"]["keep"] == "positive"
    units = {row["experimental_unit"]: row["value"] for row in value["unit_summary"]}
    assert units == POSITIVE_UNITS
    a, b = [POSITIVE_UNITS[u] for u in ("a1", "a2", "a3")], [POSITIVE_UNITS[u] for u in ("b1", "b2", "b3")]
    assert value["comparisons"][0]["p_value"] == pytest.approx(stats.ttest_ind(a, b, equal_var=False).pvalue)
    methods = client.get(f"/v1/jobs/{jid}/files/methods.md").text
    assert "GFP gate filter 1.0.0" in methods and "d1: threshold 123.76 from 25 control nuclei" in methods

    described = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json={
        "mode": "descriptive", "selection": selection(ids), "plot": {"preset": "nature-double"},
        "figure_policy": {"version": "2.0.0", "layout": "field-pages"}})
    assert described.status_code == 202, described.text
    process_one(app.state.store, settings)
    description = client.get(f"/v1/jobs/{described.json()['job_id']}/result").json()
    summary = {row["field_id"]: row for row in description["field_summary"]}
    assert summary[ids["control"]]["status"] == "gfp_negative_control"
    assert summary[ids["b1"]]["median"] == 42.0
    assert description["selection"]["gfp_gate"]["kept_observations"] == 10

    exported = client.post(f"/v1/revisions/{rid}/export", headers=HEADERS)
    assert exported.status_code == 202, exported.text
    process_one(app.state.store, settings)
    summary = client.get(f"/v1/jobs/{exported.json()['job_id']}/result").json()
    assert {row["reason"] for row in summary["statistics_omitted"]} == {"region_export_gfp_gate_unsupported"}
    assert len(summary["statistics_omitted"]) == 2
    client.close()
    app.state.store.engine.dispose()


def test_gated_requests_are_refused_with_safe_codes(tmp_path, monkeypatch):
    client, app, settings = authenticated(tmp_path)
    wid, rid, ids = reviewed_nuclei(client, app, settings, monkeypatch)
    url = f"/v1/revisions/{rid}/common-statistics"
    for changes, code in (({"control_field_ids": ["unknown-field"]}, "gfp_gate_unknown_control_field"),
                          ({"gfp_channel_id": "mcherry"}, "gfp_gate_channel_unknown")):
        response = client.post(url, headers=HEADERS, json=comparison(selection(ids, **changes)))
        assert response.status_code == 422 and response.json()["detail"] == code, response.text
    for changes in ({"percentile": 100}, {"percentile": 40}, {"control_field_ids": [ids["control"]] * 2}, {"keep": "both"}):
        assert client.post(url, headers=HEADERS, json=comparison(selection(ids, **changes))).status_code == 422
    v1 = {key: value for key, value in comparison(selection(ids)).items() if key not in ("version", "test", "plot")}
    response = client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS, json=v1)
    assert response.status_code == 422  # contract refusal (sanitised validation detail)
    association = {**{key: value for key, value in comparison(selection(ids)).items()
                      if key not in ("selection", "comparison_family", "test", "plot")},
                   "mode": "region-association", "version": "1.0.0", "x_selection": selection(ids),
                   "y_selection": {**selection(ids), "channel_id": "gfp"}, "method": "spearman"}
    response = client.post(url, headers=HEADERS, json=association)
    assert response.status_code == 422  # contract refusal (sanitised validation detail)
    # The same bodies without the filter are accepted, so the refusals above are the filter's.
    ungated = {key: value for key, value in selection(ids).items() if key != "gfp_gate"}
    assert client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS,
                       json={**v1, "selection": ungated}).status_code == 202
    assert client.post(url, headers=HEADERS, json={**association, "x_selection": ungated,
                                                   "y_selection": {**ungated, "channel_id": "gfp"}}).status_code == 202
    response = client.post(f"/v1/revisions/{rid}/descriptive-preview", headers=HEADERS,
                           json={"mode": "descriptive", "selection": selection(ids)})
    assert response.status_code == 422 and response.json()["detail"] == "gfp_gate_preview_unsupported"
    # Comparing the condition that only supplied control fields is refused in the job.
    response = client.post(url, headers=HEADERS, json={**comparison(selection(ids)), "conditions": ["A", "untransfected"],
                                                     "comparison_family": {"family_id": "primary", "kind": "control",
                                                                           "control": "A",
                                                                           "contrasts": [["A", "untransfected"]]}})
    assert response.status_code == 202
    for _ in range(3):
        process_one(app.state.store, settings)
    states = [job for job in client.get(f"/v1/workspaces/{wid}/jobs").json() if job["kind"] == "statistics"]
    errors = sorted(job["error"] for job in states if job["state"] == "failed")
    assert errors == ["gfp_gate_condition_only_control_fields"], states
    client.close()
    app.state.store.engine.dispose()


class FakeStore:
    def __init__(self, root, rows):
        self.root, self.rows = root, rows

    def one(self, table, id):
        return self.rows.get(id)

    def safe_path(self, *parts):
        return self.root.joinpath(*parts)


def write(path, value):
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_nucleoplasm_revision_binds_the_recorded_nuclear_mask_exactly(tmp_path):
    from cytellect_worker.gfp_sources import load_gfp_nuclear_source
    from test_gfp_gated_statistics import compartment_fixture

    report, config, _, expected = compartment_fixture()
    nuclear_report = {"revision_id": "rev_nuclei", "exclusions": [],
                      "field_tables": {fid: entry["table"] for fid, entry in expected["fields"].items()},
                      "field_masks": {fid: {"mask_revision_id": "rev_nuclei", "mask_sha256": entry["mask_sha256"]}
                                      for fid, entry in expected["fields"].items()}}
    provenance = {"fields": {fid: {"nuclear_source": {"revision_id": "rev_nuclei", "mask_revision_id": "rev_nuclei",
                                                      "mask_sha256": entry["mask_sha256"], "exclusions": []}}
                             for fid, entry in expected["fields"].items()}}
    write(tmp_path / "np" / "provenance.json", provenance)
    write(tmp_path / "nuclei" / "measurements.json", nuclear_report)
    nuclear = {"id": "rev_nuclei", "workspace_id": "w", "state": "succeeded", "result_dir": "nuclei",
               "config": {"analysis_kind": "region-2d", "recipe": {"source": "stardist_nuclear"},
                          "field_snapshot": config["field_snapshot"]}}
    rev = {"id": "rev_np", "workspace_id": "w", "result_dir": "np", "config": config}
    store = FakeStore(tmp_path, {"rev_nuclei": nuclear})
    bound = load_gfp_nuclear_source(store, rev, report)
    assert bound["binding"] == "parent_nucleus" and set(bound["fields"]) == set(expected["fields"])
    assert bound["fields"]["a1"]["table"] == expected["fields"]["a1"]["table"]
    assert len(bound["fields"]["a1"]["report_sha256"]) == 64
    nuclear_rev = {**rev, "config": {**config, "recipe": {"source": "stardist_nuclear"}}}
    assert load_gfp_nuclear_source(store, nuclear_rev, report) is None
    nucleoli_rev = {**rev, "config": {**config, "recipe": {**config["recipe"], "compartment": "nucleoli"}}}
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        load_gfp_nuclear_source(store, nucleoli_rev, report)
    original = provenance["fields"]["b2"]["nuclear_source"]
    provenance["fields"]["b2"]["nuclear_source"] = {**original, "mask_sha256": "0" * 64}
    write(tmp_path / "np" / "provenance.json", provenance)
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        load_gfp_nuclear_source(store, rev, report)
    provenance["fields"]["b2"]["nuclear_source"] = {**original, "exclusions": [
        {"field_id": "b2", "region_id": 1, "region_set_id": "nuclei", "reason": "Debris"}]}
    write(tmp_path / "np" / "provenance.json", provenance)
    with pytest.raises(ValueError, match="gfp_gate_nuclear_identity_mismatch"):
        load_gfp_nuclear_source(store, rev, report)
    del provenance["fields"]["b2"]["nuclear_source"]
    write(tmp_path / "np" / "provenance.json", provenance)
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        load_gfp_nuclear_source(store, rev, report)
    provenance["fields"]["b2"]["nuclear_source"] = original
    write(tmp_path / "np" / "provenance.json", provenance)
    nuclear["config"]["recipe"] = {"source": "manual"}
    with pytest.raises(ValueError, match="gfp_gate_nuclear_source_unbound"):
        load_gfp_nuclear_source(store, rev, report)

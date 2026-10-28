"""Unresolved nucleoli kept as missing (requirements Q-05, genellect/cytellect#109) through the API.

The fixture is the four-field arithmetic revision of the comparison tests, recorded as a nucleolar
compartment: field 1 has one nucleus without an established nucleolus. Detection itself is covered
by the compartment engine tests; here only the recorded states, the review and the statistics count.
"""
import copy
import json

import numpy as np
from cytellect_analysis.compartment_review import MISSING_POLICY
from cytellect_api.db import jobs, revisions
from cytellect_api.storage import read_json
from cytellect_worker.main import process_one
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated
from test_common_statistics_api import common_request
from test_region_api import region_request, tiff_bytes


def compartment_revision(client, app, settings, states=None):
    """Four measured fields (A: culture-0/1, B: culture-2/3), recorded as nucleoli with parent states."""
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Unresolved nucleoli"}).json()["id"]
    fids = []
    for index, value in enumerate([2, 4, 5, 7]):
        pixels = np.full((12, 12), 10, np.uint16)
        pixels[4:6, 4:6] = 10 + value
        labels = np.zeros((12, 12), np.uint32)
        labels[4:6, 4:6] = 1
        specification = {"channels": [{"channel_id": "marker", "label": "Measured marker",
                                       "stain": "Fixture fluorescence", "identity_confirmed": True}],
                         "metadata": {"condition": "A" if index < 2 else "B", "sample": f"sample-{index}",
                                      "experimental_unit": f"culture-{index}", "acquisition_date": "batch-1"}}
        response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS,
                               data={"specification": json.dumps(specification)}, files={
                                   "ch0": ("image.tif", tiff_bytes(pixels), "image/tiff"),
                                   "labels": ("labels.tif", tiff_bytes(labels), "image/tiff")})
        assert response.status_code == 201, response.text
        fids.append(response.json()["id"])
    body = region_request(fids[0])
    background = body["backgrounds"][fids[0]]["actin"]
    body.update(field_ids=fids, backgrounds={fid: {"marker": background} for fid in fids})
    rid = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body).json()["revision_id"]
    process_one(app.state.store, settings)
    store = app.state.store
    saved = store.one(revisions, id=rid)
    assert saved["state"] == "succeeded"
    config = copy.deepcopy(saved["config"])
    config["recipe"].update(source="fiji_nuclear_compartment", compartment="nucleoli")
    with store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == rid).values(config=config))
    report_path = store.safe_path(saved["result_dir"], "measurements.json")
    report = read_json(report_path)
    report["recipe"] = config["recipe"]
    report_path.write_text(json.dumps(report), encoding="utf-8")
    record_states(store, rid, states or {fids[0]: {1: "candidate", 2: "no_candidate"}})
    return wid, rid, fids


def record_states(store, rid, states):
    path = store.safe_path(store.one(revisions, id=rid)["result_dir"], "provenance.json")
    provenance = read_json(path)
    for fid in provenance["fields"]:
        parents = {str(parent): state for parent, state in states.get(fid, {1: "candidate"}).items()}
        provenance["fields"][fid]["detector"] = {"engine": {
            "nucleolar_states": parents, "missing_parent_count": sum(state != "candidate" for state in parents.values()),
            "nucleoplasm_missing_reasons": {}}}
    path.write_text(json.dumps(provenance), encoding="utf-8")


def confirm(client, rid, confirmed):
    return client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={
        "accept_invalidated_fields": [], "compartment_missing": {"policy": MISSING_POLICY, "confirmed": confirmed}})


def test_review_keeps_unresolved_nuclei_only_with_the_exact_confirmed_list(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, rid, fids = compartment_revision(client, app, settings)
    # Without the policy the review still requires every nucleolus to be established.
    refused = client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={})
    assert refused.status_code == 409 and refused.json()["detail"] == "unresolved_nuclear_compartments"
    ledger = client.get(f"/v1/revisions/{rid}/compartment-ledger", headers=HEADERS).json()
    assert ledger["policy"] == MISSING_POLICY
    assert ledger["fields"][fids[0]] == {"nuclei": 2, "resolved": 1, "missing": {"no_candidate": 1}, "excluded": 0}
    assert ledger["fields"][fids[3]] == {"nuclei": 1, "resolved": 1, "missing": {}, "excluded": 0}
    single = client.get(f"/v1/revisions/{rid}/compartment-ledger?field_id={fids[1]}", headers=HEADERS).json()
    assert set(single["fields"]) == {fids[1]}
    # A blanket or wrong confirmation is not accepted.
    for wrong in ({}, {fids[0]: {"indeterminate": 1}}, {fids[0]: {"no_candidate": 1}, fids[1]: {"no_candidate": 1}}):
        response = confirm(client, rid, wrong)
        assert response.status_code == 409 and response.json()["detail"] == "compartment_missing_confirmation_mismatch"
    assert confirm(client, rid, {fids[0]: {"no_candidate": 1}}).status_code == 200
    record = app.state.store.one(revisions, id=rid)["review_record"]
    assert record["compartment_missing"] == {"policy": MISSING_POLICY, "fields": ledger["fields"]}


def test_comparison_and_description_show_the_denominators_and_warn_on_different_missing_rates(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, rid, fids = compartment_revision(client, app, settings)
    assert confirm(client, rid, {fids[0]: {"no_candidate": 1}}).status_code == 200
    response = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=common_request())
    assert response.status_code == 202, response.text
    jid = response.json()["job_id"]
    process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{jid}").json()["state"] == "succeeded"
    value = client.get(f"/v1/jobs/{jid}/common-statistics").json()
    missing = value["compartment_missing"]
    assert missing["policy"] == MISSING_POLICY and missing["warning_points"] == 10
    assert [(row["condition"], row["experimental_unit"], row["nuclei"], row["resolved"], row["missing"])
            for row in missing["rows"]] == [("A", "culture-0", 2, 1, 1), ("A", "culture-1", 1, 1, 0),
                                            ("B", "culture-2", 1, 1, 0), ("B", "culture-3", 1, 1, 0)]
    # A misses 1 of 3 nuclei, B none: 33.3 points apart (no runs: the groups form one run).
    assert missing["warnings"] == [{"run": None, "difference_points": 33.3, "fractions": {"A": 0.3333, "B": 0.0}}]
    assert "compartment_missing_rate_differs" in value["warnings"]
    assert "compartment-missing.csv" in value["figure"]["source_files"]
    csv = client.get(f"/v1/jobs/{jid}/files/compartment-missing.csv")
    assert csv.status_code == 200 and "culture-0" in csv.text and "no_candidate=1" in csv.text
    assert "Unresolved nucleoli (unresolved-as-missing/1.0.0)" in client.get(f"/v1/jobs/{jid}/files/methods.md").text
    # The policy is for comparisons and descriptions; an association has no place for the ledger.
    association = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=common_request(True))
    assert association.status_code == 409 and association.json()["detail"] == "compartment_missing_association_unsupported"
    described = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json={
        "mode": "descriptive", "selection": {"source": "region", "region_set_id": "objects", "channel_id": "marker",
                                             "metric": "mean"}, "plot": {"language": "en"}})
    assert described.status_code == 202, described.text
    process_one(app.state.store, settings)
    result = client.get(f"/v1/jobs/{described.json()['job_id']}/result").json()
    assert result["compartment_missing"]["rows"] == missing["rows"]
    assert "compartment_missing_rate_differs" in result["warnings"]
    # Export and replay recompute both results from the saved review record with the same ledger.
    from cytellect_analysis.region_exports import _recompute_statistics
    store = app.state.store
    saved = store.one(revisions, id=rid)
    report = read_json(store.safe_path(saved["result_dir"], "measurements.json"))
    config = {**saved["config"], "review_record": saved["review_record"]}
    provenance = read_json(store.safe_path(saved["result_dir"], "provenance.json"))
    for job_id in (jid, described.json()["job_id"]):
        stored = read_json(store.safe_path(store.one(jobs, id=job_id)["result_dir"], "result.json"))
        assert _recompute_statistics(report, config, stored, provenance=provenance) == {
            key: item for key, item in stored.items() if key != "figure"}


def test_a_changed_ledger_or_a_failed_nucleus_still_stops(tmp_path):
    client, app, settings = authenticated(tmp_path)
    _, rid, fids = compartment_revision(client, app, settings)
    assert confirm(client, rid, {fids[0]: {"no_candidate": 1}}).status_code == 200
    record_states(app.state.store, rid, {fids[0]: {1: "candidate", 2: "indeterminate"}})
    response = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=common_request())
    assert response.status_code == 409 and response.json()["detail"] == "compartment_missing_ledger_changed"

    _, failed, fids = compartment_revision(client, app, settings, {})
    record_states(app.state.store, failed, {fids[0]: {1: "candidate", 2: "processing_failed"}})
    ledger = client.get(f"/v1/revisions/{failed}/compartment-ledger", headers=HEADERS)
    assert ledger.status_code == 409 and ledger.json()["detail"] == "compartment_state_not_missing"
    response = confirm(client, failed, {fids[0]: {"processing_failed": 1}})
    assert response.status_code == 409 and response.json()["detail"] == "compartment_state_not_missing"


def test_policy_is_refused_where_there_are_no_compartments(tmp_path):
    from test_region_comparison_api import reviewed_units

    client, app, settings = authenticated(tmp_path)
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "plain"}).json()["id"]
    _, rid, _ = reviewed_units(client, app, settings)
    assert client.get(f"/v1/revisions/{rid}/compartment-ledger", headers=HEADERS).status_code == 409
    assert wid

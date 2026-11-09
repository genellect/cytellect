"""Declared strata (experiment design 1.1.0): one stratum per formal aggregation, never pooled.

Synthetic 12 x 12 numeric fields only check the contract arithmetic and refusals (which fields
enter, which requests are refused, what is recorded); they are not biological evidence."""
import io
import json
import zipfile

import numpy as np
import pytest
from cytellect_analysis.experiment_design import (
    ExperimentDesign,
    StratifiedExperimentDesign,
    field_metadata,
    parse_design,
    readiness,
)
from cytellect_analysis.experiment_strata import (
    CohortStratum,
    check_cohort_stratum,
    check_source_strata,
    design_sha256,
    stratum_methods_lines,
    stratum_record,
)
from cytellect_analysis.region_exports import replay_region_bundle
from cytellect_api.db import revisions
from cytellect_worker.main import process_one
from pydantic import ValidationError
from sqlalchemy import update
from test_api_worker import HEADERS, authenticated
from test_region_api import region_request, tiff_bytes
from test_region_comparison_api import comparison_request

V10 = {"version": "1.0.0", "layout": "pair", "groups": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
       "control_group_id": "a", "runs": [{"id": "r1", "label": "R1", "performed_on": None, "acquired_on": "2026-01-01"}],
       "independence_confirmed": True, "fields": {"f1": {"group_id": "a", "run_id": "r1", "sample": None, "acquired_on": None}}}


def stratified(fields, *, levels=("level-a", "level-b")):
    return {"version": "1.1.0", "layout": "pair", "groups": [{"id": "a", "label": "A"}, {"id": "b", "label": "B"}],
            "control_group_id": "a",
            "runs": [{"id": "r1", "label": "R1", "performed_on": None, "acquired_on": "2026-01-01"},
                     {"id": "r2", "label": "R2", "performed_on": None, "acquired_on": "2026-01-02"}],
            "independence_confirmed": True,
            "factors": [{"id": "factor", "label": "Factor", "levels": [{"id": value, "label": value.upper()} for value in levels]}],
            "strata": [{"id": f"s-{value}", "label": value.upper(), "levels": {"factor": value}} for value in levels],
            "fields": fields}


def members(layout):
    """{field_id: (stratum, run, group)} for every combination: 2 strata x 2 runs x 2 groups."""
    return {f"f-{s}-{r}-{g}": (s, r, g) for s in ("level-a", "level-b") for r in ("r1", "r2") for g in ("a", "b")}


def assignments():
    return {fid: {"group_id": g, "run_id": r, "sample": None, "acquired_on": None, "stratum_id": f"s-{s}"}
            for fid, (s, r, g) in members(None).items()}


def test_version_1_0_0_keeps_its_model_and_bytes():
    parsed = parse_design(V10)
    assert isinstance(parsed, ExperimentDesign) and parsed.model_dump(mode="json") == V10
    without_version = {key: value for key, value in V10.items() if key != "version"}
    assert parse_design(without_version).model_dump(mode="json") == V10
    assert json.dumps(ExperimentDesign.model_validate(V10).model_dump(mode="json")) == json.dumps(V10)


def test_strata_are_declared_explicitly_and_never_inferred():
    design = parse_design(stratified(assignments()))
    assert isinstance(design, StratifiedExperimentDesign)
    missing = assignments()
    del missing["f-level-a-r1-a"]["stratum_id"]
    # A field without its declared stratum is not completed by guessing: it stays unassigned and is named.
    unassigned = parse_design(stratified(missing))
    assert unassigned.fields["f-level-a-r1-a"].stratum_id is None
    assert {"code": "experiment_design_unstratified_fields", "field_ids": ["f-level-a-r1-a"]} in readiness(unassigned, missing)
    with pytest.raises(ValueError, match="comparison_stratum_unassigned"):
        check_source_strata(stratified(missing), {"field_ids": ["f-level-a-r1-a"]})
    unknown = assignments()
    unknown["f-level-a-r1-a"]["stratum_id"] = "s-level-c"
    with pytest.raises(ValidationError, match="experiment_design_unknown_stratum"):
        parse_design(stratified(unknown))
    partial = stratified(assignments())
    partial["strata"][0]["levels"] = {"factor": "level-c"}
    with pytest.raises(ValidationError, match="experiment_design_stratum_levels"):
        parse_design(partial)
    repeated = stratified(assignments())
    repeated["strata"][1]["levels"] = {"factor": "level-a"}
    with pytest.raises(ValidationError, match="experiment_design_duplicate"):
        parse_design(repeated)
    # Groups, runs and samples are unchanged by strata; a third group is still refused (two groups only).
    three = stratified(assignments())
    three["groups"].append({"id": "c", "label": "C"})
    with pytest.raises(ValidationError):
        parse_design(three)


def test_a_draft_with_factors_but_no_strata_saves_and_admits_no_cohort():
    """Factors can be saved before any stratum is declared; nothing is assigned or aggregated meanwhile."""
    draft = stratified({fid: {**value, "stratum_id": None} for fid, value in assignments().items()},
                       levels=("level-a", "level-b"))
    draft["factors"].append({"id": "factor-2", "label": "Factor 2", "levels": [{"id": "level-x", "label": "Level X"}]})
    draft["strata"] = []
    design = parse_design(draft)
    assert design.strata == [] and design.model_dump(mode="json") == draft
    issues = readiness(design, draft["fields"])
    assert {"code": "experiment_design_no_strata"} in issues
    assert {"code": "experiment_design_unstratified_fields", "field_ids": sorted(draft["fields"])} in issues
    request = CohortStratum(design_sha256=design_sha256(design), stratum_id="s-level-a")
    with pytest.raises(ValueError, match="cohort_stratum_empty"):
        check_cohort_stratum(design, request, ["f-level-a-r1-a"], [], field_metadata(design))
    # A stratum must name one level of every factor, including the one added later.
    draft["strata"] = [{"id": "s-level-a", "label": "LEVEL-A", "levels": {"factor": "level-a"}}]
    with pytest.raises(ValidationError, match="experiment_design_stratum_levels"):
        parse_design(draft)
    draft["strata"] = [{"id": "s-level-a-x", "label": "LEVEL-A / Level X", "levels": {"factor": "level-a", "factor-2": "level-x"}}]
    assert parse_design(draft).strata[0].levels == {"factor": "level-a", "factor-2": "level-x"}


def test_readiness_checks_each_stratum_without_pooling():
    fields = assignments()
    del fields["f-level-b-r2-b"]
    issues = readiness(parse_design(stratified(fields)), fields)
    assert {"code": "experiment_design_missing_combination", "run_id": "r2", "group_ids": ["b"],
            "stratum_id": "s-level-b"} in issues
    assert not any(issue.get("stratum_id") == "s-level-a" for issue in issues)


def test_cohort_takes_exactly_one_declared_stratum_with_the_derived_metadata():
    design = parse_design(stratified(assignments()))
    derived = {fid: value.model_dump(mode="json") for fid, value in field_metadata(design).items()}
    level_a = sorted(fid for fid, (s, _, _) in members(None).items() if s == "level-a")
    request = CohortStratum(design_sha256=design_sha256(design), stratum_id="s-level-a")
    record = check_cohort_stratum(design.model_dump(mode="json"), request, level_a, set(), derived)
    assert record["field_ids"] == level_a and record["levels"] == [
        {"factor_id": "factor", "factor": "Factor", "level_id": "level-a", "level": "LEVEL-A"}]
    with pytest.raises(ValueError, match="cohort_stratum_required"):
        check_cohort_stratum(design, None, level_a, set(), derived)
    with pytest.raises(ValueError, match="cohort_stratum_mixed"):
        check_cohort_stratum(design, request, [*level_a, "f-level-b-r1-a"], set(), derived)
    with pytest.raises(ValueError, match="cohort_stratum_incomplete"):
        check_cohort_stratum(design, request, level_a[1:], set(), derived)
    # A field excluded in the workspace counts for its own stratum only; the record keeps assigned,
    # analysed and excluded fields apart, and Methods states each count.
    kept = check_cohort_stratum(design, request, level_a[1:], {level_a[0], "f-level-b-r1-a"}, derived,
                                exclusion_reasons={level_a[0]: "out of focus", "f-level-b-r1-a": "other stratum"})
    assert (kept["field_ids"], kept["analysed_field_ids"], kept["excluded_fields"]) == (
        level_a, level_a[1:], [{"field_id": level_a[0], "reason": "out of focus"}])
    lines = " ".join(stratum_methods_lines(kept))
    assert "assigned 4 fields to this declared stratum; 3 were analysed and 1 were excluded" in lines
    relabelled = {**derived, level_a[0]: {**derived[level_a[0]], "condition": "B"}}
    with pytest.raises(ValueError, match="cohort_stratum_metadata_mismatch"):
        check_cohort_stratum(design, request, level_a, set(), relabelled)
    stale = CohortStratum(design_sha256="0" * 64, stratum_id="s-level-a")
    with pytest.raises(ValueError, match="cohort_stratum_design_changed"):
        check_cohort_stratum(design, stale, level_a, set(), derived)
    with pytest.raises(ValueError, match="cohort_stratum_without_design"):
        check_cohort_stratum(V10, request, ["f1"], set(), {"f1": {}})
    assert check_cohort_stratum(V10, None, ["f1"], set(), {"f1": {}}) is None


def test_descriptions_and_comparisons_read_one_stratum_of_the_saved_design():
    design = stratified(assignments())
    level_a = sorted(fid for fid, (s, _, _) in members(None).items() if s == "level-a")
    record = stratum_record(parse_design(design), "s-level-a")
    derived = {fid: {"metadata": value.model_dump(mode="json")} for fid, value in field_metadata(parse_design(design)).items()}
    snapshot = {fid: derived[fid] for fid in level_a}
    check_source_strata(design, {"field_snapshot": snapshot, "cohort_sources": {}, "stratum": record})
    # A metadata edit (for example a child that swaps groups) is refused under the same stratum and hash.
    swapped = {**snapshot, level_a[0]: {"metadata": {**snapshot[level_a[0]]["metadata"], "condition": "B"}}}
    with pytest.raises(ValueError, match="comparison_stratum_metadata_mismatch"):
        check_source_strata(design, {"field_snapshot": swapped, "cohort_sources": {}, "stratum": record})
    with pytest.raises(ValueError, match="comparison_stratum_required"):
        check_source_strata(design, {"field_ids": [level_a[0]]})  # one field's own revision carries no stratum
    with pytest.raises(ValueError, match="comparison_stratum_required"):
        check_source_strata(design, {"field_snapshot": dict.fromkeys(level_a, {}), "cohort_sources": {"x": {}}})
    with pytest.raises(ValueError, match="comparison_stratum_mixed"):
        check_source_strata(design, {"field_snapshot": dict.fromkeys([*level_a, "f-level-b-r1-a"], {}), "stratum": record})
    with pytest.raises(ValueError, match="comparison_stratum_unassigned"):
        check_source_strata(design, {"field_ids": ["elsewhere"]})
    moved = stratified({**assignments(), level_a[0]: {**assignments()[level_a[0]], "stratum_id": "s-level-b"}})
    with pytest.raises(ValueError, match="comparison_stratum_"):
        check_source_strata(moved, {"field_snapshot": snapshot, "cohort_sources": {}, "stratum": record})
    check_source_strata(V10, {"field_snapshot": {"f1": {}}, "cohort_sources": {}})  # unstratified: unchanged


# --- API: cohort, review, comparison, Methods and replay record of one stratum -------------------------------

VALUES = {"level-a": {"a": (2, 4), "b": (5, 7)}, "level-b": {"a": (40, 42), "b": (70, 90)}}


def _workspace(client, app, settings):
    wid = client.post("/v1/workspaces", headers=HEADERS, json={"title": "Strata"}).json()["id"]
    ids, sources = {}, {}
    for key, (stratum, run, group) in members(None).items():
        pixels = np.full((12, 12), 10, np.uint16)
        pixels[4:6, 4:6] = 10 + VALUES[stratum][group][int(run[-1]) - 1]
        labels = np.zeros((12, 12), np.uint32)
        labels[4:6, 4:6] = 1
        spec = {"channels": [{"channel_id": "marker", "label": "Measured marker", "stain": "Fixture fluorescence",
                              "identity_confirmed": True}]}
        response = client.post(f"/v1/workspaces/{wid}/region-fields", headers=HEADERS, data={"specification": json.dumps(spec)},
                               files={"ch0": ("image.tif", tiff_bytes(pixels), "image/tiff"),
                                      "labels": ("labels.tif", tiff_bytes(labels), "image/tiff")})
        assert response.status_code == 201, response.text
        fid = response.json()["id"]
        ids[key] = fid
        body = region_request(fid)
        body["backgrounds"] = {fid: {"marker": body["backgrounds"][fid]["actin"]}}
        queued = client.post(f"/v1/workspaces/{wid}/region-analyses", headers=HEADERS, json=body)
        assert queued.status_code == 202, queued.text
        process_one(app.state.store, settings)
        sources[fid] = queued.json()["revision_id"]
    design = stratified({ids[key]: value for key, value in assignments().items()})
    saved = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                       json={"version": 0, "spec": {"channel_assignment_version": 0, "experiment": design}})
    assert saved.status_code == 200, saved.text
    # The API names the saved design's hash, so the browser never recomputes it.
    assert saved.json()["experiment_sha256"] == design_sha256(design)
    assert client.get(f"/v1/workspaces/{wid}/analysis-spec").json()["experiment_sha256"] == design_sha256(design)
    return wid, ids, sources, design


def _cohort_body(client, wid, ids, sources, design, stratum):
    plan = parse_design(design)
    derived = {fid: value.model_dump(mode="json") for fid, value in field_metadata(plan).items()}
    chosen = [ids[key] for key, (s, _, _) in members(None).items() if s == stratum]
    active = client.get(f"/v1/workspaces/{wid}").json()["active_revision"]
    return {"sources": [{"field_id": fid, "revision_id": sources[fid]} for fid in chosen],
            "metadata": {fid: derived[fid] for fid in chosen}, "expected_active_revision_id": active,
            "stratum": {"design_version": "1.1.0", "design_sha256": design_sha256(plan), "stratum_id": f"s-{stratum}"}}


def test_api_compares_two_groups_within_one_declared_stratum_and_refuses_pooling(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, ids, sources, design = _workspace(client, app, settings)
    path = f"/v1/workspaces/{wid}/region-cohorts"
    body = _cohort_body(client, wid, ids, sources, design, "level-a")

    pooled = {key: value for key, value in body.items() if key != "stratum"}
    assert client.post(path, json=pooled, headers=HEADERS).json()["detail"] == "cohort_stratum_required"
    other = _cohort_body(client, wid, ids, sources, design, "level-b")
    mixed = {**body, "sources": body["sources"] + other["sources"][:1],
             "metadata": {**body["metadata"], **dict(list(other["metadata"].items())[:1])}}
    assert client.post(path, json=mixed, headers=HEADERS).json()["detail"] == "cohort_stratum_mixed"

    queued = client.post(path, json=body, headers=HEADERS)
    assert queued.status_code == 202, queued.text
    rid = queued.json()["revision_id"]
    process_one(app.state.store, settings)
    cohort = app.state.store.one(revisions, id=rid)
    assert cohort["state"] == "succeeded" and cohort["config"]["stratum"]["stratum_id"] == "s-level-a"
    assert set(cohort["config"]["field_snapshot"]) == {fid for fid in body["metadata"]}
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200

    request = {**comparison_request(), "version": "2.0.0", "test": "welch-t",
               "plot": {"kind": "box", "language": "en", "y_label": "Measured signal"}}
    accepted = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=request)
    assert accepted.status_code == 202, accepted.text
    process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{accepted.json()['job_id']}").json()
    assert job["state"] == "succeeded", job
    result = client.get(f"/v1/jobs/{accepted.json()['job_id']}/common-statistics").json()
    assert result["stratum"]["label"] == "LEVEL-A" and result["stratum"]["field_ids"] == sorted(body["metadata"])
    # Only this stratum's units (R1 · A, R2 · A, R1 · B, R2 · B) entered; the other stratum's values did not.
    assert [row["experimental_units"] for row in result["counts"]] == [2, 2]
    assert result["comparisons"][0]["estimate"] == pytest.approx(-3)
    methods = client.get(f"/v1/jobs/{accepted.json()['job_id']}/files/methods.md")
    assert methods.status_code == 200 and "Stratum: LEVEL-A (Factor: LEVEL-A)" in methods.text
    assert "Other strata were neither pooled with it nor compared" in methods.text
    assert {row["field_id"] for row in result["source_fields"]} == set(body["metadata"])

    # The exported bundle replays the same result, stratum record included.
    export = client.post(f"/v1/revisions/{rid}/export?include_raw=true", headers=HEADERS).json()["job_id"]
    process_one(app.state.store, settings)
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(tmp_path / "bundle")
    verification = replay_region_bundle(tmp_path / "bundle", tmp_path / "bundle" / "raw", tmp_path / "replay")
    assert verification["matched_saved_comparisons"]
    replayed = json.loads((tmp_path / "replay/statistics/0/result.json").read_text(encoding="utf-8"))
    assert replayed["stratum"] == result["stratum"]

    # A metadata child that swaps the groups of one run's A and B fields keeps the stratum and hash,
    # but its metadata no longer is the design's: statistics on it are refused.
    first_a, first_b = ids["f-level-a-r1-a"], ids["f-level-a-r1-b"]
    snapshot = app.state.store.one(revisions, id=rid)["config"]["field_snapshot"]
    swapped = {first_a: snapshot[first_b]["metadata"], first_b: snapshot[first_a]["metadata"]}
    child = client.post(f"/v1/revisions/{rid}/region-metadata", headers=HEADERS, json={"version": "1.0.0", "fields": swapped})
    assert child.status_code == 202, child.text
    process_one(app.state.store, settings)
    child_rid = child.json()["revision_id"]
    assert client.post(f"/v1/revisions/{child_rid}/review", headers=HEADERS, json={}).status_code == 200
    relabelled = client.post(f"/v1/revisions/{child_rid}/common-statistics", headers=HEADERS, json=request)
    assert relabelled.status_code == 409 and relabelled.json()["detail"] == "comparison_stratum_metadata_mismatch"

    # Moving a field to the other stratum makes the saved cohort stale: no reuse for statistics.
    moved = json.loads(json.dumps(design))
    first = body["sources"][0]["field_id"]
    moved["fields"][first]["stratum_id"] = "s-level-b"
    saved = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                       json={"version": 1, "spec": {"channel_assignment_version": 0, "experiment": moved}})
    assert saved.status_code == 200, saved.text
    refused = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=request)
    assert refused.status_code == 409 and refused.json()["detail"].startswith("comparison_stratum_")


def test_api_refuses_a_pooled_cohort_assembled_before_strata_were_declared(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, ids, sources, design = _workspace(client, app, settings)
    body = _cohort_body(client, wid, ids, sources, design, "level-a")
    queued = client.post(f"/v1/workspaces/{wid}/region-cohorts", json=body, headers=HEADERS)
    process_one(app.state.store, settings)
    rid = queued.json()["revision_id"]
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    # Simulate a cohort saved without a stratum (assembled under a design without strata).
    cohort = app.state.store.one(revisions, id=rid)
    config = {key: value for key, value in cohort["config"].items() if key != "stratum"}
    with app.state.store.transaction() as conn:
        conn.execute(update(revisions).where(revisions.c.id == rid).values(config=config))
    request = {**comparison_request(), "version": "2.0.0", "test": "welch-t",
               "plot": {"kind": "box", "language": "en", "y_label": "Measured signal"}}
    refused = client.post(f"/v1/revisions/{rid}/common-statistics", headers=HEADERS, json=request)
    assert refused.status_code == 409 and refused.json()["detail"] == "comparison_stratum_required"
    described = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS,
                            json={"mode": "descriptive", "selection": request["selection"], "group_by": "field",
                                  "plot": {"kind": "distribution", "language": "en"}})
    assert described.status_code == 409 and described.json()["detail"] == "comparison_stratum_required"


def test_api_keeps_the_stratum_for_one_adopted_field_with_same_stratum_exclusions(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, ids, sources, design = _workspace(client, app, settings)
    level_a = [ids[key] for key, (s, _, _) in members(None).items() if s == "level-a"]
    kept, dropped = level_a[0], level_a[1:]
    selection = client.get(f"/v1/workspaces/{wid}/selection", headers=HEADERS).json()
    current = {entry["field_id"]: entry for entry in selection["entries"]}
    entries = [{**current.get(fid, {"id": f"e-{fid}"}), "field_id": fid, "revision_id": None if fid in dropped else rid,
                "exclusion_reason": "out of focus" if fid in dropped else None} for fid, rid in sources.items()]
    adopted = client.post(f"/v1/workspaces/{wid}/selection", headers=HEADERS,
                          json={"version": selection["version"], "entries": entries})
    assert adopted.status_code == 200, adopted.text
    description = {"mode": "descriptive", "selection": comparison_request()["selection"], "group_by": "field",
                   "plot": {"kind": "distribution", "language": "en"}}
    # The field's own revision carries no stratum: a stratified design never describes it directly.
    assert client.post(f"/v1/revisions/{sources[kept]}/review", headers=HEADERS, json={}).status_code == 200
    direct = client.post(f"/v1/revisions/{sources[kept]}/descriptive", headers=HEADERS, json=description)
    assert direct.status_code == 409 and direct.json()["detail"] == "comparison_stratum_required"

    body = _cohort_body(client, wid, ids, sources, design, "level-a")
    body["sources"] = [item for item in body["sources"] if item["field_id"] == kept]
    body["metadata"] = {kept: body["metadata"][kept]}
    body["workspace_selection"] = adopted.json()
    queued = client.post(f"/v1/workspaces/{wid}/region-cohorts", json=body, headers=HEADERS)
    assert queued.status_code == 202, queued.text
    rid = queued.json()["revision_id"]
    process_one(app.state.store, settings)
    record = app.state.store.one(revisions, id=rid)["config"]["stratum"]
    assert (record["field_ids"], record["analysed_field_ids"]) == (sorted(level_a), [kept])
    assert record["excluded_fields"] == [{"field_id": fid, "reason": "out of focus"} for fid in sorted(dropped)]
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200

    accepted = client.post(f"/v1/revisions/{rid}/descriptive", headers=HEADERS, json=description)
    assert accepted.status_code == 202, accepted.text
    jid = accepted.json()["job_id"]
    process_one(app.state.store, settings)
    assert client.get(f"/v1/jobs/{jid}").json()["state"] == "succeeded"
    result = client.get(f"/v1/jobs/{jid}/result").json()
    assert result["stratum"] == record
    methods = client.get(f"/v1/jobs/{jid}/files/methods.md")
    assert methods.status_code == 200, methods.text
    assert "assigned 4 fields to this declared stratum; 1 were analysed and 3 were excluded" in methods.text

    export = client.post(f"/v1/revisions/{rid}/export?include_raw=true", headers=HEADERS).json()["job_id"]
    process_one(app.state.store, settings)
    archive = client.get(f"/v1/jobs/{export}/files/analysis.zip")
    with zipfile.ZipFile(io.BytesIO(archive.content)) as opened:
        opened.extractall(tmp_path / "bundle")
    replay_region_bundle(tmp_path / "bundle", tmp_path / "bundle" / "raw", tmp_path / "replay")
    replayed = json.loads((tmp_path / "replay/statistics/0/result.json").read_text(encoding="utf-8"))
    assert replayed["stratum"] == record


def test_legacy_region_comparison_cannot_bypass_strata(tmp_path):
    client, app, settings = authenticated(tmp_path)
    wid, ids, sources, design = _workspace(client, app, settings)
    plain = {key: value for key, value in design.items() if key not in ("factors", "strata")}
    plain = {**plain, "version": "1.0.0", "fields": {fid: {key: value for key, value in item.items() if key != "stratum_id"}
                                                     for fid, item in design["fields"].items()}}
    spec = client.get(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS).json()
    saved = client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                       json={"version": spec["version"], "spec": {"channel_assignment_version": 0, "experiment": plain}})
    assert saved.status_code == 200 and "experiment_sha256" not in saved.json()
    derived = {fid: value.model_dump(mode="json") for fid, value in field_metadata(parse_design(plain)).items()}
    active = client.get(f"/v1/workspaces/{wid}").json()["active_revision"]
    cohort = client.post(f"/v1/workspaces/{wid}/region-cohorts", headers=HEADERS, json={
        "sources": [{"field_id": fid, "revision_id": rid} for fid, rid in sources.items()],
        "metadata": derived, "expected_active_revision_id": active})
    assert cohort.status_code == 202, cohort.text  # an unstratified design keeps the earlier behaviour
    process_one(app.state.store, settings)
    rid = cohort.json()["revision_id"]
    assert client.post(f"/v1/revisions/{rid}/review", headers=HEADERS, json={}).status_code == 200
    queued = client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS, json=comparison_request())
    assert queued.status_code == 202, queued.text
    # The design becomes stratified before the queued legacy comparison runs: the worker refuses it.
    spec = client.get(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS).json()
    assert client.put(f"/v1/workspaces/{wid}/analysis-spec", headers=HEADERS,
                      json={"version": spec["version"], "spec": {"channel_assignment_version": 0, "experiment": design}}).status_code == 200
    process_one(app.state.store, settings)
    job = client.get(f"/v1/jobs/{queued.json()['job_id']}").json()
    assert job["state"] == "failed" and job["error"] == "comparison_stratum_legacy_unsupported", job
    again = client.post(f"/v1/revisions/{rid}/region-comparisons", headers=HEADERS, json=comparison_request())
    assert again.status_code == 409 and again.json()["detail"] == "comparison_stratum_legacy_unsupported"


def test_every_stratum_refusal_has_a_researcher_message():
    """The worker reports these codes as they are; the workspace explains each one in words."""
    from pathlib import Path

    from cytellect_analysis.experiment_strata import SAFE_ERROR_CODES
    from cytellect_worker.errors import SAFE_ERRORS

    messages = (Path(__file__).resolve().parents[1] / "apps/web/src/lib/api.ts").read_text(encoding="utf-8")
    cohort = {"cohort_stratum_required", "cohort_stratum_without_design", "cohort_stratum_design_changed",
              "cohort_stratum_mixed", "cohort_stratum_incomplete", "cohort_stratum_metadata_mismatch",
              "cohort_stratum_empty", "stratum_unknown", "experiment_design_unknown_stratum",
              "experiment_design_stratum_levels"}
    assert SAFE_ERROR_CODES <= SAFE_ERRORS
    assert all(f"\n {code}:" in messages for code in SAFE_ERROR_CODES | cohort)

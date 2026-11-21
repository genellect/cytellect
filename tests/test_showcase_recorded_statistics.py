"""The demo's index of recorded statistics (genellect/cytellect#257 D-1, owner decision 2026-11-21)."""
import json


def _entry(scene, path, body, status=202, method="POST"):
    return {"scene": scene, "method": method, "path": path, "body": json.dumps(body), "status": status}


def test_lists_each_recorded_choice_once_per_scene():
    from cytellect_showcase.build import recorded_statistics

    mean = {"mode": "region-experimental-unit", "selection": {"source": "region", "region_set_id": "nucleoli", "metric": "mean", "channel_id": "npm1"}}
    entries = [
        _entry("oxaliplatin:ai-1", "/v1/revisions/r1/common-statistics", mean),
        _entry("oxaliplatin:walk-2", "/v1/revisions/r2/common-statistics", mean),
        _entry("oxaliplatin:ai-1", "/v1/revisions/r1/descriptive", {"mode": "descriptive", "selection": {
            "source": "field-summary", "region_set_id": "nuclei", "metric": "positive_fraction", "positivity": {"channel_id": "eu5"}}}),
        _entry("plk1:walk", "/v1/revisions/r3/descriptive", {"mode": "descriptive", "selection": {
            "source": "region", "region_set_id": "nuclei", "metric": "area_px", "channel_id": None,
            "channel_gate": {"channel_id": "gfp", "keep": "positive"}}}),
        # Not a recorded calculation: a read, a refusal, another request.
        _entry("oxaliplatin:ai-1", "/v1/jobs/j1/common-statistics", None, status=200, method="GET"),
        _entry("oxaliplatin:ai-1", "/v1/revisions/r1/common-statistics", mean, status=422),
        _entry("oxaliplatin:ai-1", "/v1/workspaces/w/selection", {"revision_id": "r1"}),
    ]
    assert recorded_statistics(entries) == {"version": 1, "scenes": {
        "oxaliplatin": [
            {"analysis": "comparison", "region": "nucleoli", "metric": "mean", "channel": "npm1", "positivity": None, "gate": None},
            {"analysis": "distribution", "region": "nuclei", "metric": "positive_fraction", "channel": None, "positivity": "eu5", "gate": None},
        ],
        "plk1": [{"analysis": "distribution", "region": "nuclei", "metric": "area_px", "channel": None, "positivity": None, "gate": "gfp:positive"}],
    }}


def test_the_seed_saved_results_are_recorded_choices(tmp_path):
    """The demo opens a saved result without calculating it again, so no request is recorded for it: its choice comes
    from the seed's saved results (the opening comparison and its companions must stay offered)."""
    from cytellect_showcase.build import recorded_statistics, seed_statistics

    spec = {"mode": "region-experimental-unit", "selection": {"source": "compartment-summary", "region_set_id": "nucleoplasm",
                                                              "metric": "nucleolar_eccentricity", "channel_id": None}}
    (tmp_path / "jobs.json").write_text(json.dumps([{"id": "j1"}, {"id": "j2"}]))
    (tmp_path / "result.json").write_text(json.dumps({"spec": spec}))
    (tmp_path / "other.json").write_text(json.dumps({"spec": {"mode": "descriptive"}}))
    (tmp_path / "scenes.json").write_text(json.dumps({"version": 1, "scenes": [{"id": "ox", "workspaceId": "w1"}]}))
    (tmp_path / "index.json").write_text(json.dumps({"version": 1, "entries": {
        "GET /v1/workspaces/w1/jobs": {"status": 200, "file": "jobs.json"},
        "GET /v1/jobs/j1/common-statistics": {"status": 200, "file": "result.json"},
        # A job of no listed workspace and a failed read are not choices.
        "GET /v1/jobs/j9/result": {"status": 200, "file": "other.json"},
        "GET /v1/jobs/j2/result": {"status": 404, "file": "other.json"},
    }}))
    saved = seed_statistics(tmp_path)
    assert saved == [("ox", spec)]
    assert recorded_statistics([], saved) == {"version": 1, "scenes": {"ox": [
        {"analysis": "comparison", "region": "nucleoplasm", "metric": "nucleolar_eccentricity", "channel": None,
         "positivity": None, "gate": None}]}}


def test_an_association_records_both_axes():
    from cytellect_showcase.build import recorded_statistics

    body = {"mode": "region-association", "x_selection": {"region_set_id": "nuclei", "metric": "area_px", "channel_id": None},
            "y_selection": {"region_set_id": "nuclei", "metric": "mean", "channel_id": "npm1"}}
    [item] = recorded_statistics([_entry("s:walk", "/v1/revisions/r/common-statistics", body)])["scenes"]["s"]
    assert item == {"analysis": "association", "region": "nuclei", "metric": "mean", "channel": "npm1", "positivity": None,
                    "gate": None, "x": {"metric": "area_px", "channel": None}}

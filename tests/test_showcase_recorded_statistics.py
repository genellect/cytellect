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


def test_an_association_records_both_axes():
    from cytellect_showcase.build import recorded_statistics

    body = {"mode": "region-association", "x_selection": {"region_set_id": "nuclei", "metric": "area_px", "channel_id": None},
            "y_selection": {"region_set_id": "nuclei", "metric": "mean", "channel_id": "npm1"}}
    [item] = recorded_statistics([_entry("s:walk", "/v1/revisions/r/common-statistics", body)])["scenes"]["s"]
    assert item == {"analysis": "association", "region": "nuclei", "metric": "mean", "channel": "npm1", "positivity": None,
                    "gate": None, "x": {"metric": "area_px", "channel": None}}

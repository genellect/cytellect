"""Which demo scenes record every operation, and which only their story (DM-10)."""
import json
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parents[1] / "services" / "showcase" / "datasets"
PUBLIC_SCENES = ("zenodo-6643470-oxaliplatin", "zenodo-6643470-cisplatin", "zenodo-6643470-nucleolar",
                 "cpg0016-jump-source13-plk1")


def test_every_public_scene_records_every_operation():
    """The side panel offers only recorded choices, so each scene records them all (2026-11-21, owner decision,
    genellect/cytellect#257 SR-05): no scene of the public demo is recorded for its story only."""
    from cytellect_showcase.build import journal_scope

    for scene in PUBLIC_SCENES:
        manifest = json.loads((DATASETS / f"{scene}.json").read_text(encoding="utf-8"))
        assert journal_scope(manifest) == "full", scene
    with pytest.raises(SystemExit, match="unknown journal scope"):
        journal_scope({"scenario": {"journal": "some"}})


def test_the_declared_primary_measure_is_a_planned_analysis():
    """scenario.primary_outcome names one planned analysis; its measure is declared (never its time, NS-06)."""
    from cytellect_showcase.build import primary_outcome

    manifest = json.loads((DATASETS / "zenodo-6643470-nucleolar.json").read_text(encoding="utf-8"))
    assert primary_outcome(manifest["scenario"]) == {"version": "1.0.0", "metric": "mean", "region_set_id": "nucleoli",
                                                     "channel_id": "eu5"}
    assert primary_outcome({"statistics": {}}) is None
    with pytest.raises(SystemExit, match="names no planned analysis"):
        primary_outcome({"primary_outcome": "association", "statistics": {}})


def test_story_scenes_record_the_opening_analyses_and_companions_once():
    from cytellect_showcase.build import journal_scope, story_metrics

    manifest = json.loads((DATASETS / "zenodo-6643470-cisplatin.json").read_text(encoding="utf-8"))
    manifest["scenario"]["journal"] = "story"
    assert journal_scope(manifest) == "story"
    assert story_metrics(manifest) == [
        {"region": "nucleoplasm", "metric": "nucleolar_eccentricity"},
        {"region": "nucleoplasm", "metric": "nucleolar_area_px"},
        {"region": "nucleoli", "metric": "mean"},
    ]

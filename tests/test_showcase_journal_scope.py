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

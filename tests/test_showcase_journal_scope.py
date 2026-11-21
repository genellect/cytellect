"""Which demo scenes record every operation, and which only their story (DM-10)."""
import json
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parents[1] / "services" / "showcase" / "datasets"


def test_story_scenes_record_the_opening_analyses_and_companions_once():
    from cytellect_showcase.build import journal_scope, story_metrics

    manifest = json.loads((DATASETS / "zenodo-6643470-cisplatin.json").read_text(encoding="utf-8"))
    # Every scene records the full exploration since 2026-11-21 (owner decision, #257 SR-05); the story scope stays
    # available for a scene that does not fit the published files' limit (DM-10).
    assert journal_scope(manifest) == "full"
    assert journal_scope({"scenario": {**manifest["scenario"], "journal": "story"}}) == "story"
    assert story_metrics(manifest) == [
        {"region": "nucleoplasm", "metric": "nucleolar_eccentricity"},
        {"region": "nucleoplasm", "metric": "nucleolar_area_px"},
        {"region": "nucleoli", "metric": "mean"},
    ]
    for path in DATASETS.glob("*.json"):
        if path.stem != "zenodo-6643470":
            assert journal_scope(json.loads(path.read_text(encoding="utf-8"))) == "full", path.name
    with pytest.raises(SystemExit, match="unknown journal scope"):
        journal_scope({"scenario": {"journal": "some"}})


def test_each_scene_declares_its_planned_opening_comparison_as_primary():
    """#257 RP-04, NS-06: the demo shows the comparison planned before measuring as the declared primary measure."""
    from cytellect_showcase.build import primary_outcome

    first = json.loads((DATASETS / "zenodo-6643470-oxaliplatin.json").read_text(encoding="utf-8"))
    assert primary_outcome(first) == {"version": "1.0.0", "metric": "nucleolar_eccentricity",
                                      "region_set_id": "nucleoplasm", "channel_id": None}
    for path in DATASETS.glob("*.json"):
        if path.stem != "zenodo-6643470":
            assert primary_outcome(json.loads(path.read_text(encoding="utf-8"))) is not None, path.name
    assert primary_outcome({"scenario": {}}) is None

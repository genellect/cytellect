"""Which demo scenes record every operation, and which only their story (DM-10)."""
import json
from pathlib import Path

import pytest

DATASETS = Path(__file__).resolve().parents[1] / "services" / "showcase" / "datasets"


def test_story_scenes_record_the_opening_analyses_and_companions_once():
    from cytellect_showcase.build import journal_scope, story_metrics

    manifest = json.loads((DATASETS / "zenodo-6643470-oxaliplatin.json").read_text(encoding="utf-8"))
    assert journal_scope(manifest) == "story"
    assert story_metrics(manifest) == [
        {"region": "nucleoplasm", "metric": "nucleolar_eccentricity"},
        {"region": "nucleoplasm", "metric": "nucleolar_area_px"},
        {"region": "nucleoli", "metric": "mean"},
    ]
    # The demo's first scene keeps the full exploration the browser tests walk through.
    first = json.loads((DATASETS / "zenodo-6643470-nucleolar.json").read_text(encoding="utf-8"))
    assert journal_scope(first) == "full"
    with pytest.raises(SystemExit, match="unknown journal scope"):
        journal_scope({"scenario": {"journal": "some"}})

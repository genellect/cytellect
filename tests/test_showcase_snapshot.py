"""The published demo's recorded responses refer only to files that are committed with it."""
import json
from pathlib import Path

SNAPSHOT = Path(__file__).resolve().parents[1] / "apps/web/public/showcase/snapshot"


def test_recorded_responses_name_existing_files():
    index = json.loads((SNAPSHOT / "index.json").read_text(encoding="utf-8"))
    named = {entry["file"] for entry in index["entries"].values()}
    journal = SNAPSHOT / "journal.json"
    if journal.is_file():
        named |= {entry["file"] for entry in json.loads(journal.read_text(encoding="utf-8"))["entries"] if entry["file"]}
    assert sorted(name for name in named if not (SNAPSHOT / name).is_file()) == []

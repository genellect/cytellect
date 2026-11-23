"""The published demo's recorded responses refer only to files that are committed with it."""
import json
from pathlib import Path

from cytellect_showcase.journal_files import part_names, read_journal

SNAPSHOT = Path(__file__).resolve().parents[1] / "apps/web/public/showcase/snapshot"


def test_recorded_responses_name_existing_files():
    index = json.loads((SNAPSHOT / "index.json").read_text(encoding="utf-8"))
    named = {entry["file"] for entry in index["entries"].values()}
    if (SNAPSHOT / "journal.json").is_file():
        named |= {entry["file"] for entry in read_journal(SNAPSHOT)["entries"] if entry["file"]}
        # The journal's index names its parts (one per scene).
        named |= set(part_names(SNAPSHOT))
    assert sorted(name for name in named if not (SNAPSHOT / name).is_file()) == []


def test_every_published_file_stays_below_githubs_file_limit():
    """GitHub refuses a file above 100 MiB; the journal is split by scene to stay below it."""
    published = SNAPSHOT.parent
    large = [path.relative_to(published).as_posix() for path in published.rglob("*")
             if path.is_file() and path.stat().st_size > 100 * 1024 * 1024]
    assert large == []

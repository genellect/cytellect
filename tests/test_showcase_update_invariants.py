"""The presentation verifier rejects numeric/settings/asset drift in public records."""
import copy
import importlib.util
import json
import shutil
from pathlib import Path

import pytest
from cytellect_showcase.journal_files import read_journal

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("showcase_update", ROOT / "scripts/verify_showcase_update.py")
assert spec and spec.loader
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
SNAPSHOT = ROOT / "apps/web/public/showcase/snapshot"


@pytest.fixture
def recorded():
    catalogue = json.loads((SNAPSHOT / "figures.json").read_text(encoding="utf-8"))
    return next(group["opening"] for group in catalogue["groups"].values())


@pytest.mark.parametrize("change", ["settings", "metadata", "asset"])
def test_rejects_changed_published_drawing(tmp_path, recorded, change):
    target = tmp_path / "snapshot"
    target.mkdir()
    for name in recorded["files"].values():
        shutil.copyfile(SNAPSHOT / name, target / name)
    updated = copy.deepcopy(recorded)
    if change == "settings":
        updated["plot"]["font_size"] += 1
    elif change == "metadata":
        updated["figure"]["style"]["font_size_pt"] += 1
    else:
        (target / next(iter(updated["files"].values()))).write_bytes(b"changed")
    with pytest.raises(ValueError, match={"settings": "settings changed", "metadata": "metadata changed",
                                         "asset": "checksum changed"}[change]):
        checker.same_item(SNAPSHOT.parent, tmp_path, recorded, updated)


def test_exact_scientific_values_do_not_use_the_catalogues_rounding():
    # Read an actual public result, not manufactured measurement data.
    journal = read_journal(SNAPSHOT)
    entry = next(entry for entry in journal["entries"] if entry["method"] == "GET" and entry.get("file")
                 and entry["path"].endswith("/common-statistics"))
    original = json.loads((SNAPSHOT / entry["file"]).read_text(encoding="utf-8"))
    changed = copy.deepcopy(original)
    changed["unit_summary"][0]["value"] += 1e-12
    assert checker.result_key(original) != checker.result_key(changed)


def test_only_known_presentation_defaults_and_capture_ids_are_normalized():
    journal = read_journal(SNAPSHOT)
    entry = next(entry for entry in journal["entries"] if entry["method"] == "GET" and entry.get("file")
                 and entry["path"].endswith("/common-statistics"))
    original = json.loads((SNAPSHOT / entry["file"]).read_text(encoding="utf-8"))
    changed = copy.deepcopy(original)
    changed["source_fingerprint"] = "f" * 64
    changed["spec"]["plot"]["presentation"] = copy.deepcopy(checker.DEFAULT_PRESENTATION)
    assert checker.result_key(original) == checker.result_key(changed)
    changed["spec"]["plot"]["presentation"]["outlines"] = False
    assert checker.result_key(original) != checker.result_key(changed)

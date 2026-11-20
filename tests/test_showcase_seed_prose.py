"""Prose updates retain saved scientific exports from the registered public seed."""
import copy
import json
import zipfile
from pathlib import Path

import pytest
from cytellect_showcase.figure_text import preserve_seed

SEED = Path(__file__).resolve().parents[1] / "apps/web/public/showcase/seed.zip"


@pytest.fixture
def seed_pair(tmp_path):
    with zipfile.ZipFile(SEED) as archive:
        names = archive.namelist()
        result = next(name for name in names if name.endswith("/output/result.json")
                      and json.loads(archive.read(name)).get("source_kind") == "region-2d")
        csv = next(name for name in names if name.startswith(result.removesuffix("result.json")) and name.endswith(".csv"))
        svg = next(name for name in names if name.startswith(result.removesuffix("result.json")) and name.endswith(".svg"))
        exports = [name for name in names if name.startswith(result.removesuffix("result.json"))
                   and Path(name).name in {"figure.zip", "figure-archive.json", "figure-data.json", "descriptive-output.json"}]
        entries = {name: archive.read(name) for name in (result, csv, svg, *exports, "cytellect.sqlite", "showcase.json", "proposals.json")}
    old, new = tmp_path / "old.zip", tmp_path / "new.zip"
    def write(path, values):
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for name, body in values.items():
                archive.writestr(name, body)
    write(old, entries)
    changed = copy.deepcopy(entries)
    changed[svg] += b"\n<!-- rerendered -->"
    for name in exports:
        if name.endswith(".zip"):
            changed[name] += b"different export metadata"
    proposals = json.loads(changed["proposals.json"])
    # The published proposals stay real; change their serialization to identify the adopted member.
    changed["proposals.json"] = json.dumps(proposals, ensure_ascii=False, indent=2).encode()
    write(new, changed)
    return old, new, entries, changed, result, csv, write


def test_only_proposal_presentation_is_adopted(seed_pair):
    old, new, entries, changed, _, _, _ = seed_pair
    receipt = preserve_seed(old, new)
    with zipfile.ZipFile(new) as archive:
        for name, body in entries.items():
            assert archive.read(name) == (changed[name] if name == "proposals.json" else body)
    assert receipt["entries"] == len(entries)


@pytest.mark.parametrize("change", ["result", "csv", "database"])
def test_changed_scientific_input_cannot_be_hidden_by_retaining_old_exports(seed_pair, change, tmp_path):
    old, new, _, changed, result, csv, write = seed_pair
    if change == "result":
        value = json.loads(changed[result])
        value["unit_summary"][0]["value"] += 1
        changed[result] = json.dumps(value).encode()
    elif change == "csv":
        changed[csv] += b"changed"
    else:
        import sqlite3

        path = tmp_path / "mutated.sqlite"
        path.write_bytes(changed["cytellect.sqlite"])
        with sqlite3.connect(path) as connection:
            connection.execute("CREATE TABLE unexpected_change (value TEXT)")
        connection.close()
        changed["cytellect.sqlite"] = path.read_bytes()
    write(new, changed)
    with pytest.raises(ValueError, match="seed scientific|seed database"):
        preserve_seed(old, new)

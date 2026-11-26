"""The recorded tour on disk: ``snapshot/journal.json`` and its parts (docs/showcase.md).

A tour of every scene in full is larger than the 100 MB a file may have on GitHub, so ``journal.json`` lists parts,
one per demo scene, in the order the tour recorded them (``{"version": 2, "parts": ["journal-<scene>.json", ...]}``),
and each part is a journal of its own (``{"version": 1, "entries": [...]}``). Read in order, the parts are the one
tour the demo replays (apps/web/src/lib/showcase/transport.ts). A journal written as one file (version 1) is read as
it is. The index also gives each part's number of entries and the workspaces its paths name (``counts``,
``workspaces``; scene_index), so the demo reads the open workspace's scene first.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

INDEX = "journal.json"
# GitHub refuses a file above 100 MiB; a part is kept clearly below it.
PART_LIMIT_BYTES = 95 * 1024 * 1024
PART = re.compile(r"journal-[a-z0-9-]+\.json\Z")
WORKSPACE = re.compile(r"/v1/workspaces/([^/?]+)")
REVISION = re.compile(r"/v1/revisions/([^/?]+)")


def part_names(snapshot: Path) -> list[str]:
    """The files the journal consists of: the index and its parts (only the index for a single-file journal)."""
    index = json.loads((snapshot / INDEX).read_text(encoding="utf-8"))
    if "parts" not in index:
        return [INDEX]
    return [INDEX, *_parts(index)]


def _parts(index: dict) -> list[str]:
    parts = index.get("parts")
    if index.get("version") != 2 or not isinstance(parts, list) or not all(isinstance(name, str) and PART.fullmatch(name)
                                                                             for name in parts):
        raise ValueError("showcase_journal_index_invalid")
    return parts


def read_journal(snapshot: Path) -> dict:
    """The whole tour as one journal (``{"version": 1, "entries": [...]}``), whichever way it is stored."""
    index = json.loads((snapshot / INDEX).read_text(encoding="utf-8"))
    if "parts" not in index:
        return index
    entries: list[dict] = []
    for name in _parts(index):
        part = json.loads((snapshot / name).read_text(encoding="utf-8"))
        if part.get("version") != 1 or not isinstance(part.get("entries"), list):
            raise ValueError("showcase_journal_part_invalid")
        entries.extend(part["entries"])
    return {"version": 1, "entries": entries}


def _scene(entry: dict) -> str:
    """The demo scene of an entry: its walk is named ``<scene>:<walk>`` (a single-scene demo names no scene)."""
    name = (entry.get("scene") or "").split(":")[0] if ":" in (entry.get("scene") or "") else ""
    slug = re.sub(r"[^a-z0-9-]+", "-", name.lower()).strip("-")
    return slug or "demo"


def write_journal(snapshot: Path, journal: dict) -> list[str]:
    """Write the tour as an index and its parts; returns the files written (index first).

    Each run of consecutive entries of one scene is a part: a recorded tour walks the scenes one after another, so
    usually there is one part per scene (walks kept from an earlier tour follow the recorded ones, in parts of their
    own). Reading the parts in order gives exactly the same tour. Earlier parts this one does not name are left for
    the caller's clean-up of unnamed files.
    """
    runs: list[tuple[str, list[dict]]] = []
    for entry in journal["entries"]:
        scene = _scene(entry)
        if not runs or runs[-1][0] != scene:
            runs.append((scene, []))
        runs[-1][1].append(entry)
    count: dict[str, int] = {}
    names = []
    for scene, entries in runs:
        count[scene] = count.get(scene, 0) + 1
        name = f"journal-{scene}.json" if count[scene] == 1 else f"journal-{scene}-{count[scene]}.json"
        if name in names:
            # A later run of scene `x` (`journal-x-2.json`) and the first part of a scene named `x-2` would share a file.
            raise SystemExit(f"journal part {name} would be written twice: rename the scene whose id ends in -{count[scene]}")
        text = json.dumps({"version": 1, "entries": entries}, indent=1, ensure_ascii=False) + "\n"
        if len(text.encode("utf-8")) > PART_LIMIT_BYTES:
            raise SystemExit(f"journal part {name} is {len(text.encode('utf-8')):,} bytes, above {PART_LIMIT_BYTES:,}: "
                             "split it before publishing (GitHub refuses files above 100 MiB)")
        (snapshot / name).write_text(text, encoding="utf-8", newline="\n")
        names.append(name)
    index: dict = {"version": 2, "parts": names, **scene_index(runs)}
    (snapshot / INDEX).write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8", newline="\n")
    return [INDEX, *names]


def _owned(runs: list[tuple[str, list[dict]]], pattern: re.Pattern) -> list[list[str]] | None:
    """The identifiers each part's paths name by ``pattern``, or None when one is named by "*" or by the parts of two
    scenes: a request naming such an identifier could then match another scene's walk."""
    named: list[list[str]] = []
    owners: dict[str, set[str]] = {}
    for scene, entries in runs:
        found = set()
        for entry in entries:
            match = pattern.match(entry.get("path") or "")
            if match:
                if "*" in match.group(1):
                    return None
                found.add(match.group(1))
        for identifier in found:
            owners.setdefault(identifier, set()).add(scene)
        named.append(sorted(found))
    return None if any(len(scenes) > 1 for scenes in owners.values()) else named


def scene_index(runs: list[tuple[str, list[dict]]]) -> dict:
    """Each part's number of entries, and the workspaces and analysis versions its paths name, so the demo can read
    the open workspace's scene first and answer its changes before the other parts arrive (transport.ts). Each list
    is written only when that is exact: no recorded path names one by "*", and none is named by the parts of two
    scenes (a change naming it can then match only that scene's walks, wherever the other parts are in the tour)."""
    workspaces = _owned(runs, WORKSPACE)
    if workspaces is None:
        return {}
    revisions = _owned(runs, REVISION)
    return {"counts": [len(entries) for _, entries in runs], "workspaces": workspaces,
            **({"revisions": revisions} if revisions is not None else {})}

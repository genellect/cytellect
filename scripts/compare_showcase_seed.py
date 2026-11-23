"""Check that a rebuilt public demo kept every value of the published one and only added new ones.

For a demo recorded again with the same images and recorded detections (genellect/cytellect#257, owner decision
2026-11-23): every published field's masks and measured rows, and every saved statistics result, must be found in the
new data unchanged. Rows, columns and results may be added. Identifiers (fields, revisions, jobs) are generated anew, so
fields are matched by their scene and input pixels, regions by their mask and region id, results by their scene and
request. Measurements are compared exactly; statistics within a relative 1e-9 (the published results were recomputed
in the browser runtime, whose last floating-point digits can differ from CPython, docs/showcase.md).

    uv run python scripts/compare_showcase_seed.py --old apps/web/public/showcase --new-data <work>/data --new-state <work>/state.json
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sqlite3
import sys
import tempfile
import zipfile
from pathlib import Path

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
IDS = {"field_id", "analysis_revision_id", "mask_revision_id", "revision_id", "job_id", "source_job_id", "workspace_id"}
# Records of how and when a result was made, not what it says.
VOLATILE = {"figure", "software", "versions", "scipy_version", "numpy_version", "source_fingerprint", "created",
            "calculated_at", "plot", "methods_template", "figure_policy"}


class Source:
    """One demo's data: its database, its run outputs and the scene of each workspace."""

    def __init__(self, files: dict[str, bytes] | None = None, root: Path | None = None, scenes: dict[str, str] | None = None):
        self.files, self.root, self.scenes = files, root, scenes or {}
        self._db = tempfile.NamedTemporaryFile(suffix=".sqlite")
        self._db.write(self.read("cytellect.sqlite"))
        self._db.flush()
        db = sqlite3.connect(self._db.name)
        self.field_workspace, self.field_key = {}, {}
        for fid, workspace, info in db.execute("select id, workspace_id, image_info from fields"):
            self.field_workspace[fid] = workspace
            inputs = json.loads(info or "{}").get("inputs") or {}
            self.field_key[fid] = tuple(sorted(value["sha256"] for value in inputs.values()))
        self.revision_workspace = dict(db.execute("select id, workspace_id from revisions"))
        db.close()

    def read(self, name: str) -> bytes:
        return self.files[name] if self.files is not None else (self.root / name).read_bytes()  # type: ignore[operator]

    def names(self, pattern: str) -> list[str]:
        if self.files is not None:
            return [name for name in self.files if re.fullmatch(pattern, name)]
        return [path.relative_to(self.root).as_posix() for path in self.root.glob("runs/*/output/*")  # type: ignore[union-attr]
                if re.fullmatch(pattern, path.relative_to(self.root).as_posix())]

    def scene_of_field(self, fid: str) -> str | None:
        return self.scenes.get(self.field_workspace.get(fid, ""))

    def tables(self) -> dict[tuple, dict]:
        """(scene, field pixels, region set, mask) -> {(region, channel): row}."""
        found: dict[tuple, dict] = {}
        for name in self.names(r"runs/[^/]+/output/measurements\.json"):
            report = json.loads(self.read(name))
            for fid, table in (report.get("field_tables") or {}).items():
                scene = self.scene_of_field(fid)
                if scene is None:
                    continue
                key = (scene, self.field_key[fid], table["region_set"]["region_set_id"], table.get("mask_sha256"))
                rows = {(row["region_id"], row.get("channel_id")): {k: v for k, v in row.items() if k not in IDS}
                        for row in table.get("rows", [])}
                found.setdefault(key, {}).update(rows)
        return found

    def results(self) -> dict[tuple, list[dict]]:
        """(scene, request) -> saved statistics results."""
        found: dict[tuple, list[dict]] = {}
        for name in self.names(r"runs/[^/]+/output/result\.json"):
            result = json.loads(self.read(name))
            spec = result.get("spec") or {}
            scene = self.scenes.get(self.revision_workspace.get(result.get("revision_id", ""), ""))
            if scene is None or "mode" not in spec:
                continue
            request = {key: value for key, value in spec.items() if key not in VOLATILE}
            found.setdefault((scene, json.dumps(blank(request), sort_keys=True)), []).append(result)
        return found


def blank(value):
    """Identifiers written as '*', volatile records removed."""
    if isinstance(value, dict):
        return {key: "*" if key in IDS else blank(inner) for key, inner in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [blank(item) for item in value]
    if isinstance(value, str):
        return UUID.sub("*", value)
    return value


def kept(old, new, path: str, problems: list[str], tolerance: float) -> None:
    """Every value of ``old`` is in ``new`` (new keys may be added)."""
    if isinstance(old, dict):
        if not isinstance(new, dict):
            problems.append(f"{path}: not an object any more")
            return
        for key, value in old.items():
            if key not in new:
                problems.append(f"{path}.{key}: missing")
            else:
                kept(value, new[key], f"{path}.{key}", problems, tolerance)
    elif isinstance(old, list):
        if not isinstance(new, list) or len(new) != len(old):
            problems.append(f"{path}: list of {len(old)} became {len(new) if isinstance(new, list) else type(new).__name__}")
            return
        for index, (left, right) in enumerate(zip(old, new, strict=True)):
            kept(left, right, f"{path}[{index}]", problems, tolerance)
    elif isinstance(old, float) and isinstance(new, (int, float)) and not isinstance(new, bool):
        if not (math.isclose(old, new, rel_tol=tolerance, abs_tol=tolerance * 1e-3) or (math.isnan(old) and math.isnan(new))):
            problems.append(f"{path}: {old!r} became {new!r}")
    elif old != new:
        problems.append(f"{path}: {str(old)[:80]!r} became {str(new)[:80]!r}")


def compare(old: Source, new: Source) -> list[str]:
    problems: list[str] = []
    old_tables, new_tables = old.tables(), new.tables()
    for key, rows in sorted(old_tables.items(), key=str):
        label = f"{key[0]} field {key[1][0][:8]} {key[2]}"
        if key not in new_tables:
            problems.append(f"{label}: no measurement of the same mask")
            continue
        for row_key, row in rows.items():
            if row_key not in new_tables[key]:
                problems.append(f"{label} region {row_key}: missing")
            else:
                kept(row, new_tables[key][row_key], f"{label} region {row_key}", problems, 0.0)
    old_results, new_results = old.results(), new.results()
    for key, results in sorted(old_results.items()):
        label = f"{key[0]} {json.loads(key[1]).get('mode')} {json.dumps(json.loads(key[1]).get('selection'))}"
        candidates = new_results.get(key, [])
        if not candidates:
            problems.append(f"{label}: no result of the same request")
            continue
        for result in results:
            attempts = []
            for candidate in candidates:
                found: list[str] = []
                kept(blank(result), blank(candidate), label, found, 1e-9)
                attempts.append(found)
            if all(attempts):
                problems.extend(min(attempts, key=len)[:5])
    print(json.dumps({"measured_tables": len(old_tables), "new_tables": len(new_tables), "results": len(old_results),
                      "new_results": len(new_results), "problems": len(problems)}))
    return problems


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--old", type=Path, required=True, help="the published demo directory (seed.zip, manifest.json)")
    parser.add_argument("--new-data", type=Path, required=True, help="the rebuild's data directory")
    parser.add_argument("--new-state", type=Path, required=True, help="the rebuild's state.json")
    args = parser.parse_args(argv)
    manifest = json.loads((args.old / "manifest.json").read_text(encoding="utf-8"))
    with zipfile.ZipFile(args.old / "seed.zip") as archive:
        files = {name: archive.read(name) for name in archive.namelist()
                 if name == "cytellect.sqlite" or re.fullmatch(r"runs/[^/]+/output/(measurements|result)\.json", name)}
    old = Source(files=files, scenes={scene["workspace_id"]: scene["id"] for scene in manifest["scenes"]})
    state = json.loads(args.new_state.read_text(encoding="utf-8"))
    new = Source(root=args.new_data, scenes={value["scenario"]["workspace_id"]: scene for scene, value in state["scenes"].items()
                                             if value.get("scenario")})
    problems = compare(old, new)
    for line in problems[:60]:
        print(line)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())

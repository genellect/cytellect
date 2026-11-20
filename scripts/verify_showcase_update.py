"""Verify a presentation-only update against the complete earlier public demo.

No rounding or numeric tolerance is used. Capture identifiers and library-version
records may differ; scientific values, settings, input pixels, masks and drawings
must be identical. Run after the figures stage, before adopting its artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import re
import zipfile
from pathlib import Path

UUID = re.compile(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}")
VOLATILE = {"figure", "source_job_id", "source_fingerprint", "software", "versions", "scipy_version", "numpy_version"}
PROSE = {"figure-legend.md", "figure-caption.md"}
SCIENCE_FILES = {".tif", ".tiff", ".npy", ".npz", ".csv", ".svg", ".png", ".pdf"}


def read(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def canonical(value):
    """Keep every scientific value at its recorded precision, including tiny changes."""
    if isinstance(value, dict):
        return {key: canonical(inner) for key, inner in value.items() if key not in VOLATILE}
    if isinstance(value, list):
        return [canonical(inner) for inner in value]
    if isinstance(value, str):
        return UUID.sub("*", value)
    return value


def result_key(value: dict) -> str:
    return json.dumps(canonical(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def results(root: Path, seed: zipfile.ZipFile, catalogue: dict) -> set[str]:
    values: set[str] = set()
    covered: set[str] = set()

    def add(body: bytes, job: str):
        value = json.loads(body)
        if isinstance(value, dict) and value.get("source_kind") == "region-2d" and "spec" in value:
            values.add(result_key(value))
            if source := catalogue["sources"].get(job):
                covered.add(source["group"])

    entries = read(root / "snapshot/index.json")["entries"]
    responses = [(key.removeprefix("GET "), entry) for key, entry in entries.items() if key.startswith("GET ")]
    responses.extend((entry["path"], entry) for entry in read(root / "snapshot/journal.json")["entries"]
                     if entry["method"] == "GET")
    for path, entry in responses:
        if entry.get("file") and (match := re.fullmatch(r"/v1/jobs/([^/]+)/(common-statistics|result)", path)):
            add((root / "snapshot" / entry["file"]).read_bytes(), match[1])
    for name in seed.namelist():
        if match := re.fullmatch(r"runs/([^/]+)/output/result.json", name):
            add(seed.read(name), match[1])
    require(bool(values), "no recorded scientific results were checked")
    require(covered == set(catalogue["groups"]), f"results not checked for {len(set(catalogue['groups']) - covered)} groups")
    return values


def asset(root: Path, name: str) -> bytes:
    require(Path(name).name == name, "unsafe content-addressed asset name")
    body = (root / "snapshot" / name).read_bytes()
    require(hashlib.sha256(body).hexdigest()[:24] == Path(name).stem, f"asset checksum changed: {name}")
    return body


def same_item(before: Path, after: Path, old: dict, new: dict) -> int:
    require(old["plot"] == new["plot"], "figure settings changed")
    require(set(old["files"]) == set(new["files"]), "figure file types changed")
    require({k: v for k, v in old["figure"].items() if k != "legend_gaps"} ==
            {k: v for k, v in new["figure"].items() if k != "legend_gaps"}, "drawing metadata changed")
    checked = 0
    for name in old["files"]:
        a, b = asset(before, old["files"][name]), asset(after, new["files"][name])
        if name not in PROSE:
            require(a == b, f"published drawing changed: {name}")
            checked += 1
    return checked


def packages(root: Path, catalogue: dict) -> dict[tuple[str, int], list[tuple[tuple[str, bytes], ...]]]:
    found: dict[tuple[str, int], list[tuple[tuple[str, bytes], ...]]] = {}
    for entry in catalogue["packages"]:
        key = (catalogue["sources"][entry["source"]]["group"], entry["figure"])
        with zipfile.ZipFile(io.BytesIO(asset(root, entry["files"]["publication.zip"]))) as archive:
            files = tuple(sorted((name, archive.read(name)) for name in archive.namelist()
                                 if name.startswith("edited-figure/") and Path(name).name not in PROSE))
        require(bool(files), "publication package has no edited drawing/source files")
        found.setdefault(key, []).append(files)
    for values in found.values():
        values.sort()
    return found


def verify(before: Path, after: Path) -> dict[str, int]:
    old = read(before / "snapshot/figures.json")
    new = read(after / "snapshot/figures.json")
    require(old["groups"].keys() == new["groups"].keys(), "recorded result groups changed")
    require(old["saved"].keys() == new["saved"].keys(), "saved figures changed")
    drawings = 0
    for key, group in old["groups"].items():
        other = new["groups"][key]
        require(group["observations"] == other["observations"], "observations display changed")
        old_items, new_items = [group["opening"], *group["figures"]], [other["opening"], *other["figures"]]
        require(len(old_items) == len(new_items), "figure variant count changed")
        drawings += sum(same_item(before, after, x, y) for x, y in zip(old_items, new_items, strict=True))
    for key, item in old["saved"].items():
        require(item["source"] == new["saved"][key]["source"], "saved figure source changed")
        drawings += same_item(before, after, item, new["saved"][key])
    items = [item for group in old["groups"].values() for item in [group["opening"], *group["figures"]]]
    items.extend(old["saved"].values())
    drawing_files = {file for item in items for name, file in item["files"].items() if name not in PROSE}
    a, b = packages(before, old), packages(after, new)
    require(a == b, "publication package drawing/source data changed")
    with zipfile.ZipFile(before / "seed.zip") as original, zipfile.ZipFile(after / "seed.zip") as updated:
        protected = {name for name in original.namelist() if Path(name).suffix in SCIENCE_FILES}
        require(protected == {name for name in updated.namelist() if Path(name).suffix in SCIENCE_FILES},
                "seed scientific file set changed")
        for name in protected:
            require(original.read(name) == updated.read(name), f"seed input/mask/measurement/drawing changed: {name}")
        original_results, updated_results = results(before, original, old), results(after, updated, new)
        require(original_results == updated_results, f"scientific results changed: "
                f"{len(original_results - updated_results)} missing, {len(updated_results - original_results)} added")
    return {"result_groups": len(old["groups"]), "exact_results": len(original_results),
            "drawing_files": len(drawing_files), "drawing_references": drawings, "protected_seed_files": len(protected),
            "publication_packages": sum(len(values) for values in a.values())}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--after", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(verify(args.before, args.after), sort_keys=True))


if __name__ == "__main__":
    main()

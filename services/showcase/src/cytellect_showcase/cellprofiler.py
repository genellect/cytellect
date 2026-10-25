"""JUMP's published CellProfiler nuclei for the demo fields, matched to the demo's adopted nuclei.

The JUMP Cell Painting consortium published, for every image, CellProfiler's nucleus count
(Image.csv, pinned by SHA-256) and every nucleus's centre, bounding box and area (Nuclei.csv,
about 24 GB per plate). Only the rows of the demo's images are read, by byte ranges; the
extracted rows are cached with their SHA-256 so a rebuild reproduces the same reference.
JUMP numbers image sites from 0 (file F005 is Metadata_Site 4); images are matched by file name.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import time
import urllib.request
from collections import Counter
from pathlib import Path

KEEP = ["ImageNumber", "ObjectNumber", "Nuclei_AreaShape_Area", "Nuclei_AreaShape_Center_X", "Nuclei_AreaShape_Center_Y",
        "Nuclei_AreaShape_BoundingBoxMinimum_X", "Nuclei_AreaShape_BoundingBoxMinimum_Y",
        "Nuclei_AreaShape_BoundingBoxMaximum_X", "Nuclei_AreaShape_BoundingBoxMaximum_Y"]


def _get(url: str, start: int | None = None, end: int | None = None) -> bytes:
    headers = {"User-Agent": "cytellect-showcase-build"} | ({"Range": f"bytes={start}-{end}"} if start is not None else {})
    for attempt in range(6):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=300) as response:
                data = response.read()
            if start is None or len(data) == end - start + 1 or end is None:
                return data
        except OSError:
            pass
        time.sleep(2 * (attempt + 1))
    raise SystemExit(f"cellprofiler reference: range read failed {url} {start}-{end}")


def _size(url: str) -> int:
    with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=60) as response:
        return int(response.headers["Content-Length"])


def image_table(source: dict, cache: Path) -> list[dict]:
    cache.mkdir(parents=True, exist_ok=True)
    target = cache / source["sha256"]
    if not target.exists():
        target.write_bytes(_get(source["url"]))
    data = target.read_bytes()
    if hashlib.sha256(data).hexdigest() != source["sha256"]:
        target.unlink()
        raise SystemExit(f"cellprofiler reference: Image.csv mismatch {source['url']}")
    return list(csv.DictReader(io.StringIO(data.decode("utf8"))))


def object_rows(url: str, numbers: set[int], cache: Path) -> list[dict]:
    """Rows of Nuclei.csv for the given ImageNumbers (the file is nearly sorted by ImageNumber)."""
    key = hashlib.sha256(json.dumps([url, sorted(numbers)]).encode()).hexdigest()
    cached = cache / f"nuclei-{key}.json"
    if cached.exists():
        return json.loads(cached.read_text())
    size = _size(url)
    header = next(csv.reader([_get(url, 0, 400000).decode("utf8", "replace").split("\n", 1)[0]]))
    index = {name: header.index(name) for name in KEEP}

    def first(offset: int) -> int | None:
        try:
            return int(_get(url, offset, offset + 80000).decode("utf8", "replace").split("\n")[1].split(",")[0])
        except (IndexError, ValueError):
            return None
    samples = [(0, 0)] + [(offset, value) for offset in (int(size * i / 800) for i in range(1, 800))
                          if (value := first(offset)) is not None] + [(size, 10**12)]
    ranges = []
    for number in sorted(numbers):
        low = max(i for i, (_, value) in enumerate(samples) if value < number)
        high = min(i for i, (_, value) in enumerate(samples) if value > number and i > low)
        ranges.append((samples[max(low - 1, 0)][0], min(samples[min(high + 1, len(samples) - 1)][0], size - 1)))
    merged: list[tuple[int, int]] = []
    for start, end in sorted(ranges):
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(end, merged[-1][1]))
        else:
            merged.append((start, end))
    rows = []
    for start, end in merged:
        for line in _get(url, start, end).decode("utf8", "replace").split("\n")[1:-1]:
            values = next(csv.reader([line]), [])
            if len(values) == len(header) and values[0].isdigit() and int(values[0]) in numbers:
                rows.append({name: values[i] for name, i in index.items()})
    cached.write_text(json.dumps(rows))
    return rows


def reference(manifest: dict, cache: Path) -> dict:
    """Per demo field (by source file name): CellProfiler's counts and nucleus centres/areas."""
    plan = manifest["reference"]
    fields: dict[str, dict] = {}
    for plate in plan["plates"]:
        table = image_table(plate["image_table"], cache)
        wanted = {}
        for row in table:
            name = row["FileName_OrigDNA"]
            if name in plan["files"]:
                wanted[int(float(row["Image_ImageNumber"]))] = (name, row)
        rows = object_rows(plate["object_table_url"], set(wanted), cache)
        by_image = {}
        for row in rows:
            by_image.setdefault(int(row["ImageNumber"]), []).append(row)
        for number, (name, row) in wanted.items():
            objects = by_image.get(number, [])
            if len(objects) != int(float(row["Count_Nuclei"])):
                raise SystemExit(f"cellprofiler reference: {name} has {len(objects)} rows, Count_Nuclei {row['Count_Nuclei']}")
            fields[name] = {"plate": plate["plate"], "site_index": int(row["Metadata_Site"]),
                            "count_nuclei": int(float(row["Count_Nuclei"])),
                            "count_nuclei_including_edges": int(float(row["Count_NucleiIncludingEdges"])),
                            "objects": [{"x": float(o["Nuclei_AreaShape_Center_X"]), "y": float(o["Nuclei_AreaShape_Center_Y"]),
                                         "area_px": float(o["Nuclei_AreaShape_Area"])}
                                        for o in sorted(objects, key=lambda o: int(o["ObjectNumber"]))]}
    missing = set(plan["files"]) - set(fields)
    if missing:
        raise SystemExit(f"cellprofiler reference: images not found {sorted(missing)}")
    digest = hashlib.sha256(json.dumps(fields, sort_keys=True).encode()).hexdigest()
    return {"fields": fields, "sha256": digest}


def compare(fields: dict, labels_by_name: dict) -> dict:
    """Match each field's CellProfiler centres to the demo's adopted nuclear labels."""
    import numpy as np
    from cytellect_analysis.reference_objects import match_reference_centres
    from scipy import ndimage

    out = {}
    for name, field in fields.items():
        labels = labels_by_name[name]
        result = match_reference_centres(labels, [(o["x"], o["y"]) for o in field["objects"]])
        ids = [int(v) for v in np.unique(labels) if v]
        areas = dict(zip(ids, ndimage.sum_labels(np.ones_like(labels), labels, ids).tolist(), strict=True))
        centres = dict(zip(ids, ndimage.center_of_mass(np.ones_like(labels), labels, ids), strict=True))
        markers = [[round(o["x"], 1), round(o["y"], 1), round(float(np.sqrt(o["area_px"] / np.pi)), 1), status]
                   for o, status in zip(field["objects"], result["reference"], strict=True)]
        markers += [[round(float(centres[i][1]), 1), round(float(centres[i][0]), 1),
                     round(float(np.sqrt(areas[i] / np.pi)), 1), "labels_only"] for i in result["labels_only"]]
        reference_areas = Counter(status for status in result["reference"])
        out[name] = {**result["summary"], "count_nuclei": field["count_nuclei"],
                     "reference_only_area_px": [o["area_px"] for o, s in zip(field["objects"], result["reference"], strict=True)
                                                if s == "reference_only"],
                     "both_area_px": [o["area_px"] for o, s in zip(field["objects"], result["reference"], strict=True) if s == "both"],
                     "count_nuclei_including_edges": field["count_nuclei_including_edges"],
                     "median_area_px": {
                         status: float(np.median([o["area_px"] for o, s in zip(field["objects"], result["reference"], strict=True)
                                                  if s == status])) if reference_areas[status] else None
                         for status in ("both", "split", "reference_only")},
                     "median_label_area_px": float(np.median(list(areas.values()))) if areas else None,
                     "markers": markers}
    return out


def group_summary(compared: dict, design: dict, field_of: dict) -> dict:
    """Per condition and per run: each method's mean nuclei per field (border-touching nuclei
    excluded in both, as CellProfiler's Count_Nuclei does) and what only the reference method holds.

    ``compared`` is :func:`compare` keyed by source file, ``field_of`` maps each file to its
    workspace field id and ``design`` is the saved experiment design (control first).
    """
    import numpy as np

    groups = sorted(design["groups"], key=lambda group: group["id"] != design.get("control_group_id"))
    runs = design.get("runs") or []

    def summary(names: list[str]) -> dict:
        rows = [compared[name] for name in names]
        pooled_only = [area for row in rows for area in row["reference_only_area_px"]]
        pooled_both = [area for row in rows for area in row["both_area_px"]]
        reference_objects = sum(row["reference_objects"] for row in rows)
        return {"fields": len(rows),
                "cytellect_per_field": float(np.mean([row["labels_away_from_border"] for row in rows])),
                "cellprofiler_per_field": float(np.mean([row["count_nuclei"] for row in rows])),
                "reference_only_per_field": float(np.mean([row["reference_only"] for row in rows])),
                "split_per_field": float(np.mean([row["split"] for row in rows])),
                "labels_only_per_field": float(np.mean([row["labels_only"] for row in rows])),
                "matched_fraction": sum(row["both"] for row in rows) / reference_objects if reference_objects else None,
                "reference_only_median_area_px": float(np.median(pooled_only)) if pooled_only else None,
                "matched_median_area_px": float(np.median(pooled_both)) if pooled_both else None}

    def names(group_id: str, run_id: str | None = None) -> list[str]:
        return sorted(name for name, field_id in field_of.items() if name in compared
                      and design["fields"][field_id]["group_id"] == group_id
                      and (run_id is None or design["fields"][field_id]["run_id"] == run_id))

    def ratio(rows: list[dict]) -> dict | None:
        # Treatment ÷ control of the mean nuclei per field, for each method (display only).
        if len(rows) != 2 or not rows[0]["cytellect_per_field"] or not rows[0]["cellprofiler_per_field"]:
            return None
        return {method: rows[1][f"{method}_per_field"] / rows[0][f"{method}_per_field"] for method in ("cytellect", "cellprofiler")}

    overall = [{"id": group["id"], "label": group["label"], **summary(names(group["id"]))} for group in groups if names(group["id"])]
    per_run = []
    for run in runs:
        rows = [{"id": group["id"], **summary(names(group["id"], run["id"]))} for group in groups if names(group["id"], run["id"])]
        per_run.append({"id": run["id"], "label": run["label"], "groups": rows, "ratio": ratio(rows)})
    return {"groups": overall, "ratio": ratio(overall), "runs": per_run}

"""Offline replay from exact original TIFFs and approved saved masks."""
import argparse
import json
from pathlib import Path

import numpy as np

from .contracts import Recipe, StatisticsRequest
from .exports import _json
from .exports_csv import write_csv
from .figures import render_figures
from .images import read_tiff, sha256
from .masks import polygon_mask
from .measurement import apply_gfp_gate, measure
from .statistics import analyze_sensitivity


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _inside(root, relative):
    root = root.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise ValueError("replay_path_outside_package")
    return path


def replay(bundle_dir: Path, raw_dir: Path, output_dir: Path):
    bundle_dir, raw_dir = bundle_dir.resolve(), raw_dir.resolve()
    if output_dir.resolve().is_relative_to(bundle_dir) or bundle_dir.is_relative_to(output_dir.resolve()):
        raise ValueError("replay_output_must_be_separate")
    manifest = _read(bundle_dir / "manifest.json")
    for relative, expected in manifest["files"].items():
        if sha256(_inside(bundle_dir, relative)) != expected:
            raise ValueError("replay_bundle_hash_mismatch")
    config = _read(bundle_dir / "revision.json")["config"]
    recipe = Recipe.model_validate(config["recipe"])
    expected = _read(bundle_dir / "measurements.json")
    if expected.get("field_failures") or set(expected.get("invalidated_nucleoli", [])) - set(config.get("review_record", {}).get("accept_invalidated_fields", [])):
        raise ValueError("replay_requires_complete_reviewed_masks")
    output_dir.mkdir(parents=True, exist_ok=False)
    cells, objects, manual_rows = [], [], []
    for fid in config["field_ids"]:
        snapshot = config["field_snapshot"][fid]
        info = snapshot["image_info"]
        folder = _inside(raw_dir, fid)
        for role, source in info["inputs"].items():
            if role not in ("dapi", "ncl", "gfp", "ome"):
                raise ValueError("unsupported_replay_channel")
            if sha256(folder / f"{role}.tif") != source["sha256"]:
                raise ValueError("replay_original_hash_mismatch")
        if "ome" in info["inputs"]:
            stack = read_tiff(folder / "ome.tif", channel_indices=info["channel_mapping"])
            channels = dict(zip(info.get("channel_roles", ("dapi", "ncl", "gfp")), stack, strict=True))
        else:
            channels = {role: read_tiff(folder / f"{role}.tif", legacy=info["legacy"])
                        for role in info["inputs"]}
        with np.load(_inside(bundle_dir, f"masks/{fid}/labels.npz"), allow_pickle=False) as masks:
            nuclei, nucleoli, manual = masks["nuclei"], masks["nucleoli"], masks["manual"]
            background = (polygon_mask(nuclei.shape, config["backgrounds"][fid]["polygon"])
                          if recipe.id != "ncl-legacy-rgb" else None)
            measured = measure(channels, nuclei, nucleoli, background, recipe, snapshot["metadata"], fid, manual)
        field_cells, field_objects, field_manual = measured
        for row in field_cells:
            exclusion = next((x for x in config.get("exclusions", [])
                              if x["field_id"] == fid and x["nucleus_id"] in (None, row["nucleus_id"])), None)
            if exclusion:
                row["excluded"], row["exclusion_reason"] = True, exclusion["reason"]
        cells.extend(field_cells)
        objects.extend(field_objects)
        manual_rows.extend(field_manual)
    cells = apply_gfp_gate(cells, recipe)
    result = {**expected, "cells": cells, "nucleoli": objects, "manual_rois": manual_rows}
    _json(output_dir / "measurements.json", result)
    for filename, data in (("cells.csv", cells), ("nucleoli.csv", objects), ("manual-rois.csv", manual_rows)):
        write_csv(output_dir / filename, data)
    for stats_path in sorted((bundle_dir / "statistics").glob("*/result.json")):
        recorded = _read(stats_path)
        spec = StatisticsRequest.model_validate(recorded["spec"])
        fresh = analyze_sensitivity(cells, spec)
        folder = output_dir / "statistics" / stats_path.parent.name
        render_figures(fresh, folder)
        _json(folder / "result.json", fresh)
    return result


def main():
    parser = argparse.ArgumentParser(description="Replay approved-mask measurements from hash-verified TIFFs")
    parser.add_argument("--bundle-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    arguments = parser.parse_args()
    replay(arguments.bundle_dir, arguments.raw_dir, arguments.output_dir)


if __name__ == "__main__":
    main()

import json
import zipfile

import numpy as np
import pytest
import tifffile
from cytellect_analysis.contracts import PlotSpec, Recipe, StatisticsRequest
from cytellect_analysis.exports import build_export_bundle
from cytellect_analysis.exports_csv import write_csv
from cytellect_analysis.figures import japanese_font, render_figures
from cytellect_analysis.images import sha256
from cytellect_analysis.masks import polygon_mask
from cytellect_analysis.measurement import apply_gfp_gate, measure
from cytellect_analysis.replay import replay
from cytellect_analysis.statistics import analyze


def example(tmp_path):
    shape = (12, 15)
    nuclei = np.zeros(shape, np.uint32)
    nuclei[3:9, 4:11] = 1
    nucleoli = np.zeros(shape, np.uint32)
    nucleoli[4:6, 6:8] = 1
    channels = {c: np.full(shape, 10, dtype=np.uint16) for c in ("dapi", "ncl", "gfp")}
    for channel in channels.values():
        channel[nuclei > 0] = 30
    channels["ncl"][nucleoli > 0] = 90
    recipe = Recipe()
    metadata = {"condition": "Synthetic", "experimental_unit": "replicate", "sample": "sample",
                "acquisition_date": "date", "pair": None, "repeat_length": None, "pixel_size_um": None}
    polygon = [[0, 0], [3, 0], [3, 2], [0, 2]]
    manual = np.zeros(shape, np.uint32)
    cells, objects, rois = measure(channels, nuclei, nucleoli, polygon_mask(shape, polygon), recipe,
                                   metadata, "field", manual)
    report = {"revision_id": "revision", "recipe": recipe.model_dump(), "cells": apply_gfp_gate(cells, recipe),
              "nucleoli": objects, "manual_rois": rois, "field_failures": [], "invalidated_nucleoli": []}
    raw_dir = tmp_path / "originals" / "field"
    raw_dir.mkdir(parents=True)
    inputs = {}
    files = []
    for role, array in channels.items():
        path = raw_dir / f"{role}.tif"
        tifffile.imwrite(path, array)
        inputs[role] = {"sha256": sha256(path)}
        files.append((f"field/{role}.tif", path))
    config = {"recipe": recipe.model_dump(), "field_ids": ["field"], "exclusions": [],
              "backgrounds": {"field": {"polygon": polygon, "confirmed": True}},
              "field_snapshot": {"field": {"metadata": metadata,
                  "image_info": {"inputs": inputs, "legacy": False, "channel_mapping": ["dapi", "ncl", "gfp"]}}}}
    masks = {"field": {"nuclei": nuclei, "nucleoli": nucleoli, "manual": manual}}
    return report, config, masks, files


def test_bundle_excludes_raw_and_replays_hash_verified_originals(tmp_path):
    report, config, masks, files = example(tmp_path)
    archive = build_export_bundle(tmp_path / "export", report=report, config=config,
                                  provenance={"engine": "synthetic", "code_commit": "test"},
                                  field_masks=masks, raw_files=files)
    with zipfile.ZipFile(archive) as source:
        assert not any(n.startswith("raw/") for n in source.namelist())
        assert {"cells.csv", "methods.md", "replay.py", "manifest.json", "masks/field/nuclei-rois.zip"} <= set(source.namelist())
        manifest = json.loads(source.read("manifest.json"))
        assert manifest["raw_included"] is False
    fresh = replay(tmp_path / "export" / "bundle", tmp_path / "originals", tmp_path / "replayed")
    assert fresh["cells"] == report["cells"]
    assert fresh["nucleoli"] == report["nucleoli"]
    files[0][1].write_bytes(b"changed")
    with pytest.raises(ValueError, match="replay_original_hash_mismatch"):
        replay(tmp_path / "export" / "bundle", tmp_path / "originals", tmp_path / "another")


def test_raw_requires_opt_in_and_rejects_arbitrary_archive_names(tmp_path):
    report, config, masks, files = example(tmp_path)
    archive = build_export_bundle(tmp_path / "export", report=report, config=config,
                                  provenance={}, field_masks=masks, raw_files=files, include_raw=True)
    with zipfile.ZipFile(archive) as source:
        assert "raw/field/dapi.tif" in source.namelist()
    with pytest.raises(ValueError, match="raw_export_inputs_incomplete|invalid_raw_export_name"):
        build_export_bundle(tmp_path / "unsafe", report=report, config=config,
                            provenance={}, field_masks=masks, include_raw=True,
                            raw_files=[("../secret", files[0][1])])


def test_csv_strings_do_not_become_spreadsheet_formulas(tmp_path):
    path = tmp_path / "values.csv"
    write_csv(path, [{"condition": "=1+1", "value": -2.5}, {"condition": "normal", "value": 2}])
    text = path.read_text(encoding="utf-8-sig")
    assert "'=1+1,-2.5" in text


def statistical_result(language="en", kind="distribution"):
    rows = []
    for group, effect in (("A", 0), ("B", 2)):
        for unit in range(3):
            for cell in range(3):
                rows.append({"condition": group, "experimental_unit": f"{group}{unit}", "sample": f"{group}{unit}",
                             "field_id": f"{group}{unit}", "acquisition_date": "d",
                             "ncl_nucleus_mean_corrected": effect + unit + cell*.2,
                             "gfp_mean_corrected": 1 + cell + unit*.2, "pair": f"pair{unit}",
                             "gfp_positive": True, "excluded": False})
    request = StatisticsRequest(metric="ncl_nucleus_mean_corrected", baseline="A", comparisons=[("A", "B")],
                                independent_units_confirmed=True,
                                plot=PlotSpec(language=language, kind=kind))
    return analyze(rows, request)


@pytest.mark.parametrize("kind", ["distribution", "scatter", "paired"])
def test_figure_vector_text_counts_and_source_tables(tmp_path, kind):
    result = statistical_result(kind=kind)
    render_figures(result, tmp_path)
    svg = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "<text" in svg and "units=3" in svg
    assert (tmp_path / "figure.pdf").read_bytes().startswith(b"%PDF")
    assert (tmp_path / "figure.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "field-summary.csv").is_file()
    if kind == "scatter":
        assert "not cluster-adjusted" in svg


def test_japanese_figure_font_is_explicit(tmp_path):
    try:
        font = japanese_font()
    except ValueError:
        pytest.skip("Japanese font must be installed in Linux runtime; local environment lacks it")
    metadata = render_figures(statistical_result(language="ja"), tmp_path)
    assert metadata["font"] == font
    assert "独立実験単位" in (tmp_path / "figure.svg").read_text(encoding="utf-8")

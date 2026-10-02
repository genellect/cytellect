import json
import shutil
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
from cytellect_analysis.replay import remeasure, replay
from cytellect_analysis.statistics import analyze, analyze_sensitivity


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
              "review_record": {"confirmed_at": 1.0, "accepted_invalidated_fields": []},
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


def test_replay_skips_only_explicitly_excluded_failed_fields(tmp_path):
    report, config, masks, _ = example(tmp_path)
    config["field_ids"].append("unreadable")
    config["field_snapshot"]["unreadable"] = config["field_snapshot"]["field"]
    config["exclusions"] = [{"field_id": "unreadable", "nucleus_id": None, "reason": "unreadable input"}]
    report["excluded_failed_fields"] = [{"field_id": "unreadable", "reason": "unreadable input"}]
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=masks)
    fresh = replay(tmp_path / "export" / "bundle", tmp_path / "originals", tmp_path / "replayed")
    assert fresh["cells"] == report["cells"]
    assert fresh["excluded_failed_fields"] == report["excluded_failed_fields"]
    config["exclusions"] = []
    build_export_bundle(tmp_path / "invalid", report=report, config=config, provenance={}, field_masks=masks)
    with pytest.raises(ValueError, match="replay_excluded_field_inconsistent"):
        replay(tmp_path / "invalid" / "bundle", tmp_path / "originals", tmp_path / "invalid-output")


def test_diagnostic_bundle_needs_recorded_review_before_replay(tmp_path):
    report, config, masks, _ = example(tmp_path)
    config.pop("review_record")
    build_export_bundle(tmp_path / "diagnostic", report=report, config=config, provenance={}, field_masks=masks)
    with pytest.raises(ValueError, match="replay_requires_complete_reviewed_masks"):
        replay(tmp_path / "diagnostic" / "bundle", tmp_path / "originals", tmp_path / "unreviewed")


@pytest.mark.parametrize("removed", ["revision.json", "masks/field/labels.npz"])
def test_replay_rejects_an_incomplete_hash_manifest(tmp_path, removed):
    report, config, masks, _ = example(tmp_path)
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=masks)
    manifest_path = tmp_path / "export" / "bundle" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["files"].pop(removed)
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")
    with pytest.raises(ValueError, match="replay_manifest_incomplete"):
        replay(manifest_path.parent, tmp_path / "originals", tmp_path / "unhashed")


def test_replay_uses_whole_field_exclusion_precedence(tmp_path):
    report, config, masks, _ = example(tmp_path)
    config["exclusions"] = [{"field_id": "field", "nucleus_id": 1, "reason": "specific object"},
                            {"field_id": "field", "nucleus_id": None, "reason": "whole field"}]
    report["cells"][0].update(excluded=True, exclusion_reason="whole field")
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=masks)
    fresh = replay(tmp_path / "export" / "bundle", tmp_path / "originals", tmp_path / "replayed")
    assert fresh["cells"] == report["cells"]


def test_export_consumes_field_masks_without_materializing_all_fields(tmp_path):
    report, config, masks, _ = example(tmp_path)
    def records():
        yield "field", masks["field"]
        assert (tmp_path / "export" / "bundle" / "masks" / "field" / "labels.npz").is_file()
        yield "second-field", masks["field"]
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={}, field_masks=records())
    assert (tmp_path / "export" / "bundle" / "masks" / "second-field" / "labels.npz").is_file()


@pytest.mark.parametrize("with_alternate", [False, True])
def test_replayed_statistics_and_figures_retain_adopted_revision(tmp_path, with_alternate):
    report = {"revision_id": "adopted-revision", "cells": [], "nucleoli": [], "manual_rois": [],
              "field_failures": [], "invalidated_nucleoli": []}
    config = {"recipe": Recipe().model_dump(), "field_ids": [], "field_snapshot": {},
              "backgrounds": {}, "exclusions": [],
              "review_record": {"confirmed_at": 1.0, "accepted_invalidated_fields": []}}
    masks = {}
    for group, effect in (("A", 0), ("B", 4)):
        for unit in range(3):
            fid = f"{group}{unit}"
            field_report, field_config, field_masks, _ = example(tmp_path / fid)
            snapshot = field_config["field_snapshot"]["field"]
            snapshot["metadata"].update(condition=group, experimental_unit=fid, sample=fid)
            raw = tmp_path / "originals" / fid
            shutil.copytree(tmp_path / fid / "originals" / "field", raw)
            ncl = tifffile.imread(raw / "ncl.tif")
            ncl[field_masks["field"]["nuclei"] > 0] += effect + unit
            tifffile.imwrite(raw / "ncl.tif", ncl)
            snapshot["image_info"]["inputs"]["ncl"]["sha256"] = sha256(raw / "ncl.tif")
            channels = {role: tifffile.imread(raw / f"{role}.tif") for role in ("dapi", "ncl", "gfp")}
            layers = field_masks["field"]
            background = field_config["backgrounds"]["field"]
            measured = measure(channels, layers["nuclei"], layers["nucleoli"],
                               polygon_mask(ncl.shape, background["polygon"]), Recipe(),
                               snapshot["metadata"], fid, layers["manual"])
            for key, values in zip(("cells", "nucleoli", "manual_rois"), measured, strict=True):
                report[key].extend(values)
            config["field_ids"].append(fid)
            config["field_snapshot"][fid] = snapshot
            config["backgrounds"][fid] = background
            masks[fid] = layers
    report["cells"] = apply_gfp_gate(report["cells"], Recipe())
    spec = StatisticsRequest(metric="ncl_nucleoplasm_mean_corrected", baseline="A", comparisons=[("A", "B")],
                             independent_units_confirmed=True, sensitivity_gfp_thresholds=[0])
    alternate_rows = {}
    if with_alternate:
        spec.sensitivity_region_revision_ids = ["alternate"]
        alternate_config = json.loads(json.dumps(config))
        alternate_config["recipe"]["nucleolar_method"] = "dapi-low"
        snapshot_root = tmp_path / "statistics-job" / "alternatives" / "0"
        snapshot_root.mkdir(parents=True)
        for fid, layers in masks.items():
            folder = snapshot_root / "masks" / fid
            folder.mkdir(parents=True)
            alternative = layers["nucleoli"].copy()
            alternative[4] = 0
            np.savez_compressed(folder / "labels.npz", **{**layers, "nucleoli": alternative})
        alternate_report = remeasure(alternate_config, {**report, "revision_id": "alternate"},
                                     snapshot_root / "masks", tmp_path / "originals")
        for name, data in (("revision.json", {"id": "alternate", "config": alternate_config}),
                           ("measurements.json", alternate_report), ("provenance.json", {"synthetic": True})):
            (snapshot_root / name).write_text(json.dumps(data), encoding="utf-8")
        alternate_rows["alternate"] = alternate_report["cells"]
        assert alternate_report["cells"][0][spec.metric] != report["cells"][0][spec.metric]
    result = analyze_sensitivity(report["cells"], spec, alternate_rows=alternate_rows)
    if with_alternate:
        result["region_sensitivity_sources"] = [{"revision_id": "alternate", "reviewed": True,
            "relative_path": "alternatives/0", "nucleolar_definition": {"nucleolar_method": "dapi-low"}}]
    result["revision_id"] = report["revision_id"]
    build_export_bundle(tmp_path / "export", report=report, config=config, provenance={},
                         field_masks=masks, statistics_results=[result],
                         statistics_roots=[(0, tmp_path / "statistics-job")] if with_alternate else [])
    replay(tmp_path / "export" / "bundle", tmp_path / "originals", tmp_path / "replayed")
    folder = tmp_path / "replayed" / "statistics" / "0"
    fresh = json.loads((folder / "result.json").read_text(encoding="utf-8"))
    figure = json.loads((folder / "figure-data.json").read_text(encoding="utf-8"))
    assert fresh["comparisons"] == result["comparisons"]
    assert fresh["revision_id"] == figure["revision_id"] == "adopted-revision"
    assert fresh["sensitivities"] == json.loads(json.dumps(result["sensitivities"]))
    scenario_rows = fresh["sensitivities"][0]["result"]["plot_data"]
    assert all(row["gfp_gate_threshold"] == 0 and row["gfp_gate_method"] == "manual"
               and row["gfp_gate_exploratory"] and row["gfp_negative_control_fields"] == []
               for row in scenario_rows)
    assert all(row["gfp_gate_method"] == "none" for row in fresh["plot_data"])
    if with_alternate:
        recalculated = json.loads((folder / "alternatives" / "0" / "measurements.json").read_text(encoding="utf-8"))
        assert recalculated["cells"] == alternate_rows["alternate"]


def statistical_result(language="en", kind="distribution"):
    rows = []
    for group, effect in (("A", 0), ("B", 2)):
        for unit in range(3):
            for cell in range(3):
                rows.append({"condition": group, "experimental_unit": f"{group}{unit}", "sample": f"{group}{unit}",
                             "field_id": f"{group}{unit}", "acquisition_date": "d",
                             "ncl_nucleus_mean_corrected": effect + unit + cell*.2 + effect*unit*.05,
                             "gfp_mean_corrected": 1 + cell + unit*.2, "pair": f"pair{unit}",
                             "gfp_positive": True, "excluded": False})
    request = StatisticsRequest(metric="ncl_nucleus_mean_corrected", baseline="A", comparisons=[("A", "B")],
                                independent_units_confirmed=True, paired=kind == "paired",
                                plot=PlotSpec(language=language, kind=kind))
    return analyze(rows, request)


@pytest.mark.parametrize("kind", ["distribution", "scatter", "paired"])
def test_figure_vector_text_counts_and_source_tables(tmp_path, kind):
    result = statistical_result(kind=kind)
    render_figures(result, tmp_path)
    svg = (tmp_path / "figure.svg").read_text(encoding="utf-8")
    assert "<text" in svg
    assert "independent units=3" in (tmp_path / "figure-caption.md").read_text(encoding="utf-8")
    assert (tmp_path / "figure.pdf").read_bytes().startswith(b"%PDF")
    assert (tmp_path / "figure.png").read_bytes().startswith(b"\x89PNG")
    assert (tmp_path / "field-summary.csv").is_file()
    if kind == "scatter":
        assert "no regression or cell-independent confidence band" in (tmp_path / "figure-caption.md").read_text(encoding="utf-8")


def test_japanese_figure_font_is_explicit(tmp_path):
    try:
        font = japanese_font()
    except ValueError:
        pytest.skip("Japanese font must be installed in Linux runtime; local environment lacks it")
    metadata = render_figures(statistical_result(language="ja"), tmp_path)
    assert metadata["font"] == font
    assert "独立実験単位" in (tmp_path / "figure.svg").read_text(encoding="utf-8")


def test_methods_describe_real_field_engine_chain_and_complete_legacy_parameters():
    from cytellect_analysis.exports import methods_text
    recipe = Recipe(id="ncl-legacy-rgb", gfp_gate="negative-control", gfp_threshold=6,
                    gfp_negative_control_fields=["negative"], gfp_negative_control_confirmed=True)
    provenance = {"fields": {"f": {"engine": "reused-reviewed-labels", "source_revision": "parent",
                                   "source_provenance": {"engine": "Fiji StarDist", "model_sha256": "abc", "n_tiles": 4}}}}
    methods = methods_text({"recipe": recipe.model_dump()}, provenance, {"revision_id": "new"})
    assert "Field f: reused-reviewed-labels" in methods and "Fiji StarDist" in methods
    assert "engine identity unavailable" not in methods
    for text in ("320", "anti-aliased bilinear", "MAD", "clipped to zero", "300", "6000",
                 "negative", "otsu-qc-batch", "provenance.json", "REPLAY.md", '"seed": 0'):
        assert text in methods


@pytest.mark.parametrize("ome", [False, True])
def test_gfp_only_bundle_replays_without_fabricated_ncl(tmp_path, ome):
    report, config, masks, files = example(tmp_path)
    recipe = Recipe(id="gfp-nuclear-2d")
    config["recipe"] = report["recipe"] = recipe.model_dump()
    info = config["field_snapshot"]["field"]["image_info"]
    info["inputs"].pop("ncl")
    masks["field"]["nucleoli"][:] = 0
    config["field_snapshot"]["field"]["image_info"]["channel_roles"] = ["dapi", "gfp"]
    channels = {role: tifffile.imread(tmp_path / "originals" / "field" / f"{role}.tif") for role in ("dapi", "gfp")}
    cells, objects, manual = measure(channels, masks["field"]["nuclei"], masks["field"]["nucleoli"],
                                    polygon_mask(channels["dapi"].shape, config["backgrounds"]["field"]["polygon"]),
                                    recipe, config["field_snapshot"]["field"]["metadata"], "field", masks["field"]["manual"])
    report.update(cells=apply_gfp_gate(cells, recipe), nucleoli=objects, manual_rois=manual)
    if ome:
        path = tmp_path / "originals" / "field" / "ome.tif"
        tifffile.imwrite(path, np.stack([channels["gfp"], channels["dapi"]]), ome=True, metadata={"axes": "CYX"})
        info["inputs"] = {"ome": {"sha256": sha256(path)}}
        info["channel_mapping"] = [1, 0]
        files = [("field/ome.tif", path)]
    build_export_bundle(tmp_path / "export", report=report, config=config,
                         provenance={}, field_masks=masks, raw_files=[v for v in files if not v[0].endswith("ncl.tif")])
    fresh = replay(tmp_path / "export" / "bundle", tmp_path / "originals", tmp_path / "replayed")
    assert fresh["cells"] == report["cells"]
    assert fresh["cells"][0]["ncl_nucleus_mean_corrected"] is None

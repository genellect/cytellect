"""Private, traceable result bundles. Original images require explicit opt-in."""
import hashlib
import importlib.metadata
import json
import platform
import re
import zipfile
from pathlib import Path

import numpy as np
import tifffile

from .exports_csv import write_csv
from .roi import export_roi_zip

ENVIRONMENT_PACKAGES = ("cytellect", "numpy", "scipy", "pandas", "statsmodels", "matplotlib",
                        "scikit-image", "tifffile", "roifile", "pydantic")


def _json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2, sort_keys=True), encoding="utf-8")


def _safe_id(value):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", value):
        raise ValueError("invalid_export_identifier")
    return value


def environment():
    versions = {}
    for name in ENVIRONMENT_PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = "unavailable"
    return {"python": platform.python_version(), "system": platform.system(), "architecture": platform.machine(),
            "packages": versions}


def methods_text(config, provenance, report, statistics_results=()):
    recipe = config.get("recipe", report.get("recipe", {}))
    legacy = recipe.get("id") == "ncl-legacy-rgb"
    lines = ["# Cytellect Methods", "", "Generated from the recorded configuration; review before publication.", "",
             f"Analysis revision: {report.get('revision_id', 'not recorded')}.",
             f"Recipe: {recipe.get('id', 'not recorded')} {recipe.get('version', 'not recorded')}.",
             f"Detection engine: {provenance.get('engine', 'not recorded')}. Random seed: {recipe.get('seed', 'not recorded')}.",
             "", "## Images and regions", "",
             "Input hashes, axis/channel assignments and per-field metadata are preserved in revision.json.",
             "Saved label masks in original pixel coordinates define nuclei and nucleolar candidates; "
             "the nucleoplasm is the nuclear pixel set minus the nucleolar union. "
             "Nucleolar mean intensity uses all union pixels, not an unweighted mean of individual objects.",
             f"Candidate definition: {recipe.get('nucleolar_method', 'not recorded')}; "
             f"Gaussian sigma {recipe.get('smoothing_sigma_px', 'not recorded')} px; "
             f"minimum area {recipe.get('minimum_area_px', 'not recorded')} px; "
             f"split touching candidates {recipe.get('split_touching', False)}.",
             "NCL-defined candidates can change as NCL redistributes; this is a region-definition limitation.",
             "Display LUTs do not change measurement pixels. Source images are immutable.",
             "", "## Quantification and selection", "",
             ("Legacy background is the median of all pixels outside all nuclei on the downsampled measurement grid; "
              "if there are no outside pixels, zero is used as in the historical procedure. This assumption is specific "
              "to compatibility analysis. Raw values and clipped nonnegative corrected values are both retained."
              if legacy else "Background is the median of the recorded user-confirmed background ROI. "
              "Raw and background-corrected mean, median and integrated intensities are retained."),
             ("This is a compatibility recipe. Its recorded grayscale conversion, resampling, clipping and epsilon "
              "are distinct from native quantification; consult recipe provenance for the exact implementation."
              if legacy else "Native background correction preserves negative values. "
              "The nucleoplasm/nucleolar ratio and its log2 value require positive means for both compartments; "
              "undefined ratios retain a missing-value reason rather than an arbitrary epsilon."),
             f"GFP selection: {recipe.get('gfp_gate', 'not recorded')}; "
             f"threshold {recipe.get('gfp_threshold')}; maximum {recipe.get('gfp_maximum')}. "
             "Batch-specific thresholds and per-object selection reasons are recorded in measurements.json.",
             "Explicit exclusions are retained. Missing physical calibration is reported in pixels, without invented micrometre units.",
             f"Failed fields: {len(report.get('field_failures', []))}. "
             f"Fields awaiting nucleolar review: {len(report.get('invalidated_nucleoli', []))}.",
             "", "## Statistical analysis", ""]
    if not statistics_results:
        lines.append("No statistical analysis is included in this bundle.")
    for index, result in enumerate(statistics_results):
        spec = result["spec"]
        lines += [f"Analysis {index}: statistics protocol {result.get('statistics_version', 'not recorded')}; "
                  f"metric {spec['metric']}; mode {spec['mode']}.",
                  f"Aggregation: {result.get('aggregation', 'recorded in result.json')}.",
                  f"Baseline: {spec['baseline']}; planned comparisons: {json.dumps(spec['comparisons'], ensure_ascii=False)}; "
                  f"Holm family: {spec.get('comparison_family', 'all')}; paired: {spec['paired']}.",
                  "Observation, field and independent experimental unit counts are reported separately. "
                  "Intervals for individual comparisons are 95% and are not simultaneous multiplicity-adjusted intervals."]
        if result.get("model"):
            lines += [f"Model: {result['model']['formula']}.",
                      f"GFP transform: {result['model']['gfp_transform']}; {result['model']['gfp_centering']}.",
                      "OLS uses field-clustered CRV1 standard errors with finite-sample correction and t inference "
                      "with number-of-fields minus one degrees of freedom. Cell/field inference is exploratory.",
                      f"Adjusted means: {result['model']['adjusted_means']}."]
        lines += ["Warnings: " + "; ".join(result.get("warnings", []))]
    lines += ["", "## Reproducibility and exchange", "",
              "measurement JSON is authoritative. CSV strings that could execute spreadsheet formulas are prefixed "
              "with an apostrophe; numeric values remain numeric. SVG uses editable text, PDF embeds TrueType fonts.",
              "Fiji ROI ZIPs contain exact integer rectangles for each horizontal object run. "
              "Use Cytellect's manifest to reconstruct object IDs. Arbitrary imported polygon ROIs are unsupported.",
              "Run replay.py with the documented raw-image directory and the recorded environment. "
              "Masks are replayed as approved regions; automatic detection is not rerun by the measurement replay.",
              "Original images are omitted unless explicitly requested. Bundles contain confidential derived research "
              "information and must be stored privately.", ""]
    return "\n".join(lines)


def build_export_bundle(destination: Path, *, report, config, provenance, field_masks,
                        raw_files=(), statistics_results=(), include_raw=False):
    """field_masks: {field_id: {nuclei, nucleoli, manual: uint32 2D ndarray}}.

    raw_files contains (field_id/role.tif, private Path), never uploaded names.
    Files remain private: the caller must enforce ownership and expiration on this directory.
    """
    destination.mkdir(parents=True, exist_ok=True)
    content = destination / "bundle"
    content.mkdir(exist_ok=False)
    statistics_results = list(statistics_results)
    _json(content / "measurements.json", report)
    _json(content / "revision.json", {"id": report.get("revision_id"), "config": config})
    _json(content / "provenance.json", provenance)
    _json(content / "environment.json", environment())
    for name, key in (("cells", "cells"), ("nucleoli", "nucleoli"), ("manual-rois", "manual_rois")):
        write_csv(content / f"{name}.csv", report.get(key, []))
    for fid, masks in sorted(field_masks.items()):
        _safe_id(fid)
        folder = content / "masks" / fid
        folder.mkdir(parents=True)
        if set(masks) != {"nuclei", "nucleoli", "manual"}:
            raise ValueError("export_mask_layers_missing")
        np.savez_compressed(folder / "labels.npz", **masks)
        for layer, labels in masks.items():
            tifffile.imwrite(folder / f"{layer}.tif", np.asarray(labels, dtype=np.uint32), metadata={"axes": "YX"})
            export_roi_zip(labels, folder / f"{layer}-rois.zip")
    raw_manifest = []
    if include_raw:
        raw_files = list(raw_files)
        expected_raw = {f"{fid}/{role}.tif": details["sha256"]
                        for fid, field in config.get("field_snapshot", {}).items()
                        for role, details in field["image_info"]["inputs"].items()}
        if {name for name, _ in raw_files} != set(expected_raw):
            raise ValueError("raw_export_inputs_incomplete")
        for name, source in raw_files:
            if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}/(dapi|ncl|gfp|ome)\.tif", name):
                raise ValueError("invalid_raw_export_name")
            target = content / "raw" / name
            if target.exists():
                raise ValueError("duplicate_raw_export")
            target.parent.mkdir(parents=True, exist_ok=True)
            source = Path(source)
            digest = hashlib.sha256()
            with source.open("rb") as src, target.open("xb") as dst:
                while block := src.read(1024 * 1024):
                    dst.write(block)
                    digest.update(block)
            if digest.hexdigest() != expected_raw[name]:
                raise ValueError("raw_export_hash_mismatch")
            raw_manifest.append({"path": f"raw/{name}", "sha256": digest.hexdigest()})
    from .figures import render_figures
    for index, result in enumerate(statistics_results):
        folder = content / "statistics" / str(index)
        folder.mkdir(parents=True)
        _json(folder / "result.json", result)
        render_figures(result, folder)
    methods = methods_text(config, provenance, report, statistics_results)
    (content / "methods.md").write_text(methods, encoding="utf-8")
    (destination / "methods.md").write_text(methods, encoding="utf-8")
    (content / "replay.py").write_text(
        '"""Run with the Cytellect environment recorded in environment.json."""\n'
        'from cytellect_analysis.replay import main\n'
        'if __name__ == "__main__":\n    main()\n', encoding="utf-8")
    (content / "REPLAY.md").write_text(
        "# Reproduce approved-mask quantification\n\n"
        "Install the exact Cytellect code commit and locked dependencies recorded in provenance/environment. "
        "From the extracted package run:\n\n"
        "    python replay.py --bundle-dir . --raw-dir /private/originals --output-dir /private/replayed\n\n"
        "The originals directory must contain <field_id>/dapi.tif, ncl.tif, gfp.tif, or ome.tif as "
        "recorded in revision.json. Original file hashes are verified before reading. "
        "Use --raw-dir raw only when originals were explicitly included. "
        "Replay uses saved corrected masks; it does not download models or rerun segmentation. "
        "Compare replayed measurements, comparisons and figures with the exported source. "
        "Store this package privately.\n", encoding="utf-8")
    members = sorted(path for path in content.rglob("*") if path.is_file())
    manifest = {"format": "cytellect-reproducibility/1", "revision_id": report.get("revision_id"),
                "raw_included": include_raw, "raw_files": raw_manifest,
                "replay_scope": "approved masks -> measurements -> recorded statistical analyses and plots",
                "files": {p.relative_to(content).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in members}}
    _json(content / "manifest.json", manifest)
    archive_path = destination / "analysis.zip"
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted(p for p in content.rglob("*") if p.is_file()):
            entry = zipfile.ZipInfo(path.relative_to(content).as_posix(), date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = 0o600 << 16
            with path.open("rb") as source, archive.open(entry, "w") as target:
                while block := source.read(1024 * 1024):
                    target.write(block)
    return archive_path

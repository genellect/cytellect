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


def _engine_chain(record):
    parts = []
    seen = set()
    while isinstance(record, dict) and record and id(record) not in seen:
        seen.add(id(record))
        identity = record.get("engine", record.get("name", "engine identity unavailable"))
        details = {k: v for k, v in record.items() if k in
                   ("version", "model", "model_name", "model_sha256", "runtime_sha256", "n_tiles",
                    "nucleolar_detection", "source_revision")}
        parts.append(str(identity) + (" " + json.dumps(details, ensure_ascii=False, sort_keys=True) if details else ""))
        record = record.get("source_provenance")
    return " <- ".join(parts)


def methods_text(config, provenance, report, statistics_results=()):
    recipe = config.get("recipe", report.get("recipe", {}))
    legacy = recipe.get("id") == "ncl-legacy-rgb"
    gfp_only = recipe.get("id") == "gfp-nuclear-2d"
    fields = provenance.get("fields") or report.get("engine_provenance") or {}
    lines = ["# Cytellect Methods", "", "Generated from recorded configuration; review before publication.", "",
             f"Analysis revision: {report.get('revision_id', provenance.get('revision_id', 'unavailable'))}.",
             f"Recipe: {recipe.get('id')} {recipe.get('version')}; random seed {recipe.get('seed')}.",
             "Measurement protocol versions: " + ", ".join(sorted({
                 str(row.get("measurement_protocol_version", "unrecorded")) for row in report.get("cells", [])})) + ".",
             "", "## Detection and region history", ""]
    if fields:
        lines += [f"- Field {fid}: {_engine_chain(record)}." for fid, record in sorted(fields.items())]
    else:
        lines.append(f"Detection engine: {provenance.get('engine', 'engine identity unavailable in this export')}.")
    lines += ["",
              "Reused masks retain their source revision and nested detector provenance; edits determine the saved canonical pixel sets.",
              f"StarDist normalization percentiles {recipe.get('percentile_low')}–{recipe.get('percentile_high')}; "
              f"probability threshold {recipe.get('probability')}; NMS threshold {recipe.get('nms')}.",
              "Input hashes, acquired channel roles, axis assignments and calibration are in "
              "[revision.json](revision.json); detector versions, model/runtime hashes and code identity are in "
              "[provenance.json](provenance.json). Absent channels are missing, never measured zero.",
              "Source images are immutable. Display LUTs do not change measurement pixels.",
              "Saved masks use original image coordinates. The nucleoplasm is the nucleus minus the nucleolar union; "
              "the union mean uses all pixels, not an unweighted mean of object means."]
    if gfp_only:
        lines += ["This GFP nuclear recipe measures DAPI-defined nuclear GFP. NCL and nucleolar detection are not performed. "
                  "Nucleolar counts, areas and NCL intensities are not measured."]
    elif legacy:
        parameters = recipe.get("legacy", {})
        lines += ["Compatibility RGB conversion takes max(R,G,B) and ignores alpha. The longest dimension is resized to "
                  f"at most {parameters.get('target_long_dimension_px')} pixels without upsampling, using anti-aliased bilinear "
                  "resampling. Floating resized values are used for measurement; only detection DAPI is rounded to source dtype. "
                  "Canonical labels are restored by nearest-neighbour resampling and reprojected to the recorded measurement grid.",
                  "Within each nucleus the compatibility high region uses strict greater-than Otsu. A uniform signal uses "
                  "the whole nucleus; fewer than max(3, ceil(0.01*nuclear pixels)) high pixels triggers the top10-percent "
                  "percentile rule including ties. These compatibility fallbacks are recorded and do not apply to native analysis.",
                  "Legacy background is the median outside all nuclei on the measurement grid; if no outside pixels exist, "
                  "zero is used. Corrected negative pixels are clipped to zero. Epsilon=max(1, 1.4826*MAD of background NCL). "
                  "The compatibility index is log2[(whole-nucleus corrected mean+epsilon)/(high-region corrected mean+epsilon)].",
                  f"Legacy QC enabled {parameters.get('apply_quality_exclusions')}; minimum 20 measurement-grid nuclear pixels; "
                  f"area range {parameters.get('nucleus_area_min_scaled_px')}–{parameters.get('nucleus_area_max_scaled_px')} scaled pixels; "
                  f"DAPI SNR minimum {parameters.get('dapi_snr_min')}; saturation fraction maximum "
                  f"{parameters.get('saturation_fraction_max')}; touching image borders is excluded when QC is enabled.",
                  f"Legacy GFP mode: {parameters.get('gfp_mode')}. In otsu-qc-batch mode the batch threshold is fitted only "
                  "to independently QC-passing nuclei; a constant distribution uses its median."]
    else:
        lines += [f"Nucleolar candidate definition {recipe.get('nucleolar_method')}; Gaussian sigma "
                  f"{recipe.get('smoothing_sigma_px')} px; minimum area {recipe.get('minimum_area_px')} px; "
                  f"split touching {recipe.get('split_touching')}; DAPI-low percentile {recipe.get('dapi_low_percentile')}.",
                  "Native candidates have no whole-nucleus/top-fraction fallback. Background is the median of each recorded "
                  "user-confirmed ROI. Corrected negative values remain signed. Nucleoplasm/nucleolar mean ratios and log2 "
                  "ratios require both corrected means to be positive; otherwise a missing-value reason is retained."]
    if not gfp_only:
        lines.append("NCL-defined regions can change with the NCL distribution; this circular region-definition limitation "
                     "requires interpretation and sensitivity checks independent of the desired outcome.")
    lines += ["", "## Quantification and selection", "",
              ("Background is the median of the confirmed ROI and native negative corrections remain signed." if not legacy else "Compatibility background and clipping follow the recorded procedure above."),
              "Raw/corrected mean, median and pixel-sum intensities are retained. Pixel-sum units depend on the stated grid. "
              "Missing physical calibration produces pixel areas, not invented micrometre units. Saturation fractions count "
              "pixels at the stored integer dtype maximum; camera-specific effective-bit saturation is not inferred.",
              f"Recorded GFP gate {recipe.get('gfp_gate')}; threshold {recipe.get('gfp_threshold')}; "
              f"maximum {recipe.get('gfp_maximum')}; negative-control fields "
              f"{json.dumps(recipe.get('gfp_negative_control_fields', []))}; explicit control confirmation "
              f"{recipe.get('gfp_negative_control_confirmed', False)}.",
              "Actual batch thresholds, epsilon, coordinate transforms, selection reasons and exclusions are retained in "
              "[measurements.json](measurements.json). A disabled GFP gate does not imply GFP positivity was measured.",
              f"Failed fields {len(report.get('field_failures', []))}; fields flagged for nucleolar review "
              f"{len(report.get('invalidated_nucleoli', []))}; review decisions in revision.json.",
              "", "## Statistical analysis", ""]
    if not statistics_results:
        lines.append("No statistical analysis is included in this bundle.")
    for index, result in enumerate(statistics_results):
        spec = result["spec"]
        lines += [f"Analysis {index}: statistics protocol {result.get('statistics_version')}; metric {spec['metric']}; "
                  f"mode {spec['mode']}. [Recorded result](statistics/{index}/result.json).",
                  f"Aggregation: {result.get('aggregation')}.",
                  f"Baseline {spec['baseline']}; planned comparisons {json.dumps(spec['comparisons'], ensure_ascii=False)}; "
                  f"Holm family {spec.get('comparison_family', 'all')}; paired {spec['paired']}.",
                  "Tests are two-sided. Exact statistic, degrees of freedom, effect estimate, standard error, p value and "
                  "Holm-adjusted p value are retained. Individual 95% intervals are not simultaneous multiplicity-adjusted intervals. "
                  "Observation, field and independent-unit counts and groupwise missingness are reported separately."]
        if result.get("model"):
            model = result["model"]
            lines += [f"Model {model['formula']}; GFP transform {model['gfp_transform']}; {model['gfp_centering']}.",
                      "OLS uses field-clustered CRV1 finite-sample covariance and t inference with fields minus one degrees "
                      "of freedom. Between-field dependence within one biological unit is not accounted for by field clustering. "
                      "These analyses are exploratory.",
                      f"Adjusted means: {model['adjusted_means']}."]
        lines += ["Warnings: " + "; ".join(result.get("warnings", []))]
    lines += ["", "## Reproducibility and exchange", "",
              "The complete recorded recipe, including inactive options for auditability, is:", "",
              chr(96)*3 + "json", json.dumps(recipe, ensure_ascii=False, indent=2, sort_keys=True), chr(96)*3, "",
              "Measurement JSON is authoritative. Potential spreadsheet formulas in text are prefixed with an apostrophe in "
              "CSV; numeric values remain numeric. Fiji ROI ZIPs preserve exact pixel sets as integer horizontal-run rectangles; "
              "their manifest preserves object grouping. Arbitrary polygon imports are unsupported.",
              "Restore the code and [environment](environment.json), then follow [REPLAY.md](REPLAY.md) and run "
              "[replay.py](replay.py). [manifest.json](manifest.json) records package hashes. Replay verifies original hashes "
              "and uses approved saved masks; it does not redownload models or rerun detection.",
              "Original images are omitted unless explicitly requested. Derived results remain confidential.", ""]
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
        result = {**result, "figure": render_figures(result, folder)}
        _json(folder / "result.json", result)
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

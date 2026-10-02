"""Verify published GFP exports and compare Cytellect to actual ImageJ ROI statistics."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import subprocess
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/public/bbbc013"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    for field in manifest["images"]:
        for item in field["channels"].values():
            path = FIXTURE / item["path"]
            values = tifffile.imread(path)
            if digest(path.read_bytes()) != item["sha256"] or digest(values.tobytes()) != item["pixel_sha256"]:
                raise ValueError("public_gfp_fixture_hash_mismatch")
            if list(values.shape) != item["shape"] or str(values.dtype) != item["dtype"]:
                raise ValueError("public_gfp_fixture_format_mismatch")
    return manifest


def acquire():
    manifest = json.loads((FIXTURE / "manifest.json").read_text(encoding="utf-8"))
    with tempfile.TemporaryDirectory() as directory:
        archive = Path(directory) / "images.zip"
        urllib.request.urlretrieve(manifest["archive"]["url"], archive)
        if digest(archive.read_bytes()) != manifest["archive"]["sha256"]:
            raise ValueError("public_gfp_archive_hash_mismatch")
        with zipfile.ZipFile(archive) as bundle:
            for field in manifest["images"]:
                for item in field["channels"].values():
                    raw = bundle.read(item["source_member"])
                    if digest(raw) != item["source_sha256"]:
                        raise ValueError("public_gfp_member_hash_mismatch")
                    image = Image.open(io.BytesIO(raw))
                    palette = image.getpalette()
                    if palette is not None and any(palette[3*i:3*i+3] != [i, i, i] for i in range(256)):
                        raise ValueError("non_identity_gray_palette")
                    values = np.asarray(image)
                    tifffile.imwrite(FIXTURE / item["path"], values, photometric="minisblack", metadata=None)
    return verify()


def reference_offset(labels):
    # Fixed spatial search, independent of GFP intensities. This is an arithmetic
    # validation offset ROI, NOT a claim that the region is biologically cell-free.
    for y in range(0, labels.shape[0] - 14, 15):
        for x in range(0, labels.shape[1] - 14, 15):
            if not labels[y:y+15, x:x+15].any():
                mask = np.zeros(labels.shape, dtype=bool)
                mask[y:y+15, x:x+15] = True
                return mask, {"x": x, "y": y, "width": 15, "height": 15}
    raise ValueError("reference_offset_roi_unavailable")


def imagej_reference(image_path, labels, output, executable):
    from cytellect_analysis.engine import _classpath, runtime_info

    output.mkdir(parents=True, exist_ok=True)
    runtime, java, _ = runtime_info(executable)
    classes = output / "classes"
    classes.mkdir(exist_ok=True)
    cp = _classpath(runtime, classes)
    source = FIXTURE.parents[2] / "engines/fiji/Bbbc013Reference.java"
    prefs = source.with_name("CytellectPreferences.java")
    javac = java.with_name("javac.exe" if os.name == "nt" else "javac")
    subprocess.run([str(javac), "-encoding", "UTF-8", "-cp", cp, "-d", str(classes), str(source), str(prefs)], check=True, capture_output=True, timeout=120)
    label_path = output / "reference-labels.tif"
    tifffile.imwrite(label_path, labels.astype(np.float32), photometric="minisblack")
    request = {"mode": "measure", "input": str(image_path), "labels": str(label_path), "output": str(output)}
    request_path = output / "reference-request.json"
    request_path.write_text(json.dumps(request), encoding="utf-8")
    subprocess.run([str(java), "-Djava.awt.headless=true", "-Djava.util.prefs.PreferencesFactory=CytellectPreferences", "-Djava.io.tmpdir="+str(output), "-Duser.home="+str(output), "-cp", cp, "Bbbc013Reference", str(request_path)], check=True, capture_output=True, timeout=180)
    return json.loads((output / "imagej-reference.json").read_text())


def evaluate(directory, executable):
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect
    from cytellect_analysis.measurement import measure

    manifest = verify()
    directory = Path(directory).resolve()
    directory.mkdir(parents=True, exist_ok=True)
    recipe = Recipe(id="gfp-nuclear-2d", gfp_gate="none")
    fields = []
    for field in manifest["images"]:
        output = directory / field["id"]
        channels = {role: tifffile.imread(FIXTURE / item["path"]) for role, item in field["channels"].items()}
        nuclei, nucleoli, provenance = detect(channels, recipe, output / "detection", executable)
        assert not nucleoli.any() and not (output / "detection/ncl.tif").exists()
        offset, offset_rect = reference_offset(nuclei)
        cells, _, _ = measure(channels, nuclei, nucleoli, offset, recipe, {}, field["id"])
        reference_labels = nuclei.copy()
        reference_labels[offset] = 999999
        reference = imagej_reference(FIXTURE / field["channels"]["gfp"]["path"], reference_labels, output / "reference", executable)
        lookup = {row["id"]: row for row in reference}
        background = lookup[999999]["median"]
        errors: dict[str, list[float]] = {key: [] for key in ("area", "raw_mean", "raw_median", "raw_integrated", "offset_median", "corrected_mean", "corrected_integrated")}
        median_disagreements = []
        rows = []
        for cell in cells:
            ref = lookup[cell["nucleus_id"]]
            comparisons = {"area": (cell["nucleus_area_px"], ref["count"]),
                           "raw_mean": (cell["gfp_mean"], ref["mean"]),
                           "raw_median": (cell["gfp_median"], ref["median_midpoint"]),
                           "raw_integrated": (cell["gfp_integrated"], ref["integrated"]),
                           "offset_median": (cell["gfp_background"], background),
                           "corrected_mean": (cell["gfp_mean_corrected"], ref["mean"]-background),
                           "corrected_integrated": (cell["gfp_integrated_corrected"], ref["integrated"]-background*ref["count"])}
            for key, (actual, expected) in comparisons.items():
                error = abs(actual-expected)
                errors[key].append(error)
                if error > (1e-8 if "integrated" in key else 1e-10):
                    raise AssertionError(f"ImageJ reference mismatch: {field['id']} nucleus {cell['nucleus_id']} {key}")
            if cell["gfp_median"] != ref["median"]:
                median_disagreements.append({"id": cell["nucleus_id"], "cytellect": cell["gfp_median"], "imagej": ref["median"]})
            rows.append({"id": cell["nucleus_id"], "area": cell["nucleus_area_px"], "gfp_raw_mean": cell["gfp_mean"], "gfp_raw_integrated": cell["gfp_integrated"], "gfp_corrected_mean": cell["gfp_mean_corrected"], "imagej": ref})
        report = {"id": field["id"], "source_channels": field["channels"], "nuclei": len(cells), "offset_roi": offset_rect, "offset_median": background,
                  "maximum_absolute_errors": {key: max(values, default=0) for key, values in errors.items()},
                  "nuclear_median_differences": median_disagreements, "rows": rows, "engine": provenance}
        fields.append(report)
        (output / "comparison.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({"field": field["id"], "nuclei": len(cells), "max_errors": report["maximum_absolute_errors"], "median_differences": len(median_disagreements)}), flush=True)
    summary = {"dataset": manifest["dataset"], "recipe": recipe.model_dump(), "scope": "Fixed-mask numerical agreement, not segmentation accuracy, biological replication or native FRM validation", "reference": "Actual ImageJ ImagePlus.getStatistics on ThresholdToSelection ROIs from identical canonical masks; Java bridge does not call Python measurement functions", "reference_bridge_hash_normalization": "LF newlines", "reference_bridge_sha256": digest((FIXTURE.parents[2] / "engines/fiji/Bbbc013Reference.java").read_bytes().replace(b"\r\n", b"\n")), "background_caveat": "Reference offset: first 15x15 nuclear-mask-free spatial block, without GFP-based tuning; not a biologically validated cell-free region", "median_policy": "ImageJ histogram median and NumPy midpoint median differ for some even-sized ROIs; recorded separately, not silently rounded. Odd 225-pixel offset ROI removes this definitional difference for background validation.", "fields": fields}
    (directory / "benchmark.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--evaluate", type=Path)
    parser.add_argument("--fiji", default=os.environ.get("CYTELLECT_FIJI_EXECUTABLE", ""))
    args = parser.parse_args()
    if args.download:
        acquire()
    if args.evaluate:
        evaluate(args.evaluate, args.fiji)
    else:
        verify()
        print("BBBC013 paired published GFP/DRAQ fixtures verified")

"""Reproduce a source-attributed DAPI/NCL real-image validation outside the checkout."""
import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/nucleolar/manifest.json"


def acquire(data_dir):
    data_dir = Path(data_dir).resolve()
    if data_dir.is_relative_to(ROOT):
        raise ValueError("public_original_must_stay_outside_checkout")
    data_dir.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    target = data_dir / f"{manifest['accession']}.tiff"
    if not target.exists():
        with urllib.request.urlopen(manifest["download_url"], timeout=60) as response, target.open("xb") as stream:
            size = 0
            while block := response.read(1024*1024):
                size += len(block)
                if size > manifest["bytes"]:
                    raise ValueError("public_download_size_mismatch")
                stream.write(block)
    if target.stat().st_size != manifest["bytes"] or hashlib.sha256(target.read_bytes()).hexdigest() != manifest["sha256"]:
        raise ValueError("public_original_hash_mismatch")
    return target, manifest


def _preview(array):
    low, high = np.percentile(array, [1, 99.8])
    return np.uint8(np.clip((array.astype(float)-low)/max(high-low, 1), 0, 1)*255)


def evaluate(data_dir, output, executable):
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect
    from cytellect_analysis.masks import contours, validate_labels

    source, manifest = acquire(data_dir)
    output = Path(output).resolve()
    if output.is_relative_to(ROOT):
        raise ValueError("public_evaluation_work_must_stay_outside_checkout")
    output.mkdir(parents=True, exist_ok=True)
    with tifffile.TiffFile(source) as file:
        series = file.series[0]
        if (len(file.series) != 1 or series.axes != "CYX" or list(series.shape) != manifest["schema"]["shape"]
                or str(series.dtype) != "uint16"):
            raise ValueError("public_axes_changed")
        original = series.asarray()
    channels = {role: original[index] for role, index in manifest["schema"]["channel_map"].items()}
    recipe = Recipe()
    nuclei, nucleoli, provenance = detect(channels, recipe, output / "engine", executable)
    validate_labels(nuclei, nucleoli)
    np.savez_compressed(output / "labels.npz", nuclei=nuclei, nucleoli=nucleoli)
    dapi, ncl = _preview(channels["dapi"]), _preview(channels["ncl"])
    # The display is a LUT-derived result, never used as a measurement source.
    composite = np.stack([ncl, np.uint8(dapi.astype(float)*.25), dapi], axis=-1)
    Image.fromarray(composite).save(output / "demo-preview.png")
    Image.fromarray(dapi).save(output / "demo-dapi.png")
    Image.fromarray(ncl).save(output / "demo-ncl.png")
    cells = []
    for label in np.unique(nuclei):
        if label == 0:
            continue
        whole = nuclei == label
        enriched = whole & (nucleoli > 0)
        plasma = whole & ~enriched
        cells.append({
            "nucleus_id": int(label), "area_px": int(whole.sum()),
            "dna_mean_raw": float(channels["dapi"][whole].mean()),
            "ncl_nucleus_mean_raw": float(channels["ncl"][whole].mean()),
            "ncl_nucleoli_mean_raw": float(channels["ncl"][enriched].mean()) if enriched.any() else None,
            "ncl_nucleoplasm_mean_raw": float(channels["ncl"][plasma].mean()) if plasma.any() else None,
            "nucleolar_area_px": int(enriched.sum()), "nucleolar_count": int(np.unique(nucleoli[enriched]).size),
            "nucleolar_area_fraction": float(enriched.sum()/whole.sum()),
        })
    demo = {"dataset": manifest["dataset"], "source": manifest["source"], "license": manifest["license"],
            "license_url": manifest["license_url"], "publication": manifest["publication"],
            "attribution": manifest["attribution"], "image_id": manifest["accession"], "channel": "DAPI / NCL",
            "width": int(original.shape[2]), "height": int(original.shape[1]),
            "quantification": "Original uint16 DAPI/NCL pixels; compartment means use union pixels; no background correction or GFP.",
            "image_sha256": manifest["sha256"], "channel_mapping": manifest["schema"],
            "projection": manifest["projection"], "labels": contours(nuclei),
            "nucleolar_labels": contours(nucleoli), "measurements": cells, "engine": provenance,
            "nucleus_count": len(cells), "nucleolus_count": int(np.unique(nucleoli[nucleoli>0]).size),
            "validation_scope": manifest["validation_scope"],
            "unsupported": ["GFP (not acquired)", "detection accuracy (no ground-truth masks)", "group inference (one field)"],
            "display_transform": {"per_channel_percentiles": [1, 99.8], "ncl": "red", "dapi": "blue + 25 percent green",
                                  "original_pixels_modified": False, "spatial_downsampling": False}}
    (output / "demo.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
    print(json.dumps({"nuclei": len(cells), "nucleoli": demo["nucleolus_count"],
                      "source": manifest["accession"], "shape": list(original.shape),
                      "channel_map": manifest["schema"]["channel_map"], "accuracy_evaluated": False}), flush=True)
    return demo


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--fiji", default="")
    args = parser.parse_args()
    if args.output:
        evaluate(args.data_dir, args.output, args.fiji)
    else:
        target, _ = acquire(args.data_dir)
        print(f"Verified public accession: {target.name}")


if __name__ == "__main__":
    main()

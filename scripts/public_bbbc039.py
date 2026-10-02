"""Acquire/verify the fixed CC0 benchmark; optionally run real Fiji evaluation.

python scripts/public_bbbc039.py --verify
python scripts/public_bbbc039.py --download
python scripts/public_bbbc039.py --evaluate /private/public-benchmark --fiji /opt/fiji
All downloaded identifiers and pixels here are already publicly licensed BBBC039.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
import urllib.request
import zipfile
from pathlib import Path

import numpy as np
import tifffile
from PIL import Image
from scipy.optimize import linear_sum_assignment
from skimage.measure import label

FIXTURE = Path(__file__).resolve().parents[1] / "fixtures/public/bbbc039"


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    for field in manifest["images"]:
        for role in ("image", "mask"):
            item = field[role]
            if digest((FIXTURE / item["path"]).read_bytes()) != item["sha256"]:
                raise ValueError("public_fixture_hash_mismatch")
    return manifest


def acquire():
    manifest = json.loads((FIXTURE / "manifest.json").read_text())
    with tempfile.TemporaryDirectory() as temporary:
        for name, item in manifest["archives"].items():
            file = Path(temporary) / name
            urllib.request.urlretrieve(item["url"], file)
            if digest(file.read_bytes()) != item["sha256"]:
                raise ValueError("public_archive_hash_mismatch")
            if name == "metadata.zip":
                with zipfile.ZipFile(file) as bundle:
                    names = sorted(bundle.read("metadata/test.txt").decode().splitlines())[:5]
                    if [Path(n).stem for n in names] != [n["id"] for n in manifest["images"]]:
                        raise ValueError("public_split_changed")
            else:
                role = "image" if name == "images.zip" else "mask"
                with zipfile.ZipFile(file) as bundle:
                    for field in manifest["images"]:
                        item = field[role]
                        data = bundle.read(item["member"])
                        if digest(data) != item["sha256"]:
                            raise ValueError("public_member_hash_mismatch")
                        target = FIXTURE / item["path"]
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(data)
    return verify()


def decode_ground_truth(path):
    # Dataset author's documented decoder: connected components of equal-valued
    # pixels in the first channel. This preserves touching differently coloured
    # instances rather than binarizing all nonzero colours.
    pixels = np.asarray(Image.open(path))
    return label(pixels[..., 0] if pixels.ndim == 3 else pixels, connectivity=2).astype(np.uint32)


def match_instances(truth, prediction, threshold=0.5):
    truth_ids = np.r_[0, np.unique(truth[truth > 0])]
    prediction_ids = np.r_[0, np.unique(prediction[prediction > 0])]
    truth = np.searchsorted(truth_ids, truth).reshape(-1)
    prediction = np.searchsorted(prediction_ids, prediction).reshape(-1)
    matrix = np.zeros((int(truth.max()) + 1, int(prediction.max()) + 1), dtype=np.int64)
    np.add.at(matrix, (truth, prediction), 1)
    intersection = matrix[1:, 1:].astype(float)
    union = matrix.sum(axis=1)[1:, None] + matrix.sum(axis=0)[None, 1:] - intersection
    iou = np.divide(intersection, union, out=np.zeros_like(intersection), where=union > 0)
    if iou.size:
        # Maximize valid one-to-one matches first, then IoU among equally sized matchings.
        row, col = linear_sum_assignment(-(iou >= threshold).astype(float) - iou / (min(iou.shape) + 1))
        tp = int(np.count_nonzero(iou[row, col] >= threshold))
    else:
        tp = 0
    nt, npred = matrix.shape[0] - 1, matrix.shape[1] - 1
    fp, fn = npred - tp, nt - tp
    return {"true_instances": nt, "predicted_instances": npred, "tp": tp, "fp": fp, "fn": fn,
            "precision": tp / npred if npred else 0., "recall": tp / nt if nt else 0.,
            "f1": 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 1., "iou_threshold": threshold}


def evaluate(output, executable):
    from cytellect_analysis.contracts import Recipe
    from cytellect_analysis.engine import detect
    from cytellect_analysis.masks import contours

    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=True)
    manifest = verify()
    records = []
    for index, field in enumerate(manifest["images"]):
        original = tifffile.imread(FIXTURE / field["image"]["path"])
        truth = decode_ground_truth(FIXTURE / field["mask"]["path"])
        # The engine API accepts NCL; zeros are only a non-measured placeholder in
        # this nuclei-only benchmark. They are never presented as acquired NCL.
        nuclei, _, provenance = detect({"dapi": original, "ncl": np.zeros_like(original)}, Recipe(),
                                        output / field["id"], executable)
        record = {"id": field["id"], **match_instances(truth, nuclei),
                  "image_sha256": field["image"]["sha256"],
                  "bridge_sha256": provenance["bridge_sha256"],
                  "model_sha256": provenance["model_sha256"],
                  "n_tiles": provenance["n_tiles"]}
        records.append(record)
        print(json.dumps(record), flush=True)
        if index == 0:
            low, high = np.percentile(original, [1, 99.8])
            preview = np.round(np.clip((original.astype(float) - low) / (high - low), 0, 1) * 255).astype(np.uint8)
            Image.fromarray(preview).save(output / "demo-preview.png")
            measurements = []
            for nucleus in np.unique(nuclei):
                if not nucleus:
                    continue
                values = original[nuclei == nucleus].astype(float)
                measurements.append({"nucleus_id": int(nucleus), "area_px": int(values.size),
                                     "dna_mean_raw": float(values.mean()), "dna_integral_raw": float(values.sum())})
            demo = {"dataset": manifest["dataset"], "source": manifest["source"], "license": manifest["license"],
                    "image_id": field["id"], "channel": "DNA / Hoechst", "width": int(original.shape[1]),
                    "height": int(original.shape[0]), "quantification": "original 16-bit DNA pixels; no background correction",
                    "image_sha256": field["image"]["sha256"], "labels": contours(nuclei),
                    "measurements": measurements, "benchmark": record, "engine": provenance,
                    "unsupported": ["NCL", "GFP", "nucleolar quantification"]}
            (output / "demo.json").write_text(json.dumps(demo, indent=2), encoding="utf-8")
    tp, fp, fn = (sum(row[key] for row in records) for key in ("tp", "fp", "fn"))
    report = {"dataset": manifest["dataset"], "source": manifest["source"], "license": manifest["license"],
              "selection": manifest["selection"], "model_overlap": manifest["model_overlap"],
              "parameters": Recipe().model_dump(), "scope": "nuclear segmentation only; no NCL/GFP claims",
              "fields": records, "micro": {"tp": tp, "fp": fp, "fn": fn, "f1": 2 * tp / (2 * tp + fp + fn)},
              "mean_field_f1": float(np.mean([row["f1"] for row in records]))}
    (output / "report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--verify", action="store_true")
    parser.add_argument("--evaluate", type=Path)
    parser.add_argument("--fiji", default="")
    args = parser.parse_args()
    if args.download:
        acquire()
    if args.evaluate:
        print(json.dumps(evaluate(args.evaluate, args.fiji), indent=2))
    else:
        verify()
        print("Public CC0 fixture hashes verified")


if __name__ == "__main__":
    main()

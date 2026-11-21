"""NCL positive-area fraction on a public original image, against an independent pixel count (#257 NS-02).

The image is OpenCell's NCL field FID00034252 (CZ Biohub, CC BY-SA 4.0; Issue #257 F-6), read from its public
distribution and checked against the SHA-256 below. It is used here only to check the calculation and is not
redistributed or added to the product or the demo.

- Nuclear mask: Otsu's threshold of the Hoechst channel, holes filled, connected components of at least 200 px. The
  mask's only role is to be the same for both calculations; it is not a segmentation result.
- region-features/1.0.0 (`field_features`, the implementation statistics use) gives each nucleus's NCL positive-area
  fraction at Otsu's threshold of the field's nuclear NCL pixels (256 bins), and the threshold it used.
- Independently, numpy counts each nucleus's pixels at or above that recorded threshold over its pixels, and Otsu's
  threshold is written out in numpy from the same definition (not scikit-image) and compared with the recorded one.

    uv run python scripts/check_ncl_area_public.py --cache <directory outside the checkout>
"""
from __future__ import annotations

import argparse
import hashlib
import json
import urllib.request
from pathlib import Path

import numpy as np
import tifffile
from cytellect_analysis.region_features import field_features
from scipy import ndimage
from skimage.filters import threshold_otsu  # the mask only

URL = ("https://czb-opencell.s3.amazonaws.com/microscopy/raw/NCL_ENSG00000115053/"
       "OC-FOV_NCL_ENSG00000115053_CID001030_FID00034252_proj.tif")
SHA256 = "ea42b700280c2afd4da8ce1a6fe862c0a7600806e90afccb98557d9c8e4bf213"
HOECHST, NCL = 0, 1
MINIMUM_NUCLEUS_PX = 200


def _image(cache: Path) -> np.ndarray:
    path = cache / "opencell-ncl-FID00034252-proj.tif"
    if not path.is_file():
        cache.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(URL, timeout=120) as response:  # noqa: S310 - fixed public https URL
            path.write_bytes(response.read())
    if hashlib.sha256(path.read_bytes()).hexdigest() != SHA256:
        raise SystemExit("The downloaded image does not match the recorded SHA-256")
    return tifffile.imread(path)


def _nuclei(hoechst: np.ndarray) -> np.ndarray:
    foreground = ndimage.binary_fill_holes(hoechst > threshold_otsu(hoechst))
    labels, count = ndimage.label(foreground)
    sizes = ndimage.sum(np.ones_like(labels), labels, range(1, count + 1))
    keep = {index + 1 for index, size in enumerate(sizes) if size >= MINIMUM_NUCLEUS_PX}
    labels[~np.isin(labels, sorted(keep))] = 0
    relabelled, _ = ndimage.label(labels > 0)
    return relabelled.astype(np.uint32)


def _otsu(values: np.ndarray) -> float:
    """Otsu's threshold written out in numpy: 256 equal-width bins between the minimum and maximum, the cut that
    maximises the between-class variance, reported as that bin's centre (the definition in docs/methods.md)."""
    values = values.astype(np.float64)
    counts, edges = np.histogram(values, bins=256, range=(values.min(), values.max()))
    centres = (edges[:-1] + edges[1:]) / 2
    weight_low, weight_high = np.cumsum(counts), np.cumsum(counts[::-1])[::-1]
    mean_low = np.cumsum(counts * centres) / np.maximum(weight_low, 1)
    mean_high = (np.cumsum((counts * centres)[::-1]) / np.maximum(weight_high[::-1], 1))[::-1]
    between = weight_low[:-1] * weight_high[1:] * (mean_low[:-1] - mean_high[1:]) ** 2
    return float(centres[int(np.argmax(between))])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, required=True)
    args = parser.parse_args()
    image = _image(args.cache)
    nuclei = _nuclei(image[HOECHST])
    ncl = image[NCL]
    record = field_features(nuclei, "positive_area_fraction", image=ncl)
    threshold = record["threshold"]["value"]
    independent = _otsu(ncl[nuclei > 0])
    ids = [int(value) for value in np.unique(nuclei) if value]
    counts = ndimage.sum(np.ones_like(nuclei), nuclei, ids)
    positive = ndimage.sum(ncl >= threshold, nuclei, ids)
    differences = [abs(record["values"][rid]["value"] - hit / count)
                   for rid, count, hit in zip(ids, counts, positive, strict=True)]
    fractions = [record["values"][rid]["value"] for rid in ids]
    summary = {"image_sha256": SHA256, "nuclei": len(ids), "threshold": threshold,
               "independent_otsu": independent,
               "threshold_relative_difference": abs(threshold - independent) / independent,
               "max_absolute_difference": max(differences),
               "fraction_range": [min(fractions), max(fractions)],
               "missing": sum(record["values"][rid]["value"] is None for rid in ids)}
    summary["passed"] = (bool(ids) and summary["threshold_relative_difference"] <= 1e-12 and summary["max_absolute_difference"] == 0
                         and summary["missing"] == 0)
    print(json.dumps(summary, indent=1))


if __name__ == "__main__":
    main()

"""Per-nucleolus shape and signal metrics on public real nucleolar images (genellect/cytellect#257, RP-01/RP-02).

Plan: genellect/cytellect#259, docs/drafts/nucleolar-measurement/implementation.md section 5 and decision 4.
Report: docs/public-nucleolar-shape-validation.md. Nothing here changes the product, its metrics or its screens.

Materials (fixtures/public/nucleolar-shape/manifest.json). Originals are downloaded into a directory outside the
checkout and checked against the recorded size, MD5 and SHA-256 before every use. They are never committed.

- Schmidt et al. DS6b (Zenodo 6643490, CC BY 4.0): every file. 30min and 2hrs are the tuning split, 4hrs the
  evaluation split.
- Schmidt et al. DS1 (Zenodo 6643187, CC BY 4.0): evaluation split. ``FIELDS_PER_GROUP`` files per cell line and
  condition, the ones with the smallest SHA-256 of ``SUBSET_SALT + file name``. The rule reads names only.
- DS6a (Zenodo 6643470) is not used: its fields are the public demo's.

Rules fixed on 2026-11-21, before any nucleolar value of these files was read (the constants below):

1. Detection is the product's current setting, unchanged and not tuned here. DS6b: nuclei by Fiji StarDist 2D
   (Versatile, percentiles 1-99.8, probability 0.5, NMS 0.3, automatic detection scale nuclear-size/1.0.0) on the
   DAPI-filter channel; nucleoli by the marker definition (cytellect-nucleolar-v2 protocol 2.1.0 with the defaults the
   API builds when no pixel size is given) on NPM1-mTagRFP. DS1 has no nuclear stain, so the product's per-nucleus
   rule cannot run. Its nucleoli come from a parent-free substitute fixed here: the same detection copy as the marker
   rule (rolling ball and Gaussian with the product's radii), one Otsu threshold per field instead of the per-nucleus
   min-max fraction, and the same area and solidity filters. DS1 masks are therefore not product masks.
2. Shape values are region-shape/1.0.0 of genellect/cytellect#258 (scikit-image regionprops): solidity, axis ratio,
   eccentricity; no value for an object touching the image border or with a zero minor axis or perimeter. Signal
   values are nuclear-signal/1.0.0 applied to nucleoli: raw CV, CV after the product's automatic background (DS6b),
   and the positive-area fraction at the field's Otsu threshold of all nucleolar pixels.
3. An independent implementation (NumPy moments, SciPy convex hull and ndimage statistics, a separate Otsu) is
   compared with the #258 code on every object; agreement means a difference of at most ``AGREEMENT``.
4. Resolution error. ``mask``: the same outline sampled every second pixel (the #258 method, applied to nucleoli).
   ``image``: the field binned 2 x 2 (mean of four pixels, rounded to uint16), detected again with the same rule and
   matched one to one at IoU >= ``MATCH_IOU``. DS6b goes from 0.325 to 0.65 um/px, DS1 from 0.1625 to 0.325 um/px
   (the DS6b resolution; DS6b itself was acquired with 2 x 2 camera binning). Errors are |delta solidity|,
   |delta axis ratio| / axis ratio and |delta eccentricity| against the finer grid, binned by the coarse area.
5. Minimum area per metric and method, chosen on the tuning split only: the smallest bin edge whose bin and every
   larger evaluable bin (at least ``MIN_BIN_OBJECTS`` objects) have a 90th percentile within ``TOLERANCE``. The
   metric's minimum is the larger of the two methods. It is a pixel count at the resolution of measurement.
6. Held-out check on the evaluation split (DS6b 4hrs and DS1), both methods: every evaluable bin at or above the
   minimum is within tolerance, and at least one such bin exists.
7. Decision 4: a per-nucleolus shape metric is shown for nucleoli only if the held-out check passes and, on the
   evaluation split at the native resolution, every condition has a measurable rate >= ``RATE_MINIMUM`` and the
   rates of the conditions compared with each other differ by at most ``RATE_SPREAD`` (comparison sets: DS6b 4hrs;
   DS1 HCT116; DS1 U2OS). The denominator is every detected nucleolus of the condition.
8. Also reported, without a pass rule (the plan sets none): area distributions, measurable rates at every candidate
   minimum, the change of each condition's difference from its control before and after the minimum-area exclusion,
   signal-metric measurability and resolution dependence, and agreement of the DS1 substitute with the product rule
   on DS6b. Agreement in direction with the paper is not a pass criterion.

Every field that fails is listed with its reason and is never dropped silently.

    uv run python scripts/validate_nucleolar_shape_public.py register --data-dir DIR
    uv run python scripts/validate_nucleolar_shape_public.py run --data-dir DIR --work DIR --fiji FIJI [--workers 3]
    uv run python scripts/validate_nucleolar_shape_public.py summarize --work DIR
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import multiprocessing
import re
import shutil
import sys
import time
import traceback
import urllib.request
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/nucleolar-shape/manifest.json"
SUMMARY = ROOT / "fixtures/public/nucleolar-shape/summary.json"
PROTOCOL = "nucleolar-shape-validation/1.0.0"
ZENODO_RECORD = "https://zenodo.org/api/records/{record}"

FIELDS_PER_GROUP = 15
SUBSET_SALT = "cytellect-nucleolar-shape-validation/1:"
SHAPE_METRICS = ("solidity", "axis_ratio", "eccentricity")
TOLERANCE = {"solidity": 0.05, "axis_ratio": 0.10, "eccentricity": 0.05}  # axis ratio: relative to the finer grid
QUANTILE = 0.90
BIN_EDGES = (1, 4, 8, 12, 16, 24, 32, 48, 64, 96, 128, 192, 256)
MIN_BIN_OBJECTS = 20
MATCH_IOU = 0.5
RATE_MINIMUM = 0.80
RATE_SPREAD = 0.10
PR258_MINIMUM_AREA_PX = 96
AGREEMENT = 1e-9
METHODS = ("mask", "image")
CONTROL = {"ds6b": "UntreatedWithEU", "ds1": "Untreated"}

DATASETS: dict[str, dict[str, Any]] = {
    "ds6b": {
        "record": 6643490,
        "name": "DS6b_5EU_TimeCourse_RawData (Schmidt, Rohatgi, Brandman 2022)",
        "source": "https://zenodo.org/records/6643490",
        "doi": "10.5281/zenodo.6643490",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "citation": "Schmidt HB et al. Oxaliplatin disrupts nucleolar function through biophysical disintegration. "
                    "Cell Reports 2022. doi:10.1016/j.celrep.2022.111629",
        "attribution": "Images: Schmidt HB, Rohatgi R, Brandman O (2022), DS6b_5EU_TimeCourse_RawData, Zenodo, "
                       "doi:10.5281/zenodo.6643490, CC BY 4.0. Originals are not redistributed; only aggregate "
                       "values derived from them are stored.",
        "scope": "U2OS FBL-sfGFP / NPM1-mTagRFP knock-in cells; 5-EU added during 30 min, 2 h or 4 h drug treatments "
                 "(paper Figure 5C-E), clicked to Alexa Fluor 647 azide, mounted in ProLong Glass NucBlue. Olympus "
                 "IX83, 40x/1.4 oil, ORCA-Fusion with 2 x 2 binning (OME DetectorSettings), single plane, uint16.",
        "shape": [4, 1152, 1152],
        "pixel_um": 0.325,
        "binning": "2x2",
        "channels": [
            {"index": 0, "ome_name": "DAPI", "emission_nm": 455, "id": "nuclear", "stain": "NucBlue (Hoechst 33342)",
             "role": "nuclear (StarDist)"},
            {"index": 1, "ome_name": "TRITC", "emission_nm": 580, "id": "npm1", "stain": "NPM1-mTagRFP",
             "role": "nucleolar marker (defines nucleoli; measured, circular)"},
            {"index": 2, "ome_name": "FITC", "emission_nm": 518, "id": "fbl", "stain": "FBL-sfGFP", "role": "measured"},
            {"index": 3, "ome_name": "Cy5", "emission_nm": 670, "id": "eu5", "stain": "5-EU (Alexa Fluor 647 azide)",
             "role": "measured"},
        ],
        "channel_basis": "Every registered file's embedded OME channel names and emission wavelengths (index 0 DAPI "
                         "455 nm, 1 TRITC 580 nm, 2 FITC 518 nm, 3 Cy5 670 nm) matched to the fluorophores the paper "
                         "gives for these cells and this experiment: FBL-sfGFP and NPM1-mTagRFP knock-ins, 5-EU "
                         "clicked to Alexa Fluor 647, NucBlue mounting medium (Methods, key resources table). This is "
                         "the filter-name mapping of the registered DS6a demo scenes (TRITC = NPM1, Cy5 = 5-EU, DAPI = "
                         "Hoechst); the order differs from DS6a and is read from each file's OME metadata, never "
                         "from the file name. Visual check (2026-11-21, one 4hrs UntreatedWithEU and one UntreatedNoEU "
                         "field): DAPI shows nuclei, TRITC nucleoli, Cy5 nucleolus-enriched signal only with 5-EU. "
                         "FITC also shows cytoplasmic signal of unknown origin. Provider confirmation is not claimed.",
        "split_rule": "Time point in the file name: 30min and 2hrs = tuning, 4hrs = evaluation (decision 4).",
        "subset_rule": "Every file of the record.",
        "group": "time point",
    },
    "ds1": {
        "record": 6643187,
        "name": "DS1_Morphometry_RawData (Schmidt, Rohatgi, Brandman 2022)",
        "source": "https://zenodo.org/records/6643187",
        "doi": "10.5281/zenodo.6643187",
        "license": "CC-BY-4.0",
        "license_url": "https://creativecommons.org/licenses/by/4.0/",
        "citation": "Schmidt HB et al. Oxaliplatin disrupts nucleolar function through biophysical disintegration. "
                    "Cell Reports 2022. doi:10.1016/j.celrep.2022.111629",
        "attribution": "Images: Schmidt HB, Rohatgi R, Brandman O (2022), DS1_Morphometry_RawData, Zenodo, "
                       "doi:10.5281/zenodo.6643187, CC BY 4.0. Originals are not redistributed; only aggregate "
                       "values derived from them are stored.",
        "scope": "HCT116 and U2OS FBL-sfGFP / NPM1-mTagRFP knock-in cells after 4 h treatments, fixed, imaged in the "
                 "FITC and TRITC channels (paper Figure 1C, Methods). Olympus IX83, 40x/1.4 oil, ORCA-Fusion "
                 "without binning, single plane, uint16 (14 significant bits). No nuclear stain. All files are "
                 "dated 2022-03-08; they are not counted as independent experiments.",
        "shape": [2, 2304, 2304],
        "pixel_um": 0.1625,
        "binning": "1x1",
        "channels": [
            {"index": 0, "ome_name": "TRITC", "emission_nm": 580, "id": "npm1", "stain": "NPM1-mTagRFP",
             "role": "nucleolar marker (defines nucleoli; measured, circular)"},
            {"index": 1, "ome_name": "FITC", "emission_nm": 518, "id": "fbl", "stain": "FBL-sfGFP", "role": "measured"},
        ],
        "channel_basis": "The paper does not label the channels of this record. Evidence: (1) every registered file's "
                         "embedded OME names and emission wavelengths, index 0 TRITC 580 nm and index 1 FITC 518 nm; "
                         "(2) the paper's cells carry exactly two fluorescent knock-ins, FBL-sfGFP and NPM1-mTagRFP, "
                         "and the morphometry was acquired 'in the FITC and TRITC channels' and measured 'using the "
                         "nucleolar marker NPM1' (Methods; Figure 1C legend); TRITC excites mTagRFP and FITC excites "
                         "sfGFP; (3) the same filter-name mapping as DS6a and DS6b (TRITC = NPM1); (4) visual check "
                         "(2026-11-21) of 40x_U2OS_Untreated_20220308_01_1101.tif: TRITC fills each nucleolus "
                         "(granular component), FITC forms beads inside nucleoli (dense fibrillar component). Adopted: "
                         "NPM1 = index 0, FBL = index 1. Provider confirmation is not claimed.",
        "split_rule": "Whole record = evaluation (decision 4).",
        "subset_rule": f"{FIELDS_PER_GROUP} files per cell line and condition: the smallest SHA-256 hex digests of "
                       f"the UTF-8 string '{SUBSET_SALT}' + file name. Fixed before download; reads names only.",
        "group": "cell line",
    },
}
NAME_PATTERN = {
    "ds6b": re.compile(r"^40x_NA1\.4_(30min|2hrs|4hrs)_([A-Za-z0-9]+)_(\d{8})_(\d+)_(\d+)\.tif$"),
    "ds1": re.compile(r"^40x_(HCT116|U2OS)_([A-Za-z0-9]+)_(\d{8})_(\d+)_(\d+)\.tif$"),
}


# --------------------------------------------------------------------------------------------------------------
# Registration
# --------------------------------------------------------------------------------------------------------------
def outside_checkout(path: Path) -> Path:
    path = Path(path).resolve()
    if path.is_relative_to(ROOT):
        raise ValueError("public_original_must_stay_outside_checkout")
    return path


def parse_name(dataset: str, name: str) -> dict[str, str]:
    match = NAME_PATTERN[dataset].match(name)
    if not match:
        raise ValueError(f"unexpected_file_name: {name}")
    if dataset == "ds6b":
        timepoint, condition = match.group(1), match.group(2)
        return {"group": timepoint, "condition": condition, "timepoint": timepoint,
                "split": "evaluation" if timepoint == "4hrs" else "tuning"}
    line, condition = match.group(1), match.group(2)
    return {"group": line, "condition": condition, "cell_line": line, "split": "evaluation"}


def subset_key(name: str) -> str:
    return hashlib.sha256((SUBSET_SALT + name).encode("utf-8")).hexdigest()


def select_files(dataset: str, names: list[str]) -> list[str]:
    if dataset == "ds6b":
        return sorted(names)
    groups: dict[tuple[str, str], list[str]] = defaultdict(list)
    for name in names:
        parsed = parse_name(dataset, name)
        groups[(parsed["cell_line"], parsed["condition"])].append(name)
    chosen = [name for key in sorted(groups) for name in sorted(groups[key], key=subset_key)[:FIELDS_PER_GROUP]]
    return sorted(chosen)


def ome_record(path: Path) -> dict[str, Any]:
    import tifffile

    with tifffile.TiffFile(path) as tif:
        if len(tif.series) != 1:
            raise ValueError("public_series_count")
        series = tif.series[0]
        xml = tif.ome_metadata or ""
        record: dict[str, Any] = {"axes": series.axes, "shape": list(series.shape), "dtype": str(series.dtype)}
    channels = []
    for attributes in re.findall(r"<OME:Channel ([^>]*)>", xml):
        values = dict(re.findall(r'(\w+)="([^"]*)"', attributes))
        channels.append({"name": values.get("Name"), "emission_nm": float(values.get("EmissionWavelength", "nan"))})
    found = re.search(r"<OME:Pixels ([^>]*)>", xml)
    pixels = dict(re.findall(r'(\w+)="([^"]*)"', found.group(1))) if found else {}
    acquired = re.search(r"<OME:AcquisitionDate>([^<]+)<", xml)
    record.update(channels=channels, pixel_x_um=float(pixels.get("PhysicalSizeX", "nan")),
                  pixel_y_um=float(pixels.get("PhysicalSizeY", "nan")),
                  binning=sorted(set(re.findall(r'Binning="([^"]+)"', xml))),
                  acquired=acquired.group(1) if acquired else None)
    return record


def check_ome(dataset: str, record: dict[str, Any]) -> None:
    spec = DATASETS[dataset]
    names = [channel["name"] for channel in record["channels"]]
    emissions = [channel["emission_nm"] for channel in record["channels"]]
    if (record["axes"] != "CYX" or record["shape"] != spec["shape"] or record["dtype"] != "uint16"
            or names != [channel["ome_name"] for channel in spec["channels"]]
            or emissions != [float(channel["emission_nm"]) for channel in spec["channels"]]
            or abs(record["pixel_x_um"] - spec["pixel_um"]) > 1e-9 or abs(record["pixel_y_um"] - spec["pixel_um"]) > 1e-9
            or record["binning"] != [spec["binning"]]):
        raise ValueError("public_ome_metadata_changed")


def download(url: str, target: Path, size: int, md5: str, attempts: int = 3) -> str:
    for attempt in range(attempts):
        if target.exists() and target.stat().st_size != size:
            print(f"incomplete earlier download removed: {target.name}", flush=True)
            target.unlink()
        if target.exists():
            break
        partial = target.with_name(target.name + ".part")
        with urllib.request.urlopen(url, timeout=300) as response, partial.open("wb") as stream:
            received = 0
            while block := response.read(1 << 20):
                received += len(block)
                if received > size:
                    raise ValueError("public_download_size_mismatch")
                stream.write(block)
        # A connection can end early without an error: a short file is never given the final name.
        if received == size:
            partial.rename(target)
        else:
            partial.unlink()
            print(f"incomplete download ({received} of {size} bytes), attempt {attempt + 1}: {target.name}", flush=True)
    data = target.read_bytes()
    if len(data) != size or hashlib.md5(data).hexdigest() != md5:
        raise ValueError(f"public_original_md5_mismatch: {target.name}")
    return hashlib.sha256(data).hexdigest()


def register(data_dir: Path) -> dict[str, Any]:
    data_dir = outside_checkout(data_dir)
    manifest: dict[str, Any] = {"schema": "cytellect-public-nucleolar-shape/1", "protocol": PROTOCOL,
                                "script": "scripts/validate_nucleolar_shape_public.py",
                                "originals": "Downloaded outside the checkout; never committed.",
                                "excluded": "DS6a (Zenodo 6643470): the public demo's fields; not used.",
                                "datasets": {}}
    for dataset, spec in DATASETS.items():
        with urllib.request.urlopen(ZENODO_RECORD.format(record=spec["record"]), timeout=120) as response:
            record = json.loads(response.read())
        files = {item["key"]: item for item in record["files"]}
        chosen = select_files(dataset, list(files))
        (data_dir / dataset).mkdir(parents=True, exist_ok=True)

        def fetch(name: str, dataset: str = dataset, files: dict = files) -> dict[str, Any]:
            item = files[name]
            algorithm, md5 = item["checksum"].split(":")
            if algorithm != "md5":
                raise ValueError("public_checksum_algorithm")
            target = data_dir / dataset / name
            sha256 = download(item["links"]["self"], target, int(item["size"]), md5)
            ome = ome_record(target)
            check_ome(dataset, ome)
            print(f"registered {dataset} {name}", flush=True)
            return {"name": name, "url": item["links"]["self"], "bytes": int(item["size"]), "md5": md5,
                    "sha256": sha256, **parse_name(dataset, name), "acquired": ome["acquired"]}

        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            entries = list(pool.map(fetch, chosen))
        metadata = record["metadata"]
        manifest["datasets"][dataset] = {
            **{key: value for key, value in spec.items() if key not in ("record",)},
            "record": spec["record"], "record_title": metadata.get("title"),
            "record_license_id": (metadata.get("license") or {}).get("id"),
            "record_publication_date": metadata.get("publication_date"),
            "record_files": len(files), "registered_files": len(entries),
            "control": CONTROL[dataset], "files": entries,
        }
        if manifest["datasets"][dataset]["record_license_id"] != "cc-by-4.0":
            raise ValueError("public_license_changed")
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------------------------------------------
# Product detection (unchanged settings) and the DS1 substitute
# --------------------------------------------------------------------------------------------------------------
def product_detectors() -> dict[str, dict[str, Any]]:
    """The detectors the API builds for the demo's settings (build_run_request, no proposal, no overrides)."""
    from cytellect_api.run_recipes import _nucleolar_defaults
    from cytellect_showcase.build import default_settings

    settings = default_settings()
    nuclear = {"engine": "fiji-stardist-2d", "model": "Versatile (fluorescent nuclei)", "percentile_low": 1,
               "percentile_high": 99.8, "probability": settings["nuclearProbability"], "nms": settings["nuclearNms"]}
    definition = {**settings["nucleolarDefinition"], "source": "marker", "marker": "npm1"}
    nucleolar = _nucleolar_defaults(definition)
    nucleolar["relative_threshold"] = definition["relative"]
    nucleolar["maximum_area_px"] = settings["nucleolarMaximumArea"]
    return {"nuclear": nuclear, "nucleolar": nucleolar}


def detect_nuclei_auto(image: np.ndarray, detector: dict, work: Path, fiji: str) -> tuple[np.ndarray, dict]:
    """AutoScaledNuclearRecipe in services/worker/src/cytellect_worker/regions.py."""
    from cytellect_analysis.engine import detect_nuclei
    from cytellect_analysis.nuclear_scale import automatic_detection_max_side, estimate_nuclear_diameter

    scale = estimate_nuclear_diameter(image)
    side = automatic_detection_max_side(image.shape, scale["diameter_px"])
    labels, _ = detect_nuclei(image, detector, work / "engine", fiji, scratch_root=work, detection_max_side=side)
    return labels, {"diameter_px": scale.get("diameter_px"), "detection_max_side_px": side}


def detect_nucleoli_product(nuclear: np.ndarray, marker: np.ndarray, nuclei: np.ndarray, detector: dict,
                            work: Path, fiji: str) -> tuple[np.ndarray, dict]:
    from cytellect_analysis.compartment_engine import detect_compartments

    masks, info = detect_compartments({"dapi": nuclear, "ncl": marker}, nuclei, detector, work / "compartments", fiji,
                                      scratch_root=work)
    states = Counter(str(value) for value in info["nucleolar_states"].values())
    return masks["nucleoli"], {"states": dict(sorted(states.items())), "nuclei": int(len(np.unique(nuclei)) - 1)}


def detect_nucleoli_parent_free(marker: np.ndarray, detector: dict) -> tuple[np.ndarray, dict]:
    """DS1 substitute: the marker rule's detection copy and filters with one Otsu threshold per field."""
    from scipy import ndimage as ndi
    from skimage.filters import threshold_otsu
    from skimage.measure import regionprops
    from skimage.restoration import rolling_ball

    raw = marker.astype(np.float64)
    detection = raw - rolling_ball(raw, radius=detector["background_radius_px"])
    detection = ndi.gaussian_filter(detection, detector["smoothing_sigma_px"], mode="nearest")
    if float(detection.max()) == float(detection.min()):
        return np.zeros(marker.shape, np.uint32), {"threshold": None, "components": 0}
    threshold = float(threshold_otsu(detection, nbins=256))
    labels, count = ndi.label(detection > threshold, structure=np.ones((3, 3), bool))
    out = np.zeros(marker.shape, np.uint32)
    kept = 0
    for region in regionprops(labels):
        if region.area < detector["minimum_area_px"] or region.solidity < detector["minimum_solidity"]:
            continue
        kept += 1
        rows, cols = region.coords[:, 0], region.coords[:, 1]
        out[rows, cols] = kept
    return out, {"threshold": threshold, "components": int(count), "kept": kept}


def bin2(plane: np.ndarray) -> np.ndarray:
    """2 x 2 mean of a uint16 plane, rounded half to even back to uint16 (scale-free for the detectors used)."""
    height, width = plane.shape
    if height % 2 or width % 2:
        raise ValueError("bin2_odd_shape")
    total = plane.astype(np.uint32).reshape(height // 2, 2, width // 2, 2).sum(axis=(1, 3))
    return np.rint(total / 4.0).astype(np.uint16)


def decimate2(labels: np.ndarray) -> np.ndarray:
    """Every second pixel from offset 1, as scripts/evaluate_shape_minimum_area.py of #258 with factor 2."""
    return np.ascontiguousarray(labels[1::2, 1::2])


# --------------------------------------------------------------------------------------------------------------
# Measurements: the #258 formulas and an independent implementation
# --------------------------------------------------------------------------------------------------------------
def border_ids(labels: np.ndarray) -> set[int]:
    edge = np.concatenate([labels[0, :], labels[-1, :], labels[:, 0], labels[:, -1]])
    return {int(value) for value in np.unique(edge) if value}


def shapes_pr258(labels: np.ndarray) -> dict[str, np.ndarray]:
    """region-shape/1.0.0 (#258 region_shape.region_shapes) for every label, minimum area 1."""
    from skimage.measure import regionprops

    touching = border_ids(labels)
    rows: dict[str, list] = defaultdict(list)
    for region in regionprops(labels.astype(np.int64)):
        rid, area = int(region.label), int(region.area)
        rows["id"].append(rid)
        rows["area"].append(area)
        rows["border"].append(rid in touching)
        values = (math.nan, math.nan, math.nan)
        degenerate = False
        if rid not in touching:
            perimeter = float(region.perimeter_crofton)
            major, minor = float(region.axis_major_length), float(region.axis_minor_length)
            if perimeter <= 0 or minor <= 0 or not math.isfinite(perimeter):
                degenerate = True
            else:
                values = (area / float(region.area_convex), major / minor, float(region.eccentricity))
        rows["degenerate"].append(degenerate)
        for metric, value in zip(SHAPE_METRICS, values, strict=True):
            rows[metric].append(value)
    return {"id": np.asarray(rows["id"], np.int64), "area": np.asarray(rows["area"], np.int64),
            "border": np.asarray(rows["border"], bool), "degenerate": np.asarray(rows["degenerate"], bool),
            **{metric: np.asarray(rows[metric], np.float64) for metric in SHAPE_METRICS}}


def shape_independent(coords: np.ndarray) -> tuple[float, float, float]:
    """Solidity, axis ratio and eccentricity from first principles (NaN when the minor axis is zero).

    Moments: population covariance of pixel centres, closed-form eigenvalues. Convex area: pixel centres inside or
    on the SciPy convex hull of the pixel edge midpoints (the definition regionprops documents), tested with the
    hull's half-plane equations.
    """
    from scipy.spatial import ConvexHull

    points = coords.astype(np.float64)
    centred = points - points.mean(axis=0)
    a = float(np.mean(centred[:, 0] ** 2))
    b = float(np.mean(centred[:, 0] * centred[:, 1]))
    c = float(np.mean(centred[:, 1] ** 2))
    half_trace, root = (a + c) / 2.0, math.sqrt(max(((a - c) / 2.0) ** 2 + b * b, 0.0))
    major, minor = half_trace + root, max(half_trace - root, 0.0)
    if minor <= 0 or major <= 0:
        return math.nan, math.nan, math.nan
    offsets = np.array([[-0.5, 0.0], [0.5, 0.0], [0.0, -0.5], [0.0, 0.5]])
    corners = np.unique((points[:, None, :] + offsets[None, :, :]).reshape(-1, 2), axis=0)
    hull = ConvexHull(corners)
    low, high = coords.min(axis=0), coords.max(axis=0)
    grid = np.stack(np.meshgrid(np.arange(low[0], high[0] + 1), np.arange(low[1], high[1] + 1), indexing="ij"),
                    axis=-1).reshape(-1, 2).astype(np.float64)
    inside = np.all(grid @ hull.equations[:, :2].T + hull.equations[:, 2] <= 1e-10, axis=1)
    return len(coords) / int(inside.sum()), math.sqrt(major / minor), math.sqrt(1.0 - minor / major)


def shapes_independent(labels: np.ndarray, ids: np.ndarray, skip: np.ndarray) -> dict[str, np.ndarray]:
    from scipy import ndimage as ndi

    slices = ndi.find_objects(labels.astype(np.int64))
    out = {metric: np.full(len(ids), math.nan) for metric in SHAPE_METRICS}
    for index, rid in enumerate(ids):
        if skip[index]:
            continue
        window = slices[rid - 1]
        rows, cols = np.nonzero(labels[window] == rid)
        coords = np.stack([rows + window[0].start, cols + window[1].start], axis=1)
        for metric, value in zip(SHAPE_METRICS, shape_independent(coords), strict=True):
            out[metric][index] = value
    return out


def otsu_pr258(values: np.ndarray) -> float | None:
    """nuclear-signal/1.0.0 field threshold: skimage threshold_otsu on float values, 256 bins."""
    if values.size < 2 or float(values.min()) == float(values.max()):
        return None
    from skimage.filters import threshold_otsu

    return float(threshold_otsu(values.astype(np.float64), nbins=256))


def otsu_independent(values: np.ndarray) -> float | None:
    """Otsu's rule written out: 256 equal bins over [min, max], first split with the largest between-class variance."""
    values = values.astype(np.float64)
    if values.size < 2 or float(values.min()) == float(values.max()):
        return None
    counts, edges = np.histogram(values, bins=256, range=(float(values.min()), float(values.max())))
    centres = (edges[:-1] + edges[1:]) / 2.0
    best, chosen = -1.0, 0
    for split in range(255):
        left, right = counts[:split + 1], counts[split + 1:]
        w0, w1 = float(left.sum()), float(right.sum())
        if not w0 or not w1:
            continue
        m0 = float((left * centres[:split + 1]).sum()) / w0
        m1 = float((right * centres[split + 1:]).sum()) / w1
        variance = w0 * w1 * (m0 - m1) ** 2
        if variance > best:
            best, chosen = variance, split
    return float(centres[chosen])


def signal_pr258(labels: np.ndarray, image: np.ndarray, ids: np.ndarray, background: float | None
                 ) -> dict[str, Any]:
    """nuclear-signal/1.0.0 on nucleoli: raw CV, corrected CV (when a background is given), positive-area fraction."""
    from scipy import ndimage as ndi

    pixels = image.astype(np.float64)
    threshold = otsu_pr258(pixels[labels > 0])
    slices = ndi.find_objects(labels.astype(np.int64))
    cv = np.full(len(ids), math.nan)
    corrected = np.full(len(ids), math.nan)
    positive = np.full(len(ids), math.nan)
    for index, rid in enumerate(ids):
        window = slices[rid - 1]
        inside = pixels[window][labels[window] == rid]
        mean, sd = float(inside.mean()), float(inside.std(ddof=0))
        if mean > 0:
            cv[index] = sd / mean
        if background is not None and mean - background > 0:
            corrected[index] = sd / (mean - background)
        if threshold is not None:
            positive[index] = int(np.count_nonzero(inside >= threshold)) / inside.size
    return {"cv": cv, "cv_corrected": corrected, "positive": positive, "threshold": threshold}


def signal_independent(labels: np.ndarray, image: np.ndarray, ids: np.ndarray) -> dict[str, Any]:
    from scipy import ndimage as ndi

    pixels = image.astype(np.float64)
    index = ids.tolist()
    mean = np.asarray(ndi.mean(pixels, labels, index), np.float64)
    variance = np.asarray(ndi.variance(pixels, labels, index), np.float64)
    cv = np.where(mean > 0, np.sqrt(np.maximum(variance, 0.0)) / np.where(mean > 0, mean, 1.0), math.nan)
    threshold = otsu_independent(pixels[labels > 0])
    positive = np.full(len(ids), math.nan)
    if threshold is not None:
        above = np.asarray(ndi.sum_labels((pixels >= threshold).astype(np.float64), labels, index))
        sizes = np.asarray(ndi.sum_labels(np.ones_like(pixels), labels, index))
        positive = above / sizes
    return {"cv": cv, "positive": positive, "threshold": threshold}


def automatic_background(image: np.ndarray, exclusion: np.ndarray) -> float | None:
    """The product's automatic background (region_measurement_v2): median of the candidate pixels, else None."""
    from cytellect_analysis import background_candidate

    mask, _ = background_candidate.automatic_background(image, exclusion)
    return None if mask is None else float(np.median(image[mask]))


def match(fine: np.ndarray, coarse: np.ndarray, factor: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """One-to-one pairs (fine id, coarse id, IoU) with IoU >= MATCH_IOU on the fine grid, greedy by IoU."""
    up = np.repeat(np.repeat(coarse, factor, axis=0), factor, axis=1) if factor > 1 else coarse
    if up.shape != fine.shape:
        raise ValueError("match_shape")
    both = (fine > 0) & (up > 0)
    if not both.any():
        return np.zeros(0, np.int64), np.zeros(0, np.int64), np.zeros(0)
    keys = fine[both].astype(np.uint64) << np.uint64(32) | up[both].astype(np.uint64)
    pairs, overlap = np.unique(keys, return_counts=True)
    fine_ids = (pairs >> np.uint64(32)).astype(np.int64)
    coarse_ids = (pairs & np.uint64(0xFFFFFFFF)).astype(np.int64)
    fine_area = np.bincount(fine.ravel().astype(np.int64))
    coarse_area = np.bincount(up.ravel().astype(np.int64))
    iou = overlap / (fine_area[fine_ids] + coarse_area[coarse_ids] - overlap)
    order = np.argsort(-iou, kind="stable")
    used_fine: set[int] = set()
    used_coarse: set[int] = set()
    chosen = []
    for index in order:
        if iou[index] < MATCH_IOU:
            break
        f, c = int(fine_ids[index]), int(coarse_ids[index])
        if f in used_fine or c in used_coarse:
            continue
        used_fine.add(f)
        used_coarse.add(c)
        chosen.append(index)
    chosen_array = np.asarray(chosen, np.int64)
    return fine_ids[chosen_array], coarse_ids[chosen_array], iou[chosen_array]


# --------------------------------------------------------------------------------------------------------------
# One field
# --------------------------------------------------------------------------------------------------------------
def measure(labels: np.ndarray, planes: dict[str, np.ndarray], backgrounds: dict[str, float | None] | None,
            prefix: str, independent: bool) -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    shape = shapes_pr258(labels)
    arrays = {f"{prefix}{key}": value for key, value in shape.items()}
    info: dict[str, Any] = {"thresholds": {}, "independent_thresholds": {}}
    skip = shape["border"] | shape["degenerate"]
    if independent:
        for metric, value in shapes_independent(labels, shape["id"], skip).items():
            arrays[f"{prefix}ind_{metric}"] = value
    for channel, plane in planes.items():
        background = (backgrounds or {}).get(channel)
        signal = signal_pr258(labels, plane, shape["id"], background)
        arrays[f"{prefix}cv_{channel}"] = signal["cv"]
        arrays[f"{prefix}pos_{channel}"] = signal["positive"]
        if backgrounds is not None:
            arrays[f"{prefix}cvc_{channel}"] = signal["cv_corrected"]
        info["thresholds"][channel] = signal["threshold"]
        if independent:
            other = signal_independent(labels, plane, shape["id"])
            arrays[f"{prefix}ind_cv_{channel}"] = other["cv"]
            arrays[f"{prefix}ind_pos_{channel}"] = other["positive"]
            info["independent_thresholds"][channel] = other["threshold"]
    return arrays, info


def resolution_pairs(native: np.ndarray, coarse: np.ndarray, native_ids: np.ndarray, method: str
                     ) -> dict[str, np.ndarray]:
    """For each native object: the coarse id (0 when none) and, for ``image``, the IoU."""
    from scipy import ndimage as ndi

    partner = np.zeros(len(native_ids), np.int64)
    iou = np.full(len(native_ids), math.nan)
    position = {int(rid): index for index, rid in enumerate(native_ids)}
    if method == "mask":
        # A sampled object split into pieces is not one object any more (#258: scipy label, 4-connectivity).
        for rid, window in enumerate(ndi.find_objects(coarse.astype(np.int64)), start=1):
            if window is not None and rid in position and ndi.label(coarse[window] == rid)[1] == 1:
                partner[position[rid]] = rid
    else:
        fine_ids, coarse_ids, values = match(native, coarse, 2)
        for f, c, value in zip(fine_ids, coarse_ids, values, strict=True):
            partner[position[int(f)]] = int(c)
            iou[position[int(f)]] = float(value)
    return {"partner": partner, "iou": iou}


def align(coarse_arrays: dict[str, np.ndarray], prefix: str, partner: np.ndarray) -> dict[str, np.ndarray]:
    """Coarse values re-indexed to the native objects (NaN / 0 / True when there is no partner)."""
    ids = coarse_arrays[f"{prefix}id"]
    lookup = {int(rid): index for index, rid in enumerate(ids)}
    rows = np.array([lookup.get(int(value), -1) for value in partner], np.int64)
    present = rows >= 0
    out: dict[str, np.ndarray] = {}
    for key, value in coarse_arrays.items():
        if key == f"{prefix}id":
            continue
        if value.dtype == bool:
            filled = np.ones(len(rows), bool)
        elif np.issubdtype(value.dtype, np.integer):
            filled = np.zeros(len(rows), value.dtype)
        else:
            filled = np.full(len(rows), math.nan)
        filled[present] = value[rows[present]]
        out[key] = filled
    return out


def process_field(task: dict[str, Any]) -> dict[str, Any]:
    import tifffile

    dataset, entry = task["dataset"], task["entry"]
    work, fiji = Path(task["work"]), task["fiji"]
    stem = entry["name"].removesuffix(".tif")
    target = work / "fields" / dataset
    target.mkdir(parents=True, exist_ok=True)
    result_path, arrays_path = target / f"{stem}.json", target / f"{stem}.npz"
    if result_path.is_file():
        previous = json.loads(result_path.read_text(encoding="utf-8"))
        if (previous.get("protocol") == PROTOCOL and previous.get("sha256") == entry["sha256"]
                and previous.get("status") == "ok" and arrays_path.is_file()):
            return previous
    info: dict[str, Any] = {"protocol": PROTOCOL, "dataset": dataset, "name": entry["name"],
                            "sha256": entry["sha256"], "split": entry["split"], "group": entry["group"],
                            "condition": entry["condition"], "status": "failed", "stage": "verify"}
    scratch = work / "tmp" / stem
    started = time.perf_counter()
    try:
        path = Path(task["data_dir"]) / dataset / entry["name"]
        data = path.read_bytes()
        if len(data) != entry["bytes"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            raise ValueError("public_original_hash_mismatch")
        del data
        check_ome(dataset, ome_record(path))
        stack = tifffile.imread(path)
        spec = DATASETS[dataset]
        planes = {channel["id"]: np.ascontiguousarray(stack[channel["index"]]) for channel in spec["channels"]}
        binned = {key: bin2(value) for key, value in planes.items()}
        detectors = task["detectors"]
        measured = [key for key in planes if key != "nuclear"]
        arrays: dict[str, np.ndarray] = {}
        if dataset == "ds6b":
            info["stage"] = "nuclei"
            nuclei, scale = detect_nuclei_auto(planes["nuclear"], detectors["nuclear"], scratch / "n1", fiji)
            info["stage"] = "nucleoli"
            nucleoli, states = detect_nucleoli_product(planes["nuclear"], planes["npm1"], nuclei,
                                                       detectors["nucleolar"], scratch / "n1", fiji)
            info["stage"] = "nuclei-binned"
            nuclei2, scale2 = detect_nuclei_auto(binned["nuclear"], detectors["nuclear"], scratch / "n2", fiji)
            info["stage"] = "nucleoli-binned"
            coarse, states2 = detect_nucleoli_product(binned["nuclear"], binned["npm1"], nuclei2,
                                                      detectors["nucleolar"], scratch / "n2", fiji)
            info.update(native={"pixel_um": spec["pixel_um"], **scale, **states},
                        binned={"pixel_um": 2 * spec["pixel_um"], **scale2, **states2})
            exclusion = (nucleoli > 0) | (nuclei > 0)
            backgrounds = {key: automatic_background(planes[key], exclusion) for key in measured}
            exclusion2 = (coarse > 0) | (nuclei2 > 0)
            backgrounds2 = {key: automatic_background(binned[key], exclusion2) for key in measured}
            info["native"]["backgrounds"], info["binned"]["backgrounds"] = backgrounds, backgrounds2
            # Channel identity check (not a metric): 5-EU channel median inside nuclei.
            info["native"]["eu5_nuclear_median"] = float(np.median(planes["eu5"][nuclei > 0])) if nuclei.any() else None
            info["stage"] = "substitute"
            substitute, substitute_info = detect_nucleoli_parent_free(planes["npm1"], detectors["nucleolar"])
            product_ids, substitute_ids, _ = match(nucleoli, substitute, 1)
            sub_ids = [int(value) for value in np.unique(substitute) if value]
            inside = {int(value) for value in np.unique(substitute[nuclei > 0]) if value}
            info["substitute"] = {**substitute_info, "objects": len(sub_ids), "matched": int(len(product_ids)),
                                  "objects_touching_nuclei": len(inside)}
            arrays["n_parent"] = np.zeros(0, np.int64)  # filled below
        else:
            backgrounds, backgrounds2 = None, None
            info["stage"] = "nucleoli"
            nucleoli, threshold = detect_nucleoli_parent_free(planes["npm1"], detectors["nucleolar"])
            info["stage"] = "nucleoli-binned"
            coarse, threshold2 = detect_nucleoli_parent_free(binned["npm1"], detectors["nucleolar"])
            info.update(native={"pixel_um": spec["pixel_um"], **threshold},
                        binned={"pixel_um": 2 * spec["pixel_um"], **threshold2})
        info["stage"] = "measure"
        signal_planes = {key: planes[key] for key in measured}
        signal_binned = {key: binned[key] for key in measured}
        native_arrays, native_info = measure(nucleoli, signal_planes, backgrounds, "n_", independent=True)
        arrays.update(native_arrays)
        if dataset == "ds6b":
            from scipy import ndimage as ndi

            slices = ndi.find_objects(nucleoli.astype(np.int64))
            arrays["n_parent"] = np.asarray([int(nuclei[slices[rid - 1]][nucleoli[slices[rid - 1]] == rid][0])
                                             for rid in native_arrays["n_id"]], np.int64)
            matched = set(int(value) for value in product_ids)
            arrays["n_substitute_match"] = np.asarray([int(rid) in matched for rid in native_arrays["n_id"]], bool)
        info["native"].update(objects=int(len(native_arrays["n_id"])), **native_info)
        coarse_arrays, coarse_info = measure(coarse, signal_binned, backgrounds2, "c_", independent=False)
        arrays.update(coarse_arrays)
        info["binned"].update(objects=int(len(coarse_arrays["c_id"])), **coarse_info)
        pairs = resolution_pairs(nucleoli, coarse, native_arrays["n_id"], "image")
        arrays["image_partner"], arrays["image_iou"] = pairs["partner"], pairs["iou"]
        arrays.update({f"image_{key[2:]}": value for key, value in align(coarse_arrays, "c_", pairs["partner"]).items()})
        decimated = decimate2(nucleoli)
        mask_arrays, _ = measure(decimated, signal_binned, None, "m_", independent=False)
        pairs = resolution_pairs(nucleoli, decimated, native_arrays["n_id"], "mask")
        arrays["mask_partner"] = pairs["partner"]
        arrays.update({f"mask_{key[2:]}": value for key, value in align(mask_arrays, "m_", pairs["partner"]).items()})
        np.savez_compressed(arrays_path, **arrays)
        info.update(status="ok", stage="done", seconds=round(time.perf_counter() - started, 1))
    except Exception as error:  # noqa: BLE001 - every failure is recorded with its reason
        info.update(error=f"{type(error).__name__}: {error}", traceback=traceback.format_exc(limit=4)[-1500:])
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    result_path.write_text(json.dumps(info, indent=1, default=float) + "\n", encoding="utf-8")
    return info


def run(data_dir: Path, work: Path, fiji: str, workers: int, datasets: list[str]) -> None:
    data_dir, work = outside_checkout(data_dir), outside_checkout(work)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    detectors = product_detectors()
    (work / "detectors.json").parent.mkdir(parents=True, exist_ok=True)
    (work / "detectors.json").write_text(json.dumps(detectors, indent=1) + "\n", encoding="utf-8")
    tasks = [{"dataset": dataset, "entry": entry, "work": str(work), "fiji": fiji, "data_dir": str(data_dir),
              "detectors": detectors}
             for dataset in datasets for entry in manifest["datasets"][dataset]["files"]]
    context = multiprocessing.get_context("spawn")
    done = 0
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers, mp_context=context) as pool:
        for info in pool.map(process_field, tasks):
            done += 1
            print(f"[{done}/{len(tasks)}] {info['dataset']} {info['name']} {info['status']}"
                  + (f" {info.get('error')}" if info["status"] != "ok" else ""), flush=True)


# --------------------------------------------------------------------------------------------------------------
# Summary
# --------------------------------------------------------------------------------------------------------------
def quantiles(values: np.ndarray, points=(10, 25, 50, 75, 90)) -> dict[str, float | None]:
    values = values[np.isfinite(values)]
    return {f"p{point}": (float(np.percentile(values, point)) if values.size else None) for point in points}


def bin_of(area: np.ndarray) -> np.ndarray:
    return np.searchsorted(np.asarray(BIN_EDGES), area, side="right") - 1


def error_rows(records: dict[str, np.ndarray]) -> list[dict[str, Any]]:
    """Per coarse-area bin: objects and the 90th percentile of each metric's error."""
    bins = bin_of(records["area"])
    rows = []
    for index, low in enumerate(BIN_EDGES):
        inside = bins == index
        high = BIN_EDGES[index + 1] if index + 1 < len(BIN_EDGES) else None
        row: dict[str, Any] = {"area_from_px": low, "area_below_px": high, "objects": int(inside.sum()),
                               "evaluable": bool(inside.sum() >= MIN_BIN_OBJECTS)}
        for metric in SHAPE_METRICS:
            value = float(np.quantile(records[metric][inside], QUANTILE)) if inside.any() else None
            row[f"{metric}_p{int(QUANTILE * 100)}"] = value
            row[f"{metric}_within"] = value is not None and value <= TOLERANCE[metric]
        rows.append(row)
    return rows


def minimum_area(rows: list[dict[str, Any]], metric: str) -> int | None:
    """Smallest bin edge whose bin is evaluable and within tolerance, as is every larger evaluable bin."""
    key = f"{metric}_within"
    for index, row in enumerate(rows):
        if not (row["evaluable"] and row[key]):
            continue
        if all(later[key] for later in rows[index:] if later["evaluable"]):
            return int(row["area_from_px"])
    return None


def held_out(rows: list[dict[str, Any]], metric: str, minimum: int | None) -> dict[str, Any]:
    if minimum is None:
        return {"checked_bins": 0, "passed": False, "reason": "minimum_area_undetermined"}
    checked = [row for row in rows if row["evaluable"] and row["area_from_px"] >= minimum]
    failing = [row["area_from_px"] for row in checked if not row[f"{metric}_within"]]
    if not checked:
        return {"checked_bins": 0, "passed": False, "reason": "no_evaluable_bin_at_or_above_minimum"}
    return {"checked_bins": len(checked), "failing_bins_from_px": failing, "passed": not failing,
            "reason": None if not failing else "tolerance_exceeded"}


def decide(rates: dict[str, list[float]], held_out_passed: bool, minimum: int | None) -> dict[str, Any]:
    """Decision 4 from the measurable rates of each evaluation comparison set (condition rates in [0, 1])."""
    sets = {}
    for name, values in rates.items():
        low, high = (min(values), max(values)) if values else (None, None)
        sets[name] = {"minimum_rate": low, "maximum_rate": high,
                      "spread": None if low is None or high is None else high - low,
                      "all_at_least_minimum": bool(values) and low is not None and low >= RATE_MINIMUM,
                      "spread_within": bool(values) and high is not None and low is not None
                      and high - low <= RATE_SPREAD + 1e-12}
    passed = (minimum is not None and held_out_passed and bool(sets)
              and all(item["all_at_least_minimum"] and item["spread_within"] for item in sets.values()))
    return {"minimum_area_px": minimum, "held_out_shape_error_passed": held_out_passed, "sets": sets,
            "show_for_nucleoli": passed}


class Fields:
    """Per-field results of a work directory, grouped."""

    def __init__(self, work: Path, manifest: dict[str, Any]):
        self.infos: list[dict[str, Any]] = []
        self.arrays: dict[str, dict[str, np.ndarray]] = {}
        for dataset, spec in manifest["datasets"].items():
            for entry in spec["files"]:
                stem = entry["name"].removesuffix(".tif")
                path = work / "fields" / dataset / f"{stem}.json"
                if not path.is_file():
                    self.infos.append({"dataset": dataset, "name": entry["name"], "split": entry["split"],
                                       "group": entry["group"], "condition": entry["condition"],
                                       "status": "not_run", "sha256": entry["sha256"]})
                    continue
                info = json.loads(path.read_text(encoding="utf-8"))
                if info.get("sha256") != entry["sha256"] or info.get("protocol") != PROTOCOL:
                    info = {**info, "status": "stale"}
                self.infos.append(info)
                if info["status"] == "ok":
                    with np.load(path.with_suffix(".npz")) as data:
                        self.arrays[entry["name"]] = {key: data[key] for key in data.files}

    def ok(self, dataset: str, split: str | None = None) -> list[dict[str, Any]]:
        return [info for info in self.infos if info["dataset"] == dataset and info["status"] == "ok"
                and (split is None or info["split"] == split)]

    def stack(self, infos: list[dict[str, Any]], keys: list[str]) -> dict[str, np.ndarray]:
        out = {}
        for key in keys:
            parts = [self.arrays[info["name"]][key] for info in infos if key in self.arrays[info["name"]]]
            out[key] = np.concatenate(parts) if parts else np.zeros(0)
        return out


def resolution_records(fields: Fields, infos: list[dict[str, Any]], method: str) -> dict[str, np.ndarray]:
    keys = ["n_area", "n_border", "n_degenerate", *(f"n_{m}" for m in SHAPE_METRICS), f"{method}_partner",
            f"{method}_area", f"{method}_border", f"{method}_degenerate", *(f"{method}_{m}" for m in SHAPE_METRICS)]
    data = fields.stack(infos, keys)
    valid = ((data["n_border"] == 0) & (data["n_degenerate"] == 0) & (data[f"{method}_partner"] > 0)
             & (data[f"{method}_border"] == 0) & (data[f"{method}_degenerate"] == 0))
    records = {"area": data[f"{method}_area"][valid]}
    for metric in SHAPE_METRICS:
        fine, coarse = data[f"n_{metric}"][valid], data[f"{method}_{metric}"][valid]
        records[metric] = np.abs(coarse - fine) / (fine if metric == "axis_ratio" else 1.0)
    return records


def coverage(fields: Fields, infos: list[dict[str, Any]], method: str) -> list[dict[str, Any]]:
    """Native objects off the border by their expected coarse area (native area / 4): share with a coarse partner."""
    data = fields.stack(infos, ["n_area", "n_border", f"{method}_partner"])
    keep = data["n_border"] == 0
    expected = data["n_area"][keep] / 4.0
    partner = data[f"{method}_partner"][keep] > 0
    bins = bin_of(np.maximum(expected, 1))
    return [{"expected_area_from_px": low, "objects": int((bins == index).sum()),
             "with_partner": int(partner[bins == index].sum())} for index, low in enumerate(BIN_EDGES)]


def measurable(area: np.ndarray, border: np.ndarray, degenerate: np.ndarray, minimum: int) -> np.ndarray:
    return (area >= minimum) & (border == 0) & (degenerate == 0)


def condition_table(fields: Fields, dataset: str, prefix: str, minima: dict[str, int | None]
                    ) -> list[dict[str, Any]]:
    """Per split, group and condition: area distribution and measurable rates."""
    pixel = DATASETS[dataset]["pixel_um"] * (2 if prefix == "c_" else 1)
    rows = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for info in fields.ok(dataset):
        groups[(info["split"], info["group"], info["condition"])].append(info)
    for (split, group, condition), infos in sorted(groups.items()):
        data = fields.stack(infos, [f"{prefix}area", f"{prefix}border", f"{prefix}degenerate"])
        area, border, degenerate = data[f"{prefix}area"], data[f"{prefix}border"], data[f"{prefix}degenerate"]
        total = int(area.size)
        row: dict[str, Any] = {"split": split, "group": group, "condition": condition, "fields": len(infos),
                               "failed_fields": sum(1 for info in fields.infos if info["dataset"] == dataset
                                                    and info["status"] != "ok" and info["split"] == split
                                                    and info["group"] == group and info["condition"] == condition),
                               "nucleoli": total, "border_fraction": float(border.mean()) if total else None,
                               "degenerate_fraction": float(degenerate.mean()) if total else None,
                               "area_px": quantiles(area.astype(float)),
                               "area_um2": quantiles(area.astype(float) * pixel * pixel),
                               "rate_by_minimum_px": {str(edge): (float(measurable(area, border, degenerate, edge).mean())
                                                                  if total else None) for edge in BIN_EDGES}}
        per_metric = {}
        for metric, minimum in {**minima, "pr258_96px": PR258_MINIMUM_AREA_PX}.items():
            if minimum is None:
                per_metric[metric] = None
                continue
            field_rates = []
            for info in infos:
                one = fields.arrays[info["name"]]
                if one[f"{prefix}area"].size:
                    field_rates.append(float(measurable(one[f"{prefix}area"], one[f"{prefix}border"],
                                                        one[f"{prefix}degenerate"], minimum).mean()))
            per_metric[metric] = {"minimum_area_px": minimum, "minimum_area_um2": minimum * pixel * pixel,
                                  "rate": float(measurable(area, border, degenerate, minimum).mean()) if total else None,
                                  "field_rate_min": min(field_rates) if field_rates else None,
                                  "field_rate_max": max(field_rates) if field_rates else None,
                                  "fields_without_nucleoli": len(infos) - len(field_rates)}
        row["rates_at_minimum"] = per_metric
        rows.append(row)
    return rows


def missingness(fields: Fields, dataset: str, metric: str, minimum: int) -> list[dict[str, Any]]:
    """Each condition minus its control (same split and group): median before and after the minimum-area rule."""
    pixel = DATASETS[dataset]["pixel_um"]
    groups: dict[tuple[str, str], dict[str, list[dict[str, Any]]]] = defaultdict(lambda: defaultdict(list))
    for info in fields.ok(dataset):
        groups[(info["split"], info["group"])][info["condition"]].append(info)
    rows = []
    for (split, group), conditions in sorted(groups.items()):
        control = conditions.get(CONTROL[dataset])
        if not control:
            continue

        def values(infos):
            data = fields.stack(infos, ["n_area", "n_border", "n_degenerate", f"n_{metric}"])
            usable = (data["n_border"] == 0) & (data["n_degenerate"] == 0) & np.isfinite(data[f"n_{metric}"])
            after = usable & (data["n_area"] >= minimum)
            return (data[f"n_{metric}"][usable], data[f"n_{metric}"][after],
                    data["n_area"][usable] * pixel * pixel, data["n_area"][after] * pixel * pixel)

        base = values(control)
        for condition, infos in sorted(conditions.items()):
            if condition == CONTROL[dataset]:
                continue
            other = values(infos)
            medians = [float(np.median(part)) if part.size else None for part in (*other, *base)]
            before = None if medians[0] is None or medians[4] is None else medians[0] - medians[4]
            after = None if medians[1] is None or medians[5] is None else medians[1] - medians[5]
            area_before = None if medians[2] is None or medians[6] is None else medians[2] - medians[6]
            area_after = None if medians[3] is None or medians[7] is None else medians[3] - medians[7]
            rows.append({"split": split, "group": group, "condition": condition, "control": CONTROL[dataset],
                         "minimum_area_px": minimum,
                         "n_before": [int(other[0].size), int(base[0].size)],
                         "n_after": [int(other[1].size), int(base[1].size)],
                         "median_before": [medians[0], medians[4]], "median_after": [medians[1], medians[5]],
                         "difference_before": before, "difference_after": after,
                         "difference_change": None if before is None or after is None else after - before,
                         "area_um2_difference_before": area_before, "area_um2_difference_after": area_after})
    return rows


def agreement(fields: Fields) -> dict[str, Any]:
    out: dict[str, Any] = {"tolerance": AGREEMENT}
    for dataset in DATASETS:
        infos = fields.ok(dataset)
        report: dict[str, Any] = {"objects": 0}
        if not infos:
            out[dataset] = report
            continue
        keys = list(fields.arrays[infos[0]["name"]])
        data = fields.stack(infos, keys)
        report["objects"] = int(data["n_id"].size)
        skip = (data["n_border"] > 0) | (data["n_degenerate"] > 0)
        for metric in SHAPE_METRICS:
            primary, other = data[f"n_{metric}"][~skip], data[f"n_ind_{metric}"][~skip]
            both = np.isfinite(primary) & np.isfinite(other)
            report[metric] = {"compared": int(both.sum()),
                              "missing_mismatch": int((np.isfinite(primary) != np.isfinite(other)).sum()),
                              "max_abs_difference": float(np.max(np.abs(primary[both] - other[both]))) if both.any() else None}
        for key in sorted(k for k in keys if k.startswith("n_cv_") or k.startswith("n_pos_")):
            other_key = key.replace("n_", "n_ind_", 1)
            primary, other = data[key], data[other_key]
            both = np.isfinite(primary) & np.isfinite(other)
            report[key[2:]] = {"compared": int(both.sum()),
                               "missing_mismatch": int((np.isfinite(primary) != np.isfinite(other)).sum()),
                               "max_abs_difference": float(np.max(np.abs(primary[both] - other[both]))) if both.any() else None}
        thresholds = [(info["native"]["thresholds"][channel], info["native"]["independent_thresholds"][channel])
                      for info in infos for channel in info["native"]["thresholds"]]
        report["otsu_threshold_mismatch"] = sum(1 for a, b in thresholds if a != b)
        report["otsu_thresholds_compared"] = len(thresholds)
        values = [item["max_abs_difference"] for item in report.values()
                  if isinstance(item, dict) and item.get("max_abs_difference") is not None]
        report["agrees"] = (all(value <= AGREEMENT for value in values) and report["otsu_threshold_mismatch"] == 0
                            and all(item.get("missing_mismatch", 0) == 0 for item in report.values() if isinstance(item, dict)))
        out[dataset] = report
    return out


def signal_summary(fields: Fields) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for dataset, spec in DATASETS.items():
        channels = [channel["id"] for channel in spec["channels"] if channel["id"] != "nuclear"]
        rows = []
        groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
        for info in fields.ok(dataset):
            groups[(info["split"], info["group"], info["condition"])].append(info)
        for (split, group, condition), infos in sorted(groups.items()):
            keys = ["n_area"] + [f"n_{kind}_{c}" for c in channels for kind in ("cv", "pos")]
            if dataset == "ds6b":
                keys += [f"n_cvc_{c}" for c in channels]
            data = fields.stack(infos, keys)
            total = int(data["n_area"].size)
            row: dict[str, Any] = {"split": split, "group": group, "condition": condition, "nucleoli": total}
            for key in keys[1:]:
                row[key[2:] + "_rate"] = float(np.isfinite(data[key]).mean()) if total else None
            if dataset == "ds6b":
                for c in channels:
                    row[f"background_not_established_fields_{c}"] = sum(
                        1 for info in infos if info["native"]["backgrounds"].get(c) is None)
            rows.append(row)
        resolution = {}
        for split in sorted({info["split"] for info in fields.ok(dataset)}):
            infos = fields.ok(dataset, split)
            for method in METHODS:
                for channel in channels:
                    keys = ["n_border", f"{method}_partner", f"{method}_area", f"{method}_border",
                            f"n_cv_{channel}", f"{method}_cv_{channel}", f"n_pos_{channel}", f"{method}_pos_{channel}"]
                    data = fields.stack(infos, keys)
                    valid = (data["n_border"] == 0) & (data[f"{method}_partner"] > 0) & (data[f"{method}_border"] == 0)
                    with np.errstate(divide="ignore", invalid="ignore"):
                        cv_change = (np.abs(data[f"{method}_cv_{channel}"] - data[f"n_cv_{channel}"])
                                     / data[f"n_cv_{channel}"])
                    pos_change = np.abs(data[f"{method}_pos_{channel}"] - data[f"n_pos_{channel}"])
                    bins = bin_of(data[f"{method}_area"])
                    table = []
                    for index, low in enumerate(BIN_EDGES):
                        inside = valid & (bins == index)
                        cv_in, pos_in = cv_change[inside], pos_change[inside]
                        cv_in, pos_in = cv_in[np.isfinite(cv_in)], pos_in[np.isfinite(pos_in)]
                        table.append({"area_from_px": low, "objects": int(inside.sum()),
                                      "cv_relative_change_p50": float(np.median(cv_in)) if cv_in.size else None,
                                      "cv_relative_change_p90": float(np.quantile(cv_in, QUANTILE)) if cv_in.size else None,
                                      "positive_fraction_change_p50": float(np.median(pos_in)) if pos_in.size else None,
                                      "positive_fraction_change_p90": float(np.quantile(pos_in, QUANTILE)) if pos_in.size else None})
                    resolution[f"{split}/{method}/{channel}"] = table
        out[dataset] = {"conditions": rows, "resolution": resolution}
    return out


def summarize(work: Path, output: Path) -> dict[str, Any]:
    work = outside_checkout(work)
    manifest_text = MANIFEST.read_text(encoding="utf-8")
    manifest = json.loads(manifest_text)
    fields = Fields(work, manifest)
    detectors = json.loads((work / "detectors.json").read_text(encoding="utf-8"))
    failures = [{key: info.get(key) for key in ("dataset", "name", "split", "condition", "status", "stage", "error")}
                for info in fields.infos if info["status"] != "ok"]
    cohorts = {"ds6b/tuning": ("ds6b", "tuning"), "ds6b/evaluation": ("ds6b", "evaluation"),
               "ds1/evaluation": ("ds1", "evaluation")}
    resolution: dict[str, Any] = {}
    for name, (dataset, split) in cohorts.items():
        infos = fields.ok(dataset, split)
        resolution[name] = {"fine_um_per_px": DATASETS[dataset]["pixel_um"],
                            "coarse_um_per_px": 2 * DATASETS[dataset]["pixel_um"], "fields": len(infos)}
        for method in METHODS:
            records = resolution_records(fields, infos, method)
            resolution[name][method] = {"pairs": int(records["area"].size), "bins": error_rows(records),
                                        "coverage": coverage(fields, infos, method)}
    minima: dict[str, Any] = {}
    for metric in SHAPE_METRICS:
        by_method = {method: minimum_area(resolution["ds6b/tuning"][method]["bins"], metric) for method in METHODS}
        chosen = None if any(value is None for value in by_method.values()) else max(by_method.values())
        checks = {f"{cohort}/{method}": held_out(resolution[cohort][method]["bins"], metric, chosen)
                  for cohort in ("ds6b/evaluation", "ds1/evaluation") for method in METHODS}
        minima[metric] = {"by_method": by_method, "minimum_area_px": chosen,
                          "minimum_area_um2": {dataset: (None if chosen is None else chosen * spec["pixel_um"] ** 2)
                                               for dataset, spec in DATASETS.items()},
                          "held_out": checks, "held_out_passed": all(item["passed"] for item in checks.values())}
    chosen_minima = {metric: minima[metric]["minimum_area_px"] for metric in SHAPE_METRICS}
    tables = {"ds6b": condition_table(fields, "ds6b", "n_", chosen_minima),
              "ds1": condition_table(fields, "ds1", "n_", chosen_minima),
              "ds1_binned": condition_table(fields, "ds1", "c_", chosen_minima)}
    decisions = {}
    for metric in SHAPE_METRICS:
        rates: dict[str, list[float]] = defaultdict(list)
        minimum = chosen_minima[metric]
        if minimum is not None:
            for dataset in ("ds6b", "ds1"):
                for row in tables[dataset]:
                    if row["split"] == "evaluation" and row["rates_at_minimum"][metric]["rate"] is not None:
                        rates[f"{dataset}/{row['group']}"].append(row["rates_at_minimum"][metric]["rate"])
        decisions[metric] = decide(dict(rates), minima[metric]["held_out_passed"], minimum)
    bias = {metric: {f"{dataset}@{minimum}": missingness(fields, dataset, metric, minimum)
                     for dataset in DATASETS
                     for minimum in sorted({value for value in (chosen_minima[metric], PR258_MINIMUM_AREA_PX)
                                            if value is not None})}
            for metric in SHAPE_METRICS}
    substitute = {}
    for split in ("tuning", "evaluation"):
        infos = fields.ok("ds6b", split)
        data = fields.stack(infos, ["n_substitute_match"])
        objects = sum(info["substitute"]["objects"] for info in infos)
        substitute[split] = {
            "product_nucleoli": int(data["n_substitute_match"].size),
            "product_matched_fraction": float(data["n_substitute_match"].mean()) if data["n_substitute_match"].size else None,
            "substitute_objects": objects,
            "substitute_matched_fraction": (sum(info["substitute"]["matched"] for info in infos) / objects) if objects else None,
            "substitute_touching_nuclei_fraction": (sum(info["substitute"]["objects_touching_nuclei"] for info in infos)
                                                    / objects) if objects else None}
    channel_check = defaultdict(list)
    for info in fields.ok("ds6b"):
        value = info["native"].get("eu5_nuclear_median")
        if value is not None:
            channel_check[f"{info['group']}/{info['condition']}"].append(value)
    nuclei = defaultdict(lambda: Counter())
    for info in fields.ok("ds6b"):
        nuclei[f"{info['split']}/{info['group']}/{info['condition']}"].update(
            {"nuclei": info["native"]["nuclei"], **{f"state_{key}": value for key, value in info["native"]["states"].items()}})
    summary = {
        "protocol": PROTOCOL, "manifest_sha256": hashlib.sha256(manifest_text.encode("utf-8")).hexdigest(),
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "rules": {"tolerance": TOLERANCE, "quantile": QUANTILE, "bin_edges_px": BIN_EDGES,
                  "min_bin_objects": MIN_BIN_OBJECTS, "match_iou": MATCH_IOU, "rate_minimum": RATE_MINIMUM,
                  "rate_spread": RATE_SPREAD, "agreement": AGREEMENT, "fields_per_group_ds1": FIELDS_PER_GROUP,
                  "controls": CONTROL},
        "detectors": detectors,
        "fields": {dataset: {"registered": len(spec["files"]),
                             "ok": len(fields.ok(dataset)),
                             "not_ok": sum(1 for info in fields.infos if info["dataset"] == dataset and info["status"] != "ok")}
                   for dataset, spec in manifest["datasets"].items()},
        "failures": failures,
        "nuclei_ds6b": {key: dict(value) for key, value in sorted(nuclei.items())},
        "channel_check_eu5_nuclear_median": {key: quantiles(np.asarray(values, float), (10, 50, 90))
                                             for key, values in sorted(channel_check.items())},
        "implementation_agreement": agreement(fields),
        "resolution": resolution, "minimum_area": minima, "conditions": tables, "decision4": decisions,
        "missingness": bias, "signal": signal_summary(fields), "ds1_substitute_on_ds6b": substitute,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("register", help="download, verify and write the manifest")
    one.add_argument("--data-dir", type=Path, required=True)
    two = commands.add_parser("run", help="detect and measure every registered field")
    two.add_argument("--data-dir", type=Path, required=True)
    two.add_argument("--work", type=Path, required=True)
    two.add_argument("--fiji", required=True)
    two.add_argument("--workers", type=int, default=1)
    two.add_argument("--dataset", action="append", choices=sorted(DATASETS))
    three = commands.add_parser("summarize", help="write the JSON summary")
    three.add_argument("--work", type=Path, required=True)
    three.add_argument("--output", type=Path, default=SUMMARY)
    args = parser.parse_args(argv)
    if args.command == "register":
        manifest = register(args.data_dir)
        print(json.dumps({dataset: spec["registered_files"] for dataset, spec in manifest["datasets"].items()}))
    elif args.command == "run":
        run(args.data_dir, args.work, args.fiji, args.workers, args.dataset or list(DATASETS))
    else:
        summary = summarize(args.work, args.output)
        print(json.dumps({"fields": summary["fields"],
                          "decision4": {metric: value["show_for_nucleoli"] for metric, value in summary["decision4"].items()}}))


if __name__ == "__main__":
    sys.exit(main())

"""Marker-contrast rule for nuclei without established nucleoli, on public real images (owner decision 20, #257).

Plan: docs/drafts/nucleolar-measurement/implementation.md (decision 20; the procedure of section 5). Product:
cytellect-nucleolar-v2 protocol 2.2.0 (packages/analysis/src/cytellect_analysis/nucleolar_detector_v2.py).
Report: docs/public-nucleolar-shape-validation.md, section "Nuclei without marker contrast (decision 20)".

Owner decisions (2026-11-21) this checks:

1. A nucleus whose nucleolar-marker contrast is below a noise-based criterion is ``indeterminate``; its candidates
   are not adopted and its nucleolar values are missing, never 0. The criterion is the parent signal / noise of
   cellpose-sam-ncl-parent/4.2.0, unchanged; only its minimum ``k`` is chosen here. No lower bound on marker
   enrichment and no area cut beyond (2).
2. Minimum area max(4 px, 0.3 um2) from the image calibration.
5. DS6a fields the public demo does not use may be used at 0.1625 um/px, split by a hash of the file name into tuning
   and evaluation before looking.

Rules fixed in the commit that adds this file, before any nucleolar value of the new protocol was computed:

R1. Material. DS6b (fixtures/public/nucleolar-shape/manifest.json): 30min and 2hrs = tuning, 4hrs = evaluation.
    DS6a (Zenodo 6643470): every file of the record except those any registered demo scene uses (the ``sources`` of
    services/showcase/datasets/zenodo-6643470*.json). The split is the parity of the first byte of
    SHA-256(``SPLIT_SALT`` + file name): even = tuning, odd = evaluation. Of each replicate x condition x split,
    the ``DS6A_PER_CELL`` files with the smallest such digest are used (disk). Names only; fixed before download.
R2. Detection. Nuclei: the product's StarDist recipe with the automatic scale (nuclear-size/1.1.0), cached once per
    field and shared by every nucleolar version. Nucleoli: ``BASELINE`` (the current 2.1.0 product default, pinned
    from the previous validation) and the product's 2.2.0 with the field's OME calibration.
R3. Comparison sets (conditions compared with each other): tuning = DS6b 30min, DS6b 2hrs, DS6a tuning;
    evaluation = DS6b 4hrs, DS6a evaluation.
R4. Acceptance, per comparison set, of the new version against the baseline on the same nuclei:
    A1 the indeterminate-nucleus rates of the conditions (indeterminate / all nuclei of the condition) differ by
       at most ``RATE_SPREAD`` (same form as decision 4);
    A2 in every condition, at most ``DIM_SHARE_MAX`` of the adopted objects are as bright as the nucleoplasm: raw
       marker mean of the object <= ``DIM_RATIO`` x raw marker mean of its parent's nucleoplasm (the parent's pixels
       outside every adopted object of the same version);
    A3 in every condition, the median over measured nuclei of the per-nucleus union mean (raw marker, pixel-weighted)
       and of the per-nucleus union area changes from the baseline by at most ``WIDTH`` (relative).
    Treatment effects (direction or size of a difference between conditions) are never acceptance criteria.
R5. Choice of k on the tuning sets only: the smallest k of ``K_GRID`` for which A1, A2 and A3 hold on every tuning
    set. If none does, k = ``PRECEDENT_K`` (the 4.2.0 value) and the tuning failure is reported. The product default
    (MINIMUM_CONTRAST_SNR) is then set to k in a commit before the evaluation runs once.
R6. Evaluation: once, with the committed product default. The command refuses to run if the default differs from
    the tuning record, if the rule or detector files have uncommitted changes, or if an evaluation record exists.
    Its commit SHA is recorded. A defect found afterwards is reported, not silently re-run.
R7. Reported without a pass rule: the separate effects of the contrast rule and of the physical minimum (DS6a),
    size breakdowns, per-nucleolus intensities, and every failed field with its reason. Detection correctness is
    not evaluated: there are no independent hand-drawn outlines (NS-03).

    uv run python -I scripts/validate_nucleolar_indeterminate_public.py register --data-dir DIR
    uv run python -I scripts/validate_nucleolar_indeterminate_public.py nuclei --data-dir DIR --work DIR --fiji FIJI
    uv run python -I scripts/validate_nucleolar_indeterminate_public.py tune --data-dir DIR --work DIR
    uv run python -I scripts/validate_nucleolar_indeterminate_public.py evaluate --data-dir DIR --work DIR
    uv run python -I scripts/validate_nucleolar_indeterminate_public.py summarize --work DIR
"""
from __future__ import annotations

import argparse
import concurrent.futures
import hashlib
import json
import math
import re
import shutil
import subprocess
import sys
import traceback
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_nucleolar_shape_public as shape  # noqa: E402  (shared registration and detection helpers)

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "fixtures/public/nucleolar-indeterminate/manifest.json"
SUMMARY = ROOT / "fixtures/public/nucleolar-indeterminate/summary.json"
SHAPE_MANIFEST = ROOT / "fixtures/public/nucleolar-shape/manifest.json"
DEMO_REGISTRATIONS = sorted((ROOT / "services/showcase/datasets").glob("zenodo-6643470*.json"))
PROTOCOL = "nucleolar-indeterminate-validation/1.0.0"
RULE_FILES = ("scripts/validate_nucleolar_indeterminate_public.py",
              "packages/analysis/src/cytellect_analysis/nucleolar_detector_v2.py")

SPLIT_SALT = "cytellect-nucleolar-indeterminate/1:"
DS6A_PER_CELL = 1  # 2 at first; reduced before any value was computed because the shared disk filled
K_GRID = (1.0, 1.5, 2.0, 3.0, 4.0, 5.0, 6.0, 8.0, 10.0)
PRECEDENT_K = 5.0
RATE_SPREAD = 0.10
DIM_RATIO = 1.10
DIM_SHARE_MAX = 0.05
WIDTH = 0.10
NO_GATE_K = 1e-9  # the product's 2.2.0 with a vanishing k: records every parent's contrast without gating
SIZE_EDGES_UM2 = (0.0, 0.3, 1.0, 3.0)  # size breakdown for the report: <0.3, 0.3-1, 1-3, >=3 um2
BASELINE: dict[str, Any] = {  # 2.1.0 as the product builds it without a pixel size (previous validation)
    "engine": "cytellect-nucleolar-v2", "protocol_version": "2.1.0", "source": "marker", "smoothing_sigma_px": 0.7,
    "rim_exclusion_px": 4, "relative_threshold": 0.7, "marker_fraction": 0.4, "background_radius_px": 10,
    "minimum_area_px": 4, "maximum_area_px": None, "minimum_solidity": 0.6}
NEW_BASE: dict[str, Any] = {**BASELINE, "protocol_version": "2.2.0", "minimum_area_um2": 0.3}
TUNING_SETS = ("ds6b-30min", "ds6b-2hrs", "ds6a-tuning")
EVALUATION_SETS = ("ds6b-4hrs", "ds6a-evaluation")

DS6A = {
    "record": 6643470,
    "name": "DS6a_5EU_Pulse_RawData (Schmidt, Rohatgi, Brandman 2022)",
    "source": "https://zenodo.org/records/6643470",
    "doi": "10.5281/zenodo.6643470",
    "license": "CC-BY-4.0",
    "license_url": "https://creativecommons.org/licenses/by/4.0/",
    "citation": "Schmidt HB et al. Oxaliplatin disrupts nucleolar function through biophysical disintegration. "
                "Cell Reports 2022. doi:10.1016/j.celrep.2022.111629",
    "attribution": "Images: Schmidt HB, Rohatgi R, Brandman O (2022), DS6a_5EU_Pulse_RawData, Zenodo, "
                   "doi:10.5281/zenodo.6643470, CC BY 4.0. Originals are not redistributed; only aggregate values "
                   "derived from them are stored.",
    "scope": "U2OS FBL-sfGFP / NPM1-mTagRFP knock-in cells, 5-EU pulse, Hoechst. Olympus IX83, 40x/1.4 oil, "
             "0.1625 um/px, single plane, uint16 (the registered demo scenes' description).",
    "pixel_um": 0.1625,
    "channels": {"nuclear": 3, "npm1": 1},
    "channel_basis": "The registered demo scenes (services/showcase/datasets/zenodo-6643470*.json): Hoechst = OME "
                     "channel 3 (filter DAPI), NPM1-mTagRFP = OME channel 1 (filter TRITC). Checked in each file's OME.",
}
DS6A_NAME = re.compile(r"^40x_1\.4_(Rep\d)_([A-Za-z0-9]+)_(\d{8})_(\d+)_(\d+)\.tif$")


# --------------------------------------------------------------------------------------------------------------
# Registration (R1)
# --------------------------------------------------------------------------------------------------------------
def split_digest(name: str) -> str:
    return hashlib.sha256((SPLIT_SALT + name).encode("utf-8")).hexdigest()


def split_of(name: str) -> str:
    return "tuning" if int(split_digest(name)[:2], 16) % 2 == 0 else "evaluation"


def demo_files() -> set[str]:
    used: set[str] = set()
    for path in DEMO_REGISTRATIONS:
        for source in json.loads(path.read_text(encoding="utf-8"))["sources"].values():
            used.add(source["filename"])
    return used


def choose_ds6a(names: list[str], excluded: set[str]) -> list[dict[str, str]]:
    cells: dict[tuple[str, str, str], list[str]] = defaultdict(list)
    for name in names:
        match = DS6A_NAME.match(name)
        if not match:
            raise ValueError(f"unexpected_file_name: {name}")
        if name in excluded:
            continue
        cells[(match.group(1), match.group(2), split_of(name))].append(name)
    chosen = []
    for (replicate, condition, split), members in sorted(cells.items()):
        for name in sorted(members, key=split_digest)[:DS6A_PER_CELL]:
            chosen.append({"name": name, "replicate": replicate, "condition": condition, "split": split,
                           "split_digest": split_digest(name)})
    return sorted(chosen, key=lambda item: item["name"])


def check_ds6a_ome(record: dict[str, Any]) -> None:
    names = [channel["name"] for channel in record["channels"]]
    if (record["axes"] != "CYX" or record["dtype"] != "uint16" or len(names) < 4
            or names[DS6A["channels"]["nuclear"]] != "DAPI" or names[DS6A["channels"]["npm1"]] != "TRITC"
            or abs(record["pixel_x_um"] - DS6A["pixel_um"]) > 1e-9 or abs(record["pixel_y_um"] - DS6A["pixel_um"]) > 1e-9):
        raise ValueError("public_ome_metadata_changed")


def register(data_dir: Path) -> dict[str, Any]:
    data_dir = shape.outside_checkout(data_dir)
    with urllib.request.urlopen(shape.ZENODO_RECORD.format(record=DS6A["record"]), timeout=120) as response:
        record = json.loads(response.read())
    if (record["metadata"].get("license") or {}).get("id") != "cc-by-4.0":
        raise ValueError("public_license_changed")
    files = {item["key"]: item for item in record["files"]}
    excluded = demo_files()
    if not excluded or not excluded <= set(files):
        raise ValueError("demo_registration_unexpected")
    chosen = choose_ds6a(list(files), excluded)
    (data_dir / "ds6a").mkdir(parents=True, exist_ok=True)

    def fetch(entry: dict[str, str]) -> dict[str, Any]:
        item = files[entry["name"]]
        algorithm, md5 = item["checksum"].split(":")
        if algorithm != "md5":
            raise ValueError("public_checksum_algorithm")
        target = data_dir / "ds6a" / entry["name"]
        sha256 = shape.download(item["links"]["self"], target, int(item["size"]), md5)
        ome = shape.ome_record(target)
        check_ds6a_ome(ome)
        print(f"registered ds6a {entry['name']}", flush=True)
        return {**entry, "url": item["links"]["self"], "bytes": int(item["size"]), "md5": md5, "sha256": sha256,
                "shape": ome["shape"], "acquired": ome["acquired"]}

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        entries = list(pool.map(fetch, chosen))
    manifest = {
        "schema": "cytellect-public-nucleolar-indeterminate/1", "protocol": PROTOCOL,
        "script": "scripts/validate_nucleolar_indeterminate_public.py",
        "originals": "Downloaded outside the checkout; never committed.",
        "ds6b": "All 360 files of fixtures/public/nucleolar-shape/manifest.json: 30min and 2hrs = tuning, "
                "4hrs = evaluation.",
        "ds6a": {
            **{key: value for key, value in DS6A.items() if key != "record"},
            "record": DS6A["record"], "record_title": record["metadata"].get("title"),
            "record_license_id": (record["metadata"].get("license") or {}).get("id"),
            "record_files": len(files),
            "excluded_demo_files": sorted(excluded),
            "excluded_rule": "Every file named in the sources of services/showcase/datasets/zenodo-6643470*.json "
                             "(the registered demo scenes).",
            "split_rule": f"Parity of the first byte of SHA-256('{SPLIT_SALT}' + file name): even = tuning, "
                          "odd = evaluation. Names only; fixed before download.",
            "subset_rule": f"Per replicate x condition x split, the {DS6A_PER_CELL} files with the smallest such "
                           "digest (disk space).",
            "split_counts": {split: sum(1 for name in files if name not in excluded and split_of(name) == split)
                             for split in ("tuning", "evaluation")},
            "registered_files": len(entries),
            "files": entries,
        },
    }
    MANIFEST.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return manifest


# --------------------------------------------------------------------------------------------------------------
# Fields
# --------------------------------------------------------------------------------------------------------------
def fields(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    """Every field with its comparison set, condition and the OME calibration it must carry."""
    out = []
    for entry in json.loads(SHAPE_MANIFEST.read_text(encoding="utf-8"))["datasets"]["ds6b"]["files"]:
        out.append({"dataset": "ds6b", "name": entry["name"], "sha256": entry["sha256"], "bytes": entry["bytes"],
                    "split": entry["split"], "set": f"ds6b-{entry['timepoint']}", "condition": entry["condition"],
                    "replicate": None, "pixel_um": 0.325, "nuclear": 0, "npm1": 1})
    for entry in manifest["ds6a"]["files"]:
        out.append({"dataset": "ds6a", "name": entry["name"], "sha256": entry["sha256"], "bytes": entry["bytes"],
                    "split": entry["split"], "set": f"ds6a-{entry['split']}", "condition": entry["condition"],
                    "replicate": entry["replicate"], "pixel_um": DS6A["pixel_um"],
                    "nuclear": DS6A["channels"]["nuclear"], "npm1": DS6A["channels"]["npm1"]})
    return out


def load_planes(data_dir: Path, field: dict[str, Any]) -> tuple[np.ndarray, np.ndarray, float]:
    import tifffile

    path = Path(data_dir) / field["dataset"] / field["name"]
    data = path.read_bytes()
    if len(data) != field["bytes"] or hashlib.sha256(data).hexdigest() != field["sha256"]:
        raise ValueError("public_original_hash_mismatch")
    del data
    ome = shape.ome_record(path)
    if abs(ome["pixel_x_um"] - field["pixel_um"]) > 1e-9 or abs(ome["pixel_y_um"] - field["pixel_um"]) > 1e-9:
        raise ValueError("public_ome_metadata_changed")
    if field["dataset"] == "ds6a":
        check_ds6a_ome(ome)
    else:
        shape.check_ome("ds6b", ome)
    stack = tifffile.imread(path)
    return (np.ascontiguousarray(stack[field["nuclear"]]), np.ascontiguousarray(stack[field["npm1"]]),
            float(ome["pixel_x_um"] * ome["pixel_y_um"]))


def stem(field: dict[str, Any]) -> str:
    return field["name"].removesuffix(".tif")


# --------------------------------------------------------------------------------------------------------------
# Nuclei (R2), cached once
# --------------------------------------------------------------------------------------------------------------
def nuclei_field(task: dict[str, Any]) -> dict[str, Any]:
    field, work = task["field"], Path(task["work"])
    target = work / "nuclei" / field["dataset"]
    target.mkdir(parents=True, exist_ok=True)
    out = target / f"{stem(field)}.npz"
    record = target / f"{stem(field)}.json"
    if out.is_file() and record.is_file():
        previous = json.loads(record.read_text(encoding="utf-8"))
        if previous.get("sha256") == field["sha256"] and previous.get("status") == "ok":
            return previous
    info: dict[str, Any] = {"protocol": PROTOCOL, "name": field["name"], "sha256": field["sha256"], "status": "failed"}
    scratch = work / "tmp" / stem(field)
    try:
        nuclear, _, _ = load_planes(Path(task["data_dir"]), field)
        detector = shape.product_detectors()["nuclear"]
        labels, scale = shape.detect_nuclei_auto(nuclear, detector, scratch, task["fiji"])
        from cytellect_analysis.nuclear_scale import PROTOCOL as SCALE_PROTOCOL

        np.savez_compressed(out, labels=labels.astype(np.uint32))
        info.update(status="ok", nuclei=int(len(np.unique(labels)) - 1), scale_protocol=SCALE_PROTOCOL,
                    detector=detector, **scale)
    except Exception as error:  # noqa: BLE001 - every failure is recorded with its reason
        info.update(error=shape.redact(f"{type(error).__name__}: {error}"),
                    traceback=shape.redact(traceback.format_exc(limit=4)[-1500:]))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    record.write_text(json.dumps(info, indent=1, default=float) + "\n", encoding="utf-8")
    print(f"nuclei {field['name']}: {info['status']} {info.get('nuclei')}", flush=True)
    return info


def run_nuclei(data_dir: Path, work: Path, fiji: str, workers: int, only: str | None) -> None:
    work = shape.outside_checkout(work)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = [{"field": field, "work": str(work), "data_dir": str(data_dir), "fiji": fiji}
             for field in fields(manifest) if only is None or field["dataset"] == only]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(nuclei_field, tasks))
    print(json.dumps({"fields": len(results), "failed": sum(r["status"] != "ok" for r in results)}))


# --------------------------------------------------------------------------------------------------------------
# Nucleolar versions on cached nuclei
# --------------------------------------------------------------------------------------------------------------
REASONS = ("", "insufficient_marker_contrast", "uniform_or_empty_interior")
STATES = ("candidate", "no_candidate", "indeterminate")


def measure_version(marker: np.ndarray, nuclei: np.ndarray, nucleoli: np.ndarray, info: dict) -> dict[str, np.ndarray]:
    """Per parent and per object values of one detection, from original marker pixels."""
    from scipy import ndimage as ndi

    pixels = marker.astype(np.float64)
    parents = np.asarray([int(v) for v in np.unique(nuclei) if v], np.int64)
    states = {int(k): v for k, v in info["nucleolar_states"].items()}
    thresholds = {int(k): v for k, v in info["nucleolar_thresholds"].items()}
    union = nucleoli > 0
    union_labels = np.where(union, nuclei, 0)
    plasm_labels = np.where(union, 0, nuclei)
    ids = parents.tolist()
    ones = np.ones_like(pixels)
    union_area = np.asarray(ndi.sum_labels(ones, union_labels, ids), np.int64) if ids else np.zeros(0, np.int64)
    with np.errstate(invalid="ignore", divide="ignore"):
        union_mean = np.asarray(ndi.mean(pixels, union_labels, ids), np.float64) if ids else np.zeros(0)
        plasm_mean = np.asarray(ndi.mean(pixels, plasm_labels, ids), np.float64) if ids else np.zeros(0)
    union_mean = np.where(union_area > 0, union_mean, np.nan)
    objects = np.asarray([int(v) for v in np.unique(nucleoli) if v], np.int64)
    oids = objects.tolist()
    area = np.asarray(ndi.sum_labels(ones, nucleoli, oids), np.int64) if oids else np.zeros(0, np.int64)
    mean = np.asarray(ndi.mean(pixels, nucleoli, oids), np.float64) if oids else np.zeros(0)
    parent = np.asarray(ndi.maximum(nuclei, nucleoli, oids), np.int64) if oids else np.zeros(0, np.int64)
    count = np.bincount(np.searchsorted(parents, parent), minlength=len(parents)) if oids else np.zeros(len(parents), np.int64)
    return {
        "parent_id": parents,
        "state": np.asarray([STATES.index(states.get(p, "indeterminate")) for p in ids], np.int8),
        "reason": np.asarray([REASONS.index(thresholds.get(p, {}).get("missing_reason") or "") for p in ids], np.int8),
        "snr": np.asarray([thresholds.get(p, {}).get("marker_contrast_snr", np.nan) for p in ids], np.float64),
        "union_area": union_area, "union_mean": union_mean, "plasm_mean": plasm_mean, "count": count,
        "object_parent": parent, "object_area": area, "object_mean": mean,
    }


def detect(nuclear: np.ndarray, marker: np.ndarray, nuclei: np.ndarray, detector: dict[str, Any],
           pixel_area_um2: float | None) -> dict[str, np.ndarray]:
    from cytellect_analysis.nucleolar_detector_v2 import detect_nucleoli_v2

    nucleoli, info = detect_nucleoli_v2(nuclear, marker, nuclei, detector, pixel_area_um2=pixel_area_um2)
    record = measure_version(marker, nuclei, nucleoli, info)
    record["minimum_area_px"] = np.asarray([(info.get("minimum_area") or {}).get("px", detector["minimum_area_px"])])
    record["noise"] = np.asarray([(info.get("marker_contrast") or {}).get("noise", np.nan)])
    return record


def versions_for(stage: str, k: float | None) -> dict[str, tuple[dict[str, Any], bool]]:
    """Detector and whether it receives the calibration, per version name."""
    if stage == "tune":
        return {"baseline": (BASELINE, False), "nogate": ({**NEW_BASE, "minimum_contrast_snr": NO_GATE_K}, True)}
    from cytellect_analysis.nucleolar_detector_v2 import NucleolarDetectorV22

    product = NucleolarDetectorV22().model_dump(mode="json")
    if product["minimum_contrast_snr"] != k:
        raise ValueError("evaluation_k_differs_from_tuning")
    return {"baseline": (BASELINE, False), "new": (product, True),
            "area_only": ({**product, "minimum_contrast_snr": NO_GATE_K}, True), "gate_only": (product, False)}


def versions_field(task: dict[str, Any]) -> dict[str, Any]:
    field, work, stage = task["field"], Path(task["work"]), task["stage"]
    target = work / stage / field["dataset"]
    target.mkdir(parents=True, exist_ok=True)
    out, record = target / f"{stem(field)}.npz", target / f"{stem(field)}.json"
    info: dict[str, Any] = {"protocol": PROTOCOL, "name": field["name"], "sha256": field["sha256"], "status": "failed"}
    try:
        nuclei_info = json.loads((work / "nuclei" / field["dataset"] / f"{stem(field)}.json").read_text(encoding="utf-8"))
        if nuclei_info.get("status") != "ok" or nuclei_info.get("sha256") != field["sha256"]:
            raise ValueError("nuclei_not_available")
        with np.load(work / "nuclei" / field["dataset"] / f"{stem(field)}.npz") as data:
            nuclei = data["labels"]
        nuclear, marker, pixel_area = load_planes(Path(task["data_dir"]), field)
        arrays = {}
        for version, (detector, calibrated) in versions_for(stage, task.get("k")).items():
            for key, value in detect(nuclear, marker, nuclei, detector, pixel_area if calibrated else None).items():
                arrays[f"{version}.{key}"] = value
        np.savez_compressed(out, **arrays)
        info.update(status="ok", nuclei=int(len(np.unique(nuclei)) - 1), pixel_area_um2=pixel_area)
    except Exception as error:  # noqa: BLE001 - every failure is recorded with its reason
        info.update(error=shape.redact(f"{type(error).__name__}: {error}"),
                    traceback=shape.redact(traceback.format_exc(limit=4)[-1500:]))
    record.write_text(json.dumps(info, indent=1, default=float) + "\n", encoding="utf-8")
    print(f"{stage} {field['name']}: {info['status']}", flush=True)
    return info


def gate(arrays: dict[str, np.ndarray], source: str, k: float) -> dict[str, np.ndarray]:
    """Apply the 2.2.0 contrast rule with minimum k to a no-gate record (identical to running the product with k)."""
    snr = arrays[f"{source}.snr"]
    low = np.isfinite(snr) & (snr < k)
    out = {key.split(".", 1)[1]: value for key, value in arrays.items() if key.startswith(source + ".")}
    out["state"] = np.where(low, STATES.index("indeterminate"), out["state"]).astype(np.int8)
    out["reason"] = np.where(low, REASONS.index("insufficient_marker_contrast"), out["reason"]).astype(np.int8)
    out["union_area"] = np.where(low, 0, out["union_area"])
    out["union_mean"] = np.where(low, np.nan, out["union_mean"])
    out["count"] = np.where(low, 0, out["count"])
    dropped = np.isin(out["object_parent"], out["parent_id"][low])
    # The nucleoplasm of a gated parent becomes the whole nucleus; it is not used (the parent is not measured).
    for key in ("object_parent", "object_area", "object_mean"):
        out[key] = out[key][~dropped]
    return out


def version(arrays: dict[str, np.ndarray], name: str) -> dict[str, np.ndarray]:
    return {key.split(".", 1)[1]: value for key, value in arrays.items() if key.startswith(name + ".")}


# --------------------------------------------------------------------------------------------------------------
# Criteria (R4)
# --------------------------------------------------------------------------------------------------------------
def condition_stats(records: list[tuple[dict[str, Any], dict[str, np.ndarray]]], pixel_um: float) -> dict[str, Any]:
    nuclei = indeterminate = contrast = measured = objects = dim = 0
    union_mean, union_area, object_mean, object_area = [], [], [], []
    for _, r in records:
        nuclei += len(r["parent_id"])
        indeterminate += int(np.sum(r["state"] == STATES.index("indeterminate")))
        contrast += int(np.sum(r["reason"] == REASONS.index("insufficient_marker_contrast")))
        ok = r["state"] == STATES.index("candidate")
        measured += int(ok.sum())
        union_mean.append(r["union_mean"][ok])
        union_area.append(r["union_area"][ok])
        lookup = {int(p): i for i, p in enumerate(r["parent_id"])}
        rows = np.asarray([lookup[int(p)] for p in r["object_parent"]], np.int64)
        plasm = r["plasm_mean"][rows] if rows.size else np.zeros(0)
        objects += len(r["object_area"])
        dim += int(np.sum(r["object_mean"] <= DIM_RATIO * plasm))
        object_mean.append(r["object_mean"])
        object_area.append(r["object_area"])
    um = np.concatenate(union_mean) if union_mean else np.zeros(0)
    ua = np.concatenate(union_area) if union_area else np.zeros(0)
    oa = np.concatenate(object_area) if object_area else np.zeros(0)
    om = np.concatenate(object_mean) if object_mean else np.zeros(0)
    area_um2 = oa * pixel_um * pixel_um
    edges = (*SIZE_EDGES_UM2, math.inf)
    sizes = {f"{lo:g}-{hi:g}" if math.isfinite(hi) else f">={lo:g}": int(np.sum((area_um2 >= lo) & (area_um2 < hi)))
             for lo, hi in zip(edges[:-1], edges[1:])}
    return {
        "fields": len(records), "nuclei": nuclei, "indeterminate": indeterminate,
        "indeterminate_contrast": contrast, "indeterminate_rate": indeterminate / nuclei if nuclei else None,
        "measured_nuclei": measured, "objects": objects, "dim_objects": dim,
        "dim_share": dim / objects if objects else None,
        "union_mean_median": float(np.median(um)) if um.size else None,
        "union_area_median": float(np.median(ua)) if ua.size else None,
        "object_area_median_px": float(np.median(oa)) if oa.size else None,
        "object_mean_median": float(np.median(om)) if om.size else None,
        "object_size_um2": sizes,
    }


def set_stats(by_condition: dict[str, dict[str, Any]], baseline: dict[str, dict[str, Any]] | None) -> dict[str, Any]:
    rates = [c["indeterminate_rate"] for c in by_condition.values() if c["indeterminate_rate"] is not None]
    spread = (max(rates) - min(rates)) if rates else None
    dims = [c["dim_share"] for c in by_condition.values() if c["dim_share"] is not None]
    out: dict[str, Any] = {"conditions": by_condition, "rate_spread": spread,
                           "dim_share_max": max(dims) if dims else None}
    a1 = spread is not None and len(rates) == len(by_condition) and spread <= RATE_SPREAD + 1e-12
    a2 = len(dims) == len(by_condition) and all(d <= DIM_SHARE_MAX + 1e-12 for d in dims)
    out["A1"], out["A2"] = bool(a1), bool(a2)
    if baseline is not None:
        changes, a3 = {}, True
        for condition, stats in by_condition.items():
            row = {}
            for key in ("union_mean_median", "union_area_median"):
                old, new = baseline[condition][key], stats[key]
                change = (new / old - 1) if old and new is not None else None
                row[key] = change
                a3 = a3 and change is not None and abs(change) <= WIDTH + 1e-12
            changes[condition] = row
        out["changes_from_baseline"] = changes
        out["A3"] = bool(a3)
    return out


def aggregate(work: Path, stage: str, field_list: list[dict[str, Any]], sets: tuple[str, ...],
              versions: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    """``versions``: name -> function(arrays) -> record."""
    grouped: dict[str, dict[str, list]] = {name: defaultdict(list) for name in versions}
    failures, pixel = [], {}
    for field in field_list:
        if field["set"] not in sets:
            continue
        path = work / stage / field["dataset"] / f"{stem(field)}.json"
        info = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"status": "not_run"}
        if info.get("status") != "ok" or info.get("sha256") != field["sha256"]:
            failures.append({"set": field["set"], "name": field["name"], "status": info.get("status", "stale"),
                             "error": info.get("error")})
            continue
        with np.load(path.with_suffix(".npz")) as data:
            arrays = {key: data[key] for key in data.files}
        pixel[field["set"]] = field["pixel_um"]
        for name, make in versions.items():
            grouped[name][(field["set"], field["condition"])].append((field, make(arrays)))
    result: dict[str, Any] = {}
    for set_name in sets:
        per_version = {}
        for name in versions:
            per_version[name] = {condition: condition_stats(records, pixel.get(set_name, 0.0))
                                 for (s, condition), records in sorted(grouped[name].items()) if s == set_name}
        result[set_name] = {name: set_stats(per_version[name], per_version["baseline"] if name != "baseline" else None)
                            for name in versions}
    return result, failures


def choose_k(per_k: dict[float, dict[str, Any]]) -> tuple[float, bool]:
    for k in K_GRID:
        if all(per_k[k][s]["new"]["A1"] and per_k[k][s]["new"]["A2"] and per_k[k][s]["new"]["A3"] for s in TUNING_SETS):
            return k, True
    return PRECEDENT_K, False


# --------------------------------------------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------------------------------------------
def run_stage(data_dir: Path, work: Path, stage: str, split: str, workers: int, k: float | None) -> list[dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    tasks = [{"field": field, "work": str(work), "data_dir": str(data_dir), "stage": stage, "k": k}
             for field in fields(manifest) if field["split"] == split]
    with concurrent.futures.ProcessPoolExecutor(max_workers=workers) as pool:
        return list(pool.map(versions_field, tasks))


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True, timeout=60).stdout.strip()


def tune(data_dir: Path, work: Path, workers: int) -> dict[str, Any]:
    work = shape.outside_checkout(work)
    run_stage(data_dir, work, "tune", "tuning", workers, None)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    field_list = fields(manifest)
    per_k, failures = {}, []
    for k in K_GRID:
        per_k[k], failures = aggregate(work, "tune", field_list, TUNING_SETS,
                                       {"baseline": lambda a: version(a, "baseline"),
                                        "new": lambda a, k=k: gate(a, "nogate", k)})
    chosen, passed = choose_k(per_k)
    record = {"protocol": PROTOCOL, "rule_commit": git("rev-parse", "HEAD"), "k_grid": list(K_GRID),
              "chosen_k": chosen, "tuning_passed": passed, "per_k": {str(k): v for k, v in per_k.items()},
              "failures": failures}
    (work / "tuning.json").write_text(json.dumps(record, indent=1, default=float) + "\n", encoding="utf-8")
    return record


def evaluate(data_dir: Path, work: Path, workers: int) -> dict[str, Any]:
    work = shape.outside_checkout(work)
    target = work / "evaluation.json"
    if target.exists():
        raise SystemExit("evaluation already recorded; a rerun is not silent (remove it and report why)")
    tuning = json.loads((work / "tuning.json").read_text(encoding="utf-8"))
    if git("status", "--porcelain", "--", *RULE_FILES):
        raise SystemExit("rule or detector files have uncommitted changes")
    k = float(tuning["chosen_k"])
    run_stage(data_dir, work, "evaluate", "evaluation", workers, k)
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    result, failures = aggregate(work, "evaluate", fields(manifest), EVALUATION_SETS,
                                 {name: (lambda a, name=name: version(a, name))
                                  for name in ("baseline", "new", "area_only", "gate_only")})
    passed = all(result[s]["new"]["A1"] and result[s]["new"]["A2"] and result[s]["new"]["A3"] for s in EVALUATION_SETS)
    record = {"protocol": PROTOCOL, "evaluation_commit": git("rev-parse", "HEAD"), "k": k,
              "passed": passed and not failures, "sets": result, "failures": failures}
    target.write_text(json.dumps(record, indent=1, default=float) + "\n", encoding="utf-8")
    return record


def summarize(work: Path, output: Path) -> dict[str, Any]:
    tuning = json.loads((work / "tuning.json").read_text(encoding="utf-8"))
    evaluation_path = work / "evaluation.json"
    evaluation = json.loads(evaluation_path.read_text(encoding="utf-8")) if evaluation_path.exists() else None
    nuclei = defaultdict(lambda: {"fields": 0, "failed": 0, "diameter_px": []})
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    for field in fields(manifest):
        path = work / "nuclei" / field["dataset"] / f"{stem(field)}.json"
        info = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {"status": "not_run"}
        entry = nuclei[field["set"]]
        entry["fields"] += 1
        if info.get("status") != "ok":
            entry["failed"] += 1
        elif info.get("diameter_px") is not None:
            entry["diameter_px"].append(info["diameter_px"])
    nuclear = {name: {"fields": v["fields"], "failed": v["failed"],
                      "diameter_px_min": min(v["diameter_px"]) if v["diameter_px"] else None,
                      "diameter_px_max": max(v["diameter_px"]) if v["diameter_px"] else None}
               for name, v in sorted(nuclei.items())}
    summary = {"protocol": PROTOCOL, "rules": {"k_grid": list(K_GRID), "precedent_k": PRECEDENT_K,
                                               "rate_spread": RATE_SPREAD, "dim_ratio": DIM_RATIO,
                                               "dim_share_max": DIM_SHARE_MAX, "width": WIDTH,
                                               "baseline": BASELINE},
               "nuclei": nuclear, "tuning": tuning, "evaluation": evaluation}
    output.write_text(json.dumps(summary, indent=1, ensure_ascii=False, default=float) + "\n", encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    one = commands.add_parser("register", help="choose, download and verify the DS6a fields")
    one.add_argument("--data-dir", type=Path, required=True)
    two = commands.add_parser("nuclei", help="detect and cache nuclei of every field (real Fiji)")
    two.add_argument("--data-dir", type=Path, required=True)
    two.add_argument("--work", type=Path, required=True)
    two.add_argument("--fiji", required=True)
    two.add_argument("--workers", type=int, default=1)
    two.add_argument("--dataset", choices=("ds6a", "ds6b"))
    for name in ("tune", "evaluate"):
        sub = commands.add_parser(name)
        sub.add_argument("--data-dir", type=Path, required=True)
        sub.add_argument("--work", type=Path, required=True)
        sub.add_argument("--workers", type=int, default=1)
    three = commands.add_parser("summarize")
    three.add_argument("--work", type=Path, required=True)
    three.add_argument("--output", type=Path, default=SUMMARY)
    args = parser.parse_args(argv)
    if args.command == "register":
        manifest = register(args.data_dir)
        print(json.dumps({"registered": manifest["ds6a"]["registered_files"], "splits": manifest["ds6a"]["split_counts"]}))
    elif args.command == "nuclei":
        run_nuclei(args.data_dir, args.work, args.fiji, args.workers, args.dataset)
    elif args.command == "tune":
        record = tune(args.data_dir, args.work, args.workers)
        print(json.dumps({"chosen_k": record["chosen_k"], "tuning_passed": record["tuning_passed"],
                          "failures": len(record["failures"])}))
    elif args.command == "evaluate":
        record = evaluate(args.data_dir, args.work, args.workers)
        print(json.dumps({"k": record["k"], "passed": record["passed"], "failures": len(record["failures"])}))
    else:
        summarize(args.work, args.output)


if __name__ == "__main__":
    sys.exit(main())

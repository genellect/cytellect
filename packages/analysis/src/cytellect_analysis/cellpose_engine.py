"""Pinned, offline Cellpose-SAM candidates; original-coordinate integer labels."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import Field, FiniteFloat, model_validator
from scipy import ndimage as ndi

from .masks import validate_label_array
from .regions import RegionModel, _array_hash

MODEL_SHA256: Literal["0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667"] = "0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667"
MODEL_SIZE = 1233586851


class CellposeParameters(RegionModel):
    model: Literal["cpsam_v2"] = "cpsam_v2"
    model_sha256: Literal["0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667"] = MODEL_SHA256
    diameter_px: FiniteFloat | None = Field(default=None, gt=0, le=4096)
    normalization_percentile_low: FiniteFloat = Field(default=1.0, ge=0, lt=100)
    normalization_percentile_high: FiniteFloat = Field(default=99.0, gt=0, le=100)
    flow_threshold: FiniteFloat = Field(default=0.4, gt=0, le=10)
    cellprob_threshold: FiniteFloat = Field(default=0.0, ge=-20, le=20)
    minimum_area_px: int = Field(default=15, ge=1, le=16777216)
    maximum_size_fraction: FiniteFloat = Field(default=1.0, gt=0, le=1)
    iterations: int | None = Field(default=None, ge=1, le=10000)
    batch_size: int = Field(default=1, ge=1, le=8)
    compute_device: Literal["cpu", "auto", "cuda"] = "cpu"

    @model_validator(mode="after")
    def ordered_percentiles(self):
        if self.normalization_percentile_low >= self.normalization_percentile_high:
            raise ValueError("cellpose_normalization_range_invalid")
        return self


class CellposeDetectorSpec(CellposeParameters):
    engine: Literal["cellpose-sam"] = "cellpose-sam"
    protocol_version: Literal["4.0.0"] = "4.0.0"


class NclCellposeDetectorSpec(CellposeParameters):
    engine: Literal["cellpose-sam-ncl"] = "cellpose-sam-ncl"
    protocol_version: Literal["4.1.0"] = "4.1.0"
    smoothing_sigma_px: FiniteFloat = Field(default=0.9, gt=0, le=16)
    background_radius_px: int = Field(default=10, ge=1, le=128)


class NclParentCellposeDetectorSpec(CellposeParameters):
    """Parent-conditioned NCL copy; 4.0/4.1 replay is deliberately unchanged."""
    engine: Literal["cellpose-sam-ncl-parent"] = "cellpose-sam-ncl-parent"
    protocol_version: Literal["4.2.0", "4.2.1"] = "4.2.1"
    smoothing_sigma_px: FiniteFloat = Field(default=0.9, gt=0, le=16)
    parent_background_percentile: FiniteFloat = Field(default=75, ge=0, lt=100)
    nuclear_diameter_fraction: FiniteFloat = Field(default=0.25, gt=0, le=1)
    crop_padding_px: int = Field(default=32, ge=1, le=256)
    minimum_contrast_snr: FiniteFloat = Field(default=5, gt=0, le=100)
    local_background_radius_px: int = Field(default=8, ge=1, le=128)
    maximum_nuclear_coverage: FiniteFloat = Field(default=0.5, gt=0, lt=1)


def _assets() -> Path:
    configured = os.environ.get("CYTELLECT_CELLPOSE_ASSETS")
    if configured:
        return Path(configured)
    for parent in Path(__file__).resolve().parents:
        candidate = parent / "engines" / "cellpose"
        if (candidate / "runtime.lock.json").is_file():
            return candidate
    # Windows wheels can live outside the extracted application. The managed
    # launcher fixes cwd to that version's app directory. Accept only its
    # release-bound adapter; never search arbitrary sibling/global directories.
    root = Path.cwd()
    candidate = root / "engines" / "cellpose"
    if (candidate / "runtime.lock.json").is_file():
        _verify_release_assets(root, candidate)
        return candidate
    raise ValueError("cellpose_adapter_missing")


@lru_cache(maxsize=8)
def _verified_hash(path: str, _size: int, _mtime: int, _ctime: int) -> str:
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _verify_file(path: Path, expected: str, size: int | None, error: str):
    if not path.is_file():
        raise ValueError(error)
    stat = path.stat()
    if size is not None and stat.st_size != size:
        raise ValueError(error)
    if _verified_hash(str(path.resolve()), stat.st_size, stat.st_mtime_ns, stat.st_ctime_ns) != expected:
        raise ValueError(error)


def _verify_release_assets(root: Path, assets: Path):
    """Bind the cwd fallback to the installer's complete release manifest."""
    error = "cellpose_adapter_integrity_failed"
    try:
        release = json.loads((root / "local-release.json").read_text(encoding="utf-8"))
        if (not isinstance(release, dict) or release.get("schema") != "cytellect-local-release/1"
                or release.get("platform") != "windows-x64"):
            raise ValueError(error)
        files = release.get("files")
        if not isinstance(files, list) or any(not isinstance(entry, dict) for entry in files):
            raise ValueError(error)
        for name in ("runtime.lock.json", "runner.py", "requirements.lock"):
            relative = f"engines/cellpose/{name}"
            entries = [entry for entry in files if entry.get("path") == relative]
            path = assets / name
            if len(entries) != 1 or not path.resolve().is_relative_to(root.resolve()):
                raise ValueError(error)
            if any(part.is_symlink() or part.is_junction() for part in [path, assets, assets.parent, root]):
                raise ValueError(error)
            _verify_file(path, entries[0]["sha256"], entries[0]["size"], error)
        lock = json.loads((assets / "runtime.lock.json").read_text(encoding="utf-8"))
        if (not isinstance(lock, dict) or not isinstance(lock.get("model"), dict)
                or lock.get("schema") != "cytellect-cellpose-runtime/1" or lock.get("python") != "3.12"
                or lock["model"]["sha256"] != MODEL_SHA256 or lock["model"]["size"] != MODEL_SIZE):
            raise ValueError(error)
        _verify_file(assets / "runner.py", lock["runner_sha256"], None, error)
        _verify_file(assets / "requirements.lock", lock["requirements_sha256"], None, error)
    except (OSError, KeyError, TypeError, json.JSONDecodeError) as exception:
        raise ValueError(error) from exception


def runtime_status() -> dict:
    """Sanitized capability probe, without loading Torch or making requests."""
    try:
        assets = _assets()
        lock = json.loads((assets / "runtime.lock.json").read_text(encoding="utf-8"))
        python = os.environ.get("CYTELLECT_CELLPOSE_PYTHON")
        model_dir = os.environ.get("CYTELLECT_CELLPOSE_MODEL_DIR")
        if not python or not Path(python).is_file():
            raise ValueError("cellpose_runtime_missing")
        if not model_dir:
            raise ValueError("cellpose_model_missing")
        _verify_file(assets / "runner.py", lock["runner_sha256"], None, "cellpose_adapter_integrity_failed")
        model = Path(model_dir) / "cpsam_v2"
        if not model.is_file():
            raise ValueError("cellpose_model_missing")
        _verify_file(model, MODEL_SHA256, MODEL_SIZE, "cellpose_model_integrity_failed")
        return {"available": True, "model": "cpsam_v2", "model_sha256": MODEL_SHA256,
                "packages": lock["packages"], "python": "3.12", "runtime_downloads": False}
    except (ValueError, OSError, KeyError, json.JSONDecodeError) as error:
        message = str(error)
        return {"available": False, "error": message if message.startswith("cellpose_")
                else "cellpose_runtime_invalid", "runtime_downloads": False}


def exclude_nuclear_scale_candidates(raw: np.ndarray, nuclei: np.ndarray, maximum_coverage: float) -> tuple[np.ndarray, list[dict]]:
    """Remove whole candidate instances, never subtract adopted nuclear pixels.

    A candidate must be predominantly in one parent (90% of its pixels) and
    occupy more than the recorded fraction of that parent. Boundary/ambiguous
    candidates still go through the independent parent binder. Raw labels stay
    available as an artifact; a rejected nucleus does not imply absent nucleoli.
    """
    validate_label_array(raw)
    validate_label_array(nuclei)
    if raw.shape != nuclei.shape:
        raise ValueError("cellpose_parent_shape_invalid")
    if not 0 < maximum_coverage < 1:
        raise ValueError("cellpose_nuclear_coverage_invalid")
    filtered = raw.copy()
    parent_area = {int(v): int(count) for v, count in zip(*np.unique(nuclei, return_counts=True)) if v}
    excluded = []
    for source in (int(v) for v in np.unique(raw) if v):
        pieces, count = ndi.label(raw == source, np.ones((3, 3), bool))
        for component in range(1, count + 1):
            mask = pieces == component
            ids, overlaps = np.unique(nuclei[mask], return_counts=True)
            for parent, overlap in zip(ids, overlaps):
                if not parent:
                    continue
                coverage = float(overlap / parent_area[int(parent)])
                purity = float(overlap / mask.sum())
                if coverage > maximum_coverage and purity >= 0.9:
                    filtered[mask] = 0
                    excluded.append({"source_label_id": source, "component": component,
                                     "parent_id": int(parent), "reason": "nuclear_scale_candidate",
                                     "nuclear_coverage": coverage, "parent_purity": purity})
                    break
    return filtered, excluded


def bind_nucleolar_candidates(raw: np.ndarray, nuclei: np.ndarray) -> tuple[np.ndarray, dict]:
    """Reject ambiguous/boundary objects whole, retaining raw masks for review."""
    validate_label_array(raw)
    validate_label_array(nuclei)
    if raw.shape != nuclei.shape:
        raise ValueError("cellpose_parent_shape_invalid")
    labels = np.zeros_like(raw, dtype=np.uint32)
    states = {int(value): "no_candidate" for value in np.unique(nuclei) if value}
    parents: dict[int, int] = {}
    objects: dict[int, dict] = {}
    review: list[dict] = []
    next_id = 1
    for source_id in (int(value) for value in np.unique(raw) if value):
        # Defensive split: disconnected pixels must never share one object ID.
        pieces, count = ndi.label(raw == source_id, np.ones((3, 3), dtype=bool))
        for piece in range(1, count + 1):
            mask = pieces == piece
            present = np.unique(nuclei[mask])
            nonzero = [int(value) for value in present if value]
            reason = None
            if not nonzero:
                reason = "outside_adopted_nuclei"
            elif len(nonzero) != 1:
                reason = "multiple_parent_nuclei"
            elif 0 in present:
                reason = "crosses_nuclear_boundary"
            elif (mask & ~ndi.binary_erosion(nuclei == nonzero[0], np.ones((3, 3), bool))).any():
                reason = "touches_nuclear_boundary"
            if reason:
                review.append({"source_label_id": source_id, "component": piece,
                               "reason": reason, "parent_ids": nonzero})
                for parent in nonzero:
                    states[parent] = "review_required"
                continue
            parent = nonzero[0]
            labels[mask] = next_id
            parents[next_id] = parent
            objects[next_id] = {"parent_id": parent, "source_label_id": source_id, "component": piece}
            if states[parent] != "review_required":
                states[parent] = "candidate"
            next_id += 1
    return labels, {"parent_ids": parents, "objects": objects, "nucleolar_states": states,
                    "review_candidates": review, "review_candidate_count": len(review),
                    "parent_policy": "fully_contained_single_parent_no_clipping"}


def detect_cellpose(image: np.ndarray, detector: CellposeDetectorSpec | NclCellposeDetectorSpec | NclParentCellposeDetectorSpec, output_dir: Path,
                    nuclei: np.ndarray | None = None) -> tuple[np.ndarray, dict]:
    detector = (NclParentCellposeDetectorSpec.model_validate(detector) if isinstance(detector, NclParentCellposeDetectorSpec)
                else NclCellposeDetectorSpec.model_validate(detector) if isinstance(detector, NclCellposeDetectorSpec)
                else CellposeDetectorSpec.model_validate(detector))
    if image.ndim != 2 or image.dtype not in (np.uint8, np.uint16) or not image.size:
        raise ValueError("cellpose_input_invalid")
    if nuclei is not None:
        validate_label_array(nuclei)
        if nuclei.shape != image.shape:
            raise ValueError("cellpose_parent_shape_invalid")
    if isinstance(detector, NclParentCellposeDetectorSpec) and nuclei is None:
        raise ValueError("cellpose_adopted_nuclei_required")
    capability = runtime_status()
    if not capability["available"]:
        raise ValueError(capability["error"])
    assets = _assets()
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    source, raw_path = output_dir / "cellpose-input.npy", output_dir / "cellpose-raw-labels.npy"
    request_path, receipt_path = output_dir / "cellpose-request.json", output_dir / "cellpose-receipt.json"
    np.save(source, image, allow_pickle=False)
    parent_path = output_dir / "cellpose-parent-input.npy"
    request = {"input_path": str(source.resolve()),
                                      "output_path": str(raw_path.resolve()),
                                      "model_path": str((Path(os.environ["CYTELLECT_CELLPOSE_MODEL_DIR"]) /
                                                         "cpsam_v2").resolve()),
                                      "parameters": detector.model_dump(mode="json")}
    if isinstance(detector, NclParentCellposeDetectorSpec):
        np.save(parent_path, nuclei, allow_pickle=False)
        request["parent_path"] = str(parent_path.resolve())
    request_path.write_text(json.dumps(request), encoding="utf-8")
    environment = os.environ.copy()
    environment.update({"HF_HUB_OFFLINE": "1", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONNOUSERSITE": "1"})
    environment.pop("PYTHONPATH", None)
    try:
        result = subprocess.run([os.environ["CYTELLECT_CELLPOSE_PYTHON"], "-I", str(assets / "runner.py"),
                                 str(request_path.resolve()), str(receipt_path.resolve())],
                                capture_output=True, env=environment, timeout=1800, check=False)
        if not receipt_path.is_file():
            raise ValueError("cellpose_inference_failed")
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        if result.returncode or receipt.get("status") != "succeeded":
            code = receipt.get("error", "cellpose_inference_failed")
            raise ValueError(code if code.startswith("cellpose_") and len(code) < 80 else "cellpose_inference_failed")
        raw = np.load(raw_path, allow_pickle=False)
        try:
            validate_label_array(raw)
        except ValueError as error:
            raise ValueError("cellpose_output_invalid") from error
        if raw.shape != image.shape:
            raise ValueError("cellpose_output_shape_invalid")
        binding_input, nuclear_exclusions = raw, []
        if isinstance(detector, NclParentCellposeDetectorSpec) and detector.protocol_version == "4.2.1":
            binding_input, nuclear_exclusions = exclude_nuclear_scale_candidates(raw, nuclei, detector.maximum_nuclear_coverage)
        labels, binding = bind_nucleolar_candidates(binding_input, nuclei) if nuclei is not None else (raw.astype(np.uint32), {})
        if isinstance(detector, NclParentCellposeDetectorSpec) and detector.protocol_version == "4.2.1":
            binding["nuclear_candidate_filter"] = {"protocol_version": "1.0.0", "maximum_nuclear_coverage": detector.maximum_nuclear_coverage,
                                                  "minimum_parent_purity": 0.9, "policy": "reject_whole_instance_keep_raw_artifact"}
            binding["nuclear_candidate_exclusions"] = nuclear_exclusions
            binding["indeterminate_parent_reasons"] = {}
            for exclusion in nuclear_exclusions:
                parent = exclusion["parent_id"]
                if binding["nucleolar_states"].get(parent) == "no_candidate":
                    binding["nucleolar_states"][parent] = "indeterminate"
                    binding["indeterminate_parent_reasons"][str(parent)] = "nuclear_scale_candidates_only"
        if isinstance(detector, NclParentCellposeDetectorSpec):
            for parent, reason in receipt.get("indeterminate_parents", {}).items():
                binding["nucleolar_states"][int(parent)] = "indeterminate"
            binding.setdefault("indeterminate_parent_reasons", {}).update(receipt.get("indeterminate_parents", {}))
            binding["parent_conditioning"] = receipt.get("parent_conditioning", [])
            binding["signal_review_candidates"] = receipt.get("signal_review_candidates", [])
        if nuclei is not None and receipt.get("normalization", {}).get("constant_signal"):
            binding["nucleolar_states"] = {parent: "indeterminate" for parent in binding["nucleolar_states"]}
            binding["indeterminate_reason"] = "constant_detection_signal"
        np.save(output_dir / "cellpose-labels.npy", labels, allow_pickle=False)
        info = {"engine": detector.engine, "nucleolar_detector_protocol_version": detector.protocol_version,
                "model": detector.model, "model_sha256": MODEL_SHA256,
                "parameters": detector.model_dump(mode="json"), "runtime": receipt,
                "detection_preprocessing": receipt.get("preprocessing", {"algorithm": "none"}),
                "source_sha256": _array_hash(image, image.dtype.newbyteorder("<").str),
                "mask_sha256": _array_hash(labels, "<u4"),
                "raw_mask_sha256": _array_hash(raw, "<u4"), "raw_mask_artifact": raw_path.name,
                "measurement_pixels": "original, unchanged", "coordinate_transform": receipt["coordinate_transform"],
                "input_dtype": str(image.dtype), "input_shape": list(image.shape),
                "mask_meaning": "Cellpose-SAM instance candidates, requiring researcher review", **binding}
        if nuclei is not None:
            info["nucleolar_definition_source"] = "marker"
        return labels, info
    except subprocess.TimeoutExpired as error:
        raise ValueError("cellpose_inference_timeout") from error
    except (OSError, json.JSONDecodeError) as error:
        raise ValueError("cellpose_inference_failed") from error
    finally:
        # Original research pixels/paths exist only within the private attempt.
        # Remove transient duplicated inputs/descriptors after execution.
        source.unlink(missing_ok=True)
        parent_path.unlink(missing_ok=True)
        request_path.unlink(missing_ok=True)

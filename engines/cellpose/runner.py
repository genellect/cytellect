"""Fixed 3.12 isolated Cellpose runtime. No network, GUI, or submitted Python."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import socket
import sys
from pathlib import Path


def offline_socket(*_args, **_kwargs):
    raise RuntimeError("cellpose_network_forbidden")


def verify_assets(lock: dict):
    if lock.get("schema") != "cytellect-cellpose-runtime/1" or lock.get("python") != "3.12":
        raise RuntimeError("cellpose_adapter_integrity_failed")
    if (lock["model"]["id"] != "cpsam_v2" or lock["model"]["size"] != 1233586851
            or lock["model"]["sha256"] != "0f1cc3f7ecdd8a037a57c6c48d9d8921391be4cbce3fa9f13c3e3a2e1253c667"):
        raise RuntimeError("cellpose_model_integrity_failed")
    for name, key in (("runner.py", "runner_sha256"), ("requirements.lock", "requirements_sha256")):
        with Path(__file__).with_name(name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != lock[key]:
                raise RuntimeError("cellpose_adapter_integrity_failed")


def prepare_detection_input(image, parameters: dict):
    """Detection-copy transform; never receive or modify the adopted nuclei."""
    if parameters["engine"] == "cellpose-sam" and parameters["protocol_version"] == "4.0.0":
        return image, {"algorithm": "none", "protocol_version": "4.0.0"}
    if parameters["engine"] != "cellpose-sam-ncl" or parameters["protocol_version"] != "4.1.0":
        raise RuntimeError("cellpose_protocol_invalid")
    import numpy as np
    from scipy import ndimage as ndi

    sigma, radius = parameters["smoothing_sigma_px"], parameters["background_radius_px"]
    coordinates = np.arange(-radius, radius + 1)
    footprint = coordinates[:, None] ** 2 + coordinates[None, :] ** 2 <= radius ** 2
    smoothed = ndi.gaussian_filter(image.astype(np.float32), sigma, mode="reflect")
    background = ndi.grey_opening(smoothed, footprint=footprint, mode="reflect")
    detection = np.maximum(smoothed - background, 0)
    return detection, {"algorithm": "ncl_local_background_removal", "protocol_version": "4.1.0",
                       "smoothing_sigma_px": sigma, "background_radius_px": radius,
                       "background_footprint": "euclidean_disk", "boundary_mode": "reflect",
                       "subtraction": "maximum(smoothed-grey_opening(smoothed),0)",
                       "detection_dtype": "float32", "parameter_units": "original_image_pixels",
                       "nuclear_mask_applied_before_inference": False}


def normalize_detection_channels(detection, parameters: dict):
    import numpy as np

    percentiles = [parameters["normalization_percentile_low"], parameters["normalization_percentile_high"]]
    if parameters["engine"] in ("cellpose-sam-ncl", "cellpose-sam-ncl-parent"):
        from cellpose import transforms

        # Call the pinned official transform directly, retaining float32 in-place
        # arithmetic, its 1e-3 cutoff, and its large-image percentile sampling.
        channels = np.stack([detection, np.zeros_like(detection), np.zeros_like(detection)], axis=-1)
        source = detection
        stride = [1, 1]
        if detection.size > 224 ** 3:
            stride = [max(1, size // 224) for size in detection.shape]
            source = detection[::stride[0], ::stride[1]]
        low, high = np.percentile(source, percentiles)
        channels = transforms.normalize_img(channels, normalize=True, percentile=tuple(percentiles))
        normalization = {"percentiles": percentiles, "constant_signal": bool(high - low <= 1e-3),
                         "detection_low": float(low), "detection_high": float(high),
                         "source": "ncl_local_background_removed_detection_copy",
                         "implementation": "cellpose.transforms.normalize_img",
                         "percentile_sampling_stride": stride}
    else:
        # Compatibility protocol: preserve its exact original manual arithmetic.
        low, high = np.percentile(detection, percentiles)
        normalized = np.zeros(detection.shape, dtype=np.float32)
        if high > low:
            normalized = (detection.astype(np.float32) - low) / (high - low)
        channels = np.stack([normalized, np.zeros_like(normalized), np.zeros_like(normalized)], axis=-1)
        normalization = {"percentiles": percentiles, "constant_signal": bool(high <= low),
                         "original_low": float(low), "original_high": float(high)}
    return channels, normalization


def parent_conditioned_inference(image, nuclei, parameters, network):
    """Smooth the original plane first, then condition independent parent crops.

    No original-value mutation, outside-nucleus background, fixed image-size
    downscale, or whole-nucleus fallback. Raw candidates retain original IDs.
    """
    import numpy as np
    from scipy import ndimage as ndi

    p = parameters
    if (nuclei.shape != image.shape or nuclei.dtype.kind not in "iu"
            or (nuclei < 0).any() or int(nuclei.max()) >= 2 ** 24):
        raise RuntimeError("cellpose_parent_shape_invalid")
    smoothed = ndi.gaussian_filter(image.astype(np.float32), p["smoothing_sigma_px"], mode="reflect")
    active = nuclei > 0
    # Robust field noise measured from original-minus-smoothed residuals in the
    # lower nuclear signal range. Half an input code unit is the quantization floor.
    noise = 0.5
    if active.any():
        background = active & (smoothed <= np.percentile(smoothed[active], p["parent_background_percentile"]))
        residual = (image.astype(np.float32) - smoothed)[background]
        if residual.size:
            noise = max(noise, float(1.4826 * np.median(np.abs(residual - np.median(residual)))))
    output = np.zeros(image.shape, np.uint32)
    records, review, indeterminate = [], [], {}
    next_id = 1
    boxes = ndi.find_objects(nuclei)
    for parent in (int(v) for v in np.unique(nuclei) if v):
        box = boxes[parent - 1]
        padding = p["crop_padding_px"]
        y0, y1 = max(0, box[0].start - padding), min(image.shape[0], box[0].stop + padding)
        x0, x1 = max(0, box[1].start - padding), min(image.shape[1], box[1].stop + padding)
        scope = nuclei[y0:y1, x0:x1] == parent
        original = image[y0:y1, x0:x1]
        values = smoothed[y0:y1, x0:x1][scope]
        baseline = float(np.percentile(values, p["parent_background_percentile"]))
        excess = float(np.percentile(values, p["normalization_percentile_high"]) - baseline)
        diameter = p["diameter_px"] or float(2 * np.sqrt(scope.sum() / np.pi) * p["nuclear_diameter_fraction"])
        record = {"parent_id": parent, "crop_yxyx": [y0, y1, x0, x1], "background": baseline,
                  "diameter_px": diameter, "noise": noise, "signal_snr": excess / noise}
        records.append(record)
        if excess < p["minimum_contrast_snr"] * noise:
            indeterminate[str(parent)] = "insufficient_ncl_signal"
            continue
        detection = np.maximum(smoothed[y0:y1, x0:x1] - baseline, 0)
        detection[~scope] = 0  # after smoothing; never create a pre-smoothing boundary
        channels, normalization = normalize_detection_channels(detection, p)
        record["normalization"] = normalization
        if normalization["constant_signal"]:
            indeterminate[str(parent)] = "constant_detection_signal"
            continue
        result = network.eval(channels, channel_axis=-1, normalize=False, diameter=diameter,
                              resample=True, flow_threshold=p["flow_threshold"], cellprob_threshold=p["cellprob_threshold"],
                              min_size=p["minimum_area_px"], max_size_fraction=p["maximum_size_fraction"],
                              batch_size=p["batch_size"], niter=p["iterations"], do_3D=False, augment=False, tile_overlap=0.1)
        labels = np.asarray(result[0])
        if labels.shape != scope.shape or labels.dtype.kind not in "iu" or (labels < 0).any():
            raise RuntimeError("cellpose_output_invalid")
        record["model_candidate_count"] = int(np.count_nonzero(np.unique(labels)))
        for source in (int(v) for v in np.unique(labels) if v):
            pieces, count = ndi.label(labels == source, np.ones((3, 3), bool))
            for component in range(1, count + 1):
                mask = pieces == component
                ring = ndi.binary_dilation(mask, iterations=p["local_background_radius_px"]) & ~mask & scope & (labels == 0)
                reason = None
                if int(mask.sum()) < p["minimum_area_px"]:
                    reason = "below_minimum_area"
                elif not ring.any():
                    reason = "local_background_unavailable"
                elif float(original[mask].mean()) - max(baseline, float(original[ring].mean())) < p["minimum_contrast_snr"] * noise:
                    reason = "insufficient_local_ncl_enrichment"
                if reason:
                    review.append({"parent_id": parent, "source_label_id": source, "component": component, "reason": reason})
                    continue
                # Crossing/boundary candidates are intentionally not clipped.
                # The authoritative parent binder rejects them whole.
                target = output[y0:y1, x0:x1]
                if (target[mask] != 0).any():
                    review.append({"parent_id": parent, "source_label_id": source, "component": component,
                                   "reason": "overlapping_parent_candidates"})
                    continue
                target[mask] = next_id
                next_id += 1
    return output, {"parent_conditioning": records, "indeterminate_parents": indeterminate,
                    "signal_review_candidates": review,
                    "normalization": {"implementation": "cellpose.transforms.normalize_img", "scope": "per_parent_crop"},
                    "preprocessing": {"algorithm": "ncl_parent_conditioned", "protocol_version": p["protocol_version"],
                                      "parameters": p, "smoothing_before_parent_restriction": True,
                                      "noise_estimator": "1.4826*MAD(original-smoothed),lower_nuclear_signal;floor=0.5",
                                      "diameter_source": "explicit_px_or_nuclear_equivalent_diameter_fraction",
                                      "parameter_units": "original_image_pixels"}}


def run(request_path: Path) -> dict:
    request = json.loads(request_path.read_text(encoding="utf-8"))
    lock = json.loads(Path(__file__).with_name("runtime.lock.json").read_text(encoding="utf-8"))
    verify_assets(lock)
    if sys.version_info[:2] != (3, 12):
        raise RuntimeError("cellpose_python_version_mismatch")
    versions = {name: importlib.metadata.version(name) for name in lock["packages"]}
    if versions != lock["packages"]:
        raise RuntimeError("cellpose_runtime_version_mismatch")
    model_path = Path(request["model_path"])
    model = lock["model"]
    if not model_path.is_file():
        raise RuntimeError("cellpose_model_missing")
    if model_path.stat().st_size != model["size"]:
        raise RuntimeError("cellpose_model_integrity_failed")
    with model_path.open("rb") as stream:
        if hashlib.file_digest(stream, "sha256").hexdigest() != model["sha256"]:
            raise RuntimeError("cellpose_model_integrity_failed")
    # CELLPOSE_LOCAL_MODELS_PATH must exist before importing Cellpose. Explicit
    # local paths and two network guards prevent its model fallback downloader.
    os.environ["CELLPOSE_LOCAL_MODELS_PATH"] = str(model_path.parent)
    os.environ["HF_HUB_OFFLINE"] = "1"
    socket.create_connection = offline_socket
    socket.socket.connect = offline_socket
    socket.socket.connect_ex = offline_socket
    import numpy as np
    import torch
    from cellpose import models, utils

    utils.download_url_to_file = offline_socket
    models.cache_model_path = offline_socket
    p = request["parameters"]
    image = np.load(request["input_path"], allow_pickle=False)
    if image.ndim != 2 or image.dtype not in (np.uint8, np.uint16):
        raise RuntimeError("cellpose_input_invalid")
    selection = p["compute_device"]
    has_cuda = torch.cuda.is_available()
    if selection == "cuda" and not has_cuda:
        raise RuntimeError("cellpose_gpu_unavailable")
    device = "cuda" if has_cuda and selection != "cpu" else "cpu"
    torch.set_num_threads(min(8, max(1, os.cpu_count() or 1)))
    # CPU uses float32, avoiding unsupported/slow CPU bfloat16 kernels.
    network = models.CellposeModel(pretrained_model=str(model_path),
                                  device=torch.device(device), gpu=device == "cuda",
                                  use_bfloat16=device == "cuda")
    if p["engine"] == "cellpose-sam-ncl-parent" and p["protocol_version"] in ("4.2.0", "4.2.1"):
        if "parent_path" not in request:
            raise RuntimeError("cellpose_adopted_nuclei_required")
        nuclei = np.load(request["parent_path"], allow_pickle=False)
        labels, details = parent_conditioned_inference(image, nuclei, p, network)
        np.save(request["output_path"], labels, allow_pickle=False)
        return {"status": "succeeded", "runtime_packages": versions, "device": device,
                "precision": "bfloat16" if device == "cuda" else "float32", **details,
                "input_channels": "one NCL plane conditioned within each adopted nucleus plus two zero planes",
                "coordinate_transform": {"scale_x": 1, "scale_y": 1, "resample": True,
                                         "dynamics_grid": "original image", "crop_offsets_restored": True}}
    detection, preprocessing = prepare_detection_input(image, p)
    # One explicitly selected stain, plus two zero channels. No channel order
    # inference, hidden DAPI input, display LUT, or measurement transformation.
    channels, normalization = normalize_detection_channels(detection, p)
    if not normalization["constant_signal"]:
        result = network.eval(channels, channel_axis=-1, normalize=False,
                              diameter=p["diameter_px"], resample=True,
                              flow_threshold=p["flow_threshold"],
                              cellprob_threshold=p["cellprob_threshold"],
                              min_size=p["minimum_area_px"],
                              max_size_fraction=p["maximum_size_fraction"],
                              batch_size=p["batch_size"], niter=p["iterations"],
                              do_3D=False, augment=False, tile_overlap=0.1)
        labels = np.asarray(result[0])
    else:
        labels = np.zeros(image.shape, dtype=np.uint32)
    if labels.shape != image.shape or labels.dtype.kind not in "iu" or (labels < 0).any():
        raise RuntimeError("cellpose_output_invalid")
    if int(labels.max()) > np.iinfo(np.uint32).max:
        raise RuntimeError("cellpose_output_invalid")
    np.save(request["output_path"], labels.astype(np.uint32), allow_pickle=False)
    return {"status": "succeeded", "runtime_packages": versions, "device": device,
            "precision": "bfloat16" if device == "cuda" else "float32",
            "normalization": normalization, "preprocessing": preprocessing,
            "input_channels": "one explicitly selected plane plus two zero planes",
            "coordinate_transform": {"scale_x": 1, "scale_y": 1,
                                     "resample": True, "dynamics_grid": "original image"}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("request", type=Path)
    parser.add_argument("receipt", type=Path)
    args = parser.parse_args()
    try:
        receipt = run(args.request)
    except (MemoryError, RuntimeError) as error:
        name = str(error)
        code = name if name.startswith("cellpose_") and len(name) < 80 else (
            "cellpose_memory_exhausted" if "out of memory" in name.lower() or isinstance(error, MemoryError)
            else "cellpose_inference_failed")
        receipt = {"status": "failed", "error": code}
    except (importlib.metadata.PackageNotFoundError, ModuleNotFoundError):
        receipt = {"status": "failed", "error": "cellpose_runtime_missing"}
    except Exception:
        receipt = {"status": "failed", "error": "cellpose_inference_failed"}
    args.receipt.write_text(json.dumps(receipt), encoding="utf-8")
    return 0 if receipt["status"] == "succeeded" else 1


if __name__ == "__main__":
    sys.exit(main())

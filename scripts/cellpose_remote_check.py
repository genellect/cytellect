"""Compare Cellpose through the remote service with the local runner on one image.

CI: --start-service runs engines/cellpose/server.py on this machine's CPU runtime;
the remote path must then return exactly the local labels.
Remote GPU acceptance: set CYTELLECT_CELLPOSE_REMOTE_URL (and _TOKEN) instead and
record timing and agreement. CI and shared environments use registered public
images only; a researcher's own images are checked on the PC that holds them.
The receipt holds counts and timings, never pixels or paths.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

import numpy as np
import tifffile
from cytellect_analysis import cellpose_engine as engine
from cytellect_analysis.cellpose_engine import (
    CellposeDetectorSpec,
    NclParentCellposeDetectorSpec,
    detect_cellpose,
)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def start_service() -> tuple[subprocess.Popen, str]:
    port = free_port()
    environment = {**os.environ, "CYTELLECT_CELLPOSE_RUNTIME_LOCK": "runtime.lock.json", "PYTHONDONTWRITEBYTECODE": "1"}
    process = subprocess.Popen([os.environ["CYTELLECT_CELLPOSE_PYTHON"], "-I", str(engine._assets() / "server.py"),
                                "--host", "127.0.0.1", "--port", str(port),
                                "--model", str(Path(os.environ["CYTELLECT_CELLPOSE_MODEL_DIR"]) / "cpsam_v2")],
                               env=environment, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    url = f"http://127.0.0.1:{port}"
    for _ in range(300):
        if process.poll() is not None:
            raise SystemExit("cellpose service exited: " + process.stderr.read().decode(errors="replace")[-400:])
        try:
            with urllib.request.urlopen(url + "/health", timeout=2) as response:
                if response.status == 200:
                    return process, url
        except OSError:
            time.sleep(1)
    process.kill()
    raise SystemExit("cellpose service did not start")


def nuclei_stand_in(dapi: np.ndarray) -> np.ndarray:
    """Otsu/watershed nuclei for timing the NCL protocol only; not the product's StarDist nuclei."""
    from scipy import ndimage as ndi
    from skimage import feature, filters, morphology, segmentation

    smooth = ndi.gaussian_filter(dapi.astype(np.float32), 2)
    mask = morphology.remove_small_objects(smooth > filters.threshold_otsu(smooth), max_size=200)
    distance = ndi.distance_transform_edt(mask)
    peaks = feature.peak_local_max(distance, min_distance=20, labels=ndi.label(mask)[0])
    markers = np.zeros(mask.shape, np.int32)
    markers[tuple(peaks.T)] = np.arange(1, len(peaks) + 1)
    return segmentation.watershed(-distance, markers, mask=mask).astype(np.uint32)


def detect(image, detector, nuclei, remote_url):
    environment = dict(os.environ)
    try:
        if remote_url:
            os.environ["CYTELLECT_CELLPOSE_REMOTE_URL"] = remote_url
        else:
            os.environ.pop("CYTELLECT_CELLPOSE_REMOTE_URL", None)
        with tempfile.TemporaryDirectory() as scratch:
            started = time.monotonic()
            labels, info = detect_cellpose(image, detector, Path(scratch), nuclei=nuclei)
            return labels, info, time.monotonic() - started
    finally:
        os.environ.clear()
        os.environ.update(environment)


def matched(a: np.ndarray, b: np.ndarray) -> int:
    """Objects in a with an IoU >= 0.5 partner in b (one-to-one at that threshold)."""
    count = 0
    for label in np.unique(a[a > 0]):
        region = a == label
        partners, overlap = np.unique(b[region], return_counts=True)
        for partner, inter in zip(partners, overlap):
            if partner and inter / (region.sum() + (b == partner).sum() - inter) >= 0.5:
                count += 1
                break
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", type=Path, required=True, help="Registered public image")
    parser.add_argument("--plane", type=int, default=None, help="Plane index of a multi-plane image")
    parser.add_argument("--nuclei-plane", type=int, default=None, help="NCL protocol: plane for stand-in nuclei")
    parser.add_argument("--crop", type=int, default=None)
    parser.add_argument("--start-service", action="store_true", help="Serve the local CPU runtime for comparison")
    parser.add_argument("--skip-local", action="store_true", help="Remote timing only")
    parser.add_argument("--require-identical", action="store_true")
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    data = tifffile.imread(args.image)
    image = data if args.plane is None else data[args.plane]
    nuclei = None
    detector = CellposeDetectorSpec()
    if args.nuclei_plane is not None:
        nuclei = nuclei_stand_in(data[args.nuclei_plane])
        detector = NclParentCellposeDetectorSpec()
    if args.crop:
        image = image[:args.crop, :args.crop]
        nuclei = None if nuclei is None else nuclei[:args.crop, :args.crop]
    service = None
    try:
        if args.start_service:
            service, remote_url = start_service()
        else:
            remote_url = os.environ.get("CYTELLECT_CELLPOSE_REMOTE_URL")
            if not remote_url:
                raise SystemExit("set CYTELLECT_CELLPOSE_REMOTE_URL or use --start-service")
        receipt = {"schema": "cytellect-cellpose-remote-check/1", "engine": detector.engine,
                   "protocol_version": detector.protocol_version, "shape": list(image.shape),
                   "parents": None if nuclei is None else int(len(np.unique(nuclei)) - 1)}
        remote, info, seconds = detect(image, detector, nuclei, remote_url)
        receipt["remote"] = {"objects": int(len(np.unique(remote)) - 1), "seconds": round(seconds, 1),
                             "device": info["runtime"].get("device"), "gpu": info["runtime"].get("gpu"),
                             "precision": info["runtime"].get("precision")}
        if not args.skip_local:
            local, local_info, seconds = detect(image, detector, nuclei, None)
            receipt["local"] = {"objects": int(len(np.unique(local)) - 1), "seconds": round(seconds, 1),
                                "device": local_info["runtime"].get("device")}
            receipt["identical"] = bool(np.array_equal(local, remote))
            receipt["pixel_disagreement"] = float(np.mean((local > 0) != (remote > 0)))
            receipt["local_objects_matched_iou50"] = matched(local, remote)
            receipt["remote_objects_matched_iou50"] = matched(remote, local)
    finally:
        if service is not None:
            service.terminate()
            service.wait(timeout=30)
    args.receipt.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print(json.dumps(receipt))
    if args.require_identical and not receipt.get("identical"):
        sys.exit(1)


if __name__ == "__main__":
    main()

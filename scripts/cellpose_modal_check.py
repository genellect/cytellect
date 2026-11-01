"""Verify deployed model identities with public pixels through Modal's authenticated CLI.

Runs in the deploy workflow with its existing Modal API credentials. The loopback
relay forwards only this check's fixed public image to the fixed production URL;
credentials stay inside Modal CLI and its temporary private auth cache.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import numpy as np
import tifffile
from cytellect_analysis import cellpose_engine as engine
from cytellect_analysis.engine import detect_nuclei
from cytellect_analysis.nuclear_scale import automatic_detection_max_side, estimate_nuclear_diameter
from cytellect_analysis.region_contracts import NuclearDetectorSpec

ROOT = Path(__file__).resolve().parents[1]
URL = "https://genellect--cytellect-cellpose-cellposeserver.us-east.modal.direct"
BASELINE_REF = "v0.1.0-local.21"
BASELINE_COMMIT = "3090c044fe642b989d51c1c6acca1f4778ae3ea8"


def baseline_client(folder: Path):
    folder.mkdir()
    for name in ("runtime.lock.json", "gpu.lock.json", "runner.py", "requirements.lock", "requirements-cuda.lock"):
        (folder / name).write_bytes(subprocess.check_output(
            ["git", "show", f"{BASELINE_COMMIT}:engines/cellpose/{name}"], cwd=ROOT))
    source = folder / "cellpose_engine.py"
    source.write_bytes(subprocess.check_output(
        ["git", "show", f"{BASELINE_COMMIT}:packages/analysis/src/cytellect_analysis/cellpose_engine.py"], cwd=ROOT))
    spec = importlib.util.spec_from_file_location("cytellect_analysis.release_21_cellpose_engine", source)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module._assets = lambda: folder
    return module


def relay_handler(scratch: Path):
    class Relay(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # No payloads, headers, credentials or curl diagnostics in logs.

        def do_POST(self):
            size = int(self.headers.get("Content-Length", "0"))
            if self.path not in ("/", "/v1/cellpose") or not 0 < size <= 8 * 1024 * 1024:
                self.send_error(400)
                return
            with tempfile.TemporaryDirectory(dir=scratch) as temporary:
                request, response = Path(temporary) / "request.npz", Path(temporary) / "response.npz"
                request.write_bytes(self.rfile.read(size))
                try:
                    result = subprocess.run(
                        ["modal", "curl", "--silent", "--max-time", "1800", "--request", "POST",
                         "--header", "Content-Type: application/octet-stream", "--data-binary", f"@{request}",
                         "--output", str(response), "--write-out", "%{http_code}", URL + "/v1/cellpose"],
                        capture_output=True, timeout=1810, check=False)
                    status = result.stdout.decode().strip()
                    if result.returncode or len(status) != 3 or not status.isdigit():
                        self.send_error(502)
                        return
                    body = response.read_bytes()
                    self.send_response(int(status))
                    self.send_header("Content-Type", "application/octet-stream")
                    self.send_header("Content-Length", str(len(body)))
                    self.end_headers()
                    self.wfile.write(body)
                except (OSError, subprocess.TimeoutExpired):
                    self.send_error(502)
    return Relay


def verify(scratch: Path, receipt_path: Path):
    manifest = json.loads((ROOT / "fixtures/public/nucleolar/manifest.json").read_text())
    image_path = scratch / "public.tiff"
    with urllib.request.urlopen(manifest["download_url"], timeout=120) as response:
        image_path.write_bytes(response.read(manifest["bytes"] + 1))
    assert image_path.stat().st_size == manifest["bytes"]
    assert hashlib.sha256(image_path.read_bytes()).hexdigest() == manifest["sha256"]
    pixels = tifffile.imread(image_path)
    mapping = manifest["schema"]["channel_map"]
    image, dapi = (pixels[mapping[key], :512, :512] for key in ("ncl", "dapi"))
    scale = estimate_nuclear_diameter(dapi)
    nuclei, nuclear_info = detect_nuclei(
        dapi, NuclearDetectorSpec(), scratch / "nuclei", os.environ["CYTELLECT_FIJI_EXECUTABLE"],
        detection_max_side=automatic_detection_max_side(dapi.shape, scale["diameter_px"]))
    assert nuclei.shape == image.shape and np.any(nuclei)
    old = baseline_client(scratch / "baseline-client")
    lock = json.loads((ROOT / "engines/cellpose/gpu.lock.json").read_text())
    records = []
    first = None
    for client, model in ((old, "cpsam_v2"), (engine, "ncl-r1-step0375"),
                          (engine, "ncl-r1-step0750"), (old, "cpsam_v2")):
        sha = engine.MODEL_SHA256 if model == "cpsam_v2" else engine.NCL_MODEL_HASHES[model]
        detector = client.NclParentCellposeDetectorSpec(model=model, model_sha256=sha)
        started = time.monotonic()
        labels, info = client.detect_cellpose(image, detector, scratch / f"inference-{len(records)}", nuclei=nuclei)
        runtime = info["runtime"]
        assert runtime["device"] == "cuda" and runtime["precision"] == "float32"
        assert runtime["service"]["model_sha256"] == sha
        if model == "cpsam_v2":
            assert runtime["service"]["runner_sha256"] == lock["baseline_runner_sha256"]
            if first is None:
                first = labels.copy()
            else:
                assert np.array_equal(first, labels), "baseline changed after model switching"
        else:
            assert runtime["model_load"] == "strict_state_dict"
            assert runtime["model_identity"]["id"] == model
            assert runtime["service"]["runner_sha256"] == lock["runner_sha256"]
        record = {"client": BASELINE_REF if client is old else "current", "model": model,
                  "baseline_source_commit": BASELINE_COMMIT if client is old else None,
                  "model_sha256": sha, "runner_sha256": runtime["service"]["runner_sha256"],
                  "model_load": runtime.get("model_load", "pinned_cellpose_loader"), "gpu": runtime["gpu"],
                  "seconds": round(time.monotonic() - started, 2),
                  "objects": int(len(np.unique(labels[labels > 0]))),
                  "mask_sha256": hashlib.sha256(labels.tobytes()).hexdigest()}
        records.append(record)
        print(json.dumps(record), flush=True)
        receipt_path.write_text(json.dumps({"source": manifest["source"], "source_sha256": manifest["sha256"],
            "crop": [0, 0, 512, 512], "parent_detector": "product StarDist 2D, automatic nuclear scale",
            "parent_model_sha256": nuclear_info["model_sha256"], "parents": int(len(np.unique(nuclei[nuclei > 0]))),
            "scope": "deployment execution; not detection accuracy", "checks": records,
            "complete": len(records) == 4}, indent=2))


def client_environment(relay_url: str) -> dict[str, str]:
    # Only the current, reviewed relay process receives Modal's API credentials.
    # The immutable baseline client runs in a child without these variables.
    environment = {key: value for key, value in os.environ.items() if not key.startswith("MODAL_")}
    environment["CYTELLECT_CELLPOSE_REMOTE_URL"] = relay_url
    environment.pop("CYTELLECT_CELLPOSE_REMOTE_TOKEN", None)
    environment.pop("CYTELLECT_CELLPOSE_REMOTE_SECRET", None)
    environment.pop("XDG_CACHE_HOME", None)
    return environment


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--client-only", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--scratch", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.client_only:
        if args.scratch is None or any(key.startswith("MODAL_") for key in os.environ):
            parser.error("client verification requires scratch space and no Modal credentials")
        verify(args.scratch, args.receipt)
        return
    with tempfile.TemporaryDirectory(prefix="cytellect-modal-check-") as temporary:
        scratch = Path(temporary)
        client_scratch = scratch / "client"
        client_scratch.mkdir()
        os.environ["XDG_CACHE_HOME"] = str(scratch / "private-auth-cache")
        server = ThreadingHTTPServer(("127.0.0.1", 0), relay_handler(scratch))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        environment = client_environment(f"http://127.0.0.1:{server.server_port}")
        try:
            subprocess.run([sys.executable, str(Path(__file__).resolve()), "--client-only",
                            "--scratch", str(client_scratch), "--receipt", str(args.receipt.resolve())],
                           env=environment, check=True)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


if __name__ == "__main__":
    main()

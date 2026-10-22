"""HTTP service running the pinned Cellpose runner for one field at a time.

Deployed as the remote GPU inference container; CI runs the same service on CPU.
Request contents are kept only in memory for the duration of the request: no
files, no payload logging, and the response carries only labels and the receipt.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import io
import json
import os
import sys
import threading
import time
import zipfile
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

ASSETS = Path(__file__).resolve().parent
MAX_BODY_BYTES = 256 * 1024 * 1024
MAX_SIDE = 8192
ROUTES = ("/", "/v1/cellpose")


class InputError(ValueError):
    pass


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def load_runner():
    # Loaded by path: the isolated interpreter does not add this directory to sys.path.
    spec = importlib.util.spec_from_file_location("cytellect_cellpose_runner", ASSETS / "runner.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_archive(body: bytes, limit: int) -> dict:
    """Arrays from an .npz body, refusing pickles and oversized decompressed members."""
    import numpy as np

    try:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            if sum(item.file_size for item in archive.infolist()) > limit:
                raise InputError("cellpose_remote_input_too_large")
        with np.load(io.BytesIO(body), allow_pickle=False) as arrays:
            return {name: arrays[name] for name in arrays.files}
    except (zipfile.BadZipFile, OSError, ValueError) as error:
        if isinstance(error, InputError):
            raise
        raise InputError("cellpose_remote_input_invalid") from error


def write_archive(**arrays) -> bytes:
    import numpy as np

    stream = io.BytesIO()
    np.savez_compressed(stream, **arrays)
    return stream.getvalue()


class Service:
    def __init__(self, model_path: Path, require_gpu: bool):
        self.runner = load_runner()
        self.model_path = model_path
        self.require_gpu = require_gpu
        # Fails before serving if the packages, adapter or model differ from the lock.
        self.versions = self.runner.prepare_runtime(model_path)
        lock = self.runner.runtime_lock()
        self.identity = {"runner_sha256": digest(ASSETS / "runner.py"), "server_sha256": digest(Path(__file__)),
                         "requirements_sha256": lock["requirements_sha256"], "model_sha256": lock["model"]["sha256"]}
        self.guard = threading.Lock()

    def infer(self, body: bytes) -> bytes:
        import numpy as np

        arrays = read_archive(body, MAX_BODY_BYTES * 4)
        if not {"request", "image"} <= set(arrays) <= {"request", "image", "parent"}:
            raise InputError("cellpose_remote_input_invalid")
        try:
            request = json.loads(arrays["request"].tobytes().decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise InputError("cellpose_remote_input_invalid") from error
        image, parent = arrays["image"], arrays.get("parent")
        if (not isinstance(request, dict) or set(request) != {"parameters"} or not isinstance(request["parameters"], dict)
                or image.ndim != 2 or image.dtype not in (np.uint8, np.uint16) or not image.size
                or max(image.shape) > MAX_SIDE):
            raise InputError("cellpose_remote_input_invalid")
        if parent is not None and (parent.shape != image.shape or parent.dtype.kind not in "iu"):
            raise InputError("cellpose_remote_input_invalid")
        parameters = request["parameters"]
        if self.require_gpu and parameters.get("compute_device") == "cpu":
            raise InputError("cellpose_remote_gpu_required")
        with self.guard:
            labels, receipt = self.runner.infer(parameters, image, parent, self.model_path, self.versions)
        receipt["service"] = self.identity
        return write_archive(labels=labels.astype(np.uint32),
                             receipt=np.frombuffer(json.dumps(receipt).encode("utf-8"), dtype=np.uint8))


def handler_for(service: Service, secret: str | None):
    class Handler(BaseHTTPRequestHandler):
        server_version = "cytellect-cellpose"
        sys_version = ""

        def reply(self, status: int, body: bytes, content_type: str = "application/json"):
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def error(self, status: int, code: str):
            self.reply(status, json.dumps({"error": code}).encode("utf-8"))

        def do_GET(self):
            if self.path.split("?")[0] == "/health":
                self.reply(200, b'{"status":"ok"}')
            else:
                self.error(404, "cellpose_remote_route_unknown")

        def do_POST(self):
            started = time.monotonic()
            if self.path.split("?")[0] not in ROUTES:
                return self.error(404, "cellpose_remote_route_unknown")
            if secret is not None and self.headers.get("X-Cytellect-Secret") != secret:
                return self.error(403, "cellpose_remote_rejected")
            try:
                length = int(self.headers.get("Content-Length", ""))
            except ValueError:
                return self.error(411, "cellpose_remote_input_invalid")
            if not 0 < length <= MAX_BODY_BYTES:
                return self.error(413, "cellpose_remote_input_too_large")
            body = self.rfile.read(length)
            try:
                result = service.infer(body)
            except InputError as error:
                return self.error(400, str(error))
            except MemoryError:
                return self.error(507, "cellpose_memory_exhausted")
            except RuntimeError as error:
                name = str(error)
                code = (name if name.startswith("cellpose_") and len(name) < 80
                        else "cellpose_memory_exhausted" if "out of memory" in name.lower() else "cellpose_inference_failed")
                return self.error(422, code)
            except Exception:
                return self.error(500, "cellpose_inference_failed")
            finally:
                body = b""
            self.reply(200, result, "application/octet-stream")
            sys.stderr.write(f"cellpose request completed in {time.monotonic() - started:.1f}s\n")

        def log_message(self, *_args):
            # Never record paths, client addresses or request contents.
            pass

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=os.environ.get("CYTELLECT_CELLPOSE_HOST", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=int(os.environ.get("CYTELLECT_CELLPOSE_PORT", "8080")))
    parser.add_argument("--model", type=Path, default=Path(os.environ.get("CYTELLECT_CELLPOSE_MODEL", "/opt/cellpose-models/cpsam_v2")))
    parser.add_argument("--require-gpu", action="store_true", default=os.environ.get("CYTELLECT_REQUIRE_GPU") == "1")
    args = parser.parse_args()
    service = Service(args.model, args.require_gpu)
    if args.require_gpu:
        import torch

        if not torch.cuda.is_available():
            raise SystemExit("cellpose_gpu_unavailable")
    secret = os.environ.get("CYTELLECT_CELLPOSE_SECRET") or None
    server = ThreadingHTTPServer((args.host, args.port), handler_for(service, secret))
    sys.stderr.write(f"cellpose service ready on port {args.port}\n")
    server.serve_forever()


if __name__ == "__main__":
    main()

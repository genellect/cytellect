"""Provision a fixed, isolated Cellpose runtime and reusable model cache.

Run only at install/build time. Inference has no package/model downloads.
The runtime and model cache must remain outside the application checkout.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path


def digest(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def provision_model(model_cache: Path, artifact: dict) -> Path:
    model_cache.mkdir(parents=True, exist_ok=True)
    target = model_cache / artifact["id"]
    if target.exists():
        if target.stat().st_size != artifact["size"] or digest(target) != artifact["sha256"]:
            raise RuntimeError("cellpose_cached_model_integrity_failed")
        return target
    # Fixed URL supplied by the repository manifest, never by a submitted job.
    partial = model_cache / (artifact["id"] + ".partial")
    try:
        for _attempt in range(4):
            offset = partial.stat().st_size if partial.exists() else 0
            request = urllib.request.Request(artifact["url"], headers={"Range": f"bytes={offset}-"} if offset else {})
            with urllib.request.urlopen(request, timeout=120) as response:
                append = offset > 0 and response.status == 206
                with partial.open("ab" if append else "wb") as stream:
                    shutil.copyfileobj(response, stream, 1024 * 1024)
            if partial.stat().st_size == artifact["size"] and digest(partial) == artifact["sha256"]:
                os.replace(partial, target)
                return target
            if partial.stat().st_size >= artifact["size"]:
                partial.unlink()
        raise RuntimeError("cellpose_download_integrity_failed")
    finally:
        partial.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--model-cache", type=Path, required=True)
    parser.add_argument("--python", default=sys.executable, help="Python 3.12 interpreter, already installed")
    parser.add_argument("--uv", default="uv")
    parser.add_argument("--model-only", action="store_true")
    parser.add_argument("--runtime-only", action="store_true",
                        help="Docker build: provision fixed packages/model independently of the job adapter")
    args = parser.parse_args()
    if args.runtime_only and os.name == "nt":
        parser.error("runtime-only is for Docker builds; Windows setup must verify the job adapter")
    repo = Path(__file__).resolve().parents[1]
    assets = repo / "engines" / "cellpose"
    destination, cache = args.destination.resolve(), args.model_cache.resolve()
    for target in (destination, cache):
        if target == repo or repo in target.parents:
            parser.error("Runtime/model binaries must be outside the checkout")
    manifest = "provisioning.lock.json" if args.runtime_only else "runtime.lock.json"
    lock = json.loads((assets / manifest).read_text(encoding="utf-8"))
    expected_schema = "cytellect-cellpose-provisioning/1" if args.runtime_only else "cytellect-cellpose-runtime/1"
    if lock.get("schema") != expected_schema:
        raise RuntimeError("cellpose_provisioning_manifest_invalid")
    if not args.runtime_only and digest(assets / "runner.py") != lock["runner_sha256"]:
        raise RuntimeError("cellpose_adapter_integrity_failed")
    if digest(assets / "requirements.lock") != lock["requirements_sha256"]:
        raise RuntimeError("cellpose_package_lock_integrity_failed")
    model = provision_model(cache, lock["model"])
    if args.model_only:
        print("Pinned Cellpose model verified", flush=True)
        return
    query = subprocess.run([args.python, "-I", "-c", "import sys;print('%d.%d'%sys.version_info[:2])"],
                           capture_output=True, text=True, check=True)
    if query.stdout.strip() != "3.12":
        parser.error("Cellpose runtime requires the pinned Python 3.12 minor version")
    executable = destination / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not destination.exists():
        if os.name == "nt":
            # Preserve the official Python venv launchers, instead of generating
            # an unsigned uv redirector that application control may reject.
            subprocess.run([args.python, "-I", "-m", "venv", "--without-pip", str(destination)], check=True)
        else:
            subprocess.run([args.uv, "venv", str(destination), "--python", args.python], check=True)
    elif not executable.is_file():
        parser.error("Destination exists and is not an isolated Python runtime")
    subprocess.run([args.uv, "pip", "sync", str(assets / "requirements.lock"),
                    "--python", str(executable), "--require-hashes", "--torch-backend", "cpu"], check=True)
    with tempfile.TemporaryDirectory(prefix="cytellect-cellpose-verify-", dir=destination.parent) as temporary:
        script = Path(temporary) / "verify.py"
        script.write_text("import importlib.metadata,json; print(json.dumps({name:importlib.metadata.version(name) "
                          f"for name in {list(lock['packages'])!r}" + "}))", encoding="utf-8")
        installed = subprocess.run([str(executable), "-I", str(script)], capture_output=True, text=True, check=True)
        if json.loads(installed.stdout) != lock["packages"]:
            raise RuntimeError("cellpose_runtime_version_mismatch")
    receipt = {"schema": lock["schema"], "python": lock["python"], "packages": lock["packages"],
               "model_sha256": lock["model"]["sha256"], "model_size": model.stat().st_size,
               "requirements_sha256": lock["requirements_sha256"]}
    if not args.runtime_only:
        receipt["runner_sha256"] = lock["runner_sha256"]
    (destination / "cytellect-runtime.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("Pinned isolated Cellpose runtime and reusable model verified", flush=True)


if __name__ == "__main__":
    main()

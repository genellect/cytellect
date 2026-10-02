"""Install fixed public Fiji artifacts at build/setup time, outside the checkout.

Usage: python scripts/fiji_setup.py /opt/fiji --platform linux-x64
The destination must not exist. Downloads happen only here, never in a job.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import tempfile
import urllib.request
import zipfile
from pathlib import Path


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def download(url: str, target: Path, expected: str) -> None:
    # Some proxies end large streaming responses early without a read exception.
    # Always check the complete byte count/hash; resume verified HTTP ranges only.
    for attempt in range(4):
        offset = target.stat().st_size if target.exists() else 0
        request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
        with urllib.request.urlopen(request, timeout=120) as response:
            append = offset > 0 and response.status == 206
            with target.open("ab" if append else "wb") as stream:
                shutil.copyfileobj(response, stream, 1024 * 1024)
        received = sha(target)
        if received == expected:
            return
        print("Incomplete or mismatched artifact; retry", attempt + 1, "bytes", target.stat().st_size, flush=True)
        # A complete but incorrect payload must be fetched from byte zero.
        with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as response:
            size = int(response.headers.get("Content-Length", "0"))
        if size and target.stat().st_size >= size:
            target.unlink()
    raise RuntimeError("Downloaded artifact SHA-256 mismatch after retries")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--platform", choices=("linux-x64", "windows-x64"),
                        default="windows-x64" if platform.system() == "Windows" else "linux-x64")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    if destination == repo or repo in destination.parents:
        parser.error("Fiji binaries must be outside the checkout")
    if destination.exists():
        parser.error("Destination exists; choose a new directory (existing installations are never modified)")
    lock = json.loads((repo / "engines/fiji/runtime.lock.json").read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cytellect-fiji-", dir=destination.parent) as temporary:
        stage = Path(temporary)
        archive = stage / "distribution.zip"
        item = lock["fiji"][args.platform]
        print("Downloading pinned Fiji distribution", flush=True)
        download(item["url"], archive, item["sha256"])
        unpack = stage / "unpacked"
        unpack.mkdir()
        with zipfile.ZipFile(archive) as bundle:
            for entry in bundle.infolist():
                target = (unpack / entry.filename).resolve()
                if unpack not in target.parents:
                    raise RuntimeError("Unsafe archive path")
                if stat.S_ISLNK(entry.external_attr >> 16):
                    # Resolve in a second pass after real targets are extracted.
                    continue
                bundle.extract(entry, unpack)
                permissions = (entry.external_attr >> 16) & 0o777
                if permissions and target.is_file():
                    target.chmod(permissions)
            for entry in bundle.infolist():
                if not stat.S_ISLNK(entry.external_attr >> 16):
                    continue
                target = (unpack / entry.filename).resolve()
                link = bundle.read(entry).decode("utf-8")
                resolved = (target.parent / link).resolve()
                if Path(link).is_absolute() or unpack not in resolved.parents:
                    raise RuntimeError("Unsafe symlink in Fiji distribution")
                target.parent.mkdir(parents=True, exist_ok=True)
                os.symlink(link, target, target_is_directory=resolved.is_dir())
        roots = [p for p in unpack.rglob("jars") if (p.parent / "plugins").is_dir()]
        if len(roots) != 1:
            raise RuntimeError("Unexpected Fiji archive structure")
        runtime = roots[0].parent
        for plugin in lock["plugins"]:
            print("Verifying plugin:", plugin["path"], flush=True)
            target = runtime / plugin["path"]
            target.parent.mkdir(parents=True, exist_ok=True)
            # Remove only alternate versions of the same explicitly pinned module.
            stem = target.name.rsplit("-", 1)[0]
            for previous in target.parent.glob(stem + "-*.jar"):
                if re.match(re.escape(stem) + r"-[0-9]", previous.name):
                    previous.unlink()
            download(plugin["url"], target, plugin["sha256"])
        model = lock["model"]
        with zipfile.ZipFile(runtime / model["container"]) as jar:
            if hashlib.sha256(jar.read(model["member"])).hexdigest() != model["sha256"]:
                raise RuntimeError("Embedded model SHA-256 mismatch")
        inventory = []
        for artifact in sorted(runtime.rglob("*.jar")):
            inventory.append({"path": artifact.relative_to(runtime).as_posix(), "sha256": sha(artifact)})
        for java in sorted((runtime / "java").glob("**/bin/java*")):
            if java.is_file():
                inventory.append({"path": java.relative_to(runtime).as_posix(), "sha256": sha(java)})
        provenance = {"platform": args.platform, "distribution": item, "artifacts": inventory,
                      "model": model, "lock_sha256": sha(repo / "engines/fiji/runtime.lock.json")}
        (runtime / "cytellect-runtime.json").write_text(json.dumps(provenance, indent=2) + "\n")
        shutil.copy2(repo / "engines/fiji/runtime.lock.json", runtime / "cytellect-lock.json")
        shutil.move(str(runtime), destination)
    print("Fiji installed and hash-checked. Set CYTELLECT_FIJI_EXECUTABLE to", destination)
    print("Run the marked integration tests; installation alone is not validation.")


if __name__ == "__main__":
    main()

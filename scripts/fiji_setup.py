"""Install fixed public Fiji artifacts at build/setup time, outside the checkout.

Usage: python scripts/fiji_setup.py /opt/fiji --platform linux-x64
The destination must not exist. Downloads happen only here, never in a job.
With --offline-dir, every artifact is copied from that directory, where each file is
named by its SHA-256 (the Windows installer's bundled copy); nothing is downloaded.
With --cache-dir, verified downloads are kept in that directory under the same names and
reused on the next setup (CI keeps it between runs); every reused copy is hash-checked again.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import http.client
import json
import os
import platform
import re
import shutil
import stat
import tempfile
import time
import urllib.error
import urllib.request
import zipfile
from pathlib import Path


def sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


# Rate limits, gateway errors and dropped connections are retried with backoff;
# any other HTTP status stops setup.
TRANSIENT_HTTP = frozenset({408, 425, 429, 500, 502, 503, 504})
TRANSIENT_ERRORS = (urllib.error.URLError, http.client.HTTPException, ConnectionError, TimeoutError)


def transient(error: Exception) -> tuple[str, str]:
    """The reason and Retry-After of a transient failure; any other HTTP status is raised."""
    if isinstance(error, urllib.error.HTTPError):
        if error.code not in TRANSIENT_HTTP:
            raise error
        return f"HTTP {error.code}", error.headers.get("Retry-After", "")
    return type(error).__name__, ""


def transfer(url: str, target: Path) -> tuple[str, str] | None:
    """Write one response to target, resuming a partial file; (reason, Retry-After) after a transient failure."""
    offset = target.stat().st_size if target.exists() else 0
    request = urllib.request.Request(url, headers={"Range": f"bytes={offset}-"} if offset else {})
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            append = offset > 0 and response.status == 206
            with target.open("ab" if append else "wb") as stream:
                shutil.copyfileobj(response, stream, 1024 * 1024)
        return None
    except urllib.error.HTTPError as error:
        if error.code == 416 and offset:
            # The kept bytes already reach the end of the resource, so they are wrong: start from byte zero.
            target.unlink()
            return transfer(url, target)
        return transient(error)
    except TRANSIENT_ERRORS as error:
        return transient(error)


def copy_offline(directory: Path, target: Path, expected: str) -> None:
    """Copy one bundled artifact named by its digest; a missing or altered copy stops setup."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("offline_artifact_digest_invalid")
    source = directory / expected
    if source.is_symlink() or not source.is_file():
        raise RuntimeError("offline_artifact_missing")
    shutil.copyfile(source, target)
    if sha(target) != expected:
        target.unlink()
        raise RuntimeError("offline_artifact_hash_mismatch")


def copy_cached(cache: Path, target: Path, expected: str) -> bool:
    """Use a cached copy only if it still has the pinned digest; a stale copy is discarded."""
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise RuntimeError("cached_artifact_digest_invalid")
    source = cache / expected
    try:
        if source.is_symlink() or not source.is_file():
            return False
        shutil.copyfile(source, target)
        if sha(target) == expected:
            print("Reused verified download from the cache", flush=True)
            return True
        source.unlink()
    except OSError as error:
        # The cache only saves time; an unreadable or undeletable copy falls back to downloading.
        print("Download cache not used;", type(error).__name__, flush=True)
    target.unlink(missing_ok=True)
    return False


def store_cached(cache: Path, target: Path, expected: str) -> None:
    """Keep a verified download; the cache only saves time, so a failure to write it is a warning."""
    partial = cache / f".{expected}.partial"
    try:
        cache.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(target, partial)
        os.replace(partial, cache / expected)
    except OSError as error:
        with contextlib.suppress(OSError):
            partial.unlink(missing_ok=True)
        print("Download cache not updated;", type(error).__name__, flush=True)


def download(url: str, target: Path, expected: str, offline: Path | None = None, cache: Path | None = None) -> None:
    if offline is not None:
        copy_offline(offline, target, expected)
        return
    if cache is not None and copy_cached(cache, target, expected):
        return
    # Some proxies end large streaming responses early without a read exception.
    # Always check the complete byte count/hash; resume verified HTTP ranges only.
    failure, retry = "SHA-256 mismatch", None
    for attempt in range(6):
        if retry is not None:
            # Wait only before another attempt, never after the last one.
            failure, wait = retry
            delay = min(int(wait), 120) if wait.isdigit() else min(5 * 2 ** (attempt - 1), 60)
            print("Transient download failure;", failure, "; retry in", delay, "s", flush=True)
            time.sleep(delay)
        retry = transfer(url, target)
        if retry is not None:
            continue
        received = sha(target)
        if received == expected:
            if cache is not None:
                store_cached(cache, target, expected)
            return
        failure = "SHA-256 mismatch"
        print("Incomplete or mismatched artifact; retry", attempt + 1, "bytes", target.stat().st_size, flush=True)
        # A complete but incorrect payload must be fetched from byte zero.
        try:
            with urllib.request.urlopen(urllib.request.Request(url, method="HEAD"), timeout=30) as response:
                size = int(response.headers.get("Content-Length", "0"))
        except TRANSIENT_ERRORS as error:
            # The size is unknown: keep the bytes so the next attempt resumes them (416 resets a full copy).
            retry = transient(error)
            continue
        if size and target.stat().st_size >= size:
            target.unlink()
    if retry is not None:
        failure = retry[0]
    # Name the last failure: a rate limit that outlasts the retries is not a corrupted artifact.
    raise RuntimeError(f"Download failed after retries (last: {failure}): {url}")


def verify_existing_runtime(expected_runtime: Path, destination: Path, output: Path) -> None:
    """Only a full match to newly reconstructed fixed inputs proves old ownership."""
    from cytellect_api.local_storage import inventory

    expected = inventory(expected_runtime.parent, expected_runtime.name)
    actual = destination.absolute()
    if inventory(actual.parent, actual.name) != expected:
        raise RuntimeError("storage_runtime_unverified")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(expected), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--scratch-root", type=Path, help="Installer-owned temporary directory")
    parser.add_argument("--verify-existing", action="store_true", help="Compare an old runtime with newly verified fixed inputs")
    parser.add_argument("--inventory-output", type=Path, help="Write the verified public runtime inventory")
    parser.add_argument("--platform", choices=("linux-x64", "windows-x64"),
                        default="windows-x64" if platform.system() == "Windows" else "linux-x64")
    parser.add_argument("--offline-dir", type=Path,
                        help="Directory of bundled artifacts named by SHA-256; disables downloads")
    parser.add_argument("--cache-dir", type=Path,
                        help="Keep verified downloads here, named by SHA-256, and reuse them after a new hash check")
    args = parser.parse_args()
    offline = args.offline_dir.resolve() if args.offline_dir else None
    if offline is not None and not offline.is_dir():
        parser.error("Offline artifact directory is missing")
    if offline is not None and args.cache_dir is not None:
        parser.error("--offline-dir and --cache-dir cannot be combined")
    cache = args.cache_dir.resolve() if args.cache_dir else None
    repo = Path(__file__).resolve().parents[1]
    destination = args.destination.resolve()
    if destination == repo or repo in destination.parents:
        parser.error("Fiji binaries must be outside the checkout")
    if destination.exists() and not args.verify_existing:
        parser.error("Destination exists; choose a new directory (existing installations are never modified)")
    if args.verify_existing and (not destination.is_dir() or args.inventory_output is None):
        parser.error("Existing-runtime verification needs a directory and an inventory output")
    lock = json.loads((repo / "engines/fiji/runtime.lock.json").read_text())
    destination.parent.mkdir(parents=True, exist_ok=True)
    scratch = args.scratch_root.resolve() if args.scratch_root else destination.parent
    scratch.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="cytellect-fiji-", dir=scratch) as temporary:
        stage = Path(temporary)
        archive = stage / "distribution.zip"
        item = lock["fiji"][args.platform]
        print("Copying bundled Fiji distribution" if offline else "Downloading pinned Fiji distribution", flush=True)
        download(item["url"], archive, item["sha256"], offline, cache)
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
            download(plugin["url"], target, plugin["sha256"], offline, cache)
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
        if args.verify_existing:
            verify_existing_runtime(runtime, args.destination, args.inventory_output)
        else:
            shutil.move(str(runtime), destination)
    if args.verify_existing:
        print("Existing Fiji matches the complete pinned input inventory.")
    else:
        print("Fiji installed and hash-checked. Set CYTELLECT_FIJI_EXECUTABLE to", destination)
    print("Run the marked integration tests; installation alone is not validation.")


if __name__ == "__main__":
    main()

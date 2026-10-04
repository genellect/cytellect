"""Conservative storage collection after a successful explicit Windows setup.

Only exact, previously recorded installation trees are eligible. Research data,
unknown installations, redirected paths and running applications are never owned
by this collector. An unavailable process inventory disables deletion.
"""
from __future__ import annotations

import argparse
import base64
import contextlib
import csv
import ctypes
import hashlib
import json
import os
import re
import stat
import sys
import tempfile
from pathlib import Path
from typing import Any

import psutil

SCHEMA = "cytellect-setup-storage/1"
APP = re.compile(r"apps/\d+\.\d+\.\d+(?:-[a-z0-9.]+)?-[a-f0-9]{12}\Z")
RUNTIME = re.compile(r"(?:runtimes/(?:fiji-[a-f0-9]{16}|python-[a-z0-9.-]+)|tools/uv-[0-9.]+)\Z")
CACHE = re.compile(r"setup-cache/(?:python-[a-f0-9]{64}|uv-[0-9.]+)\.zip\Z")


def child(root: Path, relative: str) -> Path:
    if not relative or "\\" in relative or ":" in relative:
        raise ValueError("unsafe_storage_path")
    parts = relative.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError("unsafe_storage_path")
    path = root.joinpath(*parts)
    for part in [*root.parents, root, *[root.joinpath(*parts[:i]) for i in range(1, len(parts) + 1)]]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("redirected_storage_path")
    if not path.resolve().is_relative_to(root.resolve()) or path == root:
        raise ValueError("unsafe_storage_path")
    return path


def inventory(root: Path, relative: str) -> dict[str, Any]:
    target = child(root, relative)
    if not target.is_dir():
        raise ValueError("missing_storage_directory")
    files: dict[str, str] = {}
    directories = []
    size = 0
    for directory, names, leaves in os.walk(target, followlinks=False):
        for name in sorted(names + leaves):
            path = Path(directory) / name
            safe = child(root, path.relative_to(root).as_posix())
            if safe.is_dir():
                directories.append(safe.relative_to(target).as_posix())
            elif safe.is_file():
                with safe.open("rb") as handle:
                    files[safe.relative_to(target).as_posix()] = hashlib.file_digest(handle, "sha256").hexdigest()
                size += safe.stat().st_size
            else:
                raise ValueError("unknown_storage_entry")
    return {"files": files, "directories": sorted(directories), "bytes": size}


def declared_app_files(root: Path, relative: str, release: dict[str, Any], snapshot: dict[str, Any]) -> None:
    """A first snapshot is not ownership: establish it from release/wheel manifests."""
    app = child(root, relative)
    allowed = {"local-release.json", "setup-complete.json", ".venv/pyvenv.cfg", ".venv/.gitignore"}
    # uv pip creates this empty coordination file even in CPython-created venvs.
    if snapshot["files"].get(".venv/.lock") == hashlib.sha256(b"").hexdigest():
        allowed.add(".venv/.lock")
    allowed.update(".venv/Scripts/" + name for name in (
        "python.exe", "pythonw.exe", "activate", "activate.bat", "deactivate.bat", "Activate.ps1",
        "activate.fish", "activate.csh"))
    for entry in release["files"]:
        if snapshot["files"].get(entry["path"]) != entry["sha256"]:
            raise ValueError("storage_release_modified")
        allowed.add(entry["path"])
    site = app / ".venv/Lib/site-packages"
    records = list(site.glob("*.dist-info/RECORD")) if site.is_dir() else []
    if site.is_dir() and not records:
        raise ValueError("storage_wheel_inventory_missing")
    for record in records:
        allowed.add(record.relative_to(app).as_posix())
        with record.open(encoding="utf-8", newline="") as handle:
            for name, encoded, _ in csv.reader(handle):
                file = (site / name).resolve()
                if not file.is_relative_to(app / ".venv"):
                    raise ValueError("storage_wheel_path_invalid")
                key = file.relative_to(app).as_posix()
                child(root, relative + "/" + key)
                if not encoded and file == record:
                    continue
                algorithm, value = encoded.split("=", 1)
                if algorithm not in {"sha256", "sha384", "sha512"}:
                    raise ValueError("storage_wheel_digest_invalid")
                with file.open("rb") as content:
                    digest = hashlib.file_digest(content, algorithm).digest()
                if base64.urlsafe_b64encode(digest).decode().rstrip("=") != value:
                    raise ValueError("storage_wheel_modified")
                allowed.add(key)
    if set(snapshot["files"]) - allowed:
        raise ValueError("storage_unowned_app_files")
    known_directories = {str(Path(name).parent).replace("\\", "/") for name in allowed}
    known_directories |= {str(parent).replace("\\", "/") for name in allowed for parent in Path(name).parents}
    known_directories |= {".venv", ".venv/Include", ".venv/Lib", ".venv/Lib/site-packages", ".venv/Scripts"}
    if set(snapshot["directories"]) - known_directories:
        raise ValueError("storage_unowned_app_directories")


def persist(root: Path, ledger: dict[str, Any]) -> None:
    destination = child(root, "setup-storage.json")
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=root,
                                         prefix="setup-storage-", suffix=".tmp", delete=False) as handle:
            temporary = child(root, Path(handle.name).name)
            json.dump(ledger, handle, ensure_ascii=True, indent=2)
            handle.flush()
            os.fsync(handle.fileno())
        temporary.replace(destination)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


def owned_windows_pids() -> list[int]:
    """WTS exposes process SIDs without opening protected system processes.

    https://learn.microsoft.com/windows/win32/procthread/process-enumeration
    The installation DACL admits the current user and SYSTEM only.
    """
    if sys.platform != "win32":
        raise OSError("windows_process_inventory_required")
    from ctypes import wintypes

    class ProcessInfo(ctypes.Structure):
        _fields_ = [("session", wintypes.DWORD), ("pid", wintypes.DWORD),
                    ("name", wintypes.LPWSTR), ("sid", ctypes.c_void_p)]

    wts = ctypes.WinDLL("wtsapi32", use_last_error=True)
    adv = ctypes.WinDLL("advapi32", use_last_error=True)
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    pointer = ctypes.POINTER(ProcessInfo)()
    count = wintypes.DWORD()
    wts.WTSEnumerateProcessesW.argtypes = [wintypes.HANDLE, wintypes.DWORD, wintypes.DWORD,
                                         ctypes.POINTER(ctypes.POINTER(ProcessInfo)), ctypes.POINTER(wintypes.DWORD)]
    wts.WTSEnumerateProcessesW.restype = wintypes.BOOL
    wts.WTSFreeMemory.argtypes = [ctypes.c_void_p]
    adv.OpenProcessToken.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.POINTER(wintypes.HANDLE)]
    adv.GetTokenInformation.argtypes = [wintypes.HANDLE, ctypes.c_int, ctypes.c_void_p,
                                        wintypes.DWORD, ctypes.POINTER(wintypes.DWORD)]
    adv.EqualSid.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    adv.EqualSid.restype = wintypes.BOOL
    kernel.GetCurrentProcess.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    token = wintypes.HANDLE()
    if not adv.OpenProcessToken(kernel.GetCurrentProcess(), 8, ctypes.byref(token)):
        raise OSError("process_owner_unavailable")
    try:
        length = wintypes.DWORD()
        adv.GetTokenInformation(token, 1, None, 0, ctypes.byref(length))
        if not length.value:
            raise OSError("process_owner_unavailable")
        user = ctypes.create_string_buffer(length.value)
        if not adv.GetTokenInformation(token, 1, user, length, ctypes.byref(length)):
            raise OSError("process_owner_unavailable")
        sid = ctypes.cast(user, ctypes.POINTER(ctypes.c_void_p))[0]
        if not wts.WTSEnumerateProcessesW(None, 0, 1, ctypes.byref(pointer), ctypes.byref(count)):
            raise OSError("process_inventory_unavailable")
        try:
            # An unidentifiable interpreter could be executing a managed tree
            # under SYSTEM or another session. Never collect in that case.
            engines = {"python.exe", "pythonw.exe", "java.exe", "javaw.exe", "uv.exe",
                       "imagej-win64.exe", "powershell.exe", "pwsh.exe", "cmd.exe"}
            if any(not pointer[i].sid and (pointer[i].name or "").casefold() in engines
                   for i in range(count.value)):
                raise OSError("process_owner_unavailable")
            return [pointer[i].pid for i in range(count.value)
                    if pointer[i].sid and (adv.EqualSid(pointer[i].sid, sid)
                    or (pointer[i].name or "").casefold() in engines)]
        finally:
            wts.WTSFreeMemory(pointer)
    finally:
        kernel.CloseHandle(token)


def process_paths() -> list[str] | None:
    """Inspect our user's executable and argument paths; uncertainty keeps everything."""
    found = []
    try:
        username = psutil.Process().username()
        processes = (psutil.Process(pid) for pid in owned_windows_pids()) if os.name == "nt" else psutil.process_iter()
        for process in processes:
            if process.pid == os.getpid():
                continue
            try:
                if os.name != "nt" and process.username() != username:
                    continue
                found.extend([process.exe(), *process.cmdline()])
            except psutil.NoSuchProcess:
                continue
            except (psutil.AccessDenied, OSError):
                return None
    except (psutil.Error, OSError):
        return None
    return found


def active(root: Path, relative: str, processes: list[str]) -> bool:
    prefix = str(child(root, relative)).casefold().replace("/", "\\")
    return any(prefix in argument.casefold().replace("/", "\\") for argument in processes)


@contextlib.contextmanager
def usage_lock(root: Path):
    """Launch and collection share one OS-released installation lock."""
    path = child(root, "runtime-use.lock")
    with path.open("a+b") as stream:
        try:
            if sys.platform == "win32":
                import msvcrt
                if not path.stat().st_size:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("local_runtime_already_in_use") from exc
        yield


def installed_usage_lock():
    """Developer execution is unchanged; managed installs guard their parent root."""
    app = Path(sys.prefix).absolute().parent
    root = app.parent.parent
    if app.parent.name != "apps" or not (app / "local-release.json").is_file():
        return contextlib.nullcontext()
    child(root, app.relative_to(root).as_posix())
    return usage_lock(root)


def remove_exact(root: Path, relative: str, expected: dict[str, Any], *, interrupted: bool = False) -> int:
    """Validate absolute boundaries and every member before removing any file."""
    actual = inventory(root, relative)
    resume = (interrupted and set(actual["directories"]) <= set(expected["directories"])
              and all(expected["files"].get(name) == digest for name, digest in actual["files"].items()))
    if actual != expected and not resume:
        raise ValueError("modified_storage_directory")
    target = child(root, relative)
    # Use this one filesystem API end-to-end. Never shell-expand a deletion path.
    for name in actual["files"]:
        child(root, f"{relative}/{name}").unlink()
    for name in sorted(actual["directories"], key=lambda p: len(p.split("/")), reverse=True):
        child(root, f"{relative}/{name}").rmdir()
    target.rmdir()
    return int(actual["bytes"])


def maintain(root: Path, app: Path, created_runtimes: list[str], *, processes: list[str] | None) -> dict[str, Any]:
    root = root.absolute()
    if json.loads(child(root, "setup-root.json").read_text()) != {"product": "cytellect-local", "schema": 1}:
        raise ValueError("storage_root_not_owned")
    relative = app.absolute().relative_to(root).as_posix()
    if not APP.fullmatch(relative):
        raise ValueError("storage_app_identity")
    marker = json.loads(child(root, relative + "/setup-complete.json").read_text())
    release = json.loads(child(root, relative + "/local-release.json").read_text())
    if (Path(marker["app"]).absolute() != app.absolute() or marker["source_commit"] != release["source_commit"]
            or marker["version"] != release["version"]
            or relative != f'apps/{release["version"]}-{release["source_commit"][:12]}'):
        raise ValueError("storage_app_identity")
    references = [Path(marker["fiji"]).absolute().relative_to(root).as_posix(),
                  "runtimes/python-" + marker["python_build"]]
    if re.fullmatch(r"[0-9]+(?:\.[0-9]+)+", marker.get("uv", "")):
        references.append("tools/uv-" + marker["uv"])
    if any(not RUNTIME.fullmatch(ref) for ref in references):
        raise ValueError("storage_runtime_identity")
    for ref in references:
        child(root, ref)
    ledger_path = child(root, "setup-storage.json")
    ledger: dict[str, Any] = json.loads(ledger_path.read_text()) if ledger_path.exists() else {
        "schema": SCHEMA, "order": [], "apps": {}, "runtimes": {}, "archives": {}, "pending": []}
    if ledger.get("schema") != SCHEMA or not isinstance(ledger.get("order"), list):
        raise ValueError("storage_ledger_invalid")
    if (set(ledger["order"]) != set(ledger.get("apps", {}))
            or len(set(ledger["order"])) != len(ledger["order"])):
        raise ValueError("storage_ledger_invalid")
    for name, entry in ledger["apps"].items():
        if not APP.fullmatch(name) or any(not RUNTIME.fullmatch(ref) for ref in entry["references"]):
            raise ValueError("storage_ledger_invalid")
    if any(not RUNTIME.fullmatch(ref) for ref in ledger["runtimes"]):
        raise ValueError("storage_ledger_invalid")
    if any(not CACHE.fullmatch(ref) for ref in ledger.get("archives", {})):
        raise ValueError("storage_ledger_invalid")
    if any(not (APP.fullmatch(ref) or RUNTIME.fullmatch(ref)) for ref in ledger.get("pending", [])):
        raise ValueError("storage_ledger_invalid")
    # Previously registered trees cannot be silently re-owned after modification.
    snapshot = inventory(root, relative)
    previous = ledger["apps"].get(relative)
    if not previous:
        declared_app_files(root, relative, release, snapshot)
    if previous and previous["inventory"] != snapshot:
        raise ValueError("storage_app_modified")
    archives = []
    # Only exact digest-verified download artifacts are cache ownership evidence.
    for cache, expected in [
        (f'setup-cache/python-{marker.get("python_sha256", "")}.zip', marker.get("python_sha256")),
        (f'setup-cache/uv-{marker.get("uv", "")}.zip', marker.get("uv_sha256")),
    ]:
        if not CACHE.fullmatch(cache) or not isinstance(expected, str) or not re.fullmatch(r"[a-f0-9]{64}", expected):
            continue
        path = child(root, cache)
        if path.is_file():
            with path.open("rb") as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual == expected:
                ledger.setdefault("archives", {})[cache] = expected
                archives.append(cache)
    ledger["apps"][relative] = {"inventory": snapshot, "references": references, "archives": archives}
    ledger["order"] = [entry for entry in ledger["order"] if entry != relative] + [relative]
    for ref in created_runtimes:
        if ref not in references or ref in ledger["runtimes"]:
            raise ValueError("storage_runtime_registration")
        ledger["runtimes"][ref] = inventory(root, ref)
    keep = set(ledger["order"][-2:])
    # Persist the new successful generation BEFORE any removal. Interrupted
    # removal can leave missing old members, never an unrecorded new generation.
    persist(root, ledger)
    reclaimed = 0
    retained = []
    unverified_apps = False
    for candidate in list(ledger["order"]):
        if not APP.fullmatch(candidate):
            raise ValueError("storage_ledger_invalid")
        entry = ledger["apps"][candidate]
        if not child(root, candidate).exists() and candidate not in keep:
            del ledger["apps"][candidate]
            ledger["order"].remove(candidate)
            ledger["pending"] = [name for name in ledger.get("pending", []) if name != candidate]
            continue
        if (candidate in keep or processes is None or active(root, candidate, processes)
                or any(active(root, ref, processes) for ref in entry["references"])):
            retained.append(candidate)
            continue
        try:
            interrupted = candidate in ledger.get("pending", [])
            if not interrupted:
                if inventory(root, candidate) != entry["inventory"]:
                    raise ValueError("modified_storage_directory")
                ledger.setdefault("pending", []).append(candidate)
                persist(root, ledger)
            reclaimed += remove_exact(root, candidate, entry["inventory"], interrupted=interrupted)
        except (OSError, ValueError):
            retained.append(candidate)
            unverified_apps = True
            continue
        del ledger["apps"][candidate]
        ledger["order"].remove(candidate)
        ledger["pending"].remove(candidate)
    # Any unknown/incomplete app could refer to an old shared runtime; preserve it.
    app_root = child(root, "apps")
    unknown = unverified_apps or any("apps/" + entry.name not in ledger["apps"] for entry in app_root.iterdir())
    for name in retained:
        try:
            if inventory(root, name) != ledger["apps"][name]["inventory"]:
                unknown = True
        except (OSError, ValueError):
            unknown = True
    refs = {ref for entry in ledger["apps"].values() for ref in entry["references"]}
    for ref, snapshot in list(ledger["runtimes"].items()):
        if not RUNTIME.fullmatch(ref):
            raise ValueError("storage_ledger_invalid")
        if unknown or processes is None or ref in refs or active(root, ref, processes):
            continue
        try:
            if not child(root, ref).exists():
                del ledger["runtimes"][ref]
                ledger["pending"] = [name for name in ledger.get("pending", []) if name != ref]
                continue
            interrupted = ref in ledger.get("pending", [])
            if not interrupted:
                if inventory(root, ref) != snapshot:
                    raise ValueError("modified_storage_directory")
                ledger.setdefault("pending", []).append(ref)
                persist(root, ledger)
            reclaimed += remove_exact(root, ref, snapshot, interrupted=interrupted)
        except (OSError, ValueError):
            continue
        del ledger["runtimes"][ref]
        ledger["pending"].remove(ref)
    needed_archives = {name for entry in ledger["apps"].values() for name in entry.get("archives", [])}
    for name, expected in list(ledger.get("archives", {}).items()):
        if unknown or processes is None or name in needed_archives or active(root, name, processes):
            continue
        try:
            path = child(root, name)
            with path.open("rb") as handle:
                actual = hashlib.file_digest(handle, "sha256").hexdigest()
            if actual != expected:
                continue
            size = path.stat().st_size
            path.unlink()
            reclaimed += size
            del ledger["archives"][name]
        except (OSError, ValueError):
            continue
    persist(root, ledger)
    cache_root = child(root, "setup-cache")
    unmanaged_cache = cache_root.exists() and any(
        entry.name == "uv" or entry.suffix == ".partial"
        or (entry.suffix == ".zip" and "setup-cache/" + entry.name not in ledger.get("archives", {}))
        for entry in cache_root.iterdir())
    return {"schema": SCHEMA, "retained_apps": len(retained), "reclaimed_bytes": reclaimed,
            "unknown_apps_retained": unknown, "unmanaged_cache_retained": unmanaged_cache,
            "process_inventory_available": processes is not None}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--app", type=Path, required=True)
    parser.add_argument("--created-runtime", action="append", default=[])
    args = parser.parse_args()
    try:
        with usage_lock(args.root.absolute()):
            result = maintain(args.root, args.app, args.created_runtime, processes=process_paths())
    except ValueError as exc:
        if str(exc) != "local_runtime_already_in_use":
            raise
        result = maintain(args.root, args.app, args.created_runtime, processes=None)
    child(args.root.absolute(), "setup-storage-result.json").write_text(json.dumps(result), encoding="utf-8")


if __name__ == "__main__":
    main()

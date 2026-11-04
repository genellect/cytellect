"""Durable ownership and nonblocking recovery of private engine scratch trees."""
from __future__ import annotations

import contextlib
import json
import os
import re
import shutil
import stat
import sys
import uuid
from collections.abc import Iterator
from contextvars import ContextVar
from pathlib import Path
from typing import TextIO

SCHEMA = "cytellect-owned-scratch/1"
JOURNAL = re.compile(r"\.cytellect-scratch-([a-f0-9]{32})\.json\Z")
NAME = re.compile(r"[a-z][a-z-]{0,24}-[a-f0-9]{8}\Z")
MAX_DEFERRED_BYTES = 1024 ** 3
_scope: ContextVar[tuple[Path, int] | None] = ContextVar("engine_scratch_scope", default=None)


class ScratchCapacityExceeded(RuntimeError):
    pass


@contextlib.contextmanager
def scratch_ownership_scope(root: Path, *, max_deferred_bytes: int = MAX_DEFERRED_BYTES) -> Iterator[None]:
    if type(max_deferred_bytes) is not int or max_deferred_bytes <= 0:
        raise ValueError("scratch_capacity_invalid")
    _regular(root)
    token = _scope.set((root.absolute(), max_deferred_bytes))
    try:
        yield
    finally:
        _scope.reset(token)


def _regular(path: Path) -> None:
    for part in [*path.parents, path]:
        try:
            info = part.lstat()
        except FileNotFoundError:
            continue
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("scratch_path_redirected")


@contextlib.contextmanager
def _lock(handle: TextIO) -> Iterator[None]:
    handle.seek(0)
    if sys.platform == "win32":
        import msvcrt
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    try:
        yield
    finally:
        handle.seek(0)
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def remove_scratch(path: Path) -> None:
    _regular(path)
    if not path.exists():
        return
    # Validate all members before deleting anything. Do not follow junctions.
    for directory, names, files in os.walk(path, followlinks=False):
        for name in names + files:
            _regular(Path(directory) / name)
    shutil.rmtree(path)


def _target(journal: Path, handle: TextIO) -> Path | None:
    match = JOURNAL.fullmatch(journal.name)
    if match is None or journal.stat().st_size > 1024:
        return None
    saved = json.load(handle)
    name = saved.get("name", "")
    if (saved.get("schema") != SCHEMA or saved.get("id") != match[1]
            or not NAME.fullmatch(name) or not name.endswith("-" + match[1][:8])):
        return None
    return journal.parent / name


def _pending_bytes(root: Path) -> int:
    targets: list[Path] = []
    for parent, names, files in os.walk(root, followlinks=False):
        names[:] = [name for name in names if not (Path(parent) / name).is_symlink()
                    and not (Path(parent) / name).is_junction()]
        for name in files:
            if not JOURNAL.fullmatch(name):
                continue
            journal = Path(parent) / name
            try:
                _regular(journal)
                with journal.open("r+", encoding="ascii") as handle, _lock(handle):
                    target = _target(journal, handle)
                    if target is not None:
                        _regular(target)
                        targets.append(target)
            except (OSError, ValueError, TypeError, AttributeError):
                continue  # Live owners cannot be acquired; they are not a backlog.
    size = 0
    unique = [path for path in targets if not any(parent in targets for parent in path.parents)]
    for target in unique:
        for parent, names, files in os.walk(target, followlinks=False):
            names[:] = [name for name in names if not (Path(parent) / name).is_symlink()
                        and not (Path(parent) / name).is_junction()]
            for name in files:
                try:
                    size += (Path(parent) / name).lstat().st_size
                except OSError:
                    pass
    return size


def reap_owned_temporaries(directory: Path, *, recursive: bool = False) -> dict[str, int]:
    """Only an unlocked, valid creation journal permits removal; never wait on locks."""
    result = {"recovered": 0, "deferred": 0}
    _regular(directory)
    if not directory.is_dir():
        return result
    journals: list[Path]
    if recursive:
        journals = []
        for parent, names, files in os.walk(directory, followlinks=False):
            names[:] = [name for name in names if not (Path(parent) / name).is_symlink()
                        and not (Path(parent) / name).is_junction()]
            journals.extend(Path(parent) / name for name in files if JOURNAL.fullmatch(name))
    else:
        journals = list(directory.glob(".cytellect-scratch-*.json"))
    for journal in journals:
        try:
            _regular(journal)
            with journal.open("r+", encoding="ascii") as handle, _lock(handle):
                target = _target(journal, handle)
                if target is None:
                    continue
                remove_scratch(target)
            journal.unlink(missing_ok=True)
            result["recovered"] += 1
        except FileNotFoundError:
            continue  # An outer owned tree may already have removed its nested journal.
        except (OSError, ValueError, TypeError, AttributeError):
            result["deferred"] += 1
    return result


@contextlib.contextmanager
def claimed_scratch(directory: Path, prefix: str) -> Iterator[Path]:
    if not re.fullmatch(r"[a-z][a-z-]{0,24}-", prefix):
        raise ValueError("scratch_prefix_invalid")
    _regular(directory)
    root, limit = _scope.get() or (directory, MAX_DEFERRED_BYTES)
    if not directory.absolute().is_relative_to(root.absolute()):
        raise ValueError("scratch_scope_invalid")
    directory.mkdir(parents=True, exist_ok=True)
    reap_owned_temporaries(root, recursive=True)
    if _pending_bytes(root) >= limit:
        raise ScratchCapacityExceeded("fiji_temporary_cleanup_pending")
    identity = uuid.uuid4().hex
    target = directory / (prefix + identity[:8])
    journal = directory / f".cytellect-scratch-{identity}.json"
    if target.exists():
        raise ValueError("scratch_creation_conflict")
    # Record intent before mkdir. An OS lock proves a live owner even after Java exits.
    try:
        with journal.open("x+", encoding="ascii") as handle:
            handle.write(json.dumps({"schema": SCHEMA, "id": identity, "name": target.name}))
            handle.flush()
            os.fsync(handle.fileno())
            with _lock(handle):
                target.mkdir()
                yield target  # The caller applies its cleanup budget while holding this lock.
    finally:
        if not target.exists():
            try:
                journal.unlink(missing_ok=True)
            except OSError:
                pass  # Recovery can remove an unlocked journal with no remaining tree.

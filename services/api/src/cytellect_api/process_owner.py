"""Process identity checks, including Windows venv executable redirectors."""
from __future__ import annotations

import os
import sys
from pathlib import Path

import psutil

Identity = tuple[int, float]


def process_alive(identity: Identity) -> bool:
    try:
        process = psutil.Process(identity[0])
        return (process.is_running() and process.create_time() == identity[1]
                and process.status() != psutil.STATUS_ZOMBIE)
    except psutil.Error:
        return False


def redirector_owner() -> Identity | None:
    """Watch only a real Windows venv shim, never an ordinary launching shell.

    CPython's Windows venv executable starts a different base-Python process.
    Killing that executable does not terminate its child. Detect the executable
    mismatch and retain the shim's identity before starting application work.
    A missing shim fails closed instead of creating an already-orphaned server.
    Hardlinked uv environments execute directly and need no additional owner.
    """
    if sys.platform != "win32":
        return None
    try:
        current = psutil.Process()
        if os.path.samefile(current.exe(), sys.executable):
            return None
        parent = current.parent()
        if parent is not None:
            executable = Path(parent.exe())
            # The CLI console entry point is another waiting launch shim.
            console_entry = (executable.name.lower() == "cytellect.exe"
                             and executable.parent.resolve() == Path(sys.executable).resolve().parent)
            if os.path.samefile(executable, sys.executable) or console_entry:
                return parent.pid, parent.create_time()
    except (OSError, psutil.Error):
        pass
    raise RuntimeError("local_redirector_owner_missing")

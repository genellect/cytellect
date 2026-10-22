"""Adapters for a single-threaded interpreter without child processes (Pyodide).

The API's synchronous endpoints, dependencies, upload spools and file
responses go through ``anyio.to_thread.run_sync``. In the browser there are no
threads, so the call runs inline on the event loop instead. Results are the
same; only concurrency differs, and the showcase serializes requests anyway.
"""

from __future__ import annotations

import contextlib
import sys
import types
from collections.abc import Iterator

PYODIDE = sys.platform == "emscripten"


async def _run_inline(func, *args, abandon_on_cancel=False, cancellable=None, limiter=None):
    return func(*args)


@contextlib.contextmanager
def inline_threads() -> Iterator[None]:
    """Run anyio worker-thread calls inline for the duration of the block."""
    import anyio.to_thread

    original = anyio.to_thread.run_sync
    anyio.to_thread.run_sync = _run_inline  # type: ignore[assignment]
    try:
        yield
    finally:
        anyio.to_thread.run_sync = original  # type: ignore[assignment]


def numeric_font_weights():
    """Matplotlib < 3.11 SVG output looks numeric weights up in ``weight_dict``.

    The figure code sets the face's numeric weight (e.g. 400). Matplotlib 3.11
    (uv.lock) treats a number as itself; 3.10 (Pyodide) raises KeyError. Mapping
    each number to itself gives 3.10 the 3.11 behaviour. Returns an undo
    callable, or None when no change was needed.
    """
    import matplotlib
    from matplotlib import font_manager

    major, minor = (int(part) for part in matplotlib.__version__.split(".")[:2])
    if (major, minor) >= (3, 11):
        return None
    added = [value for value in range(1001) if value not in font_manager.weight_dict]
    for value in added:
        font_manager.weight_dict[value] = value  # type: ignore[index]

    def undo():
        for value in added:
            font_manager.weight_dict.pop(value, None)  # type: ignore[call-overload]

    return undo


class _UnavailablePsutil(types.ModuleType):
    """Import placeholder: process supervision is replaced by the inline executor."""

    def __getattr__(self, name: str):
        if name.startswith("__"):
            raise AttributeError(name)
        raise AttributeError("psutil_unavailable_in_showcase")


def ensure_psutil_importable() -> bool:
    """Let modules that import psutil at load time import under Pyodide.

    Returns True when a placeholder was installed. Any actual use fails, which
    only the replaced subprocess supervision would attempt.
    """
    try:
        import psutil  # noqa: F401
    except ImportError:
        sys.modules["psutil"] = _UnavailablePsutil("psutil")
        return True
    return False

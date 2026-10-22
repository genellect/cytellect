"""Record real detector outputs at build time and replay them in the showcase.

The four detector entry points that ``cytellect_worker.regions`` calls are
replaced under the same names. The recorder calls the real Fiji/StarDist and
Cellpose functions and stores what they returned (label arrays, engine
provenance and every file written to the engine output directory). Replay
returns exactly those recorded outputs; it never runs or approximates a
detector. A request that was not recorded fails with
``showcase_detection_not_recorded`` (see docs/showcase.md).

Record key (docs/showcase.md): SHA-256 of the UTF-8 JSON
``{"fn", "arrays", "detector", "options"}`` serialised with
``sort_keys=True`` and ``separators=(",", ":")``. An array digest is the
SHA-256 of ``dtype.str``, the JSON shape list and the C-order bytes, each
followed by a NUL separator. Output directories, executables and scratch
roots are excluded because they change from run to run.

Recording layout under ``recordings/``::

    index.json            {"version": 1, "entries": {key: entry}}
    arrays/<sha256>.npy   output arrays (content addressed, deduplicated)
    files/<sha256>        files the detector wrote to its output directory

An entry is ``{"fn", "outputs": {name: "arrays/<sha>.npy"}, "engine_info",
"files": [{"path", "file", "sha256", "bytes"}]}``. ``outputs`` holds
``labels`` for single-mask detectors and the compartment names for
``detect_compartments``.
"""
from __future__ import annotations

import copy
import hashlib
import inspect
import json
import os
import shutil
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

import numpy as np

FUNCTIONS = ("detect_nuclei", "detect_cellpose", "detect_compartments", "detect_positive_regions")
NOT_RECORDED = "showcase_detection_not_recorded"
INDEX_VERSION = 1
# Nucleolar definitions computed by pure Python/NumPy/SciPy in the shared
# analysis package. They need no Fiji or Cellpose, so replay executes them.
PYTHON_ONLY_ENGINES = frozenset({"cytellect-nucleolar-v2", "cytellect-ncl-objects"})
# Detector argument name per function, as defined by the analysis package.
_DETECTOR_ARGUMENT = {"detect_nuclei": "parameters", "detect_cellpose": "detector",
                      "detect_compartments": "parameters", "detect_positive_regions": "parameters"}

_lock = threading.RLock()
_originals: dict[str, Callable[..., Any]] = {}


class DetectionNotRecorded(ValueError):
    """Raised for any detection request outside the recorded set."""

    def __init__(self) -> None:
        super().__init__(NOT_RECORDED)


def array_digest(array: np.ndarray) -> str:
    value = np.ascontiguousarray(np.asarray(array))
    digest = hashlib.sha256()
    digest.update(value.dtype.str.encode("ascii") + b"\0")
    digest.update(json.dumps(list(value.shape)).encode("ascii") + b"\0")
    digest.update(memoryview(value).cast("B"))
    return digest.hexdigest()


def _canonical_detector(fn: str, detector: Any) -> Any:
    """Validate a detector exactly as the called function does, then dump it."""
    if detector is None:
        return None
    if hasattr(detector, "model_dump"):
        return detector.model_dump(mode="json")
    if fn == "detect_nuclei":
        from cytellect_analysis.region_contracts import NuclearDetectorSpec

        return NuclearDetectorSpec.model_validate(detector).model_dump(mode="json")
    if fn == "detect_cellpose":
        from cytellect_analysis.cellpose_engine import CellposeDetectorSpec

        return CellposeDetectorSpec.model_validate(detector).model_dump(mode="json")
    if fn == "detect_compartments":
        from cytellect_analysis.compartment_engine import NucleolarDetector
        from pydantic import TypeAdapter

        if isinstance(detector, dict) and "protocol_version" not in detector:
            detector = {"protocol_version": "1.0.0", **detector}
        return TypeAdapter(NucleolarDetector).validate_python(detector).model_dump(mode="json")
    if fn == "detect_positive_regions":
        from cytellect_analysis.signal_engine import SignalDetectorSpec

        return SignalDetectorSpec.model_validate(detector).model_dump(mode="json")
    raise ValueError("showcase_detection_function_unknown")


def record_key(fn: str, arrays: dict[str, np.ndarray], detector: Any,
               detection_max_side: int | None = None) -> str:
    """Return the documented record key for one detector call."""
    if fn not in FUNCTIONS:
        raise ValueError("showcase_detection_function_unknown")
    document = {"fn": fn, "arrays": {name: array_digest(value) for name, value in arrays.items()},
                "detector": _canonical_detector(fn, detector),
                "options": {"detection_max_side": None if detection_max_side is None else int(detection_max_side)}}
    text = json.dumps(document, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@dataclass
class _Call:
    fn: str
    key: str
    detector: Any
    output_dir: Path


def _signature(fn: str) -> inspect.Signature:
    """Bind calls against the analysis package's documented signatures."""
    from cytellect_analysis import cellpose_engine, compartment_engine, engine, signal_engine

    source: dict[str, Callable[..., Any]] = {"detect_nuclei": engine.detect_nuclei, "detect_cellpose": cellpose_engine.detect_cellpose,
              "detect_compartments": compartment_engine.detect_compartments,
              "detect_positive_regions": signal_engine.detect_positive_regions}
    return inspect.signature(source[fn])


def _describe(fn: str, args: tuple, kwargs: dict) -> _Call:
    bound = _signature(fn).bind(*args, **kwargs)
    bound.apply_defaults()
    values = bound.arguments
    arrays: dict[str, np.ndarray] = {}
    if fn == "detect_compartments":
        channels = values["channels"]
        for role in sorted(channels):
            arrays[f"channels.{role}"] = channels[role]
        arrays["nuclei"] = values["nuclei"]
    else:
        arrays["image"] = values["image"]
        if fn == "detect_cellpose" and values.get("nuclei") is not None:
            arrays["nuclei"] = values["nuclei"]
    detector = values[_DETECTOR_ARGUMENT[fn]]
    side = values.get("detection_max_side") if fn == "detect_nuclei" else None
    return _Call(fn, record_key(fn, arrays, detector, side), _canonical_detector(fn, detector),
                 Path(values["output_dir"]))


def _python_only(call: _Call) -> bool:
    return (call.fn == "detect_compartments" and isinstance(call.detector, dict)
            and call.detector.get("engine") in PYTHON_ONLY_ENGINES)


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _write_atomic(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    partial = path.with_name(path.name + ".partial")
    partial.write_bytes(data)
    os.replace(partial, path)


def _load_index(root: Path) -> dict:
    path = root / "index.json"
    if not path.is_file():
        return {"version": INDEX_VERSION, "entries": {}}
    index = json.loads(path.read_text(encoding="utf-8"))
    if index.get("version") != INDEX_VERSION or not isinstance(index.get("entries"), dict):
        raise ValueError("showcase_recordings_invalid")
    return index


def _module():
    from cytellect_worker import regions

    return regions


def _install(wrappers: dict[str, Callable[..., Any]]) -> None:
    module = _module()
    with _lock:
        for name in FUNCTIONS:
            _originals.setdefault(name, getattr(module, name))
            setattr(module, name, wrappers[name])


def uninstall() -> None:
    """Restore the real detector functions in ``cytellect_worker.regions``."""
    module = _module()
    with _lock:
        for name, original in _originals.items():
            setattr(module, name, original)
        _originals.clear()


@dataclass
class Recorder:
    root: Path
    index: dict = field(default_factory=dict)
    calls: list[dict] = field(default_factory=list)

    def _store_array(self, array: np.ndarray) -> str:
        value = np.ascontiguousarray(np.asarray(array))
        relative = f"arrays/{array_digest(value)}.npy"
        target = self.root / relative
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            partial = target.with_name(target.name + ".partial")
            with partial.open("wb") as stream:
                np.save(stream, value, allow_pickle=False)
            os.replace(partial, target)
        return relative

    def _store_files(self, directory: Path) -> list[dict]:
        records: list[dict] = []
        if not directory.is_dir():
            return records
        for path in sorted(item for item in directory.rglob("*") if item.is_file()):
            digest = _sha256_file(path)
            relative = f"files/{digest}"
            target = self.root / relative
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                partial = target.with_name(target.name + ".partial")
                shutil.copyfile(path, partial)
                os.replace(partial, target)
            records.append({"path": path.relative_to(directory).as_posix(), "file": relative,
                            "sha256": digest, "bytes": path.stat().st_size})
        return records

    def save(self, call: _Call, result: tuple, seconds: float) -> None:
        output, info = result
        outputs = ({name: self._store_array(value) for name, value in sorted(output.items())}
                   if isinstance(output, dict) else {"labels": self._store_array(output)})
        entry = {"fn": call.fn, "detector": call.detector, "outputs": outputs,
                 "engine_info": json.loads(json.dumps(info)), "files": self._store_files(call.output_dir)}
        with _lock:
            self.index["entries"][call.key] = entry
            self.calls.append({"key": call.key, "fn": call.fn, "seconds": round(seconds, 3)})
            _write_atomic(self.root / "index.json",
                          (json.dumps(self.index, sort_keys=True, indent=1) + "\n").encode("utf-8"))


def install_recorder(out_dir: Path, *, reuse: bool = False) -> Recorder:
    """Wrap the worker's detector functions; every real call is recorded.

    Existing recordings in ``out_dir`` are kept and extended. Python-only
    nucleolar definitions are executed but not recorded. With ``reuse`` a call
    whose key is already recorded returns that real recorded output (as replay
    does) instead of running the detector again; used to resume a build.
    """
    import time

    root = Path(out_dir)
    root.mkdir(parents=True, exist_ok=True)
    recorder = Recorder(root, _load_index(root))
    module = _module()
    def wrap(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs):
            call = _describe(name, args, kwargs)
            entry = recorder.index["entries"].get(call.key)
            if reuse and entry is not None and entry.get("fn") == name:
                recorder.calls.append({"key": call.key, "fn": name, "reused": True})
                return _replay_entry(root, entry, call, name)
            started = time.perf_counter()
            result = real(*args, **kwargs)
            if not _python_only(call):
                recorder.save(call, result, time.perf_counter() - started)
            return result

        wrapper.__name__ = name
        return wrapper

    wrappers = {name: wrap(name, _originals.get(name, getattr(module, name))) for name in FUNCTIONS}
    _install(wrappers)
    return recorder


def _safe_relative(root: Path, relative: str) -> Path:
    pure = PurePosixPath(relative)
    if pure.is_absolute() or ".." in pure.parts:
        raise ValueError("showcase_recordings_invalid")
    target = (root / pure).resolve()
    if root.resolve() not in target.parents:
        raise ValueError("showcase_recordings_invalid")
    return target


def _replay_entry(root: Path, entry: dict, call: _Call, name: str):
    call.output_dir.mkdir(parents=True, exist_ok=True)
    for item in entry["files"]:
        source = _safe_relative(root, item["file"])
        target = _safe_relative(call.output_dir, item["path"])
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
    arrays = {output: np.load(_safe_relative(root, relative), allow_pickle=False)
              for output, relative in entry["outputs"].items()}
    info = copy.deepcopy(entry["engine_info"])
    if name == "detect_compartments":
        return arrays, info
    return arrays["labels"], info


def install_replay(recordings_dir: Path) -> dict:
    """Serve recorded detector outputs; unrecorded requests fail visibly.

    Returns the loaded index. The error code is added to the worker's
    allowlist of field-level errors so it reaches the run step and the UI
    unchanged instead of becoming ``region_field_analysis_failed``.
    """
    root = Path(recordings_dir)
    index = _load_index(root)
    module = _module()
    module.REGION_FIELD_ERRORS.add(NOT_RECORDED)
    def wrap(name: str, real: Callable[..., Any]) -> Callable[..., Any]:
        def wrapper(*args, **kwargs):
            call = _describe(name, args, kwargs)
            entry = index["entries"].get(call.key)
            if entry is None or entry.get("fn") != name:
                if _python_only(call):
                    return real(*args, **kwargs)
                raise DetectionNotRecorded()
            return _replay_entry(root, entry, call, name)

        wrapper.__name__ = name
        return wrapper

    wrappers = {name: wrap(name, _originals.get(name, getattr(module, name))) for name in FUNCTIONS}
    _install(wrappers)
    return index

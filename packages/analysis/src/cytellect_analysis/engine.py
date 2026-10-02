"""Offline fixed Fiji / StarDist bridge. Never substitutes a different detector."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import zipfile
from pathlib import Path

import numpy as np
import tifffile

from .contracts import Recipe
from .masks import validate_labels


class EngineUnavailable(RuntimeError):
    """A required pinned engine component is unavailable."""


def _assets() -> Path:
    configured = os.environ.get("CYTELLECT_ENGINE_ASSETS")
    assets = Path(configured) if configured else Path(__file__).resolve().parents[4] / "engines" / "fiji"
    if not (assets / "runtime.lock.json").is_file():
        raise EngineUnavailable("fiji_assets_unavailable")
    return assets


def _sha(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def runtime_info(executable: str) -> tuple[Path, Path, dict]:
    if not executable:
        raise EngineUnavailable("fiji_not_configured")
    location = Path(executable).resolve()
    runtime = location if location.is_dir() else location.parent
    lock = json.loads((_assets() / "runtime.lock.json").read_text(encoding="utf-8"))
    for entry in lock["plugins"]:
        path = runtime / entry["path"]
        if not path.is_file() or _sha(path) != entry["sha256"]:
            raise EngineUnavailable("fiji_artifact_hash_mismatch")
    model = lock["model"]
    with zipfile.ZipFile(runtime / model["container"]) as jar:
        if hashlib.sha256(jar.read(model["member"])).hexdigest() != model["sha256"]:
            raise EngineUnavailable("fiji_model_hash_mismatch")
    java_name = "java.exe" if os.name == "nt" else "java"
    candidates = sorted((runtime / "java").glob("**/bin/" + java_name))
    if not candidates:
        raise EngineUnavailable("fiji_bundled_jdk_unavailable")
    return runtime, candidates[0], lock


def _classpath(runtime: Path, compiled: Path) -> str:
    # TF1.15 protobuf generated classes require the 3.x compatibility runtime.
    # Do not let the distribution's protobuf4 precede the pinned copy.
    return os.pathsep.join(map(str, [compiled, runtime / "jars/protobuf-java-3.25.8.jar", runtime / "jars/*", runtime / "plugins/*"]))


def _run(command: list[str], directory: Path, timeout: int, env: dict) -> None:
    try:
        completed = subprocess.run(
            command, cwd=directory, env=env, check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        raise EngineUnavailable("fiji_timeout") from exc
    except OSError as exc:
        raise EngineUnavailable("fiji_process_unavailable") from exc
    if completed.returncode:
        raise EngineUnavailable("fiji_execution_failed")


def detect(
    channels: dict[str, np.ndarray],
    recipe: Recipe,
    output_dir: Path,
    executable: str,
    nuclei: np.ndarray | None = None,
) -> tuple[np.ndarray, np.ndarray, dict]:
    """Detect on original-resolution copies; optional edited nuclei are preserved exactly.

    The worker owns process-tree cancellation and memory/time enforcement. All
    transient pixels, Java preferences, model extraction and temporary files stay
    inside this attempt directory, which must be on the private workspace volume.
    """
    if recipe.id == "ncl-legacy-rgb":
        from .legacy import detect_legacy_nucleoli, labels_to_original, prepare_legacy_channels

        output_dir.mkdir(parents=True, exist_ok=True)
        _, coarse_dapi, transform = prepare_legacy_channels(channels, recipe)
        if nuclei is None:
            coarse_channels = {"dapi": coarse_dapi, "ncl": np.zeros_like(coarse_dapi)}
            coarse, _, info = detect(coarse_channels, recipe.model_copy(update={"id": "ncl-native-2d"}),
                                    output_dir / "coarse-nuclei", executable)
            nuclei = labels_to_original(coarse, channels["dapi"].shape)
        else:
            _, java, lock = runtime_info(executable)
            info = {"engine": "Fiji edited nuclear masks", "nuclei_reused": True,
                    "model_sha256": lock["model"]["sha256"], "java_executable_sha256": _sha(java)}
        nucleoli, statuses = detect_legacy_nucleoli(channels, nuclei, recipe)
        validate_labels(nuclei, nucleoli)
        info.update({"recipe": recipe.id, "coordinate_transform": transform,
                     "nucleolar_status": statuses, "nucleolar_algorithm": "legacy generalized Otsu compatibility pipeline"})
        (output_dir / "engine-result.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        return nuclei, nucleoli, info
    runtime, java, lock = runtime_info(executable)
    output = output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    shape = channels["dapi"].shape
    input_roles = ("dapi",) if recipe.id == "gfp-nuclear-2d" else ("dapi", "ncl")
    if len(shape) != 2 or any(channels[key].shape != shape for key in input_roles):
        raise ValueError("fiji_input_dimensions")
    if max(shape) > 4096 or any(channels[key].dtype not in (np.uint8, np.uint16) for key in input_roles):
        raise ValueError("fiji_input_format")
    for name in input_roles:
        tifffile.imwrite(output / f"{name}.tif", channels[name], photometric="minisblack")
    if nuclei is not None:
        if nuclei.shape != shape or np.any(nuclei < 0) or np.any(nuclei != np.floor(nuclei)) or np.max(nuclei) >= 2**24:
            raise ValueError("fiji_invalid_input_labels")
        tifffile.imwrite(output / "nuclei-input.tif", nuclei.astype(np.float32), photometric="minisblack")
    request = {"directory": str(output), "recipe": recipe.model_dump(), "reuse_nuclei": nuclei is not None, "has_ncl": "ncl" in input_roles}
    (output / "request.json").write_text(json.dumps(request), encoding="utf-8")
    compiled = output / "classes"
    compiled.mkdir(exist_ok=True)
    scratch = output / "tmp"
    scratch.mkdir(exist_ok=True)
    classpath = _classpath(runtime, compiled)
    env = os.environ.copy()
    env.update({"CUDA_VISIBLE_DEVICES": "-1", "TF_CPP_MIN_LOG_LEVEL": "3", "OMP_NUM_THREADS": "1"})
    javac = java.with_name("javac.exe" if os.name == "nt" else "javac")
    assets = _assets()
    _run([str(javac), "-encoding", "UTF-8", "-cp", classpath, "-d", str(compiled),
          str(assets / "CytellectPreferences.java"), str(assets / "CytellectEngine.java")], output, 120, env)
    command = [
        str(java), "--add-opens=java.base/java.lang=ALL-UNNAMED", "-Djava.awt.headless=true",
        "-Djava.util.prefs.PreferencesFactory=CytellectPreferences",
        "-Djava.io.tmpdir=" + str(scratch), "-Duser.home=" + str(scratch),
        "-Dimagej.tensorflow.models.dir=" + str(output / "models"),
        "-Dimagej.dir=" + str(runtime), "-Dscijava.log.level=error",
        "-Xmx2g", "-cp", classpath, "CytellectEngine", str(output / "request.json"),
    ]
    _run(command, output, 1800, env)
    labels = []
    for name in ("nuclei", "nucleoli"):
        array = tifffile.imread(output / f"{name}.tif")
        if array.shape != shape or not np.isfinite(array).all() or np.any(array < 0) or np.any(array != np.floor(array)):
            raise EngineUnavailable("fiji_invalid_output_labels")
        labels.append(array.astype(np.uint32))
    validate_labels(*labels)
    if nuclei is not None and not np.array_equal(labels[0], nuclei):
        raise EngineUnavailable("fiji_modified_preserved_nuclei")
    info = json.loads((output / "engine-result.json").read_text(encoding="utf-8"))
    info.update({
        "model_sha256": lock["model"]["sha256"],
        "runtime_lock_sha256": _sha(assets / "runtime.lock.json"),
        "bridge_sha256": _sha(assets / "CytellectEngine.java"),
        "coordinate_transform": {"scale_x": 1, "scale_y": 1},
        "artifacts": [{"path": p["path"], "sha256": p["sha256"]} for p in lock["plugins"]],
        "java_executable_sha256": _sha(java),
    })
    # No local paths, image names, or submitted metadata in exported provenance.
    (output / "engine-result.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
    return labels[0], labels[1], info

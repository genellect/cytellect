"""Build the Microsoft Store (MSIX) edition's package from an accepted setup ZIP (docs/windows-msix.md).

Everything that runs is inside the package, so that the Store's signature covers every file that
Windows loads: python.org's runtime with every locked wheel installed by python.org's own pip
(``--no-index --require-hashes``; no uv), Fiji with its JDK and the native libraries that Fiji's
Java plugins would otherwise unpack into the temporary folder, the static workspace and the
release's source. Nothing is created outside the package at first run except research data and
settings in ``%LOCALAPPDATA%\\Cytellect``.

    python scripts/build_windows_msix.py build --release-zip Z --staged-install S --work-dir W \\
        --output-dir O [--makeappx M] [--pip-python P] [--identity packaging/windows/msix/store-identity.json]

``--staged-install`` is an installation that ``scripts/local_setup.ps1`` completed on the build
machine from the same ZIP (``-Console -NoShortcut``). Its composed Python runtime (python.org's
archive plus the reviewed Tcl/Tk data) and its verified Fiji are copied; its uv-made virtual
environment is not. The package is not signed here: CI signs a test package with a throwaway
certificate, and the Store signs a submitted one.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree
from xml.sax.saxutils import escape

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_windows_installer import (  # noqa: E402
    BuildError,
    download_wheels,
    extract_release,
    scan_for_secrets,
    sha256_file,
    verify_release_zip,
    verify_wheelhouse,
)

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "packaging/windows/msix/AppxManifest.xml"
IDENTITY = ROOT / "packaging/windows/msix/store-identity.json"
RECEIPT_SCHEMA = "cytellect-windows-msix/1"
PACKAGE_SCHEMA = "cytellect-msix-package/1"
NATIVES_SCHEMA = "cytellect-fiji-natives/1"
# The JNI library that TensorFlow's Java binding unpacks unless java.library.path already has it.
TENSORFLOW_JNI = re.compile(r"jars/libtensorflow_jni-[0-9.]+\.jar")
TENSORFLOW_WINDOWS = "org/tensorflow/native/windows-x86_64/"
STORE_LIMIT = 25 * 1024**3
IDENTITY_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9.-]{2,49}")


def msix_version(version: str) -> str:
    """``X.Y.Z-local.N`` as ``X.Y.(Z*1000+N).0``; the Store requires the fourth field to be 0."""
    match = re.fullmatch(r"([0-9]+)\.([0-9]+)\.([0-9]+)(?:-local\.([0-9]+))?", version)
    if not match:
        raise BuildError("version_invalid")
    major, minor, patch, local = (int(group or 0) for group in match.groups())
    if local >= 1000 or max(major, minor, patch * 1000 + local) > 65535:
        raise BuildError("version_out_of_range")
    return f"{major}.{minor}.{patch * 1000 + local}.0"


def load_identity(path: Path) -> dict:
    identity = json.loads(path.read_text(encoding="utf-8"))
    if (identity.get("schema") != "cytellect-msix-identity/1"
            or not IDENTITY_NAME.fullmatch(str(identity.get("identity_name", "")))
            or not str(identity.get("publisher", "")).startswith("CN=")
            or not str(identity.get("publisher_display_name", "")).strip()):
        raise BuildError("msix_identity_invalid")
    return identity


def render_manifest(template: str, identity: dict, version: str) -> str:
    values = {"IDENTITY_NAME": identity["identity_name"], "PUBLISHER": identity["publisher"],
              "PUBLISHER_DISPLAY_NAME": identity["publisher_display_name"], "VERSION": msix_version(version)}
    text = template
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", escape(value, {'"': "&quot;"}))
    if "{{" in text:
        raise BuildError("msix_manifest_placeholder_left")
    ElementTree.fromstring(text.encode("utf-8"))  # well-formed
    return text


def is_pe(path: Path) -> bool:
    """A Portable Executable image (DOS header pointing at a PE signature), whatever its name."""
    try:
        with path.open("rb") as stream:
            header = stream.read(64)
            if len(header) < 64 or header[:2] != b"MZ":
                return False
            offset = int.from_bytes(header[60:64], "little")
            stream.seek(offset)
            return stream.read(4) == b"PE\0\0"
    except OSError:
        return False


def pe_inventory(layout: Path) -> dict[str, int]:
    """PE images per top-level part of the package (python, fiji, ...)."""
    counts: dict[str, int] = {}
    for path in layout.rglob("*"):
        if path.is_file() and is_pe(path):
            parts = path.relative_to(layout).parts
            part = parts[0] if len(parts) > 1 else "."
            counts[part] = counts.get(part, 0) + 1
    return dict(sorted(counts.items()))


def staged_runtime(staged: Path, manifest: dict) -> tuple[Path, Path, dict]:
    """The completed application of this release in the staged installation, with its runtimes."""
    app = staged / "apps" / (manifest["version"] + "-" + manifest["source_commit"][:12])
    try:
        marker = json.loads((app / "setup-complete.json").read_text(encoding="utf-8-sig"))
        installed = json.loads((app / "local-release.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise BuildError("staged_install_incomplete") from None
    if installed != manifest or marker.get("version") != manifest["version"]:
        raise BuildError("staged_install_other_release")
    python = staged / "runtimes" / ("python-" + str(marker.get("python_build", "")))
    fiji = Path(str(marker.get("fiji", "")))
    if not (python / "python.exe").is_file() or not (python / "pythonw.exe").is_file():
        raise BuildError("staged_python_missing")
    if not fiji.is_absolute() or fiji.resolve().parent != (staged / "runtimes").resolve() or not fiji.is_dir():
        raise BuildError("staged_fiji_missing")
    return python, fiji, marker


def verify_launchers(python: Path, release: Path) -> None:
    """python.org's interpreters, by the digests that the release pins."""
    lock = json.loads((release / "engines/python/windows-runtime.lock.json").read_text(encoding="utf-8"))
    for launcher in lock["python"]["launchers"]:
        if launcher["path"] in {"python.exe", "pythonw.exe"} and sha256_file(python / launcher["path"]) != launcher["sha256"]:
            raise BuildError("python_launcher_hash_mismatch")


def runtime_pip(python: Path) -> str:
    """python.org's archive ships pip in site-packages; nothing else may be there before the install."""
    site = python / "Lib/site-packages"
    names = sorted(path.name for path in site.iterdir()) if site.is_dir() else []
    info = [name for name in names if re.fullmatch(r"pip-[0-9.]+\.dist-info", name)]
    if len(info) != 1 or set(names) - {"README.txt", "pip", info[0]}:
        raise BuildError("staged_python_not_clean")
    return info[0].removesuffix(".dist-info")


def clean_environment(**extra: str) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(("PIP_", "PYTHON", "UV_", "VIRTUAL_ENV", "CONDA"))}
    environment.update(PYTHONDONTWRITEBYTECODE="1", **extra)
    return environment


def run(command: list[str], code: str, *, cwd: Path, env: dict[str, str], timeout: int = 1800) -> str:
    try:
        completed = subprocess.run(command, cwd=cwd, env=env, check=True, capture_output=True, text=True,
                                   timeout=timeout)
    except (OSError, subprocess.SubprocessError) as error:
        output = getattr(error, "stdout", "") or ""
        errors = getattr(error, "stderr", "") or ""
        # Package-manager output names files of this build only; keep the end for the log.
        print((output + errors)[-4000:], file=sys.stderr)
        raise BuildError(code) from None
    return completed.stdout


def install_wheels(layout: Path, wheels: Path) -> dict:
    """python.org's pip, as shipped with this runtime, installs every locked wheel.

    pip writes console-script launchers (unsigned PE files) next to the interpreter; the package
    starts everything with ``python -m``, so they are removed and listed in the receipt.
    """
    python = layout / "python"
    before = {path.relative_to(python).as_posix() for path in python.rglob("*") if path.is_file()}
    pip = runtime_pip(python)
    environment = clean_environment()
    base = [str(python / "python.exe"), "-B", "-s", "-m", "pip", "--disable-pip-version-check", "--isolated"]
    run([*base, "install", "--no-index", "--find-links", str(wheels), "--require-hashes", "--only-binary=:all:",
         "--no-deps", "--no-compile", "--no-warn-script-location", "-r", "engines/python/windows-requirements.txt"],
        "msix_wheel_install_failed", cwd=layout, env=environment)
    run([*base, "check"], "msix_dependency_check_failed", cwd=layout, env=environment, timeout=600)
    removed, kept = [], []
    for path in sorted(python.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(python).as_posix()
        if relative in before:
            continue
        if path.name == "direct_url.json" and relative.startswith("Lib/site-packages/"):
            path.unlink()  # records this build machine's wheel path only
        elif not relative.startswith("Lib/site-packages/"):
            if is_pe(path):
                path.unlink()
                removed.append(relative)
            else:
                kept.append(relative)
    scripts = python / "Scripts"
    if scripts.is_dir() and not any(scripts.iterdir()):
        scripts.rmdir()
    return {"pip": pip, "removed_launchers": removed, "other_files_outside_site_packages": kept}


def extract_natives(fiji: Path, release: Path) -> dict:
    """Pre-extract TensorFlow's JNI library into ``fiji/natives`` (the engine adds it to java.library.path)."""
    lock = json.loads((release / "engines/fiji/runtime.lock.json").read_text(encoding="utf-8"))
    plugins = [entry for entry in lock["plugins"] if TENSORFLOW_JNI.fullmatch(entry["path"])]
    if len(plugins) != 1:
        raise BuildError("tensorflow_jni_not_locked")
    jar = fiji / plugins[0]["path"]
    if sha256_file(jar) != plugins[0]["sha256"]:
        raise BuildError("tensorflow_jni_hash_mismatch")
    natives = fiji / "natives"
    natives.mkdir()
    files = []
    with zipfile.ZipFile(jar) as archive:
        for member in archive.namelist():
            if not member.startswith(TENSORFLOW_WINDOWS) or not member.lower().endswith(".dll"):
                continue
            name = PurePosixPath(member).name
            data = archive.read(member)
            (natives / name).write_bytes(data)
            files.append({"name": name, "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data),
                          "source": plugins[0]["path"], "source_sha256": plugins[0]["sha256"], "member": member})
    if [entry["name"] for entry in files] != ["tensorflow_jni.dll"]:
        raise BuildError("tensorflow_jni_member_unexpected")
    record = {"schema": NATIVES_SCHEMA, "reason": "loaded from java.library.path instead of unpacked at run time",
              "files": files}
    (natives / "natives.json").write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    return record


def draw_icon(size: tuple[int, int]):
    """The workspace icon (apps/web/src/app/icon.svg), drawn for the Store's tile sizes."""
    from PIL import Image, ImageDraw

    scale = 4
    width, height = size
    side = min(width, height)
    canvas = Image.new("RGBA", (width * scale, height * scale), (0, 0, 0, 0))
    unit = side * scale / 64
    left = (width * scale - 64 * unit) / 2
    top = (height * scale - 64 * unit) / 2

    def box(cx, cy, rx, ry):
        return [left + (cx - rx) * unit, top + (cy - ry) * unit, left + (cx + rx) * unit, top + (cy + ry) * unit]

    draw = ImageDraw.Draw(canvas)
    draw.rounded_rectangle([0, 0, width * scale - 1, height * scale - 1], radius=14 * unit, fill=(3, 9, 22, 255))
    draw.ellipse(box(32.5, 31, 21.5, 21), fill=(35, 107, 241, 36), outline=(93, 145, 255, 178),
                 width=max(1, round(2.4 * unit)))
    nucleus = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
    ImageDraw.Draw(nucleus).ellipse(box(34.5, 33, 12.5, 10.5), fill=(74, 134, 247, 255))
    centre = (left + 34.5 * unit, top + 33 * unit)
    canvas = Image.alpha_composite(canvas, nucleus.rotate(24, resample=Image.BICUBIC, center=centre))
    draw = ImageDraw.Draw(canvas)
    draw.ellipse(box(37.6, 30.2, 3.1, 3.1), fill=(243, 243, 239, 255))
    draw.ellipse(box(30.6, 36.4, 1.8, 1.8), fill=(243, 243, 239, 191))
    return canvas.resize(size, Image.LANCZOS)


ASSETS = {"StoreLogo.png": (50, 50), "Square44x44Logo.png": (44, 44), "Square150x150Logo.png": (150, 150),
          "Wide310x150Logo.png": (310, 150)}


def write_assets(directory: Path) -> list[str]:
    directory.mkdir()
    for name, size in ASSETS.items():
        draw_icon(size).save(directory / name)
    return sorted(ASSETS)


NOT_FOR_DISTRIBUTION = """Cytellect MSIX prototype package (docs/windows-msix.md)

This package was built to test the Microsoft Store edition. It does not yet carry the third-party
notices (licenses/THIRD_PARTY_BUNDLED.txt) and the corresponding-source asset that the installer
edition ships, and it must not be distributed.
"""


def tree_bytes(root: Path) -> int:
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file())


def build(release_zip: Path, staged: Path, work_dir: Path, output_dir: Path, identity_path: Path,
          makeappx: Path | None, pip_python: Path) -> dict:
    manifest = verify_release_zip(release_zip)
    version, commit = manifest["version"], manifest["source_commit"]
    identity = load_identity(identity_path)
    output = output_dir / f"Cytellect-{version}-x64.msix"
    if output.exists():
        raise BuildError("msix_exists")
    layout = work_dir / "layout"
    extract_release(release_zip, layout)
    python, fiji, marker = staged_runtime(staged, manifest)
    shutil.copytree(python, layout / "python")
    verify_launchers(layout / "python", layout)
    runtime_pip(layout / "python")
    shutil.copytree(fiji, layout / "fiji")
    requirements = (layout / "engines/python/windows-requirements.txt").read_text(encoding="utf-8")
    wheels = work_dir / "wheels"
    download_wheels(requirements, wheels, work_dir, pip_python)
    wheel_count = len(verify_wheelhouse(requirements, wheels))
    installed = install_wheels(layout, wheels)
    natives = extract_natives(layout / "fiji", layout)
    (layout / "cytellect-package.json").write_text(json.dumps(
        {"schema": PACKAGE_SCHEMA, "edition": "msix", "version": version, "source_commit": commit,
         "fiji": "fiji", "web": "apps/web/out"}, indent=2) + "\n", encoding="utf-8")
    (layout / "licenses").mkdir()
    (layout / "licenses/README.txt").write_text(NOT_FOR_DISTRIBUTION, encoding="utf-8")
    assets = write_assets(layout / "Assets")
    (layout / "AppxManifest.xml").write_text(render_manifest(TEMPLATE.read_text(encoding="utf-8"), identity, version),
                                             encoding="utf-8")
    # The packaged interpreter must run the release's own source and find Fiji's verified plugins.
    check = ("import json, sys; from cytellect_api.local import installed_source_revision; "
             "from cytellect_analysis.engine import runtime_info, _native_library_flags; "
             "import numpy, scipy, skimage, matplotlib, tifffile, tkinter, cytellect_worker.main, cytellect_api.packaged; "
             "runtime, java, _ = runtime_info(sys.argv[1]); "
             "print(json.dumps({'revision': installed_source_revision(), 'natives': _native_library_flags(runtime) != []}))")
    reported = json.loads(run([str(layout / "python/python.exe"), "-B", "-E", "-c", check, str(layout / "fiji")],
                              "msix_python_check_failed", cwd=layout, env=clean_environment(), timeout=600))
    if reported != {"revision": commit, "natives": True}:
        raise BuildError("msix_python_check_mismatch")
    release_files = [layout / entry["path"] for entry in manifest["files"]]
    findings = scan_for_secrets([*release_files, layout / "AppxManifest.xml", layout / "cytellect-package.json",
                                 layout / "fiji/natives/natives.json"])
    if findings:
        raise BuildError("msix_contains_credentials:" + ",".join(sorted(findings)))
    layout_bytes = tree_bytes(layout)
    if layout_bytes > STORE_LIMIT:
        raise BuildError("msix_too_large")
    receipt = {"schema": RECEIPT_SCHEMA, "version": version, "msix_version": msix_version(version),
               "source_commit": commit, "identity": {key: identity[key] for key in
                                                     ("identity_name", "publisher", "publisher_display_name",
                                                      "partner_center")},
               "release_zip_sha256": sha256_file(release_zip), "python_build": marker.get("python_build"),
               "wheels": wheel_count, "pip": installed, "natives": natives["files"], "assets": assets,
               "layout_bytes": layout_bytes, "layout_files": sum(1 for path in layout.rglob("*") if path.is_file()),
               "pe_files": pe_inventory(layout), "signed": False, "distributable": False}
    output_dir.mkdir(parents=True, exist_ok=True)
    if makeappx is not None:
        run([str(makeappx), "pack", "/o", "/d", str(layout), "/p", str(output)], "msix_pack_failed",
            cwd=work_dir, env=clean_environment(), timeout=3600)
        receipt.update(msix=output.name, msix_sha256=sha256_file(output), msix_bytes=output.stat().st_size)
    (output_dir / f"Cytellect-{version}-msix.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest="command", required=True)
    make = commands.add_parser("build")
    make.add_argument("--release-zip", type=Path, required=True)
    make.add_argument("--staged-install", type=Path, required=True,
                      help="An installation that scripts/local_setup.ps1 completed from the same ZIP")
    make.add_argument("--work-dir", type=Path, required=True)
    make.add_argument("--output-dir", type=Path, required=True)
    make.add_argument("--identity", type=Path, default=IDENTITY)
    make.add_argument("--makeappx", type=Path, help="Windows SDK makeappx.exe; without it only the layout is built")
    make.add_argument("--pip-python", type=Path, default=Path(sys.executable),
                      help="An interpreter with pip, used only to download the locked wheels")
    args = parser.parse_args()
    for path in (args.work_dir, args.output_dir):
        resolved = path.resolve()
        if resolved == ROOT or ROOT in resolved.parents:
            parser.error("MSIX outputs must be outside the checkout")
    try:
        receipt = build(args.release_zip.resolve(), args.staged_install.resolve(), args.work_dir.resolve(),
                        args.output_dir.resolve(), args.identity.resolve(),
                        args.makeappx.resolve() if args.makeappx else None, args.pip_python)
    except BuildError as error:
        print("MSIX build failed: " + str(error), file=sys.stderr)
        raise SystemExit(2) from None
    print(json.dumps({key: receipt[key] for key in ("version", "msix_version", "wheels", "layout_bytes",
                                                    "layout_files", "pe_files", "pip")}, indent=2))


if __name__ == "__main__":
    main()

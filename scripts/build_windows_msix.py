"""Build an unsigned MSIX from the current, hash-verified Windows release ZIP."""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

from build_windows_installer import (
    BuildError,
    collect_corresponding_source,
    prepare_offline_payload,
    scan_for_secrets,
    sha256_file,
    verify_release_zip,
    write_notices,
)
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "packaging/windows/msix/AppxManifest.xml"
NS = {
    "": "http://schemas.microsoft.com/appx/manifest/foundation/windows10",
    "rescap": "http://schemas.microsoft.com/appx/manifest/foundation/windows10/restrictedcapabilities",
    "uap": "http://schemas.microsoft.com/appx/manifest/uap/windows10",
    "uap10": "http://schemas.microsoft.com/appx/manifest/uap/windows10/10",
    "virtualization": "http://schemas.microsoft.com/appx/manifest/virtualization/windows10",
}
DEV_IDENTITY = {
    "name": "Cytellect.Development",
    "publisher": "CN=Cytellect Development",
    "publisher_display_name": "Cytellect Development",
}
TENSORFLOW_JNI_JAR = "jars/libtensorflow_jni-1.15.0.jar"
TENSORFLOW_JNI_DLL = "org/tensorflow/native/windows-x86_64/tensorflow_jni.dll"


def package_version(value: str) -> str:
    if (not re.fullmatch(r"[1-9][0-9]{0,4}\.(?:0|[1-9][0-9]{0,4})\.(?:0|[1-9][0-9]{0,4})\.0", value)
            or any(int(part) > 65535 for part in value.split("."))):
        raise argparse.ArgumentTypeError("Use a Store version such as 1.0.1.0")
    return value


def write_manifest(output: Path, version: str, identity: dict[str, str]) -> None:
    if (identity.keys() != DEV_IDENTITY.keys()
            or not all(isinstance(value, str) and value.strip() for value in identity.values())
            or not re.fullmatch(r"[A-Za-z0-9.-]{3,50}", identity["name"])
            or not identity["publisher"].startswith("CN=")
            or (identity != DEV_IDENTITY and identity["name"] == DEV_IDENTITY["name"])):
        raise BuildError("msix_identity_invalid")
    for prefix, uri in NS.items():
        ET.register_namespace(prefix, uri)
    manifest = ET.parse(MANIFEST)
    package = manifest.find("Identity", NS)
    display = manifest.find("Properties/PublisherDisplayName", NS)
    if package is None or display is None:
        raise BuildError("msix_manifest_invalid")
    package.attrib.update(Name=identity["name"], Publisher=identity["publisher"], Version=version)
    display.text = identity["publisher_display_name"]
    manifest.write(output, encoding="utf-8", xml_declaration=True)


def write_logos(directory: Path) -> None:
    directory.mkdir()
    # Simple raster version of the app icon, supersampled for the small Start tile.
    icon = Image.new("RGBA", (256, 256))
    draw = ImageDraw.Draw(icon)
    draw.rounded_rectangle((0, 0, 255, 255), radius=56, fill="#030916")
    draw.ellipse((42, 36, 218, 218), fill="#0c1930", outline="#5d91ff", width=8)
    draw.ellipse((87, 84, 187, 173), fill="#236bf1")
    draw.ellipse((138, 106, 162, 130), fill="#f3f3ef")
    draw.ellipse((116, 139, 130, 153), fill="#bad0f2")
    for name, size in (("StoreLogo", 50), ("Square150x150Logo", 150), ("Square44x44Logo", 44)):
        icon.resize((size, size), Image.Resampling.LANCZOS).save(directory / (name + ".png"))


def sdk_tool(name: str) -> Path:
    kits = Path(os.environ["ProgramFiles(x86)"]) / "Windows Kits/10/bin"
    candidates = sorted(kits.glob(f"10.*/x64/{name}"),
                        key=lambda path: tuple(map(int, path.parents[1].name.split("."))), reverse=True)
    if not candidates:
        raise BuildError("msix_windows_sdk_missing")
    return candidates[0]


def stage_runtime(layout: Path, offline: Path, scratch: Path, python_sha256: str) -> None:
    python_home = layout / "python"
    powershell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    subprocess.run([str(powershell), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass",
                    "-File", str(ROOT / "scripts/prepare_windows_msix_python.ps1"),
                    "-Release", str(layout), "-Archive", str(offline / "sha256" / python_sha256),
                    "-Scratch", str(scratch / "runtime"), "-Output", str(python_home)],
                   check=True, timeout=900)
    python = python_home / "python.exe"
    env = {key: value for key, value in os.environ.items() if not key.upper().startswith(("PIP_", "UV_"))}
    env["PIP_CONFIG_FILE"] = os.devnull
    pip = [str(python), "-I", "-B", "-m", "pip", "--disable-pip-version-check"]
    scripts = python_home / "Scripts"
    original_scripts = {path.name for path in scripts.iterdir()} if scripts.exists() else set()
    subprocess.run([*pip, "install", "--no-index", "--no-cache-dir", "--require-hashes", "--only-binary=:all:",
                    "--no-deps", "--no-compile", "--find-links", str(offline / "wheels"),
                    "-r", "engines/python/windows-requirements.txt"], cwd=layout, env=env, check=True, timeout=900)
    subprocess.run([*pip, "check"], cwd=layout, env=env, check=True, timeout=120)
    for script in scripts.glob("*.exe"):
        if script.name not in original_scripts:
            script.unlink()  # CLI entry points are not invoked by the installed package.
    staged_fiji = scratch / "fiji"
    subprocess.run([sys.executable, "-B", str(layout / "scripts/fiji_setup.py"), str(staged_fiji),
                    "--offline-dir", str(offline / "sha256"), "--scratch-root", str(scratch)],
                   check=True, timeout=1800)
    runtime = layout / "fiji"
    staged_fiji.rename(runtime)
    natives = runtime / "cytellect-natives"
    natives.mkdir()
    with zipfile.ZipFile(runtime / TENSORFLOW_JNI_JAR) as jar:
        with jar.open(TENSORFLOW_JNI_DLL) as source, (natives / "tensorflow_jni.dll").open("wb") as target:
            shutil.copyfileobj(source, target)
    # Compile the bridge with the bundled interpreter, fixed JDK and the exact
    # sources that are recorded in local-release.json.
    build_bridge = """
import os
import sys
from pathlib import Path
from cytellect_analysis.engine import compile_fiji_bridge, runtime_info
from cytellect_api.local_release import installed_source_revision
root, commit = Path(sys.argv[1]), sys.argv[2]
if installed_source_revision(root) != commit:
    raise SystemExit("msix_installed_revision_mismatch")
runtime, java, _ = runtime_info(str(root / "fiji"))
compile_fiji_bridge(runtime, java, root / "engines/fiji", runtime / "cytellect-classes", os.environ.copy())
"""
    commit = json.loads((layout / "local-release.json").read_text(encoding="utf-8"))["source_commit"]
    subprocess.run([str(python), "-I", "-B", "-c", build_bridge, str(layout), commit],
                   cwd=layout, check=True, timeout=420)


def build(release_zip: Path, commit: str, version: str, output: Path, cache: Path,
          pip_python: Path, identity: dict[str, str]) -> None:
    manifest = verify_release_zip(release_zip)
    if manifest["source_commit"] != commit:
        raise BuildError("msix_release_commit_mismatch")
    if output.exists() or output.suffix.lower() != ".msix":
        raise BuildError("msix_output_invalid")
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="msix-", dir=output.parent) as directory:
        scratch = Path(directory)
        payload = scratch / "inputs"
        artifacts, wheels = prepare_offline_payload(release_zip, payload, cache, pip_python, manifest, include_uv=False)
        layout = payload / "release"
        source_dir = scratch / "sources"
        sources = collect_corresponding_source(payload, layout, artifacts, wheels, source_dir, cache,
                                               manifest["version"], commit)
        write_notices(payload, layout, artifacts, wheels, sources, source_in_package=True)
        if scan_for_secrets([layout, payload / "licenses"]):
            raise BuildError("msix_payload_contains_credentials")
        shutil.move(str(payload / "licenses"), layout)
        shutil.move(str(source_dir / sources["asset"]), layout / "licenses")
        write_manifest(layout / "AppxManifest.xml", version, identity)
        write_logos(layout / "Assets")
        stage_runtime(layout, payload / "offline", scratch,
                      next(item.sha256 for item in artifacts if item.role == "python"))
        (layout / "store-package.json").write_text(
            json.dumps({"version": version, "source_commit": commit}) + "\n", encoding="utf-8")
        staged_msix = scratch / "staged.msix"
        subprocess.run([str(sdk_tool("MakeAppx.exe")), "pack", "/d", str(layout), "/p", str(staged_msix),
                        "/h", "SHA256"], check=True, timeout=1200)
        staged_msix.rename(output)
    receipt = {"schema": "cytellect-windows-msix/1", "version": version, "source_commit": commit,
               "windows_release_version": manifest["version"], "identity": identity["name"],
               "msix_sha256": sha256_file(output), "msix_bytes": output.stat().st_size,
               "corresponding_source_sha256": sources["sha256"]}
    output.with_suffix(".json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release-zip", type=Path, required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--version", type=package_version, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--cache", type=Path, required=True)
    parser.add_argument("--pip-python", type=Path, default=Path(sys.executable))
    parser.add_argument("--identity", type=Path, help="Partner Center Name, Publisher and PublisherDisplayName JSON")
    args = parser.parse_args()
    identity = DEV_IDENTITY if args.identity is None else json.loads(args.identity.read_text(encoding="utf-8"))
    try:
        build(args.release_zip.resolve(), args.commit, args.version, args.output.resolve(),
              args.cache.resolve(), args.pip_python.resolve(), identity)
    except BuildError as error:
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()

"""Build a source-pinned Windows setup ZIP; never package runtime or research data."""
from __future__ import annotations

import argparse
import email.parser
import hashlib
import io
import json
import os
import re
import shutil
import subprocess
import tomllib
import zipfile
from pathlib import Path

from packaging.requirements import InvalidRequirement, Requirement

UV_VERSION = "0.12.2"
PRODUCTION_EXPORT = ("export", "--locked", "--no-dev", "--no-emit-project", "--no-header")
ROOT_FILES = {"pyproject.toml", "uv.lock", "README.md", "README.ja.md", "LICENSE", "NOTICE"}
SOURCE_TREES = ("packages/analysis/src/", "services/api/src/", "services/worker/src/")
SCRIPTS = {"scripts/fiji_setup.py", "scripts/local_setup.ps1", "scripts/windows_runtime.ps1"}
RUNTIME_RECORDS = {"engines/python/windows-runtime.lock.json", "engines/python/windows-tcltk-members.json"}
RUNTIME_DATA = "engines/python/windows-tcltk-9.0.4-data.zip"
INSTALL_REQUIREMENTS = "engines/python/windows-requirements.txt"
INSTALL_MANIFEST = "engines/python/windows-install.json"
DOCS = {"docs/oss.md", "docs/local.md", "docs/security.md", "docs/hosting-costs.ja.md", "docs/windows-runtime.md"}
DATA_NOTICES = {"fixtures/public/allowlist.json"}
WEB_SUFFIXES = {".html", ".js", ".css", ".json", ".txt", ".svg", ".woff2", ".woff", ".ttf",
                ".ico", ".png", ".jpg", ".jpeg", ".webp"}


def source_allowed(name: str) -> bool:
    path = Path(name)
    if any(part.startswith(".") or part in {"__pycache__", "node_modules"} for part in path.parts):
        return False
    return (name in ROOT_FILES | SCRIPTS | DOCS | DATA_NOTICES | RUNTIME_RECORDS
            or (name.startswith(SOURCE_TREES) and path.suffix == ".py")
            or (name.startswith("engines/fiji/") and path.suffix in {".java", ".json"})
            or (name.startswith("scripts/windows/") and path.suffix == ".cmd"))


def verify_file(root: Path, path: Path) -> None:
    if not path.is_file() or root.resolve() not in path.resolve().parents:
        raise ValueError("bundle_file_outside_root")
    for ancestor in [path, *path.parents]:
        if ancestor == root:
            break
        if ancestor.is_symlink() or ancestor.is_junction():
            raise ValueError("bundle_symlink_forbidden")


def collect_files(root: Path, tracked: list[str], web_dir: Path) -> dict[str, Path]:
    files = {name: root / name for name in tracked if source_allowed(name)}
    required = ROOT_FILES | SCRIPTS | RUNTIME_RECORDS | {"scripts/windows/Cytellect Setup.cmd"}
    if required - files.keys():
        raise ValueError("bundle_required_source_missing")
    for path in files.values():
        verify_file(root, path)
    if web_dir.is_symlink() or web_dir.is_junction() or not (web_dir / "index.html").is_file():
        raise ValueError("bundle_local_web_missing")
    for path in web_dir.rglob("*"):
        if path.is_dir():
            continue
        relative = path.relative_to(web_dir)
        if any(part.startswith(".") for part in relative.parts) or path.suffix not in WEB_SUFFIXES:
            raise ValueError("bundle_unexpected_web_asset")
        verify_file(web_dir, path)
        files[f"apps/web/out/{relative.as_posix()}"] = path
    # The only top-level executable is a copy of a reviewed, tracked launcher.
    files["Cytellect Setup.cmd"] = files["scripts/windows/Cytellect Setup.cmd"]
    if sum(path.stat().st_size for path in files.values()) > 100 * 1024 * 1024:
        raise ValueError("bundle_size_exceeded")
    return files


def write_bundle(output: Path, files: dict[str, Path], version: str, commit: str,
                 generated: dict[str, bytes] | None = None) -> str:
    if not re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+(?:-[a-z0-9.]+)?", version):
        raise ValueError("bundle_version_invalid")
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise ValueError("bundle_commit_invalid")
    entries = []
    payloads = {}
    payloads.update({name: path.read_bytes() for name, path in files.items()})
    for name, content in (generated or {}).items():
        allowed = name in {"THIRD_PARTY_WEB_NOTICES.txt", "web-license-inventory.json", RUNTIME_DATA,
                           INSTALL_REQUIREMENTS, INSTALL_MANIFEST}
        allowed = allowed or bool(re.fullmatch(r"wheels/cytellect-[0-9][0-9a-z.+]*-py3-none-any\.whl", name))
        if name in payloads or not allowed:
            raise ValueError("bundle_generated_asset_invalid")
        payloads[name] = content
    for name, data in sorted(payloads.items()):
        entries.append({"path": name, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
    manifest = {"schema": "cytellect-local-release/1", "version": version,
                "source_commit": commit, "platform": "windows-x64", "files": entries}
    payloads["local-release.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    output.parent.mkdir(parents=True, exist_ok=True)
    # Exclusive creation protects an already published version from replacement.
    with output.open("xb") as stream, zipfile.ZipFile(stream, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in sorted(payloads.items()):
            item = zipfile.ZipInfo(name, date_time=(2026, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_DEFLATED
            item.external_attr = 0o100644 << 16
            archive.writestr(item, data)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix(output.suffix + ".sha256").write_text(f"{digest}  {output.name}\n", encoding="ascii")
    return digest


def runtime_data(root: Path, artifact: Path) -> bytes:
    """Only include the exact reviewed data-only asset; no runtime executables."""
    lock = json.loads((root / "engines/python/windows-runtime.lock.json").read_text(encoding="utf-8"))
    if lock.get("schema") != "cytellect-windows-runtime/1" or lock["data_asset"]["path"] != RUNTIME_DATA:
        raise ValueError("bundle_runtime_lock_invalid")
    expected = lock["data_asset"]
    if artifact.is_symlink() or not artifact.is_file() or artifact.stat().st_size != expected["bytes"]:
        raise ValueError("bundle_runtime_data_invalid")
    data = artifact.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected["sha256"]:
        raise ValueError("bundle_runtime_data_hash_mismatch")
    return data


def canonical_requirements(root: Path) -> bytes:
    """Export this exact lock offline; no caller's dependency/config overrides."""
    uv = shutil.which("uv")
    if uv is None:
        raise ValueError("bundle_pinned_uv_required")
    inputs = [root / "pyproject.toml", root / "uv.lock"]
    for path in inputs:
        verify_file(root, path)
    original = [path.read_bytes() for path in inputs]
    environment = {key: value for key, value in os.environ.items()
                   if not key.upper().startswith(("UV_", "PIP_"))}
    try:
        version = subprocess.run([uv, "--version"], cwd=root, env=environment,
                                 capture_output=True, check=True, timeout=15).stdout.decode("ascii").strip()
        if not re.fullmatch(r"uv " + re.escape(UV_VERSION) + r"(?: \([^)]+\))?", version):
            raise ValueError("bundle_pinned_uv_required")
        exported = subprocess.run([uv, *PRODUCTION_EXPORT, "--no-config", "--offline", "--no-cache",
                                   "--no-python-downloads"],
                                  cwd=root, env=environment, capture_output=True, check=True, timeout=120).stdout
    except (OSError, subprocess.SubprocessError, UnicodeError):
        raise ValueError("bundle_locked_export_failed") from None
    if [path.read_bytes() for path in inputs] != original:
        raise ValueError("bundle_locked_export_source_changed")
    return exported


def normalized_dependencies(values) -> set[Requirement]:
    try:
        return {Requirement(value) for value in values}
    except (InvalidRequirement, TypeError):
        raise ValueError("bundle_project_wheel_dependencies") from None


def install_payload(root: Path, wheel: Path, requirements: Path) -> dict[str, bytes]:
    """Bind the normally built wheel's Python sources to this release checkout."""
    project = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))["project"]
    filename = f"cytellect-{project['version']}-py3-none-any.whl"
    if wheel.name != filename or wheel.is_symlink() or not wheel.is_file() or wheel.stat().st_size > 5 * 1024**2:
        raise ValueError("bundle_project_wheel_invalid")
    data = wheel.read_bytes()
    expected = {}
    for prefix in SOURCE_TREES:
        source = root / prefix
        for path in source.rglob("*.py"):
            verify_file(root, path)
            expected[path.relative_to(source).as_posix()] = path.read_bytes()
    if not expected:
        raise ValueError("bundle_project_sources_missing")
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)) or any("\\" in name or name.startswith("/") or
                                             any(part in {"", ".", ".."} for part in name.split("/"))
                                             for name in names):
            raise ValueError("bundle_project_wheel_paths")
        sources = {name for name in names if name.endswith(".py")}
        if sources != expected.keys() or any(archive.read(name) != value for name, value in expected.items()):
            raise ValueError("bundle_project_wheel_source_mismatch")
        info = f"cytellect-{project['version']}.dist-info/"
        if any(not name.startswith(info) and name not in expected for name in names):
            raise ValueError("bundle_project_wheel_extra_payload")
        metadata = email.parser.BytesParser().parsebytes(archive.read(info + "METADATA"))
        if (metadata["Name"] != "cytellect" or metadata["Version"] != project["version"] or
                set(metadata["Requires-Python"].replace(" ", "").split(",")) !=
                set(project["requires-python"].replace(" ", "").split(","))):
            raise ValueError("bundle_project_wheel_metadata")
        if (normalized_dependencies(metadata.get_all("Requires-Dist", [])) !=
                normalized_dependencies(project.get("dependencies", []))):
            raise ValueError("bundle_project_wheel_dependencies")
    dependency_bytes = requirements.read_bytes()
    dependencies = dependency_bytes.decode("utf-8")
    if not dependencies.strip() or "--hash=sha256:" not in dependencies or any(
        value in dependencies for value in ("file:", "-e ", "--editable", "--index-url", "--extra-index-url")
    ):
        raise ValueError("bundle_hashed_requirements_required")
    if dependency_bytes != canonical_requirements(root):
        raise ValueError("bundle_requirements_lock_mismatch")
    wheel_path = "wheels/" + filename
    requirement = f"./{wheel_path} --hash=sha256:{hashlib.sha256(data).hexdigest()}\n"
    locked = dependency_bytes + requirement.encode("utf-8")
    manifest = {"schema": "cytellect-windows-install/1", "requires_python": project["requires-python"],
                "wheel": {"path": wheel_path, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()},
                "requirements": {"path": INSTALL_REQUIREMENTS, "bytes": len(locked),
                                 "sha256": hashlib.sha256(locked).hexdigest()}}
    return {wheel_path: data, INSTALL_REQUIREMENTS: locked,
            INSTALL_MANIFEST: (json.dumps(manifest, indent=2) + "\n").encode("utf-8")}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="0.1.0-local.1")
    parser.add_argument("--runtime-data", type=Path, required=True,
                        help="Reviewed data-only Tcl/Tk ZIP produced on the release builder")
    parser.add_argument("--wheel", type=Path, required=True, help="Normal wheel built from this exact source")
    parser.add_argument("--requirements", type=Path, required=True,
                        help="Exact uv0.12.2 export --locked --no-dev --no-emit-project --no-header output")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    output = args.output.resolve()
    if root == output or root in output.parents:
        parser.error("Release ZIP must be outside the checkout")

    def git(*arguments: str) -> str:
        return subprocess.check_output(["git", "-c", f"safe.directory={root.as_posix()}",
                                        *arguments], cwd=root, text=True, encoding="utf-8").strip()

    if git("status", "--porcelain", "--untracked-files=all"):
        parser.error("Commit source changes before building a distributable release")
    commit = git("rev-parse", "HEAD")
    tracked = git("ls-files", "-z").split("\0")
    pnpm = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if pnpm is None:
        parser.error("Pinned pnpm must be installed on the release builder")
    subprocess.run([pnpm, "--filter", "@cytellect/web", "build:local"], cwd=root, check=True)
    if git("diff", "HEAD", "--name-only") or git("rev-parse", "HEAD") != commit:
        parser.error("Source changed during the Web build; review and commit before release")
    files = collect_files(root, tracked, root / "apps/web/out")
    from web_licenses import collect_notices

    notices, inventory = collect_notices(root)
    generated = {"THIRD_PARTY_WEB_NOTICES.txt": notices.encode("utf-8"),
                 "web-license-inventory.json": (json.dumps(inventory, indent=2) + "\n").encode("utf-8"),
                 RUNTIME_DATA: runtime_data(root, args.runtime_data.resolve())}
    generated.update(install_payload(root, args.wheel.resolve(), args.requirements.resolve()))
    print(json.dumps({"source_commit": commit,
                      "sha256": write_bundle(output, files, args.version, commit, generated),
                      "files": len(files), "bytes": output.stat().st_size}))


if __name__ == "__main__":
    main()

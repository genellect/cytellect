"""Build a source-pinned Windows setup ZIP; never package runtime or research data."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

ROOT_FILES = {"pyproject.toml", "uv.lock", "README.md", "README.ja.md", "LICENSE", "NOTICE"}
SOURCE_TREES = ("packages/analysis/src/", "services/api/src/", "services/worker/src/")
SCRIPTS = {"scripts/fiji_setup.py", "scripts/local_setup.ps1"}
DOCS = {"docs/oss.md", "docs/local.md", "docs/security.md", "docs/hosting-costs.ja.md"}
DATA_NOTICES = {"fixtures/public/allowlist.json"}
WEB_SUFFIXES = {".html", ".js", ".css", ".json", ".txt", ".svg", ".woff2", ".woff", ".ttf",
                ".ico", ".png", ".jpg", ".jpeg", ".webp"}


def source_allowed(name: str) -> bool:
    path = Path(name)
    if any(part.startswith(".") or part in {"__pycache__", "node_modules"} for part in path.parts):
        return False
    return (name in ROOT_FILES | SCRIPTS | DOCS | DATA_NOTICES
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
    required = ROOT_FILES | SCRIPTS | {"scripts/windows/Cytellect Setup.cmd"}
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
        if name in payloads or name not in {"THIRD_PARTY_WEB_NOTICES.txt", "web-license-inventory.json"}:
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--version", default="0.1.0-local.1")
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
                 "web-license-inventory.json": (json.dumps(inventory, indent=2) + "\n").encode("utf-8")}
    print(json.dumps({"source_commit": commit,
                      "sha256": write_bundle(output, files, args.version, commit, generated),
                      "files": len(files), "bytes": output.stat().st_size}))


if __name__ == "__main__":
    main()

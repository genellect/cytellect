"""Start the Microsoft Store (MSIX) edition (docs/windows-msix.md).

The package's manifest starts ``python\\pythonw.exe -B -E -m cytellect_api.packaged``. Every file
that runs is inside the read-only package: python.org's runtime with the locked wheels installed,
Fiji with its JDK and its pre-extracted native libraries, and the static workspace. Research data,
settings and the database stay in ``%LOCALAPPDATA%\\Cytellect`` (the installer's folder, so an
existing installation keeps its workspaces), which the manifest exempts from MSIX file-system
virtualization. Updates come from the Store; the in-app updater stays off because this is not an
installer-managed copy (``app_update.current_installation`` is ``None``).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import uuid
from collections.abc import Mapping
from pathlib import Path

PACKAGE_MARKER = "cytellect-package.json"
PACKAGE_SCHEMA = "cytellect-msix-package/1"
ROOT_MARKER = '{"product":"cytellect-local","schema":1}'
RETENTION = {"schema": "cytellect-local-retention/1", "mode": "manual"}

NOT_OWNED = ("作業データの保存先（%LOCALAPPDATA%\\Cytellect）に、Cytellect 以外のファイルがあります。"
             "既存のファイルを守るため、何も変更せずに終了します。PC の管理者にご相談ください。")
INCOMPLETE = "Cytellectのパッケージが不完全です。Microsoft Store から入れ直してください（データは保たれます）。"


class PackageError(Exception):
    """Fixed reasons; never a path or exception text."""


def package_root(prefix: str | Path | None = None) -> Path:
    """``<package>\\python`` is the interpreter's prefix; the package root holds the release."""
    return Path(prefix if prefix is not None else sys.prefix).absolute().parent


def read_package(root: Path) -> dict:
    try:
        marker = json.loads((root / PACKAGE_MARKER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PackageError("package_marker_missing") from None
    if not isinstance(marker, dict) or marker.get("schema") != PACKAGE_SCHEMA:
        raise PackageError("package_marker_missing")
    for key in ("fiji", "web"):
        value = marker.get(key)
        if (not isinstance(value, str) or not value or "\\" in value or ":" in value or value.startswith("/")
                or any(part in {"", ".", ".."} for part in value.split("/"))):
            raise PackageError("package_marker_missing")
    fiji, web = root / marker["fiji"], root / marker["web"]
    if not fiji.is_dir() or not (web / "index.html").is_file():
        raise PackageError("package_incomplete")
    return {**marker, "fiji_path": fiji, "web_path": web}


def data_root(environ: Mapping[str, str] | None = None) -> Path:
    """The installer's default folder, so both editions share one set of workspaces."""
    values: Mapping[str, str] = os.environ if environ is None else environ
    local = values.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(local) / "Cytellect"


def prepare_root(root: Path) -> Path:
    """Same ownership rule as the installer: an empty folder or one with Cytellect's marker.

    A fresh folder gets the marker (so the installer can use it later) and the installer's default
    retention choice: workspaces are kept until deleted. An existing installation keeps its choice.
    """
    marker = root / "setup-root.json"
    if root.exists():
        if root.is_symlink() or not root.is_dir():
            raise PackageError("install_directory_not_owned")
        if marker.is_file():
            try:
                owned = json.loads(marker.read_text(encoding="utf-8-sig")).get("product") == "cytellect-local"
            except (OSError, ValueError, AttributeError):
                owned = False
            if not owned:
                raise PackageError("install_directory_not_owned")
        elif any(root.iterdir()):
            raise PackageError("install_directory_not_owned")
    root.mkdir(parents=True, exist_ok=True)
    if not marker.exists():
        marker.write_text(ROOT_MARKER, encoding="utf-8")
    data = root / "data"
    settings = root / "settings"
    retention = settings / "retention.json"
    if not data.exists() and not retention.exists():
        settings.mkdir(exist_ok=True)
        staged = settings / f"retention-{uuid.uuid4().hex}.json"
        staged.write_text(json.dumps(RETENTION, separators=(",", ":")), encoding="utf-8")
        os.replace(staged, retention)
    data.mkdir(exist_ok=True)
    return data


def launch_arguments(package: dict, data: Path, extra: list[str]) -> list[str]:
    return ["--data-dir", str(data), "--web-dir", str(package["web_path"]), "--fiji", str(package["fiji_path"]),
            "--gui", *extra]


def main(argv: list[str] | None = None) -> None:
    from . import local

    local._null_missing_streams()
    parser = argparse.ArgumentParser(prog="cytellect packaged")
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--port", type=int)
    args = parser.parse_args(argv)
    extra = (["--no-browser"] if args.no_browser else []) + (["--port", str(args.port)] if args.port else [])
    try:
        package = read_package(package_root())
        data = prepare_root(data_root())
    except PackageError as error:
        local._report_startup_error(NOT_OWNED if str(error) == "install_directory_not_owned" else INCOMPLETE, True)
        raise SystemExit(2) from None
    except OSError:
        local._report_startup_error(local._gui_failure_message(RuntimeError()), True)
        raise SystemExit(2) from None
    local.main(launch_arguments(package, data, extra))


if __name__ == "__main__":
    main()

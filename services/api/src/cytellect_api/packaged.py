"""Start the Windows package with the existing single-user workspace."""
from __future__ import annotations

import json
import os
import re
import stat
import sys
from pathlib import Path

from . import local

PRODUCT = "cytellect-local"
STORE_ROOT_MARKER = {"product": PRODUCT, "schema": 1, "channel": "store"}


def _check_path(path: Path) -> None:
    try:
        info = path.lstat()
    except FileNotFoundError:
        return
    if (stat.S_ISLNK(info.st_mode)
            or getattr(info, "st_file_attributes", 0) & stat.FILE_ATTRIBUTE_REPARSE_POINT):
        raise ValueError("redirected_install_path")


def data_location(parent: Path) -> tuple[Path, bool]:
    """Preserve the installer workspace and its retention policy in place."""
    if not parent.is_absolute() or not parent.is_dir():
        raise ValueError("install_directory_not_owned")
    root = parent / "Cytellect"
    marker = root / "setup-root.json"
    data = root / "data"
    for path in (root, marker, data, root / "settings", data / "cytellect.sqlite",
                 data / "cytellect.sqlite-wal", data / "cytellect.sqlite-shm"):
        _check_path(path)
    root.mkdir(mode=0o700, exist_ok=True)
    if not marker.exists():
        if any(root.iterdir()):
            raise ValueError("install_directory_not_owned")
        try:
            with marker.open("x", encoding="ascii") as stream:
                json.dump(STORE_ROOT_MARKER, stream)
        except FileExistsError:
            pass
    if not marker.is_file() or marker.stat().st_size > 4096:
        raise ValueError("install_directory_not_owned")
    owner = json.loads(marker.read_text(encoding="utf-8-sig"))
    if not isinstance(owner, dict) or owner.get("product") != PRODUCT or owner.get("schema") != 1:
        raise ValueError("install_directory_not_owned")
    return data, owner.get("channel") == "store"


def main() -> None:
    local._null_missing_streams()
    root = Path(__file__).absolute().parents[4]
    try:
        version = json.loads((root / "store-package.json").read_text(encoding="utf-8"))["version"]
        if not re.fullmatch(r"[1-9][0-9]*\.[0-9]+\.[0-9]+\.0", version):
            raise ValueError("store_package_version_invalid")
        if not sys.flags.isolated or not sys.dont_write_bytecode:
            raise ValueError("store_python_not_isolated")
        if Path(sys.executable).parent != root / "python":
            raise ValueError("store_python_location_invalid")
        data, retain = data_location(Path(os.environ["LOCALAPPDATA"]))
    except (OSError, KeyError, ValueError, TypeError):
        local._report_startup_error("Cytellectの作業フォルダーを確認できません。Cytellectのサポートにお問い合わせください。", True)
        raise SystemExit(2) from None
    # The Store package owns its runtime and does not read developer overrides.
    for name in tuple(os.environ):
        if name.upper().startswith("CYTELLECT_") or name.upper() == "BROWSER":
            os.environ.pop(name, None)
    local.main(["--data-dir", str(data), "--web-dir", str(root / "apps/web/out"),
                "--fiji", str(root / "fiji"), "--gui"], store_version=version,
               retain_workspaces=retain)


if __name__ == "__main__":
    main()

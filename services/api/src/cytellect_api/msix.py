"""Store package entry point. No setup, downloads or provider credentials."""
from __future__ import annotations

import os
import sys
from pathlib import Path

from .config import Settings
from .local import _gui_failure_message, _report_startup_error, installed_source_revision, run_local
from .local_storage import child


def launch(package: Path, user_root: Path, *, gui: bool = True) -> None:
    # The manifest disables AppData write virtualization. This is the same data
    # root as the ZIP edition, outside the package's uninstall/update lifecycle.
    data = child(user_root.absolute(), "data")
    child(user_root.absolute(), "settings")
    fiji = package / "fiji"
    web = package / "apps/web/out"
    if not fiji.is_dir() or not (web / "index.html").is_file():
        raise ValueError("msix_payload_incomplete")
    os.environ["CYTELLECT_ENGINE_ASSETS"] = str(package / "engines/fiji")
    os.environ["CYTELLECT_CELLPOSE_ASSETS"] = str(package / "engines/cellpose")
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    os.environ.pop("CYTELLECT_CODE_REVISION", None)
    revision = installed_source_revision(package)
    if not revision:
        raise ValueError("msix_source_identity_invalid")
    os.environ["CYTELLECT_CODE_REVISION"] = revision
    settings = Settings(data, app_origin="http://127.0.0.1:8765", secure_cookies=False,
                        fiji_executable=str(fiji), workspace_retention_mode="manual")
    # Store creates a permanent manual-retention marker before opening the DB.
    # The existing local runtime lock also excludes simultaneous ZIP launches.
    run_local(settings, web, gui=gui, open_browser=gui)


def main() -> None:
    try:
        if sys.platform != "win32":
            raise ValueError("msix_windows_required")
        package = Path(sys.executable).resolve().parent.parent
        user_root = Path(os.environ["LOCALAPPDATA"]) / "Cytellect"
        launch(package, user_root)
    except Exception as exc:
        _report_startup_error(_gui_failure_message(exc), True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

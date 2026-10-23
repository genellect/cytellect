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
        if sys.argv[1:] == ["--diagnostic"]:
            # CI captures a fixed category only, never exception text or paths.
            category = type(exc).__name__
            if category not in {"ValueError", "ImportError", "ModuleNotFoundError", "PermissionError",
                                "OSError", "RuntimeError"}:
                category = "msix_startup_failed"
            print(category, file=sys.stderr)
            if exc.args and isinstance(exc.args[0], str) and exc.args[0] in {
                    "msix_payload_incomplete", "msix_source_identity_invalid", "local_runtime_already_in_use"}:
                print(exc.args[0], file=sys.stderr)
            raise SystemExit(1) from None
        _report_startup_error(_gui_failure_message(exc), True)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

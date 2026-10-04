"""Check the compiled local UI against the release packager's existing boundary."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path

from build_local_bundle import collect_files


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z"], cwd=root
    ).decode().strip("\0").split("\0")
    files = collect_files(root, tracked, root / "apps/web/out")
    print(json.dumps({"local_web_bundle_boundary": "passed", "files": len(files)}))


if __name__ == "__main__":
    main()

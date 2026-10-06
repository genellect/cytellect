"""Classify a pull request as documentation-only or code for CI job selection.

Pushes to main and manual runs always count as code, so every main commit keeps
the full required evidence that Windows releases depend on.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import PurePosixPath

DOC_FILES = {"LICENSE", "NOTICE"}


def is_documentation(path: str) -> bool:
    parts = PurePosixPath(path).parts
    if not parts:
        return False
    if parts[0] == "docs":
        return True
    # Root-level Markdown only; Markdown elsewhere can be packaged or rendered.
    return len(parts) == 1 and (path in DOC_FILES or path.endswith(".md"))


def code_changed(paths: list[str]) -> bool:
    # An empty or unreadable diff runs everything.
    return not paths or not all(is_documentation(path) for path in paths)


def main() -> None:
    event = os.environ.get("EVENT", "")
    base, head = os.environ.get("BASE", ""), os.environ.get("HEAD", "")
    if event != "pull_request" or not base or not head:
        code = True
    else:
        diff = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                              capture_output=True, text=True, check=False)
        code = diff.returncode != 0 or code_changed([p for p in diff.stdout.splitlines() if p])
    print(f"code={'true' if code else 'false'}")
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write(f"code={'true' if code else 'false'}\n")


if __name__ == "__main__":
    sys.exit(main())

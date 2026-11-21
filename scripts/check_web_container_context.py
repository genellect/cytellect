"""Check that the production web container copies every repository file the web build imports.

`next build` type-checks all of apps/web, tests included, but infra/Dockerfile.web copies only
selected paths. The container is built only after merge (fiji-browser), so the web job runs this
check on each pull request: a relative import that leaves the copied trees fails here.
"""
from __future__ import annotations

import json
import posixpath
import re
import subprocess
import sys
from pathlib import Path

DOCKERFILE = "infra/Dockerfile.web"
# Trees whose source the web build compiles; public/ holds served assets, not modules.
SOURCE_ROOTS = ("apps/web/", "packages/contracts/")
SKIPPED = ("apps/web/public/",)
SOURCE_SUFFIXES = (".ts", ".tsx", ".mts", ".cts", ".js", ".jsx", ".mjs", ".cjs")
IMPORT = re.compile(r"""(?:\bfrom\s*|\bimport\s*\(\s*|\bimport\s+|\brequire\s*\(\s*)["'](\.\.?/[^"']+)["']""")


def copied_sources(dockerfile: str) -> list[str]:
    """Build-context paths that COPY places in the image (copies from other stages excluded)."""
    sources = []
    for line in dockerfile.splitlines():
        words = line.split()
        if not words or words[0].upper() != "COPY" or any(w.startswith("--from") for w in words[1:]):
            continue
        sources.extend(posixpath.normpath(w) for w in words[1:-1] if not w.startswith("--"))
    return sources


def missing_imports(root: Path, dockerfile: str, files: list[str]) -> list[tuple[str, str]]:
    """(file, import) pairs whose target lies outside every copied path."""
    copied = copied_sources(dockerfile)
    missing = []
    for name in files:
        if not name.startswith(SOURCE_ROOTS) or name.startswith(SKIPPED) or not name.endswith(SOURCE_SUFFIXES):
            continue
        path = root / name
        if not path.is_file():  # tracked but deleted in the working tree
            continue
        text = path.read_text(encoding="utf-8")
        for specifier in IMPORT.findall(text):
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), specifier))
            if not any(target == source or target.startswith(source + "/") for source in copied):
                missing.append((name, specifier))
    return missing


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.check_output(
        ["git", "-c", f"safe.directory={root.as_posix()}", "ls-files", "-z", "--", *SOURCE_ROOTS], cwd=root
    ).decode().strip("\0").split("\0")
    missing = missing_imports(root, (root / DOCKERFILE).read_text(encoding="utf-8"), tracked)
    if missing:
        for name, specifier in missing:
            print(f"{name}: {specifier}", file=sys.stderr)
        sys.exit(f"{DOCKERFILE} does not copy {len(missing)} imported path(s); add a COPY line for each")
    print(json.dumps({"web_container_context": "passed", "tracked_files": len(tracked)}))


if __name__ == "__main__":
    main()

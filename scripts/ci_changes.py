"""Select CI job areas from the files a pull request changes.

Areas: python (Linux lint/types/tests/SBOM), web (contracts, Next.js, proposal
Worker, public-site browser tests), fiji (real Fiji, API/browser workflow,
containers), windows (Windows setup/launcher and Python 3.14 suite).

Pushes to main, manual runs, an unreadable diff and any path not listed below
select every area, so each main commit keeps the full evidence the Windows
release workflow requires. Hygiene checks (public tree, documentation links,
secret scan) always run.
"""
from __future__ import annotations

import os
import subprocess
import sys
from fnmatch import fnmatchcase

AREAS = ("python", "web", "fiji", "windows")
ALL = frozenset(AREAS)
PY_STACK = frozenset({"python", "web", "fiji", "windows"})  # API/analysis feed contracts and every runtime

# First matching pattern wins. Order from specific to general.
RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("docs/*", frozenset()),
    ("LICENSE", frozenset()),
    ("NOTICE", frozenset()),
    ("apps/web/scripts/*", frozenset({"web", "fiji", "windows"})),
    ("apps/web/*", frozenset({"web", "fiji"})),
    ("packages/contracts/*", frozenset({"web", "fiji"})),
    ("services/proposal-worker/*", frozenset({"web"})),
    ("packages/analysis/*", PY_STACK),
    ("services/api/*", PY_STACK),
    ("services/worker/*", PY_STACK),
    ("engines/fiji/*", frozenset({"python", "fiji", "windows"})),
    ("engines/python/*", frozenset({"python", "windows"})),
    ("scripts/windows/*", frozenset({"python", "windows"})),
    ("scripts/*.ps1", frozenset({"python", "windows"})),
    ("scripts/*", frozenset({"python", "fiji", "windows"})),
    ("tests/*", frozenset({"python", "fiji", "windows"})),
    ("validation/*", frozenset({"python"})),
    ("infra/*", frozenset({"python", "fiji"})),
    ("compose.yaml", frozenset({"python", "fiji"})),
)


def areas_for(path: str) -> frozenset[str]:
    if "/" not in path and path.endswith(".md"):
        return frozenset()
    for pattern, areas in RULES:
        if fnmatchcase(path, pattern):
            return areas
    return ALL  # workflows, lockfiles, manifests and anything unlisted


def select(paths: list[str]) -> frozenset[str]:
    if not paths:
        return ALL
    selected: set[str] = set()
    for path in paths:
        selected |= areas_for(path)
    return frozenset(selected)


def main() -> None:
    event = os.environ.get("EVENT", "")
    base, head = os.environ.get("BASE", ""), os.environ.get("HEAD", "")
    if event != "pull_request" or not base or not head:
        selected = ALL
    else:
        diff = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                              capture_output=True, text=True, check=False)
        selected = ALL if diff.returncode else select([p for p in diff.stdout.splitlines() if p])
    lines = [f"{area}={'true' if area in selected else 'false'}" for area in AREAS]
    print("\n".join(lines))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())

"""Select CI job areas from the files a pull request changes.

Areas: python (Linux lint/types/tests/SBOM), web (contracts, Next.js, proposal
Worker, public-site browser tests), lp (the landing page only: Next.js checks and
build, landing-page browser tests), fiji (real Fiji, API/browser workflow,
containers), windows (Windows setup/launcher and Python 3.14 suite). The web job
already runs the landing-page tests, so lp is dropped whenever web is selected.

Registering a documentation image (an allowlist entry under docs/) is part of the
documentation change and selects nothing.

Pushes to main, manual runs (the batch verification before merging), an unreadable diff and any
path not listed below select every area, so each main commit keeps the full evidence the Windows
release workflow requires. Hygiene checks (public tree, documentation links,
secret scan) always run.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from fnmatch import fnmatchcase

AREAS = ("python", "web", "lp", "fiji", "windows")
ALL = frozenset(AREAS) - {"lp"}  # the web job already covers the landing page
PY_STACK = frozenset({"python", "web", "fiji", "windows"})  # API/analysis feed contracts and every runtime

# First matching pattern wins. Order from specific to general.
RULES: tuple[tuple[str, frozenset[str]], ...] = (
    ("docs/*", frozenset()),
    (".github/*.md", frozenset()),  # pull-request and issue templates; workflows and other settings stay unlisted
    ("LICENSE", frozenset()),
    ("NOTICE", frozenset()),
    ("apps/web/scripts/*", frozenset({"web", "fiji", "windows"})),
    # The public landing page is covered by the landing-page browser tests; its media
    # also ship in the Windows bundle, whose boundary the Python suite checks.
    ("apps/web/public/marketing/*", frozenset({"python", "lp"})),
    ("apps/web/public/lp-metrics*", frozenset({"lp"})),
    ("apps/web/src/components/PublicLanding.tsx", frozenset({"lp"})),
    ("apps/web/src/components/Landing*.tsx", frozenset({"lp"})),
    ("apps/web/src/components/HeroFilm.tsx", frozenset({"lp"})),
    ("apps/web/src/components/optical-landing.module.css", frozenset({"lp"})),
    ("apps/web/tests/marketing.spec.ts", frozenset({"lp"})),
    ("apps/web/tests/lp-*.spec.ts", frozenset({"lp"})),
    ("apps/web/*", frozenset({"web", "fiji"})),
    ("packages/contracts/*", frozenset({"web", "fiji"})),
    ("services/proposal-worker/*", frozenset({"web"})),
    ("packages/analysis/*", PY_STACK),
    ("services/api/*", PY_STACK),
    ("services/worker/*", PY_STACK),
    ("engines/fiji/*", frozenset({"python", "fiji", "windows"})),
    ("engines/python/*", frozenset({"python", "windows"})),
    # Installer script, preflight and CI smoke; the compiled installer runs on main (windows-installer).
    ("packaging/*", frozenset({"python", "windows"})),
    ("scripts/windows/*", frozenset({"python", "windows"})),
    ("scripts/lp_film/*", frozenset()),  # offline hero-film authoring; CI never runs it
    ("scripts/*.ps1", frozenset({"python", "windows"})),
    # The web job checks the compiled local UI against this packager's boundary.
    ("scripts/build_local_bundle.py", PY_STACK),
    ("scripts/check_local_web_bundle.py", PY_STACK),
    ("scripts/*", frozenset({"python", "fiji", "windows"})),
    ("tests/*", frozenset({"python", "fiji", "windows"})),
    ("validation/*", frozenset({"python"})),
    ("fixtures/public/allowlist.json", frozenset({"python", "lp"})),
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


REGISTRY = "fixtures/public/allowlist.json"


def documentation_registry_change(old: dict, new: dict) -> bool:
    """True when every added, removed or changed allowlist entry is a documentation file."""
    changed = {key for key in old.keys() | new.keys() if old.get(key) != new.get(key)}
    return bool(changed) and all(key.startswith("docs/") for key in changed)


def _registry(revision: str) -> dict | None:
    shown = subprocess.run(["git", "show", f"{revision}:{REGISTRY}"], capture_output=True, text=True, check=False)
    if shown.returncode:
        return None
    try:
        loaded = json.loads(shown.stdout)
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def normalize(selected: frozenset[str]) -> frozenset[str]:
    """The web job includes the landing-page tests, so lp runs only without web."""
    return selected - {"lp"} if "web" in selected else selected


def select(paths: list[str]) -> frozenset[str]:
    if not paths:
        return ALL
    selected: set[str] = set()
    for path in paths:
        selected |= areas_for(path)
    return normalize(frozenset(selected))


def select_changes(paths: list[str], documentation_registry: bool) -> frozenset[str]:
    """Select areas for a readable diff; a documentation-only registry change counts as documentation."""
    if documentation_registry and REGISTRY in paths:
        rest = [path for path in paths if path != REGISTRY]
        return select(rest) if rest else frozenset()
    return select(paths)


def main() -> None:
    event = os.environ.get("EVENT", "")
    base, head = os.environ.get("BASE", ""), os.environ.get("HEAD", "")
    if event != "pull_request" or not base or not head:
        selected = ALL
    else:
        diff = subprocess.run(["git", "diff", "--name-only", f"{base}...{head}"],
                              capture_output=True, text=True, check=False)
        paths = [p for p in diff.stdout.splitlines() if p]
        documentation_registry = False
        if not diff.returncode and REGISTRY in paths:
            merge_base = subprocess.run(["git", "merge-base", base, head], capture_output=True, text=True, check=False)
            old, new = _registry(merge_base.stdout.strip() or base), _registry(head)
            documentation_registry = old is not None and new is not None and documentation_registry_change(old, new)
        selected = ALL if diff.returncode else select_changes(paths, documentation_registry)
    lines = [f"{area}={'true' if area in selected else 'false'}" for area in AREAS]
    print("\n".join(lines))
    output = os.environ.get("GITHUB_OUTPUT")
    if output:
        with open(output, "a", encoding="utf-8") as stream:
            stream.write("\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())

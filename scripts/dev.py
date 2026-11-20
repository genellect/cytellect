"""Single entry point for local setup and the checks pull-request CI runs.

Standard library only, so it runs before `uv sync` and on Windows:

    python3 scripts/dev.py setup [--fiji DIR] [--cellpose DIR]
    python3 scripts/dev.py check [python] [web] [--related | --changed] [--base REF] [--fiji]
    python3 scripts/dev.py changed [--base REF]
    python3 scripts/dev.py contracts
    python3 scripts/dev.py audit [--out DIR]
    python3 scripts/dev.py doctor [--live | --proposal-version]
    python3 scripts/dev.py serve [--data-dir DIR] [--skip-build]
    python3 scripts/dev.py public-inputs [DATASET ...] [--out DIR]

`check` runs the same commands as the `python` and `web` jobs in
.github/workflows/ci.yml; tests/test_dev_commands.py fails when the two drift.
`changed` and `check --changed` pick the areas from the changed files with the
rules pull-request CI uses (scripts/ci_changes.py). `check --related` is the short
local loop: lint, types, and only the tests that import or name the changed files
(scripts/related_tests.py); pull-request CI still runs everything.
Browser, container and Windows-installer checks stay CI-only (see docs/ci.md).

`serve` runs the analysis screen as installations do (API, worker, production web
build) for testing with registered public images; `doctor` reports whether Fiji,
the cloud GPU and the analysis-proposal service are ready for it.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from ci_changes import AREAS, REGISTRY, documentation_registry_change, select_changes
from related_tests import related_tests

ROOT = Path(__file__).resolve().parents[1]
API_ORIGIN = "http://localhost:8000"
APP_ORIGIN = "http://localhost:3000"
# The deployed Modal server (infra/modal_cellpose.py, Cellpose Modal deploy workflow); authentication required.
MODAL_CELLPOSE_URL = "https://genellect--cytellect-cellpose-cellposeserver.us-east.modal.direct"
USER_AGENT = "cytellect-dev"  # Cloudflare refuses Python's default agent (error 1010)
# Where scripts/linux_setup.sh provisions pinned tools and Fiji (its env.sh exports them).
DEV_RUNTIME = Path.home() / ".local/share/cytellect-dev"
# Keys kept on a development machine (CONTRIBUTING.md, 外部サービス); env.sh loads it.
KEY_FILE = Path.home() / ".config/cytellect/dev.env"
# `doctor --owner`: the owner's operations (CONTRIBUTING.md, オーナーの環境). Read-only calls only.
OWNER = "genellect"
REPOSITORY = "genellect/cytellect"
CLOUDFLARE_VERIFY_URL = "https://api.cloudflare.com/client/v4/user/tokens/verify"
HUGGING_FACE_WHOAMI_URL = "https://huggingface.co/api/whoami-v2"
VERCEL_USER_URL = "https://api.vercel.com/v2/user"
# In a cloud session the environment's network secret replaces this header value at the proxy.
CREDENTIAL_PLACEHOLDER = "placeholder-replaced-by-network-secret"
CONTRACT_OUTPUTS = ("packages/contracts", "apps/web/src/lib/generated.ts", "apps/web/src/lib/recipe-defaults.json")
OPENAPI = ("uv", "run", "cytellect", "openapi", "--output", "packages/contracts/openapi.json",
           "--recipe-defaults", "apps/web/src/lib/recipe-defaults.json")

# The committed contracts match the API (the first steps of the web job).
CONTRACT_CHECKS: tuple[tuple[str, ...], ...] = (
    OPENAPI,
    ("pnpm", "contracts"),
    ("git", "diff", "--exit-code", "--", *CONTRACT_OUTPUTS),
)
WEB_CHECK = ("pnpm", "check")
WORKER_CHECK = ("pnpm", "--filter", "@cytellect/proposal-worker", "check")
# The checks each pull-request CI area runs, in CI order.
RUFF = ("uv", "run", "ruff", "check", ".")
MYPY = ("uv", "run", "mypy", "packages/analysis/src", "services")
# The whole suite as parallel shards on this machine (scripts/run_test_shards.py).
PYTEST = ("uv", "run", "python", "scripts/run_test_shards.py", "tests", "-m", "not fiji")
CHECKS: dict[str, tuple[tuple[str, ...], ...]] = {
    "python": (
        RUFF,
        MYPY,
        ("uv", "run", "python", "scripts/generate_planning_fixtures.py", "--check"),
        PYTEST,
        ("uv", "run", "python", "scripts/check_public_tree.py"),
        ("uv", "run", "python", "scripts/check_docs.py"),
        ("uv", "run", "python", "scripts/proposal_schema.py", "--check"),
    ),
    "web": (
        *CONTRACT_CHECKS,
        WEB_CHECK,
        ("pnpm", "test"),
        WORKER_CHECK,
        ("pnpm", "--filter", "@cytellect/proposal-worker", "test"),
        ("pnpm", "--filter", "@cytellect/proposal-worker", "test:deployment"),
        ("node", "--test", "apps/web/scripts/finalize-local-export.test.mjs"),
        ("pnpm", "build"),
        ("pnpm", "--filter", "@cytellect/web", "build:local"),
        ("uv", "run", "python", "scripts/check_local_web_bundle.py"),
    ),
}
RELATED_PYTEST = ("uv", "run", "pytest")
FIJI_CHECK = ("uv", "run", "pytest", "-m", "fiji")
# The landing-page job without its browser tests, which stay in CI (tests/test_dev_commands.py compares both).
LP_CHECKS: tuple[tuple[str, ...], ...] = (WEB_CHECK, ("pnpm", "test"), ("pnpm", "build"))
# What the python job runs on every change, documentation-only ones included (docs/ci.md, ジョブの選び方).
DOC_CHECKS: tuple[tuple[str, ...], ...] = (
    ("uv", "run", "python", "scripts/check_docs.py"),
    ("uv", "run", "python", "scripts/check_public_tree.py"),
)


def run(argv: tuple[str, ...] | list[str], env: dict[str, str] | None = None, ok: tuple[int, ...] = (0,)) -> None:
    print("$ " + shlex.join(argv), flush=True)
    executable = shutil.which(argv[0])
    if executable is None:
        sys.exit(f"{argv[0]} is not installed; see CONTRIBUTING.md for the required tools")
    result = subprocess.run([executable, *argv[1:]], cwd=ROOT, env=env)
    if result.returncode not in ok:
        sys.exit(f"Failed ({result.returncode}): {shlex.join(argv)}")


def outside_checkout(path: Path, label: str) -> Path:
    resolved = path.expanduser().resolve()
    if resolved == ROOT or ROOT in resolved.parents:
        sys.exit(f"{label} must be outside the checkout: {resolved}")
    return resolved


def scratch_env(data_dir: Path) -> dict[str, str]:
    return {**os.environ, "CYTELLECT_DATA_DIR": str(data_dir)}


def setup(args: argparse.Namespace) -> None:
    run(("uv", "sync", "--locked", "--dev"))
    run(("pnpm", "install", "--frozen-lockfile"))
    exports = []
    if args.fiji:
        fiji = outside_checkout(args.fiji, "Fiji runtime")
        if not fiji.exists():
            run(("uv", "run", "python", "scripts/fiji_setup.py", str(fiji)))  # platform follows the OS
        exports.append(f"CYTELLECT_FIJI_EXECUTABLE={shlex.quote(str(fiji))}")
    if args.cellpose:
        cellpose = outside_checkout(args.cellpose, "Cellpose runtime")
        python = subprocess.run(["uv", "python", "find", "3.12"], cwd=ROOT, capture_output=True, text=True)
        if python.returncode:
            sys.exit("Cellpose needs a Python 3.12 interpreter: run `uv python install 3.12` first")
        runtime, models = cellpose / "runtime", cellpose / "models"
        run(("uv", "run", "python", "scripts/cellpose_setup.py", str(runtime), "--model-cache", str(models),
             "--python", python.stdout.strip()))
        executable = runtime / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        exports += [f"CYTELLECT_CELLPOSE_PYTHON={shlex.quote(str(executable))}",
                    f"CYTELLECT_CELLPOSE_MODEL_DIR={shlex.quote(str(models))}"]
    if exports:
        print("\nSet these for `cytellect serve`, `cytellect-worker` and `check --fiji`:")
        print("export " + " ".join(exports))


def changed_paths(base: str) -> list[str]:
    """Files that differ from `base`: this branch's commits, staged and unstaged edits, untracked files."""
    paths: set[str] = set()
    for argv in (("git", "diff", "--name-only", f"{base}...HEAD"), ("git", "diff", "--name-only", "HEAD"),
                 ("git", "ls-files", "--others", "--exclude-standard")):
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
        if result.returncode:
            sys.exit(f"Cannot list changes against {base}: {result.stderr.strip()} (run `git fetch origin main`)")
        paths.update(line for line in result.stdout.splitlines() if line)
    return sorted(paths)


def _registry_at(revision: str) -> dict | None:
    shown = subprocess.run(["git", "show", f"{revision}:{REGISTRY}"], cwd=ROOT, capture_output=True, text=True)
    try:
        loaded = json.loads(shown.stdout) if not shown.returncode else None
    except json.JSONDecodeError:
        return None
    return loaded if isinstance(loaded, dict) else None


def changed_areas(paths: list[str], base: str = "origin/main") -> frozenset[str]:
    """The pull-request CI areas for these files (scripts/ci_changes.py); none for no files or documentation only."""
    if not paths:
        return frozenset()
    documentation_registry = False
    if REGISTRY in paths:
        merge_base = subprocess.run(["git", "merge-base", base, "HEAD"], cwd=ROOT, capture_output=True, text=True)
        old = _registry_at(merge_base.stdout.strip() or base)
        try:
            new = json.loads((ROOT / REGISTRY).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            new = None
        documentation_registry = isinstance(old, dict) and isinstance(new, dict) and documentation_registry_change(old, new)
    return select_changes(paths, documentation_registry)


def changed(args: argparse.Namespace) -> None:
    paths = changed_paths(args.base)
    print(f"Changed files against {args.base} and the working tree: {len(paths)}")
    for path in paths:
        print(f"  {path}")
    areas = changed_areas(paths, args.base)
    print("CI areas: " + (", ".join(area for area in AREAS if area in areas) or "none (documentation only)"))
    tests = related_tests(ROOT, paths) if paths else []
    print("Related Python tests: " + ("all (the test configuration changed)" if tests is None
                                      else f"{len(tests)}" + "".join(f"\n  {test}" for test in tests)))


def related_commands(paths: list[str], selected: frozenset[str],
                     tests: list[str] | None) -> list[tuple[str, ...]]:
    """The short local loop for a change: lint and types, the related tests, contracts and documents."""
    def under(*prefixes: str) -> list[str]:
        return [path for path in paths if path.startswith(prefixes)]

    commands: list[tuple[str, ...]] = []
    python = [path for path in paths if path.endswith(".py")]
    if python or "python" in selected:
        commands.append(RUFF)
    if any(path.startswith(("packages/analysis/src/", "services/")) for path in python):
        commands.append(MYPY)
    if tests is None:
        commands.append(PYTEST)
    elif tests:
        commands.append((*RELATED_PYTEST, *tests, "-m", "not fiji"))
    if "web" in selected and under("services/api/", "packages/analysis/", "packages/contracts/"):
        commands += CONTRACT_CHECKS
    web, worker = under("apps/web/"), under("services/proposal-worker/")
    if web:
        commands.append(WEB_CHECK)
    for package, directory, changed_here in (("@cytellect/web", "apps/web/", web),
                                             ("@cytellect/proposal-worker", "services/proposal-worker/", worker)):
        sources = [path[len(directory):] for path in changed_here if (ROOT / path).is_file()]
        if sources:
            commands.append(("pnpm", "--filter", package, "exec", "vitest", "related", "--run",
                             "--passWithNoTests", *sources))
    if worker:
        commands.append(WORKER_CHECK)
    return [*commands, *DOC_CHECKS]


def check(args: argparse.Namespace) -> None:
    extra: tuple[tuple[str, ...], ...] = ()
    if sum((bool(args.areas), args.changed, args.related)) > 1:
        sys.exit("Give areas, --changed or --related: only one of them")
    if args.base != "origin/main" and not (args.changed or args.related):
        sys.exit("--base needs --related or --changed")
    if args.related:
        paths = changed_paths(args.base)
        selected = changed_areas(paths, args.base)
        tests = related_tests(ROOT, paths) if paths else []
        areas, extra = [], tuple(related_commands(paths, selected, tests))
        print("Related Python tests: " + ("all (the test configuration changed)" if tests is None else str(len(tests))))
        print("Left to pull-request CI: the full suites of " + (", ".join(a for a in AREAS if a in selected) or "no area"))
    elif args.changed:
        selected = changed_areas(changed_paths(args.base), args.base)
        areas = [area for area in CHECKS if area in selected]
        # The web job covers the landing page, so lp is selected only without web. The python
        # area already runs the document checks; every other selection gets them here.
        extra = (LP_CHECKS if "lp" in selected else ()) + (() if "python" in areas else DOC_CHECKS)
        label = ", ".join(areas + (["lp (without its browser tests)"] if "lp" in selected else [])) or (
            "none (documentation only)" if not selected else "none")
        print("Local areas: " + label)
        ci_only = [area for area in AREAS if area in selected and area not in CHECKS]
        if ci_only:
            print("Left to pull-request CI: " + ", ".join(ci_only))
    else:
        areas = args.areas or list(CHECKS)
    unknown = sorted(set(areas) - set(CHECKS))
    if unknown:
        sys.exit(f"Unknown area: {', '.join(unknown)} (choose from {', '.join(CHECKS)})")
    if "python" in areas:
        ensure_figure_font()
    if args.fiji:
        ensure_fiji()
    with tempfile.TemporaryDirectory(prefix="cytellect-check-") as scratch:
        env = scratch_env(Path(scratch))
        for area in areas:
            for argv in CHECKS[area]:
                run(argv, env)
        for argv in extra:
            # Related modules whose tests all need Fiji leave nothing to run (pytest exit 5): not a failure.
            run(argv, env, ok=(0, 5) if args.related and argv[:3] == RELATED_PYTEST else (0,))
        if args.fiji:
            run(FIJI_CHECK, env)
    print("All selected checks passed.")


def contracts(_: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="cytellect-contracts-") as scratch:
        env = scratch_env(Path(scratch))
        run(OPENAPI, env)
        run(("pnpm", "contracts"), env)
    print("Commit packages/contracts/openapi.json, recipe-defaults.json and generated.ts together.")


# Registered public images for trying the screens by hand (fixtures/public holds each source and license).
PUBLIC_INPUTS = {
    "bbbc007": "DNA and actin, one field: nucleus detection and the workspace browser tests (CC0)",
    "bbbc013": "DRAQ and FKHR-EGFP, three fields: channel gates, positive fraction and area-only (in the checkout)",
    "jump-plk1": "PLK1 knockout and control, three runs: group comparison (about 400 MB, CC0)",
    "nucleolar": "DAPI and NCL source image of the nucleolus validation (docs/public-nucleolar-validation.md)",
}


def public_inputs(args: argparse.Namespace) -> None:
    """Fetch and verify registered public images with the scripts the tests use; nothing else is downloaded."""
    unknown = sorted(set(args.datasets) - set(PUBLIC_INPUTS))
    if unknown:
        sys.exit(f"Unknown dataset: {', '.join(unknown)} (choose from {', '.join(PUBLIC_INPUTS)})")
    out = outside_checkout(args.out, "Public inputs")
    places = {}
    for dataset in args.datasets or ["bbbc007"]:
        target = out / dataset
        if dataset == "bbbc007":  # the browser-e2e job's preparation
            target = out / "workspace-inputs"
            run(("uv", "run", "python", "scripts/public_bbbc007.py", "--data-dir", str(out / "bbbc007"), "--download"))
            run(("uv", "run", "python", "scripts/prepare_workspace_bbbc007.py", "--data-dir", str(out / "bbbc007"),
                 "--output", str(target)))
            run(("uv", "run", "python", "scripts/check_public_uploads.py", str(target)))
        elif dataset == "bbbc013":
            target = ROOT / "fixtures/public/bbbc013"
        elif dataset == "jump-plk1":
            run(("uv", "run", "python", "scripts/public_jump_plk1.py", "--output", str(target)))
        else:
            run(("uv", "run", "python", "scripts/public_nucleolar.py", "--data-dir", str(target)))
        places[dataset] = target
    for dataset, target in places.items():
        print(f"{dataset}: {target}\n  {PUBLIC_INPUTS[dataset]}")


def audit(args: argparse.Namespace) -> None:
    out = outside_checkout(args.out, "Audit output") if args.out else Path(tempfile.mkdtemp(prefix="cytellect-audit-"))
    out.mkdir(parents=True, exist_ok=True)
    cache = out / "security-tools"
    run(("uv", "run", "python", "scripts/sbom.py", "--output", str(out / "dependency-inventory.json"),
         "--web-notices", str(out / "THIRD_PARTY_WEB_NOTICES.txt")))
    run(("uv", "run", "pip-audit", "--local", "--format", "cyclonedx-json", "--output", str(out / "python.cdx.json")))
    run(("pnpm", "audit", "--prod", "--audit-level", "high"))
    run(("uv", "run", "python", "scripts/scan_secrets.py", "--repo", ".", "--cache-dir", str(cache),
         "--output", str(out / "secrets.json")))
    print(f"Audit reports: {out}")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Never resend a credential to another location."""

    def redirect_request(self, *args, **kwargs):  # type: ignore[no-untyped-def]
        return None


def probe(request: urllib.request.Request, timeout: float) -> tuple[int, str]:
    """HTTP status and the service's error code, or (0, "unreachable"). Bodies are not printed."""
    request.add_header("User-Agent", USER_AGENT)
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout) as response:
            status, body = response.status, response.read(4096)
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read(4096)
    except (urllib.error.URLError, OSError):
        return 0, "unreachable"
    try:
        payload = json.loads(body)
    except ValueError:
        payload = None
    code = (payload.get("code") or payload.get("error") or "") if isinstance(payload, dict) else ""
    return status, code if isinstance(code, str) and len(code) < 80 else ""


def proposal_state(status: int, code: str) -> tuple[bool, str]:
    """Meaning of an authenticated empty proposal request; the service rejects `{}` before any model call."""
    if status == 400 and code == "request_invalid":
        return True, "device token accepted and proposals enabled (no model call was made)"
    if status == 401:
        return False, "device token rejected: issue a new invitation (docs/proposal-service.md)"
    if status == 503 and code in {"proposal_service_disabled", "budget_reconciliation_required"}:
        return False, f"service refuses proposals: {code}"
    return False, f"unexpected response {status or 'none'} {code}".rstrip()


def cellpose_state(status: int) -> tuple[bool, str]:
    if status == 200:
        return True, "connection key accepted; the GPU server answered"
    if status in (401, 403):
        return False, "connection key rejected: use the Modal proxy token as `wk-….ws-…` (docs/cloud-gpu.ja.md)"
    if status in (502, 503, 504):
        return False, (f"GPU server unavailable ({status}): starting (about 3 minutes), waiting for Modal GPU "
                       "capacity, stopped or out of budget; check the app in Modal")
    return False, f"unexpected response {status or 'none'}"


def proposal_token() -> str:
    path = os.environ.get("CYTELLECT_PROPOSAL_TOKEN_FILE", "")
    if path:
        try:
            return Path(path).expanduser().read_text(encoding="ascii").strip()
        except (OSError, UnicodeError):
            return ""
    return os.environ.get("CYTELLECT_PROPOSAL_TOKEN", "").strip()


def cloud_env(base: dict[str, str]) -> dict[str, str]:
    """Cloud GPU settings from a Modal proxy token stored as its two parts (ID `wk-…`, secret `ws-…`).

    The analysis engine reads one bearer value, `ID.secret` (docs/cloud-gpu.ja.md); explicit
    CYTELLECT_CELLPOSE_REMOTE_* values take precedence.
    """
    env = dict(base)
    key, secret = env.get("CYTELLECT_MODAL_PROXY_KEY", "").strip(), env.get("CYTELLECT_MODAL_PROXY_SECRET", "").strip()
    if key and secret and not env.get("CYTELLECT_CELLPOSE_REMOTE_TOKEN"):
        env["CYTELLECT_CELLPOSE_REMOTE_TOKEN"] = f"{key}.{secret}"
    if key and env.get("CYTELLECT_CELLPOSE_REMOTE_TOKEN") and not env.get("CYTELLECT_CELLPOSE_REMOTE_URL"):
        env["CYTELLECT_CELLPOSE_REMOTE_URL"] = MODAL_CELLPOSE_URL
    return env


def figure_font() -> str:
    """The face the figure code selects (any Japanese font is not enough); empty when there is none."""
    return tool_version(("uv", "run", "--project", str(ROOT), "--no-sync", "python", "-c",
                         "from cytellect_analysis.figures import japanese_font; print(japanese_font())"))


def ensure_figure_font() -> None:
    """Linux: install the Japanese figure font on first use, for figures and their tests."""
    if not sys.platform.startswith("linux") or figure_font():
        return
    print("Installing the Japanese figure font (first use)", flush=True)
    run(("bash", "scripts/install_figure_font.sh"))
    if not figure_font():
        sys.exit("The Japanese figure font is still unavailable (see CONTRIBUTING.md)")


def ensure_fiji() -> str:
    """Fiji for `serve`, `check --fiji` and `e2e`: the configured one, installed on first use (pinned, hash-checked)."""
    fiji = fiji_path() or (str(DEV_RUNTIME / "fiji") if DEV_RUNTIME.exists() else "")
    if not fiji:
        sys.exit("Fiji is not set up: run `bash scripts/linux_setup.sh` (Linux) or `setup --fiji DIR` "
                 "and export CYTELLECT_FIJI_EXECUTABLE")
    path = outside_checkout(Path(fiji).expanduser(), "Fiji runtime")
    if not path.exists():
        print(f"Installing the pinned Fiji in {path} (first use, about a minute)", flush=True)
        run(("uv", "run", "python", "scripts/fiji_setup.py", str(path)))
    os.environ["CYTELLECT_FIJI_EXECUTABLE"] = str(path)
    return str(path)


def fiji_path() -> str:
    """CYTELLECT_FIJI_EXECUTABLE, else the cloud setup's Fiji, so a shell without env.sh still finds it."""
    configured = os.environ.get("CYTELLECT_FIJI_EXECUTABLE", "")
    if configured:
        return configured
    provisioned = DEV_RUNTIME / "fiji"
    return str(provisioned) if provisioned.exists() else ""


def pinned_versions() -> dict[str, str]:
    """The repository's own pins (.node-version, packageManager, CI's uv), so a version bump edits only those."""
    uv = set(re.findall(r"uv==([0-9.]+)", (ROOT / ".github/workflows/ci.yml").read_text()))
    if len(uv) != 1:
        sys.exit(f"CI must pin exactly one uv version, found {sorted(uv)}")
    return {"node": (ROOT / ".node-version").read_text().strip().split(".")[0],
            "pnpm": json.loads((ROOT / "package.json").read_text())["packageManager"].split("@", 1)[1],
            "uv": uv.pop()}


def tool_version(argv: tuple[str, ...]) -> str:
    executable = shutil.which(argv[0])
    if executable is None:
        return ""
    result = subprocess.run([executable, *argv[1:]], capture_output=True, text=True)
    return result.stdout.strip() if result.returncode == 0 else ""


def doctor(args: argparse.Namespace) -> None:
    if getattr(args, "proposal_version", False):
        from proposal_preflight import check_versions
        options = {}
        if getattr(args, "packaged_client", False):
            from cytellect_api.cloud_account import DEFAULT_CLOUD_URL
            options["expected_service"] = DEFAULT_CLOUD_URL
        else:
            for option, variable in (("proposal_prompt", "CYTELLECT_PROPOSAL_PROMPT_VERSION"),
                                     ("discussion_prompt", "CYTELLECT_DISCUSSION_PROMPT_VERSION")):
                if os.environ.get(variable):
                    options[option] = os.environ[variable]
        results = check_versions(os.environ.get("CYTELLECT_PROPOSAL_URL", "").strip(), proposal_token(), probe, **options)
        for route, version, accepted, detail in results:
            print(f"[{'ok' if accepted else 'NG'}] {route} {version}: {detail}")
        if not all(item[2] for item in results):
            sys.exit("AI prompt compatibility failed; do not distribute this client.")
        return
    if getattr(args, "packaged_client", False):
        sys.exit("--packaged-client requires --proposal-version")
    failed = False
    hint = f' (run `source "{DEV_RUNTIME / "env.sh"}"` first)' if (DEV_RUNTIME / "env.sh").exists() else ""

    def report(state: str, name: str, detail: str, cloud: bool = False) -> None:
        """Cloud services only warn unless required: development continues while a GPU is unavailable."""
        nonlocal failed
        if state == "NG" and cloud and not args.require_cloud:
            state = "!!"
        elif state == "--" and cloud and args.require_cloud:
            state = "NG"
        failed = failed or state == "NG"
        print(f"[{state}] {name}: {detail}")

    pins = pinned_versions()
    node = tool_version(("node", "-p", "process.versions.node"))
    ready = node.split(".")[0] == pins["node"]
    report("ok" if ready else "NG", "Node.js", (node or "not installed") + ("" if ready else hint))
    pnpm = tool_version(("pnpm", "--version"))
    report("ok" if pnpm == pins["pnpm"] else "NG", "pnpm", (pnpm or "not installed") + ("" if pnpm == pins["pnpm"] else hint))
    uv = tool_version(("uv", "--version"))
    ready = uv.split()[1:2] == [pins["uv"]]
    report("ok" if ready else "NG", "uv", (uv or "not installed") + ("" if ready else hint))
    if sys.platform.startswith("linux"):
        # Ask the figure code itself: any Japanese font is not enough, figures need one of FONT_FAMILIES.
        font = figure_font()
        report("ok" if font else "--", "Japanese figure font",
               font or "installed on first use by `check` and `serve` (`bash scripts/install_figure_font.sh`)")
    if KEY_FILE.exists():
        private = os.name == "nt" or KEY_FILE.stat().st_mode & 0o077 == 0
        report("ok" if private else "NG", "Key file", "readable only by you" if private
               else f"other users can read it: `chmod 600 {KEY_FILE}`")
    chromium = os.environ.get("CYTELLECT_CHROMIUM_EXECUTABLE", "")
    if chromium:
        report("ok" if Path(chromium).exists() else "NG", "Browser for tests", chromium)

    fiji = fiji_path() or (str(DEV_RUNTIME / "fiji") if DEV_RUNTIME.exists() else "")
    if not fiji:
        report("NG", "Fiji (StarDist)", "run `bash scripts/linux_setup.sh` (Linux) or `setup --fiji DIR`")
    else:
        path = Path(fiji).expanduser().resolve()
        inside = path == ROOT or ROOT in path.parents
        if inside:
            report("NG", "Fiji (StarDist)", f"inside the checkout: {path}")
        else:
            report("ok" if path.exists() else "--", "Fiji (StarDist)", "outside the checkout" if path.exists()
                   else "installed on first use by `serve`, `check --fiji` and `e2e`")

    env = cloud_env(dict(os.environ))
    url, key = env.get("CYTELLECT_CELLPOSE_REMOTE_URL", "").strip(), env.get("CYTELLECT_CELLPOSE_REMOTE_TOKEN", "")
    if not url:
        report("--", "Cloud GPU (Cellpose)", "not configured; Cellpose needs this or a CPU runtime (`setup --cellpose`)", cloud=True)
    elif not url.startswith("https://") or not key:
        report("NG", "Cloud GPU (Cellpose)", cloud=True, detail="set an https CYTELLECT_CELLPOSE_REMOTE_URL and CYTELLECT_CELLPOSE_REMOTE_TOKEN")
    elif not args.live:
        report("ok", "Cloud GPU (Cellpose)", "configured; `doctor --live` contacts it (starts the GPU for about 20 s)")
    else:
        headers = {"Authorization": "Bearer " + key}
        if env.get("CYTELLECT_CELLPOSE_REMOTE_SECRET"):
            headers["X-Cytellect-Secret"] = env["CYTELLECT_CELLPOSE_REMOTE_SECRET"]
        status, _ = probe(urllib.request.Request(url.rstrip("/") + "/health", headers=headers), timeout=180)
        ok, detail = cellpose_state(status)
        report("ok" if ok else "NG", "Cloud GPU (Cellpose)", detail, cloud=True)

    service, token = os.environ.get("CYTELLECT_PROPOSAL_URL", "").strip(), proposal_token()
    if not service:
        report("--", "Analysis proposals (LLM)", "not configured; the AI instruction box stays disabled", cloud=True)
    elif not service.startswith("https://") or not token:
        report("NG", "Analysis proposals (LLM)", cloud=True, detail="set an https CYTELLECT_PROPOSAL_URL and the device token")
    elif not args.live:
        report("ok", "Analysis proposals (LLM)", "configured; `doctor --live` checks the device token without a model call")
    else:
        request = urllib.request.Request(service.rstrip("/") + "/v1/proposals", data=b"{}", method="POST",
                                         headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"})
        ok, detail = proposal_state(*probe(request, timeout=30))
        report("ok" if ok else "NG", "Analysis proposals (LLM)", detail, cloud=True)
    if getattr(args, "owner", False):
        for state, name, detail in owner_checks():
            report(state, name, detail)
    if failed:
        sys.exit("Some required parts are not ready (see CONTRIBUTING.md).")
    print("Ready. Cloud GPU and proposal items marked [!!] or [--] do not block development; "
          "pass --require-cloud to require them.")


def github_api(path: str) -> object:
    """`gh api` as the signed-in account (REST only: cloud sessions have no GraphQL); None on failure."""
    executable = shutil.which("gh")
    if executable is None:
        return None
    result = subprocess.run([executable, "api", path], capture_output=True, text=True)
    try:
        return json.loads(result.stdout) if result.returncode == 0 else None
    except ValueError:
        return None


def fetch_json(url: str, token: str, timeout: float = 20) -> tuple[int, object]:
    """Status and JSON body of an authenticated GET; the token is never printed."""
    request = urllib.request.Request(url, headers={"Authorization": "Bearer " + token, "User-Agent": USER_AGENT})
    try:
        with urllib.request.build_opener(_NoRedirect).open(request, timeout=timeout) as response:
            status, body = response.status, response.read(65536)
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read(65536)
    except (urllib.error.URLError, OSError):
        return 0, None
    try:
        return status, json.loads(body)
    except ValueError:
        return status, None


def hugging_face_token() -> str:
    """HF_TOKEN, else the token `hf auth login` stores, else the cloud placeholder."""
    if os.environ.get("HF_TOKEN", "").strip():
        return os.environ["HF_TOKEN"].strip()
    home = Path(os.environ.get("HF_HOME", Path.home() / ".cache/huggingface"))
    try:
        return (home / "token").read_text(encoding="ascii").strip() or CREDENTIAL_PLACEHOLDER
    except (OSError, UnicodeError):
        return CREDENTIAL_PLACEHOLDER


def owner_tool_pins() -> dict[str, str]:
    """The versions .claude/owner-tools.sh installs, so a version bump edits only that script."""
    script = (ROOT / ".claude/owner-tools.sh").read_text(encoding="utf-8")
    return {name: re.search(rf"^{name}_version=(\S+)", script, re.M).group(1)  # type: ignore[union-attr]
            for name in ("vercel", "huggingface_hub")}


def owner_checks() -> list[tuple[str, str, str]]:
    """The owner's accounts and tools, by read-only calls: nothing is deployed, billed or printed."""
    results: list[tuple[str, str, str]] = []
    user, repository = github_api("user"), github_api(f"repos/{REPOSITORY}")
    login = user.get("login") if isinstance(user, dict) else None
    admin = isinstance(repository, dict) and bool((repository.get("permissions") or {}).get("admin"))
    if login == OWNER and admin:
        results.append(("ok", "GitHub (owner)", f"{login}, admin on {REPOSITORY}"))
    else:
        results.append(("NG", "GitHub (owner)", f"signed in as {login or 'nobody'}; the owner needs admin on "
                        f"{REPOSITORY} (`gh auth login`)"))
    secrets = github_api(f"repos/{REPOSITORY}/actions/secrets")
    if isinstance(secrets, dict):
        names = {entry.get("name") for entry in secrets.get("secrets", [])}
        missing = sorted({"MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET"} - names)
        results.append(("NG" if missing else "ok", "Modal deploy (GitHub Actions)",
                        f"repository secrets missing: {', '.join(missing)}" if missing
                        else "deploy token stored in the repository secrets"))
    else:
        # Cloud sessions cannot list Actions secrets; the last successful deploy is the evidence left.
        runs = github_api(f"repos/{REPOSITORY}/actions/workflows/cellpose-modal-deploy.yml/runs?status=success&per_page=1")
        last = runs.get("workflow_runs", [{}])[:1] if isinstance(runs, dict) else []
        when = last[0].get("created_at", "")[:10] if last else ""
        results.append(("--", "Modal deploy (GitHub Actions)", "repository secrets not readable here; "
                        + (f"last successful deploy {when}" if when else "no successful deploy found")))
    token = os.environ.get("CLOUDFLARE_API_TOKEN", "").strip()
    if not token:
        results.append(("NG", "Cloudflare (proposal Worker)", "set CLOUDFLARE_API_TOKEN (in a cloud session, "
                        f"`{CREDENTIAL_PLACEHOLDER}` with the api.cloudflare.com network secret)"))
    else:
        status, body = fetch_json(CLOUDFLARE_VERIFY_URL, token)
        active = isinstance(body, dict) and body.get("success") and (body.get("result") or {}).get("status") == "active"
        results.append(("ok" if active else "NG", "Cloudflare (proposal Worker)",
                        "API token active" if active else f"API token not accepted ({status or 'unreachable'})"))
    for name, url, token, optional in (
            ("Hugging Face", HUGGING_FACE_WHOAMI_URL, hugging_face_token(),
             "public models need none, publishing models does"),
            ("Vercel", VERCEL_USER_URL, os.environ.get("VERCEL_TOKEN", "").strip() or CREDENTIAL_PLACEHOLDER,
             "the claude.ai Vercel connector covers deployments")):
        status, body = fetch_json(url, token)
        if status == 200 and isinstance(body, dict):
            who = body.get("name") or (body.get("user") or {}).get("username") or "accepted"
            results.append(("ok", name, f"signed in ({who})"))
        elif token != CREDENTIAL_PLACEHOLDER:
            # A token configured here was refused (expired or revoked): an operations credential is broken.
            results.append(("NG", name, f"the configured token was refused ({status or 'unreachable'}); renew it"))
        else:
            # Only the placeholder was sent: none is configured here, or a cloud network secret refused it.
            results.append(("--", name, f"no accepted token (none set here, or the network secret was refused); "
                            f"{optional}"))
    pins = owner_tool_pins()
    os.environ.setdefault("HF_HUB_DISABLE_UPDATE_CHECK", "1")  # no once-a-day hint in the version output (#226)
    for tool, argv, expected in (("Vercel CLI", ("vercel", "--version"), pins["vercel"]),
                                 # `--format quiet` prints the bare version in every context (#226): without an
                                 # AI agent, `hf` defaults to human output.
                                 ("Hugging Face CLI", ("hf", "version", "--format", "quiet"), pins["huggingface_hub"])):
        lines = tool_version(argv).splitlines()
        results.append(("ok" if expected in lines else "NG", tool, expected if expected in lines
                        else (lines[0] if lines else "not installed (`bash .claude/owner-tools.sh`)")))
    return results


def serve_env(base: dict[str, str], data_dir: Path) -> dict[str, str]:
    """The installation's settings on loopback; cloud GPU and proposal settings pass through unchanged."""
    return {**base, "CYTELLECT_DATA_DIR": str(data_dir), "CYTELLECT_APP_ORIGIN": APP_ORIGIN,
            "CYTELLECT_SECURE_COOKIES": "false", "NEXT_PUBLIC_API_ORIGIN": API_ORIGIN, "NEXT_TELEMETRY_DISABLED": "1"}


def responding(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=2):
            return True
    except (urllib.error.URLError, OSError):
        return False


def stop(processes: list[subprocess.Popen], grace: float = 20) -> None:
    """Stop each process group, not only its leader: `uv run` and pnpm start the servers as children."""
    def signal_group(process: subprocess.Popen, sig: int) -> None:
        try:
            os.killpg(process.pid, sig)
        except ProcessLookupError:
            pass

    for process in processes:
        if os.name == "nt":
            if process.poll() is None:
                process.terminate()
        else:
            signal_group(process, signal.SIGTERM)
    deadline = time.monotonic() + grace
    for process in processes:
        try:
            process.wait(timeout=max(0, deadline - time.monotonic()))
        except subprocess.TimeoutExpired:
            pass
    for process in processes:
        if os.name == "nt":
            process.kill()
        else:
            signal_group(process, signal.SIGKILL)  # members that ignored SIGTERM or outlived their leader
        process.wait()


def serve(args: argparse.Namespace) -> None:
    fiji = ensure_fiji()
    ensure_figure_font()
    for url in (API_ORIGIN + "/v1/health", APP_ORIGIN):
        if responding(url):
            sys.exit(f"{url} is already in use; stop the other server first")
    data = outside_checkout(args.data_dir, "Data directory")
    data.mkdir(parents=True, exist_ok=True, mode=0o700)
    env = serve_env(cloud_env({**os.environ, "CYTELLECT_FIJI_EXECUTABLE": fiji}), data)
    if not args.skip_build:
        run(("pnpm", "build"), env)  # NEXT_PUBLIC_API_ORIGIN is fixed at build time
    uv = shutil.which("uv") or sys.exit("uv is not installed; see CONTRIBUTING.md")
    pnpm = shutil.which("pnpm") or sys.exit("pnpm is not installed; see CONTRIBUTING.md")
    logs = Path(tempfile.mkdtemp(prefix="cytellect-serve-logs-"))
    commands = {"api": [uv, "run", "cytellect", "serve"], "worker": [uv, "run", "cytellect-worker"],
                "web": [pnpm, "--filter", "@cytellect/web", "start"]}
    processes: list[subprocess.Popen] = []
    try:
        for name, argv in commands.items():
            log = (logs / f"{name}.log").open("wb")
            processes.append(subprocess.Popen(argv, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                              start_new_session=os.name != "nt"))
        deadline = time.monotonic() + 120
        while not (responding(API_ORIGIN + "/v1/health") and responding(APP_ORIGIN)):
            if time.monotonic() > deadline or any(process.poll() is not None for process in processes):
                sys.exit(f"Startup failed; see the logs in {logs}")
            time.sleep(1)
        invitation = subprocess.run([uv, "run", "cytellect", "invite", "--hours", "24"], cwd=ROOT, env=env,
                                    capture_output=True, text=True, check=True).stdout.strip()
        gpu = "on" if env.get("CYTELLECT_CELLPOSE_REMOTE_URL") else "off"
        proposals = "on" if os.environ.get("CYTELLECT_PROPOSAL_URL") else "off"
        print(f"\nOpen {APP_ORIGIN}/workspace and enter the invitation code: {invitation}")
        print(f"Fiji on, cloud GPU (Cellpose) {gpu}, analysis proposals {proposals}. Logs: {logs}")
        print("Use registered public images only. Press Ctrl-C to stop.", flush=True)
        while all(process.poll() is None for process in processes):
            time.sleep(1)
        sys.exit(f"A server stopped; see the logs in {logs}")
    except KeyboardInterrupt:
        print("\nStopping.")
    finally:
        stop(processes)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("setup", help="Install locked dependencies; optionally provision Fiji and Cellpose")
    p.add_argument("--fiji", type=Path, metavar="DIR", help="Fiji runtime directory outside the checkout")
    p.add_argument("--cellpose", type=Path, metavar="DIR",
                   help="Cellpose-SAM runtime and model directory outside the checkout (about 2.5 GB)")
    p.set_defaults(func=setup)
    p = sub.add_parser("check", help="Run the pull-request CI checks for the python and/or web areas")
    p.add_argument("areas", nargs="*", metavar="AREA", help="python, web (default: both)")
    p.add_argument("--related", action="store_true",
                   help="Short local loop: lint, types and only the tests that import or name the changed files")
    p.add_argument("--changed", action="store_true",
                   help="Choose the areas from the changed files, as pull-request CI does")
    p.add_argument("--base", default="origin/main", metavar="REF",
                   help="With --related or --changed, compare against this ref (default: origin/main)")
    p.add_argument("--fiji", action="store_true", help="Also run the real-Fiji tests")
    p.set_defaults(func=check)
    p = sub.add_parser("changed", help="List changed files and the pull-request CI areas they select")
    p.add_argument("--base", default="origin/main", metavar="REF", help="Compare against this ref (default: origin/main)")
    p.set_defaults(func=changed)
    p = sub.add_parser("contracts", help="Regenerate OpenAPI, default recipe and TypeScript contracts")
    p.set_defaults(func=contracts)
    p = sub.add_parser("audit", help="Dependency inventory, vulnerability audits and full-history secret scan")
    p.add_argument("--out", type=Path, metavar="DIR", help="Report directory outside the checkout (default: temp)")
    p.set_defaults(func=audit)
    p = sub.add_parser("doctor", help="Report whether tools, Fiji, the cloud GPU and proposals are ready")
    live = p.add_mutually_exclusive_group()
    live.add_argument("--live", action="store_true",
                   help="Also contact the configured cloud GPU and proposal service (no model call)")
    live.add_argument("--proposal-version", action="store_true",
                      help="Require both client prompt versions on the configured AI service; no GPU, model call or usage count")
    p.add_argument("--packaged-client", action="store_true",
                   help="With --proposal-version, require the Windows client's compiled default service URL and prompts")
    p.add_argument("--require-cloud", action="store_true",
                   help="Fail when the cloud GPU or proposals are not configured, misconfigured or unavailable")
    p.add_argument("--owner", action="store_true",
                   help="Also check the owner's GitHub, Cloudflare, Hugging Face, Vercel and CLIs (read-only calls)")
    p.set_defaults(func=doctor)
    p = sub.add_parser("serve", help="Run the API, worker and production web build like an installation")
    p.add_argument("--data-dir", type=Path, default=Path.home() / "cytellect-data", metavar="DIR",
                   help="Private runtime directory outside the checkout (default: ~/cytellect-data)")
    p.add_argument("--skip-build", action="store_true", help="Reuse the last `serve` web build")
    p.set_defaults(func=serve)
    p = sub.add_parser("public-inputs", help="Fetch and verify registered public images for trying the screens",
                       epilog="\n".join(f"{name}: {use}" for name, use in PUBLIC_INPUTS.items()),
                       formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("datasets", nargs="*", metavar="DATASET",
                   help=f"{', '.join(PUBLIC_INPUTS)} (default: bbbc007)")
    p.add_argument("--out", type=Path, default=Path.home() / "cytellect-public-inputs", metavar="DIR",
                   help="Directory outside the checkout (default: ~/cytellect-public-inputs)")
    p.set_defaults(func=public_inputs)
    return parser


def command_options() -> dict[str, set[str]]:
    """Each subcommand's option names, so documents that name a command can be checked (scripts/check_docs.py)."""
    parser = build_parser()
    subcommands = next(action for action in parser._actions if isinstance(action, argparse._SubParsersAction))
    return {name: set(sub._option_string_actions) for name, sub in subcommands.choices.items()}


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

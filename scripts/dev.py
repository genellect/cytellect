"""Single entry point for local setup and the checks pull-request CI runs.

Standard library only, so it runs before `uv sync` and on Windows:

    python3 scripts/dev.py setup [--fiji DIR] [--cellpose DIR]
    python3 scripts/dev.py check [python] [web] [--fiji]
    python3 scripts/dev.py contracts
    python3 scripts/dev.py audit [--out DIR]

`check` runs the same commands as the `python` and `web` jobs in
.github/workflows/ci.yml; tests/test_dev_commands.py fails when the two drift.
Browser, container and Windows-installer checks stay CI-only (see docs/ci.md).
"""
from __future__ import annotations

import argparse
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_OUTPUTS = ("packages/contracts", "apps/web/src/lib/generated.ts", "apps/web/src/lib/recipe-defaults.json")
OPENAPI = ("uv", "run", "cytellect", "openapi", "--output", "packages/contracts/openapi.json",
           "--recipe-defaults", "apps/web/src/lib/recipe-defaults.json")

# The checks each pull-request CI area runs, in CI order.
CHECKS: dict[str, tuple[tuple[str, ...], ...]] = {
    "python": (
        ("uv", "run", "ruff", "check", "."),
        ("uv", "run", "mypy", "packages/analysis/src", "services"),
        ("uv", "run", "python", "scripts/generate_planning_fixtures.py", "--check"),
        ("uv", "run", "pytest", "tests", "-m", "not fiji"),
        ("uv", "run", "python", "scripts/check_public_tree.py"),
        ("uv", "run", "python", "scripts/check_docs.py"),
        ("uv", "run", "python", "scripts/proposal_schema.py", "--check"),
    ),
    "web": (
        OPENAPI,
        ("pnpm", "contracts"),
        ("git", "diff", "--exit-code", "--", *CONTRACT_OUTPUTS),
        ("pnpm", "check"),
        ("pnpm", "test"),
        ("pnpm", "--filter", "@cytellect/proposal-worker", "check"),
        ("pnpm", "--filter", "@cytellect/proposal-worker", "test"),
        ("pnpm", "--filter", "@cytellect/proposal-worker", "test:deployment"),
        ("node", "--test", "apps/web/scripts/finalize-local-export.test.mjs"),
        ("pnpm", "build"),
    ),
}
FIJI_CHECK = ("uv", "run", "pytest", "-m", "fiji")


def run(argv: tuple[str, ...] | list[str], env: dict[str, str] | None = None) -> None:
    print("$ " + shlex.join(argv), flush=True)
    executable = shutil.which(argv[0])
    if executable is None:
        sys.exit(f"{argv[0]} is not installed; see CONTRIBUTING.md for the required tools")
    result = subprocess.run([executable, *argv[1:]], cwd=ROOT, env=env)
    if result.returncode:
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


def check(args: argparse.Namespace) -> None:
    areas = args.areas or list(CHECKS)
    unknown = sorted(set(areas) - set(CHECKS))
    if unknown:
        sys.exit(f"Unknown area: {', '.join(unknown)} (choose from {', '.join(CHECKS)})")
    if args.fiji and not os.environ.get("CYTELLECT_FIJI_EXECUTABLE"):
        sys.exit("--fiji needs CYTELLECT_FIJI_EXECUTABLE (run `setup --fiji DIR` first)")
    with tempfile.TemporaryDirectory(prefix="cytellect-check-") as scratch:
        env = scratch_env(Path(scratch))
        for area in areas:
            for argv in CHECKS[area]:
                run(argv, env)
        if args.fiji:
            run(FIJI_CHECK, env)
    print("All selected checks passed.")


def contracts(_: argparse.Namespace) -> None:
    with tempfile.TemporaryDirectory(prefix="cytellect-contracts-") as scratch:
        env = scratch_env(Path(scratch))
        run(OPENAPI, env)
        run(("pnpm", "contracts"), env)
    print("Commit packages/contracts/openapi.json, recipe-defaults.json and generated.ts together.")


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


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    p = sub.add_parser("setup", help="Install locked dependencies; optionally provision Fiji and Cellpose")
    p.add_argument("--fiji", type=Path, metavar="DIR", help="Fiji runtime directory outside the checkout")
    p.add_argument("--cellpose", type=Path, metavar="DIR",
                   help="Cellpose-SAM runtime and model directory outside the checkout (about 2.5 GB)")
    p.set_defaults(func=setup)
    p = sub.add_parser("check", help="Run the pull-request CI checks for the python and/or web areas")
    p.add_argument("areas", nargs="*", metavar="AREA", help="python, web (default: both)")
    p.add_argument("--fiji", action="store_true", help="Also run the real-Fiji tests")
    p.set_defaults(func=check)
    p = sub.add_parser("contracts", help="Regenerate OpenAPI, default recipe and TypeScript contracts")
    p.set_defaults(func=contracts)
    p = sub.add_parser("audit", help="Dependency inventory, vulnerability audits and full-history secret scan")
    p.add_argument("--out", type=Path, metavar="DIR", help="Report directory outside the checkout (default: temp)")
    p.set_defaults(func=audit)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

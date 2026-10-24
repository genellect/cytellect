"""scripts/dev.py check must stay the same set of commands the pull-request CI jobs run."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dev import CHECKS  # noqa: E402

TOOLS = ("uv ", "pnpm ", "node ", "git diff")
# CI commands that `dev.py check` deliberately leaves out, and where they live instead.
CI_ONLY = {
    "uv sync": "setup",
    "pnpm install": "setup",
    "uv run python scripts/scientific_review.py": "CI evidence receipt",
    "uv run pytest tests/test_local_bundle.py tests/test_ci_changes.py": "subset of the full suite",
    "uv run python scripts/scan_secrets.py": "audit",
    "uv run pytest tests/test_scan_secrets.py": "audit (needs the pinned scanner cache)",
    "uv run pip-audit": "audit",
    "uv run python scripts/sbom.py": "audit",
    "pnpm audit": "audit",
    "pnpm --filter @cytellect/web exec playwright": "browser tests (docs/ci.md)",
    "pnpm --filter @cytellect/web start": "browser tests (docs/ci.md)",
}


def normalize(command: str) -> str:
    return " ".join(command.replace('"', "").replace("'", "").split())


def ci_commands(job: str) -> list[str]:
    lines = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8").splitlines()
    start = lines.index(f"  {job}:") + 1
    end = next((i for i in range(start, len(lines)) if re.match(r"^  [\w-]+:\s*$", lines[i])), len(lines))
    commands, block_indent = [], None
    for line in lines[start:end]:
        indent = len(line) - len(line.lstrip())
        if block_indent is not None and (indent > block_indent or not line.strip()):
            commands.append(line.strip())
            continue
        block_indent = None
        match = re.match(r"^\s*(?:- )?run: (.*)$", line)
        if match and match.group(1).strip() == "|":
            block_indent = indent
        elif match:
            commands.append(match.group(1))
    split = [part for command in commands for part in command.split("&&")]
    return [normalize(c) for c in split if normalize(c).startswith(TOOLS)]


def local_commands(area: str) -> list[str]:
    return [normalize(" ".join(argv)) for argv in CHECKS[area]]


def missing_in_ci(local: list[str], ci: list[str]) -> list[str]:
    return [command for command in local if not any(c.startswith(command) for c in ci)]


def missing_locally(local: list[str], ci: list[str]) -> list[str]:
    return [command for command in ci
            if not any(command.startswith(c) for c in [*local, *CI_ONLY])]


def test_every_local_check_runs_in_its_ci_job():
    for area in CHECKS:
        assert missing_in_ci(local_commands(area), ci_commands(area)) == [], area


def test_every_ci_check_is_local_or_explicitly_ci_only():
    for area in CHECKS:
        assert missing_locally(local_commands(area), ci_commands(area)) == [], (
            f"{area}: add these to scripts/dev.py CHECKS or CI_ONLY")


def test_drift_in_either_direction_is_reported():
    ci = ci_commands("python")
    assert missing_locally(local_commands("python"), [*ci, "uv run python scripts/new_gate.py"]) == [
        "uv run python scripts/new_gate.py"]
    assert missing_in_ci([*local_commands("python"), "uv run ruff format --check ."], ci) == [
        "uv run ruff format --check ."]

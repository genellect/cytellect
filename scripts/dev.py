"""Single entry point for local setup and the checks pull-request CI runs.

Standard library only, so it runs before `uv sync` and on Windows:

    python3 scripts/dev.py setup [--fiji DIR] [--cellpose DIR]
    python3 scripts/dev.py check [python] [web] [--fiji]
    python3 scripts/dev.py contracts
    python3 scripts/dev.py audit [--out DIR]
    python3 scripts/dev.py doctor [--live]
    python3 scripts/dev.py serve [--data-dir DIR] [--skip-build]

`check` runs the same commands as the `python` and `web` jobs in
.github/workflows/ci.yml; tests/test_dev_commands.py fails when the two drift.
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

ROOT = Path(__file__).resolve().parents[1]
API_ORIGIN = "http://localhost:8000"
APP_ORIGIN = "http://localhost:3000"
# The deployed Modal server (infra/modal_cellpose.py, Cellpose Modal deploy workflow); authentication required.
MODAL_CELLPOSE_URL = "https://genellect--cytellect-cellpose-cellposeserver.us-east.modal.direct"
USER_AGENT = "cytellect-dev"  # Cloudflare refuses Python's default agent (error 1010)
# Where .claude/cloud-setup.sh provisions pinned tools and Fiji (its env.sh exports them).
CLOUD_RUNTIME = Path.home() / ".local/share/cytellect-cloud"
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


def fiji_path() -> str:
    """CYTELLECT_FIJI_EXECUTABLE, else the cloud setup's Fiji, so a shell without env.sh still finds it."""
    configured = os.environ.get("CYTELLECT_FIJI_EXECUTABLE", "")
    if configured:
        return configured
    provisioned = CLOUD_RUNTIME / "fiji"
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
    failed = False
    hint = f' (run `source "{CLOUD_RUNTIME / "env.sh"}"` first)' if (CLOUD_RUNTIME / "env.sh").exists() else ""

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
        fonts = tool_version(("fc-list", ":lang=ja", "family"))
        report("ok" if fonts else "NG", "Japanese figure font", "installed" if fonts else "install fonts-noto-cjk")
    chromium = os.environ.get("CYTELLECT_CHROMIUM_EXECUTABLE", "")
    if chromium:
        report("ok" if Path(chromium).exists() else "NG", "Browser for tests", chromium)

    fiji = fiji_path()
    if not fiji:
        report("NG", "Fiji (StarDist)", "set CYTELLECT_FIJI_EXECUTABLE (run `setup --fiji DIR`)")
    else:
        path = Path(fiji).expanduser().resolve()
        inside = path == ROOT or ROOT in path.parents
        report("ok" if path.exists() and not inside else "NG", "Fiji (StarDist)",
               "outside the checkout" if path.exists() and not inside else f"missing or inside the checkout: {path}")

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
    if failed:
        sys.exit("Some required parts are not ready (see CONTRIBUTING.md).")
    print("Ready. Cloud GPU and proposal items marked [!!] or [--] do not block development; "
          "pass --require-cloud to require them.")


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
    fiji = fiji_path()
    if not fiji or not Path(fiji).expanduser().exists():
        sys.exit("serve needs Fiji: run `setup --fiji DIR` and export CYTELLECT_FIJI_EXECUTABLE")
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
    p = sub.add_parser("doctor", help="Report whether tools, Fiji, the cloud GPU and proposals are ready")
    p.add_argument("--live", action="store_true",
                   help="Also contact the configured cloud GPU and proposal service (no model call)")
    p.add_argument("--require-cloud", action="store_true",
                   help="Fail when the cloud GPU or proposals are not configured, misconfigured or unavailable")
    p.set_defaults(func=doctor)
    p = sub.add_parser("serve", help="Run the API, worker and production web build like an installation")
    p.add_argument("--data-dir", type=Path, default=Path.home() / "cytellect-data", metavar="DIR",
                   help="Private runtime directory outside the checkout (default: ~/cytellect-data)")
    p.add_argument("--skip-build", action="store_true", help="Reuse the last `serve` web build")
    p.set_defaults(func=serve)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()

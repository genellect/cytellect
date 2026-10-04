"""Pinned, fail-closed secret scanning without publishing raw scanner findings.

Scan all reachable Git commits and a snapshot of tracked working files. Never
walk the working directory or open local .env.local files. A historical commit
of such a file is still inspected by the history scan. Raw scanner JSON remains
in process memory; only aggregate rule counts can leave this wrapper.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import platform
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath
from typing import Any

LOCK = Path(__file__).with_name("security-tools.lock.json")
MAX_ARCHIVE = 64 * 1024 * 1024
MAX_EXECUTABLE = 64 * 1024 * 1024
FINDINGS_EXIT = 7


class ScanError(Exception):
    """Only fixed, non-sensitive error codes may be reported."""


def safe_environment(trusted_repo: Path | None = None) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if not k.upper().startswith(("GITLEAKS_", "GIT_"))}
    env.update({"GIT_CONFIG_NOSYSTEM": "1", "GIT_CONFIG_GLOBAL": os.devnull,
                "GIT_NO_REPLACE_OBJECTS": "1", "GIT_TERMINAL_PROMPT": "0"})
    if trusted_repo is not None:
        # Applies to Gitleaks' child Git too. Never allow '*', surrounding
        # directories, or arbitrary settings inherited from the invoking shell.
        env.update({"GIT_CONFIG_COUNT": "1", "GIT_CONFIG_KEY_0": "safe.directory",
                    "GIT_CONFIG_VALUE_0": str(trusted_repo.resolve())})
    return env


def run_capture(command: list[str], *, cwd: Path, timeout: int = 600,
                trusted_repo: Path | None = None) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(command, cwd=cwd, env=safe_environment(trusted_repo), stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE, timeout=timeout, check=False)
    except (OSError, subprocess.SubprocessError):
        raise ScanError("process_execution_failed") from None


def git(repo: Path, *args: str) -> bytes:
    result = run_capture(["git", "-C", str(repo), *args], cwd=repo, trusted_repo=repo)
    if result.returncode:
        raise ScanError("git_inspection_failed")
    return result.stdout


def platform_key() -> str:
    if platform.machine().lower() not in {"amd64", "x86_64"}:
        raise ScanError("unsupported_platform")
    system = platform.system().lower()
    if system not in {"linux", "windows"}:
        raise ScanError("unsupported_platform")
    return f"{system}-x86_64"


def executable_bytes(archive: bytes, entry: dict[str, str]) -> bytes:
    """Read only the named regular file, without extracting archive paths."""
    if hashlib.sha256(archive).hexdigest() != entry["sha256"]:
        raise ScanError("archive_checksum_mismatch")
    try:
        if entry["format"] == "zip":
            with zipfile.ZipFile(io.BytesIO(archive)) as container:
                matches = [item for item in container.infolist() if item.filename == entry["executable"]]
                if len(matches) != 1:
                    raise ScanError("invalid_executable_entry")
                item = matches[0]
                mode = item.external_attr >> 16
                if item.is_dir() or stat.S_ISLNK(mode) or item.file_size > MAX_EXECUTABLE:
                    raise ScanError("invalid_executable_entry")
                return container.read(item)
        if entry["format"] == "tar.gz":
            with tarfile.open(fileobj=io.BytesIO(archive), mode="r:gz") as container:
                tar_matches = [item for item in container.getmembers() if item.name == entry["executable"]]
                if len(tar_matches) != 1 or not tar_matches[0].isfile() or tar_matches[0].size > MAX_EXECUTABLE:
                    raise ScanError("invalid_executable_entry")
                stream = container.extractfile(tar_matches[0])
                if stream is None:
                    raise ScanError("invalid_executable_entry")
                return stream.read()
    except (OSError, ValueError, tarfile.TarError, zipfile.BadZipFile, RuntimeError):
        raise ScanError("invalid_tool_archive") from None
    raise ScanError("unsupported_archive")


def get_tool(cache_dir: Path) -> tuple[Path, dict[str, Any]]:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))["gitleaks"]
    entry = lock["platforms"][platform_key()]
    cache_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    archive_path = cache_dir / f"gitleaks-{lock['version']}-{platform_key()}.{entry['format']}"
    if not archive_path.exists():
        try:
            with urllib.request.urlopen(entry["url"], timeout=60) as response:
                archive = response.read(MAX_ARCHIVE + 1)
            if len(archive) > MAX_ARCHIVE:
                raise ScanError("tool_archive_too_large")
            # Validate before writing a reusable cache or executing anything.
            executable_bytes(archive, entry)
            archive_path.write_bytes(archive)
        except (OSError, ValueError):
            raise ScanError("tool_download_failed") from None
    if archive_path.stat().st_size > MAX_ARCHIVE:
        raise ScanError("tool_archive_too_large")
    binary = executable_bytes(archive_path.read_bytes(), entry)
    executable = cache_dir / f"gitleaks-{lock['version']}{'.exe' if os.name == 'nt' else ''}"
    if executable.exists():
        if hashlib.sha256(executable.read_bytes()).digest() != hashlib.sha256(binary).digest():
            raise ScanError("executable_checksum_mismatch")
    else:
        executable.write_bytes(binary)
    executable.chmod(0o700)
    version = run_capture([str(executable), "version"], cwd=cache_dir, timeout=30)
    if version.returncode or version.stdout.decode("ascii", errors="replace").strip() != lock["version"]:
        raise ScanError("tool_version_mismatch")
    return executable, {"name": "gitleaks", "version": lock["version"], "archive_sha256": entry["sha256"]}


def safe_tracked_path(repo: Path, name: str) -> Path:
    relative = PurePosixPath(name)
    if not relative.parts or relative.is_absolute() or ".." in relative.parts or "\\" in name:
        raise ScanError("unsafe_tracked_path")
    path = repo
    for part in relative.parts:
        path = path / part
        if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
            raise ScanError("tracked_link_not_supported")
    if not path.resolve().is_relative_to(repo):
        raise ScanError("unsafe_tracked_path")
    return path


def stage_tracked(repo: Path, target: Path) -> dict[str, int]:
    names = git(repo, "ls-files", "-z").split(b"\0")
    counts = {"files_scanned": 0, "deleted_files": 0, "local_environment_files_excluded": 0}
    for raw in names:
        if not raw:
            continue
        try:
            name = raw.decode("utf-8")
        except UnicodeDecodeError:
            raise ScanError("unsupported_tracked_filename") from None
        if PurePosixPath(name).name.lower() == ".env.local":
            counts["local_environment_files_excluded"] += 1
            continue
        source = safe_tracked_path(repo, name)
        if not source.exists():
            counts["deleted_files"] += 1
            continue
        if not source.is_file():
            raise ScanError("tracked_non_file_not_supported")
        destination = target.joinpath(*PurePosixPath(name).parts)
        destination.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        shutil.copyfile(source, destination)
        counts["files_scanned"] += 1
    return counts


def aggregate(result: subprocess.CompletedProcess) -> dict[str, Any]:
    if result.returncode not in {0, FINDINGS_EXIT}:
        raise ScanError("scanner_execution_failed")
    try:
        findings = json.loads(result.stdout)
        if not isinstance(findings, list):
            raise ValueError
        rules: Counter[str] = Counter()
        for finding in findings:
            rule = finding["RuleID"]
            if not isinstance(rule, str) or not re.fullmatch(r"[A-Za-z0-9_.-]{1,100}", rule):
                raise ValueError
            rules[rule] += 1
        if bool(findings) != (result.returncode == FINDINGS_EXIT):
            raise ValueError
    except (ValueError, TypeError, KeyError):
        raise ScanError("invalid_scanner_report") from None
    return {"finding_count": len(findings), "rules": dict(sorted(rules.items()))}


def rules_configuration() -> str:
    # Built-in rules remain enabled. Reviewed public checksums need all of:
    # generic rule, exact public source path, and exact full checksum value.
    entries = json.loads(LOCK.read_text(encoding="utf-8"))["reviewed_non_secrets"]
    lines = ["[extend]", "useDefault = true", "", "[[rules]]", 'id = "generic-api-key"']
    for entry in entries:
        if (entry["rule_id"] != "generic-api-key" or not re.fullmatch(r"[a-f0-9]{64}", entry["sha256"])
                or entry["path"] not in {"docs/resource-benchmark.md",
                                         "apps/web/public/demo/bbbc013/manifest.json",
                                         "apps/web/public/fonts/subset-manifest.json"}):
            raise ScanError("invalid_reviewed_exception")
        path_regex = "(?:^|[/\\\\])" + re.escape(entry["path"]).replace("/", "[/\\\\]") + "$"
        lines.extend(["", "[[rules.allowlists]]", 'condition = "AND"', 'regexTarget = "secret"',
                      "paths = ['''" + path_regex + "''']",
                      "regexes = ['''^" + entry["sha256"] + "$''']"])
    return "\n".join(lines) + "\n"


def scan(repo: Path, cache_dir: Path) -> dict[str, Any]:
    repo = repo.resolve()
    cache_dir = cache_dir.resolve()
    if cache_dir.is_relative_to(repo):
        raise ScanError("cache_must_be_outside_repository")
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != b"false":
        raise ScanError("complete_git_history_required")
    if Path(os.fsdecode(git(repo, "rev-parse", "--show-toplevel").strip())).resolve() != repo:
        raise ScanError("repository_root_required")
    git(repo, "rev-parse", "--verify", "HEAD")
    executable, identity = get_tool(cache_dir)
    # Only tracked public source is staged, never untracked local research/runtime.
    with tempfile.TemporaryDirectory(prefix="cytellect-secret-scan-", dir=cache_dir) as directory:
        scratch = Path(directory)
        config = scratch / "rules.toml"
        config.write_text(rules_configuration(), encoding="utf-8")
        ignore = scratch / "empty-ignore"
        ignore.write_text("", encoding="utf-8")
        common = ["--config", str(config), "--gitleaks-ignore-path", str(ignore),
                  "--ignore-gitleaks-allow", "--no-banner", "--no-color", "--redact=100",
                  "--log-level", "error", "--report-format", "json", "--report-path", "-",
                  "--exit-code", str(FINDINGS_EXIT), "--timeout", "600", "--max-decode-depth", "5"]
        history = aggregate(run_capture([str(executable), "git", str(repo),
                                          "--log-opts=--all --full-history --no-ext-diff --no-textconv",
                                          *common], cwd=scratch, timeout=660, trusted_repo=repo))
        target = scratch / "tracked"
        target.mkdir(mode=0o700)
        counts = stage_tracked(repo, target)
        if counts["local_environment_files_excluded"]:
            raise ScanError("tracked_local_environment_file_forbidden")
        tracked = aggregate(run_capture([str(executable), "dir", str(target), *common],
                                         cwd=scratch, timeout=660))
        tracked.update(counts)
    total = history["finding_count"] + tracked["finding_count"]
    return {"schema_version": 1, "tool": identity, "status": "findings" if total else "clean",
            "history": {"scope": "all_reachable_commits", **history},
            "tracked": tracked, "finding_count": total}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument("--cache-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.output.resolve().is_relative_to(args.repo.resolve()):
            raise ScanError("receipt_must_be_outside_repository")
        receipt = scan(args.repo, args.cache_dir)
    except ScanError as error:
        receipt = {"schema_version": 1, "status": "error", "error_code": str(error)}
    except Exception:
        # No exception string, traceback, filenames or subprocess output may leak.
        receipt = {"schema_version": 1, "status": "error", "error_code": "scan_failed"}
    serialized = json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    try:
        if args.output.resolve().is_relative_to(args.repo.resolve()):
            raise OSError
        args.output.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        args.output.write_text(serialized, encoding="utf-8")
    except OSError:
        print(json.dumps({"schema_version": 1, "status": "error", "error_code": "receipt_write_failed"}))
        return 2
    print(serialized, end="")
    return {"clean": 0, "findings": 1, "error": 2}[receipt["status"]]


if __name__ == "__main__":
    sys.exit(main())

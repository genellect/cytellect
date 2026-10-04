"""No actual credentials: integration secrets are generated synthetic markers."""

from __future__ import annotations

import hashlib
import importlib.util
import io
import json
import os
import subprocess
import zipfile
from pathlib import Path

import pytest

SPEC = importlib.util.spec_from_file_location("scan_secrets", Path(__file__).parents[1] / "scripts/scan_secrets.py")
assert SPEC and SPEC.loader
scanner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scanner)


def init_repository(path: Path) -> Path:
    path.mkdir()
    run_git(path, "init", "-q")
    run_git(path, "config", "user.email", "synthetic@example.invalid")
    run_git(path, "config", "user.name", "Synthetic fixture")
    return path


def run_git(path: Path, *arguments: str) -> bytes:
    result = subprocess.run(["git", "-C", str(path), *arguments], capture_output=True,
                            env=scanner.safe_environment(), check=False)
    assert result.returncode == 0, "fixture Git command failed"
    return result.stdout


def synthetic_token(letter: str) -> str:
    # This format is intentionally assembled; it is never a live credential.
    return "gh" + "p_" + hashlib.sha256(("synthetic-test-" + letter).encode()).hexdigest()[:36]


def commit(path: Path, filename: str, content: str) -> None:
    (path / filename).write_text(content, encoding="utf-8")
    run_git(path, "add", filename)
    run_git(path, "commit", "-qm", "synthetic fixture")


def test_stage_never_reads_untracked_or_local_environment(tmp_path, monkeypatch):
    repo = init_repository(tmp_path / "repo")
    commit(repo, "source.txt", "public source")
    (repo / "untracked-private.txt").write_text(synthetic_token("A"))
    (repo / ".env.local").write_text(synthetic_token("B"))
    run_git(repo, "add", ".env.local")  # Still excluded from working-file reads.
    target = tmp_path / "staged"
    target.mkdir()
    original = scanner.shutil.copyfile
    copied = []

    def checked_copy(source, destination):
        assert source.name == "source.txt"
        copied.append(source.name)
        return original(source, destination)

    monkeypatch.setattr(scanner.shutil, "copyfile", checked_copy)
    result = scanner.stage_tracked(repo.resolve(), target)
    assert copied == ["source.txt"]
    assert result == {"files_scanned": 1, "deleted_files": 0, "local_environment_files_excluded": 1}
    assert sorted(item.name for item in target.iterdir()) == ["source.txt"]


def test_scan_uses_all_history_and_isolated_forced_rules(tmp_path, monkeypatch):
    repo = init_repository(tmp_path / "repo")
    commit(repo, "source.txt", "public")
    cache = tmp_path / "tools"
    cache.mkdir()
    monkeypatch.setattr(scanner, "get_tool", lambda _: (cache / "scanner", {"version": "test"}))
    original = scanner.run_capture
    commands = []

    def fake(command, *, cwd, timeout=600, trusted_repo=None):
        if command[0] == "git":
            assert trusted_repo == repo
            return original(command, cwd=cwd, timeout=timeout, trusted_repo=trusted_repo)
        assert trusted_repo == (repo if command[1] == "git" else None)
        commands.append(command)
        config = Path(command[command.index("--config") + 1])
        assert config.read_text() == scanner.rules_configuration()
        assert "useDefault = true" in config.read_text()
        assert 'condition = "AND"' in config.read_text()
        assert "--ignore-gitleaks-allow" in command
        assert command[command.index("--report-path") + 1] == "-"
        return subprocess.CompletedProcess(command, 0, b"[]", b"private diagnostic discarded")

    monkeypatch.setattr(scanner, "run_capture", fake)
    receipt = scanner.scan(repo, cache)
    assert receipt["status"] == "clean"
    assert len(commands) == 2
    assert "--log-opts=--all --full-history --no-ext-diff --no-textconv" in commands[0]
    assert commands[1][1] == "dir"
    assert Path(commands[1][2]) != repo
    assert not any(path.name.startswith("cytellect-secret-scan-") for path in cache.iterdir())


def test_tracked_local_environment_is_never_read_and_cannot_pass_scan(tmp_path, monkeypatch):
    repo = init_repository(tmp_path / "repo")
    commit(repo, "source.txt", "public source")
    (repo / ".env.local").write_text(synthetic_token("I"))
    run_git(repo, "add", ".env.local")
    cache = tmp_path / "tools"
    cache.mkdir()
    monkeypatch.setattr(scanner, "get_tool", lambda _: (cache / "scanner", {"version": "test"}))
    original_capture = scanner.run_capture
    original_open = Path.open

    def protected_open(path, *args, **kwargs):
        assert path.name != ".env.local", "working local environment file must never be opened"
        return original_open(path, *args, **kwargs)

    def fake_capture(command, *, cwd, timeout=600, trusted_repo=None):
        if command[0] == "git":
            return original_capture(command, cwd=cwd, timeout=timeout, trusted_repo=trusted_repo)
        assert command[1] == "git", "forbidden tracked environment must stop before current-file scan"
        return subprocess.CompletedProcess(command, 0, b"[]", b"")

    monkeypatch.setattr(Path, "open", protected_open)
    monkeypatch.setattr(scanner, "run_capture", fake_capture)
    with pytest.raises(scanner.ScanError, match="^tracked_local_environment_file_forbidden$"):
        scanner.scan(repo, cache)
    assert not any(path.name.startswith("cytellect-secret-scan-") for path in cache.iterdir())


def test_aggregate_discards_values_paths_authors_and_only_keeps_counts():
    raw = json.dumps([{"RuleID": "github-pat", "Secret": synthetic_token("C"),
                       "File": "unpublished-name.txt", "Author": "private name", "StartLine": 17}]).encode()
    result = scanner.aggregate(subprocess.CompletedProcess([], scanner.FINDINGS_EXIT, raw, b"private stderr"))
    assert result == {"finding_count": 1, "rules": {"github-pat": 1}}
    assert "private" not in json.dumps(result)


@pytest.mark.parametrize("code,output", [(2, b"private failure"), (0, b"not json"),
                                          (0, b'[ {"RuleID":"github-pat"} ]'),
                                          (7, b"[]"), (7, b'[{"RuleID":"path/secret"}]')])
def test_scanner_failures_are_closed(code, output):
    with pytest.raises(scanner.ScanError) as caught:
        scanner.aggregate(subprocess.CompletedProcess([], code, output, b"private error"))
    assert str(caught.value) in {"scanner_execution_failed", "invalid_scanner_report"}


def test_fixed_entry_extraction_never_writes_archive_paths(tmp_path):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("../../outside", b"must not extract")
        archive.writestr("gitleaks.exe", b"expected binary")
    data = buffer.getvalue()
    entry = {"sha256": hashlib.sha256(data).hexdigest(), "format": "zip", "executable": "gitleaks.exe"}
    assert scanner.executable_bytes(data, entry) == b"expected binary"
    assert list(tmp_path.iterdir()) == []
    with pytest.raises(scanner.ScanError, match="archive_checksum_mismatch"):
        scanner.executable_bytes(data + b"tamper", entry)


def test_link_archive_entry_rejected():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        item = zipfile.ZipInfo("gitleaks.exe")
        item.create_system = 3
        item.external_attr = 0o120777 << 16
        archive.writestr(item, "external-target")
    data = buffer.getvalue()
    entry = {"sha256": hashlib.sha256(data).hexdigest(), "format": "zip", "executable": "gitleaks.exe"}
    with pytest.raises(scanner.ScanError, match="invalid_executable_entry"):
        scanner.executable_bytes(data, entry)


def test_shallow_checkout_rejected_before_tool_execution(tmp_path, monkeypatch):
    monkeypatch.setattr(scanner, "git", lambda *args: b"true\n")
    monkeypatch.setattr(scanner, "get_tool", lambda _: pytest.fail("must not scan incomplete history"))
    with pytest.raises(scanner.ScanError, match="complete_git_history_required"):
        scanner.scan(tmp_path / "repo", tmp_path / "cache")


def test_untrusted_configuration_environment_removed(monkeypatch):
    monkeypatch.setenv("GITLEAKS_CONFIG", "untrusted-allow-all")
    monkeypatch.setenv("GITLEAKS_CONFIG_TOML", "untrusted-allow-all")
    monkeypatch.setenv("GIT_EXTERNAL_DIFF", "untrusted-command")
    environment = scanner.safe_environment()
    assert not any(key.startswith("GITLEAKS_") for key in environment)
    assert "GIT_EXTERNAL_DIFF" not in environment
    assert environment["GIT_NO_REPLACE_OBJECTS"] == "1"


def test_explicit_repository_trust_replaces_inherited_global_trust(tmp_path, monkeypatch):
    monkeypatch.setenv("GIT_CONFIG_COUNT", "2")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "safe.directory")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "*")
    monkeypatch.setenv("GIT_CONFIG_KEY_1", "include.path")
    monkeypatch.setenv("GIT_CONFIG_VALUE_1", "untrusted-configuration")
    repo = tmp_path / "repo"
    environment = scanner.safe_environment(repo)
    assert environment["GIT_CONFIG_COUNT"] == "1"
    assert environment["GIT_CONFIG_KEY_0"] == "safe.directory"
    assert environment["GIT_CONFIG_VALUE_0"] == str(repo.resolve())
    assert "GIT_CONFIG_KEY_1" not in environment and "GIT_CONFIG_VALUE_1" not in environment
    assert environment["GIT_CONFIG_GLOBAL"] == os.devnull
    assert "GIT_CONFIG_COUNT" not in scanner.safe_environment()


def test_real_gitleaks_detects_deleted_history_and_tracked_changes_only(tmp_path):
    cache_value = os.environ.get("CYTELLECT_GITLEAKS_TEST_CACHE")
    if not cache_value:
        pytest.skip("set CYTELLECT_GITLEAKS_TEST_CACHE to test the pinned external tool")
    repo = init_repository(tmp_path / "repo")
    commit(repo, "historical.txt", "token = " + synthetic_token("D"))
    commit(repo, "historical.txt", "removed synthetic token")
    commit(repo, "current.txt", "clean initial content")
    # Two more markers are untracked and must not change findings.
    (repo / ".env.local").write_text(synthetic_token("E"))
    (repo / "untracked.txt").write_text(synthetic_token("F"))
    (repo / "current.txt").write_text("token = " + synthetic_token("G"))
    receipt = scanner.scan(repo, Path(cache_value))
    assert receipt["status"] == "findings"
    assert receipt["history"]["finding_count"] == 1
    assert receipt["tracked"]["finding_count"] == 1
    assert receipt["history"]["rules"] == {"github-pat": 1}
    assert receipt["tracked"]["rules"] == {"github-pat": 1}
    serialized = json.dumps(receipt)
    assert "historical.txt" not in serialized and "current.txt" not in serialized
    assert "Synthetic fixture" not in serialized


@pytest.mark.parametrize("entry", json.loads(scanner.LOCK.read_text())["reviewed_non_secrets"])
def test_real_gitleaks_public_checksum_exceptions_are_exact_and_do_not_hide_adjacent_key(tmp_path, entry):
    cache_value = os.environ.get("CYTELLECT_GITLEAKS_TEST_CACHE")
    if not cache_value:
        pytest.skip("set CYTELLECT_GITLEAKS_TEST_CACHE to test the pinned external tool")
    repo = init_repository(tmp_path / "repo")
    path = entry["path"]
    (repo / path).parent.mkdir(parents=True)
    known = entry["sha256"]
    # An approved checksum, a distinct plausible key beside it, and the same
    # checksum in another file exercise all three dimensions of the exception.
    commit(repo, path, "DAPI:" + known + "\n")
    commit(repo, "other.md", "DAPI:" + known + "\n")
    with (repo / path).open("a") as stream:
        stream.write("token = " + synthetic_token("H"))
    receipt = scanner.scan(repo, Path(cache_value))
    assert receipt["history"]["rules"] == {"generic-api-key": 1}
    assert receipt["tracked"]["rules"] == {"generic-api-key": 1, "github-pat": 1}


def test_public_preview_checksum_exception_matches_the_actual_allowlisted_png():
    root = Path(__file__).parents[1]
    exception = json.loads(scanner.LOCK.read_text())["reviewed_non_secrets"][1]
    public_preview = root / "apps/web/public/demo/bbbc013/demo-dapi.png"
    assert hashlib.sha256(public_preview.read_bytes()).hexdigest() == exception["sha256"]

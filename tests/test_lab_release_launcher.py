"""Metadata-only launcher rejection checks. No Docker invocation or image inputs."""

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESKTOP = ROOT / "scripts/docker-desktop.ps1"
RELEASE = ROOT / "scripts/docker-lab-release.ps1"
PWSH = shutil.which("pwsh")
pytestmark = pytest.mark.skipif(PWSH is None, reason="PowerShell 7 required")


def run_script(script, *args, env=None):
    return subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-File", str(script), *args],
        capture_output=True, text=True, timeout=20, env=env,
    )


@pytest.mark.parametrize("parameter", ["ReleaseManifest", "ManifestSha256", "InstallationDirectory"])
def test_partial_release_never_reaches_developer_docker(parameter):
    result = run_script(DESKTOP, f"-{parameter}", "incomplete")
    assert result.returncode != 0
    assert "Supply all three release arguments" in result.stderr


@pytest.mark.parametrize("action", ["Build", "Invite"])
def test_release_rejects_unsupported_actions_before_docker(action, tmp_path):
    result = run_script(
        RELEASE, "-Action", action, "-ReleaseManifest", str(tmp_path / "absent.json"),
        "-ManifestSha256", "not-a-hash", "-InstallationDirectory", str(tmp_path / "private"),
    )
    assert result.returncode != 0
    assert "release_action_unsupported" in result.stderr
    assert not (tmp_path / "private").exists()


def reject_manifest(tmp_path, data, expected):
    path = tmp_path / "invalid.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    install = tmp_path / "private"
    result = run_script(
        RELEASE, "-ReleaseManifest", str(path), "-ManifestSha256",
        hashlib.sha256(path.read_bytes()).hexdigest(), "-InstallationDirectory", str(install),
    )
    assert result.returncode != 0
    assert expected in result.stderr
    assert not install.exists()


def test_manifest_cannot_self_certify_review(tmp_path):
    reject_manifest(tmp_path, {"approved": True}, "release_fields_invalid")


def test_unknown_retention_fails_before_any_image_identity(tmp_path):
    # Deliberately incomplete negative input, not a release fixture or image ID.
    data = dict(schema_version=1, source_commit="a" * 40, platform="linux/amd64",
                retention="ttl", runtime_contract="manual-v1", files={}, images={},
                baseline=None, candidate=None)
    reject_manifest(tmp_path, data, "manual_release_required")


def test_manifest_hash_mismatch_does_not_create_installation(tmp_path):
    path = tmp_path / "invalid.json"
    path.write_text("{}", encoding="utf-8")
    result = run_script(
        RELEASE, "-ReleaseManifest", str(path), "-ManifestSha256", "0" * 64,
        "-InstallationDirectory", str(tmp_path / "private"),
    )
    assert "release_manifest_hash_mismatch" in result.stderr
    assert not (tmp_path / "private").exists()


def test_ambient_proposal_cannot_enter_release(tmp_path):
    env = dict(os.environ, CYTELLECT_PROPOSAL_OPERATOR_CONFIG="operator-config-must-not-be-read")
    result = run_script(
        DESKTOP, "-ReleaseManifest", "absent", "-ManifestSha256", "invalid",
        "-InstallationDirectory", str(tmp_path / "private"), env=env,
    )
    assert "Proposal configuration is not supported" in result.stderr
    assert not (tmp_path / "private").exists()


def test_durable_reservation_refuses_overwrite(tmp_path):
    # Load only function AST nodes: never evaluate launcher/Docker statements.
    code = r"""
    $e=$null; $t=$null
    $ast=[Management.Automation.Language.Parser]::ParseFile($env:CHECK_SCRIPT,[ref]$t,[ref]$e)
    if ($e.Count) { throw 'parse_failure' }
    foreach ($name in @('Require','Keys','WriteNew','PlainPath','EnvironmentMap','JsonDocker')) {
      $node=$ast.Find({param($n) $n -is [Management.Automation.Language.FunctionDefinitionAst] -and $n.Name -eq $name},$false)
      . ([scriptblock]::Create($node.Extent.Text))
    }
    $p=Join-Path $env:CHECK_DIR 'reservation.json'
    WriteNew $p 'original'
    $failed=$false
    try { WriteNew $p 'replacement' } catch { $failed=$true }
    if (-not $failed -or [IO.File]::ReadAllText($p) -cne 'original') { throw 'reservation_overwritten' }
    $failed=$false
    try { PlainPath 'relative' } catch { $failed=$true }
    if (-not $failed) { throw 'relative_installation_accepted' }
    $failed=$false
    try { Keys @{unexpected=1} @('installation_id') } catch { $failed=$true }
    if (-not $failed) { throw 'unowned_record_accepted' }
    $failed=$false
    try { EnvironmentMap @('MODE=manual','MODE=ttl') } catch { $failed=$true }
    if (-not $failed) { throw 'duplicate_environment_accepted' }
    function Docker { '[{"metadata":"one"}]' }
    $array=JsonDocker @('read-only-stub')
    if ($array.Count -ne 1 -or $array[0].metadata -cne 'one') { throw 'single_inspect_array_lost' }
    """
    result = subprocess.run(
        [PWSH, "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, timeout=20,
        env=dict(os.environ, CHECK_SCRIPT=str(RELEASE), CHECK_DIR=str(tmp_path)),
    )
    assert result.returncode == 0, result.stderr


def test_release_compose_has_no_build_or_interpolation():
    text = (ROOT / "infra/compose.release.yaml").read_text(encoding="utf-8")
    assert "$" not in text
    config = json.loads(text)
    assert set(config["services"]) == {"api", "worker", "web", "data-init"}
    for service in config["services"].values():
        assert "build" not in service
        assert service["image"] == ""  # Not a fabricated installable release.
    for name in ("api", "worker"):
        assert config["services"][name]["environment"]["CYTELLECT_WORKSPACE_RETENTION_MODE"] == "manual"
    assert config["volumes"]["research"]["external"] is True

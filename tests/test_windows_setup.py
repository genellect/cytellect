"""Exercise the real PowerShell release-verification boundary without installation."""
import hashlib
import json
import os
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows PowerShell installer contract")
ROOT = Path(__file__).resolve().parents[1]


def release_fixture(directory):
    directory.mkdir()
    files = []
    for name in (
        "pyproject.toml", "uv.lock", "scripts/fiji_setup.py",
        "services/api/src/cytellect_api/local.py", "engines/fiji/runtime.lock.json", "apps/web/out/index.html",
    ):
        target = directory / name
        target.parent.mkdir(parents=True, exist_ok=True)
        content = b"public installer boundary test\n"
        target.write_bytes(content)
        files.append({"path": name, "sha256": hashlib.sha256(content).hexdigest(), "size": len(content)})
    return {"schema": "cytellect-local-release/1", "platform": "windows-x64",
            "version": "0.1.0-local.1", "source_commit": "a" * 40, "files": files}


def verify(directory, install_root):
    shell = Path(os.environ["SystemRoot"]) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    return subprocess.run(
        [str(shell), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(ROOT / "scripts/local_setup.ps1"),
         "-SourceRoot", str(directory), "-InstallRoot", str(install_root), "-Console", "-VerifyOnly", "-NoShortcut"],
        capture_output=True, text=True, check=False, timeout=30,
    )


def test_verified_release_does_not_install_or_download(tmp_path):
    source = tmp_path / "source with spaces"
    manifest = release_fixture(source)
    (source / "local-release.json").write_text(json.dumps(manifest))
    result = verify(source, tmp_path / "installation")
    assert result.returncode == 0, result.stdout + result.stderr
    assert not (tmp_path / "installation").exists()


@pytest.mark.parametrize("fault", ["modified", "traversal", "duplicate", "missing", "absolute", "alternate_stream", "platform"])
def test_release_rejects_unverified_or_unsafe_files(tmp_path, fault):
    source = tmp_path / "source"
    manifest = release_fixture(source)
    if fault == "modified":
        (source / "uv.lock").write_bytes(b"changed after manifest")
    elif fault == "traversal":
        manifest["files"][0]["path"] = "../outside.toml"
    elif fault == "duplicate":
        manifest["files"].append(manifest["files"][0].copy())
    elif fault == "missing":
        manifest["files"] = manifest["files"][:-1]
    elif fault == "absolute":
        manifest["files"][0]["path"] = str(source / "pyproject.toml")
    elif fault == "alternate_stream":
        manifest["files"][0]["path"] = "pyproject.toml:stream"
    else:
        manifest["platform"] = "unexpected-platform"
    (source / "local-release.json").write_text(json.dumps(manifest))
    result = verify(source, tmp_path / "installation")
    assert result.returncode == 1
    assert not (tmp_path / "installation").exists()
    assert str(source) not in result.stdout + result.stderr

"""The researcher-facing release text (scripts/release_notes.py)."""
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("release_notes", ROOT / "scripts/release_notes.py")
assert spec is not None and spec.loader is not None
release_notes = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release_notes)

COMMIT = "0" * 39 + "1"
SHA256 = "ab" * 32


def _manifest(folder: Path, version: str, commit: str = COMMIT) -> Path:
    folder.mkdir(exist_ok=True)
    (folder / f"Cytellect-update-{version}.json").write_text(json.dumps({
        "installer": {"bytes": 1075959778, "name": f"Cytellect-Setup-{version}.exe", "sha256": SHA256},
        "schema": "cytellect-update-manifest/1", "source_commit": commit, "version": version}), encoding="utf-8")
    return folder


def test_the_text_carries_the_signed_values_and_the_written_changes(tmp_path):
    text, written = release_notes.render(_manifest(tmp_path / "release", "0.1.0-local.21"), "0.1.0-local.21", COMMIT)
    assert written
    assert text.startswith("## Cytellect 0.1.0-local.21\n")
    assert "約 1.08 GB" in text
    assert "Cytellect-Setup-0.1.0-local.21.exe" in text
    assert (ROOT / "packaging/windows/release-highlights/0.1.0-local.21.ja.md").read_text(encoding="utf-8").strip() in text
    assert "{" not in text


def test_a_version_without_written_changes_links_the_commits(tmp_path):
    text, written = release_notes.render(_manifest(tmp_path / "release", "0.1.0-local.99"), "0.1.0-local.99", COMMIT,
                                         "v0.1.0-local.21")
    assert not written
    assert f"{release_notes.REPOSITORY}/compare/v0.1.0-local.21...{COMMIT}" in text


def test_the_text_is_for_researchers_not_the_test_record():
    template = release_notes.TEMPLATE.read_text(encoding="utf-8")
    for internal in ("BBBC007", "JUMP", "receipt", "gates", "SHA-256", "GPL", "PATH", "LOCALAPPDATA"):
        assert internal not in template


def test_a_manifest_for_another_commit_is_refused(tmp_path):
    folder = _manifest(tmp_path / "release", "0.1.0-local.21", commit="f" * 40)
    with pytest.raises(ValueError):
        release_notes.render(folder, "0.1.0-local.21", COMMIT)


def test_the_command_writes_the_text_and_reports_missing_changes(tmp_path, capsys):
    folder = _manifest(tmp_path / "release", "0.1.0-local.99")
    out = tmp_path / "notes.md"
    assert release_notes.main(["--release-dir", str(folder), "--version", "0.1.0-local.99", "--commit", COMMIT,
                               "--out", str(out)]) == 0
    assert "release-highlights/0.1.0-local.99.ja.md" in capsys.readouterr().out
    assert f"{release_notes.REPOSITORY}/commits/{COMMIT}" in out.read_text(encoding="utf-8")
    assert release_notes.main(["--release-dir", str(tmp_path / "missing"), "--version", "0.1.0-local.99",
                               "--commit", COMMIT, "--out", str(out)]) == 1

"""Size limit of the published demo files (scripts/check_public_tree.py, DM-10).

Only a temporary repository with a few small text files; the limit is lowered instead of creating large files.
"""
import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load():
    spec = importlib.util.spec_from_file_location("check_public_tree", ROOT / "scripts/check_public_tree.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules["check_public_tree"] = module
    spec.loader.exec_module(module)
    return module


cpt = load()


def repo(tmp_path: Path, files: dict[str, bytes], untracked: dict[str, bytes] | None = None) -> Path:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    for name, data in files.items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True)
    for name, data in (untracked or {}).items():
        path = tmp_path / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return tmp_path


SHOWCASE = {
    "apps/web/public/showcase/a.json": b"x" * 40,
    "apps/web/public/showcase/scene/b.json": b"y" * 60,
    "apps/web/public/other.json": b"z" * 500,
    "docs/note.md": b"w" * 500,
}


def test_counts_only_tracked_files_under_showcase(tmp_path):
    base = repo(tmp_path, SHOWCASE, untracked={"apps/web/public/showcase/local.json": b"u" * 1000})
    assert cpt.showcase_size(base, cpt.tracked_files(base)) == 100


def test_symlink_counts_as_its_target(tmp_path):
    base = repo(tmp_path, SHOWCASE)
    try:
        (base / "apps/web/public/showcase/link.json").symlink_to(base / "docs/note.md")
    except OSError:
        pytest.skip("symlinks need extra privileges on this system")
    subprocess.run(["git", "-C", str(base), "add", "-A"], check=True)
    names = cpt.tracked_files(base)
    assert "apps/web/public/showcase/link.json" in names
    assert cpt.showcase_size(base, names) == 600


@pytest.mark.parametrize(("limit", "rejected"), [(101, False), (100, False), (99, True)])
def test_limit_is_inclusive(tmp_path, capsys, monkeypatch, limit, rejected):
    base = repo(tmp_path, SHOWCASE)
    monkeypatch.setattr(cpt, "SHOWCASE_LIMIT_BYTES", limit)
    if rejected:
        with pytest.raises(SystemExit) as error:
            cpt.main(base)
        message = str(error.value)
        assert message.startswith("Public tree rejected: published demo files")
        assert "total 100 bytes" in message
        assert f"above the {limit}-byte" in message
        assert "unregistered data" not in message
    else:
        cpt.main(base)
        assert "Public tree check passed." in capsys.readouterr().out


def test_size_and_content_findings_are_both_reported(tmp_path, monkeypatch):
    base = repo(tmp_path, {**SHOWCASE, "apps/web/public/showcase/unregistered.png": b"p" * 10})
    monkeypatch.setattr(cpt, "SHOWCASE_LIMIT_BYTES", 50)
    with pytest.raises(SystemExit) as error:
        cpt.main(base)
    message = str(error.value)
    assert "1 unregistered data or sensitive-content findings" in message
    assert "total 110 bytes" in message
    assert "above the 50-byte" in message

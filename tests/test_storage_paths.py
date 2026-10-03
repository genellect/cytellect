"""Storage containment remains exact across Windows extended-path aliases."""

import os
from pathlib import PurePosixPath, PureWindowsPath

import pytest
from cytellect_api import db


@pytest.mark.parametrize("root,target,allowed", [
    (r"C:\private", r"C:\private\field", True),
    (r"C:\private", r"\\?\C:\private\field", True),
    (r"\\?\C:\private", r"C:\PRIVATE\field", True),
    (r"C:\private", r"\\?\c:\PRIVATE", True),
    (r"\\server\share\private", r"\\?\UNC\server\share\private\field", True),
    (r"\\?\UNC\server\share\private", r"\\SERVER\SHARE\PRIVATE\field", True),
    (r"C:\private", r"C:\private-sibling\field", False),
    (r"C:\private", r"\\?\C:\private-sibling\field", False),
    (r"C:\private", r"D:\private\field", False),
    (r"C:\private", r"C:\private\..\outside", False),
    (r"C:\private", r"C:private\field", False),
    (r"C:\private", r"\private\field", False),
    (r"C:\private", r"private\field", False),
    (r"C:\private", r"\\.\C:\private\field", False),
    (r"C:\private", r"\\?\GLOBALROOT\Device\HarddiskVolume1\private", False),
    (r"C:\private", r"\\?\Volume{00000000-0000-0000-0000-000000000000}\private", False),
    (r"\\server\share\private", r"\\server\other\private\field", False),
    (r"\\server\share\private", r"\\other\share\private\field", False),
    (r"\\server\share\private", r"\\?\UNC\server\share\private-sibling", False),
    (r"\\.\C:\private", r"\\.\C:\private\field", False),
])
def test_windows_namespace_containment(root, target, allowed):
    assert db._is_within_storage(PureWindowsPath(target), PureWindowsPath(root)) is allowed
    if not allowed:
        with pytest.raises(ValueError, match="^invalid_storage_path$"):
            db._relative_storage_path(PureWindowsPath(target), PureWindowsPath(root))


@pytest.mark.parametrize("root,target,expected", [
    (r"C:\private", r"\\?\C:\private\runs\attempt\output", "runs/attempt/output"),
    (r"\\?\C:\private", r"c:\PRIVATE\runs\attempt\output", "runs/attempt/output"),
    (r"C:\private", r"\\?\c:\PRIVATE", "."),
    (r"\\server\share\private", r"\\?\UNC\SERVER\SHARE\private\runs\output", "runs/output"),
    (r"\\?\UNC\server\share\private", r"\\server\share\private\runs\output", "runs/output"),
])
def test_windows_relative_artifact_names_preserve_posix_format(root, target, expected):
    assert db._relative_storage_path(PureWindowsPath(target), PureWindowsPath(root)) == expected


def test_posix_containment_remains_case_sensitive():
    root = PurePosixPath("/private")
    assert db._is_within_storage(root / "field", root)
    assert not db._is_within_storage(PurePosixPath("/PRIVATE/field"), root)
    assert not db._is_within_storage(PurePosixPath("/private-sibling/field"), root)


def test_storage_rejects_resolved_parent_escape(tmp_path):
    store = db.Store(tmp_path / "private")
    with pytest.raises(ValueError, match="^invalid_storage_path$"):
        store.safe_path("..", "outside")
    with pytest.raises(ValueError, match="^invalid_storage_path$"):
        store.relative_path(store.root / ".." / "outside")


def test_storage_relative_artifact_round_trip(tmp_path):
    store = db.Store(tmp_path / "private")
    artifact = store.safe_path("runs", "attempt", "output")
    artifact.mkdir(parents=True)
    assert store.relative_path(artifact) == "runs/attempt/output"
    assert store.safe_path(store.relative_path(artifact)) == artifact


@pytest.mark.skipif(os.name != "nt", reason="Windows realpath error transition")
def test_missing_parent_creation_during_realpath_keeps_valid_storage_path(tmp_path, monkeypatch):
    import ntpath

    store = db.Store(tmp_path / "private")
    parts = ("workspaces", "workspace", "fields", "field")
    candidate = store.root.joinpath(*parts)
    original = ntpath._getfinalpathname
    winerrors = []

    def create_parent_after_first_miss(path):
        if os.fspath(path) == str(candidate):
            try:
                return original(path)
            except OSError as error:
                winerrors.append(error.winerror)
                if len(winerrors) == 1:
                    assert error.winerror == 3
                    candidate.parent.mkdir(parents=True)
                raise
        return original(path)

    # Exercise the real ntpath/pathlib implementation, changing only the timing
    # of another uploader creating shared parents between two OS lookups.
    with monkeypatch.context() as patch:
        patch.setattr(ntpath, "_getfinalpathname", create_parent_after_first_miss)
        resolved = store.safe_path(*parts)
    assert winerrors == [3, 2, 2]
    assert str(resolved).startswith("\\\\?\\")
    assert not resolved.is_relative_to(store.root)  # Baseline check falsely rejects it.
    assert store.relative_path(resolved) == "workspaces/workspace/fields/field"
    resolved.mkdir()
    (resolved / "proof.txt").write_text("synthetic", encoding="utf-8")
    assert (candidate / "proof.txt").read_text(encoding="utf-8") == "synthetic"


@pytest.mark.skipif(os.name != "nt", reason="Windows junction containment")
def test_storage_rejects_junction_to_an_outside_directory(tmp_path):
    import _winapi

    store = db.Store(tmp_path / "private")
    outside = tmp_path / "outside"
    outside.mkdir()
    junction = store.root / "redirected"
    _winapi.CreateJunction(str(outside), str(junction))
    try:
        with pytest.raises(ValueError, match="^invalid_storage_path$"):
            store.safe_path("redirected", "field")
        with pytest.raises(ValueError, match="^invalid_storage_path$"):
            store.relative_path(junction / "field")
    finally:
        junction.rmdir()
    assert outside.is_dir()

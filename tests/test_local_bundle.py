"""The installer bundle must not accidentally distribute runtime/research files."""
import importlib.util
import json
import zipfile
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "build_local_bundle", Path(__file__).resolve().parents[1] / "scripts/build_local_bundle.py"
)
assert spec is not None and spec.loader is not None
bundle = importlib.util.module_from_spec(spec)
spec.loader.exec_module(bundle)


@pytest.mark.parametrize("name", [".env.local", "runtime/session.sqlite", "private.tiff", "report.pdf",
                                  "services/api/src/.env", "services/api/src/private.tif",
                                  "services/api/src/__pycache__/app.pyc", "apps/web/public/private.png"])
def test_source_allowlist_denies_research_and_runtime(name):
    assert not bundle.source_allowed(name)


def fixture_tree(root):
    names = bundle.ROOT_FILES | bundle.SCRIPTS | {"scripts/windows/Cytellect Setup.cmd"}
    for name in names:
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("reviewed source", encoding="utf-8")
    web = root / "apps/web/out"
    web.mkdir(parents=True)
    (web / "index.html").write_text("<html>local</html>", encoding="utf-8")
    return sorted(names), web


def test_manifest_has_exact_hashes_and_protects_existing_release(tmp_path):
    names, web = fixture_tree(tmp_path)
    files = bundle.collect_files(tmp_path, names, web)
    output = tmp_path / "release.zip"
    digest = bundle.write_bundle(output, files, "0.1.0-local.1", "a" * 40)
    import hashlib

    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("local-release.json"))
        assert manifest["source_commit"] == "a" * 40
        assert {entry["path"] for entry in manifest["files"]} == set(files)
        for entry in manifest["files"]:
            assert hashlib.sha256(archive.read(entry["path"])).hexdigest() == entry["sha256"]
    assert digest == hashlib.sha256(output.read_bytes()).hexdigest()
    with pytest.raises(FileExistsError):
        bundle.write_bundle(output, files, "0.1.0-local.1", "a" * 40)


def test_unexpected_static_file_is_not_silently_distributed(tmp_path):
    names, web = fixture_tree(tmp_path)
    (web / ".env").write_text("not public", encoding="utf-8")
    with pytest.raises(ValueError, match="unexpected_web_asset"):
        bundle.collect_files(tmp_path, names, web)


def test_generated_license_is_hashed_but_arbitrary_generated_files_are_rejected(tmp_path):
    names, web = fixture_tree(tmp_path)
    files = bundle.collect_files(tmp_path, names, web)
    output = tmp_path / "notices.zip"
    bundle.write_bundle(output, files, "0.1.0-local.1", "b" * 40,
                        {"THIRD_PARTY_WEB_NOTICES.txt": b"upstream license"})
    with zipfile.ZipFile(output) as archive:
        manifest = json.loads(archive.read("local-release.json"))
        assert "THIRD_PARTY_WEB_NOTICES.txt" in {entry["path"] for entry in manifest["files"]}
    with pytest.raises(ValueError, match="generated_asset_invalid"):
        bundle.write_bundle(tmp_path / "invalid.zip", files, "0.1.0-local.1", "b" * 40,
                            {"private.json": b"never distribute"})

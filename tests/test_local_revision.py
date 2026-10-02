import hashlib
import json

from cytellect_api.local import installed_source_revision


def release(tmp_path):
    entries = []
    for relative in ("packages/analysis/src/cytellect_analysis", "services/api/src/cytellect_api",
                     "services/worker/src/cytellect_worker"):
        file = tmp_path / relative / "__init__.py"
        file.parent.mkdir(parents=True)
        file.write_bytes(b"# packaged source\n")
        entries.append({"path": file.relative_to(tmp_path).as_posix(), "size": file.stat().st_size,
                        "sha256": hashlib.sha256(file.read_bytes()).hexdigest()})
    data = {"schema": "cytellect-local-release/1", "source_commit": "a" * 40, "files": entries}
    (tmp_path / "local-release.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def test_packaged_revision_requires_unchanged_and_complete_source(tmp_path):
    release(tmp_path)
    assert installed_source_revision(tmp_path) == "a" * 40
    source = tmp_path / "packages/analysis/src/cytellect_analysis/__init__.py"
    source.write_bytes(b"# changed source!\n")
    assert installed_source_revision(tmp_path) is None


def test_unlisted_extra_source_or_missing_manifest_never_claim_commit(tmp_path):
    assert installed_source_revision(tmp_path) is None
    release(tmp_path)
    (tmp_path / "services/api/src/cytellect_api/unlisted.py").write_text("# not in release")
    assert installed_source_revision(tmp_path) is None


def test_incomplete_and_escaping_manifest_cannot_claim_commit(tmp_path):
    data = release(tmp_path)
    data["files"].pop()
    manifest = tmp_path / "local-release.json"
    manifest.write_text(json.dumps(data))
    assert installed_source_revision(tmp_path) is None
    data["files"][0]["path"] = "../outside.py"
    manifest.write_text(json.dumps(data))
    assert installed_source_revision(tmp_path) is None

"""Derived updates retain the origin of the published workspace and recordings."""
import json
from pathlib import Path
from types import SimpleNamespace

from cytellect_showcase import build
from cytellect_showcase.build import generation_provenance


def test_examples_keep_the_original_capture_commit():
    previous = {"generated_from_commit": "capture", "derived_updates": {"figures": "drawing"}}
    assert generation_provenance(previous, {"reseed", "examples"}, "examples") == {
        "generated_from_commit": "capture", "derived_updates": {"figures": "drawing", "examples": "examples"}}


def test_a_new_recording_sets_a_new_capture_commit():
    assert generation_provenance({"generated_from_commit": "old"}, {"reseed", "publish", "snapshot", "journal"}, "new") == {
        "generated_from_commit": "new"}


def test_derived_manifest_preserves_the_capture_environment(tmp_path, monkeypatch):
    manifest = Path(__file__).resolve().parents[1] / "services/showcase/datasets/zenodo-6643470-oxaliplatin.json"
    (tmp_path / "manifest.json").write_text(json.dumps({"generated_from_commit": "capture", "runtime": {"python": "original"},
                                                       "journal": {"kept_scenes": ["public:tour"], "reused_from_commit": "earlier"}}))
    monkeypatch.setattr(build, "runtime_versions", lambda fiji: {"python": "update"})
    monkeypatch.setattr(build, "git_commit", lambda: "derived")
    args = SimpleNamespace(out=tmp_path, work=tmp_path / "work", stages="reseed,examples", fiji="not-invoked")
    build.write_manifest(args, [(manifest, json.loads(manifest.read_text(encoding="utf-8")))], {})
    record = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
    assert record["generated_from_commit"] == "capture"
    assert record["runtime"] == {"python": "original"}
    assert record["journal"] == {"kept_scenes": ["public:tour"], "reused_from_commit": "earlier"}
    assert record["derived_update_environments"] == {"examples": {"python": "update"}}

"""The combined presentation build consumes the newly recorded journal, never the old catalogue input."""
import json
from pathlib import Path

from cytellect_showcase import build


def test_figures_follow_the_completed_recording_and_can_run_on_their_own(tmp_path, monkeypatch):
    manifest = Path(__file__).resolve().parents[1] / "services/showcase/datasets/zenodo-6643470-oxaliplatin.json"
    identity = json.loads(manifest.read_text(encoding="utf-8"))["id"]
    calls = []
    def reseed(out, work, manifests, state):
        calls.append("reseed")
        state["scenes"][identity] = {"scenario":{"workspace_id":"public-workspace","fields":[],"owner":"public-owner"}}
    def stage(name):
        def run(*args, **kwargs):
            calls.append(name)
            return {}
        return run
    monkeypatch.setattr(build, "reseed", reseed)
    for name in ("publish", "snapshot", "journal", "figures"):
        monkeypatch.setattr(build, name, stage(name))
    monkeypatch.setattr(build, "write_manifest", lambda *args: None)
    common = [str(manifest), "--work", str(tmp_path / "build"), "--cache", str(tmp_path / "cache"),
              "--out", str(tmp_path / "out"), "--fiji", str(tmp_path / "no-detector")]
    build.main([*common, "--stages", "reseed,publish,snapshot,journal,figures"])
    assert calls == ["reseed", "publish", "snapshot", "journal", "figures"]
    calls.clear()
    build.main([*common, "--stages", "figures"])
    assert calls == ["figures"]

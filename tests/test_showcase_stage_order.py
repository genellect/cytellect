"""The combined presentation build consumes the newly recorded journal, never the old catalogue input."""
import json
import re
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


def test_manual_recording_cannot_emit_skipped_required_verify_checks():
    workflows = Path(__file__).resolve().parents[1] / ".github/workflows"
    verify = (workflows / "ci.yml").read_text(encoding="utf-8")
    recording = (workflows / "showcase-recording.yml").read_text(encoding="utf-8")
    triggers = recording.split("on:\n", 1)[1].split("\npermissions:", 1)[0]
    assert re.findall(r"^  ([\w-]+):", triggers, re.M) == ["workflow_dispatch"]
    job_names = lambda text: set(re.findall(r"^  ([\w-]+):", text.split("\njobs:\n", 1)[1], re.M))  # noqa: E731
    assert job_names(recording) == {"showcase-presentation"}
    assert not (job_names(recording) & job_names(verify))
    assert "showcase_presentation" not in verify
    assert recording.index("verify_showcase_update.py") < recording.index("name: showcase-presentation-complete")

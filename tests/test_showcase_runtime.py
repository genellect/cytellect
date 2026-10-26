"""The serverless showcase runs the real API, job handlers and analysis package in one process.

CPython drives ``cytellect_showcase.runtime`` exactly as the browser worker does
(``boot`` then ``handle``); the Node test runs the same seed inside Pyodide.
"""

import asyncio
import io
import json
import os
import shutil
import subprocess
import sys
import types
import zipfile
from pathlib import Path

import pytest
from cytellect_showcase import runtime
from showcase_seed import DRAFT, ORIGIN, build_seed, fake_detect_nuclei
from showcase_steps import assert_close, assert_workflow, numeric_view, run_steps_in_cpython, workflow_steps

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_DIR = ROOT / "apps/web/public/showcase/runtime"
CONFIG = ROOT / "apps/web/src/lib/showcase/runtime-config.json"
HARNESS = ROOT / "services/showcase/pyodide/harness.mjs"
GOAL = "視野ごとのGFP輝度を見たい"
MUTATE = [["content-type", "application/json"], ["x-cytellect-request", "1"]]


@pytest.fixture(scope="module")
def seed(tmp_path_factory):
    directory = tmp_path_factory.mktemp("showcase-seed")
    data, info = build_seed(directory, proposals={GOAL: DRAFT})
    path = directory / "seed.zip"
    path.write_bytes(data)
    return path, info


@pytest.fixture
def fake_replay(monkeypatch):
    """Stand-in for the shared detection replay when ``detections.py`` is absent."""
    try:
        from cytellect_showcase import detections  # type: ignore[attr-defined]  # noqa: F401
        return
    except ImportError:
        pass
    import cytellect_worker.regions as regions

    module = types.ModuleType("cytellect_showcase.detections")
    module.install_replay = lambda recordings: setattr(regions, "detect_nuclei", fake_detect_nuclei)
    monkeypatch.setitem(sys.modules, "cytellect_showcase.detections", module)


@pytest.fixture
def isolated():
    yield
    runtime.shutdown()


def font_dir():
    fonts = json.loads(CONFIG.read_text(encoding="utf-8"))["fonts"] if CONFIG.is_file() else []
    return RUNTIME_DIR if fonts and all((RUNTIME_DIR / item["file"]).is_file() for item in fonts) else None


class Client:
    async def call(self, method, path, body=None):
        response = await runtime.handle(method, path, MUTATE if method != "GET" else [],
                                        None if body is None else json.dumps(body).encode())
        try:
            value = json.loads(response["body"]) if response["body"] else None
        except (UnicodeDecodeError, ValueError):
            value = response["body"]
        return response["status"], value, response

    async def ok(self, method, path, body=None, status=200):
        code, value, _ = await self.call(method, path, body)
        assert code == status, (method, path, code, value)
        return value

    async def job(self, job_id):
        await runtime.settle()
        job = await self.ok("GET", f"/v1/jobs/{job_id}")
        assert job["state"] == "succeeded", (job["kind"], job.get("error"))
        return job


def run(coroutine):
    return asyncio.run(coroutine)


def test_full_workflow_runs_inline_from_seed(seed, tmp_path, fake_replay, isolated):
    path, info = seed

    async def scenario():
        await runtime.boot(path.read_bytes(), ORIGIN, root=tmp_path / "browser", font_dir=font_dir())
        client = Client()
        # The session is created internally; the caller never sends a cookie.
        assert (await client.ok("GET", "/v1/session"))["authenticated"] is True
        code, _, response = await client.call("GET", "/v1/workspaces")
        assert code == 200 and not any(name.lower() == "set-cookie" for name, _ in response["headers"])
        wid = info["workspace_id"]
        assert [w["id"] for w in await client.ok("GET", "/v1/workspaces")] == [wid]
        fields = await client.ok("GET", f"/v1/workspaces/{wid}/region-fields")
        assert {f["id"] for f in fields} == set(info["field_ids"])
        preview = await client.call("GET", f"/v1/region-fields/{info['field_ids'][0]}/preview?channel_id=gfp")
        assert preview[0] == 200 and preview[2]["body"].startswith(b"\x89PNG")
        selection = await client.ok("GET", f"/v1/workspaces/{wid}/selection")
        adopted = {entry["field_id"]: entry["revision_id"] for entry in selection["entries"]}
        fid = info["field_ids"][0]
        before = await client.ok("GET", f"/v1/revisions/{adopted[fid]}/region-measurements")
        rows = before["field_tables"][fid]["rows"]
        masks = await client.ok("GET", f"/v1/revisions/{adopted[fid]}/region-masks?field_id={fid}")
        removed = masks["regions"][0]["id"]
        # As the workspace UI does: select the saved revision, then delete one region.
        await client.ok("POST", f"/v1/workspaces/{wid}/current", {"revision_id": adopted[fid]})
        # A region deletion is a mutating request: its job runs inline afterwards.
        edited = await client.ok("POST", f"/v1/revisions/{adopted[fid]}/region-edits", {
            "field_id": fid, "region_set_id": "nuclei", "operation": "delete", "ids": [removed],
            "expected_mask_revision_id": before["field_masks"][fid]["mask_revision_id"]}, status=202)
        await client.job(edited["job_id"])
        after = await client.ok("GET", f"/v1/revisions/{edited['revision_id']}/region-measurements")
        assert len(after["field_tables"][fid]["rows"]) < len(rows)
        assert removed not in {row["region_id"] for row in after["field_tables"][fid]["rows"]}
        for entry in selection["entries"]:
            if entry["field_id"] == fid:
                entry["revision_id"] = edited["revision_id"]
                if entry.get("target_revisions"):
                    entry["target_revisions"]["nuclei"] = edited["revision_id"]
        selection = await client.ok("POST", f"/v1/workspaces/{wid}/selection", selection)
        workspace = await client.ok("GET", f"/v1/workspaces/{wid}")
        sources = [{"field_id": e["field_id"], "revision_id": e["revision_id"]} for e in selection["entries"]]
        metadata = {f["id"]: f["metadata"] for f in fields}
        cohort = await client.ok("POST", f"/v1/workspaces/{wid}/region-cohorts", {
            "sources": sources, "metadata": metadata, "workspace_selection": selection,
            "expected_active_revision_id": workspace["active_revision"]}, status=202)
        await client.job(cohort["job_id"])
        rid = cohort["revision_id"]
        await client.ok("POST", f"/v1/revisions/{rid}/review", {})
        selection_spec = {"source": "region", "region_set_id": "nuclei", "channel_id": "gfp", "metric": "mean"}
        described = await client.ok("POST", f"/v1/revisions/{rid}/descriptive", {
            "mode": "descriptive", "selection": selection_spec,
            "plot": {"preset": "nature-double", "language": "ja" if font_dir() else "en"},
            "figure_policy": {"version": "2.0.0", "layout": "field-pages"}}, status=202)
        await client.job(described["job_id"])
        description = await client.ok("GET", f"/v1/jobs/{described['job_id']}/result")
        assert description["figure"]["status"] == "ready", description["figure"]
        statistics = await client.ok("POST", f"/v1/revisions/{rid}/common-statistics", {
            "mode": "region-experimental-unit", "version": "2.0.0", "selection": selection_spec,
            "design": {"kind": "independent", "confirmed": True, "unit_definition": "Separate crops (test only)"},
            "conditions": ["A01", "A12"],
            "comparison_family": {"family_id": "planned-1", "kind": "control", "control": "A01",
                                  "contrasts": [["A01", "A12"]]},
            "acquisition_review": {"confirmed": True, "basis": "same-settings"}, "missingness_confirmed": True,
            "test": "mann-whitney-u", "plot": {"kind": "box", "language": "en", "y_label": "GFP"}}, status=202)
        await client.job(statistics["job_id"])
        result = await client.ok("GET", f"/v1/jobs/{statistics['job_id']}/common-statistics")
        assert [row["experimental_units"] for row in result["counts"]] == [2, 2]
        svg = await client.call("GET", f"/v1/jobs/{statistics['job_id']}/files/figure.svg")
        assert svg[0] == 200 and b"<svg" in svg[2]["body"]
        export = await client.ok("POST", f"/v1/revisions/{rid}/export", status=202)
        await client.job(export["job_id"])
        rendered = await client.ok("POST", f"/v1/jobs/{statistics['job_id']}/figure-render", {
            "request_id": "showcase-render", "plot": {"y_label": "GFP mean"}}, status=202)
        await client.job(rendered["job_id"])
        figure = await client.ok("GET", f"/v1/jobs/{rendered['job_id']}/figure-render")
        assert figure["comparisons"] == result["comparisons"]
        package = await client.ok("POST", f"/v1/jobs/{rendered['job_id']}/publication-package", {
            "analysis_job_id": export["job_id"], "request_id": "showcase-package"}, status=202)
        await client.job(package["job_id"])
        code, _, response = await client.call("GET", f"/v1/jobs/{package['job_id']}/files/publication.zip")
        assert code == 200
        with zipfile.ZipFile(io.BytesIO(response["body"])) as bundle:
            assert {"analysis.zip", "manifest.json", "figure-result.json"} <= set(bundle.namelist())
        # The selection changes after the statistics are saved (statistics of another region do): the
        # build's rederive replays each job under the selection it was saved with, then restores the last.
        changed = await client.ok("POST", f"/v1/workspaces/{wid}/selection", selection)
        from cytellect_showcase.rederive import rederive_in_place
        redone = rederive_in_place()
        assert redone["statistics"] >= 2 and redone["figure_render"] >= 1
        assert await client.ok("GET", f"/v1/workspaces/{wid}/selection") == changed
        jobs = await client.ok("GET", f"/v1/workspaces/{wid}/jobs")
        assert jobs and all(job["state"] in ("succeeded", "failed", "cancelled") for job in jobs)

    run(scenario())


def test_proposal_replay_hit_and_miss(seed, tmp_path, fake_replay, isolated):
    path, info = seed

    async def scenario():
        await runtime.boot(path.read_bytes(), ORIGIN, root=tmp_path / "browser")
        client = Client()
        route = f"/v1/workspaces/{info['workspace_id']}/proposal-drafts"
        hit = await client.ok("POST", route, {"goal": GOAL, "transmission_confirmed": True})
        assert hit["proposal"]["draft"]["recipe"] == DRAFT["recipe"]
        assert [link["channel_id"] for link in hit["channels"]] == ["dna", "gfp"]
        for _ in range(2):  # Asking again is the same notice, never an explicit-retry demand.
            code, value, _ = await client.call("POST", route, {"goal": "記録していない目的", "transmission_confirmed": True})
            assert code == 409 and value["detail"] == "showcase_proposal_not_recorded"

    run(scenario())


def _reseeded(path: Path, staging: Path, proposals: dict) -> bytes:
    with zipfile.ZipFile(path) as archive:
        archive.extractall(staging)
    (staging / "proposals.json").write_text(json.dumps(proposals, ensure_ascii=False), encoding="utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for item in sorted(staging.rglob("*")):
            if item.is_file() and item.relative_to(staging).parts[0] != "tmp":
                archive.write(item, item.relative_to(staging).as_posix())
    return buffer.getvalue()


def test_authored_preset_drafts_answer_changed_contexts_but_model_outputs_do_not(seed, tmp_path, fake_replay, isolated):
    """A demo-authored preset draft depends only on its instruction; a changed context still gets it."""
    from cytellect_analysis.proposal_contracts import PROPOSAL_PROMPT_VERSION
    from showcase_seed import RECORDED_MODEL

    path, info = seed
    identity = {"model": RECORDED_MODEL, "prompt_version": PROPOSAL_PROMPT_VERSION}
    mismatched = {**DRAFT, "channels": DRAFT["channels"][:1]}
    entries = {  # keys never equal a real context digest: only the authored fallback can answer
        "a" * 64: {**identity, "draft": DRAFT, "source": "showcase-authored", "goal": GOAL, "previous_goal": ""},
        "b" * 64: {**identity, "draft": DRAFT, "goal": "モデルの出力"},
        "c" * 64: {**identity, "draft": mismatched, "source": "showcase-authored", "goal": "検証に通らない案"},
    }
    seed_bytes = _reseeded(path, tmp_path / "staging", {"version": 1, "entries": entries})

    async def scenario():
        await runtime.boot(seed_bytes, ORIGIN, root=tmp_path / "browser")
        client = Client()
        route = f"/v1/workspaces/{info['workspace_id']}/proposal-drafts"
        hit = await client.ok("POST", route, {"goal": f" {GOAL} ", "transmission_confirmed": True})
        assert hit["proposal"]["draft"]["recipe"] == DRAFT["recipe"]
        assert hit["proposal"]["model"] == RECORDED_MODEL
        for goal in ("モデルの出力", "検証に通らない案"):
            code, value, _ = await client.call("POST", route, {"goal": goal, "transmission_confirmed": True})
            assert code == 409 and value["detail"] == "showcase_proposal_not_recorded", goal

    run(scenario())


def test_unrecorded_detection_is_a_field_notice_and_logout_recovers_session(seed, tmp_path, monkeypatch, isolated):
    path, info = seed

    # No replay recordings are installed: every detection is unrecorded.
    monkeypatch.setitem(sys.modules, "cytellect_showcase.detections", None)

    async def scenario():
        await runtime.boot(path.read_bytes(), ORIGIN, root=tmp_path / "browser")
        client = Client()
        wid = info["workspace_id"]
        fid = info["field_ids"][1]
        spec = await client.ok("GET", f"/v1/workspaces/{wid}/analysis-spec")
        spec["spec"]["settings"]["nuclearProbability"] = 0.61
        saved = await client.ok("PUT", f"/v1/workspaces/{wid}/analysis-spec", spec)
        created = await client.ok("POST", f"/v1/workspaces/{wid}/runs", {
            "request_id": "unrecorded", "spec_version": saved["version"], "target": "nuclei",
            "field_ids": [fid]}, status=202)
        await runtime.settle()
        result = await client.ok("GET", f"/v1/workspaces/{wid}/runs/{created['id']}")
        # Without a recording for these settings the field fails closed with a notice code.
        assert result["state"] == "failed", result
        assert result["steps"][0]["error"] == "showcase_detection_not_recorded"
        await client.ok("DELETE", "/v1/session")
        assert (await client.ok("GET", "/v1/session"))["authenticated"] is True

    run(scenario())


def test_boot_rejects_unsafe_seed_members_and_keeps_production_unpatched(tmp_path, isolated):
    import cytellect_api.proposals as proposals
    import cytellect_worker.regions as regions

    original = (proposals.request_draft, regions.detect_nuclei)
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("cytellect.sqlite", b"")
        archive.writestr("../escape.txt", b"x")
    with pytest.raises(ValueError, match="showcase_seed_invalid"):
        run(runtime.boot(buffer.getvalue(), ORIGIN, root=tmp_path))
    with pytest.raises(ValueError, match="showcase_origin_invalid"):
        run(runtime.boot(buffer.getvalue(), "javascript:alert(1)", root=tmp_path))
    with pytest.raises(RuntimeError, match="showcase_not_booted"):
        run(runtime.handle("GET", "/v1/session", [], None))
    assert (proposals.request_draft, regions.detect_nuclei) == original


def test_seed_description_restore_hook_and_empty_proposals(seed, tmp_path, monkeypatch, isolated):
    """showcase.json names the owner (build sessions are deleted); seed.restore runs before the app."""
    from cytellect_api.db import Store, sessions
    from sqlalchemy import delete

    path, info = seed
    staging = tmp_path / "staging"
    with zipfile.ZipFile(path) as archive:
        archive.extractall(staging)
    store = Store(staging)
    owner = store.rows(sessions)[0]["owner"]
    with store.transaction() as conn:
        conn.execute(delete(sessions))
    store.engine.dispose()
    (staging / "showcase.json").write_text(json.dumps({"workspace_id": info["workspace_id"], "owner": owner}), encoding="utf-8")
    (staging / "proposals.json").write_text("{}", encoding="utf-8")
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for item in sorted(staging.rglob("*")):
            if item.is_file() and item.relative_to(staging).parts[0] != "tmp":
                archive.write(item, item.relative_to(staging).as_posix())
    restored = []
    module = types.ModuleType("cytellect_showcase.seed")
    module.restore = lambda data_dir: restored.append(sorted(p.name for p in Path(data_dir).iterdir()))
    monkeypatch.setitem(sys.modules, "cytellect_showcase.seed", module)
    # `from . import seed` reads the package attribute once the real module was imported.
    import cytellect_showcase
    monkeypatch.setattr(cytellect_showcase, "seed", module, raising=False)

    async def scenario():
        await runtime.boot(buffer.getvalue(), ORIGIN, root=tmp_path / "browser")
        client = Client()
        assert [w["id"] for w in await client.ok("GET", "/v1/workspaces")] == [info["workspace_id"]]
        route = f"/v1/workspaces/{info['workspace_id']}/proposal-drafts"
        code, value, _ = await client.call("POST", route, {"goal": GOAL, "transmission_confirmed": True})
        assert code == 409 and value["detail"] == "showcase_proposal_not_recorded"

    run(scenario())
    assert restored and "cytellect.sqlite" in restored[0] and "showcase.json" in restored[0]


def test_matplotlib_310_numeric_weight_shim_is_reversible(monkeypatch):
    import matplotlib
    from cytellect_showcase import _compat
    from matplotlib import font_manager

    assert _compat.numeric_font_weights() is None  # uv.lock pins Matplotlib 3.11: no change
    monkeypatch.setattr(matplotlib, "__version__", "3.10.8")
    before = dict(font_manager.weight_dict)
    undo = _compat.numeric_font_weights()
    assert undo is not None and font_manager.weight_dict[400] == 400 and font_manager.weight_dict["bold"] == 700
    undo()
    assert font_manager.weight_dict == before


def test_drain_publishes_handler_failures_with_safe_codes(seed, tmp_path, fake_replay, isolated, monkeypatch):
    """A failing or crashing job is finished (never left running) with an allowlisted code only."""
    from cytellect_api.db import jobs
    from cytellect_showcase import _executor

    path, info = seed

    async def scenario():
        await runtime.boot(path.read_bytes(), ORIGIN, root=tmp_path / "browser")
        client = Client()
        rid = info["selection"]["entries"][0]["revision_id"]
        monkeypatch.setattr("cytellect_worker.main.run_export",
                            lambda *a: (_ for _ in ()).throw(RuntimeError("/private/path/leak")))
        queued = await client.ok("POST", f"/v1/revisions/{rid}/export", status=202)
        await runtime.settle()
        job = runtime._require().store.one(jobs, id=queued["job_id"])
        assert job["state"] == "failed" and job["error"] == "analysis_failed" and job["lease_until"] == 0
        assert _executor.drain(runtime._require().store, runtime._require().settings) == 0

    run(scenario())


def test_checkout_detection_keeps_repository_protection(tmp_path):
    from cytellect_api.config import Settings, checkout_root, configure_private_tmp

    assert checkout_root() == ROOT
    with pytest.raises(ValueError, match="outside the repository"):
        configure_private_tmp(Settings(ROOT / "private-data"))
    # Pyodide installs four levels below "/" (/lib/python3.x/site-packages): no checkout.
    # (A path absent on this host, so no symlink such as /lib -> /usr/lib applies.)
    assert checkout_root("/nonexistent-lib/python3.14/site-packages/cytellect_api/config.py") is None
    # A repository copied to the filesystem root keeps the protection.
    fake_root = tmp_path / "root"
    module = fake_root / "services/api/src/cytellect_api/config.py"
    module.parent.mkdir(parents=True)
    (fake_root / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    assert checkout_root(module) == fake_root


def node():
    return shutil.which("node") or next((str(p) for p in Path.home().glob(".local/share/cytellect-cloud/node-*/bin/node")), None)


def test_runtime_config_lists_hashed_files():
    import hashlib

    config = json.loads(CONFIG.read_text(encoding="utf-8"))
    assert config["indexURL"] == f"https://cdn.jsdelivr.net/pyodide/v{config['pyodideVersion']}/full/"
    for item in [*config["wheels"], *config["fonts"]]:
        assert hashlib.sha256((RUNTIME_DIR / item["file"]).read_bytes()).hexdigest() == item["sha256"]
    package = json.loads((ROOT / "services/showcase/pyodide/package.json").read_text(encoding="utf-8"))
    assert package["devDependencies"]["pyodide"] == config["pyodideVersion"]


def pyodide_cache():
    configured = os.environ.get("CYTELLECT_PYODIDE_CACHE")
    version = json.loads(CONFIG.read_text(encoding="utf-8"))["pyodideVersion"]
    return Path(configured) if configured else Path.home() / ".cache/cytellect/pyodide" / version


def test_cpython_runner_executes_the_harness_script(seed, tmp_path, fake_replay, isolated):
    path, info = seed

    async def scenario():
        await runtime.boot(path.read_bytes(), ORIGIN, root=tmp_path / "browser", font_dir=font_dir())
        return await run_steps_in_cpython(workflow_steps(info, GOAL))

    assert_workflow(run(scenario()), info, DRAFT["recipe"])


def test_pyodide_harness_end_to_end_matches_cpython(seed, tmp_path, fake_replay, isolated):
    """Pyodide in Node, loaded like the browser worker; outputs equal the CPython run."""
    executable = node()
    module = ROOT / "services/showcase/pyodide/node_modules/pyodide/pyodide.mjs"
    if executable is None or not module.is_file():
        pytest.skip("Node.js or the pinned pyodide npm package is not installed "
                    "(pnpm install --frozen-lockfile): Pyodide harness NOT executed")
    path, info = seed
    steps = workflow_steps(info, GOAL)
    script = tmp_path / "requests.json"
    script.write_text(json.dumps(steps, ensure_ascii=False), encoding="utf-8")
    cache = pyodide_cache()
    cache.mkdir(parents=True, exist_ok=True)
    # The harness has no stand-in detector; this script never detects (edits reuse masks).
    environment = {**os.environ, "NODE_USE_ENV_PROXY": "1"}
    completed = subprocess.run([executable, str(HARNESS), "--seed", str(path), "--requests", str(script),
                                "--origin", ORIGIN, "--cache", str(cache)],
                               capture_output=True, text=True, timeout=1800, env=environment, check=False)
    assert completed.returncode == 0, completed.stderr[-4000:]
    lines = [json.loads(line) for line in completed.stdout.splitlines() if line.startswith("{")]
    summary = lines.pop()
    assert summary["summary"] is True
    assert_workflow(lines, info, DRAFT["recipe"])

    async def reference():
        await runtime.boot(path.read_bytes(), ORIGIN, root=tmp_path / "cpython", font_dir=font_dir())
        return await run_steps_in_cpython(steps)

    assert_close(numeric_view(lines), numeric_view(run(reference())))

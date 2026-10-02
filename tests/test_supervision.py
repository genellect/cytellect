"""Failure injection at process/DB boundaries; no scientific data or engine mocks."""
import subprocess
import sys
import time
from types import SimpleNamespace

import psutil
import pytest
from cytellect_api.config import Settings
from cytellect_api.db import Store, jobs, revisions, uid, workspaces
from cytellect_worker.child import lease_is_live
from cytellect_worker.supervision import execute


def queued(tmp_path):
    settings = Settings(tmp_path)
    store = Store(tmp_path)
    wid, rid, jid = uid(), uid(), uid()
    with store.transaction() as conn:
        conn.execute(workspaces.insert().values(id=wid, owner=uid(), title="unit-test", created=time.time(), expires=time.time()+86400, deleted=False, bytes=0))
        conn.execute(revisions.insert().values(id=rid, workspace_id=wid, config={}, state="queued", created=time.time()))
        conn.execute(jobs.insert().values(id=jid, workspace_id=wid, revision_id=rid, kind="analysis", state="queued", payload={}, created=time.time(), attempts=0))
    return store, settings, store.claim()


def test_launch_failure_is_sanitized_and_request_removed(tmp_path, monkeypatch):
    store, settings, job = queued(tmp_path)

    def broken_launch(*args, **kwargs):
        raise OSError("private-path-and-experiment-must-never-be-recorded")

    monkeypatch.setattr(subprocess, "Popen", broken_launch)
    assert execute(store, settings, job)
    saved = store.one(jobs, id=job["id"])
    assert saved["state"] == "failed"
    assert saved["error"] == "worker_process_start_failed"
    assert saved["lease_until"] == 0 and saved["result_dir"] is None
    assert not store.safe_path("runs", job["lease"], "request.json").exists()


def sleeping_process(monkeypatch):
    original = subprocess.Popen
    launched = []

    def launch(*args, **kwargs):
        # Keep the production session, handles and no-output flags. Only the task
        # is a real bounded sleeping process, avoiding incidental analysis speed.
        process = original([sys.executable, "-c", "import time; time.sleep(60)"], **kwargs)
        launched.append(process)
        return process

    monkeypatch.setattr(subprocess, "Popen", launch)
    return launched


def test_parent_db_heartbeat_error_stops_real_child_before_releasing_lease(tmp_path, monkeypatch):
    store, settings, job = queued(tmp_path)
    launched = sleeping_process(monkeypatch)

    def unavailable(_):
        raise OSError("private-db-location")

    monkeypatch.setattr(store, "heartbeat", unavailable)
    assert execute(store, settings, job)
    assert len(launched) == 1 and launched[0].poll() is not None
    saved = store.one(jobs, id=job["id"])
    assert saved["error"] == "worker_supervision_failed" and saved["lease_until"] == 0
    assert not store.safe_path("runs", job["lease"], "request.json").exists()


def test_continuing_db_outage_cannot_keep_child_or_descriptor_alive(tmp_path, monkeypatch):
    store, settings, job = queued(tmp_path)
    launched = sleeping_process(monkeypatch)

    def unavailable_transaction():
        raise OSError("private-db-location")

    def unavailable(_):
        monkeypatch.setattr(store, "transaction", unavailable_transaction)
        raise OSError("private-db-location")

    monkeypatch.setattr(store, "heartbeat", unavailable)
    assert not execute(store, settings, job)
    assert launched[0].poll() is not None
    assert not store.safe_path("runs", job["lease"], "request.json").exists()
    assert store.one(jobs, id=job["id"])["result_dir"] is None


@pytest.mark.parametrize("failure", ["db", "parent", "lease", "cancelled", "deleted", "expired"])
def test_child_watchdog_fails_closed_on_unverifiable_lease(failure):
    job = {"id": "job", "workspace_id": "workspace", "lease": "lease"}
    current = {"state": "running", "lease": "lease", "lease_until": time.time()+60}
    workspace = {"deleted": False}
    parent = SimpleNamespace(is_running=lambda: True, create_time=lambda: 1)
    if failure == "parent":
        parent.create_time = lambda: 2
    if failure == "lease":
        current["lease"] = "successor"
    if failure == "cancelled":
        current["state"] = "cancelled"
    if failure == "deleted":
        workspace["deleted"] = True
    if failure == "expired":
        current["lease_until"] = 0

    def one(table, **kwargs):
        if failure == "db":
            raise OSError("private-db-location")
        return current if table is jobs else workspace

    assert not lease_is_live(SimpleNamespace(one=one), job, parent, 1)


def test_child_watchdog_accepts_only_current_live_owner_and_lease():
    job = {"id": "job", "workspace_id": "workspace", "lease": "lease"}
    current = {"state": "running", "lease": "lease", "lease_until": time.time()+60}
    store = SimpleNamespace(one=lambda table, **kwargs: current if table is jobs else {"deleted": False})
    parent = SimpleNamespace(is_running=lambda: True, create_time=lambda: 1)
    assert lease_is_live(store, job, parent, 1)


def test_cancel_stops_observed_descendant_process(tmp_path, monkeypatch):
    store, settings, job = queued(tmp_path)
    original = subprocess.Popen
    marker = tmp_path / "descendant.pid"
    code = "import subprocess,sys,time,pathlib; p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid)); time.sleep(60)"
    launched = []

    def launch(*args, **kwargs):
        process = original([sys.executable, "-c", code, str(marker)], **kwargs)
        launched.append(process)
        return process

    ticks = 0

    def heartbeat(_):
        nonlocal ticks
        ticks += 1
        return ticks == 1

    monkeypatch.setattr(subprocess, "Popen", launch)
    monkeypatch.setattr(store, "heartbeat", heartbeat)
    assert execute(store, settings, job)
    assert launched[0].poll() is not None and marker.exists()
    pid = int(marker.read_text())
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert store.one(jobs, id=job["id"])["error"] == "job_cancelled_or_lease_lost"


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX session/process-group guarantee; Windows uses observed process tree")
def test_posix_reaps_descendant_when_direct_child_exits_first(tmp_path, monkeypatch):
    store, settings, job = queued(tmp_path)
    original = subprocess.Popen
    marker = tmp_path / "orphan.pid"
    code = "import subprocess,sys,pathlib; p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(60)']); pathlib.Path(sys.argv[1]).write_text(str(p.pid))"

    def launch(*args, **kwargs):
        return original([sys.executable, "-c", code, str(marker)], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", launch)
    assert execute(store, settings, job)
    pid = int(marker.read_text())
    deadline = time.monotonic() + 3
    while psutil.pid_exists(pid) and psutil.Process(pid).status() != psutil.STATUS_ZOMBIE and time.monotonic() < deadline:
        time.sleep(0.01)
    assert not psutil.pid_exists(pid) or psutil.Process(pid).status() == psutil.STATUS_ZOMBIE
    assert store.one(jobs, id=job["id"])["error"] == "worker_process_failed"

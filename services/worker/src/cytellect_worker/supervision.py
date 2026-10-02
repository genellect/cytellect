"""Bounded child execution with durable lease fencing and sanitized diagnostics."""

import subprocess
import sys
import time
from dataclasses import asdict

import psutil
from cytellect_api.db import attempts, jobs
from cytellect_api.storage import read_json, write_json
from sqlalchemy import update


def terminate_tree(pid):
    try:
        parent = psutil.Process(pid)
        processes = list(reversed(parent.children(recursive=True))) + [parent]
    except psutil.NoSuchProcess:
        return
    for process in processes:
        try:
            process.terminate()
        except psutil.NoSuchProcess:
            pass
    _, alive = psutil.wait_procs(processes, timeout=2)
    for process in alive:
        try:
            process.kill()
        except psutil.NoSuchProcess:
            pass
    psutil.wait_procs(alive, timeout=2)


def execute(store, settings, job):
    # Every attempt owns a distinct directory; a stale attempt cannot delete a successor.
    attempt = store.safe_path("runs", job["lease"])
    with store.transaction() as conn:
        conn.execute(
            attempts.insert().values(
                id=job["lease"], workspace_id=job["workspace_id"], job_id=job["id"], created=time.time()
            )
        )
    attempt.mkdir(parents=True, exist_ok=False)
    configuration = asdict(settings)
    configuration["data_dir"] = str(settings.data_dir)
    descriptor = attempt / "request.json"
    write_json(descriptor, {"settings": configuration, "job": job})
    process = subprocess.Popen(
        [sys.executable, "-m", "cytellect_worker.child", str(descriptor), str(psutil.Process().pid)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0,
        start_new_session=sys.platform != "win32",
    )
    started = time.monotonic()
    error = None
    heartbeat = 0.0
    try:
        while process.poll() is None:
            now = time.monotonic()
            if now - heartbeat >= 1:
                if not store.heartbeat(job):
                    error = "job_cancelled_or_lease_lost"
                    break
                heartbeat = now
            if now - started > settings.job_timeout_seconds:
                error = "job_time_limit"
                break
            try:
                p = psutil.Process(process.pid)
                used = sum(q.memory_info().rss for q in [p, *p.children(recursive=True)] if q.is_running())
                if used > settings.worker_memory_mb * 1024**2:
                    error = "job_memory_limit"
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
            time.sleep(0.1)
        if error:
            terminate_tree(process.pid)
            process.wait(timeout=10)
        status_path = attempt / "status.json"
        status = read_json(status_path) if status_path.exists() else {"error": "worker_process_failed"}
        error = error or status.get("error")
        output = attempt / "output"
        if not error and (process.returncode != 0 or not output.is_dir()):
            error = "worker_process_failed"
        relative = output.relative_to(store.root).as_posix() if not error else None
        committed = store.finish(job, relative, error)
        return committed
    finally:
        if process.poll() is None:
            terminate_tree(process.pid)
            process.wait(timeout=10)
        # A cancellation becomes safe for deletion only after the process tree stopped.
        with store.transaction() as conn:
            conn.execute(
                update(jobs).where(jobs.c.id == job["id"], jobs.c.lease == job["lease"]).values(lease_until=0)
            )
        descriptor.unlink(missing_ok=True)

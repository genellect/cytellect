"""Bounded child execution with durable lease fencing and sanitized diagnostics."""

import os
import signal
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


def _stop_attempt_processes(process, observed):
    # Linux children (including Fiji) inherit the dedicated session/process group.
    # This also reaches descendants if the direct Python child exited first.
    if sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGTERM)
        except ProcessLookupError:
            pass
    for child in reversed(list(observed.values())):
        if child.is_running():
            terminate_tree(child.pid)
    if process.poll() is None:
        terminate_tree(process.pid)
    process.wait(timeout=10)
    if sys.platform != "win32":
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    for child in observed.values():
        try:
            if child.is_running() and child.status() != psutil.STATUS_ZOMBIE:
                return False
        except psutil.NoSuchProcess:
            pass
    return True


def execute(store, settings, job):
    # Every attempt owns a distinct directory; a stale attempt cannot delete a successor.
    attempt = store.safe_path("runs", job["lease"])
    descriptor = attempt / "request.json"
    process = None
    observed = {}
    error = None
    relative = None
    committed = False
    stopped = True
    try:
        with store.transaction() as conn:
            conn.execute(attempts.insert().values(
                id=job["lease"], workspace_id=job["workspace_id"], job_id=job["id"], created=time.time()
            ))
        attempt.mkdir(parents=True, exist_ok=False)
        configuration = asdict(settings)
        configuration["data_dir"] = str(settings.data_dir)
        write_json(descriptor, {"settings": configuration, "job": job})
        process = subprocess.Popen(
            [sys.executable, "-m", "cytellect_worker.child", str(descriptor), str(psutil.Process().pid)],
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if sys.platform == "win32" else 0,
            start_new_session=sys.platform != "win32",
        )
        started = time.monotonic()
        heartbeat = 0.0
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
                parent = psutil.Process(process.pid)
                children = parent.children(recursive=True)
                observed.update({child.pid: child for child in children})
                used = sum(child.memory_info().rss for child in [parent, *children] if child.is_running())
                if used > settings.worker_memory_mb * 1024**2:
                    error = "job_memory_limit"
                    break
            except psutil.NoSuchProcess:
                pass  # Child exited between poll and inspection; validate status below.
            except psutil.AccessDenied:
                error = "job_resource_monitor_failed"
                break
            time.sleep(0.1)
        if not error:
            status_path = attempt / "status.json"
            status = read_json(status_path) if status_path.exists() else {"error": "worker_process_failed"}
            if not isinstance(status, dict) or "error" not in status:
                raise ValueError("invalid_internal_status")
            from .child import ERROR_CODES
            from .errors import SAFE_ERRORS
            child_error = status["error"]
            error = (child_error if isinstance(child_error, str) and child_error in ERROR_CODES | SAFE_ERRORS
                     else "worker_process_failed") if child_error is not None else None
            output = attempt / "output"
            if not error and (process.returncode != 0 or not output.is_dir()):
                error = "worker_process_failed"
            if not error:
                relative = store.relative_path(output)
    except Exception:
        # DB/OS messages may contain private paths or submitted metadata.
        error = "worker_process_start_failed" if process is None else "worker_supervision_failed"
    finally:
        try:
            if process is not None:
                if process.poll() is None and error is None:
                    error = "job_cancelled_or_lease_lost"
                stopped = _stop_attempt_processes(process, observed)
        except Exception:
            stopped = False
            error = "worker_process_stop_failed"
        try:
            if stopped:
                committed = store.finish(job, relative if error is None else None,
                                         error or ("worker_process_start_failed" if process is None else None))
        except Exception:
            # Keep the failed/unknown attempt unpublished. DB lease recovery retries
            # it later; a database outage must not leave the child computing.
            committed = False
        finally:
            try:
                descriptor.unlink(missing_ok=True)
            except OSError:
                pass  # Still private; workspace expiry cleanup removes the attempt.
            if stopped:
                try:
                    with store.transaction() as conn:
                        conn.execute(update(jobs).where(
                            jobs.c.id == job["id"], jobs.c.lease == job["lease"]
                        ).values(lease_until=0))
                except Exception:
                    pass  # Existing finite lease expires; never extend on error.
    return committed

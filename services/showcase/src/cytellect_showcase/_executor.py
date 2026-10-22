"""In-process job execution with the worker's leases, handlers and publication.

Production runs each claimed job in a supervised child process
(``cytellect_worker.supervision.execute``). The browser has neither processes
nor threads, so the same allowlisted handlers run here, writing to the same
attempt directory (``runs/<lease>/output``). Publication still goes through
``Store.finish``, the lease-fenced commit used by the worker.
"""

from __future__ import annotations

import time

from cytellect_api.db import attempts, jobs
from sqlalchemy import update

MAX_STEPS = 500


def _handlers(store, settings, job, output):
    from cytellect_worker.figure_render import run_figure_render, run_publication_package
    from cytellect_worker.main import run_analysis, run_export, run_statistics, run_table_statistics

    # Same allowlist as cytellect_worker.child.main.
    return {
        "figure-render": lambda: run_figure_render(store, job, output),
        "publication-package": lambda: run_publication_package(store, job, output),
        "analysis": lambda: run_analysis(store, settings, job, output),
        "statistics": lambda: run_statistics(store, job, output),
        "export": lambda: run_export(store, job, output),
        "table-statistics": lambda: run_table_statistics(store, job, output),
    }


def _allowed_codes() -> frozenset[str]:
    from cytellect_worker.child import ERROR_CODES
    from cytellect_worker.errors import SAFE_ERRORS

    return frozenset(ERROR_CODES | SAFE_ERRORS)


def run_job(store, settings, job) -> bool:
    """Execute one claimed job and publish it exactly as the supervisor would."""
    attempt = store.safe_path("runs", job["lease"])
    error = None
    relative = None
    try:
        with store.transaction() as conn:
            conn.execute(attempts.insert().values(
                id=job["lease"], workspace_id=job["workspace_id"], job_id=job["id"], created=time.time()))
            # No concurrent heartbeat is possible while the handler computes, so
            # the lease covers the configured job limit instead of 60 seconds.
            conn.execute(update(jobs).where(
                jobs.c.id == job["id"], jobs.c.lease == job["lease"], jobs.c.state == "running",
            ).values(lease_until=time.time() + settings.job_timeout_seconds))
        attempt.mkdir(parents=True, exist_ok=False)
        output = attempt / "output"
        try:
            handlers = _handlers(store, settings, job, output)
            if job["kind"] not in handlers:
                raise ValueError("job_kind_not_allowlisted")
            handlers[job["kind"]]()
        except Exception as exc:
            # Unknown messages may contain file names or metadata: never persist them.
            message = str(exc)
            error = message if message in _allowed_codes() else "analysis_failed"
        if error is None and not output.is_dir():
            error = "worker_process_failed"
        if error is None:
            relative = store.relative_path(output)
    except Exception:
        error = "worker_supervision_failed"
    committed = False
    try:
        committed = store.finish(job, relative if error is None else None, error)
    except Exception:
        committed = False
    finally:
        try:
            with store.transaction() as conn:
                conn.execute(update(jobs).where(
                    jobs.c.id == job["id"], jobs.c.lease == job["lease"]).values(lease_until=0))
        except Exception:
            pass
    return committed


def drain(store, settings) -> int:
    """Advance workspace runs and execute queued jobs until nothing is left.

    Mirrors the worker loop (cleanup, ``process_one``) without sleeping.
    Returns the number of executed jobs.
    """
    from cytellect_api.workspace_runs import advance_workspace_runs
    from cytellect_worker.main import cleanup

    executed = 0
    cleanup(store)
    for _ in range(MAX_STEPS):
        advanced = advance_workspace_runs(store, settings)
        job = store.claim()
        if job is None:
            if advanced:
                continue
            return executed
        run_job(store, settings, job)
        executed += 1
        advance_workspace_runs(store, settings)
    return executed

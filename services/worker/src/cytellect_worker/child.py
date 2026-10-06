"""Internal entry point; never accepts user-submitted code or shell commands."""

import os
import sys
import threading
import time
from pathlib import Path

import psutil
from cytellect_api.config import Settings
from cytellect_api.db import Store, jobs, workspaces
from cytellect_api.storage import read_json, write_json

from .errors import SAFE_ERRORS
from .main import run_analysis, run_export, run_statistics, run_table_statistics
from .supervision import terminate_tree

# Unknown exception messages may contain filenames/conditions: never persist them.
ERROR_CODES = {
    # Generic child failure: reported as such rather than as a supervision failure.
    "analysis_failed",
    "fiji_not_configured",
    "fiji_adapter_not_installed",
    "raw_export_not_implemented",
    "revision_not_found",
    "background_missing",
    "parent_revision_unavailable",
    "job_kind_not_allowlisted",
    "review_required",
    "independent_units_must_be_confirmed",
    "no_measurements",
    "no_valid_selected_measurements",
    "comparison_group_missing",
    "two_independent_units_per_group_required",
    "unique_complete_pairs_required",
    "incomplete_pairs",
    "two_pairs_required",
    "comparison_not_estimable",
    "confounded_or_rank_deficient_model",
    "at_least_three_fields_for_cluster_model",
}


def lease_is_live(store, job, parent, parent_started):
    """Any inability to establish the lease/owner state fails closed."""
    try:
        current = store.one(jobs, id=job["id"])
        workspace = store.one(workspaces, id=job["workspace_id"])
        return bool(
            parent.is_running() and parent.create_time() == parent_started
            and current and current["state"] == "running"
            and current["lease"] == job["lease"] and current["lease_until"] > time.time()
            and workspace and not workspace["deleted"] and workspace["expires"] > time.time()
        )
    except Exception:
        # Never let an unhandled DB/psutil error silently kill just this thread.
        return False


def main():
    descriptor = Path(sys.argv[1])
    data = read_json(descriptor)
    data["settings"]["data_dir"] = Path(data["settings"]["data_dir"])
    settings = Settings(**data["settings"])
    store = Store(settings.data_dir)
    job = data["job"]
    parent = psutil.Process(int(sys.argv[2]))
    parent_started = parent.create_time()
    stopped = threading.Event()

    def watchdog():
        while not stopped.wait(0.5):
            if not lease_is_live(store, job, parent, parent_started):
                try:
                    for child in psutil.Process().children():
                        terminate_tree(child.pid)
                finally:
                    os._exit(2)

    threading.Thread(target=watchdog, daemon=True).start()
    output = descriptor.parent / "output"
    try:
        handlers = {
            "analysis": lambda: run_analysis(store, settings, job, output),
            "statistics": lambda: run_statistics(store, job, output),
            "export": lambda: run_export(store, job, output),
            "table-statistics": lambda: run_table_statistics(store, job, output),
        }
        if job["kind"] not in handlers:
            raise ValueError("job_kind_not_allowlisted")
        handlers[job["kind"]]()
        write_json(descriptor.parent / "status.json", {"error": None})
    except Exception as exc:
        message = str(exc)
        write_json(
            descriptor.parent / "status.json",
            {"error": message if message in ERROR_CODES | SAFE_ERRORS else "analysis_failed"},
        )
    finally:
        stopped.set()


if __name__ == "__main__":
    main()

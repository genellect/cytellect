"""Local launcher-owned worker; stops descendants if its launcher disappears."""
import os
import sys
import threading

import psutil

from .config import Settings, configure_private_tmp
from .db import Store
from .process_owner import process_alive, redirector_owner


def parent_alive(pid: int, created: float) -> bool:
    return process_alive((pid, created))


def main():
    parent_pid, parent_created = int(sys.argv[1]), float(sys.argv[2])
    redirector = redirector_owner()
    if not parent_alive(parent_pid, parent_created):
        raise SystemExit(2)
    settings = Settings.from_env()
    configure_private_tmp(settings)
    store = Store(settings.data_dir)
    from cytellect_worker.main import cleanup, process_one
    from cytellect_worker.supervision import terminate_tree

    stopped = threading.Event()

    # A private one-line pipe handshake lets the supervisor terminate this
    # actual interpreter even when Popen owns only a Windows redirector shim.
    current = psutil.Process()
    print(f"{current.pid} {current.create_time()}", flush=True)

    def watch():
        while not stopped.wait(0.5):
            if (not parent_alive(parent_pid, parent_created)
                    or (redirector is not None and not process_alive(redirector))):
                try:
                    for child in psutil.Process().children():
                        terminate_tree(child.pid)
                finally:
                    os._exit(2)

    def collect():
        while not stopped.is_set():
            try:
                cleanup(store)
            except Exception:
                # DB failures are retried without logging research paths.
                pass
            stopped.wait(30)

    threading.Thread(target=watch, daemon=True).start()
    threading.Thread(target=collect, daemon=True).start()
    try:
        while not stopped.is_set():
            if not process_one(store, settings):
                stopped.wait(1)
    finally:
        stopped.set()


if __name__ == "__main__":
    main()

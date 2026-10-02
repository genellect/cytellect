"""Local launcher-owned worker; stops descendants if its launcher disappears."""
import os
import sys
import threading

import psutil

from .config import Settings, configure_private_tmp
from .db import Store


def parent_alive(pid: int, created: float) -> bool:
    try:
        parent = psutil.Process(pid)
        return parent.is_running() and parent.create_time() == created and parent.status() != psutil.STATUS_ZOMBIE
    except psutil.Error:
        return False


def main():
    parent_pid, parent_created = int(sys.argv[1]), float(sys.argv[2])
    settings = Settings.from_env()
    configure_private_tmp(settings)
    store = Store(settings.data_dir)
    from cytellect_worker.main import cleanup, process_one
    from cytellect_worker.supervision import terminate_tree

    stopped = threading.Event()

    def watch():
        while not stopped.wait(0.5):
            if not parent_alive(parent_pid, parent_created):
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

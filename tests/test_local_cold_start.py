"""Real delayed imports must not obscure process ownership or orphan a worker."""
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil
from cytellect_api.config import Settings
from cytellect_api.local import WorkerSupervisor
from cytellect_api.process_owner import process_alive


def delayed_import_script(tmp_path: Path, delay: int = 60) -> tuple[Path, Path]:
    marker = tmp_path / "import-entered"
    script = tmp_path / "delayed-science.py"
    script.write_text(
        "import runpy,sys,time\nfrom pathlib import Path\n"
        "class DelayScience:\n"
        " def find_spec(self,fullname,path=None,target=None):\n"
        "  if fullname=='cytellect_worker.main':\n"
        f"   Path({str(marker)!r}).write_text('entered',encoding='ascii')\n"
        f"   time.sleep({delay})\n"
        "  return None\n"
        "sys.meta_path.insert(0,DelayScience())\n"
        "runpy.run_module('cytellect_api.local_worker',run_name='__main__')\n", encoding="utf-8")
    return script, marker


def await_file(path, timeout=10):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(.05)
    raise AssertionError("worker did not reach delayed scientific import")


def read_identity(process):
    ready = threading.Event()
    lines = []

    def read():
        lines.append(process.stdout.readline().decode().split())
        ready.set()

    threading.Thread(target=read, daemon=True).start()
    assert ready.wait(10), "identity waited for the delayed scientific import"
    assert len(lines[0]) == 2
    return lines[0]


def test_identity_is_ready_before_scientific_import_exceeds_handshake_deadline(tmp_path, monkeypatch):
    script, marker = delayed_import_script(tmp_path)
    real_popen = subprocess.Popen

    def with_delay(args, **kwargs):
        return real_popen([args[0], str(script), *args[-2:]], **kwargs)

    monkeypatch.setattr(subprocess, "Popen", with_delay)
    stopped = threading.Event()
    supervisor = WorkerSupervisor(Settings(tmp_path / "private"), stopped.set)
    try:
        supervisor.start()
        identity = supervisor.worker_identity
        assert identity is not None and process_alive(identity)
        await_file(marker)
        # Longer than the actual supervisor15s deadline, without shortening or
        # mocking that timer. The same interpreter remains alive and adopted.
        assert not stopped.wait(15.25)
        assert supervisor.worker_identity == identity and process_alive(identity)
        assert supervisor.failure is None
    finally:
        supervisor.stop()


def test_parent_exit_during_scientific_import_stops_worker(tmp_path):
    script, marker = delayed_import_script(tmp_path)
    parent = subprocess.Popen([sys.executable, "-c",
        "import os,psutil,time; print(f'{os.getpid()} {psutil.Process().create_time()}',flush=True); time.sleep(60)"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    worker = None
    observed = []
    try:
        assert parent.stdout is not None
        parent_pid, parent_created = read_identity(parent)
        parent_identity = (int(parent_pid), float(parent_created))
        env = {**os.environ, "CYTELLECT_DATA_DIR": str(tmp_path / "private")}
        worker = subprocess.Popen([sys.executable, str(script), parent_pid, parent_created], env=env,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
        assert worker.stdout is not None
        identity = read_identity(worker)
        actual = (int(identity[0]), float(identity[1]))
        await_file(marker)
        observed = psutil.Process(worker.pid).children(recursive=True)
        # Terminate the actual owner, even on Windows where Popen may be a shim.
        assert process_alive(parent_identity)
        psutil.Process(parent_identity[0]).kill()
        parent.wait(timeout=5)
        worker.wait(timeout=5)
        assert not process_alive(actual)
        _, alive = psutil.wait_procs(observed, timeout=3)
        assert not [p for p in alive if p.is_running() and p.status() != psutil.STATUS_ZOMBIE]
    finally:
        for process in observed:
            try:
                process.kill()
            except psutil.NoSuchProcess:
                pass
        for process in (worker, parent):
            if process is not None:
                if process.poll() is None:
                    try:
                        for child in reversed(psutil.Process(process.pid).children(recursive=True)):
                            child.kill()
                    except psutil.NoSuchProcess:
                        pass
                    process.kill()
                process.wait(timeout=5)
                if process.stdout:
                    process.stdout.close()

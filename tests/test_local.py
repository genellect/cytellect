"""Local bootstrap threat boundaries and real launcher/worker lifecycle."""
import errno
import io
import os
import socket
import subprocess
import sys
import threading
import time
import venv
from dataclasses import replace
from pathlib import Path
from types import ModuleType, SimpleNamespace

import httpx
import psutil
import pytest
from cytellect_api import local as local_module
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import sessions
from cytellect_api.local import WorkerSupervisor, bind_loopback, create_local_app, runtime_lock
from cytellect_api.local_worker import parent_alive
from fastapi.testclient import TestClient

ORIGIN = "http://127.0.0.1:8765"
HEADERS = {"Origin": ORIGIN, "X-Cytellect-Request": "1", "Sec-Fetch-Site": "same-origin"}


def local(tmp_path):
    web = tmp_path / "web"
    web.mkdir(exist_ok=True)
    (web / "index.html").write_text("<h1>public static shell</h1>", encoding="utf-8")
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False)
    app = create_local_app(settings, web, 8765)
    client = TestClient(app, base_url=ORIGIN, client=("127.0.0.1", 45000))
    return client, app, settings, web


def test_local_bootstrap_cookie_only_and_owner_survives_relaunch(tmp_path):
    client, app, settings, web = local(tmp_path)
    before = client.get("/v1/local/setup")
    assert before.json() == {"mode": "local", "ready": True, "fiji_configured": False, "retention_hours": 24}
    assert not app.state.store.rows(sessions)  # GET cannot authenticate.
    assert client.get("/v1/workspaces").status_code == 401
    response = client.post("/v1/local/session", headers=HEADERS)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=strict" in cookie and "Secure" not in cookie
    token = client.cookies.get(settings.cookie_name)
    assert token not in response.text and token not in (settings.data_dir / "local-owner").read_text()
    assert app.state.store.rows(sessions)[0]["digest"] != token
    created = client.post("/v1/workspaces", json={"title": "synthetic local"}, headers=HEADERS).json()
    assert client.post("/v1/local/session", headers=HEADERS).status_code == 200
    assert len(app.state.store.rows(sessions)) == 1  # Repeated readiness does not mint sessions.
    fresh = TestClient(create_local_app(settings, web, 8765), base_url=ORIGIN, client=("127.0.0.1", 45001))
    fresh.post("/v1/local/session", headers=HEADERS)
    assert fresh.get("/v1/workspaces").json()[0]["id"] == created["id"]
    assert client.get("/").headers["cross-origin-opener-policy"] == "same-origin"
    assert "frame-ancestors 'none'" in client.get("/").headers["content-security-policy"]
    assert "connect-src 'self'" in client.get("/").headers["content-security-policy"]
    assert "form-action 'self'" in client.get("/").headers["content-security-policy"]


@pytest.mark.parametrize("headers", [
    {}, {"Origin": ORIGIN}, {"X-Cytellect-Request": "1"},
    {**HEADERS, "Origin": "https://attacker.example"},
    {**HEADERS, "Origin": "null"}, {**HEADERS, "Sec-Fetch-Site": "cross-site"},
    {**HEADERS, "Sec-Fetch-Site": "same-site"}, {**HEADERS, "Sec-Fetch-Site": "none"},
    {**HEADERS, "Host": "attacker.example:8765"}, {**HEADERS, "Host": "localhost:8765"},
    {**HEADERS, "Host": "127.0.0.1:8766"}, {**HEADERS, "X-Forwarded-Host": "127.0.0.1:8765"},
])
def test_local_bootstrap_rejects_cross_origin_dns_rebinding_and_forms(tmp_path, headers):
    client, app, _, _ = local(tmp_path)
    assert client.post("/v1/local/session", headers=headers).status_code == 403
    assert not app.state.store.rows(sessions)
    assert not client.cookies


def test_local_cannot_be_used_through_remote_peer_or_cross_site_download(tmp_path):
    client, app, _, _ = local(tmp_path)
    remote = TestClient(app, base_url=ORIGIN, client=("192.0.2.1", 1000))
    assert remote.get("/v1/local/setup").status_code == 403
    assert client.options("/v1/local/session", headers={"Origin": "https://attacker.example",
        "Access-Control-Request-Method": "POST"}).status_code == 403
    assert client.get("/", headers={"Sec-Fetch-Site": "cross-site"}).status_code == 403


def test_cloud_app_has_no_local_auth_route_and_local_config_fails_closed(tmp_path):
    _, _, settings, web = local(tmp_path)
    cloud = TestClient(create_app(settings), base_url=ORIGIN)
    assert cloud.post("/v1/local/session", headers=HEADERS).status_code == 404
    with pytest.raises(ValueError, match="local_settings_invalid"):
        create_local_app(replace(settings, app_origin="http://0.0.0.0:8765"), web, 8765)
    with pytest.raises(ValueError, match="local_settings_invalid"):
        create_local_app(replace(settings, secure_cookies=True), web, 8765)


def test_runtime_lock_and_port_are_exclusive_and_release(tmp_path):
    with runtime_lock(tmp_path):
        with pytest.raises(ValueError, match="local_runtime_already_in_use"):
            with runtime_lock(tmp_path):
                pytest.fail("double launcher admitted")
    with runtime_lock(tmp_path):
        pass
    with bind_loopback(0) as sock:
        port = sock.getsockname()[1]
        assert sock.getsockname()[0] == "127.0.0.1"
        with pytest.raises(OSError):
            bind_loopback(port)
    assert parent_alive(os.getpid(), psutil.Process().create_time())
    assert not parent_alive(os.getpid(), psutil.Process().create_time() - 1)


def test_runtime_lock_does_not_relabel_failures_inside_owned_runtime(tmp_path):
    failure = OSError(errno.EADDRINUSE, "synthetic private port detail")
    with pytest.raises(OSError) as caught:
        with runtime_lock(tmp_path):
            raise failure
    assert caught.value is failure
    with runtime_lock(tmp_path):
        pass  # The owned lock is still released after a protected-body failure.


@pytest.mark.parametrize("dont_write,inherited,expected", [
    (False, None, None), (False, "0", "0"), (True, None, "1"), (True, "0", "1"),
])
def test_worker_bytecode_policy_is_only_overridden_for_no_bytecode_parent(
    tmp_path, monkeypatch, dont_write, inherited, expected,
):
    monkeypatch.setattr(sys, "dont_write_bytecode", dont_write)
    if inherited is None:
        monkeypatch.delenv("PYTHONDONTWRITEBYTECODE", raising=False)
    else:
        monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", inherited)
    launched = []

    def fake_process(pid=None):
        return SimpleNamespace(pid=123 if pid is None else pid, create_time=lambda: 4.0, parents=lambda: [])

    def fake_popen(args, **kwargs):
        launched.append((args, kwargs))
        return SimpleNamespace(pid=456, stdout=io.BytesIO(b"456 4.0\n"))

    monkeypatch.setattr(local_module.psutil, "Process", fake_process)
    monkeypatch.setattr(local_module.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(local_module, "process_alive", lambda identity: identity == (456, 4.0))
    supervisor = WorkerSupervisor(Settings(tmp_path / "private"), lambda: None)
    supervisor._spawn()  # Real supervisor handshake, synthetic pipe, no child is launched.
    assert supervisor.worker_identity == (456, 4.0)
    assert len(launched) == 1
    args, options = launched[0]
    assert args == [sys.executable, "-m", "cytellect_api.local_worker", "123", "4.0"]
    assert options["env"].get("PYTHONDONTWRITEBYTECODE") == expected
    assert os.environ.get("PYTHONDONTWRITEBYTECODE") == inherited


@pytest.mark.parametrize("automatic", [False, True])
def test_gui_browser_is_disabled_until_ready_and_again_during_stop(monkeypatch, automatic):
    """Exercise the actual GUI callbacks without a native window, server or port."""
    server = SimpleNamespace(started=False, should_exit=False)
    buttons = {}
    calls: list[str] = []
    statuses = []
    scheduled = []
    state = {"alive": False, "destroyed": False, "joined": False}

    class Widget:
        def __init__(self, *_args, **kwargs):
            self.options = kwargs
            if "command" in kwargs:
                buttons[kwargs["text"]] = self

        def pack(self, **_kwargs):
            pass

        def configure(self, **kwargs):
            self.options.update(kwargs)

    class Status:
        def __init__(self, value):
            statuses.append(value)

        def set(self, value):
            statuses.append(value)

    class Window:
        def title(self, _value): pass
        def geometry(self, _value): pass
        def resizable(self, *_values): pass
        def option_add(self, *_values): pass
        def protocol(self, *_values): pass
        def after(self, _delay, callback): scheduled.append(callback)
        def destroy(self): state["destroyed"] = True

        def mainloop(self):
            button = buttons["ブラウザで開く"]
            assert button.options["state"] == "disabled"
            button.options["command"]()
            assert not calls
            scheduled.pop(0)()
            assert button.options["state"] == "disabled"
            server.started = True
            scheduled.pop(0)()
            assert button.options["state"] == "normal"
            assert statuses[-1] == "稼働中 · " + ORIGIN
            assert calls == ([ORIGIN] if automatic else [])
            scheduled.pop(0)()
            assert calls == ([ORIGIN] if automatic else [])  # No repeated auto-open.
            button.options["command"]()
            assert calls == [ORIGIN] * (2 if automatic else 1)
            buttons["停止して閉じる"].options["command"]()
            assert server.should_exit and statuses[-1] == "停止中…"
            assert button.options["state"] == "disabled"
            button.options["command"]()
            assert calls == [ORIGIN] * (2 if automatic else 1)
            scheduled.pop(0)()
            assert button.options["state"] == "disabled"
            state["alive"] = False
            scheduled.pop(0)()
            assert state["destroyed"]

    class Thread:
        def __init__(self, **_kwargs): pass
        def start(self): state["alive"] = True
        def is_alive(self): return state["alive"]
        def join(self): state["joined"] = True

    tk = ModuleType("tkinter")
    monkeypatch.setattr(tk, "Tk", Window, raising=False)
    monkeypatch.setattr(tk, "StringVar", Status, raising=False)
    monkeypatch.setattr(tk, "ttk", SimpleNamespace(Frame=Widget, Label=Widget, Button=Widget), raising=False)
    monkeypatch.setitem(sys.modules, "tkinter", tk)
    monkeypatch.setattr(local_module.threading, "Thread", Thread)
    monkeypatch.setattr(local_module.webbrowser, "open", calls.append)
    local_module._gui(server, ORIGIN, lambda: pytest.fail("test must not start a server"), automatic)
    assert server.should_exit and state["joined"]


@pytest.mark.parametrize("failure,expected", [
    (ValueError("local_runtime_already_in_use"), "Cytellectは既に起動しています"),
    (OSError(errno.EADDRINUSE, "private synthetic path"), "接続先が使用中"),
    (PermissionError(errno.EACCES, "private synthetic path"), "開き直しても続く場合"),
    (RuntimeError("private synthetic path"), "開き直しても続く場合"),
])
def test_gui_failures_use_fixed_japanese_categories_without_exception_details(tmp_path, monkeypatch, failure, expected):
    messages = []

    def fail(*_args, **_kwargs):
        raise failure

    monkeypatch.setattr(local_module, "run_local", fail)
    monkeypatch.setattr(local_module, "installed_source_revision", lambda: None)
    monkeypatch.setattr(local_module, "_report_startup_error", lambda text, gui: messages.append((text, gui)))
    arguments = ["--data-dir", str(tmp_path / "data"), "--web-dir", str(tmp_path / "web"),
                 "--fiji", str(tmp_path)]
    with pytest.raises(SystemExit) as stopped:
        local_module.main([*arguments, "--gui"])
    assert stopped.value.code == 1
    assert len(messages) == 1 and messages[0][1] is True and expected in messages[0][0]
    assert "private" not in messages[0][0] and str(tmp_path) not in messages[0][0]
    with pytest.raises(SystemExit) as stopped:
        local_module.main(arguments)
    assert stopped.value.code == 1
    assert messages[-1] == (
        "Cytellect could not start or stopped. Check the local port, installation and runtime directory.", False,
    )


def test_gui_invalid_installation_uses_fixed_japanese_message(tmp_path, monkeypatch):
    messages = []
    monkeypatch.setattr(local_module, "_report_startup_error", lambda text, gui: messages.append((text, gui)))
    with pytest.raises(SystemExit) as stopped:
        local_module.main(["--gui", "--fiji", str(tmp_path / "missing")])
    assert stopped.value.code == 2
    assert messages == [("Cytellectの準備が完了していません。セットアップを再実行してください。", True)]


def test_gui_recognizes_windows_port_error_code_without_reading_its_message():
    failure = OSError("synthetic private connection detail")
    setattr(failure, "winerror", 10048)
    message = local_module._gui_failure_message(failure)
    assert message.startswith("接続先が使用中") and "private" not in message


def windows_redirector(tmp_path):
    """Unlike uv hardlinks, a stdlib Windows venv really redirects to base Python."""
    root = tmp_path / "redirector"
    venv.EnvBuilder(with_pip=False).create(root)
    # No installation/download: use the running test's already-locked packages.
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(str(Path(p).resolve()) for p in sys.path if p)
    return root / "Scripts" / "python.exe", env


@pytest.mark.parametrize("use_redirector", [False, pytest.param(True, marks=pytest.mark.skipif(
    sys.platform != "win32", reason="Windows executable redirector process chain"))])
def test_launcher_terminated_abruptly_does_not_leave_worker(tmp_path, use_redirector):
    # This is a lifecycle test without image processing; a directory stand-in is
    # sufficient. Actual pinned Fiji execution has separate integration tests.
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("local shell", encoding="utf-8")
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    executable, env = windows_redirector(tmp_path) if use_redirector else (sys.executable, os.environ.copy())
    process = subprocess.Popen([str(executable), "-m", "cytellect_api.local", "--data-dir",
        str(tmp_path / "runtime"), "--web-dir", str(web), "--fiji", str(tmp_path),
        "--port", str(port), "--no-browser"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env)
    descendants = []
    try:
        limit = time.monotonic() + 30
        with httpx.Client(trust_env=False) as browser:
            while time.monotonic() < limit:
                assert process.poll() is None, "launcher exited before readiness"
                try:
                    if browser.get(f"http://127.0.0.1:{port}/v1/local/setup", timeout=1).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                time.sleep(0.1)
            else:
                pytest.fail("local launcher never became ready")
        descendants = psutil.Process(process.pid).children(recursive=True)
        assert descendants, "independent worker missing"
        if use_redirector:
            # Prove this case exercises the failing process topology, rather
            # than accepting another uv direct/hardlinked interpreter run.
            assert any(not os.path.samefile(child.exe(), executable)
                       and child.name().lower() in {"python.exe", "pythonw.exe"} for child in descendants)
        process.terminate()
        process.wait(timeout=10)
        _, alive = psutil.wait_procs(descendants, timeout=10)
        assert not [p for p in alive if p.is_running() and p.status() != psutil.STATUS_ZOMBIE]
    finally:
        for child in descendants:
            try:
                child.kill()
            except psutil.NoSuchProcess:
                pass
        if process.poll() is None:
            process.kill()
        process.wait(timeout=10)


@pytest.mark.parametrize("use_redirector", [False, pytest.param(True, marks=pytest.mark.skipif(
    sys.platform != "win32", reason="Windows executable redirector process chain"))])
def test_worker_crash_recovery_is_bounded_and_closes_server(tmp_path, use_redirector, monkeypatch):
    if use_redirector:
        executable, env = windows_redirector(tmp_path)
        monkeypatch.setattr(sys, "executable", str(executable))
        monkeypatch.setenv("PYTHONPATH", env["PYTHONPATH"])
    settings = Settings(tmp_path / "worker-private", app_origin=ORIGIN, secure_cookies=False)
    stopped = threading.Event()
    supervisor = WorkerSupervisor(settings, stopped.set)
    supervisor.start()
    try:
        for failure in range(3):
            current = supervisor.process
            assert current is not None
            actual = supervisor.worker_identity
            assert actual is not None
            if use_redirector:
                assert actual[0] != current.pid
            current.kill()
            current.wait(timeout=10)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and supervisor.process is current and not stopped.is_set():
                time.sleep(0.05)
            if failure < 2:
                assert supervisor.process is not current and not stopped.is_set()
            else:
                assert stopped.is_set() and supervisor.failure == "local_worker_stopped"
            assert not parent_alive(*actual), "crashed worker shim left its actual interpreter alive"
    finally:
        supervisor.stop()


def test_stop_during_pending_worker_restart_reaps_unadopted_process(tmp_path, monkeypatch):
    """A real delayed child exercises Stop before the private PID handshake."""
    original_popen = subprocess.Popen
    launched: list[subprocess.Popen] = []
    restarting = threading.Event()

    def delayed_worker(_args, **kwargs):
        delay = 60 if launched else 0
        code = (f"import os,time,psutil; time.sleep({delay}); "
                "print(f'{os.getpid()} {psutil.Process().create_time()}',flush=True); time.sleep(60)")
        process = original_popen([sys.executable, "-c", code], **kwargs)
        launched.append(process)
        if len(launched) == 2:
            restarting.set()
        return process

    monkeypatch.setattr(subprocess, "Popen", delayed_worker)
    supervisor = WorkerSupervisor(Settings(tmp_path / "private"), lambda: None)
    try:
        supervisor.start()
        launched[0].kill()
        launched[0].wait(timeout=5)
        assert restarting.wait(5), "restart child never launched"
        supervisor.stop()
        assert supervisor.thread is not None and not supervisor.thread.is_alive()
        assert supervisor.failure is None  # User Stop is not an application failure.
        assert len(launched) == 2 and launched[1].poll() is not None
    finally:
        supervisor.stop()
        for process in launched:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)

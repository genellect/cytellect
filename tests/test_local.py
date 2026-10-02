"""Local bootstrap threat boundaries and real launcher/worker lifecycle."""
import os
import socket
import subprocess
import sys
import threading
import time
from dataclasses import replace

import httpx
import psutil
import pytest
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


def test_launcher_terminated_abruptly_does_not_leave_worker(tmp_path):
    # This is a lifecycle test without image processing; a directory stand-in is
    # sufficient. Actual pinned Fiji execution has separate integration tests.
    web = tmp_path / "web"
    web.mkdir()
    (web / "index.html").write_text("local shell", encoding="utf-8")
    with socket.socket() as free:
        free.bind(("127.0.0.1", 0))
        port = free.getsockname()[1]
    process = subprocess.Popen([sys.executable, "-m", "cytellect_api.local", "--data-dir",
        str(tmp_path / "runtime"), "--web-dir", str(web), "--fiji", str(tmp_path),
        "--port", str(port), "--no-browser"], stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
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


def test_worker_crash_recovery_is_bounded_and_closes_server(tmp_path):
    settings = Settings(tmp_path / "worker-private", app_origin=ORIGIN, secure_cookies=False)
    stopped = threading.Event()
    supervisor = WorkerSupervisor(settings, stopped.set)
    supervisor.start()
    try:
        for failure in range(3):
            current = supervisor.process
            assert current is not None
            current.kill()
            current.wait(timeout=10)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline and supervisor.process is current and not stopped.is_set():
                time.sleep(0.05)
            if failure < 2:
                assert supervisor.process is not current and not stopped.is_set()
            else:
                assert stopped.is_set() and supervisor.failure == "local_worker_stopped"
    finally:
        supervisor.stop()

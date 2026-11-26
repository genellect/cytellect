"""Explicit single-user loopback mode; the cloud API never mounts these routes."""
from __future__ import annotations

import argparse
import contextlib
import errno
import json
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
import uuid
import webbrowser
from pathlib import Path

import psutil
from fastapi import Depends, HTTPException, Request, Response
from fastapi.responses import FileResponse, JSONResponse
from sqlalchemy import update
from starlette.staticfiles import StaticFiles

from .config import Settings, configure_private_tmp
from .db import digest, recorded_retention_mode, sessions, workspaces
from .local_release import installed_source_revision as verify_source_revision
from .process_owner import Identity, process_alive, redirector_owner
from .views import LocalSetupView, PreviousStopView, SessionView


def installed_source_revision(root: Path | None = None) -> str | None:
    return verify_source_revision(root, execution_file=Path(__file__))


def _local_owner(root: Path) -> str:
    """An ownership identifier, never an authentication token. Runtime is OS-user private."""
    path = root / "local-owner"
    if path.is_symlink() or path.resolve().parent != root.resolve():
        raise ValueError("local_owner_path_invalid")
    try:
        with path.open("x", encoding="ascii") as stream:
            if os.name != "nt":
                path.chmod(0o600)
            stream.write(str(uuid.uuid4()))
    except FileExistsError:
        pass
    return str(uuid.UUID(path.read_text(encoding="ascii").strip()))


STOP_RECORD = "local-stop.json"
STOP_SCHEMA = "cytellect-local-stop/1"
# Why the launcher stopped (#284). The record holds only one of these codes and times: no research data.
NORMAL_STOPS = frozenset({"launcher_closed", "update_switch"})
ABNORMAL_STOPS = frozenset({"local_worker_stopped", "local_worker_start_failed", "parent_process_gone",
                            "server_stopped", "unhandled_exception"})
# A run that left no stop record: a forced kill, a power loss or an OS shutdown that ended the process.
UNRECORDED_STOP = "unrecorded"
# The workspace shows the same labels (STOP_LABELS in apps/web/src/lib/local-connection.ts; a test keeps them equal).
STOP_LABELS = {"local_worker_stopped": "計算処理の停止", "local_worker_start_failed": "計算処理の起動失敗",
               "parent_process_gone": "起動元のプロセスの終了", "server_stopped": "サービスの停止",
               "unhandled_exception": "予期しないエラー", "unrecorded": "理由の記録なし"}


def _write_stop_record(root: Path, value: dict) -> None:
    """Atomic replace; a failed write must never block a start or a stop."""
    path = root / STOP_RECORD
    temporary = root / f".{STOP_RECORD}.{uuid.uuid4().hex}"
    try:
        with temporary.open("x", encoding="ascii") as stream:
            if os.name != "nt":
                temporary.chmod(0o600)
            json.dump(value, stream)
        # Replacing the name never writes through a symbolic link planted there.
        os.replace(temporary, path)
    except OSError:
        with contextlib.suppress(OSError):
            temporary.unlink()


def read_previous_stop(root: Path) -> dict | None:
    """The last run's end: None when there is no record (first start) or it ended normally."""
    path = root / STOP_RECORD
    if not path.exists() and not path.is_symlink():
        return None
    try:
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 4096:
            raise ValueError("local_stop_record_invalid")
        value = json.loads(path.read_text(encoding="ascii"))
        if not isinstance(value, dict) or value.get("schema") != STOP_SCHEMA:
            raise ValueError("local_stop_record_invalid")
        if value.get("state") == "stopped" and value.get("reason") in NORMAL_STOPS:
            return None
        if value.get("state") == "stopped" and value.get("reason") in ABNORMAL_STOPS:
            stopped = value.get("time")
            return {"reason": value["reason"],
                    "time": float(stopped) if isinstance(stopped, (int, float)) and stopped > 0 else None}
    except (OSError, ValueError):
        pass
    # "running" without a stop (the process was killed) or a damaged record.
    return {"reason": UNRECORDED_STOP, "time": None}


def begin_stop_record(root: Path) -> dict | None:
    """Read the previous run's end, then mark this run as running until its stop is recorded."""
    previous = read_previous_stop(root)
    _write_stop_record(root, {"schema": STOP_SCHEMA, "state": "running", "started": int(time.time())})
    return previous


def record_stop(root: Path, reason: str) -> None:
    if reason not in NORMAL_STOPS | ABNORMAL_STOPS:
        reason = "unhandled_exception"
    _write_stop_record(root, {"schema": STOP_SCHEMA, "state": "stopped", "reason": reason, "time": int(time.time())})


def previous_stop_line(previous: dict | None) -> str | None:
    """One launcher line about an abnormal previous stop, in the PC's local time."""
    if not previous:
        return None
    line = "前回の停止：" + STOP_LABELS.get(previous["reason"], STOP_LABELS[UNRECORDED_STOP])
    if previous.get("time"):
        moment = time.localtime(previous["time"])
        line += f" · {moment.tm_mon}月{moment.tm_mday}日 {moment.tm_hour:02d}:{moment.tm_min:02d}"
    return line


class StopReason:
    """The first reason this launcher was asked to stop; later requests keep it."""

    def __init__(self):
        self.code: str | None = None
        self._lock = threading.Lock()

    def request(self, server, code: str) -> None:
        with self._lock:
            if self.code is None:
                self.code = code
        if server is not None:
            server.should_exit = True


def create_local_app(settings: Settings, web_dir: Path, port: int, *, store_version: str | None = None,
                     previous_stop: dict | None = None):
    origin = f"http://127.0.0.1:{port}"
    if settings.app_origin != origin or settings.secure_cookies or not 1 <= port <= 65535:
        raise ValueError("local_settings_invalid")
    web_dir = web_dir.resolve()
    if not (web_dir / "index.html").is_file():
        raise ValueError("local_static_build_missing")
    configure_private_tmp(settings)
    if os.name != "nt":
        settings.data_dir.chmod(0o700)
    owner = _local_owner(settings.data_dir)
    from .app import create_app
    from .cloud_account import CloudAccount, register_account_routes

    # Explicit proposal configuration (environment) keeps precedence; otherwise the
    # signed-in device's token reaches the same cloud service as GPU inference.
    account = CloudAccount(settings.data_dir,
                           remote_settings=lambda: local_cellpose_remote_environment(settings.data_dir))
    app = create_app(settings, proposal_credentials=account.credentials)
    app.state.cloud_account = account
    store = app.state.store

    def local_session(request: Request):
        token = request.cookies.get(settings.cookie_name)
        current = store.one(sessions, digest=digest(token)) if token else None
        if not (current and current["owner"] == owner and not current["revoked"] and current["expires"] > time.time()):
            raise HTTPException(401, "session_required")

    @app.middleware("http")
    async def loopback_security(request: Request, call_next):
        host_values = request.headers.getlist("host")
        peer = request.client.host if request.client else ""
        site = request.headers.get("sec-fetch-site")
        request_origin = request.headers.get("origin")
        forwarded = any(key.lower().startswith("x-forwarded-") or key.lower() == "forwarded"
                        for key in request.headers)
        if (peer != "127.0.0.1" or host_values != [f"127.0.0.1:{port}"] or forwarded
                or (request_origin is not None and request_origin != origin)
                or site not in (None, "none", "same-origin")):
            return JSONResponse({"detail": "local_origin_required"}, status_code=403,
                                headers={"Cache-Control": "no-store"})
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
            "connect-src 'self'; img-src 'self' blob: data:; font-src 'self'; "
            "form-action 'self'; frame-ancestors 'none'; base-uri 'self'; object-src 'none'"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        return response

    from .app_update import current_installation

    installed = current_installation() if store_version is None else None
    version = installed.version if installed else store_version

    @app.get("/v1/local/setup", response_model=LocalSetupView)
    def setup():
        return {"mode": "local", "ready": True, "fiji_configured": bool(settings.fiji_executable),
                **settings.retention_policy, "version": version}

    if store_version is not None:
        licenses = Path(__file__).absolute().parents[4] / "licenses"

        @app.get("/v1/local/corresponding-source", include_in_schema=False)
        def corresponding_source():
            archives = sorted(licenses.glob("Cytellect-*-gpl-sources.zip"))
            if len(archives) != 1 or not archives[0].is_file():
                raise HTTPException(404, "corresponding_source_missing")
            return FileResponse(archives[0], media_type="application/zip", filename=archives[0].name)

    @app.get("/v1/local/session", response_model=SessionView)
    def probe(request: Request):
        # The workspace's opening check: the same answer as GET /v1/session, but 200 with
        # authenticated false instead of a 401, so a first visit or a relaunch (which revokes
        # the cookie) logs no browser error. A GET never mints a session.
        token = request.cookies.get(settings.cookie_name)
        current = store.one(sessions, digest=digest(token)) if token else None
        authenticated = bool(current and not current["revoked"] and current["expires"] > time.time())
        return {"authenticated": authenticated, "mode": "local", **settings.retention_policy, "demo": settings.demo}

    @app.post("/v1/local/session", response_model=SessionView)
    def bootstrap(request: Request, response: Response):
        # The existing API middleware also requires exact Origin and the custom
        # CSRF header. Cross-origin forms, scripts and DNS rebinding cannot mint
        # this cookie. Local processes/other accounts on this PC are trusted.
        if request.headers.get("sec-fetch-site") not in (None, "same-origin"):
            return JSONResponse({"detail": "local_origin_required"}, status_code=403)
        now = time.time()
        existing = request.cookies.get(settings.cookie_name)
        current = store.one(sessions, digest=digest(existing)) if existing else None
        if not (current and current["owner"] == owner and not current["revoked"] and current["expires"] > now):
            token = secrets.token_urlsafe(32)
            with store.transaction() as conn:
                conn.execute(sessions.insert().values(digest=digest(token), owner=owner,
                                                     expires=now + 7 * 86400, revoked=False))
            response.set_cookie(settings.cookie_name, token, httponly=True, secure=False,
                                samesite="strict", max_age=7 * 86400, path="/")
        return {"authenticated": True, "mode": "local", **settings.retention_policy, "demo": settings.demo}

    register_account_routes(app, account, local_session)

    @app.get("/v1/local/previous-stop", dependencies=[Depends(local_session)], response_model=PreviousStopView)
    def previous_stop_view():
        # The PC owner's session only: the workspace shows one line after an abnormal stop (#284).
        if not previous_stop:
            return {"abnormal": False, "reason": None, "time": None}
        return {"abnormal": True, **previous_stop}

    @app.get("/v1/local/first-run")
    def first_run():
        # A fresh installation has never held a workspace; an update keeps its rows.
        return {"first_run": not store.rows(workspaces, owner=owner)}

    app.mount("/", StaticFiles(directory=web_dir, html=True, follow_symlink=False), name="local-ui")
    return app


@contextlib.contextmanager
def runtime_lock(root: Path):
    """OS-released lock prevents two launchers sharing SQLite/worker ownership."""
    root.mkdir(parents=True, exist_ok=True, mode=0o700)
    path = root / "local-launcher.lock"
    if path.is_symlink():
        raise ValueError("local_lock_path_invalid")
    stream = path.open("a+b")
    try:
        try:
            stream.seek(0)
            if sys.platform == "win32":
                import msvcrt

                if path.stat().st_size == 0:
                    stream.write(b"0")
                    stream.flush()
                stream.seek(0)
                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise ValueError("local_runtime_already_in_use") from exc
        yield
    finally:
        stream.close()


def bind_loopback(port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        # Windows otherwise permits a second binding under SO_REUSEADDR.
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        sock.bind(("127.0.0.1", port))
        sock.listen(128)
        return sock
    except BaseException:
        sock.close()
        raise


def local_cellpose_remote_environment(data_dir: Path) -> dict[str, str]:
    """Load the configured GPU inference service; images go there only for Cellpose."""
    path = data_dir.resolve().parent / "settings" / "cellpose-remote.json"
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 16_384:
            return {}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if (not isinstance(value, dict) or value.get("schema") != "cytellect-cellpose-remote/1"
                or not set(value) <= {"schema", "url", "token"} or not isinstance(value.get("url"), str)
                or not isinstance(value.get("token", ""), str)):
            return {}
        environment = {"CYTELLECT_CELLPOSE_REMOTE_URL": value["url"]}
        if value.get("token"):
            environment["CYTELLECT_CELLPOSE_REMOTE_TOKEN"] = value["token"]
        return environment
    except (OSError, ValueError, TypeError):
        # A damaged optional setting must not disable Fiji or the whole workspace.
        return {}


def local_retention_mode(data_dir: Path) -> str:
    """Setup's explicit per-installation choice; a recorded manual policy never reverts."""
    if recorded_retention_mode(data_dir) == "manual":
        return "manual"
    path = data_dir.resolve().parent / "settings" / "retention.json"
    try:
        if path.is_file() and not path.is_symlink() and path.stat().st_size <= 4096 and json.loads(
                path.read_text(encoding="utf-8-sig")) == {"schema": "cytellect-local-retention/1", "mode": "manual"}:
            return "manual"
    except (OSError, ValueError):
        pass
    return "ttl"


def local_cellpose_environment(data_dir: Path) -> dict[str, str]:
    """Load an explicit local setup receipt without executing setup or downloading."""
    root = data_dir.resolve().parent
    path = root / "settings" / "cellpose.json"
    try:
        if not path.is_file() or path.is_symlink() or path.stat().st_size > 16_384:
            return {}
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        if (not isinstance(value, dict) or set(value) != {"schema", "python", "model_dir"}
                or value["schema"] != "cytellect-cellpose-local/1"):
            return {}
        python, models = Path(value["python"]), Path(value["model_dir"])
        if (not python.is_absolute() or not models.is_absolute()
                or not python.resolve().is_relative_to(root) or not models.resolve().is_relative_to(root)
                or not python.is_file() or not models.is_dir()):
            return {}
        return {"CYTELLECT_CELLPOSE_PYTHON": str(python), "CYTELLECT_CELLPOSE_MODEL_DIR": str(models)}
    except (OSError, ValueError, TypeError):
        # A damaged optional setup must not disable Fiji or the whole workspace.
        return {}


class WorkerSupervisor:
    def __init__(self, settings: Settings, stop_server):
        self.settings = settings
        self.stop_server = stop_server
        self.stopping = threading.Event()
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.failure: str | None = None
        self.worker_identity: Identity | None = None

    def _spawn(self):
        env = os.environ.copy()
        for key, value in {**local_cellpose_environment(self.settings.data_dir),
                           **local_cellpose_remote_environment(self.settings.data_dir)}.items():
            env.setdefault(key, value)
        if sys.dont_write_bytecode:
            env["PYTHONDONTWRITEBYTECODE"] = "1"
        # Read at each Cellpose request, so signing in or out needs no restart.
        # Explicit CYTELLECT_CELLPOSE_REMOTE_* settings keep precedence.
        from .cloud_account import account_file

        env["CYTELLECT_CLOUD_ACCOUNT_FILE"] = str(account_file(self.settings.data_dir))
        env.update(CYTELLECT_DATA_DIR=str(self.settings.data_dir),
                   CYTELLECT_APP_ORIGIN=self.settings.app_origin, CYTELLECT_SECURE_COOKIES="false",
                   CYTELLECT_DEMO=str(self.settings.demo).lower(),
                   CYTELLECT_FIJI_EXECUTABLE=self.settings.fiji_executable,
                   CYTELLECT_WORKER_MEMORY_MB=str(self.settings.worker_memory_mb),
                   CYTELLECT_JOB_TIMEOUT_SECONDS=str(self.settings.job_timeout_seconds),
                   CYTELLECT_RETENTION_SECONDS=str(self.settings.retention_seconds),
                   CYTELLECT_WORKSPACE_RETENTION_MODE=self.settings.workspace_retention_mode)
        parent = psutil.Process()
        # Preserve the launcher's isolation from user Python settings and packages.
        flags = ["-B"] if sys.dont_write_bytecode else []
        if sys.flags.isolated:
            flags.append("-I")
        elif sys.flags.ignore_environment:
            flags.append("-E")
        process = subprocess.Popen(
            [sys.executable, *flags, "-m", "cytellect_api.local_worker", str(parent.pid), str(parent.create_time())],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )
        ready = threading.Event()
        identity_line: list[bytes] = []

        def read_identity():
            assert process.stdout is not None
            identity_line.append(process.stdout.readline(100))
            ready.set()

        threading.Thread(target=read_identity, daemon=True).start()
        try:
            deadline = time.monotonic() + 15
            while not ready.wait(0.1):
                if self.stopping.is_set() or time.monotonic() >= deadline:
                    raise RuntimeError("local_worker_start_failed")
            if self.stopping.is_set() or not identity_line:
                raise RuntimeError("local_worker_start_failed")
            pid, created = identity_line[0].decode("ascii").split()
            identity = (int(pid), float(created))
            worker = psutil.Process(identity[0])
            # Pipe contents are accepted only from this exact spawned tree.
            if (not process_alive(identity) or (identity[0] != process.pid
                    and process.pid not in [ancestor.pid for ancestor in worker.parents()])):
                raise RuntimeError("local_worker_start_failed")
            self.worker_identity = identity
            self.process = process
        except Exception:
            from cytellect_worker.supervision import terminate_tree

            terminate_tree(process.pid)
            process.wait(timeout=10)
            raise RuntimeError("local_worker_start_failed") from None
        finally:
            if ready.is_set() and process.stdout:
                process.stdout.close()

    def _stop_process(self):
        from cytellect_worker.supervision import terminate_tree

        # Stop the real interpreter first: a dead Windows shim no longer has a
        # traversable child tree. PID creation time prevents killing a reused PID.
        if self.worker_identity is not None and process_alive(self.worker_identity):
            terminate_tree(self.worker_identity[0])
        self.worker_identity = None
        if self.process is not None:
            terminate_tree(self.process.pid)
            self.process.wait(timeout=10)

    def start(self):
        self._spawn()

        def monitor():
            restarts = 0
            while not self.stopping.wait(0.25):
                if self.process is not None and self.process.poll() is not None:
                    self._stop_process()
                    if restarts >= 2:
                        self.failure = "local_worker_stopped"
                        self.stop_server()
                        return
                    restarts += 1
                    try:
                        self._spawn()
                    except Exception:
                        if self.stopping.is_set():
                            return
                        self.failure = "local_worker_start_failed"
                        self.stop_server()
                        return

        self.thread = threading.Thread(target=monitor, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:
            # A restart may be midway through its identity handshake. It sees
            # stopping within100ms, kills that pending tree and returns before
            # we clean up the last adopted worker; never publish a late restart.
            self.thread.join(timeout=15)
        if self.process is not None:
            self._stop_process()


OPEN_WORKSPACE_LABEL = "作業画面を開く"
OPENING_STATUS = "作業画面を開いています…"
# Inno Setup's uninstaller refuses to remove a running installation while this exists.
LAUNCHER_MUTEX = "CytellectLocalLauncher"


def running_status(url: str) -> str:
    return f"稼働中 · {url}\nブラウザが開かない場合は「{OPEN_WORKSPACE_LABEL}」を押してください。"


@contextlib.contextmanager
def launcher_mutex():
    """A named mutex that only signals "running" to the Windows uninstaller."""
    if sys.platform != "win32":
        yield
        return
    import ctypes

    kernel32 = ctypes.windll.kernel32
    handle = kernel32.CreateMutexW(None, False, LAUNCHER_MUTEX)
    try:
        yield
    finally:
        if handle:
            kernel32.CloseHandle(handle)


def _gui(server, url: str, run_server, open_browser: bool, *, request_stop=None, notice: str | None = None):
    """``request_stop`` records why the launcher stops; ``notice`` is one line about the previous stop."""
    import tkinter as tk
    from tkinter import ttk

    window = tk.Tk()
    window.title("Cytellect")
    window.geometry("460x230" if notice else "460x205")
    window.resizable(False, False)
    window.option_add("*Font", "{Segoe UI} 10")
    body = ttk.Frame(window, padding=(24, 16))
    body.pack(fill="both", expand=True)
    status = tk.StringVar(value="起動の準備中…")
    ttk.Label(body, text="Cytellect", font=("Segoe UI", 18)).pack(anchor="w", pady=(0, 8))
    ttk.Label(body, textvariable=status, wraplength=410).pack(anchor="w")
    if notice:
        ttk.Label(body, text=notice, wraplength=410).pack(anchor="w", pady=(6, 0))
    ttk.Label(body, text="この画面を閉じると、実行中の解析も停止します。", wraplength=410).pack(
        anchor="w", pady=(10, 16))

    def stop():
        if request_stop is not None:
            request_stop()
        server.should_exit = True
        status.set("停止中…")
        browser_button.configure(state="disabled")

    def open_current_browser():
        if server.started and not server.should_exit:
            webbrowser.open(url)

    controls = ttk.Frame(body)
    controls.pack(fill="x")
    browser_button = ttk.Button(controls, text=OPEN_WORKSPACE_LABEL, command=open_current_browser, state="disabled")
    browser_button.pack(side="left")
    ttk.Button(controls, text="停止して閉じる", command=stop).pack(side="right")
    window.protocol("WM_DELETE_WINDOW", stop)
    thread = threading.Thread(target=run_server, daemon=False)
    thread.start()
    opened = False
    # Ticks (150 ms) to keep "opening" visible before the steady running status.
    settle = 0

    def tick():
        nonlocal opened, settle
        running = server.started and not server.should_exit and thread.is_alive()
        browser_button.configure(state="normal" if running else "disabled")
        if running and not opened:
            opened = True
            if open_browser:
                status.set(OPENING_STATUS)
                settle = 20
                webbrowser.open(url)
            else:
                status.set(running_status(url))
        elif running and settle:
            settle -= 1
            if not settle:
                status.set(running_status(url))
        if not thread.is_alive():
            window.destroy()
        else:
            window.after(150, tick)

    window.after(150, tick)
    try:
        window.mainloop()
    finally:
        server.should_exit = True
        thread.join()


def server_config(app, port: int):
    import uvicorn

    # use_colors=False: uvicorn otherwise asks sys.stdout.isatty(), and the shortcut's
    # windowless pythonw has no stdout, so its logging configuration would fail.
    return uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False, proxy_headers=False,
                          log_level="error", use_colors=False, timeout_graceful_shutdown=5)


def revoke_local_sessions(app, settings: Settings) -> None:
    """Sessions stop granting access across launcher shutdown (also an in-app update's switch).

    A later same-origin bootstrap (POST /v1/local/session) resumes the stable local owner's
    work; the workspace's update banner does that when the new version answers 401.
    """
    with app.state.store.transaction() as conn:
        conn.execute(update(sessions).where(sessions.c.owner == _local_owner(settings.data_dir))
                     .values(revoked=True))


def run_local(settings: Settings, web_dir: Path, port: int = 8765, *, open_browser=True, gui=False,
              store_version: str | None = None):
    redirector = redirector_owner()
    configure_private_tmp(settings)
    with runtime_lock(settings.data_dir), launcher_mutex(), bind_loopback(port) as sock:
        # Only the lock holder reads and writes the stop record (#284): a refused second launch leaves it.
        previous = begin_stop_record(settings.data_dir)
        reason = StopReason()
        try:
            _serve_local(settings, web_dir, port, sock, redirector, reason, previous,
                         open_browser=open_browser, gui=gui, store_version=store_version)
        except BaseException as error:
            code = error.args[0] if isinstance(error, RuntimeError) and error.args else None
            reason.request(None, "launcher_closed" if isinstance(error, KeyboardInterrupt)
                           else code if code in ABNORMAL_STOPS else "unhandled_exception")
            raise
        finally:
            # A server that ended although nothing asked it to stop is an abnormal stop. (A termination
            # signal to the command-line launcher ends the process inside uvicorn: no record, "unrecorded".)
            record_stop(settings.data_dir, reason.code or "server_stopped")


def _serve_local(settings: Settings, web_dir: Path, port: int, sock, redirector, reason: StopReason,
                 previous: dict | None, *, open_browser: bool, gui: bool, store_version: str | None):
    import uvicorn

    from .app_update import restore_pending_database

    # After an update that could not restore the previous database, finish it before
    # this (previous) version opens and migrates the database.
    restore_pending_database(settings.data_dir)
    app = create_local_app(settings, web_dir, port, store_version=store_version, previous_stop=previous)
    server = uvicorn.Server(server_config(app, port))
    # A verified in-app update stops this launcher before its successor starts.
    app.state.request_shutdown = lambda: reason.request(server, "update_switch")
    supervisor: WorkerSupervisor

    def worker_ended() -> None:
        # The supervisor sets its failure ("local_worker_stopped" or "local_worker_start_failed") first.
        reason.request(server, supervisor.failure or "local_worker_stopped")

    supervisor = WorkerSupervisor(settings, worker_ended)
    supervisor.start()
    owner_watch_stopped = threading.Event()

    def watch_redirector():
        while not owner_watch_stopped.wait(0.25):
            if redirector is not None and not process_alive(redirector):
                reason.request(server, "parent_process_gone")
                return

    if redirector is not None:
        threading.Thread(target=watch_redirector, daemon=True).start()
    try:
        if gui:
            _gui(server, settings.app_origin, lambda: server.run(sockets=[sock]), open_browser,
                 request_stop=lambda: reason.request(None, "launcher_closed"), notice=previous_stop_line(previous))
        else:
            if previous:
                print("Cytellect local: the previous run stopped abnormally (" + previous["reason"] + ")", flush=True)
            if open_browser:
                def open_when_ready():
                    while not server.started and not server.should_exit:
                        time.sleep(0.1)
                    if server.started and not server.should_exit:
                        webbrowser.open(settings.app_origin)
                threading.Thread(target=open_when_ready, daemon=True).start()
            print("Cytellect local: " + settings.app_origin + " (Ctrl+C to stop)", flush=True)
            server.run(sockets=[sock])
    finally:
        owner_watch_stopped.set()
        supervisor.stop()
        revoke_local_sessions(app, settings)
    if supervisor.failure:
        raise RuntimeError(supervisor.failure)


def _report_startup_error(message: str, gui: bool, *, retry: bool = False, information: bool = False) -> bool:
    """Show a fixed message; True when the researcher chose to start again."""
    if gui and sys.platform == "win32":
        # A broken/missing Tcl installation must not make pythonw fail silently.
        import ctypes

        # MB_RETRYCANCEL | MB_ICONERROR, MB_ICONINFORMATION or MB_ICONERROR; IDRETRY is 4.
        style = 0x15 if retry else 0x40 if information else 0x10
        return ctypes.windll.user32.MessageBoxW(None, message, "Cytellect", style) == 4
    if gui:
        try:
            from tkinter import messagebox
            messagebox.showerror("Cytellect", message)
        except Exception:
            if sys.stderr:
                print(message, file=sys.stderr)
    elif sys.stderr:
        print(message, file=sys.stderr)
    return False


def already_running(error: Exception) -> bool:
    return isinstance(error, ValueError) and error.args == ("local_runtime_already_in_use",)


def _open_running_workspace(origin: str) -> bool:
    """When another launcher owns this installation, open its workspace instead (I5)."""
    import urllib.request

    # Loopback only: a laboratory's system proxy must never see this request.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(origin + "/v1/local/setup", timeout=3) as response:
            if response.status != 200:
                return False
    except (OSError, ValueError):
        return False
    return bool(webbrowser.open(origin))


def _gui_failure_message(error: Exception, *, opened: bool = False, retry: bool = True) -> str:
    """Fixed user actions only; never expose exception text or filesystem paths.

    ``retry`` is whether the message box offers 「再試行」; the last attempt names the next step instead.
    """
    if already_running(error):
        if opened:
            return "Cytellectは既に起動しています。作業画面をブラウザで開きました。"
        return "Cytellectは既に起動しています。開いているCytellectの画面で「作業画面を開く」を押してください。"
    if isinstance(error, OSError) and (error.errno == errno.EADDRINUSE
                                     or getattr(error, "winerror", None) == 10048):
        reason = "接続先（ポート）が使用中のため起動できません。別のソフトがこのポートを使っています。"
        return reason + ("「再試行」を押すと、もう一度起動します。続く場合はPCを再起動してください。" if retry
                         else "PCを再起動してから、デスクトップの「Cytellect」を開いてください。")
    reason = "Cytellectを起動できないか、実行が停止しました。"
    return reason + ("「再試行」を押すと、もう一度起動します。開き直しても続く場合は、"
                     "インストーラーをもう一度開いてください（データは保たれます）。" if retry
                     else "PCを再起動してから、デスクトップの「Cytellect」を開いてください。"
                     "続く場合は、インストーラーをもう一度開いてください（データは保たれます）。")


def _null_missing_streams() -> None:
    """pythonw (the shortcut) starts without stdout/stderr; libraries expect file objects."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))  # noqa: SIM115 - process lifetime


def main(argv=None, *, store_version: str | None = None):
    _null_missing_streams()
    parser = argparse.ArgumentParser(prog="cytellect local")
    parser.add_argument("--data-dir", type=Path, default=os.environ.get("CYTELLECT_DATA_DIR"))
    parser.add_argument("--web-dir", type=Path, default=os.environ.get("CYTELLECT_WEB_DIR"))
    parser.add_argument("--fiji", default=os.environ.get("CYTELLECT_FIJI_EXECUTABLE", ""))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--gui", action="store_true")
    args = parser.parse_args(argv)
    if (not args.data_dir or not args.web_dir or not args.fiji or not 1 <= args.port <= 65535
            or not Path(args.fiji).exists()):
        message = ("Cytellectの準備が完了していません。インストーラーをもう一度開いてください（データは保たれます）。" if args.gui else
                   "Cytellect installation is incomplete. Run the setup program again.")
        _report_startup_error(message, args.gui)
        raise SystemExit(2)
    settings = Settings(args.data_dir.resolve(), app_origin=f"http://127.0.0.1:{args.port}",
                        workspace_retention_mode=local_retention_mode(args.data_dir.resolve()),
                        secure_cookies=False, fiji_executable=args.fiji)
    os.environ.pop("CYTELLECT_CODE_REVISION", None)
    revision = installed_source_revision()
    if revision:
        os.environ["CYTELLECT_CODE_REVISION"] = revision
    elif store_version is not None:
        _report_startup_error("Cytellectのファイルを確認できません。Microsoft Storeから入れ直してください。", args.gui)
        raise SystemExit(2)
    from .local_storage import installed_usage_lock, usage_lock

    for attempt in range(3):
        try:
            # The Store package shares the installer's folder, so it holds that folder's lock:
            # the installer's setup, update and storage collection then see it running.
            with usage_lock(settings.data_dir.parent) if store_version is not None else installed_usage_lock():
                run_local(settings, args.web_dir, args.port, open_browser=not args.no_browser, gui=args.gui,
                          store_version=store_version)
            return
        except Exception as exc:
            if not args.gui:
                _report_startup_error("Cytellect could not start or stopped. Check the local port, "
                                      "installation and runtime directory.", False)
                raise SystemExit(1) from None
            if already_running(exc):
                opened = not args.no_browser and _open_running_workspace(settings.app_origin)
                _report_startup_error(_gui_failure_message(exc, opened=opened), True, information=opened)
                raise SystemExit(1) from None
            # Port in use or a failed start: show the reason and offer to start again.
            retry = attempt < 2
            if not _report_startup_error(_gui_failure_message(exc, retry=retry), True, retry=retry):
                raise SystemExit(1) from None


if __name__ == "__main__":
    main()

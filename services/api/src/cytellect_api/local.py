"""Explicit single-user loopback mode; the cloud API never mounts these routes."""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
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
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy import update
from starlette.staticfiles import StaticFiles

from .config import Settings, configure_private_tmp
from .db import digest, sessions


def installed_source_revision(root: Path | None = None) -> str | None:
    """A release label only when installed source matches its complete manifest.

    The manifest is not a code signature. Exported per-file/aggregate source
    hashes remain the identity of executed scientific code.
    """
    root = root or Path(__file__).resolve().parents[4]
    manifest = root / "local-release.json"
    if not manifest.is_file():
        return None
    try:
        release = json.loads(manifest.read_text(encoding="utf-8"))
        revision = release["source_commit"]
        if release["schema"] != "cytellect-local-release/1" or not re.fullmatch("[a-f0-9]{40}", revision):
            return None
        entries = {}
        for item in release["files"]:
            name = item["path"]
            if (not isinstance(name, str) or name in entries or "\\" in name or ":" in name
                    or name.startswith("/") or any(part in {"", ".", ".."} for part in name.split("/"))):
                return None
            file = root / name
            if (not file.resolve().is_relative_to(root.resolve()) or not file.is_file()
                    or file.stat().st_size != item["size"]
                    or hashlib.sha256(file.read_bytes()).hexdigest() != item["sha256"]):
                return None
            entries[name] = item
        for relative in ("packages/analysis/src/cytellect_analysis", "services/api/src/cytellect_api",
                         "services/worker/src/cytellect_worker"):
            directory = root / relative
            if not (directory / "__init__.py").is_file():
                return None
            for file in directory.rglob("*.py"):
                if file.relative_to(root).as_posix() not in entries:
                    return None
        return revision
    except (OSError, ValueError, KeyError, TypeError):
        return None


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


def create_local_app(settings: Settings, web_dir: Path, port: int):
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

    app = create_app(settings)
    store = app.state.store

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

    @app.get("/v1/local/setup")
    def setup():
        return {"mode": "local", "ready": True, "fiji_configured": bool(settings.fiji_executable),
                "retention_hours": 24}

    @app.post("/v1/local/session")
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
        return {"authenticated": True, "mode": "local", "retention_hours": 24, "demo": settings.demo}

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
        yield
    except OSError as exc:
        raise ValueError("local_runtime_already_in_use") from exc
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


class WorkerSupervisor:
    def __init__(self, settings: Settings, stop_server):
        self.settings = settings
        self.stop_server = stop_server
        self.stopping = threading.Event()
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.failure: str | None = None

    def _spawn(self):
        env = os.environ.copy()
        env.update(CYTELLECT_DATA_DIR=str(self.settings.data_dir),
                   CYTELLECT_APP_ORIGIN=self.settings.app_origin, CYTELLECT_SECURE_COOKIES="false",
                   CYTELLECT_DEMO=str(self.settings.demo).lower(),
                   CYTELLECT_FIJI_EXECUTABLE=self.settings.fiji_executable,
                   CYTELLECT_WORKER_MEMORY_MB=str(self.settings.worker_memory_mb),
                   CYTELLECT_JOB_TIMEOUT_SECONDS=str(self.settings.job_timeout_seconds),
                   CYTELLECT_RETENTION_SECONDS=str(self.settings.retention_seconds))
        parent = psutil.Process()
        self.process = subprocess.Popen(
            [sys.executable, "-m", "cytellect_api.local_worker", str(parent.pid), str(parent.create_time())],
            env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0) if os.name == "nt" else 0,
            start_new_session=os.name != "nt",
        )

    def start(self):
        self._spawn()

        def monitor():
            restarts = 0
            while not self.stopping.wait(0.25):
                if self.process is not None and self.process.poll() is not None:
                    if restarts >= 2:
                        self.failure = "local_worker_stopped"
                        self.stop_server()
                        return
                    restarts += 1
                    try:
                        self._spawn()
                    except Exception:
                        self.failure = "local_worker_start_failed"
                        self.stop_server()
                        return

        self.thread = threading.Thread(target=monitor, daemon=True)
        self.thread.start()

    def stop(self):
        self.stopping.set()
        if self.thread:
            self.thread.join(timeout=3)
        if self.process is not None:
            from cytellect_worker.supervision import terminate_tree

            terminate_tree(self.process.pid)
            self.process.wait(timeout=10)


def _gui(server, url: str, run_server, open_browser: bool):
    import tkinter as tk
    from tkinter import ttk

    window = tk.Tk()
    window.title("Cytellect")
    window.geometry("460x205")
    window.resizable(False, False)
    window.option_add("*Font", "{Segoe UI} 10")
    body = ttk.Frame(window, padding=(24, 16))
    body.pack(fill="both", expand=True)
    status = tk.StringVar(value="起動中…")
    ttk.Label(body, text="Cytellect", font=("Segoe UI", 18)).pack(anchor="w", pady=(0, 8))
    ttk.Label(body, textvariable=status).pack(anchor="w")
    ttk.Label(body, text="この画面を閉じると、実行中の解析も停止します。", wraplength=410).pack(
        anchor="w", pady=(10, 16))

    def stop():
        server.should_exit = True
        status.set("停止中…")

    controls = ttk.Frame(body)
    controls.pack(fill="x")
    ttk.Button(controls, text="ブラウザで開く", command=lambda: webbrowser.open(url)).pack(side="left")
    ttk.Button(controls, text="停止して閉じる", command=stop).pack(side="right")
    window.protocol("WM_DELETE_WINDOW", stop)
    thread = threading.Thread(target=run_server, daemon=False)
    thread.start()
    opened = False

    def tick():
        nonlocal opened
        if server.started and not opened and not server.should_exit:
            opened = True
            status.set("起動中 · " + url)
            if open_browser:
                webbrowser.open(url)
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


def run_local(settings: Settings, web_dir: Path, port: int = 8765, *, open_browser=True, gui=False):
    import uvicorn

    configure_private_tmp(settings)
    with runtime_lock(settings.data_dir), bind_loopback(port) as sock:
        app = create_local_app(settings, web_dir, port)
        server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, access_log=False,
                                               proxy_headers=False, log_level="error",
                                               timeout_graceful_shutdown=5))
        supervisor = WorkerSupervisor(settings, lambda: setattr(server, "should_exit", True))
        supervisor.start()
        try:
            if gui:
                _gui(server, settings.app_origin, lambda: server.run(sockets=[sock]), open_browser)
            else:
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
            supervisor.stop()
            # Sessions stop granting access across launcher shutdown. A later
            # same-origin bootstrap resumes the stable local owner's work.
            with app.state.store.transaction() as conn:
                conn.execute(update(sessions).where(sessions.c.owner == _local_owner(settings.data_dir))
                             .values(revoked=True))
        if supervisor.failure:
            raise RuntimeError(supervisor.failure)


def _report_startup_error(message: str, gui: bool):
    if gui and sys.platform == "win32":
        # A broken/missing Tcl installation must not make pythonw fail silently.
        import ctypes

        ctypes.windll.user32.MessageBoxW(None, message, "Cytellect", 0x10)
    elif gui:
        try:
            from tkinter import messagebox
            messagebox.showerror("Cytellect", message)
        except Exception:
            if sys.stderr:
                print(message, file=sys.stderr)
    elif sys.stderr:
        print(message, file=sys.stderr)


def main(argv=None):
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
        _report_startup_error("Cytellect installation is incomplete. Run the setup program again.", args.gui)
        raise SystemExit(2)
    settings = Settings(args.data_dir.resolve(), app_origin=f"http://127.0.0.1:{args.port}",
                        secure_cookies=False, fiji_executable=args.fiji)
    os.environ.pop("CYTELLECT_CODE_REVISION", None)
    revision = installed_source_revision()
    if revision:
        os.environ["CYTELLECT_CODE_REVISION"] = revision
    try:
        run_local(settings, args.web_dir, args.port, open_browser=not args.no_browser, gui=args.gui)
    except Exception:
        message = "Cytellect could not start or stopped. Check the local port, installation and runtime directory."
        _report_startup_error(message, args.gui)
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()

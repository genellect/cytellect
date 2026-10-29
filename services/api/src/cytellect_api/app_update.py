"""In-app update of the Windows installation (requirement I7).

``GET /v1/app/update`` reports ``current``, ``latest``, ``available`` and ``notes_url``,
plus the update ``state`` and a fixed ``error`` code. ``POST /v1/app/update`` starts an
update: it downloads the release's ``Cytellect-Setup-<version>.exe``, checks the SHA-256
published with the release, and runs that installer silently into the same folder. The
installer prepares the new version beside the current one and verifies it before the
shortcuts change. Only then does this launcher stop and a small relauncher start the new
version. If the new version does not answer, the relauncher restores the database copy
taken before the switch, the previous shortcuts and the previous version.

Trust: the published ``.sha256`` and GitHub's asset digest come from the same release, so
they detect corruption and a wrong file, not a compromised release. The trust anchor is
write access to genellect/cytellect and its release workflow token (docs/security.md).

The only network request is to GitHub's public release list of genellect/cytellect and
the release's own files. No research data, file names or identifiers are sent. The
routes exist only in the loopback local application, never in a hosted API.
"""

import argparse
import contextlib
import hashlib
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
import urllib.parse
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

REPOSITORY = "genellect/cytellect"
RELEASES_URL = f"https://api.github.com/repos/{REPOSITORY}/releases?per_page=30"
NOTES_PREFIX = f"https://github.com/{REPOSITORY}/releases/"
DOWNLOAD_HOSTS = frozenset({"github.com", "objects.githubusercontent.com", "release-assets.githubusercontent.com"})
USER_AGENT = "cytellect-local-update"
CHECK_SECONDS = 6 * 3600
RETRY_CHECK_SECONDS = 15 * 60
MAX_INSTALLER_BYTES = 2 * 1024**3
MAX_JSON_BYTES = 2 * 1024**2
INSTALLER_TIMEOUT_SECONDS = 3600
START_TIMEOUT_SECONDS = 300
EXIT_TIMEOUT_SECONDS = 120
JOBS_WAIT_SECONDS = 600
LOCAL_VERSION = re.compile(r"([0-9]+)\.([0-9]+)\.([0-9]+)-local\.([0-9]+)")
SHORTCUT_DESCRIPTION = "Cytellect local analysis and control window"
ROOT_MARKER = {"product": "cytellect-local", "schema": 1}
# States written while this launcher works on an update; "installed" and the results are final.
ACTIVE = frozenset({"downloading", "installing", "restarting"})
# Files in updates/ that are not downloads.
UPDATE_RECORDS = frozenset({"state.json", "latest.json", "switch.json", "rollback"})


class UpdateRefused(Exception):
    """A fixed reason code for a refused POST."""


def version_key(version: str | None) -> tuple[int, ...] | None:
    match = LOCAL_VERSION.fullmatch(version or "")
    return tuple(int(part) for part in match.groups()) if match else None


def newer(candidate: str | None, current: str | None) -> bool:
    """Only well-formed local versions compare; anything else is never an update."""
    new, old = version_key(candidate), version_key(current)
    return new is not None and old is not None and new > old


@dataclass(frozen=True)
class Installation:
    """One verified application version inside a Cytellect installation folder."""

    root: Path
    app: Path
    version: str
    fiji: str

    @property
    def updates(self) -> Path:
        return self.root / "updates"

    def launch(self) -> list[str]:
        """The same command as the stable shortcut that setup writes."""
        pythonw = self.app / ".venv" / "Scripts" / "pythonw.exe"
        return [str(pythonw), "-B", "-m", "cytellect_api.local", "--fiji", self.fiji,
                "--data-dir", str(self.root / "data"), "--web-dir", str(self.app / "apps" / "web" / "out"), "--gui"]

    def record(self) -> dict[str, str]:
        return {"app": str(self.app), "fiji": self.fiji, "version": self.version}


def read_installation(app: Path) -> Installation | None:
    """An application directory that setup completed, inside an owned installation root."""
    try:
        app = app.absolute()
        root = app.parent.parent
        if app.parent.name != "apps" or json.loads((root / "setup-root.json").read_text(encoding="utf-8")) != ROOT_MARKER:
            return None
        release = json.loads((app / "local-release.json").read_text(encoding="utf-8"))
        marker = json.loads((app / "setup-complete.json").read_text(encoding="utf-8"))
        if (marker.get("version") != release.get("version") or Path(marker["app"]).absolute() != app
                or not isinstance(marker.get("fiji"), str)):
            return None
        return Installation(root, app, str(release["version"]), marker["fiji"])
    except (OSError, ValueError, KeyError, TypeError):
        return None


def current_installation(module_file: str | Path = __file__) -> Installation | None:
    """The installed copy that runs this module (``<app>/.venv/Lib/site-packages``)."""
    return read_installation(Path(module_file).absolute().parents[4])


def installed_version(root: Path, version: str) -> Installation | None:
    """The completed application of exactly this version in the installation root."""
    found = [item for path in sorted((root / "apps").glob(f"{version}-*"))
             if (item := read_installation(path)) is not None and item.version == version]
    return found[0] if len(found) == 1 else None


class _CheckedRedirect(urllib.request.HTTPRedirectHandler):
    """Follow redirects only to GitHub's release hosts over HTTPS."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001 - stdlib signature
        allowed_download(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def allowed_download(url: str) -> str:
    parts = urllib.parse.urlsplit(url)
    if parts.scheme != "https" or parts.hostname not in DOWNLOAD_HOSTS | {"api.github.com"} or parts.port:
        raise UpdateRefused("update_download_host_refused")
    return url


def open_url(url: str, timeout: float):
    """GitHub over HTTPS with the system proxy and certificate store."""
    request = urllib.request.Request(allowed_download(url), headers={
        "User-Agent": USER_AGENT, "Accept": "application/vnd.github+json, application/octet-stream"})
    return urllib.request.build_opener(_CheckedRedirect()).open(request, timeout=timeout)


def fetch_json(url: str) -> Any:
    with open_url(url, 10) as response:
        data = response.read(MAX_JSON_BYTES + 1)
    if len(data) > MAX_JSON_BYTES:
        raise ValueError("update_response_too_large")
    return json.loads(data)


def latest_release(releases: Any) -> dict[str, Any] | None:
    """The newest published local release that carries an installer and its checksum."""
    best: dict[str, Any] | None = None
    if not isinstance(releases, list):
        return None
    for release in releases:
        if not isinstance(release, dict) or release.get("draft"):
            continue
        tag = str(release.get("tag_name", ""))
        version = tag[1:] if tag.startswith("v") else ""
        if version_key(version) is None:
            continue
        assets = {asset.get("name"): asset for asset in release.get("assets", []) if isinstance(asset, dict)}
        installer = assets.get(f"Cytellect-Setup-{version}.exe")
        checksum = assets.get(f"Cytellect-Setup-{version}.exe.sha256")
        if not installer or not checksum:
            continue
        notes = release.get("html_url")
        # The banner links here: only this repository's own release pages.
        notes = notes if isinstance(notes, str) and notes.startswith(NOTES_PREFIX) else None
        candidate = {"version": version, "notes_url": notes,
                     "installer_url": installer.get("browser_download_url"),
                     "installer_bytes": installer.get("size"), "installer_digest": installer.get("digest"),
                     "checksum_url": checksum.get("browser_download_url")}
        if best is None or newer(version, best["version"]):
            best = candidate
    return best


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value), encoding="utf-8")
    os.replace(temporary, path)


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def file_sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def stop_tree(process: Any) -> None:
    """Stop a started process and every descendant (the installer runs PowerShell, uv, Python)."""
    import psutil

    with contextlib.suppress(psutil.Error, OSError, AttributeError):
        parent = psutil.Process(process.pid)
        for child in [*parent.children(recursive=True), parent]:
            with contextlib.suppress(psutil.Error):
                child.kill()


def run_installer(installer: Path, root: Path) -> int:
    """Inno Setup silent mode: no window, no restart, into this installation folder."""
    try:
        process = subprocess.Popen([str(installer), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/DIR={root}"],
                                   stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError:
        return -1
    try:
        return process.wait(timeout=INSTALLER_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # A hung setup must not keep running behind the workspace.
        stop_tree(process)
        with contextlib.suppress(subprocess.TimeoutExpired):
            process.wait(timeout=30)
        return -1


def detach(command: list[str], cwd: Path) -> subprocess.Popen:
    """Start a process that outlives this launcher, without a console window."""
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200 | 0x08000000  # DETACHED, NEW_PROCESS_GROUP, NO_WINDOW
        with contextlib.suppress(OSError):
            return subprocess.Popen(command, cwd=cwd, creationflags=flags | 0x01000000,  # BREAKAWAY_FROM_JOB
                                    stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    return subprocess.Popen(command, cwd=cwd, creationflags=flags, start_new_session=os.name != "nt",
                            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def remove_downloads(updates: Path) -> None:
    """Downloaded installers and partial files are disposable; the records are kept."""
    with contextlib.suppress(OSError):
        for entry in updates.iterdir():
            if entry.name in UPDATE_RECORDS or entry.name.endswith(".tmp"):
                continue
            if entry.is_dir() and not entry.is_symlink():
                shutil.rmtree(entry, ignore_errors=True)
            else:
                with contextlib.suppress(OSError):
                    entry.unlink()


class UpdateService:
    def __init__(self, installation: Installation | None, *, port: int = 8765,
                 fetch: Callable[[str], Any] = fetch_json, opener: Callable[[str, float], Any] = open_url,
                 installer: Callable[[Path, Path], int] = run_installer,
                 spawn: Callable[[list[str], Path], Any] = detach,
                 shutdown: Callable[[], Callable[[], None] | None] = lambda: None,
                 busy: Callable[[], bool] = lambda: False,
                 clock: Callable[[], float] = time.time, sleep: Callable[[float], None] = time.sleep,
                 background: bool = True):
        self.installation = installation
        self.port = port
        self.fetch, self.opener, self.installer, self.spawn = fetch, opener, installer, spawn
        self.shutdown, self.busy, self.clock, self.sleep = shutdown, busy, clock, sleep
        self.background = background
        self.lock = threading.Lock()
        self.worker: threading.Thread | None = None
        self.memory: dict[str, Any] = {}

    # Persistent state lives beside, never inside, the research data folder.
    def _state(self) -> dict[str, Any]:
        if self.installation is None:
            return {}
        state = read_json(self.installation.updates / "state.json")
        if state.get("state") == "restarting" and state.get("version") == self.installation.version:
            # This is the new version, answering before the relauncher records success.
            return {**state, "state": "updated"}
        running = self.worker is not None and (self.worker.is_alive() or state.get("state") == "restarting")
        if state.get("state") in ACTIVE and not running:
            # A launcher closed during an update, or a switch never finished; the current version runs.
            state = {**state, "state": "failed", "error": "update_interrupted"}
        return state

    def _set_state(self, state: str, **values: Any) -> None:
        if self.installation is not None:
            write_json(self.installation.updates / "state.json",
                       {"state": state, "time": self.clock(), **values})

    def check(self) -> dict[str, Any] | None:
        """Cached release check; offline or failing GitHub never raises."""
        if self.installation is None:
            return None
        now = self.clock()
        cache_path = self.installation.updates / "latest.json"
        cached = self.memory or read_json(cache_path)
        age = now - float(cached.get("checked", 0) or 0)
        if cached and age < (CHECK_SECONDS if cached.get("ok") else RETRY_CHECK_SECONDS):
            return cached.get("release")
        try:
            release = latest_release(self.fetch(RELEASES_URL))
            cached = {"checked": now, "ok": True, "release": release}
        except Exception:
            # Offline: keep the last successful answer for display, retry later.
            cached = {"checked": now, "ok": False, "release": cached.get("release")}
        self.memory = cached
        with contextlib.suppress(OSError):
            write_json(cache_path, cached)
        return cached.get("release")

    def status(self) -> dict[str, Any]:
        if self.installation is None:
            return {"current": None, "latest": None, "available": False, "notes_url": None,
                    "state": "unsupported", "error": None}
        release = self.check()
        current = self.installation.version
        latest = release["version"] if release else None
        available = newer(latest, current)
        state = self._state()
        return {"current": current, "latest": latest, "available": available,
                "notes_url": release.get("notes_url") if release else None,
                "state": state.get("state", "idle"), "error": state.get("error")}

    def start(self) -> dict[str, Any]:
        if self.installation is None:
            raise UpdateRefused("update_unsupported")
        with self.lock:
            if self.worker is not None and self.worker.is_alive():
                raise UpdateRefused("update_in_progress")
            status = self.status()
            release = self.check()
            if not status["available"] or release is None:
                raise UpdateRefused("update_not_available")
            # Switching stops the worker; never interrupt an analysis without notice.
            if self.busy():
                raise UpdateRefused("update_jobs_running")
            remove_downloads(self.installation.updates)
            self._set_state("downloading", version=release["version"])
            self.worker = threading.Thread(target=self._run, args=(release,), daemon=True)
            if self.background:
                self.worker.start()
            else:
                self.worker.run()
        return self.status()

    def _expected_digest(self, release: dict[str, Any]) -> str:
        with self.opener(release["checksum_url"], 30) as response:
            words = response.read(4096).decode("ascii").split()
        if len(words) < 1 or not re.fullmatch(r"[0-9a-f]{64}", words[0]):
            raise UpdateRefused("update_checksum_invalid")
        digest = release.get("installer_digest")
        # GitHub's own asset digest, when present, must agree with the published file.
        if digest and digest != f"sha256:{words[0]}":
            raise UpdateRefused("update_checksum_mismatch")
        return words[0]

    def _download(self, release: dict[str, Any], target: Path, expected: str) -> None:
        partial = target.with_name(target.name + ".partial")
        hasher, received = hashlib.sha256(), 0
        try:
            with self.opener(release["installer_url"], 60) as response, partial.open("wb") as stream:
                while chunk := response.read(1024 * 1024):
                    received += len(chunk)
                    if received > MAX_INSTALLER_BYTES:
                        raise UpdateRefused("update_installer_too_large")
                    hasher.update(chunk)
                    stream.write(chunk)
            if hasher.hexdigest() != expected or (release.get("installer_bytes") not in (None, received)):
                raise UpdateRefused("update_installer_hash_mismatch")
            os.replace(partial, target)
        finally:
            partial.unlink(missing_ok=True)

    def _run(self, release: dict[str, Any]) -> None:
        assert self.installation is not None
        version = release["version"]
        folder = self.installation.updates / version
        try:
            folder.mkdir(parents=True, exist_ok=True)
            installer = folder / f"Cytellect-Setup-{version}.exe"
            expected = self._expected_digest(release)
            self._download(release, installer, expected)
            self._set_state("installing", version=version)
            # Verify again immediately before execution; the file is in the user's own folder.
            if file_sha256(installer) != expected:
                raise UpdateRefused("update_installer_hash_mismatch")
            code = self.installer(installer, self.installation.root)
            if code != 0:
                # Setup failed before switching: the current version stays as it is.
                raise UpdateRefused("update_install_failed")
            target = installed_version(self.installation.root, version)
            if target is None:
                raise UpdateRefused("update_install_incomplete")
            if not self._wait_for_jobs():
                # Installed and verified; the shortcut already opens it, so the next start uses it.
                self._set_state("installed", version=version, error="update_jobs_running")
                return
            self._switch(target)
        except UpdateRefused as refused:
            self._set_state("failed", version=version, error=str(refused))
        except Exception:
            self._set_state("failed", version=version, error="update_failed")
        finally:
            # The installer is not needed after it ran; a retry downloads it again.
            shutil.rmtree(folder, ignore_errors=True)

    def _wait_for_jobs(self) -> bool:
        """An analysis started while the installer ran finishes before the switch."""
        deadline = self.clock() + JOBS_WAIT_SECONDS
        while self.busy():
            if self.clock() >= deadline:
                return False
            self.sleep(5)
        return True

    def _switch(self, target: Installation) -> None:
        assert self.installation is not None
        import psutil

        me = psutil.Process()
        plan = {"schema": "cytellect-update-switch/1", "root": str(self.installation.root), "port": self.port,
                "wait_pid": me.pid, "wait_created": me.create_time(),
                "previous": self.installation.record(), "target": target.record()}
        plan_path = self.installation.updates / "switch.json"
        write_json(plan_path, plan)
        self._set_state("restarting", version=target.version)
        python = Path(sys.executable)
        relauncher = python.with_name("pythonw.exe") if python.with_name("pythonw.exe").is_file() else python
        self.spawn([str(relauncher), "-B", "-m", "cytellect_api.app_update", "relaunch", "--plan", str(plan_path)],
                   self.installation.app)
        stop = self.shutdown()
        if stop is not None:
            stop()


# --- Relauncher: runs after the previous launcher has exited -------------------------


def database_copy(source: Path, target: Path) -> None:
    """SQLite's online backup, so a write-ahead log is included consistently."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(source)) as origin, contextlib.closing(sqlite3.connect(target)) as copy:
        origin.backup(copy)


def wait_for_exit(pid: int, created: float, timeout: float = EXIT_TIMEOUT_SECONDS) -> bool:
    import psutil

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            process = psutil.Process(pid)
            if abs(process.create_time() - created) > 0.01:
                return True  # the identifier now names another process
        except psutil.NoSuchProcess:
            return True
        time.sleep(0.25)
    return False


def process_running(pid: int, created: float) -> bool:
    import psutil

    try:
        return abs(psutil.Process(pid).create_time() - created) <= 0.01
    except psutil.Error:
        return False


def answers(port: int, version: str, timeout: float = START_TIMEOUT_SECONDS, process: Any = None) -> bool:
    """The new launcher, of exactly this version, serves its local status on loopback."""
    deadline = time.monotonic() + timeout
    # Loopback only: a laboratory's system proxy must never see this request.
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            return False
        with contextlib.suppress(OSError, ValueError):
            with opener.open(f"http://127.0.0.1:{port}/v1/local/setup", timeout=3) as response:
                status = json.loads(response.read(65536))
                if response.status == 200 and status.get("mode") == "local" and status.get("version") == version:
                    return True
        time.sleep(1)
    return False


SHORTCUT_SCRIPT = r"""
$ErrorActionPreference = 'Stop'
$shell = New-Object -ComObject WScript.Shell
foreach ($folder in @([Environment]::GetFolderPath('DesktopDirectory'), [Environment]::GetFolderPath('Programs'))) {
    $path = Join-Path $folder 'Cytellect.lnk'
    if (-not [IO.File]::Exists($path)) { continue }
    $link = $shell.CreateShortcut($path)
    if ($link.Description -cne $env:CYTELLECT_LINK_DESCRIPTION -or
        -not $link.TargetPath.StartsWith($env:CYTELLECT_LINK_APPS, [StringComparison]::OrdinalIgnoreCase)) { continue }
    $link.TargetPath = $env:CYTELLECT_LINK_TARGET
    $link.Arguments = $env:CYTELLECT_LINK_ARGUMENTS
    $link.WorkingDirectory = $env:CYTELLECT_LINK_DIRECTORY
    $link.Save()
}
"""


def restore_shortcuts(installation: Installation) -> None:
    """Point this installation's own stable shortcuts back at the previous version."""
    if os.name != "nt":
        return
    command = installation.launch()
    arguments = subprocess.list2cmdline(command[1:])
    environment = {**os.environ, "CYTELLECT_LINK_DESCRIPTION": SHORTCUT_DESCRIPTION,
                   "CYTELLECT_LINK_APPS": str(installation.root / "apps") + "\\",
                   "CYTELLECT_LINK_TARGET": command[0], "CYTELLECT_LINK_ARGUMENTS": arguments,
                   "CYTELLECT_LINK_DIRECTORY": str(installation.app)}
    shell = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32/WindowsPowerShell/v1.0/powershell.exe"
    with contextlib.suppress(OSError, subprocess.SubprocessError):
        subprocess.run([str(shell), "-NoProfile", "-NonInteractive", "-Command", SHORTCUT_SCRIPT], env=environment,
                       stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=60, check=False, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))


@dataclass
class Relaunch:
    """Side effects of the switch, replaceable in tests."""

    wait: Callable[[int, float], bool] = wait_for_exit
    start: Callable[[list[str], Path], Any] = detach
    healthy: Callable[[int, str, Any], bool] = lambda port, version, process: answers(port, version, process=process)
    stop: Callable[[Any], None] = stop_tree
    shortcuts: Callable[[Installation], None] = restore_shortcuts
    copy: Callable[[Path, Path], None] = database_copy
    alive: Callable[[int, float], bool] = lambda pid, created: process_running(pid, created)
    clock: Callable[[], float] = time.time


def relaunch(plan_path: Path, effects: Relaunch | None = None) -> str:
    """Switch to the new version; on any failure, return to the previous one (I7).

    Every failure path restores the previous shortcuts and leaves the previous version
    running. The database copy is deleted only after it was restored or is no longer needed.
    """
    effects = effects or Relaunch()
    plan = read_json(plan_path)
    if plan.get("schema") != "cytellect-update-switch/1":
        return "invalid_plan"
    root = Path(plan["root"])
    previous = read_installation(Path(plan["previous"]["app"]))
    target = read_installation(Path(plan["target"]["app"]))
    state_path = root / "updates" / "state.json"

    def record(state: str, **values: Any) -> str:
        with contextlib.suppress(OSError):
            write_json(state_path, {"state": state, "time": effects.clock(), **values})
        return state

    if previous is None or target is None or previous.root != root or target.root != root:
        return record("failed", error="update_switch_invalid")
    database = root / "data" / "cytellect.sqlite"
    snapshot = root / "updates" / "rollback" / f"{previous.version}.sqlite"
    pid, created = int(plan["wait_pid"]), float(plan["wait_created"])
    errors: list[str] = []
    process: Any = None
    had_database = False
    copied = False
    try:
        if not effects.wait(pid, created):
            errors.append("update_previous_still_running")
        else:
            snapshot.unlink(missing_ok=True)
            had_database = database.is_file()
            if had_database:
                effects.copy(database, snapshot)
                copied = True
            process = effects.start(target.launch(), target.app)
            if effects.healthy(int(plan["port"]), target.version, process):
                # The copy holds research records; keep none once the new version runs.
                snapshot.unlink(missing_ok=True)
                return record("updated", version=target.version, previous=previous.version)
            errors.append("update_new_version_failed_to_start")
    except Exception:
        errors.append("update_switch_failed" if copied or not had_database else "update_database_copy_failed")
    # Return to the previous version. Each step is independent: one failure never skips the rest.
    if process is not None:
        with contextlib.suppress(Exception):
            effects.stop(process)
    if copied:
        try:
            effects.copy(snapshot, database)
            snapshot.unlink(missing_ok=True)
        except Exception:
            # Kept for recovery: updates/rollback/<previous version>.sqlite is the pre-update database.
            errors.append("update_database_restore_failed")
    elif had_database is False and process is not None and database.is_file():
        # There was no database before the switch, so this one holds no research records.
        with contextlib.suppress(OSError):
            database.unlink()
    with contextlib.suppress(Exception):
        effects.shortcuts(previous)
    # Recorded before the previous version starts, so that its first answer already reports it.
    result = record("rolled_back", version=target.version, previous=previous.version, error=errors[0],
                    errors=errors)
    # The previous launcher may still be running (it did not exit): then it is already the previous version.
    if not effects.alive(pid, created):
        with contextlib.suppress(Exception):
            effects.start(previous.launch(), previous.app)
    return result


def register_app_update_routes(api, settings, owner) -> None:
    """Loopback local application only; a hosted API never offers self-update."""
    if urllib.parse.urlsplit(settings.app_origin).hostname != "127.0.0.1" or settings.secure_cookies:
        return
    from fastapi import Depends, HTTPException
    from sqlalchemy import func, select

    from .db import jobs

    Owner = Annotated[str, Depends(owner)]
    port = urllib.parse.urlsplit(settings.app_origin).port or 8765
    holder: dict[str, UpdateService] = {}

    def busy() -> bool:
        """Queued or running analyses of any workspace on this PC."""
        with api.state.store.engine.connect() as conn:
            count = conn.execute(select(func.count()).select_from(jobs)
                                 .where(jobs.c.state.in_(["queued", "running"]))).scalar_one()
        return bool(count)

    def service() -> UpdateService:
        if "service" not in holder:
            holder["service"] = UpdateService(current_installation(), port=port, busy=busy,
                                              shutdown=lambda: getattr(api.state, "request_shutdown", None))
        return holder["service"]

    @api.get("/v1/app/update", include_in_schema=False)
    def update_status(_who: Owner):
        return service().status()

    @api.post("/v1/app/update", status_code=202, include_in_schema=False)
    def start_update(_who: Owner):
        try:
            return service().start()
        except UpdateRefused as refused:
            raise HTTPException(409, str(refused)) from None


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="python -m cytellect_api.app_update")
    commands = parser.add_subparsers(dest="command", required=True)
    switch = commands.add_parser("relaunch")
    switch.add_argument("--plan", type=Path, required=True)
    args = parser.parse_args(argv)
    raise SystemExit(0 if relaunch(args.plan) in {"updated", "rolled_back"} else 1)


if __name__ == "__main__":
    main()

"""In-app update of the Windows installation with fake GitHub responses (I7).

No network request, installer or launcher runs: every side effect is a test double,
and the installation tree is a generated scratch layout without research data.
"""
import contextlib
import hashlib
import io
import json
import os
import sqlite3
from pathlib import Path

import pytest
from cytellect_api import app_update
from cytellect_api.app import create_app
from cytellect_api.app_update import Installation, Relaunch, UpdateRefused, UpdateService
from cytellect_api.config import Settings
from fastapi.testclient import TestClient

INSTALLER = b"generated installer bytes for the update test\n"
DIGEST = hashlib.sha256(INSTALLER).hexdigest()


def make_app(root: Path, version: str) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "setup-root.json").write_text(json.dumps(app_update.ROOT_MARKER), encoding="utf-8")
    app = root / "apps" / f"{version}-{'a' * 12}"
    app.mkdir(parents=True)
    (app / "local-release.json").write_text(json.dumps({"version": version}), encoding="utf-8")
    (app / "setup-complete.json").write_text(json.dumps({"version": version, "app": str(app),
                                                         "fiji": str(root / "runtimes/fiji")}), encoding="utf-8")
    return app


def installation(tmp_path: Path, version="0.1.0-local.21") -> Installation:
    item = app_update.read_installation(make_app(tmp_path, version))
    assert item is not None
    return item


def release(version, *, draft=False, installer=True, checksum=True, digest=None, size=None):
    assets = []
    if installer:
        assets.append({"name": f"Cytellect-Setup-{version}.exe", "size": size,
                       "browser_download_url": f"https://github.com/genellect/cytellect/releases/download/v{version}/x.exe",
                       **({"digest": digest} if digest else {})})
    if checksum:
        assets.append({"name": f"Cytellect-Setup-{version}.exe.sha256",
                       "browser_download_url": f"https://github.com/genellect/cytellect/releases/download/v{version}/x.sha256"})
    return {"tag_name": f"v{version}", "draft": draft, "html_url": f"https://github.com/genellect/cytellect/releases/tag/v{version}",
            "assets": assets}


class Opener:
    """Serves the checksum and installer bodies that a release would publish."""

    def __init__(self, body=INSTALLER, checksum=None):
        self.body, self.checksum, self.urls = body, checksum or f"{DIGEST}  Cytellect-Setup.exe\n", []

    def __call__(self, url, timeout):
        self.urls.append(url)
        return io.BytesIO(self.checksum.encode() if url.endswith(".sha256") else self.body)


def service(tmp_path, releases, *, opener=None, installer=lambda path, root: 0, spawned=None, stops=None,
            clock=lambda: 1000.0, fetch=None, busy=lambda: False):
    current = installation(tmp_path)
    stops = stops if stops is not None else []
    return UpdateService(current, fetch=fetch or (lambda url: releases), opener=opener or Opener(),
                         installer=installer, spawn=lambda command, cwd: (spawned if spawned is not None else []).append(command),
                         shutdown=lambda: (lambda: stops.append(True)), clock=clock, busy=busy,
                         sleep=lambda seconds: None, background=False)


def test_newest_published_local_release_with_installer_and_checksum_is_chosen():
    releases = [release("0.1.0-local.23", draft=True), release("0.1.0-local.22", checksum=False),
                release("0.1.0-local.9"), release("0.1.0-local.21"), {"tag_name": "v1.0.0", "assets": []},
                "not a release"]
    latest = app_update.latest_release(releases)
    assert latest["version"] == "0.1.0-local.21"  # numeric, not lexical, comparison
    assert latest["notes_url"].endswith("/v0.1.0-local.21")
    assert app_update.latest_release({"message": "rate limited"}) is None
    assert app_update.newer("0.1.0-local.10", "0.1.0-local.9")
    assert not app_update.newer("0.1.0-local.9", "0.1.0-local.9")
    assert not app_update.newer("0.0.0-local.ci", "0.1.0-local.1") and not app_update.newer(None, "0.1.0-local.1")


def test_status_reports_the_contract_fields_and_caches_the_check(tmp_path):
    calls = []
    now = [1000.0]
    updater = service(tmp_path, [], fetch=lambda url: calls.append(url) or [release("0.1.0-local.22")],
                      clock=lambda: now[0])
    status = updater.status()
    assert status == {"current": "0.1.0-local.21", "latest": "0.1.0-local.22", "available": True,
                      "notes_url": "https://github.com/genellect/cytellect/releases/tag/v0.1.0-local.22",
                      "state": "idle", "error": None}
    assert calls == [app_update.RELEASES_URL]
    now[0] += 60
    updater.status()
    assert len(calls) == 1  # cached
    now[0] += app_update.CHECK_SECONDS
    updater.status()
    assert len(calls) == 2


def test_offline_check_never_raises_and_keeps_the_last_known_release(tmp_path):
    now = [1000.0]
    answers = [[release("0.1.0-local.22")]]

    def fetch(url):
        if answers:
            return answers.pop()
        raise OSError("offline")

    updater = service(tmp_path, [], fetch=fetch, clock=lambda: now[0])
    assert updater.status()["available"] is True
    now[0] += app_update.CHECK_SECONDS + 1
    status = updater.status()
    assert status["latest"] == "0.1.0-local.22" and status["available"] is True
    # A fresh installation without any successful check stays quiet when offline.
    fresh = UpdateService(installation(tmp_path / "fresh"), fetch=fetch, clock=lambda: now[0])
    assert fresh.status() == {"current": "0.1.0-local.21", "latest": None, "available": False,
                              "notes_url": None, "state": "idle", "error": None}


def test_development_and_hosted_copies_report_unsupported(tmp_path):
    updater = UpdateService(None)
    assert updater.status()["state"] == "unsupported" and updater.status()["available"] is False
    with pytest.raises(UpdateRefused, match="update_unsupported"):
        updater.start()
    assert app_update.current_installation(tmp_path / "a/b/c/d/e/module.py") is None


@pytest.mark.parametrize("opener,code", [
    (Opener(body=b"tampered installer"), "update_installer_hash_mismatch"),
    (Opener(checksum="not-a-digest\n"), "update_checksum_invalid"),
])
def test_unverified_download_never_runs_the_installer(tmp_path, opener, code):
    ran = []
    updater = service(tmp_path, [release("0.1.0-local.22")], opener=opener,
                      installer=lambda path, root: ran.append(path) or 0)
    updater.start()
    assert ran == []
    assert updater.status()["state"] == "failed" and updater.status()["error"] == code


def test_release_digest_must_agree_with_the_published_checksum(tmp_path):
    ran = []
    updater = service(tmp_path, [release("0.1.0-local.22", digest="sha256:" + "0" * 64)],
                      installer=lambda path, root: ran.append(path) or 0)
    updater.start()
    assert ran == [] and updater.status()["error"] == "update_checksum_mismatch"


def test_failed_installer_keeps_the_current_version_running(tmp_path):
    spawned, stops = [], []
    updater = service(tmp_path, [release("0.1.0-local.22")], installer=lambda path, root: 20,
                      spawned=spawned, stops=stops)
    updater.start()
    status = updater.status()
    assert status["state"] == "failed" and status["error"] == "update_install_failed"
    assert spawned == [] and stops == []  # no switch, no shutdown
    assert not list((tmp_path / "updates").rglob("*.exe"))


def test_verified_installation_switches_through_the_relauncher(tmp_path):
    spawned, stops, ran = [], [], []

    def install(path, root):
        assert hashlib.sha256(path.read_bytes()).hexdigest() == DIGEST
        ran.append(root)
        make_app(root, "0.1.0-local.22")
        return 0

    updater = service(tmp_path, [release("0.1.0-local.22", size=len(INSTALLER))], installer=install,
                      spawned=spawned, stops=stops)
    assert updater.start()["state"] == "restarting"
    assert ran == [tmp_path] and stops == [True]
    assert spawned and spawned[0][-5:-2] == ["-m", "cytellect_api.app_update", "relaunch"]
    plan = json.loads((tmp_path / "updates/switch.json").read_text())
    assert plan["previous"]["version"] == "0.1.0-local.21" and plan["target"]["version"] == "0.1.0-local.22"
    with pytest.raises(UpdateRefused, match="update_not_available"):
        service(tmp_path / "other", []).start()


def test_concurrent_update_is_refused(tmp_path):
    updater = service(tmp_path, [release("0.1.0-local.22")])

    class Alive:
        def is_alive(self):
            return True

    updater.worker = Alive()  # type: ignore[assignment]
    with pytest.raises(UpdateRefused, match="update_in_progress"):
        updater.start()


def test_interrupted_update_is_reported_without_a_switch(tmp_path):
    current = installation(tmp_path)
    app_update.write_json(current.updates / "state.json", {"state": "downloading", "version": "0.1.0-local.22"})
    status = UpdateService(current, fetch=lambda url: []).status()
    assert status["state"] == "failed" and status["error"] == "update_interrupted"


def test_redirects_are_limited_to_github_release_hosts():
    assert app_update.allowed_download("https://release-assets.githubusercontent.com/x")
    for url in ("http://github.com/x", "https://evil.example/x", "https://github.com:444/x", "file:///c:/x"):
        with pytest.raises(UpdateRefused):
            app_update.allowed_download(url)


def database(path: Path, value: str) -> None:
    # "with connection" only commits; closing() releases the file, which Windows needs
    # before the file can be removed or replaced.
    path.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(path)) as connection, connection:
        connection.execute("create table if not exists marker (value text)")
        connection.execute("delete from marker")
        connection.execute("insert into marker values (?)", (value,))


def marker(path: Path) -> str:
    with contextlib.closing(sqlite3.connect(path)) as connection:
        return connection.execute("select value from marker").fetchone()[0]


@pytest.fixture
def windows_file_locks(monkeypatch):
    """Refuse, as Windows does, to remove or replace a file that an SQLite connection still holds.

    On Linux an open file can be unlinked, so an unclosed connection would go unnoticed.
    """
    opened: list[tuple[Path, sqlite3.Connection]] = []
    connect = sqlite3.connect

    def tracked(database, *args, **kwargs):
        connection = connect(database, *args, **kwargs)
        opened.append((Path(database).resolve(), connection))
        return connection

    def held(path) -> bool:
        target = Path(path).resolve()
        for name, connection in opened:
            if name != target:
                continue
            try:
                connection.total_changes
            except sqlite3.ProgrammingError:
                continue  # closed
            return True
        return False

    def guard(original):
        def checked(self, *args, **kwargs):
            if held(self) or (args and isinstance(args[0], (str, os.PathLike)) and held(args[0])):
                raise PermissionError(32, "The process cannot access the file because it is being used by another process", str(self))
            return original(self, *args, **kwargs)
        return checked

    replace = os.replace

    def checked_replace(source, target, *args, **kwargs):
        if held(source) or held(target):
            raise PermissionError(32, "The process cannot access the file because it is being used by another process", str(source))
        return replace(source, target, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", tracked)
    monkeypatch.setattr(Path, "unlink", guard(Path.unlink))
    monkeypatch.setattr(Path, "replace", guard(Path.replace))
    monkeypatch.setattr(Path, "rename", guard(Path.rename))
    monkeypatch.setattr(os, "replace", checked_replace)
    return held


def switch_plan(root: Path, port: int = 8765) -> Path:
    previous = installation(root, "0.1.0-local.21")
    target = app_update.read_installation(make_app(root, "0.1.0-local.22"))
    assert target is not None
    plan = root / "updates/switch.json"
    app_update.write_json(plan, {"schema": "cytellect-update-switch/1", "root": str(root), "port": port,
                                 "wait_pid": 1, "wait_created": 1.0,
                                 "previous": previous.record(), "target": target.record()})
    return plan


class Effects:
    """Records the relauncher's side effects; any step can be made to fail."""

    def __init__(self, *, exits=True, healthy=False, fail=(), migrate=None, previous_alive=False, killable=True):
        self.exits, self.is_healthy, self.fail, self.migrate = exits, healthy, set(fail), migrate
        self.previous_alive, self.killable = previous_alive, killable
        self.started, self.stopped, self.shortcuts_restored, self.copies = [], [], [], []
        self.exited, self.killed, self.restores = [], [], 0
        self.commands, self.checked_ports = [], []

    def relaunch(self):
        def start(command, cwd):
            self.started.append(command[0])
            self.commands.append(command)
            if "start" in self.fail and len(self.started) == 1:
                raise OSError("synthetic start failure")
            if "0.1.0-local.22" in command[0] and self.migrate:
                self.migrate()
            return f"process-{len(self.started)}"

        def copy(source, target):
            self.copies.append((source.name, target.name))
            restoring = target.name == "cytellect.sqlite"
            if restoring:
                self.restores += 1
            if (("snapshot" in self.fail and not restoring) or ("restore" in self.fail and restoring)
                    or ("restore_once" in self.fail and restoring and self.restores == 1)):
                raise sqlite3.OperationalError("synthetic database lock")
            app_update.database_copy(source, target)

        def kill(pid, created):
            self.killed.append(pid)
            if self.killable:
                self.previous_alive = False

        def stop(process):
            self.stopped.append(process)
            if "stop" in self.fail:
                raise OSError("synthetic stop failure")

        def shortcuts(item):
            self.shortcuts_restored.append(item.version)
            if "shortcuts" in self.fail:
                raise OSError("synthetic shortcut failure")

        return Relaunch(wait=lambda pid, created: self.exits, start=start,
                        healthy=lambda port, version, process: (self.checked_ports.append(port) or self.is_healthy)
                        and version == "0.1.0-local.22",
                        stop=stop, exited=self.exited.append, shortcuts=shortcuts, copy=copy,
                        alive=lambda pid, created: self.previous_alive, kill=kill, pause=lambda seconds: None)


def state_of(root: Path) -> dict:
    return json.loads((root / "updates/state.json").read_text())


def test_relaunch_success_records_update_and_keeps_no_database_copy(tmp_path, windows_file_locks):
    plan = switch_plan(tmp_path)
    database(tmp_path / "data/cytellect.sqlite", "before")
    effects = Effects(healthy=True)
    assert app_update.relaunch(plan, effects.relaunch()) == "updated"
    assert len(effects.started) == 1 and "0.1.0-local.22" in effects.started[0]
    assert effects.stopped == [] and effects.shortcuts_restored == []
    assert not list((tmp_path / "updates/rollback").glob("*.sqlite"))
    assert state_of(tmp_path)["state"] == "updated" and state_of(tmp_path)["previous"] == "0.1.0-local.21"


def test_the_new_and_the_previous_version_start_on_the_launcher_port(tmp_path):
    """Started with --port, both the switch and the return use that port; the shortcut keeps 8765."""
    plan = switch_plan(tmp_path, port=8791)
    effects = Effects()
    assert app_update.relaunch(plan, effects.relaunch()) == "rolled_back"
    assert effects.checked_ports == [8791]
    assert [command[-2:] for command in effects.commands] == [["--port", "8791"], ["--port", "8791"]]
    assert "0.1.0-local.22" in effects.commands[0][0] and "0.1.0-local.21" in effects.commands[1][0]
    previous = app_update.read_installation(tmp_path / "apps" / f"0.1.0-local.21-{'a' * 12}")
    assert previous is not None and "--port" not in previous.launch()  # the shortcut's command
    plan = switch_plan(tmp_path / "updated", port=8792)
    effects = Effects(healthy=True)
    assert app_update.relaunch(plan, effects.relaunch()) == "updated"
    assert effects.checked_ports == [8792] and effects.commands[0][-2:] == ["--port", "8792"]


def test_a_plan_with_an_impossible_port_is_refused(tmp_path):
    plan = switch_plan(tmp_path, port=0)
    effects = Effects(healthy=True)
    assert app_update.relaunch(plan, effects.relaunch()) == "failed"
    assert effects.commands == [] and state_of(tmp_path)["error"] == "update_switch_invalid"


def test_new_version_that_does_not_start_falls_back_to_the_previous_version(tmp_path, windows_file_locks):
    plan = switch_plan(tmp_path)
    data = tmp_path / "data/cytellect.sqlite"
    database(data, "before update")
    effects = Effects(migrate=lambda: database(data, "migrated by the failed version"))
    assert app_update.relaunch(plan, effects.relaunch()) == "rolled_back"
    assert effects.stopped == ["process-1"] and effects.shortcuts_restored == ["0.1.0-local.21"]
    assert "0.1.0-local.22" in effects.started[0] and "0.1.0-local.21" in effects.started[1]
    assert marker(data) == "before update"  # the exact pre-update database is back
    assert not list((tmp_path / "updates/rollback").glob("*.sqlite"))
    assert state_of(tmp_path)["error"] == "update_new_version_failed_to_start"
    # The previous version then reports the fallback to the workspace banner.
    previous = app_update.read_installation(tmp_path / "apps" / f"0.1.0-local.21-{'a' * 12}")
    assert UpdateService(previous, fetch=lambda url: []).status()["state"] == "rolled_back"


@pytest.mark.parametrize("fail,error,kept", [
    ({"stop"}, "update_new_version_failed_to_start", False),       # stopping the new version fails
    ({"restore_once"}, "update_new_version_failed_to_start", False),  # a lock that clears on retry
    ({"restore"}, "update_new_version_failed_to_start", True),     # the database file stays locked
    ({"shortcuts"}, "update_new_version_failed_to_start", False),  # the shortcut cannot be rewritten
    ({"start"}, "update_switch_failed", False),                    # the new version cannot be started
    ({"snapshot"}, "update_database_copy_failed", False),          # no copy, so the new version never runs
    ({"stop", "restore", "shortcuts"}, "update_new_version_failed_to_start", True),
])
def test_every_failed_switch_restores_shortcuts_and_starts_the_previous_version(tmp_path, fail, error, kept):
    plan = switch_plan(tmp_path)
    data = tmp_path / "data/cytellect.sqlite"
    database(data, "before update")
    effects = Effects(fail=fail, migrate=lambda: database(data, "migrated"))
    assert app_update.relaunch(plan, effects.relaunch()) == "rolled_back"
    assert effects.shortcuts_restored == ["0.1.0-local.21"]
    assert "0.1.0-local.21" in effects.started[-1]
    state = state_of(tmp_path)
    assert state["state"] == "rolled_back" and state["error"] == error
    snapshots = list((tmp_path / "updates/rollback").glob("*.sqlite"))
    # A copy that could not be restored stays for recovery; otherwise none is left.
    assert bool(snapshots) is kept
    if kept:
        # The previous version finishes the restore at its start, before opening the database.
        assert "update_database_restore_failed" in state["errors"] and marker(snapshots[0]) == "before update"
        assert json.loads((tmp_path / "updates/rollback/pending.json").read_text())["version"] == "0.1.0-local.21"
        assert effects.restores == app_update.RESTORE_ATTEMPTS
    else:
        assert marker(data) == "before update"
        assert not (tmp_path / "updates/rollback/pending.json").exists()
    if effects.stopped:
        assert effects.exited == effects.stopped  # waited for the stopped version to release its files
    if "snapshot" in fail:
        assert len(effects.started) == 1  # only the previous version started


def test_previous_launcher_that_does_not_exit_is_stopped_and_started_again(tmp_path):
    plan = switch_plan(tmp_path)
    effects = Effects(exits=False, previous_alive=True)
    assert app_update.relaunch(plan, effects.relaunch()) == "rolled_back"
    assert effects.killed and len(effects.started) == 1 and "0.1.0-local.21" in effects.started[0]
    assert effects.shortcuts_restored == ["0.1.0-local.21"]
    assert state_of(tmp_path)["error"] == "update_previous_did_not_exit"


def test_a_previous_launcher_that_cannot_be_stopped_is_left_running(tmp_path):
    plan = switch_plan(tmp_path)
    effects = Effects(exits=False, previous_alive=True, killable=False)
    assert app_update.relaunch(plan, effects.relaunch()) == "rolled_back"
    assert effects.started == []  # it is still the previous version, still running
    assert effects.shortcuts_restored == ["0.1.0-local.21"]


def test_the_previous_version_restores_a_pending_database_before_opening_it(tmp_path, windows_file_locks):
    previous = installation(tmp_path, "0.1.0-local.21")
    data = tmp_path / "data/cytellect.sqlite"
    database(data, "migrated by the failed version")
    database(tmp_path / "updates/rollback/0.1.0-local.21.sqlite", "before update")
    app_update.write_json(tmp_path / "updates/rollback/pending.json",
                          {"schema": "cytellect-update-restore/1", "version": "0.1.0-local.21"})
    newer = app_update.read_installation(make_app(tmp_path, "0.1.0-local.22"))
    assert app_update.restore_pending_database(tmp_path / "data", newer) is False  # not its database
    assert marker(data) == "migrated by the failed version"
    assert app_update.restore_pending_database(tmp_path / "data", previous) is True
    assert marker(data) == "before update"
    assert not list((tmp_path / "updates/rollback").iterdir())
    assert app_update.restore_pending_database(tmp_path / "data", previous) is False  # nothing pending


def test_a_pending_restore_that_still_fails_stops_the_start(tmp_path, monkeypatch):
    previous = installation(tmp_path, "0.1.0-local.21")
    database(tmp_path / "updates/rollback/0.1.0-local.21.sqlite", "before update")
    app_update.write_json(tmp_path / "updates/rollback/pending.json", {"version": "0.1.0-local.21"})

    def locked(source, target):
        raise sqlite3.OperationalError("synthetic database lock")

    monkeypatch.setattr(app_update, "database_copy", locked)
    with pytest.raises(RuntimeError, match="update_database_restore_pending"):
        app_update.restore_pending_database(tmp_path / "data", previous)
    assert (tmp_path / "updates/rollback/pending.json").exists()  # kept for the next start


def test_new_work_is_refused_while_the_launcher_stops_for_the_switch(tmp_path):
    client, headers = local_client(tmp_path)
    holder = {"service": client.app.state.update_service()}
    holder["service"].switching = True
    refused = client.post("/v1/workspaces", json={"title": "late"}, headers=headers)
    assert refused.status_code == 409 and refused.json() == {"detail": "update_switching"}
    assert client.get("/v1/app/update").status_code == 200
    holder["service"].switching = False
    assert client.post("/v1/workspaces", json={"title": "after"}, headers=headers).status_code == 201


def test_a_deferred_switch_reports_updated_once_the_new_version_runs(tmp_path):
    current = installation(tmp_path, "0.1.0-local.22")
    app_update.write_json(current.updates / "state.json",
                          {"state": "installed", "version": "0.1.0-local.22", "error": "update_jobs_running"})
    status = UpdateService(current, fetch=lambda url: []).status()
    assert status["state"] == "updated" and status["error"] is None
    assert json.loads((current.updates / "state.json").read_text())["state"] == "updated"


def test_running_analyses_block_the_update_and_a_late_one_defers_the_switch(tmp_path):
    with pytest.raises(UpdateRefused, match="update_jobs_running"):
        service(tmp_path, [release("0.1.0-local.22")], busy=lambda: True).start()
    spawned, stops, calls = [], [], []
    clock = [1000.0]

    def busy():
        calls.append(1)
        clock[0] += 100
        return len(calls) > 1  # free when requested, then an analysis starts during installation

    def install(path, root):
        make_app(root, "0.1.0-local.22")
        return 0

    updater = UpdateService(installation(tmp_path / "late"), fetch=lambda url: [release("0.1.0-local.22")],
                            opener=Opener(), installer=install, spawn=lambda c, d: spawned.append(c),
                            shutdown=lambda: (lambda: stops.append(True)), busy=busy, clock=lambda: clock[0],
                            sleep=lambda seconds: None, background=False)
    status = updater.start()
    assert spawned == [] and stops == []  # never stops a running analysis
    assert status["state"] == "installed" and status["error"] == "update_jobs_running"


def test_downloads_are_removed_after_installation_and_before_a_new_attempt(tmp_path):
    seen = []
    updater = service(tmp_path, [release("0.1.0-local.22")],
                      installer=lambda path, root: seen.append(path.is_file()) or 20)
    current = updater.installation
    stale = current.updates / "0.1.0-local.20"
    stale.mkdir(parents=True)
    (stale / "Cytellect-Setup-0.1.0-local.20.exe.partial").write_bytes(b"old partial")
    updater.start()
    assert seen == [True] and not stale.exists()
    assert sorted(path.name for path in current.updates.iterdir()) == ["latest.json", "state.json"]


def test_a_hung_installer_is_stopped_with_its_children(tmp_path, monkeypatch):
    stopped = []

    class Hung:
        pid = 1234

        def wait(self, timeout):
            raise app_update.subprocess.TimeoutExpired("setup", timeout)

    monkeypatch.setattr(app_update.subprocess, "Popen", lambda *args, **kwargs: Hung())
    monkeypatch.setattr(app_update, "stop_tree", stopped.append)
    assert app_update.run_installer(tmp_path / "setup.exe", tmp_path) == -1
    assert len(stopped) == 1


def test_release_notes_link_only_to_this_repository():
    foreign = release("0.1.0-local.22")
    foreign["html_url"] = "https://example.invalid/phishing"
    assert app_update.latest_release([foreign])["notes_url"] is None


def local_client(tmp_path, origin="http://127.0.0.1:8765", secure=False):
    settings = Settings(tmp_path / "data", app_origin=origin, secure_cookies=secure)
    app = create_app(settings)
    client = TestClient(app)
    token = app.state.store.invite()
    headers = {"origin": origin, "x-cytellect-request": "1"}
    assert client.post("/v1/invitations/redeem", json={"token": token}, headers=headers).status_code == 200
    return client, headers


def test_routes_exist_only_in_the_loopback_application_and_require_a_session(tmp_path):
    client, headers = local_client(tmp_path)
    status = client.get("/v1/app/update")
    assert status.status_code == 200 and status.json()["state"] == "unsupported"  # a checkout, not an installation
    assert client.post("/v1/app/update", headers=headers).json() == {"detail": "update_unsupported"}
    assert TestClient(client.app).get("/v1/app/update").status_code == 401
    hosted, _ = local_client(tmp_path / "hosted", origin="https://cytellect.example", secure=True)
    assert hosted.get("/v1/app/update").status_code == 404
    assert "/v1/app/update" not in json.dumps(client.app.openapi())  # the public contract is unchanged


def test_the_relauncher_entry_runs_the_importable_module(monkeypatch):
    """`python -m cytellect_api.app_update` must use cytellect_api.app_update itself.

    Run as __main__, the file would otherwise be a second copy whose classes nothing else
    sees: the CI hook's failing start (and any other patch of the module) would not apply.
    """
    import runpy
    import warnings

    seen = []
    monkeypatch.setattr(app_update, "relaunch", lambda plan: seen.append(plan) or "updated")
    monkeypatch.setattr("sys.argv", ["app_update", "relaunch", "--plan", "switch.json"])
    with warnings.catch_warnings(), pytest.raises(SystemExit) as stopped:
        warnings.simplefilter("ignore", RuntimeWarning)  # runpy: module already imported
        runpy.run_module("cytellect_api.app_update", run_name="__main__")
    assert stopped.value.code == 0 and seen == [Path("switch.json")]


def test_the_ci_update_hook_makes_only_the_named_version_fail_to_start(tmp_path, monkeypatch):
    import importlib.util

    hook = Path(__file__).resolve().parents[1] / "packaging/windows/update-test/cytellect_ci_update_hook.py"
    # monkeypatch restores what the hook replaces.
    monkeypatch.setattr(app_update.Installation, "launch", app_update.Installation.launch)
    monkeypatch.setattr(app_update, "allowed_download", app_update.allowed_download)
    monkeypatch.setattr(app_update, "RELEASES_URL", app_update.RELEASES_URL)
    monkeypatch.delenv("CYTELLECT_TEST_RELEASES", raising=False)
    monkeypatch.setenv("CYTELLECT_TEST_FAIL_VERSION", "0.1.0-local.22")
    spec = importlib.util.spec_from_file_location("cytellect_ci_update_hook_test", hook)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    failing = installation(tmp_path / "new", "0.1.0-local.22")
    assert failing.launch()[1:] == ["-E", "-c", "raise SystemExit(3)"]
    assert failing.launch(8791)[1:] == ["-E", "-c", "raise SystemExit(3)"]  # the relauncher passes its port
    assert installation(tmp_path / "old").launch()[1:5] == ["-B", "-E", "-m", "cytellect_api.local"]


RELAUNCHER = """
import json, sys
from pathlib import Path
import psutil
from cytellect_api import app_update

pid, plan_path, result = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
plan = json.loads(plan_path.read_text(encoding="utf-8"))
plan.update(wait_pid=pid, wait_created=psutil.Process(pid).create_time())
app_update.write_json(plan_path, plan)
seen = {"shortcuts": [], "started": []}
# The previous launcher never exits: the real stop (kill_identity, stop_tree) runs on it.
outcome = app_update.relaunch(plan_path, app_update.Relaunch(
    wait=lambda pid, created: False, start=lambda command, cwd: seen["started"].append(command[0]),
    shortcuts=lambda item: seen["shortcuts"].append(item.version), pause=lambda seconds: None))
# Reached only if stopping the previous launcher spared this process (and its ancestors).
result.write_text(json.dumps({"outcome": outcome, **seen}), encoding="utf-8")
"""


def test_stopping_a_previous_launcher_spares_the_relauncher_that_descends_from_it(tmp_path):
    """The relauncher is started by the launcher it may have to stop; it must go on to restore."""
    import subprocess
    import sys
    import time

    plan = switch_plan(tmp_path)
    script, result = tmp_path / "relauncher.py", tmp_path / "result.json"
    script.write_text(RELAUNCHER, encoding="utf-8")
    # A stand-in for the previous launcher: it starts the relauncher (in its own session, as
    # detach does) and then ignores every request to stop until it is killed.
    launcher = subprocess.Popen([sys.executable, "-c", (
        "import os, subprocess, sys, time\n"
        f"subprocess.Popen([sys.executable, {str(script)!r}, str(os.getpid()), {str(plan)!r}, {str(result)!r}], "
        "start_new_session=os.name != 'nt')\n"
        "time.sleep(120)\n")])
    try:
        deadline = time.monotonic() + 60
        while not result.exists() and time.monotonic() < deadline:
            time.sleep(0.2)
        assert result.exists(), "the relauncher was stopped together with the previous launcher"
        seen = json.loads(result.read_text(encoding="utf-8"))
        assert seen["outcome"] == "rolled_back" and seen["shortcuts"] == ["0.1.0-local.21"]
        assert len(seen["started"]) == 1 and "0.1.0-local.21" in seen["started"][0]  # the previous version again
        assert state_of(tmp_path)["error"] == "update_previous_did_not_exit"
        assert launcher.wait(timeout=10) != 0  # the previous launcher itself was stopped
    finally:
        if launcher.poll() is None:
            launcher.kill()


def test_stop_tree_never_stops_this_process():
    import psutil

    class Me:
        pid = psutil.Process().pid

    app_update.stop_tree(Me())  # stopping this very process is refused; the test goes on

"""In-app update of the Windows installation with fake GitHub responses (I7).

No network request, installer or launcher runs: every side effect is a test double,
and the installation tree is a generated scratch layout without research data.
"""
import hashlib
import io
import json
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
            clock=lambda: 1000.0, fetch=None):
    current = installation(tmp_path)
    stops = stops if stops is not None else []
    return UpdateService(current, fetch=fetch or (lambda url: releases), opener=opener or Opener(),
                         installer=installer, spawn=lambda command, cwd: (spawned if spawned is not None else []).append(command),
                         shutdown=lambda: (lambda: stops.append(True)), clock=clock, background=False)


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
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("create table if not exists marker (value text)")
        connection.execute("delete from marker")
        connection.execute("insert into marker values (?)", (value,))


def marker(path: Path) -> str:
    with sqlite3.connect(path) as connection:
        return connection.execute("select value from marker").fetchone()[0]


def switch_plan(root: Path) -> Path:
    previous = installation(root, "0.1.0-local.21")
    target = app_update.read_installation(make_app(root, "0.1.0-local.22"))
    assert target is not None
    plan = root / "updates/switch.json"
    app_update.write_json(plan, {"schema": "cytellect-update-switch/1", "root": str(root), "port": 8765,
                                 "wait_pid": 1, "wait_created": 1.0,
                                 "previous": previous.record(), "target": target.record()})
    return plan


def test_relaunch_success_records_update_and_keeps_no_database_copy(tmp_path):
    plan = switch_plan(tmp_path)
    database(tmp_path / "data/cytellect.sqlite", "before")
    started = []
    effects = Relaunch(wait=lambda pid, created: True, start=lambda command, cwd: started.append(command) or "new",
                       healthy=lambda port, process: True, stop=lambda process: pytest.fail("no stop"),
                       shortcuts=lambda item: pytest.fail("no shortcut change"))
    assert app_update.relaunch(plan, effects) == "updated"
    assert len(started) == 1 and "0.1.0-local.22" in started[0][0]
    assert not list((tmp_path / "updates/rollback").glob("*.sqlite"))
    state = json.loads((tmp_path / "updates/state.json").read_text())
    assert state["state"] == "updated" and state["previous"] == "0.1.0-local.21"


def test_new_version_that_does_not_start_falls_back_to_the_previous_version(tmp_path):
    plan = switch_plan(tmp_path)
    data = tmp_path / "data/cytellect.sqlite"
    database(data, "before update")
    started, stopped, shortcuts = [], [], []

    def start(command, cwd):
        started.append(command[0])
        if len(started) == 1:
            database(data, "migrated by the failed version")
        return f"process-{len(started)}"

    effects = Relaunch(wait=lambda pid, created: True, start=start, healthy=lambda port, process: False,
                       stop=stopped.append, shortcuts=lambda item: shortcuts.append(item.version))
    assert app_update.relaunch(plan, effects) == "rolled_back"
    assert stopped == ["process-1"] and shortcuts == ["0.1.0-local.21"]
    assert "0.1.0-local.22" in started[0] and "0.1.0-local.21" in started[1]
    assert marker(data) == "before update"  # the exact pre-update database is back
    assert not list((tmp_path / "updates/rollback").glob("*.sqlite"))
    state = json.loads((tmp_path / "updates/state.json").read_text())
    assert state["state"] == "rolled_back" and state["error"] == "update_new_version_failed_to_start"
    # The previous version then reports the fallback to the workspace banner.
    previous = app_update.read_installation(tmp_path / "apps" / f"0.1.0-local.21-{'a' * 12}")
    assert UpdateService(previous, fetch=lambda url: []).status()["state"] == "rolled_back"


def test_relaunch_waits_for_the_previous_launcher(tmp_path):
    plan = switch_plan(tmp_path)
    effects = Relaunch(wait=lambda pid, created: False, start=lambda command, cwd: pytest.fail("must not start"))
    assert app_update.relaunch(plan, effects) == "failed"


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

"""scripts/dev.py doctor/serve: readiness probes never spend money or leak credentials."""
import http.server
import sys
import threading
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
from dev import (  # noqa: E402
    API_ORIGIN,
    APP_ORIGIN,
    MODAL_CELLPOSE_URL,
    cellpose_state,
    cloud_env,
    probe,
    proposal_state,
    serve_env,
)


def serve_once(handler: type[http.server.BaseHTTPRequestHandler]) -> tuple[http.server.HTTPServer, str]:
    server = http.server.HTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}"


def test_an_empty_proposal_request_proves_the_token_only_when_the_service_rejects_its_body():
    assert proposal_state(400, "request_invalid")[0]
    assert not proposal_state(401, "unauthorized")[0]
    assert not proposal_state(503, "proposal_service_disabled")[0]
    assert "budget_reconciliation_required" in proposal_state(503, "budget_reconciliation_required")[1]
    assert not proposal_state(200, "")[0]
    assert not proposal_state(0, "unreachable")[0]


def test_cellpose_health_distinguishes_a_rejected_key_from_a_starting_server():
    assert cellpose_state(200)[0]
    assert "rejected" in cellpose_state(401)[1]
    assert "capacity" in cellpose_state(503)[1]


def test_probe_reads_the_error_code_without_following_redirects():
    seen: list[str | None] = []

    class Target(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            seen.append(self.headers.get("Authorization"))
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    target, target_url = serve_once(Target)

    class Redirect(http.server.BaseHTTPRequestHandler):
        def do_POST(self):  # noqa: N802
            # Read the request body first: closing with unread bytes resets the connection on
            # Windows, and the client then sees no response at all.
            self.rfile.read(int(self.headers.get("Content-Length", 0)))
            if self.path == "/moved":
                self.send_response(307)
                self.send_header("Location", target_url + "/v1/proposals")
                self.end_headers()
                return
            body = b'{"code":"request_invalid"}'
            self.send_response(400)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    source, source_url = serve_once(Redirect)
    try:
        headers = {"Authorization": "Bearer device-token-for-test"}
        assert probe(urllib.request.Request(source_url + "/v1/proposals", data=b"{}", headers=headers), 5) == (
            400, "request_invalid")
        status, _ = probe(urllib.request.Request(source_url + "/moved", data=b"{}", headers=headers), 5)
        assert status == 307
        assert seen == []
    finally:
        source.shutdown()
        target.shutdown()
    assert probe(urllib.request.Request(source_url + "/v1/proposals", data=b"{}"), 2) == (0, "unreachable")


def test_serve_uses_loopback_origins_and_passes_cloud_settings_through(tmp_path):
    env = serve_env({"CYTELLECT_CELLPOSE_REMOTE_URL": "https://gpu.example", "CYTELLECT_PROPOSAL_URL": "https://p.example",
                     "CYTELLECT_SECURE_COOKIES": "true"}, tmp_path)
    assert env["CYTELLECT_DATA_DIR"] == str(tmp_path)
    assert env["CYTELLECT_APP_ORIGIN"] == APP_ORIGIN == "http://localhost:3000"
    assert env["NEXT_PUBLIC_API_ORIGIN"] == API_ORIGIN == "http://localhost:8000"
    assert env["CYTELLECT_SECURE_COOKIES"] == "false"
    assert env["CYTELLECT_CELLPOSE_REMOTE_URL"] == "https://gpu.example"
    assert env["CYTELLECT_PROPOSAL_URL"] == "https://p.example"


def test_a_modal_proxy_token_stored_in_two_parts_becomes_the_engine_bearer_value():
    env = cloud_env({"CYTELLECT_MODAL_PROXY_KEY": " wk-abc ", "CYTELLECT_MODAL_PROXY_SECRET": "ws-def"})
    assert env["CYTELLECT_CELLPOSE_REMOTE_TOKEN"] == "wk-abc.ws-def"
    assert env["CYTELLECT_CELLPOSE_REMOTE_URL"] == MODAL_CELLPOSE_URL
    explicit = cloud_env({"CYTELLECT_MODAL_PROXY_KEY": "wk-abc", "CYTELLECT_MODAL_PROXY_SECRET": "ws-def",
                          "CYTELLECT_CELLPOSE_REMOTE_TOKEN": "other", "CYTELLECT_CELLPOSE_REMOTE_URL": "https://x.example"})
    assert explicit["CYTELLECT_CELLPOSE_REMOTE_TOKEN"] == "other"
    assert explicit["CYTELLECT_CELLPOSE_REMOTE_URL"] == "https://x.example"
    assert "CYTELLECT_CELLPOSE_REMOTE_TOKEN" not in cloud_env({"CYTELLECT_MODAL_PROXY_KEY": "wk-abc"})
    # An env.sh that already joined the token still gets the deployed server as its default.
    joined = cloud_env({"CYTELLECT_MODAL_PROXY_KEY": "wk-abc", "CYTELLECT_CELLPOSE_REMOTE_TOKEN": "wk-abc.ws-def"})
    assert joined["CYTELLECT_CELLPOSE_REMOTE_URL"] == MODAL_CELLPOSE_URL


def test_fiji_falls_back_to_the_linux_setup_location(tmp_path, monkeypatch):
    import dev

    monkeypatch.delenv("CYTELLECT_FIJI_EXECUTABLE", raising=False)
    monkeypatch.setattr(dev, "DEV_RUNTIME", tmp_path)
    assert dev.fiji_path() == ""
    (tmp_path / "fiji").mkdir()
    assert dev.fiji_path() == str(tmp_path / "fiji")
    monkeypatch.setenv("CYTELLECT_FIJI_EXECUTABLE", "/explicit/fiji")
    assert dev.fiji_path() == "/explicit/fiji"


def test_require_cloud_fails_when_a_cloud_service_is_not_configured(monkeypatch, capsys):
    import argparse

    import dev
    import pytest

    for name in ("CYTELLECT_CELLPOSE_REMOTE_URL", "CYTELLECT_CELLPOSE_REMOTE_TOKEN", "CYTELLECT_MODAL_PROXY_KEY",
                 "CYTELLECT_MODAL_PROXY_SECRET", "CYTELLECT_PROPOSAL_URL", "CYTELLECT_PROPOSAL_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(dev, "tool_version", lambda argv: "")  # no tools, so every run exits on them
    for required, state in ((False, "[--]"), (True, "[NG]")):
        with pytest.raises(SystemExit):
            dev.doctor(argparse.Namespace(live=False, require_cloud=required))
        lines = capsys.readouterr().out.splitlines()
        assert f"{state} Cloud GPU (Cellpose): not configured; Cellpose needs this or a CPU runtime (`setup --cellpose`)" in lines
        assert any(line.startswith(f"{state} Analysis proposals (LLM)") for line in lines)


def test_doctor_asks_the_figure_code_for_the_japanese_font(monkeypatch, capsys):
    """Any Japanese font is not enough: only a face the figures select counts (base images carry others)."""
    import argparse

    import dev
    import pytest

    if not sys.platform.startswith("linux"):
        pytest.skip("doctor checks the figure font on Linux")
    calls = []

    def version(argv):
        calls.append(argv)
        return "Noto Sans CJK JP" if "japanese_font" in " ".join(argv) and found else ""

    monkeypatch.setattr(dev, "tool_version", version)
    for found, line in ((True, "[ok] Japanese figure font: Noto Sans CJK JP"),
                        (False, "[--] Japanese figure font: installed on first use")):
        with pytest.raises(SystemExit):
            dev.doctor(argparse.Namespace(live=False, require_cloud=False))
        assert any(output.startswith(line) for output in capsys.readouterr().out.splitlines())
    assert not any(argv[0] == "fc-list" for argv in calls)


def test_stop_also_ends_descendants_that_outlive_their_leader():
    import os
    import subprocess
    import time

    import dev
    import pytest

    if not sys.platform.startswith("linux"):
        pytest.skip("process groups and /proc")

    def alive(pid: int) -> bool:
        try:
            state = Path(f"/proc/{pid}/stat").read_text().rsplit(")", 1)[1].split()[0]
        except FileNotFoundError:
            return False
        return state != "Z"

    child = "import signal, time; signal.signal(signal.SIGTERM, signal.SIG_IGN); print(flush=True); time.sleep(60)"
    leader = (f"import subprocess, sys; c = subprocess.Popen([sys.executable, '-c', {child!r}], stdout=subprocess.PIPE); "
              "c.stdout.readline(); print(c.pid, flush=True); c.wait()")
    process = subprocess.Popen([sys.executable, "-c", leader], stdout=subprocess.PIPE, text=True, start_new_session=True)
    descendant = int(process.stdout.readline())
    try:
        dev.stop([process], grace=1)
        assert process.returncode is not None
        deadline = time.monotonic() + 5
        while alive(descendant) and time.monotonic() < deadline:
            time.sleep(0.05)
        assert not alive(descendant)
    finally:
        if alive(descendant):
            os.kill(descendant, 9)


def test_cloud_setup_installs_the_versions_the_repository_pins():
    import re

    import dev

    pins = dev.pinned_versions()
    setup = (ROOT / "scripts/linux_setup.sh").read_text()
    assert re.search(r"^node_version=(\d+)\.", setup, re.M).group(1) == pins["node"]
    assert re.search(r"^uv_version=(\S+)", setup, re.M).group(1) == pins["uv"]
    assert "packageManager" in setup  # pnpm comes from package.json, not a second copy


def test_doctor_rejects_a_key_file_other_users_can_read(monkeypatch, capsys, tmp_path):
    import argparse

    import dev
    import pytest

    if sys.platform.startswith("win"):
        pytest.skip("POSIX file modes")
    key_file = tmp_path / "dev.env"
    key_file.write_text("CYTELLECT_PROPOSAL_TOKEN=x\n")
    monkeypatch.setattr(dev, "KEY_FILE", key_file)
    monkeypatch.setattr(dev, "tool_version", lambda argv: "")
    for mode, line in ((0o644, "[NG] Key file: other users can read it"), (0o600, "[ok] Key file: readable only by you")):
        key_file.chmod(mode)
        with pytest.raises(SystemExit):
            dev.doctor(argparse.Namespace(live=False, require_cloud=False))
        output = capsys.readouterr().out
        assert any(entry.startswith(line) for entry in output.splitlines())
        assert "CYTELLECT_PROPOSAL_TOKEN=x" not in output


def test_wsl_checks_name_the_windows_disk_low_memory_and_an_arm_cpu(tmp_path):
    import dev

    release = tmp_path / "osrelease"
    release.write_text("6.6.87.2-microsoft-standard-WSL2\n")
    assert dev.is_wsl(release) and not dev.is_wsl(tmp_path / "missing")
    meminfo = tmp_path / "meminfo"
    meminfo.write_text("MemTotal:        4000000 kB\nMemFree:          100 kB\n")
    states = {name: (state, detail) for state, name, detail in
              dev.wsl_checks("/mnt/c/fiji", Path("/mnt/c/Users/me/data"), meminfo=meminfo, machine="aarch64")}
    assert states["WSL: Linux disk"][0] == "NG" and "/mnt/c/fiji" in states["WSL: Linux disk"][1]
    assert states["WSL: memory and disk"][0] == "!!" and ".wslconfig" in states["WSL: memory and disk"][1]
    assert states["WSL: CPU"][0] == "NG"
    meminfo.write_text("MemTotal:       16000000 kB\n")
    inside = dev.wsl_checks(str(tmp_path / "fiji"), tmp_path / "data", meminfo=meminfo, machine="x86_64")
    assert {name: state for state, name, _ in inside}["WSL: Linux disk"] == "ok"
    assert {name: state for state, name, _ in inside}["WSL: CPU"] == "ok"


def test_e2e_needs_a_running_serve(monkeypatch, tmp_path):
    import argparse

    import dev
    import pytest

    monkeypatch.setattr(dev, "responding", lambda url: False)
    monkeypatch.setattr(dev, "run", lambda *args, **kwargs: pytest.fail("nothing runs without serve"))
    with pytest.raises(SystemExit, match="start `python3 scripts/dev.py serve`"):
        dev.e2e(argparse.Namespace(data_dir=tmp_path / "data", work_dir=tmp_path / "e2e", playwright=[]))


def test_fiji_and_the_figure_font_are_installed_on_first_use(monkeypatch, tmp_path):
    """The base setup leaves Fiji and the font out; `serve`, `check` and `e2e` install them once, when needed."""
    import dev
    import pytest

    commands = []
    monkeypatch.setattr(dev, "run", lambda argv, env=None: commands.append(argv))
    monkeypatch.delenv("CYTELLECT_FIJI_EXECUTABLE", raising=False)
    monkeypatch.setattr(dev, "DEV_RUNTIME", tmp_path)
    assert dev.ensure_fiji() == str(tmp_path / "fiji")
    assert commands == [("uv", "run", "python", "scripts/fiji_setup.py", str(tmp_path / "fiji"))]
    (tmp_path / "fiji").mkdir()
    commands.clear()
    dev.ensure_fiji()
    assert commands == []  # already there: nothing is downloaded again
    monkeypatch.setenv("CYTELLECT_FIJI_EXECUTABLE", str(dev.ROOT / "fiji"))
    with pytest.raises(SystemExit, match="outside the checkout"):
        dev.ensure_fiji()

    if sys.platform.startswith("linux"):
        fonts = iter(["", "Noto Sans CJK JP"])
        monkeypatch.setattr(dev, "figure_font", lambda: next(fonts))
        dev.ensure_figure_font()
        assert commands == [("bash", "scripts/install_figure_font.sh")]

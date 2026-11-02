import hashlib
import json
from pathlib import Path

import pytest
from cytellect_analysis import install_check


def test_failed_installation_check_removes_only_owned_attempt(tmp_path, monkeypatch):
    existing = tmp_path / "preserved.txt"
    existing.write_text("keep")

    def failure(image, detector, output, fiji, **kwargs):
        (kwargs["scratch_root"] / "partial.tif").write_bytes(b"generated incomplete output")
        raise RuntimeError("fiji_execution_failed")

    monkeypatch.setattr(install_check, "detect_nuclei", failure)
    with pytest.raises(RuntimeError, match="fiji_execution_failed"):
        install_check.verify_installation("unused", tmp_path)
    assert list(tmp_path.iterdir()) == [existing]
    assert existing.read_text() == "keep"


def test_bundled_installation_image_matches_registered_public_draq_fixture():
    root = Path(__file__).resolve().parents[1]
    registered = json.loads((root / "fixtures/public/bbbc013/manifest.json").read_text())
    source = registered["images"][0]["channels"]["dapi"]
    assert registered["dataset"] == "BBBC013v1" and source["stain"] == "DRAQ (DNA)"
    assert hashlib.sha256(install_check.FIXTURE.read_bytes()).hexdigest() == source["sha256"]
    assert install_check.FIXTURE_PIXEL_SHA256 == source["pixel_sha256"]
    notice = json.loads(install_check.FIXTURE.with_name("NOTICE.json").read_text())
    assert notice["license"] == "CC-BY-3.0" and notice["sha256"] == source["sha256"]


def test_transient_check_failure_is_retained_when_one_retry_succeeds(tmp_path, monkeypatch):
    calls = []

    def verify(*args):
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("fiji_timeout")
        return {"scope": "unit test of retry control flow only"}

    monkeypatch.setattr(install_check, "verify_installation", verify)
    monkeypatch.setattr(install_check.time, "sleep", lambda seconds: None)
    result = tmp_path / "check.json"
    report = install_check.run_check("unused", tmp_path / "scratch", result)
    assert report["status"] == "passed" and len(calls) == 2
    assert [attempt["status"] for attempt in report["attempts"]] == ["failed", "passed"]
    assert report["attempts"][0]["error_code"] == "fiji_timeout"
    assert report["maximum_seconds"] == 900
    assert json.loads(result.read_text()) == report
    assert not list(tmp_path.glob("check-*.tmp"))


@pytest.mark.parametrize("code", ["installation_arithmetic_check_failed", "installation_pixels_changed",
                                  "windows_application_control_blocked", "installation_fixture_invalid"])
def test_permanent_check_errors_are_never_retried(tmp_path, monkeypatch, code):
    calls = []

    def failure(*args):
        calls.append(1)
        raise RuntimeError(code)

    monkeypatch.setattr(install_check, "verify_installation", failure)
    report = install_check.run_check("unused", tmp_path, tmp_path / "check.json")
    assert report["status"] == "failed" and report["error_code"] == code
    assert len(calls) == 1


def test_unknown_exception_text_never_enters_persistent_report(tmp_path, monkeypatch):
    private = "\\".join(("C:", "Users", "PrivateUser", "study-secret.tif user@example.test token=not-for-logs"))

    def failure(*args):
        raise RuntimeError(private)

    monkeypatch.setattr(install_check, "verify_installation", failure)
    path = tmp_path / "check.json"
    report = install_check.run_check("unused", tmp_path, path)
    assert report["error_code"] == "installation_check_failed"
    assert all(value not in path.read_text() for value in ("PrivateUser", "study-secret", "example.test", "not-for-logs"))


def test_corrupt_fixture_stops_before_engine_or_scratch_attempt(tmp_path, monkeypatch):
    fixture = tmp_path / "bad.tif"
    fixture.write_bytes(b"wrong bytes")
    monkeypatch.setattr(install_check, "FIXTURE", fixture)
    with pytest.raises(RuntimeError, match="installation_fixture_invalid"):
        install_check.verify_installation("unused", tmp_path / "scratch")
    assert not list((tmp_path / "scratch").iterdir())


@pytest.mark.parametrize("compile_seconds,execution_seconds", [(0, 300), (301, 300), (120, 1801), (True, 300)])
def test_invalid_check_budget_never_starts_or_writes_report(tmp_path, monkeypatch, compile_seconds,
                                                          execution_seconds):
    def unexpected(*args):
        raise AssertionError("engine must not start")

    monkeypatch.setattr(install_check, "verify_installation", unexpected)
    with pytest.raises(ValueError, match="installation_timeout_invalid"):
        install_check.run_check("unused", tmp_path, tmp_path / "report.json",
                                compile_seconds=compile_seconds, execution_seconds=execution_seconds)
    assert not (tmp_path / "report.json").exists()

"""Actual Compose merge checks; requires CLI only, never starts containers."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_opt_in_relay_keeps_analysis_offline_and_secret_out_of_configuration(tmp_path):
    docker = shutil.which("docker")
    if not docker:
        if os.environ.get("CYTELLECT_REQUIRE_COMPOSE_TEST") == "1":
            pytest.fail("Docker Compose CLI is required for deployment verification")
        pytest.skip("Docker Compose CLI unavailable; merged deployment not verified")
    try:
        availability = subprocess.run([docker, "compose", "version"], capture_output=True, timeout=30)
    except (OSError, subprocess.TimeoutExpired):
        if os.environ.get("CYTELLECT_REQUIRE_COMPOSE_TEST") == "1":
            pytest.fail("Docker Compose CLI did not respond; deployment verification is required", pytrace=False)
        pytest.skip("Docker Compose CLI did not respond; merged deployment not verified")
    if availability.returncode:
        if os.environ.get("CYTELLECT_REQUIRE_COMPOSE_TEST") == "1":
            pytest.fail("Docker Compose plugin is required for deployment verification")
        pytest.skip("Docker Compose plugin unavailable; merged deployment not verified")
    credential = "public-test-device-token-0123456789"
    secret = tmp_path / "device-token"
    secret.write_text(credential, encoding="ascii")
    env = {**os.environ, "CYTELLECT_RUNTIME_DIR": str(tmp_path / "runtime"),
           "CYTELLECT_PROPOSAL_URL": "https://proposal.example.test",
           "CYTELLECT_PROPOSAL_TOKEN_FILE": str(secret)}
    command = [docker, "compose", "-f", str(ROOT / "compose.yaml")]

    def configuration(extra):
        result = subprocess.run([*command, *extra, "config", "--format", "json"],
                                cwd=ROOT, env=env, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, "Compose merge failed; inspect with dummy credentials only"
        assert credential not in result.stdout
        return json.loads(result.stdout)

    base = configuration([])
    merged = configuration(["-f", str(ROOT / "infra/compose.proposal.yaml")])
    assert set(base["services"]["api"]["networks"]) == {"private"}
    assert base["networks"]["private"]["internal"] is True
    assert "CYTELLECT_PROPOSAL_TOKEN_FILE" not in base["services"]["api"]["environment"]
    api = merged["services"]["api"]
    assert set(api["networks"]) == {"private", "proposal_outbound"}
    assert not merged["networks"]["proposal_outbound"].get("internal", False)
    assert api["environment"]["CYTELLECT_PROPOSAL_TOKEN"] == ""
    assert api["environment"]["CYTELLECT_PROPOSAL_TOKEN_FILE"] == "/run/secrets/proposal_device_token"
    assert len(api["secrets"]) == 1
    assert api["secrets"][0]["source"] == "proposal_device_token"
    assert api["secrets"][0]["target"] == api["environment"]["CYTELLECT_PROPOSAL_TOKEN_FILE"]
    desktop = configuration(["-f", str(ROOT / "infra/compose.desktop.yaml"), "-f", str(ROOT / "infra/compose.proposal.yaml")])
    assert set(desktop["services"]["api"]["networks"]) == {"private", "edge", "proposal_outbound"}
    assert desktop["services"]["api"]["environment"]["CYTELLECT_PROPOSAL_PROMPT_VERSION"] == "2026-10-06.1"
    assert desktop["services"]["api"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert desktop["services"]["web"]["ports"][0]["host_ip"] == "127.0.0.1"
    assert not desktop["services"]["web"].get("secrets")
    for config in (base, merged, desktop):
        worker = config["services"]["worker"]
        assert worker["network_mode"] == "none"
        assert not worker.get("networks") and not worker.get("secrets")
        assert all(not key.startswith("CYTELLECT_PROPOSAL") for key in worker["environment"])
    assert merged["services"]["web"] == base["services"]["web"]

import os

import pytest
from cytellect_api import config as config_module
from cytellect_api.config import Settings


@pytest.fixture
def secret_env(monkeypatch, tmp_path):
    monkeypatch.setenv("CYTELLECT_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.delenv("CYTELLECT_PROPOSAL_TOKEN", raising=False)
    monkeypatch.delenv("CYTELLECT_PROPOSAL_TOKEN_FILE", raising=False)
    return monkeypatch


def test_optional_secret_is_off_by_default(secret_env):
    assert Settings.from_env().proposal_token == ""


def test_device_token_file_and_direct_environment(secret_env, tmp_path):
    token = "installation-test-token-0123456789"
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN", token)
    assert Settings.from_env().proposal_token == token
    secret_env.delenv("CYTELLECT_PROPOSAL_TOKEN")
    path = tmp_path / "device-token"
    path.write_text(token + "\n", encoding="ascii")
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN_FILE", str(path))
    assert Settings.from_env().proposal_token == token
    # Device secrets are not copied into environment variables by the reader.
    assert "CYTELLECT_PROPOSAL_TOKEN" not in os.environ


def test_conflicting_sources_fail_without_exposing_either_value(secret_env, tmp_path):
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN", "sensitive-token-0123456789")
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN_FILE", str(tmp_path / "private-name"))
    with pytest.raises(ValueError, match="^proposal_token_sources_conflict$"):
        Settings.from_env()


@pytest.mark.parametrize("content", [b"", b"short", b"a" * 1000, b"\xff", b"token-with spaces-0123456789"])
def test_invalid_secret_is_bounded_and_error_is_sanitized(secret_env, tmp_path, content):
    path = tmp_path / "private-secret-name"
    path.write_bytes(content)
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN_FILE", str(path))
    with pytest.raises(ValueError, match="^proposal_token_file_invalid$"):
        Settings.from_env()


def test_missing_secret_is_refused(secret_env, tmp_path):
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN_FILE", str(tmp_path / "missing"))
    with pytest.raises(ValueError, match="^proposal_token_file_invalid$"):
        Settings.from_env()


def test_even_valid_token_is_refused_inside_checkout(secret_env, tmp_path):
    checkout = tmp_path / "checkout"
    checkout.mkdir()
    fake_module = checkout / "services/api/src/cytellect_api/config.py"
    secret_env.setattr(config_module, "__file__", str(fake_module))
    secret = checkout / "device-token"
    secret.write_text("public-test-device-token-0123456789", encoding="ascii")
    secret_env.setenv("CYTELLECT_PROPOSAL_TOKEN_FILE", str(secret))
    with pytest.raises(ValueError, match="^proposal_token_file_invalid$"):
        Settings.from_env()

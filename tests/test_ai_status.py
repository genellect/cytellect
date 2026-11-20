"""AI configuration reads never contact a model or expose credentials."""
import pytest
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from fastapi.testclient import TestClient
from test_api_worker import HEADERS


def signed_in(tmp_path, credentials=None, **configuration):
    app = create_app(Settings(tmp_path, app_origin="http://test", secure_cookies=False, **configuration),
                     proposal_credentials=credentials)
    client = TestClient(app)
    assert client.get("/v1/ai/status").status_code == 401
    assert client.post("/v1/invitations/redeem", headers=HEADERS,
                       json={"token": app.state.store.invite()}).status_code == 200
    return client


@pytest.mark.parametrize("configuration,credentials,expected", [
    ({}, None, {"state": "unconfigured", "source": "none"}),
    ({}, lambda: None, {"state": "sign_in_required", "source": "account"}),
    ({}, lambda: ("https://proposal.test", "test-device-token"), {"state": "available", "source": "account"}),
    ({"proposal_url": "https://proposal.test", "proposal_token": "test-device-token"}, None,
     {"state": "available", "source": "operator"}),
    ({"proposal_url": "https://proposal.test"}, None, {"state": "misconfigured", "source": "operator"}),
    ({"proposal_url": "http://not-loopback.test", "proposal_token": "test-device-token"}, None,
     {"state": "misconfigured", "source": "operator"}),
])
def test_status_is_authenticated_and_configuration_only(tmp_path, monkeypatch, configuration, credentials, expected):
    def forbidden(*args, **kwargs):
        raise AssertionError("configuration status must not contact a service")
    monkeypatch.setattr("cytellect_api.proposals.post_to_service", forbidden)
    client = signed_in(tmp_path, credentials, **configuration)
    response = client.get("/v1/ai/status")
    assert response.status_code == 200 and response.json() == expected
    assert response.headers["cache-control"] == "no-store"
    assert "test-device-token" not in response.text and "proposal.test" not in response.text


def test_operator_configuration_keeps_precedence_over_the_account(tmp_path):
    def not_used():
        raise AssertionError("operator configuration takes precedence")
    client = signed_in(tmp_path, not_used, proposal_url="https://proposal.test", proposal_token="operator-token")
    assert client.get("/v1/ai/status").json() == {"state": "available", "source": "operator"}

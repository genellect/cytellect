"""Response headers and service URLs of the API: what a browser or an operator can rely on."""
import pytest
from cytellect_api import proposals
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from fastapi.testclient import TestClient
from test_api_worker import HEADERS, authenticated
from test_region_ome import image_bytes, upload

ORIGIN = "http://test"


def test_api_responses_carry_a_policy_that_runs_no_script(tmp_path):
    client, _, _ = authenticated(tmp_path)
    for response in (client.get("/v1/health"), client.get("/v1/session"), client.get("/v1/jobs/missing/files/figure.svg")):
        policy = response.headers["content-security-policy"]
        assert "default-src 'none'" in policy and "frame-ancestors 'none'" in policy
        assert "script-src" not in policy and "'self'" not in policy


def test_interface_description_is_not_served(tmp_path):
    client, _, _ = authenticated(tmp_path)
    for path in ("/openapi.json", "/docs", "/redoc"):
        assert client.get(path).status_code == 404
    # The committed contract is still generated from the application object.
    assert "/v1/workspaces" in client.app.openapi()["paths"]


@pytest.mark.parametrize("url", [
    "https://user:secret@proposals.example", "https://proposals.example/?key=value",
    "https://proposals.example/#fragment", "http://proposals.example", "ftp://proposals.example", "https://",
])
def test_proposal_service_url_follows_the_common_service_url_rule(tmp_path, url):
    settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False,
                        proposal_url=url, proposal_token="operator-token-value")
    with pytest.raises(ValueError, match="proposal_service_requires_https"):
        proposals.service_url(settings)


def test_proposal_service_url_accepts_https_and_loopback(tmp_path):
    for url in ("https://proposals.example", "https://proposals.example/base/", "http://127.0.0.1:8787"):
        settings = Settings(tmp_path / "private", app_origin=ORIGIN, secure_cookies=False,
                            proposal_url=url, proposal_token="operator-token-value")
        assert proposals.service_url(settings) == url.rstrip("/")


def test_ome_region_upload_is_refused_in_demo_mode_and_without_a_session(tmp_path):
    content = image_bytes()[0]
    client, app, _ = authenticated(tmp_path / "hosted")
    wid = client.post("/v1/workspaces", json={"title": "public fixture"}, headers=HEADERS).json()["id"]
    anonymous = upload(TestClient(app), wid, content)
    assert (anonymous.status_code, anonymous.json()) == (401, {"detail": "session_required"})

    demo = create_app(Settings(tmp_path / "demo", app_origin=ORIGIN, secure_cookies=False, demo=True))
    visitor = TestClient(demo)
    assert visitor.post("/v1/invitations/redeem", json={"token": demo.state.store.invite()}, headers=HEADERS).status_code == 200
    wid = visitor.post("/v1/workspaces", json={"title": "public fixture"}, headers=HEADERS).json()["id"]
    response = upload(visitor, wid, content)
    assert (response.status_code, response.json()) == (403, {"detail": "demo_uploads_disabled"})

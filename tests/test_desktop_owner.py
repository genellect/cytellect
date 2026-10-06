from dataclasses import replace

import pytest
from cytellect_api.app import create_app
from cytellect_api.config import Settings
from cytellect_api.db import sessions
from fastapi.testclient import TestClient
from sqlalchemy import update

ORIGIN = 'http://127.0.0.1:3087'
HEADERS = {'Origin': ORIGIN, 'X-Cytellect-Request': '1', 'Sec-Fetch-Site': 'same-site'}


def test_desktop_owner_reconnect_and_expiry(tmp_path):
    settings = Settings(tmp_path, app_origin=ORIGIN, secure_cookies=False, desktop_owner=True)
    app = create_app(settings)
    client = TestClient(app, base_url='http://127.0.0.1:8001')
    assert client.get('/v1/workspaces').status_code == 401
    assert client.post('/v1/desktop/session', headers=HEADERS).status_code == 200
    owner = app.state.store.rows(sessions)[0]['owner']
    assert client.post('/v1/desktop/session', headers=HEADERS).status_code == 200
    assert len(app.state.store.rows(sessions)) == 1
    with app.state.store.transaction() as connection:
        connection.execute(update(sessions).values(expires=0))
    assert client.get('/v1/workspaces').status_code == 401
    fresh_app = create_app(settings)
    fresh = TestClient(fresh_app, base_url='http://127.0.0.1:8001')
    response = fresh.post('/v1/desktop/session', headers=HEADERS)
    assert response.status_code == 200
    assert 'HttpOnly' in response.headers['set-cookie']
    assert fresh.get('/v1/workspaces').status_code == 200
    assert {s['owner'] for s in fresh_app.state.store.rows(sessions)} == {owner}
    hosted = TestClient(create_app(replace(settings, desktop_owner=False)))
    assert hosted.post('/v1/desktop/session', headers=HEADERS).status_code == 404


@pytest.mark.parametrize('change', [
    {'Origin': 'https://evil.example'}, {'Origin': ''}, {'Host': 'evil.example'},
    {'X-Cytellect-Request': ''}, {'Sec-Fetch-Site': 'cross-site'},
    {'Sec-Fetch-Site': ''}, {'Forwarded': 'host=127.0.0.1'},
    {'X-Forwarded-For': '127.0.0.1'},
])
def test_desktop_rejects_foreign_requests(tmp_path, change):
    app = create_app(Settings(tmp_path, app_origin=ORIGIN, secure_cookies=False, desktop_owner=True))
    client = TestClient(app, base_url='http://127.0.0.1:8001')
    assert client.post('/v1/desktop/session', headers={**HEADERS, **change}).status_code == 403
    assert not app.state.store.rows(sessions)


def test_desktop_refuses_public_configuration(tmp_path):
    with pytest.raises(ValueError, match='loopback'):
        create_app(Settings(tmp_path, app_origin='https://example.com', desktop_owner=True))

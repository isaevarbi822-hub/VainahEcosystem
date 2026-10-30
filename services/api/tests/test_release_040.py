"""v0.4.0 regression tests for Neon-safe file storage, identity and abuse controls."""
from pathlib import Path
from fastapi.testclient import TestClient
import pytest

from services.api.app.main import create_app
from services.api.app.security import _AUTH_FAILURES, _SIGNUP_ATTEMPTS

PASSWORD = 'preview-only-password-129'


def signup(c, email='alpha@example.net', invite=None):
    return c.post('/api/auth/register', json={
        'display_name': 'Alpha', 'email': email, 'password': PASSWORD, 'invite_code': invite
    })


def csrf(c):
    return {'X-CSRF-Token': c.get('/api/auth/me').json()['csrf_token']}


def test_private_beta_invite_code(monkeypatch, tmp_path):
    monkeypatch.setenv('VAINAH_SIGNUP_CODE', 'private-demo-code')
    app = create_app(f"sqlite:///{tmp_path / 'private.db'}")
    with TestClient(app) as c:
        assert signup(c).status_code == 403
        assert signup(c, invite='wrong').status_code == 403
        assert signup(c, invite='private-demo-code').status_code == 201
    app.state.engine.dispose()


def test_profile_change_password_and_revoke_sessions(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'account.db'}")
    with TestClient(app) as one, TestClient(app) as two:
        assert signup(one).status_code == 201
        assert two.post('/api/auth/login',json={'email':'alpha@example.net','password':PASSWORD}).status_code == 200
        assert one.patch('/api/auth/profile', json={'display_name':' Обновлённый '}).status_code == 403
        header = csrf(one)
        assert one.patch('/api/auth/profile', json={'display_name':' Обновлённый '}, headers=header).json()['user']['display_name']=='Обновлённый'
        assert two.get('/api/auth/me').json()['user']['display_name']=='Обновлённый'
        assert one.post('/api/auth/password',json={'current_password':'wrong-password-123','new_password':'new-password-test-55'}, headers=header).status_code == 403
        response = one.post('/api/auth/password',json={'current_password': PASSWORD,'new_password':'new-password-test-55'}, headers=header)
        assert response.status_code == 200
        assert response.json()['revoked_sessions'] == 1
        assert two.get('/api/auth/me').status_code == 401
        assert one.get('/api/auth/me').status_code == 200
        assert two.post('/api/auth/login',json={'email':'alpha@example.net','password':PASSWORD}).status_code == 401
        assert two.post('/api/auth/login',json={'email':'alpha@example.net','password':'new-password-test-55'}).status_code == 200
        assert one.post('/api/auth/logout-others', headers=header).json()['revoked_sessions'] == 1
        assert two.get('/api/auth/me').status_code == 401
    app.state.engine.dispose()


def test_private_media_database_backend_survives_restart(monkeypatch, tmp_path):
    monkeypatch.setenv('VAINAH_MEDIA_BACKEND','database')
    monkeypatch.setenv('VAINAH_UPLOAD_DIR',str(tmp_path / 'disposable-files'))
    url = f"sqlite:///{tmp_path / 'persist.db'}"
    app = create_app(url)
    content = b'\x89PNG\r\n\x1a\n' + b'media-in-database-test'
    with TestClient(app) as c:
        signup(c)
        r=c.post('/api/media/photo',files={'file':('original.png',content,'image/png')},headers=csrf(c))
        assert r.status_code == 201, r.text
        file_id=r.json()['id']
        assert c.get('/api/media/file/'+file_id).content == content
    app.state.engine.dispose()
    assert not list((tmp_path / 'disposable-files').rglob('*')) if (tmp_path / 'disposable-files').exists() else True
    restarted = create_app(url)
    with TestClient(restarted) as c:
        assert c.post('/api/auth/login',json={'email':'alpha@example.net','password':PASSWORD}).status_code == 200
        assert c.get('/api/media/file/'+file_id).content == content
        assert c.delete('/api/media/file/'+file_id,headers=csrf(c)).status_code==200
        assert c.get('/api/media/file/'+file_id).status_code==404
    restarted.state.engine.dispose()


def test_auth_limiter_and_production_config(monkeypatch, tmp_path):
    monkeypatch.setenv('ENVIRONMENT','production')
    monkeypatch.setenv('COOKIE_SECURE','true')
    monkeypatch.setenv('APP_ORIGIN','https://vainah.example')
    monkeypatch.delenv('VAINAH_SIGNUP_CODE',raising=False)
    with pytest.raises(RuntimeError, match='VAINAH_SIGNUP_CODE'):
        create_app(f"sqlite:///{tmp_path / 'not-created.db'}")
    monkeypatch.setenv('VAINAH_SIGNUP_CODE','beta-secret')
    with TestClient(create_app(f"sqlite:///{tmp_path / 'limited.db'}")) as c:
        _AUTH_FAILURES.clear(); _SIGNUP_ATTEMPTS.clear()
        for i in range(8):
            assert c.post('/api/auth/login',json={'email':'limit@example.net','password':PASSWORD}).status_code == 401
        assert c.post('/api/auth/login',json={'email':'limit@example.net','password':PASSWORD}).status_code == 429
        assert signup(c, email='test@example.net',invite='beta-secret').status_code==201
    _AUTH_FAILURES.clear();_SIGNUP_ATTEMPTS.clear()


def test_new_settings_routes_assets_and_db_health(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'health.db'}")
    with TestClient(app) as c:
        assert c.get('/api/health').json()['database']=='connected'
        html=c.get('/').text
        assert 'Vainah Messenger' in html and 'vm-auth-form' in html
        assert 'screen-settings' in c.get('/app/notes').text
        css=c.get('/assets/styles.css').text
        assert '.mobile-tabs' in css
        assert c.get('/manifests/notes.webmanifest').json()['name']=='Vainah Notes'
    app.state.engine.dispose()

"""Google identity tests run without contacting Google (verification is mocked)."""
from fastapi.testclient import TestClient
from services.api.app.main import create_app
from services.api.app import auth

def test_google_disabled_without_client_id(monkeypatch, tmp_path):
    monkeypatch.delenv("GOOGLE_CLIENT_ID", raising=False)
    app = create_app(f"sqlite:///{tmp_path / 'disabled.db'}")
    with TestClient(app) as c:
        assert c.get("/api/auth/providers").json() == {
            "email": True, "google": False, "google_client_id": None}
        assert c.post("/api/auth/google", json={"credential": "x"*50}).status_code == 503
    app.state.engine.dispose()

def test_google_signin_new_and_repeat(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
    monkeypatch.setattr(auth, "verify_google_credential", lambda _: {
        "sub": "subject-123", "email": "google@example.com", "name": "Google User"})
    app = create_app(f"sqlite:///{tmp_path / 'google.db'}")
    with TestClient(app) as first, TestClient(app) as second:
        r = first.post("/api/auth/google", json={"credential": "x"*50})
        assert r.status_code == 200, r.text
        uid = r.json()["user"]["id"]
        assert second.post("/api/auth/google", json={"credential": "x"*50}).json()["user"]["id"] == uid
        assert "password_hash" not in r.text
    app.state.engine.dispose()

def test_existing_email_not_linked_automatically(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
    monkeypatch.setattr(auth, "verify_google_credential", lambda _: {
        "sub": "subject-123", "email": "user@example.com", "name": "Google User"})
    app = create_app(f"sqlite:///{tmp_path / 'linked.db'}")
    with TestClient(app) as member, TestClient(app) as another:
        user = member.post("/api/auth/register", json={
            "email": "user@example.com", "display_name": "Member",
            "password": "long-test-password-123"}).json()["user"]
        assert another.post("/api/auth/google", json={"credential": "x"*50}).status_code == 409
        assert another.get("/api/auth/me").status_code == 401
        assert member.post("/api/auth/google/link", json={"credential": "x"*50}).status_code == 403
        csrf = member.get("/api/auth/me").json()["csrf_token"]
        assert member.post("/api/auth/google/link", json={"credential": "x"*50},
                           headers={"X-CSRF-Token": csrf}).status_code == 200
        assert another.post("/api/auth/google", json={"credential": "x"*50}).json()["user"]["id"] == user["id"]
    app.state.engine.dispose()

def test_google_signup_obeys_invite_code(monkeypatch, tmp_path):
    monkeypatch.setenv("GOOGLE_CLIENT_ID", "test-id.apps.googleusercontent.com")
    monkeypatch.setenv("VAINAH_SIGNUP_CODE", "secret-test-invite")
    monkeypatch.setattr(auth, "verify_google_credential", lambda _: {
        "sub": "subject-123", "email": "new@example.com", "name": "Google User"})
    app = create_app(f"sqlite:///{tmp_path / 'invited.db'}")
    with TestClient(app) as c:
        assert c.post("/api/auth/google", json={"credential": "x"*50}).status_code == 403
        assert c.post("/api/auth/google", json={
            "credential": "x"*50, "invite_code": "secret-test-invite"}).status_code == 200
    app.state.engine.dispose()

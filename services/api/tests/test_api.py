import pytest
from fastapi.testclient import TestClient
from services.api.app.main import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'test.db'}")
    with TestClient(app) as test_client:
        yield test_client
    app.state.engine.dispose()


def register(client, email="first@example.com", name="Первый"):
    return client.post("/api/auth/register", json={
        "display_name": name, "email": email, "password": "example-test-password-173"
    })


def csrf(client):
    response = client.get("/api/auth/me")
    assert response.status_code == 200
    return {"X-CSRF-Token": response.json()["csrf_token"]}


def test_health_and_web(client):
    assert client.get("/api/health").json()["status"] == "ok"
    assert "VAINAH ID" in client.get("/").text
    assert "renderNotes" in client.get("/assets/app.js").text


def test_anonymous_cannot_read_notes(client):
    assert client.get("/api/notes").status_code == 401
    assert client.post("/api/notes", json={"title": "x"}).status_code == 401


def test_register_login_and_restore(client):
    response = register(client, email="TEST@Example.com")
    assert response.status_code == 201
    user = response.json()["user"]
    assert user["email"] == "test@example.com"
    assert "password_hash" not in response.text
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "SameSite=strict" in response.headers["set-cookie"]
    assert client.get("/api/auth/me").json()["user"]["id"] == user["id"]
    assert register(client, email="test@example.com").status_code == 409
    assert client.post("/api/auth/login", json={"email": "test@example.com", "password": "incorrectlongpassword"}).status_code == 401
    headers = csrf(client)
    assert client.post("/api/auth/logout", headers=headers).json() == {"ok": True}
    assert client.get("/api/auth/me").status_code == 401
    assert client.post("/api/auth/login", json={"email": "test@example.com", "password": "example-test-password-173"}).status_code == 200


def test_notes_crud_and_search(client):
    register(client)
    headers = csrf(client)
    res = client.post("/api/notes", json={"title": "Первая", "content": "Привет, мой мир"}, headers=headers)
    assert res.status_code == 201
    note_id = res.json()["id"]
    assert len(client.get("/api/notes").json()["items"]) == 1
    assert len(client.get("/api/notes?q=Привет").json()["items"]) == 1
    assert len(client.get("/api/notes?q=неизвестно").json()["items"]) == 0
    res = client.put(f"/api/notes/{note_id}", json={"title": "Новая", "content": "обновлено"}, headers=headers)
    assert res.status_code == 200
    assert res.json()["title"] == "Новая"
    assert client.delete(f"/api/notes/{note_id}", headers=headers).status_code == 200
    assert client.get("/api/notes").json()["items"] == []
    assert client.delete(f"/api/notes/{note_id}", headers=headers).status_code == 404


def test_csrf_and_origin_reject_bad_requests(client):
    register(client)
    assert client.post("/api/notes", json={"title": "Без CSRF"}).status_code == 403
    assert client.post("/api/notes", json={"title": "Чужой Origin"},
                       headers={**csrf(client), "Origin": "https://attacker.example"}).status_code == 403
    assert client.post("/api/auth/login", json={"email": "first@example.com", "password": "example-test-password-173"},
                       headers={"Origin": "https://attacker.example"}).status_code == 403


def test_user_note_isolation(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'isolated.db'}")
    with TestClient(app) as alice, TestClient(app) as bob:
        register(alice, email="alice@example.com", name="Alice")
        note_id = alice.post("/api/notes", json={"title": "Private", "content": "Secret"}, headers=csrf(alice)).json()["id"]
        register(bob, email="bob@example.com", name="Bob")
        assert bob.get("/api/notes").json()["items"] == []
        assert bob.put(f"/api/notes/{note_id}", json={"title": "Hacked", "content": "X"}, headers=csrf(bob)).status_code == 404
        assert bob.delete(f"/api/notes/{note_id}", headers=csrf(bob)).status_code == 404
        assert alice.get("/api/notes").json()["items"][0]["title"] == "Private"
    app.state.engine.dispose()


def test_bounds_and_validation(client):
    assert client.post("/api/auth/register", json={"display_name": "a", "email": "x", "password": "abc"}).status_code == 422
    register(client)
    assert client.post("/api/notes", json={"title": "X" * 500}, headers=csrf(client)).status_code == 422
    assert client.get("/api/notes?q=" + "x" * 150).status_code == 422


def test_production_requires_https(monkeypatch):
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    with pytest.raises(RuntimeError, match="COOKIE_SECURE"):
        create_app()


def test_notes_persist_after_app_restart(tmp_path):
    url = f"sqlite:///{tmp_path / 'persistent.db'}"
    app_a = create_app(url)
    with TestClient(app_a) as client_a:
        register(client_a)
        assert client_a.post("/api/notes", json={"title": "Сохраняется", "content": "После перезапуска"}, headers=csrf(client_a)).status_code == 201
    app_a.state.engine.dispose()
    app_b = create_app(url)
    with TestClient(app_b) as client_b:
        response = client_b.post("/api/auth/login", json={"email": "first@example.com", "password": "example-test-password-173"})
        assert response.status_code == 200
        items = client_b.get("/api/notes").json()["items"]
        assert len(items) == 1 and items[0]["title"] == "Сохраняется"
    app_b.state.engine.dispose()


def test_api_headers_are_private(client):
    res = client.get("/api/health")
    assert res.headers["cache-control"] == "no-store"
    assert "nosniff" == res.headers["x-content-type-options"]
    assert "frame-ancestors 'none'" in res.headers["content-security-policy"]

"""Standalone Messenger channels, bots and verified badge access controls."""
from fastapi.testclient import TestClient
from services.api.app.main import create_app


def register(client, email):
    r=client.post("/api/auth/register", json={
        "email":email, "display_name":"Tester", "password":"safe-test-password-2026"})
    assert r.status_code==201, r.text
    data=r.json()
    return data["user"]["id"], {"X-CSRF-Token": data["csrf_token"]}


def test_channels_subscription_and_owner_only_posts(tmp_path, monkeypatch):
    monkeypatch.setenv("VAINAH_SIGNUP_MODE","open")
    app=create_app(f"sqlite:///{tmp_path / 'community.db'}")
    with TestClient(app) as alice, TestClient(app) as bob:
        alice_id, alice_header=register(alice,"alice-chan@example.com")
        bob_id, bob_header=register(bob,"bob-chan@example.com")
        created=alice.post("/api/community/channels",
                           json={"name":"Новости Vainah","description":"Тестовые публикации"},
                           headers=alice_header)
        assert created.status_code==201,created.text
        channel_id=created.json()["id"]
        channels=bob.get("/api/community/channels").json()["items"]
        assert any(ch["id"]==channel_id and not ch["subscribed"] for ch in channels)
        assert bob.post(f"/api/community/channels/{channel_id}/posts",
                        json={"body":"Посторонняя публикация"},headers=bob_header).status_code==403
        assert alice.post(f"/api/community/channels/{channel_id}/posts",
                         json={"body":"Первая запись"},headers=alice_header).status_code==201
        assert bob.post(f"/api/community/channels/{channel_id}/subscribe",
                        headers=bob_header).status_code==200
        assert bob.get(f"/api/community/channels/{channel_id}/posts").json()["items"][0]["body"]=="Первая запись"
        assert bob.delete(f"/api/community/channels/{channel_id}/subscribe",
                          headers=bob_header).status_code==200
        assert alice.delete(f"/api/community/channels/{channel_id}/subscribe",
                            headers=alice_header).status_code==403
    app.state.engine.dispose()


def test_bot_rules_only_owner_can_change(tmp_path, monkeypatch):
    monkeypatch.setenv("VAINAH_SIGNUP_MODE","open")
    app=create_app(f"sqlite:///{tmp_path / 'bots.db'}")
    with TestClient(app) as owner, TestClient(app) as other:
        _,owner_header=register(owner,"bot-owner@example.com")
        _,other_header=register(other,"bot-other@example.com")
        bot=owner.post("/api/community/bots",json={"name":"Помощник Vainah"},headers=owner_header)
        assert bot.status_code==201,bot.text
        bot_id=bot.json()["id"]
        endpoint=f"/api/community/bots/{bot_id}/rules"
        assert other.post(endpoint,json={"trigger":"привет","reply":"Взлом"},
                          headers=other_header).status_code==403
        assert owner.post(endpoint,json={"trigger":"привет","reply":"Добрый день!"},
                          headers=owner_header).status_code==201
        assert other.post(f"/api/community/bots/{bot_id}/reply",
                          json={"message":"Всем привет!"}).json()["reply"]=="Добрый день!"
        assert other.post(f"/api/community/bots/{bot_id}/reply",
                          json={"message":"другая фраза"}).json()["reply"]=="Пока нет ответа на этот запрос."
    app.state.engine.dispose()


def test_verified_badge_admin_only(tmp_path, monkeypatch):
    monkeypatch.setenv("VAINAH_SIGNUP_MODE","open")
    monkeypatch.delenv("VAINAH_VERIFICATION_ADMIN_IDS",raising=False)
    app=create_app(f"sqlite:///{tmp_path / 'verified.db'}")
    with TestClient(app) as admin, TestClient(app) as user:
        admin_id,admin_headers=register(admin,"badge-admin@example.com")
        user_id,user_headers=register(user,"badge-user@example.com")
        route="/api/messenger/v2/verification/manage"
        assert user.post(route,json={"user_id":user_id,"verified":True},
                         headers=user_headers).status_code==403
        monkeypatch.setenv("VAINAH_VERIFICATION_ADMIN_IDS",admin_id)
        assert admin.post(route,json={"user_id":user_id,"verified":True},
                          headers=admin_headers).status_code==200
        assert user.get("/api/messenger/v2/verification/me").json()["verified"] is True
        assert user.post(route,json={"user_id":admin_id,"verified":True},
                         headers=user_headers).status_code==403
        assert admin.post(route,json={"user_id":user_id,"verified":False},
                          headers=admin_headers).status_code==200
        assert user.get("/api/messenger/v2/verification/me").json()["verified"] is False
    app.state.engine.dispose()


def test_landing_page_hides_catalog_and_google_buttons(tmp_path, monkeypatch):
    monkeypatch.setenv("VAINAH_SIGNUP_MODE","open")
    app=create_app(f"sqlite:///{tmp_path / 'landing.db'}")
    with TestClient(app) as client:
        response=client.get("/")
        assert response.status_code==200
        assert "Vainah Messenger" in response.text
        assert "Vainah AI" not in response.text
        assert "Продолжить с Google" not in response.text
        assert client.get("/assets/messenger-home.css").status_code==200
        assert client.get("/assets/messenger-app.js").status_code==200
    app.state.engine.dispose()

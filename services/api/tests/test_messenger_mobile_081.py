"""Contract checks for Vainah Messenger's phone-sized UI and API shell."""
from fastapi.testclient import TestClient
from services.api.app.main import create_app


def test_mobile_messenger_shell_is_served(tmp_path, monkeypatch):
    monkeypatch.setenv("VAINAH_SIGNUP_MODE", "open")
    app = create_app(f"sqlite:///{tmp_path / 'mobile.db'}")
    with TestClient(app) as client:
        response = client.get("/app/messenger")
        assert response.status_code == 200
        html = response.text
        for marker in (
            'id="vm-search-action"', 'id="vm-compose-action"',
            'id="vm-floating-compose"', 'id="vm-rail-chats"',
            'id="vm-rail-channels"', 'id="vm-rail-bots"',
            'id="vm-rail-settings"', '/assets/messenger-home.css',
            '/assets/messenger-app.js'
        ):
            assert marker in html, marker
        css = client.get("/assets/messenger-home.css")
        assert css.status_code == 200
        assert ".vm-floating-compose" in css.text
        assert ".vchat-contact-channel" in css.text
        js = client.get("/assets/messenger-app.js")
        assert js.status_code == 200
        assert "openCompose" in js.text
        assert "openChannel" in js.text
        assert client.get("/api/health").json()["version"] == "0.8.1"
    app.state.engine.dispose()

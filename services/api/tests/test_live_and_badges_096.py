"""Live websocket typing and administrator-only verification integration."""
import pytest
from fastapi.testclient import TestClient
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user


def test_live_typing_does_not_share_draft_body(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'live096.db'}")
    try:
        alice,aid,ha=new_user(app,"typing-a@example.net")
        bob,bid,hb=new_user(app,"typing-b@example.net")
        with bob.websocket_connect("/api/messenger/v2/live",
             headers={"origin":"http://testserver"}) as wb:
            assert wb.receive_json()["type"]=="ready"
            with alice.websocket_connect("/api/messenger/v2/live",
                 headers={"origin":"http://testserver"}) as wa:
                assert wa.receive_json()["type"]=="ready"
                wa.send_json({"type":"typing","to":bid,"body":"Never send typed text"})
                event=wb.receive_json()
                assert event=={"type":"typing","from":aid}
    finally:
        app.state.engine.dispose()


def test_admin_verified_status_visible_and_not_user_issued(tmp_path,monkeypatch):
    app=create_app(f"sqlite:///{tmp_path/'badges096.db'}")
    try:
        alice,aid,ha=new_user(app,"verify-a@example.net")
        bob,bid,hb=new_user(app,"verify-b@example.net")
        monkeypatch.setenv("VAINAH_VERIFICATION_ADMIN_IDS",aid)
        assert bob.put("/api/people/username",headers=hb,
                       json={"username":"verified_bob"}).status_code==200
        assert bob.get("/api/people/me").json()["verified"] is False
        assert alice.get("/api/people/search?q=verified").json()["items"][0]["verified"] is False
        assert bob.post("/api/messenger/v2/verification/manage",
                        headers=hb,json={"user_id":bid,"verified":True}).status_code==403
        public_id=bob.get("/api/people/me").json()["vainah_id"]
        verified=alice.post("/api/messenger/v2/verification/manage",
                            headers=ha,json={"user_id":public_id,"verified":True})
        assert verified.status_code==200,verified.text
        assert bob.get("/api/people/me").json()["verified"] is True
        assert alice.get("/api/people/search?q=verified").json()["items"][0]["verified"] is True
        assert alice.get(f"/api/people/id/{public_id}").json()["person"]["verified"] is True
        revoked=alice.post("/api/messenger/v2/verification/manage",headers=ha,
                           json={"user_id":"@verified_bob","verified":False})
        assert revoked.status_code==200,revoked.text
        assert bob.get("/api/people/me").json()["verified"] is False
    finally:
        app.state.engine.dispose()

"""Messenger regression checks for 0.9.5 native client and profile controls."""
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user, send


def test_username_in_existing_direct_chats_and_threads(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'chats095.db'}")
    try:
        alice,aid,ha=new_user(app,"alice095@example.net")
        bob,bid,hb=new_user(app,"bob095@example.net")
        assert alice.put("/api/people/username",headers=ha,
                         json={"username":"alice095"}).status_code==200
        assert send(bob,hb,aid,"Hello world").status_code==201
        found=bob.get("/api/messenger/v2/chats")
        assert found.status_code==200
        assert found.json()["items"][0]["username"]=="alice095"
        contact=bob.get(f"/api/messenger/v2/thread/{aid}")
        assert contact.status_code==200
        assert contact.json()["contact"]["username"]=="alice095"
        assert alice.put("/api/people/username",headers=ha,
                         json={"username":"alice_new095"}).status_code==200
        assert bob.get("/api/messenger/v2/chats").json()["items"][0]["username"]=="alice_new095"
    finally:
        app.state.engine.dispose()


def test_real_chat_management_actions(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'controls095.db'}")
    try:
        alice,aid,ha=new_user(app,"alice095@example.net")
        bob,bid,hb=new_user(app,"bob095@example.net")
        assert send(alice,ha,bid).status_code==201
        assert bob.patch(f"/api/messenger/v2/preferences/{aid}",headers=hb,
                         json={"pinned":True,"muted":True}).status_code==200
        view=bob.get("/api/messenger/v2/chats").json()["items"][0]
        assert view["pinned"] and view["muted"]
        assert bob.patch(f"/api/messenger/v2/preferences/{aid}",headers=hb,
                         json={"archived":True}).status_code==200
        assert bob.get("/api/messenger/v2/chats").json()["items"][0]["archived"]
        assert bob.put(f"/api/messenger/v2/block/{aid}",headers=hb).status_code==200
        assert send(alice,ha,bid).status_code==403
        assert bob.delete(f"/api/messenger/v2/block/{aid}",headers=hb).status_code==200
        assert send(alice,ha,bid).status_code==201
    finally:
        app.state.engine.dispose()

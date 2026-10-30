"""Public username lookup and opt-in channel invitation integration."""
import pytest
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user

@pytest.fixture
def users(tmp_path):
    app=create_app(f"sqlite:///{tmp_path / 'usernames.db'}")
    a,aid,ha=new_user(app,"alice@example.net")
    b,bid,hb=new_user(app,"bob@example.net")
    c,cid,hc=new_user(app,"charlie@example.net")
    yield app,(a,aid,ha),(b,bid,hb),(c,cid,hc)
    app.state.engine.dispose()

def test_unique_names_search_privacy_and_csrf(users):
    app,(a,aid,ha),(b,bid,hb),(c,cid,hc)=users
    assert a.get("/api/people/search?q=bobb").json()["items"]==[]
    assert a.put("/api/people/username",json={"username":"Alice_vainah"}).status_code==403
    assert a.put("/api/people/username",headers=ha,json={"username":"Alice_vainah"}).json()["username"]=="alice_vainah"
    assert b.put("/api/people/username",headers=hb,json={"username":"bob_vainah"}).status_code==200
    assert c.put("/api/people/username",headers=hc,json={"username":"BOB_VAINAH"}).status_code==409
    assert c.put("/api/people/username",headers=hc,json={"username":"admin"}).status_code==422
    assert c.put("/api/people/username",headers=hc,json={"username":"bad.name"}).status_code==422
    assert a.get("/api/people/me").json()["username"]=="alice_vainah"
    assert b.get("/api/people/search?q=@ali").json()["items"]==[
        {"id":aid,"display_name":"alice","verified":False,"username":"alice_vainah"}]
    assert not any("email" in x for x in b.get("/api/people/search?q=ali").json()["items"])
    assert not a.get("/api/people/search?q=alice_vainah").json()["items"]
    assert b.get("/api/people/@Alice_Vainah").json()["person"]["id"]==aid
    assert b.get("/api/people/search?q=al").json()["items"]==[]
    assert a.put(f"/api/messenger/v2/block/{bid}",headers=ha).status_code==200
    assert b.get("/api/people/search?q=ali").json()["items"]==[]
    assert b.get("/api/people/alice_vainah").status_code==404

def test_group_member_by_username(users):
    app,(a,aid,ha),(b,bid,hb),(c,cid,hc)=users
    assert b.put("/api/people/username",headers=hb,json={"username":"bobby_vainah"}).status_code==200
    assert c.put("/api/people/username",headers=hc,json={"username":"charlie_vainah"}).status_code==200
    created=a.post("/api/messenger/v2/groups",headers=ha,json={
        "name":"Group by handles","usernames":["@Bobby_vainah","bobby_vainah"]})
    assert created.status_code==201,created.text
    gid=created.json()["id"]
    assert created.json()["members"]==2
    assert b.get("/api/messenger/v2/groups").json()["items"][0]["id"]==gid
    assert a.post(f"/api/messenger/v2/groups/{gid}/invite",headers=ha,
                  json={"username":"@charlie_vainah"}).status_code==200
    assert c.get(f"/api/messenger/v2/groups/{gid}").status_code==200
    assert b.post(f"/api/messenger/v2/groups/{gid}/invite",headers=hb,
                  json={"username":"noone_xyz"}).status_code==403

def test_channel_invites_are_opt_in_and_owner_only(users):
    app,(a,aid,ha),(b,bid,hb),(c,cid,hc)=users
    assert b.put("/api/people/username",headers=hb,json={"username":"bobby_vainah"}).status_code==200
    channel=a.post("/api/community/channels",headers=ha,json={"name":"Tech news","description":"test"})
    assert channel.status_code==201,channel.text
    channel_id=channel.json()["id"]
    endpoint=f"/api/community/channels/{channel_id}/invite"
    assert b.post(endpoint,headers=hb,json={"username":"bobby_vainah"}).status_code==403
    assert a.post(endpoint,json={"username":"bobby_vainah"}).status_code==403
    first=a.post(endpoint,headers=ha,json={"username":"@bobby_vainah"})
    assert first.status_code==200,first.text
    assert a.post(endpoint,headers=ha,json={"username":"bobby_vainah"}).status_code==409
    assert a.get("/api/community/channels/invitations").json()["items"]==[]
    invitations=b.get("/api/community/channels/invitations").json()["items"]
    assert len(invitations)==1
    invite_id=invitations[0]["id"]
    assert b.get("/api/community/channels").json()["items"][0]["subscribed"] is False
    route=f"/api/community/channels/invitations/{invite_id}/accept"
    assert c.post(route,headers=hc).status_code==404
    assert b.post(route).status_code==403
    assert b.post(route,headers=hb).status_code==200
    assert b.get("/api/community/channels").json()["items"][0]["subscribed"] is True
    assert b.get("/api/community/channels/invitations").json()["items"]==[]
    assert a.post(endpoint,headers=ha,json={"username":"bobby_vainah"}).status_code==409

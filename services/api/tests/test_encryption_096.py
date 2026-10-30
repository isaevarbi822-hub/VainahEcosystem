"""AES-GCM-at-rest: unique nonces, integrity, old messages, and ORM integration."""
import base64
import os
import pytest
from sqlalchemy import text as sql_text
from services.api.app.message_crypto import seal, open_message, PREFIX
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user, send

KEY = base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")

def test_aead_encryption_and_authenticity(monkeypatch):
    monkeypatch.setenv("VAINAH_MESSAGE_ENCRYPTION_KEY", KEY)
    a=seal("Привет, Vainah")
    b=seal("Привет, Vainah")
    assert a.startswith(PREFIX) and b.startswith(PREFIX)
    assert a != b  # fresh random nonce
    assert "Привет" not in a
    assert open_message(a) == "Привет, Vainah"
    assert open_message("До миграции") == "До миграции"
    modified=a[:-5]+("X" if a[-5]!="X" else "Y")+a[-4:]
    with pytest.raises(RuntimeError):
        open_message(modified)
    monkeypatch.delenv("VAINAH_MESSAGE_ENCRYPTION_KEY")
    with pytest.raises(RuntimeError,match="require"):
        open_message(a)

def test_encryption_through_legacy_and_new_endpoints(tmp_path,monkeypatch):
    monkeypatch.setenv("VAINAH_MESSAGE_ENCRYPTION_KEY", KEY)
    app=create_app(f"sqlite:///{tmp_path/'encrypted-messages.db'}")
    try:
        alice,aid,ha=new_user(app,"encrypted-alice@example.net")
        bob,bid,hb=new_user(app,"encrypted-bob@example.net")
        r=send(alice,ha,bid,"Секретный текст")
        assert r.status_code==201,r.text
        assert bob.get(f"/api/messenger/v2/thread/{aid}").json()["items"][0]["body"]=="Секретный текст"
        assert bob.get(f"/api/messenger/v2/search/{aid}?q=Секретный").json()["items"][0]["body"]=="Секретный текст"
        group=alice.post("/api/messenger/v2/groups",json={"name":"Шифрованная группа","emails":["encrypted-bob@example.net"]},headers=ha)
        assert group.status_code==201,group.text
        gid=group.json()["id"]
        posted=alice.post(f"/api/messenger/v2/groups/{gid}/send",json={"body":"Групповой секрет"},headers=ha)
        assert posted.status_code==201,posted.text
        assert bob.get(f"/api/messenger/v2/groups/{gid}/messages").json()["items"][0]["body"]=="Групповой секрет"
        legacy=alice.post("/api/messenger/send",json={"email":"encrypted-bob@example.net","body":"Старый клиент"},headers=ha)
        assert legacy.status_code==201,legacy.text
        with app.state.engine.connect() as conn:
            direct=conn.execute(sql_text("SELECT body FROM direct_messages")).scalars().all()
            group_bodies=conn.execute(sql_text("SELECT body FROM messenger_group_messages")).scalars().all()
        assert len(direct)==2 and all(x.startswith(PREFIX) for x in direct)
        assert len(group_bodies)==1 and group_bodies[0].startswith(PREFIX)
        assert "Старый клиент" not in str(direct)
        assert all(open_message(x) for x in direct+group_bodies)
    finally:
        app.state.engine.dispose()

def test_unconfigured_server_keeps_legacy_plaintext_compatible(tmp_path,monkeypatch):
    monkeypatch.delenv("VAINAH_MESSAGE_ENCRYPTION_KEY",raising=False)
    assert seal("legacy")=="legacy"
    app=create_app(f"sqlite:///{tmp_path/'unencrypted.db'}")
    try:
        a,aid,ha=new_user(app,"plain-a@example.net")
        b,bid,hb=new_user(app,"plain-b@example.net")
        assert send(a,ha,bid,"До настройки").status_code==201
        monkeypatch.setenv("VAINAH_MESSAGE_ENCRYPTION_KEY",KEY)
        assert b.get(f"/api/messenger/v2/thread/{aid}").json()["items"][0]["body"]=="До настройки"
        assert send(a,ha,bid,"После настройки").status_code==201
        both=b.get(f"/api/messenger/v2/thread/{aid}").json()["items"]
        assert {v["body"] for v in both}=={"До настройки","После настройки"}
    finally:app.state.engine.dispose()

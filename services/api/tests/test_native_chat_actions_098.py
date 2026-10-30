"""Android message actions should be grounded in server-owned authorization.

Test the real endpoints used by long-press reply/reaction/edit/delete/search,
with AES-GCM-at-rest enabled to cover ciphertext compatibility.
"""
import base64
from sqlalchemy import text as sql_text

from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user, send
from services.api.app.message_crypto import PREFIX


def test_android_direct_message_actions_with_encrypted_storage(tmp_path, monkeypatch):
    key=base64.urlsafe_b64encode(bytes(range(32))).decode("ascii")
    monkeypatch.setenv("VAINAH_MESSAGE_ENCRYPTION_KEY",key)
    app=create_app(f"sqlite:///{tmp_path / 'message-actions.db'}")
    try:
        alice,aid,ha=new_user(app,"message-actions-a@example.net")
        bob,bid,hb=new_user(app,"message-actions-b@example.net")
        sent=send(alice,ha,bid,"Начальный текст")
        assert sent.status_code==201,sent.text
        mid=sent.json()["id"]
        assert alice.put(f"/api/messenger/v2/message/{mid}/reaction",
                         headers=ha,json={"emoji":"❤️"}).status_code==200
        assert bob.put(f"/api/messenger/v2/message/{mid}/reaction",
                       headers=hb,json={"emoji":"👍"}).status_code==200
        reactions=bob.get(f"/api/messenger/v2/thread/{aid}").json()["items"][0]["reactions"]
        assert {r["emoji"] for r in reactions}=={"❤️","👍"}
        reply=bob.post("/api/messenger/v2/send",headers=hb,json={
            "contact_id":aid,"body":"Ответ для проверки","reply_to_id":mid})
        assert reply.status_code==201,reply.text
        assert reply.json()["reply_to"]["id"]==mid
        assert bob.patch(f"/api/messenger/v2/message/{mid}",headers=hb,
                           json={"body":"Недопустимое редактирование"}).status_code==404
        edited=alice.patch(f"/api/messenger/v2/message/{mid}",headers=ha,
                           json={"body":"Обновлённый текст"})
        assert edited.status_code==200,edited.text
        assert edited.json()["edited_at"] is not None
        found=bob.get(f"/api/messenger/v2/search/{aid}",params={"q":"обновлённый"})
        assert found.status_code==200,found.text
        assert [m["id"] for m in found.json()["items"]]==[mid]
        with app.state.engine.connect() as conn:
            raw=conn.execute(sql_text("SELECT body FROM direct_messages WHERE id=:id"),
                             {"id":mid}).scalar_one()
        assert raw.startswith(PREFIX)
        assert "Обновлённый" not in raw
        assert bob.delete(f"/api/messenger/v2/message/{mid}",headers=hb).status_code==404
        deleted=alice.delete(f"/api/messenger/v2/message/{mid}",headers=ha)
        assert deleted.status_code==200,deleted.text
        now=bob.get(f"/api/messenger/v2/thread/{aid}").json()["items"]
        target=next(m for m in now if m["id"]==mid)
        assert target["deleted"] is True and target["body"]=="" and target["reactions"]==[]
        assert bob.put(f"/api/messenger/v2/message/{mid}/reaction",headers=hb,
                       json={"emoji":"👍"}).status_code==409
    finally:
        app.state.engine.dispose()

"""Media in group conversations is only visible to current members."""
import io
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user


def test_group_media_protected_round_video_and_voice(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'groups-media.db'}")
    try:
        alice,aid,ha=new_user(app,"media-group-a@example.net")
        bob,bid,hb=new_user(app,"media-group-b@example.net")
        eve,eid,he=new_user(app,"media-group-e@example.net")
        created=alice.post("/api/messenger/v2/groups",headers=ha,json={
            "name":"Семья","emails":["media-group-b@example.net"]})
        assert created.status_code==201,created.text
        gid=created.json()["id"]
        mp4=b"\x00\x00\x00\x18ftypisom"+b"\x00"*45
        def upload(client,headers,filename,mime,body):
            return client.post(f"/api/messenger/v2/groups/{gid}/send-file",headers=headers,
                files={"file":(filename,io.BytesIO(body),mime)})
        assert upload(eve,he,"video-note-intruder.mp4","video/mp4",mp4).status_code==404
        filmed=upload(alice,ha,"video-note-hello.mp4","video/mp4",mp4)
        assert filmed.status_code==201,filmed.text
        assert filmed.json()["attachment"]["kind"]=="video_note"
        path=filmed.json()["attachment"]["url"]
        assert bob.get(path).content==mp4
        assert eve.get(path).status_code==404
        assert bob.get(f"/api/messenger/v2/groups/{gid}/messages").json()["items"][0]["attachment"]["kind"]=="video_note"
        voice=upload(bob,hb,"voice-hey.m4a","audio/mp4",mp4)
        assert voice.status_code==201,voice.text
        assert voice.json()["attachment"]["kind"]=="voice"
        pdf=upload(alice,ha,"page.pdf","application/pdf",b"%PDF-1.6\nhi")
        assert pdf.status_code==201
        assert bob.get(pdf.json()["attachment"]["url"]).headers["content-disposition"]=="attachment"
        assert upload(alice,ha,"evil.mp4","video/mp4",b"<script/>").status_code==415
        assert eve.get(f"/api/messenger/v2/groups/{gid}/messages").status_code==404
    finally:
        app.state.engine.dispose()

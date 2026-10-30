"""Vainah Messenger media regression tests for voice, video notes, files and privacy."""
import io
import pytest
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user

def upload(client,headers,contact,filename,mime,content):
    return client.post("/api/messenger/v2/send-file",
        data={"contact_id":contact},
        files={"file":(filename,io.BytesIO(content),mime)},headers=headers)

def test_authenticated_media_round_trip_and_video_kind(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'media010.db'}")
    try:
        alice,aid,ha=new_user(app,"media-010-a@example.net")
        bob,bid,hb=new_user(app,"media-010-b@example.net")
        mp4=b"\x00\x00\x00\x18ftypisom"+b"\x00"*80
        round_note=upload(alice,ha,bid,"video-note-test.mp4","video/mp4",mp4)
        assert round_note.status_code==201,round_note.text
        video=round_note.json()["attachment"]
        assert video["type"]=="video/mp4"
        assert video["kind"]=="video_note"
        assert bob.get(video["url"]).content==mp4
        assert bob.get("/api/messenger/v2/thread/"+aid).json()["items"][0]["attachment"]["kind"]=="video_note"
        voice=upload(bob,hb,aid,"voice-test.m4a","audio/mp4",mp4)
        assert voice.status_code==201,voice.text
        assert voice.json()["attachment"]["kind"]=="voice"
        assert voice.json()["attachment"]["type"]=="audio/mp4"
        picture=upload(alice,ha,bid,"image.png","image/png",b"\x89PNG\r\n\x1a\n"+b"data")
        assert picture.status_code==201,picture.text
        assert picture.json()["attachment"]["kind"]=="photo"
        document=upload(alice,ha,bid,"document.pdf","application/pdf",b"%PDF-1.6\n" + b"data")
        assert document.status_code==201,document.text
        assert document.json()["attachment"]["kind"]=="file"
        assert bob.get(document.json()["attachment"]["url"]).headers["content-disposition"]=="attachment"
        zipped=upload(alice,ha,bid,"archive.zip","application/zip",b"PK\x03\x04"+b"\x00"*30)
        assert zipped.status_code==201,zipped.text
        assert zipped.json()["attachment"]["type"]=="application/zip"
    finally:
        app.state.engine.dispose()

def test_media_privacy_wrong_mime_limits_and_blocking(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'media-privacy.db'}")
    try:
        alice,aid,ha=new_user(app,"media-privacy-a@example.net")
        bob,bid,hb=new_user(app,"media-privacy-b@example.net")
        charlie,cid,hc=new_user(app,"media-privacy-c@example.net")
        fake=upload(alice,ha,bid,"bad.mp4","video/mp4",b"<script>alert('x')</script>")
        assert fake.status_code==415
        good=upload(alice,ha,bid,"clip.mp4","video/mp4",b"\x00\x00\x00\x18ftypisom"+b"x"*32)
        assert good.status_code==201
        url=good.json()["attachment"]["url"]
        assert charlie.get(url).status_code==404
        assert bob.get(url).status_code==200
        assert bob.delete("/api/messenger/v2/message/"+good.json()["id"],headers=hb).status_code==404
        assert alice.delete("/api/messenger/v2/message/"+good.json()["id"],headers=ha).status_code==200
        assert bob.get(url).status_code==404
        assert bob.put(f"/api/messenger/v2/block/{aid}",headers=hb).status_code==200
        assert upload(alice,ha,bid,"blocked.png","image/png",b"\x89PNG\r\n\x1a\n").status_code==403
    finally:
        app.state.engine.dispose()

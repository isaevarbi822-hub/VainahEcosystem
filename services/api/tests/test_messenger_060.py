"""New 0.6 Messenger behaviors, privacy and cross-user isolation."""
import pytest
from fastapi.testclient import TestClient
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user, send


@pytest.fixture
def trio(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'v060.db'}")
    a, aid, ha = new_user(app, 'alice@example.net')
    b, bid, hb = new_user(app, 'bob@example.net')
    c, cid, hc = new_user(app, 'charlie@example.net')
    yield app, (a, aid, ha), (b, bid, hb), (c, cid, hc)
    app.state.engine.dispose()


def test_private_preferences_not_shared_with_contact(trio):
    app, (a,aid,ha), (b,bid,hb), (c,cid,hc) = trio
    assert send(a,ha,bid).status_code == 201
    updated = a.patch(f'/api/messenger/v2/preferences/{bid}', headers=ha,
                      json={'pinned':True,'muted':True,'archived':True})
    assert updated.status_code == 200, updated.text
    own = a.get('/api/messenger/v2/chats').json()['items'][0]
    theirs = b.get('/api/messenger/v2/chats').json()['items'][0]
    assert own['pinned'] and own['muted'] and own['archived']
    assert not theirs['pinned'] and not theirs['muted'] and not theirs['archived']
    assert b.patch(f'/api/messenger/v2/preferences/{aid}', json={'archived':True}).status_code == 403
    assert a.patch(f'/api/messenger/v2/preferences/{aid}', headers=ha, json={'pinned':True}).status_code == 422
    assert a.patch(f'/api/messenger/v2/preferences/{cid}', headers=ha, json={'pinned':True}).status_code == 200


def test_replies_and_search_only_visible_to_participants(trio):
    app, (a,aid,ha), (b,bid,hb), (c,cid,hc) = trio
    original = send(a,ha,bid,'Мой секретный альбом').json()['id']
    response = b.post('/api/messenger/v2/send', headers=hb,
                      json={'contact_id':aid,'body':'Смотрю','reply_to_id':original})
    assert response.status_code==201,response.text
    assert response.json()['reply_to']['body']=='Мой секретный альбом'
    matches = a.get(f'/api/messenger/v2/search/{bid}?q=секретный').json()['items']
    assert len(matches)==1 and matches[0]['id']==original
    assert c.get(f'/api/messenger/v2/search/{aid}?q=секретный').json()['items']==[]
    assert b.post('/api/messenger/v2/send', headers=hb,
                  json={'contact_id':cid,'body':'Hi','reply_to_id':original}).status_code==404
    assert c.get(f'/api/messenger/v2/thread/{bid}').json()['items']==[]
    assert a.delete(f'/api/messenger/v2/message/{original}',headers=ha).status_code == 200
    assert not a.get(f'/api/messenger/v2/search/{bid}?q=секретный').json()['items']
    assert b.post('/api/messenger/v2/send', headers=hb,
                  json={'contact_id':aid,'body':'Hi','reply_to_id':original}).status_code==409


def test_group_membership_create_send_read_and_leave(trio):
    app, (a,aid,ha), (b,bid,hb), (c,cid,hc) = trio
    result = a.post('/api/messenger/v2/groups',headers=ha,
                    json={'name':'Vainah Team','emails':['bob@example.net']})
    assert result.status_code==201,result.text
    gid=result.json()['id']
    assert b.get('/api/messenger/v2/groups').json()['items'][0]['name']=='Vainah Team'
    assert c.get('/api/messenger/v2/groups').json()['items']==[]
    assert c.get(f'/api/messenger/v2/groups/{gid}').status_code==404
    assert c.get(f'/api/messenger/v2/groups/{gid}/messages').status_code==404
    assert c.post(f'/api/messenger/v2/groups/{gid}/send', headers=hc,json={'body':'bad'}).status_code==404
    assert c.post(f'/api/messenger/v2/groups/{gid}/read', headers=hc).status_code==404
    assert a.post(f'/api/messenger/v2/groups/{gid}/send', headers=ha,json={'body':'Добро пожаловать!'}).status_code==201
    assert b.get('/api/messenger/v2/groups').json()['items'][0]['unread']==1
    msgs=b.get(f'/api/messenger/v2/groups/{gid}/messages').json()['items']
    assert len(msgs)==1 and msgs[0]['sender']=='alice'
    assert b.post(f'/api/messenger/v2/groups/{gid}/read',headers=hb).status_code==200
    assert b.get('/api/messenger/v2/groups').json()['items'][0]['unread']==0
    assert b.post(f'/api/messenger/v2/groups/{gid}/invite',headers=hb,json={'email':'charlie@example.net'}).status_code==403
    assert a.post(f'/api/messenger/v2/groups/{gid}/invite',headers=ha,json={'email':'charlie@example.net'}).status_code==200
    assert c.get(f'/api/messenger/v2/groups/{gid}').json()['members']==3
    assert b.delete(f'/api/messenger/v2/groups/{gid}/leave',headers=hb).status_code==200
    assert b.get(f'/api/messenger/v2/groups/{gid}/messages').status_code==404
    assert a.delete(f'/api/messenger/v2/groups/{gid}/leave',headers=ha).status_code==409
    assert c.delete(f'/api/messenger/v2/groups/{gid}',headers=hc).status_code==403
    assert a.delete(f'/api/messenger/v2/groups/{gid}',headers=ha).status_code==200
    assert c.get(f'/api/messenger/v2/groups/{gid}/messages').status_code==404


def test_group_admin_checks_duplicates_block_and_csrf(trio):
    app, (a,aid,ha), (b,bid,hb), (c,cid,hc) = trio
    assert b.put(f'/api/messenger/v2/block/{aid}',headers=hb).status_code==200
    blocked=a.post('/api/messenger/v2/groups',headers=ha,
                   json={'name':'Test Group','emails':['bob@example.net']})
    assert blocked.status_code==403
    assert b.delete(f'/api/messenger/v2/block/{aid}',headers=hb).status_code==200
    res=a.post('/api/messenger/v2/groups', headers=ha,
               json={'name':'Test Group','emails':['bob@example.net','bob@example.net']})
    assert res.status_code==201,res.text
    gid=res.json()['id'];assert res.json()['members']==2
    assert a.post(f'/api/messenger/v2/groups/{gid}/invite', headers=ha,
                  json={'email':'bob@example.net'}).status_code==409
    assert a.post(f'/api/messenger/v2/groups/{gid}/invite',headers=ha,
                  json={'email':'nobody@example.net'}).status_code==404
    assert a.post(f'/api/messenger/v2/groups/{gid}/send',json={'body':'hacked'}).status_code==403
    assert a.post(f'/api/messenger/v2/groups/{gid}/send',headers=ha,json={'body':'   '}).status_code==422
    assert a.post('/api/messenger/v2/groups',headers=ha,
                  json={'name':' ','emails':[]}).status_code==422
    assert a.post(f'/api/messenger/v2/groups/{gid}/invite',headers=ha,
                  json={'email':'charlie@example.net'}).status_code==200
    assert c.get(f'/api/messenger/v2/groups/{gid}').status_code==200


def test_audio_webm_signature_and_media_permissions(trio):
    app, (a,aid,ha), (b,bid,hb), (c,cid,hc) = trio
    # EBML/WebM header; audio is always served as non-executable media.
    payload=bytes.fromhex('1a45dfa3')+b'payload for sample'
    file=a.post('/api/messenger/v2/send-file',headers=ha,data={'contact_id':bid},
                files={'file':('voice.webm',payload,'audio/webm')})
    assert file.status_code==201,file.text
    url=file.json()['attachment']['url']
    assert b.get(url).content==payload
    assert c.get(url).status_code==404

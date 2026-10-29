"""Regression tests for the 0.5 direct-chat features and privacy boundaries."""
import pytest
from fastapi.testclient import TestClient
from services.api.app.main import create_app


@pytest.fixture()
def app(tmp_path):
    instance = create_app(f"sqlite:///{tmp_path / 'messenger.db'}")
    yield instance
    instance.state.engine.dispose()


def new_user(app, email):
    c = TestClient(app)
    r = c.post('/api/auth/register', json={
        'email': email, 'display_name': email.split('@')[0], 'password': 'very-long-private-password',
    })
    assert r.status_code == 201, r.text
    return c, r.json()['user']['id'], {'X-CSRF-Token': r.json()['csrf_token']}


def send(c, headers, peer, body='Привет'):
    return c.post('/api/messenger/v2/send', json={'contact_id': peer, 'body': body}, headers=headers)


def test_send_chats_read_and_reactions(app):
    a, alice, ha = new_user(app,'alice@example.net')
    b, bob, hb = new_user(app,'bob@example.net')
    res=send(a,ha,bob,'Салам!')
    assert res.status_code == 201,res.text
    msg=res.json(); assert msg['read_at'] is None
    assert msg['body']=='Салам!'
    assert b.get('/api/messenger/v2/chats').json()['items'][0]['unread']==1
    thread=b.get(f'/api/messenger/v2/thread/{alice}').json()
    assert thread['items'][0]['mine'] is False
    assert b.post(f'/api/messenger/v2/thread/{alice}/read',headers=hb).json()['read_count']==1
    assert b.get('/api/messenger/v2/chats').json()['items'][0]['unread']==0
    assert a.get(f'/api/messenger/v2/thread/{bob}').json()['items'][0]['read_at'] is not None
    assert b.put(f'/api/messenger/v2/message/{msg["id"]}/reaction',json={'emoji':'❤️'},headers=hb).status_code==200
    assert a.get(f'/api/messenger/v2/thread/{bob}').json()['items'][0]['reactions'][0]['emoji']=='❤️'
    assert b.put(f'/api/messenger/v2/message/{msg["id"]}/reaction',json={'emoji':'❤️'},headers=hb).status_code==200
    assert not a.get(f'/api/messenger/v2/thread/{bob}').json()['items'][0]['reactions']


def test_edit_and_delete_ownership(app):
    a, alice, ha = new_user(app,'alice@example.net')
    b, bob, hb = new_user(app,'bob@example.net')
    c, charlie, hc = new_user(app,'charlie@example.net')
    msg=send(a,ha,bob).json()['id']
    assert b.patch(f'/api/messenger/v2/message/{msg}',json={'body':'Подмена'},headers=hb).status_code==404
    assert c.delete(f'/api/messenger/v2/message/{msg}',headers=hc).status_code==404
    assert c.get(f'/api/messenger/v2/thread/{bob}').json()['items']==[]
    assert a.patch(f'/api/messenger/v2/message/{msg}',json={'body':'Изменено'},headers=ha).status_code==200
    assert b.get(f'/api/messenger/v2/thread/{alice}').json()['items'][0]['edited_at'] is not None
    assert a.delete(f'/api/messenger/v2/message/{msg}',headers=ha).status_code==200
    assert b.get(f'/api/messenger/v2/thread/{alice}').json()['items'][0]['deleted'] is True
    assert b.get(f'/api/messenger/v2/thread/{alice}').json()['items'][0]['body']==''
    assert a.patch(f'/api/messenger/v2/message/{msg}',json={'body':'Нельзя'},headers=ha).status_code==409
    assert b.put(f'/api/messenger/v2/message/{msg}/reaction',json={'emoji':'🔥'},headers=hb).status_code==409


def test_blocks_apply_to_old_and_new_api(app):
    a, alice, ha = new_user(app,'alice@example.net')
    b, bob, hb = new_user(app,'bob@example.net')
    assert b.put(f'/api/messenger/v2/block/{alice}',headers=hb).status_code==200
    assert send(a,ha,bob).status_code==403
    assert a.post('/api/messenger/send',json={'email':'bob@example.net','body':'bypass'},headers=ha).status_code==403
    assert send(b,hb,alice).status_code==403
    assert b.delete(f'/api/messenger/v2/block/{alice}',headers=hb).status_code==200
    assert send(a,ha,bob).status_code==201
    assert a.put(f'/api/messenger/v2/block/{alice}',headers=ha).status_code==422


def test_file_privacy_and_deletion(app):
    a, alice, ha = new_user(app,'alice@example.net')
    b, bob, hb = new_user(app,'bob@example.net')
    c, charlie, hc = new_user(app,'charlie@example.net')
    png=b'\x89PNG\r\n\x1a\n'+b'mock-content'
    res=a.post('/api/messenger/v2/send-file',headers=ha,data={'contact_id':bob},files={'file':('image.png',png,'image/png')})
    assert res.status_code==201,res.text
    message=res.json();attachment=message['attachment'];uri=attachment['url']
    assert a.get(uri).content==png and b.get(uri).content==png
    assert c.get(uri).status_code==404
    assert b.delete('/api/messenger/v2/message/'+message['id'],headers=hb).status_code==404
    assert a.delete('/api/messenger/v2/message/'+message['id'],headers=ha).status_code==200
    assert b.get(uri).status_code==404
    assert a.get('/api/messenger/v2/thread/'+bob).json()['items'][0]['deleted'] is True
    assert a.post('/api/messenger/v2/send-file',headers=ha,data={'contact_id':bob},files={'file':('bad.png',b'not-a-png','image/png')}).status_code==415


def test_report_access_and_csrf(app):
    a, alice, ha = new_user(app,'alice@example.net')
    b, bob, hb = new_user(app,'bob@example.net')
    c, charlie, hc = new_user(app,'charlie@example.net')
    msg=send(a,ha,bob).json()['id']
    assert b.post('/api/messenger/v2/report',json={'message_id':msg,'reason':'Нежелательное сообщение'},headers=hb).status_code==201
    assert a.post('/api/messenger/v2/report',json={'message_id':msg,'reason':'Нежелательное сообщение'},headers=ha).status_code==404
    assert c.post('/api/messenger/v2/report',json={'message_id':msg,'reason':'Нежелательное сообщение'},headers=hc).status_code==404
    assert b.post('/api/messenger/v2/thread/'+alice+'/read').status_code==403
    assert a.put('/api/messenger/v2/message/'+msg+'/reaction',json={'emoji':'<script>'},headers=ha).status_code==422


def test_existing_suite_and_manifest_routes_survive(app):
    a, alice, ha = new_user(app,'alice@example.net')
    assert a.get('/api/health').json()['version']=='0.7.0'
    assert a.get('/app/messenger').status_code==200
    assert a.get('/app/notes').status_code==200
    assert a.get('/api/notes').status_code==200

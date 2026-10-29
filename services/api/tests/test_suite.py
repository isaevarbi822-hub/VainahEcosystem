"""Integration checks for all eleven application modules and identity isolation."""
import io
import pytest
from fastapi.testclient import TestClient
from services.api.app.main import create_app
from services.api.app import integrations


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("VAINAH_UPLOAD_DIR", str(tmp_path / "uploads"))
    app = create_app(f"sqlite:///{tmp_path / 'apps.db'}")
    with TestClient(app) as client:
        yield client
    app.state.engine.dispose()


def register(client, email):
    r = client.post("/api/auth/register", json={
        "email": email, "display_name": email.split('@')[0], "password": "super-long-test-password"})
    assert r.status_code == 201, r.text
    return r.json()["user"]


def csrf(client):
    return {"X-CSRF-Token": client.get("/api/auth/me").json()["csrf_token"]}


@pytest.mark.parametrize("kind,payload", [
    ("calendar", {"title": "Встреча", "date": "2026-11-01", "time": "14:30", "description": "Описание"}),
    ("study", {"title": "Алгебра", "subject": "Математика", "due": "2026-11-02", "details": "x+2=3", "done": False}),
    ("bookmarks", {"title": "Example", "url": "https://example.org"}),
    ("places", {"name": "Oslo", "latitude": 59.9139, "longitude": 10.7522}),
    ("playlists", {"name": "My songs", "tracks": []}),
])
def test_app_records_crud(client, kind, payload):
    register(client, "alice@example.com")
    h=csrf(client)
    r=client.post(f"/api/data/{kind}",json={"payload":payload},headers=h)
    assert r.status_code == 201,r.text
    pk=r.json()["id"]
    assert client.get(f"/api/data/{kind}").json()["items"][0]["id"]==pk
    assert client.put(f"/api/data/{kind}/{pk}",json={"payload":payload},headers=h).status_code==200
    assert client.delete(f"/api/data/{kind}/{pk}",headers=h).status_code==200
    assert not client.get(f"/api/data/{kind}").json()["items"]


def test_app_records_private_and_validation(client):
    register(client,'alice@example.com'); headers=csrf(client)
    assert client.post('/api/data/bookmarks',json={'payload':{'title':'X','url':'javascript:alert(1)'}},headers=headers).status_code==422
    assert client.post('/api/data/study',json={'payload':{'title':'X','unexpected':'x'}},headers=headers).status_code==422
    assert client.post('/api/data/calendar',json={'payload':{'date':'2026/11/01'}},headers=headers).status_code==422
    assert client.post('/api/data/places',json={'payload':{'latitude':999,'longitude':3}},headers=headers).status_code==422
    assert client.post('/api/data/calendar',json={'payload':{'title':'X'}},headers={}).status_code==403
    result=client.post('/api/data/calendar',json={'payload':{'title':'Alice birthday'}},headers=headers)
    pk=result.json()['id']
    client.post('/api/auth/logout',headers=headers)
    register(client,'bob@example.com');headers=csrf(client)
    assert client.get('/api/data/calendar').json()['items']==[]
    assert client.delete(f'/api/data/calendar/{pk}',headers=headers).status_code==404
    assert client.put(f'/api/data/calendar/{pk}',json={'payload':{'title':'mine'}},headers=headers).status_code==404


def test_messenger_messages_private(client):
    alice=register(client,'alice@example.com'); ca=csrf(client)
    client.post('/api/auth/logout',headers=ca)
    bob=register(client,'bob@example.com'); cb=csrf(client)
    client.post('/api/auth/logout',headers=cb)
    charlie=register(client,'charlie@example.com'); cc=csrf(client)
    assert client.get(f'/api/messenger/thread/{bob["id"]}').json()['items']==[]
    client.post('/api/auth/logout',headers=cc)
    client.post('/api/auth/login',json={'email':'alice@example.com','password':'super-long-test-password'})
    ca=csrf(client)
    assert client.post('/api/messenger/send',json={'email':'bob@example.com','body':'Привет'},headers=ca).status_code==201
    assert len(client.get(f'/api/messenger/thread/{bob["id"]}').json()['items'])==1
    client.post('/api/auth/logout',headers=ca)
    client.post('/api/auth/login',json={'email':'charlie@example.com','password':'super-long-test-password'})
    assert client.get(f'/api/messenger/thread/{bob["id"]}').json()['items']==[]
    assert client.get('/api/messenger/contacts').json()['items']==[]
    client.post('/api/auth/logout',headers=csrf(client))
    client.post('/api/auth/login',json={'email':'bob@example.com','password':'super-long-test-password'})
    assert client.get(f'/api/messenger/thread/{alice["id"]}').json()['items'][0]['body']=='Привет'


def test_media_upload_download_private(client):
    register(client,'alice@example.com');head=csrf(client)
    file_content=b'\x89PNG\r\n\x1a\n'+b'safe-test-png-data'
    res=client.post('/api/media/photo',files={'file':('pic.png',file_content,'image/png')},headers=head)
    assert res.status_code==201,res.text
    fid=res.json()['id'];assert client.get(f'/api/media/file/{fid}').content==file_content
    assert len(client.get('/api/media/photo').json()['items'])==1
    assert client.post('/api/media/audio',files={'file':('foo.mp3',b'not audio','audio/mpeg')},headers=head).status_code==415
    assert client.post('/api/media/photo',files={'file':('wrong.png',b'wrong','image/png')},headers=head).status_code==415
    client.post('/api/auth/logout',headers=head)
    register(client,'bob@example.com');head=csrf(client)
    assert client.get(f'/api/media/file/{fid}').status_code==404
    assert client.delete(f'/api/media/file/{fid}',headers=head).status_code==404
    assert client.get('/api/media/photo').json()['items']==[]


def test_audio_upload_and_delete(client):
    register(client,'alice@example.com');head=csrf(client)
    content=b'ID3'+b'\x00'*24
    res=client.post('/api/media/audio',files={'file':('mine.mp3',content,'audio/mpeg')},headers=head)
    assert res.status_code==201,res.text
    pk=res.json()['id'];assert client.get('/api/media/file/'+pk).content==content
    assert client.delete('/api/media/file/'+pk,headers=head).status_code==200
    assert client.get('/api/media/file/'+pk).status_code==404


def test_weather_geocoding_and_translation_with_mock(client, monkeypatch):
    register(client,'alice@example.com')
    def mocked(url, params=None, **kwargs):
        if 'geocoding' in url: return {'results':[{'name':'Oslo','country':'Norway','latitude':59.9,'longitude':10.7}]}
        if 'forecast' in url: return {'current':{'temperature_2m':11},'daily':{'time':['2026-10-29']}}
        return {'responseData':{'translatedText':'Hello'}}
    monkeypatch.setattr(integrations,'remote_json',mocked)
    assert client.get('/api/location/search?city=Oslo').json()['items'][0]['name']=='Oslo'
    assert client.get('/api/weather?latitude=59.9&longitude=10.7').json()['current']['temperature_2m']==11
    assert client.post('/api/translate',json={'text':'Привет','source':'ru','target':'en'},headers=csrf(client)).json()['translation']=='Hello'
    assert client.post('/api/translate',json={'text':'x','source':'ru','target':'ru'},headers=csrf(client)).status_code==422
    assert client.get('/api/weather?latitude=999&longitude=3').status_code==422


def test_ai_model_status_and_unconfigured_message(client,monkeypatch):
    register(client,'alice@example.com')
    for key in ('VAINAH_AI_BASE_URL','VAINAH_AI_API_KEY','VAINAH_AI_MODEL'):monkeypatch.delenv(key,raising=False)
    assert client.get('/api/ai/status').json()['configured'] is False
    response=client.post('/api/ai/chat',json={'prompt':'привет'},headers=csrf(client))
    assert response.status_code==503
    assert 'не подключена' in response.text


def test_app_routes_require_login(client):
    for url in ('/api/data/study','/api/media/photo','/api/messenger/contacts','/api/ai/status','/api/location/search?city=Oslo'):
        assert client.get(url).status_code==401


def test_all_eleven_pwa_routes(client):
    for name in ('ai','messenger','browser','music','weather','maps','notes','translate','study','photos','calendar'):
        page=client.get(f'/app/{name}')
        assert page.status_code==200
        assert f'/manifests/{name}.webmanifest' in page.text
        manifest=client.get(f'/manifests/{name}.webmanifest')
        assert manifest.status_code==200
        assert manifest.json()['start_url']==f'/app/{name}'
        for icon in manifest.json()['icons']:
            assert client.get(icon['src']).status_code==200
    assert client.get('/app/nothing').status_code==404
    assert client.get('/manifests/nothing.webmanifest').status_code==404
    assert client.get('/assets/suite-ui.js').status_code==200
    assert 'id="screen-feature"' in client.get('/').text

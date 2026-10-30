"""Apple OAuth native handoff security contracts; Apple network verification is mocked."""
import base64
import hashlib
from fastapi.testclient import TestClient
from services.api.app.main import create_app
from services.api.app import apple_login

def setup_apple(monkeypatch):
    values={
        "APP_ORIGIN":"https://vainahecosystem.onrender.com",
        "APPLE_SERVICE_ID":"no.vainah.apple.test",
        "APPLE_TEAM_ID":"TESTTEAMID",
        "APPLE_KEY_ID":"TESTKEYID",
        "APPLE_PRIVATE_KEY_P8":"dummy-test-key",
        "APPLE_REDIRECT_URI":"https://vainahecosystem.onrender.com/api/auth/apple/callback",
        "VAINAH_SIGNUP_MODE":"open",
    }
    for key,value in values.items():monkeypatch.setenv(key,value)

def proof(verifier):
    return base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()

def test_apple_requires_server_developer_config(tmp_path,monkeypatch):
    for key in ("APPLE_SERVICE_ID","APPLE_TEAM_ID","APPLE_KEY_ID","APPLE_PRIVATE_KEY_P8","APPLE_REDIRECT_URI"):
        monkeypatch.delenv(key,raising=False)
    app=create_app(f"sqlite:///{tmp_path/'apple-off.db'}")
    with TestClient(app) as client:
        assert client.get("/api/auth/apple/config").json()=={"enabled":False}
        res=client.post("/api/auth/apple/start",json={"challenge":"a"*43})
        assert res.status_code==503
    app.state.engine.dispose()

def test_apple_native_one_time_proof_no_session_leak(tmp_path,monkeypatch):
    setup_apple(monkeypatch)
    seen=[]
    def fake_verify(code,nonce):
        seen.append((code,nonce))
        return {"sub":"apple-sub-123","email":"relay@privaterelay.appleid.com"}
    monkeypatch.setattr(apple_login,"verify_apple_code",fake_verify)
    app=create_app(f"sqlite:///{tmp_path/'apple-native.db'}")
    with TestClient(app) as client:
        verifier="Q"*54
        start=client.post("/api/auth/apple/start",json={"challenge":proof(verifier)})
        assert start.status_code==200,start.text
        url=start.json()["url"]
        state=start.json()["state"]
        assert "https://appleid.apple.com/auth/authorize" in url
        assert client.get("/api/auth/apple/config").json()=={"enabled":True}
        assert client.post("/api/auth/apple/exchange",json={"state":state,"verifier":verifier}).status_code==401
        callback=client.post("/api/auth/apple/callback",data={"code":"sample-valid-code","state":state})
        assert callback.status_code==200,callback.text
        assert "vainah-messenger://auth/apple?state=" in callback.text
        assert "sample-valid-code" not in callback.text
        assert "vainah_session" not in callback.text
        assert len(seen)==1
        bad=client.post("/api/auth/apple/exchange",json={"state":state,"verifier":"x"*40})
        assert bad.status_code==403,bad.text
        good=client.post("/api/auth/apple/exchange",json={"state":state,"verifier":verifier})
        assert good.status_code==200,good.text
        assert good.json()["user"]["email"]=="relay@privaterelay.appleid.com"
        assert "vainah_session=" in good.headers.get("set-cookie","")
        assert client.get("/api/auth/me").status_code==200
        assert client.post("/api/auth/apple/exchange",json={"state":state,"verifier":verifier}).status_code==401
        assert client.post("/api/auth/apple/callback",data={"code":"sample-valid-code","state":state}).status_code==400
    app.state.engine.dispose()

def test_apple_does_not_auto_link_existing_email(tmp_path,monkeypatch):
    setup_apple(monkeypatch)
    monkeypatch.setattr(apple_login,"verify_apple_code",lambda code,nonce: {
        "sub":"another-apple-id","email":"already@example.net"})
    app=create_app(f"sqlite:///{tmp_path/'apple-collision.db'}")
    with TestClient(app) as client:
        register=client.post("/api/auth/register",json={
            "email":"already@example.net","password":"safe-password-123","display_name":"Existing"})
        assert register.status_code==201
        verifier="S"*54
        start=client.post("/api/auth/apple/start",json={"challenge":proof(verifier)})
        assert start.status_code==200
        callback=client.post("/api/auth/apple/callback",data={
            "state":start.json()["state"],"code":"valid-code"})
        assert callback.status_code==409
    app.state.engine.dispose()

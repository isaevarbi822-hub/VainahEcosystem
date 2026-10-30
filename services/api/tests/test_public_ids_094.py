"""Vainah Messenger 0.9.4 permanent numeric account IDs."""
import re
import pytest
from sqlalchemy import select
from fastapi.testclient import TestClient
from services.api.app.main import create_app
from services.api.app import public_ids
from services.api.app.public_ids import VainahPublicId
from services.api.tests.test_messenger_050 import new_user

@pytest.fixture
def app(tmp_path):
    app=create_app(f"sqlite:///{tmp_path/'numeric-ids.db'}")
    yield app
    app.state.engine.dispose()

def test_unique_numeric_ids_are_stable_on_login_and_username_change(app):
    a,aid,ha=new_user(app,"alice@example.net")
    b,bid,hb=new_user(app,"bob@example.net")
    first=a.get("/api/auth/me").json()["user"]["vainah_id"]
    second=b.get("/api/auth/me").json()["user"]["vainah_id"]
    assert re.fullmatch(r"[1-9][0-9]{9}",first)
    assert re.fullmatch(r"[1-9][0-9]{9}",second)
    assert first != second
    assert first != aid
    assert a.get("/api/people/me").json()["vainah_id"]==first
    assert a.get("/api/people/me").json()["vainah_id"]==first
    renamed=a.put("/api/people/username",headers=ha,json={"username":"alice_vainah"})
    assert renamed.status_code==200
    assert a.get("/api/people/me").json()["vainah_id"]==first
    assert a.get("/api/auth/me").json()["user"]["vainah_id"]==first
    login=TestClient(app)
    response=login.post("/api/auth/login",json={
        "email":"alice@example.net","password":"very-long-private-password"})
    assert response.status_code==200
    assert response.json()["user"]["vainah_id"]==first
    exact=b.get("/api/people/id/"+first)
    assert exact.status_code==200
    assert exact.json()["person"]["id"]==aid
    assert exact.json()["person"]["display_name"]=="alice"
    assert b.get("/api/people/id/"+first[:8]).status_code==404
    assert a.get("/api/people/id/"+first).status_code==404
    assert a.put(f"/api/messenger/v2/block/{bid}",headers=ha).status_code==200
    assert b.get("/api/people/id/"+first).status_code==404

def test_existing_users_without_id_get_one_on_next_authenticated_read(app):
    a,aid,ha=new_user(app,"alice@example.net")
    with app.state.session_factory() as db:
        row=db.get(VainahPublicId,aid)
        assert row is not None
        db.delete(row)
        db.commit()
    first=a.get("/api/people/me")
    assert first.status_code==200
    numeric=first.json()["vainah_id"]
    assert len(numeric)==10
    assert a.get("/api/auth/me").json()["user"]["vainah_id"]==numeric

def test_colliding_numeric_id_is_retried_without_reassigning_another_user(app,monkeypatch):
    a,aid,ha=new_user(app,"alice@example.net")
    current=a.get("/api/people/me").json()["vainah_id"]
    b,bid,hb=new_user(app,"bob@example.net")
    with app.state.session_factory() as db:
        db.delete(db.get(VainahPublicId,bid))
        db.commit()
    # Monkeypatch only the random number generator, never the DB's unique constraint.
    desired="6999999999"
    choices=iter([int(current)-1_000_000_000,int(desired)-1_000_000_000])
    monkeypatch.setattr(public_ids.secrets,"randbelow",lambda n:next(choices))
    generated=b.get("/api/people/me")
    assert generated.status_code==200,generated.text
    assert generated.json()["vainah_id"]==desired
    assert a.get("/api/people/me").json()["vainah_id"]==current
    with app.state.session_factory() as db:
        records=db.scalars(select(VainahPublicId)).all()
        assert {record.public_id for record in records}=={current,desired}

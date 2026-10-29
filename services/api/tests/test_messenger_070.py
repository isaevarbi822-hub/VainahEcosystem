"""WebSocket event authentication, live messaging and call authorization."""
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect
from services.api.app.main import create_app
from services.api.tests.test_messenger_050 import new_user, send


@pytest.fixture
def clients(tmp_path):
    app = create_app(f"sqlite:///{tmp_path / 'realtime.db'}")
    alice, aid, ha = new_user(app, "alice@example.net")
    bob, bid, hb = new_user(app, "bob@example.net")
    stranger, sid, hs = new_user(app, "stranger@example.net")
    yield app, (alice, aid, ha), (bob, bid, hb), (stranger, sid, hs)
    app.state.engine.dispose()


def ws(c):
    return c.websocket_connect('/api/messenger/v2/live', headers={'origin':'http://testserver'})


def test_rejects_missing_origin_and_unauthenticated(clients):
    app, (a, aid, ha), (b, bid, hb), _ = clients
    with pytest.raises(WebSocketDisconnect):
        with a.websocket_connect('/api/messenger/v2/live'):
            pass
    with pytest.raises(WebSocketDisconnect):
        with a.websocket_connect('/api/messenger/v2/live', headers={'origin':'https://attacker.invalid'}):
            pass
    with pytest.raises(WebSocketDisconnect):
        with TestClient(app).websocket_connect('/api/messenger/v2/live',headers={'origin':'http://testserver'}):
            pass


def test_auth_live_delivery_and_private_call_invitation(clients):
    app, (a, aid, ha), (b, bid, hb), (c, cid, hc) = clients
    with ws(a) as wa, ws(b) as wb, ws(c) as wc:
        assert wa.receive_json()['type'] == 'ready'
        assert wb.receive_json()['type'] == 'ready'
        assert wc.receive_json()['type'] == 'ready'
        result = send(a, ha, bid, 'Привет в реальном времени')
        assert result.status_code == 201
        # Both participants are notified; no broadcast to unrelated users.
        assert wa.receive_json()['type'] == 'message.changed'
        assert wb.receive_json()['type'] == 'message.changed'
        assert c.get(f'/api/messenger/v2/thread/{bid}').json()['items'] == []
        wc.send_json({'type':'call.accept','call_id':result.json()['id']})
        assert wc.receive_json()['type'] == 'error'
        wa.send_json({'type':'call.invite','to':bid,'media':'video'})
        ringing = wa.receive_json()
        incoming = wb.receive_json()
        assert ringing['type'] == 'call.ringing'
        assert incoming['type'] == 'call.incoming'
        assert incoming['name'] == 'alice'
        call_id = ringing['call_id']
        assert incoming['call_id'] == call_id
        wc.send_json({'type':'call.signal','call_id':call_id,'signal':{'type':'offer','sdp':'forged'}})
        assert wc.receive_json()['type'] == 'error'
        wb.send_json({'type':'call.accept','call_id':call_id})
        assert wa.receive_json()['type'] == 'call.accepted'
        assert wb.receive_json()['type'] == 'call.accepted'
        wa.send_json({'type':'call.signal','call_id':call_id,'signal':{'type':'offer','sdp':'safe test SDP'}})
        event = wb.receive_json()
        assert event['type'] == 'call.signal' and event['signal']['sdp'] == 'safe test SDP'
        wb.send_json({'type':'call.end','call_id':call_id})
        assert wa.receive_json()['type'] == 'call.ended'
        assert wb.receive_json()['type'] == 'call.ended'


def test_block_and_busy_checks(clients):
    app, (a, aid, ha), (b, bid, hb), (c, cid, hc) = clients
    assert b.put(f'/api/messenger/v2/block/{aid}', headers=hb).status_code == 200
    with ws(a) as wa, ws(b) as wb:
        wa.receive_json();wb.receive_json()
        wa.send_json({'type':'call.invite','to':bid,'media':'audio'})
        assert wa.receive_json()['type'] == 'call.unavailable'
        # Invalid media and recipient never generate invitations.
        wa.send_json({'type':'call.invite','to':cid,'media':'screenshare'})
        wa.send_json({'type':'ping'})
        assert wa.receive_json()['type'] == 'pong'

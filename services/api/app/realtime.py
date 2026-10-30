"""Vainah Messenger v0.7: authenticated WebSocket live updates and WebRTC signalling.

Transport is intentionally single-process (Render: one Uvicorn worker). It is
NOT a push service and does not provide end-to-end encryption or TURN relay.
"""
from __future__ import annotations

import asyncio
import hmac
import os
import time
from collections import defaultdict, deque
from dataclasses import dataclass
from urllib.parse import urlsplit
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy import select
from .models import LoginSession, User
from .security import COOKIE_NAME, token_digest
from .messenger import block_exists

router = APIRouter(tags=["Messenger live"])


def correct_origin(ws: WebSocket) -> bool:
    origin = ws.headers.get("origin", "")
    if not origin:
        return False  # Browser connects always send Origin; reject unknown native clients.
    configured = os.getenv("APP_ORIGIN", "").strip().rstrip("/")
    expected = configured or f"{'https' if ws.url.scheme == 'wss' else 'http'}://{ws.headers.get('host', '')}"
    try:
        a, b = urlsplit(origin), urlsplit(expected)
        return a.scheme == b.scheme and a.netloc == b.netloc and a.path in ("", "/")
    except ValueError:
        return False


def session_user(ws: WebSocket) -> str | None:
    token = ws.cookies.get(COOKIE_NAME)
    if not token or len(token) > 256:
        return None
    with ws.app.state.session_factory() as db:
        record = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(token)))
        if not record or record.expires_at <= int(time.time()):
            return None
        user = db.get(User, record.user_id)
        return user.id if user else None


@dataclass
class Call:
    id: str
    caller: str
    callee: str
    media: str
    status: str
    created_at: float

    def participants(self) -> tuple[str, str]:
        return self.caller, self.callee


class LiveHub:
    def __init__(self) -> None:
        self.clients: dict[str, set[WebSocket]] = defaultdict(set)
        self.loops: dict[WebSocket, asyncio.AbstractEventLoop] = {}
        self.calls: dict[str, Call] = {}
        self.rate: dict[str, deque[float]] = defaultdict(deque)

    async def join(self, user: str, ws: WebSocket) -> None:
        self.loops[ws] = asyncio.get_running_loop()
        self.clients[user].add(ws)

    def leave(self, user: str, ws: WebSocket) -> None:
        self.clients[user].discard(ws)
        self.loops.pop(ws, None)
        if not self.clients[user]:
            self.clients.pop(user, None)
            # End live calls if no device remains online; notify remaining party.
            for call in list(self.calls.values()):
                if user in call.participants():
                    other = call.callee if call.caller == user else call.caller
                    self.publish([other], {"type": "call.ended", "call_id": call.id, "reason": "disconnected"})
                    self.calls.pop(call.id, None)

    def publish(self, users: list[str] | tuple[str, ...], payload: dict) -> None:
        """Safe to call from synchronous FastAPI endpoints running in a worker thread."""
        for user in set(users):
            for ws in tuple(self.clients.get(user, ())):
                try:
                    loop = self.loops.get(ws)
                    if loop is None or loop.is_closed():
                        continue
                    loop.call_soon_threadsafe(lambda sock=ws: asyncio.create_task(self._send(sock, payload)))
                except RuntimeError:
                    pass

    async def _send(self, ws: WebSocket, payload: dict) -> None:
        try:
            await ws.send_json(payload)
        except (RuntimeError, OSError, WebSocketDisconnect):
            pass

    def allowed_rate(self, user: str) -> bool:
        now = time.monotonic()
        q = self.rate[user]
        while q and now - q[0] > 15:
            q.popleft()
        if len(q) >= 45:
            return False
        q.append(now)
        return True

    def expire_calls(self) -> None:
        now = time.monotonic()
        for call in list(self.calls.values()):
            if (call.status == "ringing" and now - call.created_at > 75) or now - call.created_at > 7200:
                self.publish(list(call.participants()), {"type": "call.ended", "call_id": call.id, "reason": "timeout"})
                self.calls.pop(call.id, None)

    def busy(self, user: str) -> bool:
        return any(user in c.participants() for c in self.calls.values())


async def handle_action(ws: WebSocket, hub: LiveHub, user: str, data: dict) -> None:
    kind = data.get("type")
    if kind == "ping":
        await hub._send(ws, {"type": "pong"})
        return
    if not hub.allowed_rate(user):
        await hub._send(ws, {"type": "error", "message": "Слишком много запросов"})
        return
    hub.expire_calls()
    if kind == "typing":
        target = data.get("to")
        if not isinstance(target,str) or len(target)!=36 or target==user:
            return
        with ws.app.state.session_factory() as db:
            peer=db.get(User,target)
            allowed = bool(peer) and not block_exists(db,user,target) and not block_exists(db,target,user)
        if allowed and hub.clients.get(target):
            hub.publish([target],{"type":"typing","from":user})
        return
    if kind == "call.invite":
        target = data.get("to")
        media = data.get("media")
        if not isinstance(target, str) or media not in ("audio", "video") or target == user:
            return
        with ws.app.state.session_factory() as db:
            peer = db.get(User, target)
            permitted = bool(peer) and not block_exists(db, user, target) and not block_exists(db, target, user)
            source = db.get(User, user)
            label = source.display_name if source else "Контакт"
        if not permitted or hub.busy(user) or hub.busy(target) or not hub.clients.get(target):
            await hub._send(ws, {"type": "call.unavailable", "reason": "Абонент недоступен или занят"})
            return
        call = Call(str(uuid4()), user, target, media, "ringing", time.monotonic())
        hub.calls[call.id] = call
        hub.publish([user], {"type": "call.ringing", "call_id": call.id, "to": target, "media": media})
        hub.publish([target], {"type": "call.incoming", "call_id": call.id,
                               "from": user, "name": label, "media": media})
        return
    call_id = data.get("call_id")
    if not isinstance(call_id, str) or len(call_id) > 60:
        return
    call = hub.calls.get(call_id)
    if not call or user not in call.participants():
        await hub._send(ws, {"type": "error", "message": "Звонок не найден"})
        return
    other = call.callee if user == call.caller else call.caller
    if kind == "call.accept" and user == call.callee and call.status == "ringing":
        call.status = "active"
        hub.publish([call.caller, call.callee], {"type": "call.accepted", "call_id": call_id})
    elif kind in ("call.decline", "call.end"):
        hub.calls.pop(call_id, None)
        hub.publish([call.caller, call.callee], {"type": "call.ended", "call_id": call_id, "reason": "declined" if kind == "call.decline" else "ended"})
    elif kind == "call.signal" and call.status == "active":
        signal = data.get("signal")
        if not isinstance(signal, dict) or len(str(signal)) > 16000:
            return
        subtype = signal.get("type")
        if subtype not in ("offer", "answer", "candidate"):
            return
        # No SDP persistence: signalling is forwarded only to the intended party.
        hub.publish([other], {"type": "call.signal", "call_id": call_id, "from": user, "signal": signal})


@router.websocket("/api/messenger/v2/live")
async def live(ws: WebSocket):
    if not correct_origin(ws):
        await ws.close(code=1008)
        return
    user = session_user(ws)
    if not user:
        await ws.close(code=1008)
        return
    hub: LiveHub = ws.app.state.live_hub
    await ws.accept()
    await hub.join(user, ws)
    await hub._send(ws, {"type": "ready", "transport": "websocket"})
    try:
        while True:
            # Recheck login-session validity and provide a bounded silent timeout.
            try:
                raw = await asyncio.wait_for(ws.receive_text(), timeout=35)
            except asyncio.TimeoutError:
                if session_user(ws) != user:
                    await ws.close(code=1008)
                    break
                await hub._send(ws, {"type": "heartbeat"})
                continue
            if len(raw) > 16384:
                await ws.close(code=1009)
                break
            if session_user(ws) != user:
                await ws.close(code=1008)
                break
            import json
            try:
                payload = json.loads(raw)
            except ValueError:
                continue
            if isinstance(payload, dict):
                await handle_action(ws, hub, user, payload)
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(user, ws)


def notify(request, recipients: list[str], event_type: str, **details):
    hub: LiveHub | None = getattr(request.app.state, "live_hub", None)
    if hub:
        hub.publish(recipients, {"type": event_type, **details})

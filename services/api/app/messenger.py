"""Vainah Messenger: account-scoped direct chat with privacy and moderation controls.

This is SERVER-STORED messaging, not end-to-end encrypted messaging. The endpoint
layout is /api/messenger/v2 to keep existing 0.4 clients compatible.
"""
from __future__ import annotations

import os
import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import (
    DirectMessage, MessageAttachment, MessageDetails, MessageReaction,
    MessageReceipt, MessengerBlock, MessengerReport, MessengerChatPreference, MessageReply, User, VerifiedAccount, uid,
)
from .security import csrf_protect, current_user, enforce_origin
from .suite import detected_type

router = APIRouter(prefix="/api/messenger/v2", tags=["Vainah Messenger"])

def inform(request: Request, users: list[str], event: str, **kwargs) -> None:
    hub = getattr(request.app.state, "live_hub", None)
    if hub:
        hub.publish(users, {"type": event, **kwargs})

EMOJI = {"❤️", "👍", "😂", "😮", "😢", "🔥"}
MAX_UPLOAD = 5 * 1024 * 1024
ACCEPTED = {"image/jpeg", "image/png", "image/webp", "image/gif", "audio/mpeg", "audio/wav", "audio/ogg", "audio/mp4", "audio/webm"}
_SEND_TIMES: dict[str, deque] = defaultdict(deque)
_SEND_LOCK = Lock()


class SendMessage(BaseModel):
    contact_id: str = Field(min_length=36, max_length=36)
    body: str = Field(min_length=1, max_length=3000)
    reply_to_id: str | None = Field(default=None, min_length=36, max_length=36)


class EditMessage(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


class ReactionData(BaseModel):
    emoji: str = Field(min_length=1, max_length=8)


class PreferencesData(BaseModel):
    pinned: bool | None = None
    archived: bool | None = None
    muted: bool | None = None


class ReportData(BaseModel):
    message_id: str = Field(min_length=36, max_length=36)
    reason: str = Field(min_length=3, max_length=240)


def block_exists(db: Session, owner_id: str, target_id: str) -> bool:
    return db.scalar(select(MessengerBlock.id).where(
        MessengerBlock.owner_id == owner_id,
        MessengerBlock.target_id == target_id,
    )) is not None


def check_pair(db: Session, me: str, other: str, require_open: bool = True) -> User:
    if me == other:
        raise HTTPException(422, "Нельзя выбрать себя")
    peer = db.get(User, other)
    if not peer:
        raise HTTPException(404, "Контакт не найден")
    if require_open and (block_exists(db, me, other) or block_exists(db, other, me)):
        raise HTTPException(403, "Переписка с этим контактом недоступна")
    return peer


def validate_send_rate(user_id: str) -> None:
    # Private preview anti-spam guard; production needs shared Redis/edge limiting.
    if os.getenv("ENVIRONMENT", "development") != "production" and os.getenv("VAINAH_MESSAGE_RATE_LIMIT", "") != "true":
        return
    with _SEND_LOCK:
        q = _SEND_TIMES[user_id]
        ts = time.monotonic()
        while q and ts - q[0] > 60:
            q.popleft()
        if len(q) >= 25:
            raise HTTPException(429, "Слишком много сообщений. Попробуйте позже")
        q.append(ts)


def pair_filter(me: str, other: str):
    return or_(
        and_(DirectMessage.sender_id == me, DirectMessage.recipient_id == other),
        and_(DirectMessage.sender_id == other, DirectMessage.recipient_id == me),
    )


def view_message(db: Session, message: DirectMessage, viewer_id: str) -> dict:
    info = db.get(MessageDetails, message.id)
    is_deleted = bool(info and info.deleted_at)
    receipt = db.get(MessageReceipt, message.id)
    reactions = db.scalars(select(MessageReaction).where(MessageReaction.message_id == message.id)).all()
    attachment = db.scalar(select(MessageAttachment).where(MessageAttachment.message_id == message.id))
    reply = db.get(MessageReply, message.id)
    target = db.get(DirectMessage, reply.replied_to_id) if reply else None
    target_info = db.get(MessageDetails, target.id) if target else None
    reply_view = None
    if target and not (target_info and target_info.deleted_at):
        reply_view = {"id": target.id, "body": target.body[:180] or "Вложение",
                      "mine": target.sender_id == viewer_id}
    return {
        "id": message.id, "mine": message.sender_id == viewer_id,
        "body": "" if is_deleted else message.body,
        "created_at": message.created_at,
        "edited_at": info.edited_at if info and not is_deleted else None,
        "reply_to": None if is_deleted else reply_view,
        "deleted": is_deleted,
        "read_at": receipt.read_at if receipt else None,
        "reactions": [] if is_deleted else [{"emoji": r.emoji, "mine": r.user_id == viewer_id} for r in reactions],
        "attachment": None if is_deleted or not attachment else {
            "id": attachment.id, "filename": attachment.filename,
            "type": attachment.media_type, "size": attachment.size,
            "url": f"/api/messenger/v2/file/{attachment.id}",
        },
    }


@router.get("/chats")
def chats(db: Session = Depends(get_db), user: User = Depends(current_user)):
    messages = db.scalars(select(DirectMessage).where(
        or_(DirectMessage.sender_id == user.id, DirectMessage.recipient_id == user.id)
    ).order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc()).limit(1000)).all()
    # Fetch receipts in one query rather than issuing a database query per message.
    incoming = [m.id for m in messages if m.recipient_id == user.id]
    seen_ids = set(db.scalars(select(MessageReceipt.message_id).where(
        MessageReceipt.message_id.in_(incoming))).all()) if incoming else set()
    peers: dict[str, dict] = {}
    for m in messages:
        other_id = m.recipient_id if m.sender_id == user.id else m.sender_id
        if other_id not in peers:
            peers[other_id] = {"last": m, "unread": 0}
        if m.recipient_id == user.id and m.id not in seen_ids:
            peers[other_id]["unread"] += 1
    contacts = db.scalars(select(User).where(User.id.in_(peers.keys()))).all() if peers else []
    users = {u.id: u for u in contacts}
    verified_ids = set(db.scalars(select(VerifiedAccount.user_id).where(
        VerifiedAccount.user_id.in_(peers.keys()))).all()) if peers else set()
    result = []
    for peer_id, info in peers.items():
        peer = users.get(peer_id)
        if not peer:
            continue
        last = info["last"]
        metadata = db.get(MessageDetails, last.id)
        attachment = db.scalar(select(MessageAttachment).where(MessageAttachment.message_id == last.id))
        preview = "Сообщение удалено" if metadata and metadata.deleted_at else last.body[:110] or ("📎 Вложение" if attachment else "")
        prefs = db.scalar(select(MessengerChatPreference).where(
            MessengerChatPreference.user_id == user.id, MessengerChatPreference.contact_id == peer_id))
        result.append({
            "pinned": bool(prefs and prefs.pinned),
            "archived": bool(prefs and prefs.archived),
            "muted": bool(prefs and prefs.muted),
            "id": peer.id, "display_name": peer.display_name, "email": peer.email,
            "preview": preview, "updated_at": last.created_at,
            "unread": info["unread"], "blocked": block_exists(db, user.id, peer.id),
            "verified": peer_id in verified_ids,
        })
    result.sort(key=lambda c: (not c["pinned"], -c["updated_at"], c["id"]))
    return {"items": result}


@router.patch("/preferences/{contact_id}", dependencies=[Depends(csrf_protect)])
def update_preferences(contact_id: str, data: PreferencesData, request: Request,
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_pair(db, user.id, contact_id, require_open=False)
    row = db.scalar(select(MessengerChatPreference).where(
        MessengerChatPreference.user_id == user.id,
        MessengerChatPreference.contact_id == contact_id))
    if row is None:
        row = MessengerChatPreference(user_id=user.id, contact_id=contact_id)
        db.add(row)
    for key in ("pinned", "archived", "muted"):
        value = getattr(data, key)
        if value is not None:
            setattr(row, key, value)
    db.commit()
    return {"pinned": row.pinned, "archived": row.archived, "muted": row.muted}


@router.get("/search/{contact_id}")
def search_messages(contact_id: str, q: str, db: Session = Depends(get_db),
                    user: User = Depends(current_user)):
    check_pair(db, user.id, contact_id, require_open=False)
    q = q.strip()
    if len(q) < 2 or len(q) > 80:
        raise HTTPException(422, "Поисковый запрос от 2 до 80 символов")
    # Literal substring matching: SQL wildcard characters are not search operators.
    escaped = q.replace(chr(92), chr(92)*2).replace("%", chr(92)+"%").replace("_", chr(92)+"_")
    matches = db.scalars(select(DirectMessage).where(
        pair_filter(user.id, contact_id),
        DirectMessage.body.ilike(f"%{escaped}%", escape=chr(92)),
    ).order_by(DirectMessage.created_at.desc()).limit(50)).all()
    return {"items": [view_message(db, message, user.id) for message in matches
                      if not (db.get(MessageDetails, message.id) and
                              db.get(MessageDetails, message.id).deleted_at)]}


@router.get("/thread/{contact_id}")
def thread(contact_id: str, before: int | None = None, db: Session = Depends(get_db), user: User = Depends(current_user)):
    peer = check_pair(db, user.id, contact_id, require_open=False)
    query = select(DirectMessage).where(pair_filter(user.id, contact_id))
    if before is not None:
        query = query.where(DirectMessage.created_at < before)
    messages = db.scalars(query.order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc()).limit(100)).all()
    return {"contact": {"id": peer.id, "display_name": peer.display_name, "email": peer.email},
            "blocked": block_exists(db, user.id, contact_id),
            "items": [view_message(db, msg, user.id) for msg in reversed(messages)],
            "has_more": len(messages) == 100}


@router.post("/send", status_code=201, dependencies=[Depends(csrf_protect)])
def send(data: SendMessage, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_pair(db, user.id, data.contact_id)
    if not data.body.strip():
        raise HTTPException(422, "Напишите сообщение")
    validate_send_rate(user.id)
    if data.reply_to_id:
        previous = db.get(DirectMessage, data.reply_to_id)
        if not previous or not (
            (previous.sender_id == user.id and previous.recipient_id == data.contact_id) or
            (previous.sender_id == data.contact_id and previous.recipient_id == user.id)
        ):
            raise HTTPException(404, "Сообщение для ответа не найдено")
        details = db.get(MessageDetails, previous.id)
        if details and details.deleted_at:
            raise HTTPException(409, "Нельзя ответить на удалённое сообщение")
    msg = DirectMessage(sender_id=user.id, recipient_id=data.contact_id, body=data.body.strip())
    db.add(msg)
    db.flush()
    if data.reply_to_id:
        db.add(MessageReply(message_id=msg.id, replied_to_id=data.reply_to_id))
    db.commit()
    db.refresh(msg)
    inform(request, [user.id, data.contact_id], "message.changed", contact_id=user.id, sender_id=user.id)
    return view_message(db, msg, user.id)


@router.post("/send-file", status_code=201, dependencies=[Depends(csrf_protect)])
async def send_file(request: Request, contact_id: str = Form(...), file: UploadFile = File(...),
                    db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_pair(db, user.id, contact_id)
    validate_send_rate(user.id)
    content = await file.read(MAX_UPLOAD + 1)
    if not content or len(content) > MAX_UPLOAD:
        raise HTTPException(413, "Максимум 5 МБ")
    mime = detected_type(content)
    if mime not in ACCEPTED:
        raise HTTPException(415, "Допустимы изображения и аудиофайлы")
    name = (file.filename or "file").replace("\\", "/").split("/")[-1][:160]
    msg = DirectMessage(sender_id=user.id, recipient_id=contact_id, body="")
    db.add(msg)
    db.flush()
    db.add(MessageAttachment(message_id=msg.id, filename=name, media_type=mime, size=len(content), content=content))
    db.commit()
    db.refresh(msg)
    inform(request, [user.id, contact_id], "message.changed", contact_id=user.id, sender_id=user.id)
    return view_message(db, msg, user.id)


@router.get("/file/{attachment_id}")
def file_get(attachment_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    a = db.get(MessageAttachment, attachment_id)
    if not a:
        raise HTTPException(404, "Вложение не найдено")
    msg = db.get(DirectMessage, a.message_id)
    details = db.get(MessageDetails, a.message_id)
    if not msg or user.id not in (msg.sender_id, msg.recipient_id) or (details and details.deleted_at):
        raise HTTPException(404, "Вложение не найдено")
    return Response(a.content, media_type=a.media_type, headers={
        "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff",
        "Content-Security-Policy": "default-src 'none'; sandbox",
        "Content-Disposition": "inline",
    })


@router.post("/thread/{contact_id}/read", dependencies=[Depends(csrf_protect)])
def mark_read(contact_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_pair(db, user.id, contact_id, require_open=False)
    unread = db.scalars(select(DirectMessage).where(
        DirectMessage.sender_id == contact_id, DirectMessage.recipient_id == user.id
    ).order_by(DirectMessage.created_at.desc()).limit(500)).all()
    created = 0
    for msg in unread:
        if not db.get(MessageReceipt, msg.id):
            db.add(MessageReceipt(message_id=msg.id, read_at=int(time.time())))
            created += 1
    db.commit()
    if created:
        inform(request, [contact_id, user.id], "message.read", contact_id=user.id)
    return {"ok": True, "read_count": created}


@router.patch("/message/{message_id}", dependencies=[Depends(csrf_protect)])
def edit_message(message_id: str, data: EditMessage, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    msg = db.get(DirectMessage, message_id)
    if not msg or msg.sender_id != user.id:
        raise HTTPException(404, "Сообщение не найдено")
    meta = db.get(MessageDetails, message_id)
    if meta and meta.deleted_at:
        raise HTTPException(409, "Сообщение удалено")
    if db.scalar(select(MessageAttachment).where(MessageAttachment.message_id == message_id)):
        raise HTTPException(409, "Вложение нельзя изменить")
    if int(time.time()) - msg.created_at > 15 * 60:
        raise HTTPException(409, "Сообщение можно изменить в течение 15 минут")
    if not data.body.strip():
        raise HTTPException(422, "Пустое сообщение")
    msg.body = data.body.strip()
    if meta is None:
        meta = MessageDetails(message_id=message_id)
        db.add(meta)
    meta.edited_at = int(time.time())
    db.commit()
    inform(request, [msg.sender_id, msg.recipient_id], "message.changed", contact_id=user.id, sender_id=user.id)
    return view_message(db, msg, user.id)


@router.delete("/message/{message_id}", dependencies=[Depends(csrf_protect)])
def delete_message(message_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    msg = db.get(DirectMessage, message_id)
    if not msg or msg.sender_id != user.id:
        raise HTTPException(404, "Сообщение не найдено")
    meta = db.get(MessageDetails, message_id)
    if meta is None:
        meta = MessageDetails(message_id=message_id)
        db.add(meta)
    meta.deleted_at = int(time.time())
    for r in db.scalars(select(MessageReaction).where(MessageReaction.message_id == message_id)).all():
        db.delete(r)
    attachment = db.scalar(select(MessageAttachment).where(MessageAttachment.message_id == message_id))
    if attachment: db.delete(attachment)
    msg.body = ""
    db.commit()
    inform(request, [msg.sender_id, msg.recipient_id], "message.changed", contact_id=user.id, sender_id=user.id)
    return {"ok": True}


@router.put("/message/{message_id}/reaction", dependencies=[Depends(csrf_protect)])
def react(message_id: str, data: ReactionData, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    msg = db.get(DirectMessage, message_id)
    if not msg or user.id not in (msg.sender_id, msg.recipient_id):
        raise HTTPException(404, "Сообщение не найдено")
    meta = db.get(MessageDetails, message_id)
    if meta and meta.deleted_at:
        raise HTTPException(409, "Сообщение удалено")
    if data.emoji not in EMOJI:
        raise HTTPException(422, "Реакция не поддерживается")
    check_pair(db, msg.sender_id, msg.recipient_id)
    existing = db.scalar(select(MessageReaction).where(
        MessageReaction.message_id == message_id, MessageReaction.user_id == user.id))
    if existing and existing.emoji == data.emoji:
        db.delete(existing)
    elif existing:
        existing.emoji = data.emoji
    else:
        db.add(MessageReaction(message_id=message_id, user_id=user.id, emoji=data.emoji))
    db.commit()
    inform(request, [msg.sender_id, msg.recipient_id], "message.changed", contact_id=user.id, sender_id=user.id)
    return {"ok": True}


@router.put("/block/{contact_id}", dependencies=[Depends(csrf_protect)])
def block(contact_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_pair(db, user.id, contact_id, require_open=False)
    if not block_exists(db, user.id, contact_id):
        db.add(MessengerBlock(owner_id=user.id, target_id=contact_id))
        db.commit()
    return {"ok": True, "blocked": True}


@router.delete("/block/{contact_id}", dependencies=[Depends(csrf_protect)])
def unblock(contact_id: str, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    row = db.scalar(select(MessengerBlock).where(MessengerBlock.owner_id == user.id, MessengerBlock.target_id == contact_id))
    if row:
        db.delete(row)
        db.commit()
    return {"ok": True, "blocked": False}


@router.post("/report", status_code=201, dependencies=[Depends(csrf_protect)])
def report(data: ReportData, request: Request, db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    msg = db.get(DirectMessage, data.message_id)
    if not msg or msg.recipient_id != user.id:
        raise HTTPException(404, "Сообщение не найдено")
    db.add(MessengerReport(reporter_id=user.id, message_id=msg.id, reason=data.reason.strip()))
    db.commit()
    return {"ok": True, "notice": "Жалоба сохранена; автоматическая модерация пока не настроена"}

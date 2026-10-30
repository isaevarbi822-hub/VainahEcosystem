"""Vainah Messenger 0.6 group chats: private, invite-by-exact-email preview.

Server-stored and NOT end-to-end encrypted. Group admin actions and membership
checks are enforced server-side, independent of client UI.
"""
from __future__ import annotations

import time
from fastapi import APIRouter, Depends, HTTPException, Request, File, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select, func
from sqlalchemy.orm import Session

from .database import get_db
from .models import MessengerGroup, MessengerGroupMember, MessengerGroupMessage, MessengerGroupAttachment, VerifiedAccount, User
from .messenger import block_exists, validate_send_rate, inform, MAX_UPLOAD, MEDIA_LIMITS, verified_upload_type
from .handles import find_by_username
from .security import current_user, csrf_protect, enforce_origin

router = APIRouter(prefix="/api/messenger/v2/groups", tags=["Messenger groups"])
MAX_MEMBERS = 25


class GroupCreate(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    emails: list[str] = Field(default_factory=list, max_length=24)
    usernames: list[str] = Field(default_factory=list, max_length=24)


class GroupSend(BaseModel):
    body: str = Field(min_length=1, max_length=3000)


class GroupInvite(BaseModel):
    email: str | None = Field(default=None, min_length=5, max_length=254)
    username: str | None = Field(default=None, min_length=3, max_length=33)


def membership(db: Session, group_id: str, user_id: str):
    group = db.get(MessengerGroup, group_id)
    member = db.scalar(select(MessengerGroupMember).where(
        MessengerGroupMember.group_id == group_id,
        MessengerGroupMember.user_id == user_id))
    if not group or not member:
        raise HTTPException(404, "Группа не найдена или доступ закрыт")
    return group, member


def group_view(db: Session, group: MessengerGroup, member: MessengerGroupMember):
    members = db.scalars(select(MessengerGroupMember).where(MessengerGroupMember.group_id == group.id)).all()
    last = db.scalar(select(MessengerGroupMessage).where(
        MessengerGroupMessage.group_id == group.id).order_by(
        MessengerGroupMessage.created_at.desc(), MessengerGroupMessage.id.desc()).limit(1))
    unread = db.scalar(select(func.count(MessengerGroupMessage.id)).where(
        MessengerGroupMessage.group_id == group.id,
        MessengerGroupMessage.sender_id != member.user_id,
        MessengerGroupMessage.created_at > member.last_read_at,
    )) or 0
    return {"id": group.id, "name": group.name, "owner_id": group.owner_id,
            "members": len(members), "preview": "Сообщение удалено" if last and last.deleted_at else ((last.body[:100] or "📎 Медиафайл") if last else "Новая группа"),
            "unread": unread, "updated_at": (last.created_at // 1000) if last else group.created_at}


@router.get("")
def groups(db: Session = Depends(get_db), user: User = Depends(current_user)):
    rows = db.scalars(select(MessengerGroupMember).where(MessengerGroupMember.user_id == user.id)).all()
    items = [group_view(db, db.get(MessengerGroup, row.group_id), row) for row in rows
             if db.get(MessengerGroup, row.group_id)]
    items.sort(key=lambda x: x["updated_at"], reverse=True)
    return {"items": items}


@router.post("", status_code=201, dependencies=[Depends(csrf_protect)])
def create_group(data: GroupCreate, request: Request,
                 db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    name = data.name.strip()
    if len(name) < 2:
        raise HTTPException(422, "Введите название группы")
    count = db.scalar(select(func.count(MessengerGroup.id)).where(MessengerGroup.owner_id == user.id)) or 0
    if count >= 20:
        raise HTTPException(409, "Достигнут лимит групп")
    emails = {mail.strip().lower() for mail in data.emails if mail.strip()}
    emails.discard(user.email.lower())
    peers_by_id = {}
    for mail in emails:
        peer = db.scalar(select(User).where(User.email == mail))
        if not peer:
            raise HTTPException(404, "Один из указанных аккаунтов не найден")
        peers_by_id[peer.id] = peer
    for handle in data.usernames:
        peer = find_by_username(db, handle)
        if not peer:
            raise HTTPException(404, "Один из @username не найден")
        if peer.id != user.id: peers_by_id[peer.id] = peer
    if len(peers_by_id) > 24:
        raise HTTPException(422, "В группе может быть до 25 участников")
    peers = list(peers_by_id.values())
    for peer in peers:
        if block_exists(db, user.id, peer.id) or block_exists(db, peer.id, user.id):
            raise HTTPException(403, "Нельзя пригласить заблокированный контакт")
    group = MessengerGroup(name=name, owner_id=user.id)
    db.add(group)
    db.flush()
    for person in [user, *peers]:
        db.add(MessengerGroupMember(group_id=group.id, user_id=person.id))
    db.commit()
    inform(request, [p.id for p in [user,*peers]], "group.changed", group_id=group.id, sender_id=user.id)
    return {"id": group.id, "name": group.name, "members": len(peers) + 1}


@router.get("/{group_id}")
def group_info(group_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    group, member = membership(db, group_id, user.id)
    rows = db.scalars(select(MessengerGroupMember).where(MessengerGroupMember.group_id == group_id)).all()
    people = [db.get(User, row.user_id) for row in rows]
    return {**group_view(db, group, member), "people": [
        {"id": u.id, "display_name": u.display_name} for u in people if u
    ]}


def group_attachment_view(db: Session, message: MessengerGroupMessage):
    attachment = db.scalar(select(MessengerGroupAttachment).where(
        MessengerGroupAttachment.message_id == message.id))
    if not attachment:
        return None
    return {
        "id": attachment.id, "filename": attachment.filename,
        "type": attachment.media_type, "size": attachment.size,
        "kind": ("video_note" if attachment.media_type.startswith("video/")
                 and attachment.filename.startswith("video-note-") else
                 "voice" if attachment.media_type.startswith("audio/")
                 and attachment.filename.startswith("voice-") else
                 "photo" if attachment.media_type.startswith("image/") else
                 "video" if attachment.media_type.startswith("video/") else "file"),
        "url": f"/api/messenger/v2/groups/{message.group_id}/file/{attachment.id}",
    }


@router.get("/{group_id}/messages")
def messages(group_id: str, before: int | None = None, db: Session = Depends(get_db),
             user: User = Depends(current_user)):
    group, _ = membership(db, group_id, user.id)
    query = select(MessengerGroupMessage).where(MessengerGroupMessage.group_id == group.id)
    if before:
        query = query.where(MessengerGroupMessage.created_at < before)
    rows = db.scalars(query.order_by(MessengerGroupMessage.created_at.desc(), MessengerGroupMessage.id.desc()).limit(80)).all()
    users = {u.id: u.display_name for u in db.scalars(select(User).where(
        User.id.in_({m.sender_id for m in rows}))).all()} if rows else {}
    verified = set(db.scalars(select(VerifiedAccount.user_id).where(
        VerifiedAccount.user_id.in_({m.sender_id for m in rows}))).all()) if rows else set()
    return {"items": [{"id": m.id, "mine": m.sender_id == user.id,
             "sender": users.get(m.sender_id, "Участник"),
             "sender_verified": m.sender_id in verified,
             "body": "" if m.deleted_at else m.body,
             "deleted": bool(m.deleted_at), "created_at": m.created_at // 1000,
             "reactions": [], "read_at": None, "edited_at": None,
             "attachment": None if m.deleted_at else group_attachment_view(db,m),
             "reply_to": None} for m in reversed(rows)], "has_more": len(rows) == 80}


@router.post("/{group_id}/send", status_code=201, dependencies=[Depends(csrf_protect)])
def send(group_id: str, data: GroupSend, request: Request,
         db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    membership(db, group_id, user.id)
    if not data.body.strip():
        raise HTTPException(422, "Сообщение пустое")
    validate_send_rate(user.id)
    message = MessengerGroupMessage(group_id=group_id, sender_id=user.id,
                                    body=data.body.strip(), created_at=time.time_ns() // 1_000_000)
    db.add(message)
    db.commit()
    members = db.scalars(select(MessengerGroupMember).where(MessengerGroupMember.group_id == group_id)).all()
    inform(request, [m.user_id for m in members], "group.changed", group_id=group_id, sender_id=user.id)
    return {"id": message.id, "ok": True}


@router.post("/{group_id}/send-file", status_code=201, dependencies=[Depends(csrf_protect)])
async def send_group_file(group_id: str, request: Request, file: UploadFile = File(...),
                          db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    membership(db, group_id, user.id)
    validate_send_rate(user.id)
    content = await file.read(MAX_UPLOAD + 1)
    if not content or len(content) > MAX_UPLOAD:
        raise HTTPException(413, "Файл слишком большой (максимум 20 МБ)")
    mime = verified_upload_type(content, file.content_type or "")
    if mime not in MEDIA_LIMITS:
        raise HTTPException(415, "Поддерживаются фото, видео, аудио, PDF и ZIP")
    if len(content) > MEDIA_LIMITS[mime]:
        raise HTTPException(413, "Размер файла превышает лимит формата")
    filename = (file.filename or "media").replace("\\", "/").split("/")[-1][:160]
    message = MessengerGroupMessage(group_id=group_id, sender_id=user.id, body="",
                                    created_at=time.time_ns() // 1_000_000)
    db.add(message)
    db.flush()
    db.add(MessengerGroupAttachment(message_id=message.id, filename=filename,
                                    media_type=mime, size=len(content), content=content))
    db.commit()
    members = db.scalars(select(MessengerGroupMember).where(
        MessengerGroupMember.group_id == group_id)).all()
    inform(request, [m.user_id for m in members], "group.changed",
           group_id=group_id, sender_id=user.id)
    return {"id": message.id, "attachment": group_attachment_view(db, message)}


@router.get("/{group_id}/file/{attachment_id}")
def group_file(group_id: str, attachment_id: str, db: Session = Depends(get_db),
               user: User = Depends(current_user)):
    membership(db, group_id, user.id)
    attachment = db.get(MessengerGroupAttachment, attachment_id)
    if attachment is None:
        raise HTTPException(404, "Вложение не найдено")
    message = db.get(MessengerGroupMessage, attachment.message_id)
    if not message or message.group_id != group_id or message.deleted_at:
        raise HTTPException(404, "Вложение не найдено")
    return Response(attachment.content, media_type=attachment.media_type,
                    headers={"Cache-Control": "private, no-store",
                             "X-Content-Type-Options": "nosniff",
                             "Content-Security-Policy": "default-src 'none'; sandbox",
                             "Content-Disposition": ("inline" if attachment.media_type.startswith(
                                 ("image/", "video/", "audio/")) else "attachment")})


@router.post("/{group_id}/read", dependencies=[Depends(csrf_protect)])
def read(group_id: str, request: Request, db: Session = Depends(get_db),
         user: User = Depends(current_user)):
    enforce_origin(request)
    _, member = membership(db, group_id, user.id)
    member.last_read_at = time.time_ns() // 1_000_000
    db.commit()
    return {"ok": True}


@router.post("/{group_id}/invite", dependencies=[Depends(csrf_protect)])
def invite(group_id: str, data: GroupInvite, request: Request,
           db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    group, _ = membership(db, group_id, user.id)
    if group.owner_id != user.id:
        raise HTTPException(403, "Приглашать может только администратор")
    count = db.scalar(select(func.count(MessengerGroupMember.id)).where(
        MessengerGroupMember.group_id == group_id)) or 0
    if count >= MAX_MEMBERS:
        raise HTTPException(409, "В группе может быть до 25 участников")
    if bool(data.email) == bool(data.username):
        raise HTTPException(422, "Укажите email или @username")
    person = (find_by_username(db, data.username) if data.username else
              db.scalar(select(User).where(User.email == data.email.strip().lower())))
    if not person:
        raise HTTPException(404, "Аккаунт не найден")
    if block_exists(db, user.id, person.id) or block_exists(db, person.id, user.id):
        raise HTTPException(403, "Контакт заблокирован")
    existing = db.scalar(select(MessengerGroupMember).where(
        MessengerGroupMember.group_id == group_id, MessengerGroupMember.user_id == person.id))
    if existing:
        raise HTTPException(409, "Этот пользователь уже состоит в группе")
    db.add(MessengerGroupMember(group_id=group_id, user_id=person.id))
    db.commit()
    member_ids = [m.user_id for m in db.scalars(select(MessengerGroupMember).where(
        MessengerGroupMember.group_id == group_id)).all()]
    inform(request, member_ids, "group.changed", group_id=group_id, sender_id=user.id)
    return {"ok": True}


@router.delete("/{group_id}/leave", dependencies=[Depends(csrf_protect)])
def leave(group_id: str, request: Request, db: Session = Depends(get_db),
          user: User = Depends(current_user)):
    enforce_origin(request)
    group, member = membership(db, group_id, user.id)
    if group.owner_id == user.id:
        raise HTTPException(409, "Администратор не может выйти: удалите группу")
    db.delete(member)
    db.commit()
    member_ids = [m.user_id for m in db.scalars(select(MessengerGroupMember).where(
        MessengerGroupMember.group_id == group_id)).all()]
    inform(request, member_ids + [user.id], "group.changed", group_id=group_id, sender_id=user.id)
    return {"ok": True}


@router.delete("/{group_id}", dependencies=[Depends(csrf_protect)])
def delete_group(group_id: str, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    enforce_origin(request)
    group, _ = membership(db, group_id, user.id)
    if group.owner_id != user.id:
        raise HTTPException(403, "Удалить группу может только администратор")
    participants = [m.user_id for m in db.scalars(select(MessengerGroupMember).where(MessengerGroupMember.group_id == group_id)).all()]
    for row in db.scalars(select(MessengerGroupMessage).where(MessengerGroupMessage.group_id == group_id)).all(): db.delete(row)
    for row in db.scalars(select(MessengerGroupMember).where(MessengerGroupMember.group_id == group_id)).all(): db.delete(row)
    db.delete(group)
    db.commit()
    inform(request, participants, "group.changed", group_id=group_id, sender_id=user.id)
    return {"ok": True}

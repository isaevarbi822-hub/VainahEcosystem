"""Personal app data, direct messages, and private audio/photo library.

All database lookups include the Vainah ID; no user-selected paths are used.
Local self-hosted prototype only: requires more security controls for public deployment.
"""
from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from .database import get_db
from .models import AppRecord, DirectMessage, PrivateMedia, PrivateMediaBlob, User, VerifiedAccount, uid
from .security import csrf_protect, current_user, enforce_origin

router = APIRouter(prefix="/api", tags=["Vainah applications"])
KINDS = {"calendar", "study", "bookmarks", "places", "playlists"}
MAX_BY_KIND = {"calendar": 250, "study": 250, "bookmarks": 200, "places": 200, "playlists": 100}


class RecordData(BaseModel):
    payload: dict = Field(default_factory=dict)


class MessageData(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    body: str = Field(min_length=1, max_length=3000)


def check_kind(kind: str) -> None:
    if kind not in KINDS:
        raise HTTPException(404, "Такое приложение не найдено")


def clean_payload(kind: str, payload: dict) -> str:
    if any(not isinstance(k, str) or len(k) > 40 for k in payload):
        raise HTTPException(422, "Неверные поля")
    schema = {
        "calendar": {"title": 160, "date": 10, "time": 5, "description": 2000},
        "study": {"title": 160, "subject": 70, "due": 10, "details": 2000, "done": 0},
        "bookmarks": {"title": 160, "url": 1500},
        "places": {"name": 150, "latitude": -1, "longitude": -1},
        "playlists": {"name": 100, "tracks": -2},
    }[kind]
    if set(payload) - set(schema):
        raise HTTPException(422, "Неизвестные поля")
    cleaned = {}
    for key, limit in schema.items():
        value = payload.get(key, [] if limit == -2 else False if limit == 0 else "")
        if limit == -1:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                raise HTTPException(422, f"Неверные координаты: {key}")
            value = float(value)
            if not (-90 <= value <= 90 if key == "latitude" else -180 <= value <= 180):
                raise HTTPException(422, "Координаты вне диапазона")
        elif limit == -2:
            if not isinstance(value, list) or len(value) > 100 or any(not isinstance(x, str) or len(x) != 36 for x in value):
                raise HTTPException(422, "Неверный плейлист")
        elif limit == 0:
            if not isinstance(value, bool):
                raise HTTPException(422, "Неверный статус")
        elif not isinstance(value, str) or len(value) > limit:
            raise HTTPException(422, f"Слишком длинное поле: {key}")
        cleaned[key] = value.strip() if isinstance(value, str) else value
    if kind in ("calendar", "study"):
        for field in ("date", "due"):
            if field in cleaned and cleaned[field] and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", cleaned[field]):
                raise HTTPException(422, "Дата должна быть YYYY-MM-DD")
        if kind == "calendar" and cleaned["time"] and not re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", cleaned["time"]):
            raise HTTPException(422, "Время должно быть HH:MM")
    if kind == "bookmarks" and not re.fullmatch(r"https?://[^\s/]+(?:/[^\s]*)?", cleaned["url"], flags=re.I):
        raise HTTPException(422, "Нужна ссылка http(s)")
    return json.dumps(cleaned, ensure_ascii=False)


def record_view(record: AppRecord):
    return {"id": record.id, "kind": record.kind, "payload": json.loads(record.payload),
            "created_at": record.created_at, "updated_at": record.updated_at}


@router.get("/data/{kind}")
def list_records(kind: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    check_kind(kind)
    records = db.scalars(select(AppRecord).where(AppRecord.user_id == user.id, AppRecord.kind == kind)
                         .order_by(AppRecord.updated_at.desc()).limit(300)).all()
    return {"items": [record_view(record) for record in records]}


@router.post("/data/{kind}", status_code=201, dependencies=[Depends(csrf_protect)])
def create_record(kind: str, data: RecordData, request: Request, db: Session = Depends(get_db),
                  user: User = Depends(current_user)):
    enforce_origin(request)
    check_kind(kind)
    existing = db.query(AppRecord).filter_by(user_id=user.id, kind=kind).count()
    if existing >= MAX_BY_KIND[kind]:
        raise HTTPException(409, "Достигнут лимит записей")
    record = AppRecord(user_id=user.id, kind=kind, payload=clean_payload(kind, data.payload))
    db.add(record)
    db.commit()
    db.refresh(record)
    return record_view(record)


@router.put("/data/{kind}/{record_id}", dependencies=[Depends(csrf_protect)])
def update_record(kind: str, record_id: str, data: RecordData, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_kind(kind)
    record = db.scalar(select(AppRecord).where(AppRecord.id == record_id, AppRecord.user_id == user.id,
                                                AppRecord.kind == kind))
    if not record:
        raise HTTPException(404, "Запись не найдена")
    record.payload = clean_payload(kind, data.payload)
    record.updated_at = int(time.time())
    db.commit()
    return record_view(record)


@router.delete("/data/{kind}/{record_id}", dependencies=[Depends(csrf_protect)])
def delete_record(kind: str, record_id: str, request: Request,
                  db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    check_kind(kind)
    record = db.scalar(select(AppRecord).where(AppRecord.id == record_id, AppRecord.user_id == user.id,
                                                AppRecord.kind == kind))
    if not record:
        raise HTTPException(404, "Запись не найдена")
    db.delete(record)
    db.commit()
    return {"ok": True}


def public_contact(user: User):
    return {"id": user.id, "display_name": user.display_name, "email": user.email}


@router.get("/messenger/contact")
def find_contact(email: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if len(email) > 254:
        raise HTTPException(422, "Адрес слишком длинный")
    match = db.scalar(select(User).where(User.email == email.strip().lower()))
    if not match or match.id == user.id:
        raise HTTPException(404, "Аккаунт не найден")
    contact = public_contact(match)
    contact["verified"] = db.get(VerifiedAccount, match.id) is not None
    return {"contact": contact}


@router.get("/messenger/contacts")
def contacts(db: Session = Depends(get_db), user: User = Depends(current_user)):
    messages = db.scalars(select(DirectMessage).where(
        or_(DirectMessage.sender_id == user.id, DirectMessage.recipient_id == user.id)
    ).order_by(DirectMessage.created_at.desc()).limit(300)).all()
    ids = list(dict.fromkeys(m.recipient_id if m.sender_id == user.id else m.sender_id for m in messages))
    users = db.scalars(select(User).where(User.id.in_(ids))).all() if ids else []
    by_id = {u.id: u for u in users}
    return {"items": [public_contact(by_id[i]) for i in ids if i in by_id]}


@router.get("/messenger/thread/{contact_id}")
def thread(contact_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if not db.get(User, contact_id) or contact_id == user.id:
        raise HTTPException(404, "Собеседник не найден")
    stmt = select(DirectMessage).where(or_(
        and_(DirectMessage.sender_id == user.id, DirectMessage.recipient_id == contact_id),
        and_(DirectMessage.sender_id == contact_id, DirectMessage.recipient_id == user.id)
    )).order_by(DirectMessage.created_at.desc(), DirectMessage.id.desc()).limit(100)
    messages = db.scalars(stmt).all()[::-1]
    return {"items": [{"id": m.id, "mine": m.sender_id == user.id, "body": m.body,
                        "created_at": m.created_at} for m in messages]}


@router.post("/messenger/send", status_code=201, dependencies=[Depends(csrf_protect)])
def send_message(data: MessageData, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    enforce_origin(request)
    recipient = db.scalar(select(User).where(User.email == data.email.strip().lower()))
    if not recipient or recipient.id == user.id:
        raise HTTPException(404, "Получатель не найден")
    from .messenger import check_pair, validate_send_rate
    check_pair(db, user.id, recipient.id)
    validate_send_rate(user.id)
    if not data.body.strip():
        raise HTTPException(422, "Пустое сообщение")
    message = DirectMessage(sender_id=user.id, recipient_id=recipient.id, body=data.body.strip())
    db.add(message)
    db.commit()
    return {"id": message.id, "ok": True}


MAX_SIZE = {"photo": 8 * 1024 * 1024, "audio": 20 * 1024 * 1024}
TYPES = {"photo": {"image/jpeg", "image/png", "image/webp", "image/gif"},
         "audio": {"audio/mpeg", "audio/mp3", "audio/wav", "audio/x-wav", "audio/ogg", "audio/mp4"}}


def use_database_media(db: Session) -> bool:
    override = os.getenv("VAINAH_MEDIA_BACKEND", "").strip().lower()
    if override not in {"", "database", "filesystem"}:
        raise RuntimeError("VAINAH_MEDIA_BACKEND must be 'database' or 'filesystem'")
    if override:
        return override == "database"
    return db.get_bind().dialect.name == "postgresql"


def upload_root() -> Path:
    configured = os.getenv("VAINAH_UPLOAD_DIR")
    directory = Path(configured) if configured else Path(__file__).resolve().parents[3] / "data" / "uploads"
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def detected_type(data: bytes) -> str | None:
    if data.startswith(b"\xff\xd8\xff"): return "image/jpeg"
    if data.startswith(b"\x89PNG\r\n\x1a\n"): return "image/png"
    if data.startswith((b"GIF87a", b"GIF89a")): return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP": return "image/webp"
    if data.startswith(b"ID3") or (len(data) > 2 and data[0] == 255 and data[1] & 224 == 224): return "audio/mpeg"
    if data[:4] == b"RIFF" and data[8:12] == b"WAVE": return "audio/wav"
    if data.startswith(b"OggS"): return "audio/ogg"
    if data.startswith(bytes.fromhex("1a45dfa3")): return "audio/webm"
    if data[4:8] == b"ftyp": return "audio/mp4"
    return None


@router.get("/media/{category}")
def media_list(category: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    if category not in MAX_SIZE: raise HTTPException(404, "Категория не найдена")
    items = db.scalars(select(PrivateMedia).where(PrivateMedia.user_id == user.id,
                        PrivateMedia.category == category).order_by(PrivateMedia.created_at.desc()).limit(100)).all()
    return {"items": [media_view(i) for i in items]}


def media_view(item: PrivateMedia):
    return {"id": item.id, "filename": item.filename, "type": item.media_type,
            "category": item.category, "size": item.size, "created_at": item.created_at,
            "url": f"/api/media/file/{item.id}"}


@router.post("/media/{category}", status_code=201, dependencies=[Depends(csrf_protect)])
async def media_upload(category: str, request: Request, file: UploadFile = File(...),
                       db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    if category not in MAX_SIZE: raise HTTPException(404, "Категория не найдена")
    if db.query(PrivateMedia).filter_by(user_id=user.id, category=category).count() >= 80:
        raise HTTPException(409, "Лимит файлов достигнут")
    # Read at most limit+1, then reject without saving; never trust client-side Content-Type.
    content = await file.read(MAX_SIZE[category] + 1)
    if not content or len(content) > MAX_SIZE[category]:
        raise HTTPException(413, "Размер файла превышает лимит")
    media_type = detected_type(content)
    if media_type is None or media_type not in TYPES[category]:
        raise HTTPException(415, "Неподдерживаемый формат файла")
    file_id = uid()
    filename = Path(file.filename or "file").name[:180]
    item = PrivateMedia(id=file_id, user_id=user.id, category=category,
                        filename=filename, media_type=media_type, size=len(content))
    db.add(item)
    target = None
    if use_database_media(db):
        # Data and metadata commit atomically. On Render's ephemeral disk these bytes
        # stay in Neon across deploys; for large public libraries use object storage.
        db.add(PrivateMediaBlob(id=file_id, content=content))
    else:
        user_dir = upload_root() / user.id
        user_dir.mkdir(parents=True, exist_ok=True)
        target = user_dir / file_id
        target.write_bytes(content)
    try:
        db.commit()
    except Exception:
        if target is not None:
            target.unlink(missing_ok=True)
        raise
    return media_view(item)


@router.get("/media/file/{file_id}")
def media_download(file_id: str, db: Session = Depends(get_db), user: User = Depends(current_user)):
    item = db.scalar(select(PrivateMedia).where(PrivateMedia.id == file_id, PrivateMedia.user_id == user.id))
    if not item:
        raise HTTPException(404, "Файл не найден")
    blob = db.get(PrivateMediaBlob, item.id)
    headers = {"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"}
    if blob is not None:
        return Response(content=blob.content, media_type=item.media_type, headers=headers)
    # Existing filesystem files from older installations remain accessible.
    target = upload_root() / user.id / item.id
    if not target.is_file():
        raise HTTPException(404, "Файл отсутствует в хранилище")
    return FileResponse(target, media_type=item.media_type, headers=headers)


@router.delete("/media/file/{file_id}", dependencies=[Depends(csrf_protect)])
def media_delete(file_id: str, request: Request, db: Session = Depends(get_db),
                 user: User = Depends(current_user)):
    enforce_origin(request)
    item = db.scalar(select(PrivateMedia).where(PrivateMedia.id == file_id, PrivateMedia.user_id == user.id))
    if not item:
        raise HTTPException(404, "Файл не найден")
    blob = db.get(PrivateMediaBlob, item.id)
    if blob is not None:
        db.delete(blob)
    db.delete(item)
    db.commit()
    (upload_root() / user.id / item.id).unlink(missing_ok=True)
    return {"ok": True}

"""User-scoped notes CRUD APIs."""
import time
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import or_, select
from sqlalchemy.orm import Session
from .database import get_db
from .models import Note, User
from .schemas import NoteCreate, NoteUpdate
from .security import csrf_protect, current_user, enforce_origin

router = APIRouter(prefix="/api/notes", tags=["Vainah Notes"])


def note_view(note: Note):
    return {"id": note.id, "title": note.title, "content": note.content,
            "created_at": note.created_at, "updated_at": note.updated_at}


def owned_note(db: Session, user: User, note_id: str) -> Note:
    note = db.scalar(select(Note).where(Note.id == note_id, Note.user_id == user.id))
    if not note:
        raise HTTPException(status_code=404, detail="Заметка не найдена")
    return note


@router.get("")
def list_notes(q: str = "", db: Session = Depends(get_db), user: User = Depends(current_user)):
    stmt = select(Note).where(Note.user_id == user.id)
    if q:
        if len(q) > 100:
            raise HTTPException(status_code=422, detail="Слишком длинный запрос")
        stmt = stmt.where(or_(Note.title.ilike(f"%{q}%"), Note.content.ilike(f"%{q}%")))
    notes = db.scalars(stmt.order_by(Note.updated_at.desc(), Note.id.desc()).limit(100)).all()
    return {"items": [note_view(note) for note in notes]}


@router.post("", status_code=201, dependencies=[Depends(csrf_protect)])
def create_note(data: NoteCreate, request: Request, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    enforce_origin(request)
    note = Note(user_id=user.id, title=data.title.strip() or "Без названия", content=data.content)
    db.add(note)
    db.commit()
    db.refresh(note)
    return note_view(note)


@router.put("/{note_id}", dependencies=[Depends(csrf_protect)])
def update_note(note_id: str, data: NoteUpdate, request: Request,
                db: Session = Depends(get_db), user: User = Depends(current_user)):
    enforce_origin(request)
    note = owned_note(db, user, note_id)
    note.title = data.title.strip() or "Без названия"
    note.content = data.content
    note.updated_at = int(time.time())
    db.commit()
    return note_view(note)


@router.delete("/{note_id}", dependencies=[Depends(csrf_protect)])
def delete_note(note_id: str, request: Request, db: Session = Depends(get_db),
                user: User = Depends(current_user)):
    enforce_origin(request)
    note = owned_note(db, user, note_id)
    db.delete(note)
    db.commit()
    return {"ok": True}

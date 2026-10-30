"""Opt-in, unique public usernames for Messenger. Never reveal email in search."""
from __future__ import annotations
import re
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base, get_db
from .public_ids import get_or_create_public_id, find_user_by_public_id
from .models import User, MessengerBlock
from .security import current_user, csrf_protect, enforce_origin

router = APIRouter(prefix="/api/people", tags=["Public usernames"])
HANDLE_RE = re.compile(r"^[a-z][a-z0-9_]{4,31}$")
RESERVED = {"admin","support","vainah","telegram","system","official","security","moderator","helpdesk","staff","everyone","deleted","anonymous"}
class UserHandle(Base):
    __tablename__ = "messenger_user_handles"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id",ondelete="CASCADE"),primary_key=True)
    username: Mapped[str] = mapped_column(String(32),unique=True,index=True,nullable=False)

class UsernameChange(BaseModel):
    username: str = Field(min_length=5,max_length=33)

def normalized(value: str) -> str:
    return value.strip().removeprefix("@").lower()

def validate_username(value: str) -> str:
    value=normalized(value)
    if not HANDLE_RE.fullmatch(value) or value in RESERVED or value.startswith("vainah_"):
        raise HTTPException(422,"Имя: 5–32 символа, латиница, цифры и _, первая буква — латинская")
    return value

def find_by_username(db:Session,value:str)->User|None:
    value=normalized(value)
    if not HANDLE_RE.fullmatch(value): return None
    entry=db.scalar(select(UserHandle).where(UserHandle.username==value))
    return db.get(User,entry.user_id) if entry else None

def username_for(db:Session,user_id:str)->str|None:
    entry=db.get(UserHandle,user_id)
    return entry.username if entry else None

def blocked(db:Session,me:str,them:str)->bool:
    return bool(db.scalar(select(MessengerBlock.id).where(
        ((MessengerBlock.owner_id==me)&(MessengerBlock.target_id==them))|
        ((MessengerBlock.owner_id==them)&(MessengerBlock.target_id==me)))))

@router.get("/me")
def me(db:Session=Depends(get_db),user:User=Depends(current_user)):
    return {"username":username_for(db,user.id),"display_name":user.display_name,
            "vainah_id":get_or_create_public_id(db,user.id)}

@router.put("/username",dependencies=[Depends(csrf_protect)])
def update_username(data:UsernameChange,request:Request,db:Session=Depends(get_db),
                    user:User=Depends(current_user)):
    enforce_origin(request)
    value=validate_username(data.username)
    occupied=db.scalar(select(UserHandle).where(UserHandle.username==value))
    if occupied and occupied.user_id!=user.id:
        raise HTTPException(409,"Это имя пользователя уже занято")
    own=db.get(UserHandle,user.id)
    if own: own.username=value
    else: db.add(UserHandle(user_id=user.id,username=value))
    try:db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409,"Это имя пользователя уже занято")
    return {"username":value}

@router.get("/search")
def search(q:str="",db:Session=Depends(get_db),user:User=Depends(current_user)):
    term=normalized(q)
    if len(term)<3 or len(term)>32 or not re.fullmatch(r"[a-z0-9_]+",term):
        return {"items":[]}
    rows=db.scalars(select(UserHandle).where(UserHandle.username.like(term+"%"))
                    .order_by(UserHandle.username).limit(20)).all()
    items=[]
    for row in rows:
        if row.user_id==user.id or blocked(db,user.id,row.user_id):continue
        person=db.get(User,row.user_id)
        if person:items.append({"id":person.id,"display_name":person.display_name,"username":row.username})
    return {"items":items[:12]}

@router.get("/id/{vainah_id}")
def lookup_vainah_id(vainah_id: str, db: Session = Depends(get_db),
                     user: User = Depends(current_user)):
    """Exact-only ID lookup, never prefix enumeration. Honors both-way blocks."""
    person = find_user_by_public_id(db, vainah_id)
    if not person or person.id == user.id or blocked(db, user.id, person.id):
        raise HTTPException(404, "Пользователь не найден")
    return {"person": {"id": person.id, "username": username_for(db, person.id),
                       "display_name": person.display_name, "vainah_id": vainah_id}}

@router.get("/{username}")
def lookup(username:str,db:Session=Depends(get_db),user:User=Depends(current_user)):
    person=find_by_username(db,username)
    if not person or person.id==user.id or blocked(db,user.id,person.id):
        raise HTTPException(404,"Пользователь не найден")
    return {"person":{"id":person.id,"username":username_for(db,person.id),"display_name":person.display_name}}

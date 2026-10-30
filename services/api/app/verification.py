"""Verification badges belong to administrators, never user profile settings."""
from __future__ import annotations
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, VerifiedAccount
from .public_ids import find_user_by_public_id
from .handles import find_by_username
from .security import current_user, csrf_protect, enforce_origin

router = APIRouter(prefix="/api/messenger/v2/verification", tags=["verification"])

class VerificationAction(BaseModel):
    user_id: str
    verified: bool = True

def owner_id() -> str:
    """One immutable internal user ID; never a username or client-supplied role."""
    return os.getenv("VAINAH_OWNER_USER_ID", "").strip()


@router.get("/me")
def my_badge(user: User = Depends(current_user), db: Session = Depends(get_db)):
    owner = owner_id()
    is_owner = bool(owner) and user.id == owner
    if is_owner and db.get(VerifiedAccount, user.id) is None:
        db.add(VerifiedAccount(user_id=user.id, verified_by=user.id))
        db.commit()
    return {"verified": is_owner or db.get(VerifiedAccount, user.id) is not None,
            "can_manage": is_owner}


@router.post("/manage", dependencies=[Depends(csrf_protect)])
def manage_badge(data: VerificationAction, request: Request,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce_origin(request)
    owner = owner_id()
    if not owner or user.id != owner:
        raise HTTPException(403, "Только владелец Vainah может управлять галочками")
    identifier = data.user_id.strip()
    target = db.get(User, identifier)
    if target is None and identifier.isascii() and identifier.isdigit():
        target = find_user_by_public_id(db, identifier)
    if target is None and identifier.startswith("@"):
        target = find_by_username(db, identifier)
    if target is None:
        raise HTTPException(404, "Аккаунт не найден")
    if target.id == owner and not data.verified:
        raise HTTPException(409, "Нельзя снять галочку с аккаунта владельца")
    previous = db.get(VerifiedAccount, target.id)
    if data.verified and previous is None:
        db.add(VerifiedAccount(user_id=target.id, verified_by=user.id))
    elif not data.verified and previous is not None:
        db.delete(previous)
    db.commit()
    return {"user_id": target.id, "verified": data.verified}

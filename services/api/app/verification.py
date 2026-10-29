"""Verification badges belong to administrators, never user profile settings."""
from __future__ import annotations
import os
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, VerifiedAccount
from .security import current_user, csrf_protect, enforce_origin

router = APIRouter(prefix="/api/messenger/v2/verification", tags=["verification"])

class VerificationAction(BaseModel):
    user_id: str
    verified: bool = True

@router.get("/me")
def my_badge(user: User = Depends(current_user), db: Session = Depends(get_db)):
    return {"verified": db.get(VerifiedAccount, user.id) is not None,
            "can_manage": user.id in {s.strip() for s in os.getenv("VAINAH_VERIFICATION_ADMIN_IDS", "").split(",") if s.strip()}}

@router.post("/manage", dependencies=[Depends(csrf_protect)])
def manage_badge(data: VerificationAction, request: Request,
                 user: User = Depends(current_user), db: Session = Depends(get_db)):
    enforce_origin(request)
    admins = {s.strip() for s in os.getenv("VAINAH_VERIFICATION_ADMIN_IDS", "").split(",") if s.strip()}
    if user.id not in admins:
        raise HTTPException(403, "Только администратор Vainah может управлять галочками")
    target = db.get(User, data.user_id)
    if target is None: raise HTTPException(404, "Аккаунт не найден")
    previous = db.get(VerifiedAccount, target.id)
    if data.verified and previous is None:
        db.add(VerifiedAccount(user_id=target.id, verified_by=user.id))
    elif not data.verified and previous is not None:
        db.delete(previous)
    db.commit()
    return {"user_id": target.id, "verified": data.verified}

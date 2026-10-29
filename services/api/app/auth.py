"""One account for the Vainah family of applications (local MVP identity service)."""
from __future__ import annotations

import hmac
import os

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from .database import get_db
from .models import User, LoginSession
from .schemas import Credentials, Signup, ProfileUpdate, PasswordChange
from .security import (COOKIE_NAME, SESSION_SECONDS, csrf_protect, current_session,
                       current_user, enforce_origin, hash_password, secure_cookie_enabled,
                       start_session, token_digest, verify_password,
                       enforce_auth_limit, count_auth_attempt, clear_login_attempts)

router = APIRouter(prefix="/api/auth", tags=["Vainah ID"])


def public_user(user: User):
    return {"id": user.id, "email": user.email, "display_name": user.display_name,
            "created_at": user.created_at}


def issue_cookie(response: Response, token: str):
    response.set_cookie(key=COOKIE_NAME, value=token, httponly=True, secure=secure_cookie_enabled(),
                        samesite="strict", max_age=SESSION_SECONDS, path="/")


@router.post("/register", status_code=201)
def register(data: Signup, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_origin(request)
    caller = request.client.host if request.client else "unknown"
    enforce_auth_limit("register", caller)
    expected_code = os.getenv("VAINAH_SIGNUP_CODE", "")
    if expected_code and not hmac.compare_digest(data.invite_code or "", expected_code):
        raise HTTPException(status_code=403, detail="Для регистрации нужен код приглашения")
    if db.scalar(select(User).where(User.email == data.email)):
        raise HTTPException(status_code=409, detail="Этот email уже используется")
    user = User(email=data.email, display_name=data.display_name, password_hash=hash_password(data.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Этот email уже используется")
    db.refresh(user)
    count_auth_attempt("register", caller)
    token, csrf = start_session(db, user)
    issue_cookie(response, token)
    return {"user": public_user(user), "csrf_token": csrf}


@router.post("/login")
def login(data: Credentials, request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_origin(request)
    enforce_auth_limit("login", data.email)
    user = db.scalar(select(User).where(User.email == data.email))
    if not user or not verify_password(data.password, user.password_hash):
        count_auth_attempt("login", data.email)
        raise HTTPException(status_code=401, detail="Неверный email или пароль")
    clear_login_attempts(data.email)
    token, csrf = start_session(db, user)
    issue_cookie(response, token)
    return {"user": public_user(user), "csrf_token": csrf}


@router.get("/me")
def me(user: User = Depends(current_user), session: LoginSession = Depends(current_session)):
    return {"user": public_user(user), "csrf_token": session.csrf_token}


@router.post("/logout", dependencies=[Depends(csrf_protect)])
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    enforce_origin(request)
    token = request.cookies.get(COOKIE_NAME)
    if token:
        record = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(token)))
        if record:
            db.delete(record)
            db.commit()
    response.delete_cookie(COOKIE_NAME, path="/", samesite="strict", secure=secure_cookie_enabled())
    return {"ok": True}


@router.patch("/profile", dependencies=[Depends(csrf_protect)])
def update_profile(data: ProfileUpdate, request: Request, db: Session = Depends(get_db),
                   user: User = Depends(current_user)):
    enforce_origin(request)
    user.display_name = data.display_name
    db.commit()
    return {"user": public_user(user)}


@router.post("/password", dependencies=[Depends(csrf_protect)])
def update_password(data: PasswordChange, request: Request, db: Session = Depends(get_db),
                    user: User = Depends(current_user), session: LoginSession = Depends(current_session)):
    enforce_origin(request)
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=403, detail="Неверный текущий пароль")
    if data.current_password == data.new_password:
        raise HTTPException(status_code=422, detail="Новый пароль должен отличаться")
    user.password_hash = hash_password(data.new_password)
    other_sessions = db.scalars(select(LoginSession).where(
        LoginSession.user_id == user.id, LoginSession.id != session.id)).all()
    for item in other_sessions:
        db.delete(item)
    db.commit()
    return {"ok": True, "revoked_sessions": len(other_sessions)}


@router.post("/logout-others", dependencies=[Depends(csrf_protect)])
def logout_others(request: Request, db: Session = Depends(get_db),
                  user: User = Depends(current_user), session: LoginSession = Depends(current_session)):
    enforce_origin(request)
    other_sessions = db.scalars(select(LoginSession).where(
        LoginSession.user_id == user.id, LoginSession.id != session.id)).all()
    for item in other_sessions:
        db.delete(item)
    db.commit()
    return {"ok": True, "revoked_sessions": len(other_sessions)}

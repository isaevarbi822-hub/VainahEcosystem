"""Sign in with Apple on Android using Apple's hosted OAuth flow.

One-use state, nonce, server-side code exchange and client-bound proof prevent
forged identity and intercepted deep links from creating local sessions.
Requires real Apple developer credentials; disabled until configured.
"""
from __future__ import annotations
import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import time
from urllib.parse import urlencode, quote
from urllib.request import Request as UrlRequest, urlopen

import jwt
from jwt import PyJWKClient
from fastapi import APIRouter, Depends, HTTPException, Request, Response, Form
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, ForeignKey, Integer, String, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column

from .database import Base, get_db
from .models import User, LinkedIdentity
from .security import (start_session, hash_password, enforce_auth_limit,
                       count_auth_attempt, enforce_origin)
from .auth import issue_cookie, public_user

router=APIRouter(prefix="/api/auth/apple",tags=["Sign in with Apple"])
TTL=5*60
APPLE_ISSUER="https://appleid.apple.com"

class AppleLoginAttempt(Base):
    __tablename__="apple_login_attempts"
    state_hash:Mapped[str]=mapped_column(String(64),primary_key=True)
    nonce:Mapped[str]=mapped_column(String(96))
    challenge:Mapped[str]=mapped_column(String(64))
    user_id:Mapped[str|None]=mapped_column(ForeignKey("users.id",ondelete="CASCADE"),nullable=True)
    expires_at:Mapped[int]=mapped_column(Integer,index=True)
    consumed:Mapped[bool]=mapped_column(Boolean,default=False)

class AppleStart(BaseModel):
    challenge:str=Field(min_length=43,max_length=43)

class AppleExchange(BaseModel):
    state:str=Field(min_length=32,max_length=140)
    verifier:str=Field(min_length=32,max_length=200)

def configured()->bool:
    names=["APPLE_SERVICE_ID","APPLE_TEAM_ID","APPLE_KEY_ID","APPLE_PRIVATE_KEY_P8","APPLE_REDIRECT_URI"]
    if not all(os.getenv(n,"").strip() for n in names):return False
    redirect=os.environ["APPLE_REDIRECT_URI"]
    origin=os.getenv("APP_ORIGIN","").rstrip("/")
    return (redirect.startswith("https://") and redirect.endswith("/api/auth/apple/callback")
            and bool(origin) and redirect.startswith(origin+"/"))

def digest(value:str)->str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()

def b64url(value:bytes)->str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")

def apple_secret()->str:
    now=int(time.time())
    key=os.environ["APPLE_PRIVATE_KEY_P8"].replace("\\n","\n")
    return jwt.encode({"iss":os.environ["APPLE_TEAM_ID"],"iat":now,"exp":now+600,
        "aud":APPLE_ISSUER,"sub":os.environ["APPLE_SERVICE_ID"]},key,
        algorithm="ES256",headers={"kid":os.environ["APPLE_KEY_ID"]})

def verify_apple_code(code:str,nonce:str)->dict:
    body=urlencode({"client_id":os.environ["APPLE_SERVICE_ID"],
        "client_secret":apple_secret(),"code":code,
        "grant_type":"authorization_code",
        "redirect_uri":os.environ["APPLE_REDIRECT_URI"]}).encode()
    request=UrlRequest(APPLE_ISSUER+"/auth/token",data=body,
                       headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    try:
        with urlopen(request,timeout=12) as response:
            data=json.load(response)
    except Exception:
        raise HTTPException(502,"Не удалось подтвердить вход через Apple")
    token=data.get("id_token","")
    if not token:raise HTTPException(401,"Apple не вернул подтверждение личности")
    try:
        key=PyJWKClient(APPLE_ISSUER+"/auth/keys").get_signing_key_from_jwt(token).key
        claims=jwt.decode(token,key,algorithms=["RS256"],audience=os.environ["APPLE_SERVICE_ID"],
                          issuer=APPLE_ISSUER,options={"require":["sub","exp","iat","iss","aud"]})
    except Exception:
        raise HTTPException(401,"Подпись ответа Apple недействительна")
    if not hmac.compare_digest(str(claims.get("nonce","")),nonce):
        raise HTTPException(401,"Подтверждение Apple не соответствует запросу")
    if not claims.get("sub"):raise HTTPException(401,"Apple ID не определён")
    return claims

def return_page(state:str)->HTMLResponse:
    url="vainah-messenger://auth/apple?state="+quote(state,safe="")
    # The URL contains only opaque state, never an ID token or Vainah session.
    return HTMLResponse("""<!doctype html><html lang="ru"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"></head>
<body style="font:16px system-ui;background:#101114;color:#fff;text-align:center;padding:45px 22px">
<h2>Apple ID подтверждён</h2><p>Нажмите кнопку, чтобы вернуться в Vainah Messenger.</p>
<a style="display:block;padding:17px;background:#229ff5;border-radius:16px;color:white;text-decoration:none"
href='"""+url+"""'>Вернуться в Vainah Messenger</a></body></html>""",
        headers={"Cache-Control":"no-store","Referrer-Policy":"no-referrer"})

@router.get("/config")
def apple_config():
    return {"enabled":configured()}

@router.post("/start")
def apple_start(data:AppleStart,request:Request,db:Session=Depends(get_db)):
    enforce_origin(request)
    if not configured():raise HTTPException(503,"Apple ID пока не настроен владельцем сервиса")
    if not re.fullmatch(r"[A-Za-z0-9_-]{43}",data.challenge):
        raise HTTPException(422,"Некорректное подтверждение приложения")
    enforce_auth_limit("login",request.client.host if request.client else "unknown")
    state=secrets.token_urlsafe(40)
    nonce=secrets.token_urlsafe(32)
    db.add(AppleLoginAttempt(state_hash=digest(state),nonce=nonce,challenge=data.challenge,
                             expires_at=int(time.time())+TTL))
    db.commit()
    url=APPLE_ISSUER+"/auth/authorize?"+urlencode({
        "client_id":os.environ["APPLE_SERVICE_ID"],
        "redirect_uri":os.environ["APPLE_REDIRECT_URI"],
        "response_type":"code","response_mode":"form_post","scope":"name email",
        "state":state,"nonce":nonce,
    })
    return {"url":url,"state":state}

@router.post("/callback",response_class=HTMLResponse)
def apple_callback(state:str=Form(""),code:str=Form(""),error:str=Form(""),
                   user:str=Form(""),db:Session=Depends(get_db)):
    if not configured():raise HTTPException(503,"Apple ID не настроен")
    if not state or len(state)>140:raise HTTPException(400,"Некорректное состояние Apple")
    attempt=db.get(AppleLoginAttempt,digest(state))
    if not attempt or attempt.consumed or attempt.user_id or attempt.expires_at<int(time.time()):
        raise HTTPException(400,"Запрос входа истёк или уже использован")
    if error or not code:raise HTTPException(400,"Вход через Apple не завершён")
    # Atomically reserve this state, so it cannot be replayed during code validation.
    claimed=db.execute(update(AppleLoginAttempt).where(
        AppleLoginAttempt.state_hash==digest(state),AppleLoginAttempt.user_id.is_(None),
        AppleLoginAttempt.consumed.is_(False),AppleLoginAttempt.expires_at>=int(time.time()))
        .values(consumed=True))
    if claimed.rowcount!=1:
        db.rollback()
        raise HTTPException(400,"Этот запрос Apple уже обработан")
    db.commit()
    claims=verify_apple_code(code,attempt.nonce)
    sub=str(claims["sub"])
    identity=db.scalar(select(LinkedIdentity).where(
        LinkedIdentity.provider=="apple",LinkedIdentity.subject==sub))
    if identity:
        person=db.get(User,identity.user_id)
        if not person:raise HTTPException(401,"Связанный аккаунт не найден")
    else:
        email=str(claims.get("email","")).strip().lower()
        if not email or "@" not in email:
            raise HTTPException(409,"Apple не передал email для создания аккаунта")
        existing=db.scalar(select(User).where(User.email==email))
        if existing:
            raise HTTPException(409,"Email уже зарегистрирован. Войдите через email/Google; автоматическое объединение аккаунтов выключено.")
        invite_required=(os.getenv("VAINAH_SIGNUP_MODE","").lower()!="open"
                         and bool(os.getenv("VAINAH_SIGNUP_CODE","")))
        if invite_required:raise HTTPException(403,"Регистрация по Apple ID закрыта на время тестирования")
        person=User(email=email,display_name=email.split("@")[0][:80],
                    password_hash=hash_password(secrets.token_urlsafe(48)))
        db.add(person);db.flush()
        db.add(LinkedIdentity(user_id=person.id,provider="apple",subject=sub))
        try:db.commit()
        except IntegrityError:
            db.rollback()
            raise HTTPException(409,"Apple ID уже привязан")
    attempt=db.get(AppleLoginAttempt,digest(state))
    attempt.user_id=person.id
    attempt.consumed=False
    db.commit()
    return return_page(state)

@router.post("/exchange")
def apple_exchange(data:AppleExchange,request:Request,response:Response,
                   db:Session=Depends(get_db)):
    enforce_origin(request)
    record=db.get(AppleLoginAttempt,digest(data.state))
    if not record or record.consumed or not record.user_id or record.expires_at<int(time.time()):
        raise HTTPException(401,"Вход Apple завершён или истёк")
    proof=b64url(hashlib.sha256(data.verifier.encode()).digest())
    if not hmac.compare_digest(proof,record.challenge):
        raise HTTPException(403,"Подтверждение приложения не совпадает")
    taken=db.execute(update(AppleLoginAttempt).where(
        AppleLoginAttempt.state_hash==digest(data.state),AppleLoginAttempt.consumed.is_(False))
        .values(consumed=True))
    if taken.rowcount!=1:
        db.rollback()
        raise HTTPException(409,"Вход уже использован")
    person=db.get(User,record.user_id)
    if not person:raise HTTPException(401,"Пользователь не найден")
    db.commit()
    session_token,csrf=start_session(db,person)
    issue_cookie(response,session_token)
    return {"user":public_user(person),"csrf_token":csrf}

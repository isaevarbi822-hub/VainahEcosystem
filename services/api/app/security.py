"""Local MVP auth. Use a professionally managed OIDC identity provider before public launch."""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import time
import threading
from collections import defaultdict, deque
from urllib.parse import urlsplit

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session
from .database import get_db
from .models import LoginSession, User

COOKIE_NAME = "vainah_session"
SESSION_SECONDS = 14 * 24 * 60 * 60
PASSWORD_HASHER = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)

# A safety net for private, single-instance previews. NOT a substitute for a
# Redis-backed or edge-enforced limiter in a public multi-worker deployment.
_LIMIT_LOCK = threading.Lock()
_AUTH_FAILURES = defaultdict(deque)
_SIGNUP_ATTEMPTS = defaultdict(deque)


def limiter_enabled() -> bool:
    return os.getenv("VAINAH_RATE_LIMIT", "").lower() in {"true", "1", "yes"} or os.getenv("ENVIRONMENT") == "production"


def enforce_auth_limit(kind: str, identifier: str) -> None:
    if not limiter_enabled():
        return
    store, max_attempts, window = (_AUTH_FAILURES, 8, 15 * 60) if kind == "login" else (_SIGNUP_ATTEMPTS, 5, 60 * 60)
    key = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    with _LIMIT_LOCK:
        now = time.monotonic()
        history = store[key]
        while history and now - history[0] >= window:
            history.popleft()
        if len(history) >= max_attempts:
            raise HTTPException(status_code=429, detail="Слишком много попыток. Повторите позже.")


def count_auth_attempt(kind: str, identifier: str) -> None:
    if not limiter_enabled():
        return
    store = _AUTH_FAILURES if kind == "login" else _SIGNUP_ATTEMPTS
    key = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    with _LIMIT_LOCK:
        store[key].append(time.monotonic())


def clear_login_attempts(identifier: str) -> None:
    key = hashlib.sha256(identifier.encode("utf-8")).hexdigest()
    with _LIMIT_LOCK:
        _AUTH_FAILURES.pop(key, None)



def hash_password(password: str) -> str:
    return PASSWORD_HASHER.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return PASSWORD_HASHER.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError):
        return False


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def start_session(db: Session, user: User) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf = secrets.token_urlsafe(32)
    db.add(LoginSession(user_id=user.id, token_hash=token_digest(token), csrf_token=csrf,
                        expires_at=int(time.time()) + SESSION_SECONDS))
    db.commit()
    return token, csrf


def current_session(request: Request, db: Session = Depends(get_db)) -> LoginSession:
    token = request.cookies.get(COOKIE_NAME)
    if not token or len(token) > 256:
        raise HTTPException(status_code=401, detail="Требуется вход в Vainah ID")
    record = db.scalar(select(LoginSession).where(LoginSession.token_hash == token_digest(token)))
    if record is None or record.expires_at <= int(time.time()):
        raise HTTPException(status_code=401, detail="Сеанс завершён. Войдите снова.")
    return record


def current_user(db: Session = Depends(get_db), session: LoginSession = Depends(current_session)) -> User:
    user = db.get(User, session.user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="Пользователь не найден")
    return user


def csrf_protect(request: Request, session: LoginSession = Depends(current_session)) -> None:
    supplied = request.headers.get("X-CSRF-Token", "")
    if not supplied or not hmac.compare_digest(supplied, session.csrf_token):
        raise HTTPException(status_code=403, detail="Неверный CSRF-токен")


def enforce_origin(request: Request) -> None:
    """Prevent browser cross-origin POST requests; CSRF remains required for session writes."""
    origin = request.headers.get("Origin")
    if not origin:
        return  # CLI clients do not send Origin; state-changing session writes still need CSRF.
    configured = os.getenv("APP_ORIGIN", "").strip().rstrip("/")
    expected = configured or f"{request.url.scheme}://{request.url.netloc}"
    try:
        actual = urlsplit(origin)
        target = urlsplit(expected)
    except ValueError:
        raise HTTPException(status_code=403, detail="Недопустимый Origin")
    if (actual.scheme, actual.netloc) != (target.scheme, target.netloc):
        raise HTTPException(status_code=403, detail="Запрос с другого сайта запрещён")


def secure_cookie_enabled() -> bool:
    return os.getenv("COOKIE_SECURE", "false").lower() in {"true", "1", "yes"}


def ensure_safe_environment() -> None:
    if os.getenv("ENVIRONMENT", "development").lower() == "production":
        if not secure_cookie_enabled():
            raise RuntimeError("COOKIE_SECURE=true is mandatory in production")
        if not os.getenv("APP_ORIGIN", "").startswith("https://"):
            raise RuntimeError("APP_ORIGIN=https://... is mandatory in production")
        if not os.getenv("VAINAH_SIGNUP_CODE", ""):
            raise RuntimeError("Set VAINAH_SIGNUP_CODE to prevent open unverified registrations")

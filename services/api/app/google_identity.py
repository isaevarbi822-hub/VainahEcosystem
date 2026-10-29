"""Optional Sign in with Google for hosted Vainah web apps.

Google ID tokens are verified server-side, never by trusting an email alone.
Embedded WebViews require a platform-native flow; they must not run Google OAuth.
"""
from __future__ import annotations
import os
from fastapi import HTTPException

def google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()

def verify_google_credential(credential: str) -> dict[str, str]:
    audience = google_client_id()
    if not audience:
        raise HTTPException(status_code=503, detail="Вход через Google пока не настроен")
    if not (30 <= len(credential) <= 12000):
        raise HTTPException(status_code=401, detail="Недействительный Google-токен")
    try:
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
        claims = id_token.verify_oauth2_token(
            credential, google_requests.Request(), audience=audience
        )
    except Exception as exc:
        raise HTTPException(status_code=401, detail="Не удалось подтвердить вход Google") from exc
    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Неверный издатель Google-токена")
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Email в Google не подтверждён")
    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not subject or len(subject) > 255:
        raise HTTPException(status_code=401, detail="Некорректный Google ID")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        raise HTTPException(status_code=401, detail="В Google-аккаунте нет email")
    email = email.strip().lower()
    name = claims.get("name")
    if not isinstance(name, str) or not name.strip():
        name = email.split("@")[0]
    return {"sub": subject, "email": email, "name": name.strip()[:80]}

"""Server-side Google Identity Services ID-token verification.

No token, email address, or sensitive Google claim is logged on failure.
Embedded WebViews must use platform-approved external-browser sign-in.
"""
from __future__ import annotations

import logging
import os

from fastapi import HTTPException

_LOG = logging.getLogger(__name__)


def google_client_id() -> str:
    return os.getenv("GOOGLE_CLIENT_ID", "").strip()


def _invalid_reason(exc: ValueError) -> str:
    """Map untrusted exception messages to bounded diagnostic categories."""
    message = str(exc).lower()
    if "audience" in message:
        return "audience_mismatch"
    if "expired" in message or "expiration" in message:
        return "expired_token"
    if "issuer" in message:
        return "issuer_mismatch"
    if "signature" in message:
        return "invalid_signature"
    return "invalid_token"


def verify_google_credential(credential: str) -> dict[str, str]:
    audience = google_client_id()
    if not audience:
        raise HTTPException(status_code=503, detail="Вход через Google пока не настроен")
    if not (30 <= len(credential) <= 12000):
        raise HTTPException(status_code=401, detail="Недействительный Google-токен")

    try:
        from google.auth.exceptions import TransportError
        from google.auth.transport import requests as google_requests
        from google.oauth2 import id_token
    except (ImportError, AttributeError) as exc:
        _LOG.error("Google login unavailable: missing Python dependency (%s)", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Серверу не хватает библиотеки проверки Google. Требуется обновление зависимостей.",
        ) from exc

    try:
        claims = id_token.verify_oauth2_token(
            credential, google_requests.Request(), audience=audience
        )
    except TransportError as exc:
        _LOG.warning("Google login unavailable: certificate_fetch_failed")
        raise HTTPException(
            status_code=503,
            detail="Не удалось подключиться к Google для проверки входа. Попробуйте позже.",
        ) from exc
    except ValueError as exc:
        reason = _invalid_reason(exc)
        _LOG.warning("Google login rejected: %s", reason)
        if reason == "audience_mismatch":
            message = "Google Client ID не совпадает. Проверьте настройки Google Cloud и Render."
        elif reason == "expired_token":
            message = "Время действия входа Google истекло. Повторите вход."
        else:
            message = "Google отклонил токен. Обновите страницу и попробуйте ещё раз."
        raise HTTPException(status_code=401, detail=message) from exc
    except Exception as exc:
        _LOG.error("Google login server error: %s", type(exc).__name__)
        raise HTTPException(
            status_code=503,
            detail="Ошибка проверки Google на сервере. Администратор может проверить логи Render.",
        ) from exc

    if claims.get("iss") not in {"accounts.google.com", "https://accounts.google.com"}:
        raise HTTPException(status_code=401, detail="Неверный издатель Google-токена")
    if claims.get("email_verified") is not True:
        raise HTTPException(status_code=401, detail="Email в Google не подтверждён")
    subject = claims.get("sub")
    email = claims.get("email")
    if not isinstance(subject, str) or not subject or len(subject) > 254:
        raise HTTPException(status_code=401, detail="Некорректный Google ID")
    if not isinstance(email, str) or "@" not in email or len(email) > 254:
        raise HTTPException(status_code=401, detail="В Google-аккаунте нет email")
    email = email.strip().lower()
    name = claims.get("name")
    if not isinstance(name, str) or not name.strip():
        name = email.split("@")[0]
    return {"sub": subject, "email": email, "name": name.strip()[:80]}

"""Authenticated encryption at rest for Messenger message text.

This protects stored message bodies against a database-only compromise when
VAINAH_MESSAGE_ENCRYPTION_KEY is provisioned outside the database. It is not
end-to-end encryption: the API server holds the key and decrypts for clients.

New rows are encrypted; old plaintext rows remain readable until migrated.
Losing or rotating the key without decrypting existing rows loses message access.
"""
from __future__ import annotations

import base64
import os
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator

PREFIX = "vainah:gcm:v1:"
AAD = b"Vainah Messenger:message-body:v1"

def key_bytes() -> bytes | None:
    encoded = os.getenv("VAINAH_MESSAGE_ENCRYPTION_KEY", "").strip()
    if not encoded:
        return None
    try:
        decoded = base64.urlsafe_b64decode(encoded + "=" * (-len(encoded) % 4))
    except Exception as exc:
        raise RuntimeError("VAINAH_MESSAGE_ENCRYPTION_KEY must be URL-safe base64") from exc
    if len(decoded) != 32:
        raise RuntimeError("VAINAH_MESSAGE_ENCRYPTION_KEY must encode exactly 32 random bytes")
    return decoded

def seal(value: str) -> str:
    if value.startswith(PREFIX):
        raise ValueError("Message plaintext cannot start with the reserved encrypted prefix")
    key = key_bytes()
    if key is None:
        return value
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, value.encode("utf-8"), AAD)
    return PREFIX + base64.urlsafe_b64encode(nonce + ciphertext).decode("ascii")

def open_message(value: str) -> str:
    if not value.startswith(PREFIX):
        return value  # Existing, pre-encryption database rows.
    key = key_bytes()
    if key is None:
        raise RuntimeError("Encrypted Vainah messages require VAINAH_MESSAGE_ENCRYPTION_KEY")
    try:
        raw = base64.urlsafe_b64decode(value[len(PREFIX):])
        if len(raw) < 28:
            raise ValueError("Invalid encrypted message length")
        return AESGCM(key).decrypt(raw[:12], raw[12:], AAD).decode("utf-8")
    except Exception as exc:
        raise RuntimeError("Encrypted Vainah message cannot be decrypted; verify the server key") from exc

class EncryptedMessageText(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        return seal(value) if value is not None else None
    def process_result_value(self, value, dialect):
        return open_message(value) if value is not None else None

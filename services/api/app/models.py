"""Account, session and notes tables shared by all future Vainah apps."""
from __future__ import annotations

import time
import uuid
from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base


def now() -> int:
    return int(time.time())


def uid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    display_name: Mapped[str] = mapped_column(String(80))
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    notes: Mapped[list[Note]] = relationship(back_populates="owner", cascade="all, delete-orphan")
    sessions: Mapped[list[LoginSession]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class LoginSession(Base):
    __tablename__ = "login_sessions"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    csrf_token: Mapped[str] = mapped_column(String(80))
    expires_at: Mapped[int] = mapped_column(Integer, index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    owner: Mapped[User] = relationship(back_populates="sessions")


class Note(Base):
    __tablename__ = "notes"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160), default="Без названия")
    content: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)
    owner: Mapped[User] = relationship(back_populates="notes")


Index("ix_notes_user_updated", Note.user_id, Note.updated_at)


class AppRecord(Base):
    """User-scoped structured records for Calendar, Study, Maps, Browser, and playlists."""
    __tablename__ = "app_records"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    kind: Mapped[str] = mapped_column(String(32), index=True)
    payload: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    updated_at: Mapped[int] = mapped_column(Integer, default=now)


Index("ix_app_records_user_kind", AppRecord.user_id, AppRecord.kind)


class DirectMessage(Base):
    __tablename__ = "direct_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    recipient_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


Index("ix_messages_pair_created", DirectMessage.sender_id, DirectMessage.recipient_id, DirectMessage.created_at)


class PrivateMedia(Base):
    __tablename__ = "private_media"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    category: Mapped[str] = mapped_column(String(12), index=True)
    filename: Mapped[str] = mapped_column(String(180))
    media_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class PrivateMediaBlob(Base):
    """Optional database-backed media for ephemeral deployments (Render + Neon)."""
    __tablename__ = "private_media_blobs"
    id: Mapped[str] = mapped_column(ForeignKey("private_media.id", ondelete="CASCADE"), primary_key=True)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)

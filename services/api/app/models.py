"""Account, session and notes tables shared by all future Vainah apps."""
from __future__ import annotations

import time
import uuid
from sqlalchemy import ForeignKey, Index, Integer, LargeBinary, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base
from .message_crypto import EncryptedMessageText


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

class VerifiedAccount(Base):
    """Admin-issued verification; separate table preserves existing user schema."""
    __tablename__ = "verified_accounts"
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    verified_at: Mapped[int] = mapped_column(Integer, default=now)
    verified_by: Mapped[str] = mapped_column(String(36))


class LinkedIdentity(Base):
    """Stable external identity; Google account IDs are never inferred from email."""
    __tablename__ = "linked_identities"
    __table_args__ = (UniqueConstraint("provider", "subject", name="uq_linked_identity_provider_subject"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    provider: Mapped[str] = mapped_column(String(32), index=True)
    subject: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[int] = mapped_column(Integer, default=now)


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
    body: Mapped[str] = mapped_column(EncryptedMessageText())
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


class MessageDetails(Base):
    """Separate table so existing 0.4 PostgreSQL messages do not need column changes."""
    __tablename__ = "message_details"
    message_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), primary_key=True)
    edited_at: Mapped[int | None] = mapped_column(Integer, nullable=True)
    deleted_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MessageReceipt(Base):
    __tablename__ = "message_receipts"
    message_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[int] = mapped_column(Integer, default=now)


class MessageReaction(Base):
    __tablename__ = "message_reactions"
    __table_args__ = (UniqueConstraint("message_id", "user_id", name="uq_message_reaction_person"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    message_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    emoji: Mapped[str] = mapped_column(String(8))


class MessageAttachment(Base):
    __tablename__ = "message_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    message_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(160))
    media_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary)


class MessengerBlock(Base):
    __tablename__ = "messenger_blocks"
    __table_args__ = (UniqueConstraint("owner_id", "target_id", name="uq_messenger_block"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    target_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class MessengerReport(Base):
    __tablename__ = "messenger_reports"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    reporter_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), index=True)
    reason: Mapped[str] = mapped_column(String(240))
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class MessengerChatPreference(Base):
    """Private per-user chat controls; no changes to legacy message rows."""
    __tablename__ = "messenger_chat_preferences"
    __table_args__ = (UniqueConstraint("user_id", "contact_id", name="uq_messenger_chat_preference"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    pinned: Mapped[bool] = mapped_column(default=False)
    archived: Mapped[bool] = mapped_column(default=False)
    muted: Mapped[bool] = mapped_column(default=False)


class MessageReply(Base):
    """Optional quote relation for 0.6 direct messages."""
    __tablename__ = "message_replies"
    message_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), primary_key=True)
    replied_to_id: Mapped[str] = mapped_column(ForeignKey("direct_messages.id", ondelete="CASCADE"), index=True)


class MessengerGroup(Base):
    __tablename__ = "messenger_groups"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    name: Mapped[str] = mapped_column(String(80))
    owner_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[int] = mapped_column(Integer, default=now)


class MessengerGroupMember(Base):
    __tablename__ = "messenger_group_members"
    __table_args__ = (UniqueConstraint("group_id", "user_id", name="uq_messenger_group_member"),)
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey("messenger_groups.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    joined_at: Mapped[int] = mapped_column(Integer, default=now)
    last_read_at: Mapped[int] = mapped_column(Integer, default=0)


class MessengerGroupMessage(Base):
    __tablename__ = "messenger_group_messages"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    group_id: Mapped[str] = mapped_column(ForeignKey("messenger_groups.id", ondelete="CASCADE"), index=True)
    sender_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(EncryptedMessageText())
    created_at: Mapped[int] = mapped_column(Integer, default=now)
    deleted_at: Mapped[int | None] = mapped_column(Integer, nullable=True)


class MessengerGroupAttachment(Base):
    """Private group media; authorization always follows group membership."""
    __tablename__ = "messenger_group_attachments"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uid)
    message_id: Mapped[str] = mapped_column(
        ForeignKey("messenger_group_messages.id", ondelete="CASCADE"), unique=True, index=True)
    filename: Mapped[str] = mapped_column(String(160))
    media_type: Mapped[str] = mapped_column(String(50))
    size: Mapped[int] = mapped_column(Integer)
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)


Index("ix_messenger_group_messages_recent", MessengerGroupMessage.group_id, MessengerGroupMessage.created_at)

"""Stable numeric Vainah account IDs. Independent of @username and internal UUID.

IDs are generated server-side and assigned only once, guarded by a database
uniqueness constraint. Existing users receive an ID at first authenticated read.
"""
from __future__ import annotations
import secrets
from sqlalchemy import ForeignKey, String, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped, Session, mapped_column
from .database import Base

class VainahPublicId(Base):
    __tablename__ = "vainah_public_ids"
    user_id: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    public_id: Mapped[str] = mapped_column(String(10), unique=True,
                                           index=True, nullable=False)

def get_or_create_public_id(db: Session, user_id: str) -> str:
    existing = db.get(VainahPublicId, user_id)
    if existing:
        return existing.public_id
    for _ in range(12):
        # A 10-digit ID; random, not sequential, to limit account enumeration.
        candidate = str(1_000_000_000 + secrets.randbelow(9_000_000_000))
        try:
            with db.begin_nested():
                db.add(VainahPublicId(user_id=user_id, public_id=candidate))
                db.flush()
            db.commit()
            return candidate
        except IntegrityError:
            # May be ID collision or concurrent first-use for the same user.
            db.expire_all()
            existing = db.get(VainahPublicId, user_id)
            if existing:
                return existing.public_id
    raise RuntimeError("Could not assign a unique Vainah ID")

def find_user_by_public_id(db: Session, public_id: str):
    if len(public_id) != 10 or not public_id.isascii() or not public_id.isdigit():
        return None
    from .models import User
    row = db.scalar(select(VainahPublicId).where(VainahPublicId.public_id == public_id))
    return db.get(User, row.user_id) if row else None

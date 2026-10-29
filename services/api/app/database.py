"""Database access and lifecycle for the API."""
import os
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    configured = os.getenv("DATABASE_URL", "").strip()
    if configured:
        # Render/legacy URL prefix compatibility.
        return configured.replace("postgres://", "postgresql+psycopg://", 1).replace(
            "postgresql://", "postgresql+psycopg://", 1
        )
    root = Path(__file__).resolve().parents[3]
    data = root / "data"
    data.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{data / 'vainah.db'}"


def create_session_factory(url: str | None = None):
    url = url or database_url()
    if url.startswith("sqlite:///") and ":memory:" not in url:
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(
        url,
        connect_args={"check_same_thread": False} if url.startswith("sqlite") else {},
        pool_pre_ping=True,
    )
    Base.metadata.create_all(bind=engine)  # MVP only; migrate to Alembic before production.
    return engine, sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db(request: Request):
    session: Session = request.app.state.session_factory()
    try:
        yield session
    finally:
        session.close()

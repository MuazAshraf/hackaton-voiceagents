from __future__ import annotations

import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


def _database_url() -> str:
    url = os.getenv("DATABASE_URL", "").strip()
    if url:
        return url
    local_db = Path(__file__).resolve().parent / "voiceform.db"
    return f"sqlite:///{local_db.as_posix()}"


DATABASE_URL = _database_url()
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def create_tables() -> None:
    from models import AuditEvent, VoiceSession  # noqa: F401

    Base.metadata.create_all(bind=engine)

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Boolean, DateTime, ForeignKey, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class VoiceSession(Base):
    __tablename__ = "voice_sessions"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    call_id: Mapped[str | None] = mapped_column(String(128), nullable=True, index=True)

    captured_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    captured_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    captured_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)

    verified_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    verified_email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    verified_phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    form_submitted: Mapped[bool] = mapped_column(Boolean, default=False)
    contact_source: Mapped[str] = mapped_column(String(20), default="voice")

    booking_uid: Mapped[str | None] = mapped_column(String(128), nullable=True)
    booking_status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    events: Mapped[list["AuditEvent"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    session_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("voice_sessions.session_id"), index=True
    )
    event_type: Mapped[str] = mapped_column(String(80), index=True)
    event_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    session: Mapped[VoiceSession] = relationship(back_populates="events")

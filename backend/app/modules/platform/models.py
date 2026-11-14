from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class SystemSetting(Base):
    """Key/value platform settings (feature flags, AI mode policy). Changes are audited."""
    __tablename__ = "system_settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class Job(IdMixin, Base):
    """Durable background job (transactional outbox). Workers claim with FOR UPDATE SKIP LOCKED."""
    __tablename__ = "jobs"
    __table_args__ = (UniqueConstraint("idempotency_key"),)
    kind: Mapped[str] = mapped_column(String(60), index=True)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)  # queued|running|done|failed|dead
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=5)
    idempotency_key: Mapped[str | None] = mapped_column(String(200))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Notification(IdMixin, Base):
    __tablename__ = "notifications"
    channel: Mapped[str] = mapped_column(String(20))  # email|telegram|inapp
    recipient: Mapped[str] = mapped_column(String(320))
    template: Mapped[str] = mapped_column(String(60))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    classification: Mapped[str] = mapped_column(String(20), default="personal")  # personal|operational|aggregate
    status: Mapped[str] = mapped_column(String(20), default="queued")  # queued|sent|failed|suppressed
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)

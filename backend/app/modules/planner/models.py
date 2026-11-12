from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class Itinerary(IdMixin, TimestampMixin, Base):
    __tablename__ = "itineraries"
    owner_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    current_version: Mapped[int] = mapped_column(Integer, default=1)
    start_date: Mapped[str | None] = mapped_column(String(10))
    share_token_hash: Mapped[str | None] = mapped_column(String(64), unique=True)
    shared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ItineraryVersion(IdMixin, Base):
    __tablename__ = "itinerary_versions"
    __table_args__ = (UniqueConstraint("itinerary_id", "version"),)
    itinerary_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("itineraries.id", ondelete="CASCADE"), index=True)
    version: Mapped[int] = mapped_column(Integer)
    request: Mapped[dict] = mapped_column(JSONB, default=dict)
    plan: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, utcnow


class AnalyticsEvent(IdMixin, Base):
    """Privacy-conscious engagement event: no user id, no IP, no session id, day granularity."""
    __tablename__ = "analytics_events"
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    event_type: Mapped[str] = mapped_column(String(40), index=True)
    destination_slug: Mapped[str | None] = mapped_column(String(100))
    locale: Mapped[str | None] = mapped_column(String(8))
    term: Mapped[str | None] = mapped_column(String(60))  # normalised search term, scrubbed of digits/@
    source: Mapped[str] = mapped_column(String(10), default="client")  # client|server


class TourismMeasurement(IdMixin, Base):
    """Measured tourism activity entered by the Bureau (e.g. site visitor counts) with provenance."""
    __tablename__ = "tourism_measurements"
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    destination_slug: Mapped[str | None] = mapped_column(String(100))
    metric: Mapped[str] = mapped_column(String(40))  # visitors|international_visitors|guided_groups
    value: Mapped[int] = mapped_column(Integer)
    source: Mapped[str] = mapped_column(String(300))
    method_note: Mapped[str] = mapped_column(String(500), default="")
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

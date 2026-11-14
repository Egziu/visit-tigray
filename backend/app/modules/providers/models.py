"""Verified tourism provider directory + future reservation architecture (feature-flagged off)."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

PROVIDER_TYPES = ("hotel", "lodge", "restaurant", "cafe", "tour_operator", "guide", "transport", "museum",
                  "cultural_institution", "handicraft", "community_tourism", "event_organizer")


class Provider(IdMixin, TimestampMixin, Base):
    __tablename__ = "providers"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(160))
    type: Mapped[str] = mapped_column(String(30), index=True)
    area: Mapped[str] = mapped_column(String(120), default="")
    summary_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    services: Mapped[list] = mapped_column(JSONB, default=list)
    contact: Mapped[dict] = mapped_column(JSONB, default=dict)
    availability_note: Mapped[str] = mapped_column(String(500), default="")
    languages: Mapped[list] = mapped_column(JSONB, default=list)
    destination_slugs: Mapped[list] = mapped_column(JSONB, default=list)
    licence_number: Mapped[str | None] = mapped_column(String(80))
    licence_authority: Mapped[str | None] = mapped_column(String(200))
    verification_status: Mapped[str] = mapped_column(String(12), default="unverified", index=True)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verification_expires: Mapped[date | None] = mapped_column(Date)
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    verification_note: Mapped[str | None] = mapped_column(String(1000))
    contact_changed_since_verification: Mapped[bool] = mapped_column(Boolean, default=False)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class ProviderMember(Base):
    __tablename__ = "provider_members"
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(10), default="owner")


class VerificationRequest(IdMixin, Base):
    __tablename__ = "provider_verification_requests"
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), index=True)
    submitted_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    licence_number: Mapped[str] = mapped_column(String(80))
    licence_authority: Mapped[str] = mapped_column(String(200))
    evidence_note: Mapped[str] = mapped_column(Text, default="")
    document_media_ids: Mapped[list] = mapped_column(JSONB, default=list)
    status: Mapped[str] = mapped_column(String(12), default="pending")
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    decision_note: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Inquiry(IdMixin, Base):
    __tablename__ = "provider_inquiries"
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"), index=True)
    visitor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    message: Mapped[str] = mapped_column(String(3000))
    travel_dates: Mapped[str | None] = mapped_column(String(100))
    group_size: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(10), default="new")
    reply: Mapped[str | None] = mapped_column(String(3000))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class BookingRequest(IdMixin, TimestampMixin, Base):
    """Reservation architecture (quote -> request -> confirm/cancel -> refund -> reconcile).

    Endpoints are disabled by the ``bookings``/``payments`` feature flags until institutional, legal,
    security and operational approvals exist. No payment provider is integrated.
    """
    __tablename__ = "booking_requests"
    provider_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("providers.id", ondelete="CASCADE"))
    visitor_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    status: Mapped[str] = mapped_column(String(20), default="requested")  # quoted|requested|confirmed|cancelled|refunded
    details: Mapped[dict] = mapped_column(JSONB, default=dict)
    quote_amount_minor: Mapped[int | None] = mapped_column(Integer)
    currency: Mapped[str | None] = mapped_column(String(3))
    idempotency_key: Mapped[str] = mapped_column(String(80), unique=True)

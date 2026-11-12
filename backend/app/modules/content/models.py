"""Destination CMS, categories, aliases, advisories and events."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from geoalchemy2 import Geography
from sqlalchemy import (Boolean, Date, DateTime, Float, ForeignKey, Index, Integer, String, Text, UniqueConstraint)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

LOCALES = ("en", "ti", "am")


class Category(IdMixin, TimestampMixin, Base):
    """Editor-defined destination categories — new ones need no code change."""
    __tablename__ = "categories"
    slug: Mapped[str] = mapped_column(String(80), unique=True)
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    icon: Mapped[str | None] = mapped_column(String(40))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Destination(IdMixin, TimestampMixin, Base):
    """Working copy (edited by staff) + immutable published snapshot (served to the public)."""
    __tablename__ = "destinations"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    category_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"))
    interests: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    area: Mapped[str] = mapped_column(String(120), default="")
    status: Mapped[str] = mapped_column(String(20), default="draft", index=True)  # draft|in_review|scheduled|published|archived
    publish_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Geography: precise location is staff-only when sensitivity != public.
    location = mapped_column(Geography("POINT", srid=4326, spatial_index=False), nullable=True)
    location_sensitivity: Mapped[str] = mapped_column(String(10), default="public")  # public|coarse|hidden
    # Operational facts: null means UNKNOWN and must be displayed as such.
    visit_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    accessibility: Mapped[dict] = mapped_column(JSONB, default=dict)  # {step_free, terrain, facilities, notes} values or 'unknown'
    permit_required: Mapped[str] = mapped_column(String(10), default="unknown")  # yes|no|unknown
    permit_authority: Mapped[str | None] = mapped_column(String(200))
    contact: Mapped[dict] = mapped_column(JSONB, default=dict)
    timeline: Mapped[list] = mapped_column(JSONB, default=list)  # [{period, label_i18n, source_ref}]
    sources: Mapped[list] = mapped_column(JSONB, default=list)  # [{title, author, publisher, year, url, note, knowledge_document_id}]
    heritage_designations: Mapped[list] = mapped_column(JSONB, default=list)
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    verified_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    review_due: Mapped[date | None] = mapped_column(Date)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    updated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    published_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_text: Mapped[str] = mapped_column(Text, default="")
    published_location = mapped_column(Geography("POINT", srid=4326, spatial_index=False), nullable=True)  # coarsened copy for public queries

    translations: Mapped[list[DestinationTranslation]] = relationship(lazy="selectin", cascade="all, delete-orphan",
                                                                     back_populates="destination")
    category: Mapped[Category | None] = relationship(lazy="joined")

    __table_args__ = (Index("ix_destinations_search_trgm", "search_text", postgresql_using="gin",
                            postgresql_ops={"search_text": "gin_trgm_ops"}),
                      Index("ix_destinations_published_location", "published_location", postgresql_using="gist"),
                      Index("ix_destinations_location", "location", postgresql_using="gist"))


class DestinationTranslation(IdMixin, TimestampMixin, Base):
    __tablename__ = "destination_translations"
    __table_args__ = (UniqueConstraint("destination_id", "locale"),)
    destination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"))
    locale: Mapped[str] = mapped_column(String(8))
    name: Mapped[str] = mapped_column(String(160))
    eyebrow: Mapped[str] = mapped_column(String(160), default="")
    summary: Mapped[str] = mapped_column(Text, default="")
    body: Mapped[str] = mapped_column(Text, default="")
    etiquette: Mapped[str] = mapped_column(Text, default="")
    accessibility_notes: Mapped[str] = mapped_column(Text, default="")
    # machine = AI/MT draft, never presented as reviewed · draft = human draft · reviewed = approved by reviewer
    status: Mapped[str] = mapped_column(String(12), default="draft")
    translated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    destination: Mapped[Destination] = relationship(back_populates="translations")


class DestinationRevision(IdMixin, Base):
    __tablename__ = "destination_revisions"
    __table_args__ = (UniqueConstraint("destination_id", "number"),)
    destination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    number: Mapped[int] = mapped_column(Integer)
    snapshot: Mapped[dict] = mapped_column(JSONB)
    note: Mapped[str] = mapped_column(String(500), default="")
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class PlaceAlias(IdMixin, Base):
    """Aksum / Axum / አክሱም — cross-lingual and variant names for search and retrieval."""
    __tablename__ = "place_aliases"
    __table_args__ = (UniqueConstraint("destination_id", "normalized"),)
    destination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(160))
    normalized: Mapped[str] = mapped_column(String(160), index=True)
    locale: Mapped[str | None] = mapped_column(String(8))
    kind: Mapped[str] = mapped_column(String(20), default="variant")  # official|variant|transliteration|historic


class Advisory(IdMixin, TimestampMixin, Base):
    """Official travel advisory. Level 'travel_not_advised' disables operational itinerary routing."""
    __tablename__ = "advisories"
    title_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    body_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    level: Mapped[str] = mapped_column(String(30))  # info|caution|avoid_nonessential|travel_not_advised
    region_wide: Mapped[bool] = mapped_column(Boolean, default=False)
    destination_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    issuing_authority: Mapped[str] = mapped_column(String(200))
    source_url: Mapped[str | None] = mapped_column(String(500))
    effective_from: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    effective_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="draft")  # draft|published|withdrawn
    published_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class Event(IdMixin, TimestampMixin, Base):
    __tablename__ = "events"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    kind: Mapped[str] = mapped_column(String(30), default="festival")
    starts_on: Mapped[date | None] = mapped_column(Date)
    ends_on: Mapped[date | None] = mapped_column(Date)
    ethiopian_month: Mapped[int | None] = mapped_column(Integer)  # recurring by Ethiopian calendar
    ethiopian_day: Mapped[int | None] = mapped_column(Integer)
    date_note_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id"))
    status: Mapped[str] = mapped_column(String(20), default="draft")
    verified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    sources: Mapped[list] = mapped_column(JSONB, default=list)
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class RouteSegment(IdMixin, TimestampMixin, Base):
    """Verified travel facts between two destinations. Absent segment => unknown, never invented."""
    __tablename__ = "route_segments"
    __table_args__ = (UniqueConstraint("from_id", "to_id", "mode"),)
    from_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"))
    to_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"))
    mode: Mapped[str] = mapped_column(String(20), default="road")
    distance_km: Mapped[float | None] = mapped_column(Float)
    duration_minutes: Mapped[int | None] = mapped_column(Integer)
    condition_note: Mapped[str] = mapped_column(String(500), default="")
    source: Mapped[str] = mapped_column(String(300))
    verified_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    valid_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

"""Tigray Tourism Awards — governed competitions. AI assists administration; humans decide winners."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class Competition(IdMixin, TimestampMixin, Base):
    __tablename__ = "competitions"
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    title_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    rules_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    eligibility_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    prize_description_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    terms_version: Mapped[str] = mapped_column(String(20), default="draft")
    status: Mapped[str] = mapped_column(String(12), default="draft", index=True)  # draft|open|judging|results|closed|cancelled
    opens_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    closes_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    min_age: Mapped[int] = mapped_column(Integer, default=16)
    max_entries_per_category: Mapped[int] = mapped_column(Integer, default=1)
    anonymous_judging: Mapped[bool] = mapped_column(Boolean, default=True)
    public_voting: Mapped[bool] = mapped_column(Boolean, default=False)
    # Gates — each recorded by a different authority before opening.
    legal_terms_approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    legal_terms_approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    funding_confirmed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    funding_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    bureau_authorized_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    bureau_authorized_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    results_published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class CompetitionCategory(IdMixin, Base):
    __tablename__ = "competition_categories"
    __table_args__ = (UniqueConstraint("competition_id", "key"),)
    competition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    key: Mapped[str] = mapped_column(String(60))
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    rubric: Mapped[list] = mapped_column(JSONB, default=list)  # [{key, label, weight, max}]


class Sponsor(IdMixin, Base):
    __tablename__ = "competition_sponsors"
    competition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(200))
    contribution: Mapped[str] = mapped_column(String(1000))
    agreement_ref: Mapped[str] = mapped_column(String(200))
    recorded_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Entry(IdMixin, TimestampMixin, Base):
    __tablename__ = "competition_entries"
    competition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"), index=True)
    category_key: Mapped[str] = mapped_column(String(60))
    entrant_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    memory_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="SET NULL"))
    media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"))
    title: Mapped[str] = mapped_column(String(160))
    statement: Mapped[str] = mapped_column(Text)
    rights_confirmed: Mapped[bool] = mapped_column(Boolean)
    terms_version: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(14), default="submitted")  # submitted|eligible|ineligible|shortlisted|winner|withdrawn|disqualified
    integrity_flags: Mapped[list] = mapped_column(JSONB, default=list)  # duplicate images, text overlap
    review_note: Mapped[str | None] = mapped_column(String(1000))


class JudgeAssignment(IdMixin, Base):
    __tablename__ = "competition_judges"
    __table_args__ = (UniqueConstraint("competition_id", "judge_id"),)
    competition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"))
    judge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    coi_declared_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    conflicted_entry_ids: Mapped[list] = mapped_column(JSONB, default=list)
    coi_statement: Mapped[str | None] = mapped_column(String(2000))


class Score(IdMixin, Base):
    __tablename__ = "competition_scores"
    __table_args__ = (UniqueConstraint("entry_id", "judge_id"),)
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competition_entries.id", ondelete="CASCADE"), index=True)
    judge_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    scores: Mapped[dict] = mapped_column(JSONB)
    weighted_total: Mapped[float] = mapped_column(Float)
    comment: Mapped[str | None] = mapped_column(String(2000))
    submitted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class WinnerProposal(IdMixin, Base):
    __tablename__ = "competition_winner_proposals"
    __table_args__ = (UniqueConstraint("competition_id", "category_key", "rank"),)
    competition_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competitions.id", ondelete="CASCADE"))
    category_key: Mapped[str] = mapped_column(String(60))
    entry_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("competition_entries.id", ondelete="CASCADE"))
    rank: Mapped[int] = mapped_column(Integer, default=1)
    proposed_by: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    rationale: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(12), default="proposed")  # proposed|approved|rejected
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    fulfilment_status: Mapped[str] = mapped_column(String(14), default="not_started")  # not_started|in_progress|fulfilled
    fulfilment_note: Mapped[str | None] = mapped_column(String(1000))

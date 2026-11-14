"""Social layer: Journals (long-form publishing + subscriptions) and Spaces (real-time community channels)."""
from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, Identity, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow

# ------------------------------------------------------------------ Journals

class Publication(TimestampMixin, Base):
    """One publication per creator (their 'newsletter')."""
    __tablename__ = "publications"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    tagline: Mapped[str] = mapped_column(String(200), default="")
    about: Mapped[str] = mapped_column(Text, default="")
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"))


class JournalPost(IdMixin, TimestampMixin, Base):
    __tablename__ = "journal_posts"
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(160))
    subtitle: Mapped[str] = mapped_column(String(240), default="")
    # Structured blocks only (paragraph/heading/quote/image/divider) — never raw HTML.
    blocks: Mapped[list] = mapped_column(JSONB, default=list)
    cover_media_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="SET NULL"))
    destination_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="SET NULL"))
    tags: Mapped[list[str]] = mapped_column(ARRAY(String(40)), default=list)
    locale: Mapped[str] = mapped_column(String(8), default="en")
    status: Mapped[str] = mapped_column(String(12), default="pending", index=True)  # pending|approved|rejected|removed
    featured: Mapped[bool] = mapped_column(Boolean, default=False)
    reading_minutes: Mapped[int] = mapped_column(Integer, default=1)
    consent_publish_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    notify_subscribers: Mapped[bool] = mapped_column(Boolean, default=True)
    subscribers_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    ai_flags: Mapped[list] = mapped_column(JSONB, default=list)
    moderation_note: Mapped[str | None] = mapped_column(String(500))
    moderated_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class JournalLike(Base):
    __tablename__ = "journal_likes"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_posts.id", ondelete="CASCADE"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class JournalComment(IdMixin, Base):
    __tablename__ = "journal_comments"
    post_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_posts.id", ondelete="CASCADE"), index=True)
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    parent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("journal_comments.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(2000))
    status: Mapped[str] = mapped_column(String(12), default="visible")  # visible|pending|removed
    ai_flags: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Subscription(Base):
    __tablename__ = "publication_subscriptions"
    subscriber_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    publication_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("publications.user_id", ondelete="CASCADE"), primary_key=True)
    email_digest: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


# ------------------------------------------------------------------ Spaces

class Space(IdMixin, TimestampMixin, Base):
    __tablename__ = "spaces"
    slug: Mapped[str] = mapped_column(String(60), unique=True)
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    description_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    icon: Mapped[str] = mapped_column(String(16), default="✳")
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class Channel(IdMixin, Base):
    __tablename__ = "space_channels"
    __table_args__ = (UniqueConstraint("space_id", "slug"),)
    space_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), index=True)
    slug: Mapped[str] = mapped_column(String(60))
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    topic_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    kind: Mapped[str] = mapped_column(String(16), default="text")  # text|announcements (moderators post)
    slow_mode_seconds: Mapped[int] = mapped_column(Integer, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, default=100)


class SpaceMember(Base):
    __tablename__ = "space_members"
    space_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("spaces.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    role: Mapped[str] = mapped_column(String(12), default="member")  # member|moderator
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    banned_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SpaceMessage(Base):
    """Monotonic integer ids let clients resume streams with ?after=<id>."""
    __tablename__ = "space_messages"
    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("space_channels.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"))
    body: Mapped[str] = mapped_column(String(4000))
    reply_to_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("space_messages.id", ondelete="SET NULL"))
    status: Mapped[str] = mapped_column(String(10), default="visible")  # visible|held|removed
    ai_flags: Mapped[list] = mapped_column(JSONB, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # bumped on edit/reaction/removal so streams can emit updates
    revision: Mapped[int] = mapped_column(BigInteger, default=0)
    updated_seq: Mapped[int] = mapped_column(BigInteger, default=0, index=True)
    removed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))

    __table_args__ = (Index("ix_space_messages_channel_id_id", "channel_id", "id"),)


class MessageReaction(Base):
    __tablename__ = "space_message_reactions"
    message_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("space_messages.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    emoji: Mapped[str] = mapped_column(String(8), primary_key=True)

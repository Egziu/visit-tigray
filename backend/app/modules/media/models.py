from __future__ import annotations

import uuid

from sqlalchemy import BigInteger, Boolean, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin


class MediaAsset(IdMixin, TimestampMixin, Base):
    """An uploaded image. Lifecycle: quarantine -> (scan) -> clean|infected -> approved|rejected.

    Only re-encoded variants (metadata stripped) are ever served; the original upload bytes are
    never stored.
    """
    __tablename__ = "media_assets"
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    purpose: Mapped[str] = mapped_column(String(20), default="community")  # community|destination|competition|knowledge
    status: Mapped[str] = mapped_column(String(20), default="quarantine", index=True)
    scan_status: Mapped[str] = mapped_column(String(20), default="pending")  # pending|clean|infected|unavailable
    scan_detail: Mapped[str | None] = mapped_column(String(300))
    mime: Mapped[str] = mapped_column(String(40))
    width: Mapped[int] = mapped_column(Integer)
    height: Mapped[int] = mapped_column(Integer)
    bytes: Mapped[int] = mapped_column(BigInteger)
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    phash: Mapped[str] = mapped_column(String(16), index=True)  # 64-bit dHash, hex
    storage_prefix: Mapped[str] = mapped_column(String(200))
    variants: Mapped[dict] = mapped_column(JSONB, default=dict)  # {"sm": {"key","w","h"}, ...}
    original_filename: Mapped[str | None] = mapped_column(String(200))
    exif_stripped: Mapped[bool] = mapped_column(Boolean, default=True)
    had_gps_metadata: Mapped[bool] = mapped_column(Boolean, default=False)
    # Rights and provenance
    license: Mapped[str | None] = mapped_column(String(120))
    credit: Mapped[str | None] = mapped_column(String(200))
    attribution_url: Mapped[str | None] = mapped_column(String(500))
    is_illustrative: Mapped[bool] = mapped_column(Boolean, default=False)
    is_reconstruction: Mapped[bool] = mapped_column(Boolean, default=False)
    is_ai_generated: Mapped[bool] = mapped_column(Boolean, default=False)
    rights_confirmed_by_uploader: Mapped[bool] = mapped_column(Boolean, default=False)
    custodial_approval_ref: Mapped[str | None] = mapped_column(String(200))
    alt_text_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    caption_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))


class DestinationMedia(IdMixin, Base):
    __tablename__ = "destination_media"
    __table_args__ = (UniqueConstraint("destination_id", "media_id"),)
    destination_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id", ondelete="CASCADE"), index=True)
    media_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("media_assets.id", ondelete="CASCADE"))
    sort_order: Mapped[int] = mapped_column(Integer, default=100)
    is_hero: Mapped[bool] = mapped_column(Boolean, default=False)

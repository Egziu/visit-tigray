"""Tigray Knowledge Vault: source-governed documents, permission-classified chunks, knowledge graph."""
from __future__ import annotations

import uuid
from datetime import date, datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import Boolean, Computed, Date, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, TSVECTOR, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin

EMBED_DIM = 384  # changing this requires a migration + full re-index (see docs/LOCAL_AI_ARCHITECTURE.md)
CLASSIFICATIONS = ("public", "internal", "restricted", "sacred")


class KnowledgeDocument(IdMixin, TimestampMixin, Base):
    __tablename__ = "knowledge_documents"
    # Provenance & citation metadata (required by docs/KNOWLEDGE_GOVERNANCE.md)
    title: Mapped[str] = mapped_column(String(400))
    author: Mapped[str | None] = mapped_column(String(300))
    publisher: Mapped[str | None] = mapped_column(String(300))  # or institution
    published_on: Mapped[str | None] = mapped_column(String(40))  # free-form: "1980", "2019-03"
    original_language: Mapped[str] = mapped_column(String(12), default="und")
    detected_language: Mapped[str | None] = mapped_column(String(12))
    rights_status: Mapped[str] = mapped_column(String(30), default="unknown")
    license_note: Mapped[str | None] = mapped_column(String(500))
    url: Mapped[str | None] = mapped_column(String(800))
    citation: Mapped[str | None] = mapped_column(Text)
    destination_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    geographic_scope: Mapped[str | None] = mapped_column(String(200))
    access_classification: Mapped[str] = mapped_column(String(12), default="internal")
    verification_status: Mapped[str] = mapped_column(String(20), default="unverified")  # unverified|verified|disputed
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revalidate_on: Mapped[date | None] = mapped_column(Date)
    # Versioning
    version: Mapped[int] = mapped_column(Integer, default=1)
    supersedes_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id"))
    # Workflow
    status: Mapped[str] = mapped_column(String(20), default="uploaded", index=True)
    status_history: Mapped[list] = mapped_column(JSONB, default=list)
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    approved_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    mime: Mapped[str] = mapped_column(String(80), default="text/plain")
    sha256: Mapped[str] = mapped_column(String(64), index=True)
    storage_key: Mapped[str | None] = mapped_column(String(300))
    extracted_text: Mapped[str | None] = mapped_column(Text)
    scan_status: Mapped[str] = mapped_column(String(20), default="pending")
    injection_flags: Mapped[list] = mapped_column(JSONB, default=list)
    processing_error: Mapped[str | None] = mapped_column(Text)
    retrieval_check: Mapped[dict | None] = mapped_column(JSONB)
    consent_reference: Mapped[str | None] = mapped_column(String(200))  # oral histories: informed-consent record
    custodian_approval_ref: Mapped[str | None] = mapped_column(String(200))  # religious heritage
    is_synthetic: Mapped[bool] = mapped_column(Boolean, default=False)


class KnowledgeChunk(IdMixin, Base):
    __tablename__ = "knowledge_chunks"
    document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"), index=True)
    ordinal: Mapped[int] = mapped_column(Integer)
    text: Mapped[str] = mapped_column(Text)
    folded: Mapped[str] = mapped_column(Text)  # search key: folded + transliterated
    language: Mapped[str] = mapped_column(String(12))
    embedding = mapped_column(Vector(EMBED_DIM))
    embedding_model: Mapped[str] = mapped_column(String(120))
    tsv = mapped_column(TSVECTOR, Computed("to_tsvector('simple', folded)", persisted=True))
    # Denormalised for permission filtering inside SQL (never post-filter in Python only).
    access_classification: Mapped[str] = mapped_column(String(12), index=True)
    destination_ids: Mapped[list[uuid.UUID]] = mapped_column(ARRAY(UUID(as_uuid=True)), default=list)
    published: Mapped[bool] = mapped_column(Boolean, default=False, index=True)

    __table_args__ = (
        Index("ix_knowledge_chunks_tsv", "tsv", postgresql_using="gin"),
        Index("ix_knowledge_chunks_embedding", "embedding", postgresql_using="hnsw",
              postgresql_with={"m": 16, "ef_construction": 64}, postgresql_ops={"embedding": "vector_cosine_ops"}),
        Index("ix_knowledge_chunks_folded_trgm", "folded", postgresql_using="gin", postgresql_ops={"folded": "gin_trgm_ops"}),
    )


class KgEntity(IdMixin, TimestampMixin, Base):
    __tablename__ = "kg_entities"
    kind: Mapped[str] = mapped_column(String(30))  # destination|person|period|artifact|tradition|place
    key: Mapped[str] = mapped_column(String(120), unique=True)
    name_i18n: Mapped[dict] = mapped_column(JSONB, default=dict)
    destination_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("destinations.id"))
    access_classification: Mapped[str] = mapped_column(String(12), default="public")


class KgRelation(IdMixin, TimestampMixin, Base):
    """A sourced claim. Contested claims are kept side by side with their sources, never merged."""
    __tablename__ = "kg_relations"
    subject_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("kg_entities.id", ondelete="CASCADE"), index=True)
    predicate: Mapped[str] = mapped_column(String(60))
    object_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("kg_entities.id", ondelete="CASCADE"))
    object_text: Mapped[str | None] = mapped_column(String(500))
    source_document_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("knowledge_documents.id", ondelete="CASCADE"))
    contested: Mapped[bool] = mapped_column(Boolean, default=False)
    note: Mapped[str | None] = mapped_column(String(500))

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base, IdMixin, TimestampMixin, utcnow


class AIModel(IdMixin, TimestampMixin, Base):
    """Model registry. Weights are NOT stored here or in git — only references and evaluation data."""
    __tablename__ = "ai_models"
    key: Mapped[str] = mapped_column(String(80), unique=True)
    role: Mapped[str] = mapped_column(String(20))  # chat|embedding|rerank|stt|tts|ocr
    provider: Mapped[str] = mapped_column(String(30))  # ollama|llamacpp|vllm|openai_compatible|builtin
    base_url: Mapped[str | None] = mapped_column(String(300))
    model_name: Mapped[str] = mapped_column(String(200))
    version: Mapped[str | None] = mapped_column(String(80))
    license: Mapped[str | None] = mapped_column(String(200))
    commercial_use: Mapped[str] = mapped_column(String(20), default="unknown")  # yes|restricted|no|unknown
    quantization: Mapped[str | None] = mapped_column(String(40))
    profile: Mapped[str] = mapped_column(String(20), default="development")  # development|regional_office|datacenter
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False)
    eval_summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    notes: Mapped[str | None] = mapped_column(Text)


class Conversation(IdMixin, TimestampMixin, Base):
    __tablename__ = "tie_conversations"
    owner_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    channel: Mapped[str] = mapped_column(String(20), default="public")  # public|bureau
    locale: Mapped[str] = mapped_column(String(8), default="en")
    persona: Mapped[str] = mapped_column(String(30), default="storyteller")
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class Message(IdMixin, Base):
    __tablename__ = "tie_messages"
    conversation_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tie_conversations.id", ondelete="CASCADE"), index=True)
    role: Mapped[str] = mapped_column(String(12))  # user|assistant
    content: Mapped[str] = mapped_column(Text)
    citations: Mapped[list] = mapped_column(JSONB, default=list)
    confidence: Mapped[str | None] = mapped_column(String(30))
    mode_used: Mapped[str | None] = mapped_column(String(40))
    provider: Mapped[str | None] = mapped_column(String(120))
    provider_local: Mapped[bool | None] = mapped_column(Boolean)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    warnings: Mapped[list] = mapped_column(JSONB, default=list)
    policy: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Feedback(IdMixin, Base):
    __tablename__ = "tie_feedback"
    message_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("tie_messages.id", ondelete="CASCADE"), index=True)
    rating: Mapped[str] = mapped_column(String(8))
    comment: Mapped[str | None] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class EvalRun(IdMixin, Base):
    __tablename__ = "tie_eval_runs"
    started_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    mode: Mapped[str] = mapped_column(String(40))
    provider: Mapped[str | None] = mapped_column(String(120))
    dataset: Mapped[str] = mapped_column(String(120))
    summary: Mapped[dict] = mapped_column(JSONB, default=dict)
    results: Mapped[list] = mapped_column(JSONB, default=list)
    pass_rate: Mapped[float | None] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

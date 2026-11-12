"""Platform settings, feature flags, durable job queue and notification outbox."""
from __future__ import annotations

import logging
import smtplib
from collections.abc import Callable
from datetime import timedelta
from email.message import EmailMessage
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.modules.platform.models import Job, Notification, SystemSetting

log = logging.getLogger("visit_tigray.jobs")

# Defaults. Flags that move money or open competitions are OFF until approvals exist.
DEFAULTS: dict[str, Any] = {
    "feature_flags": {
        "bookings": False, "payments": False, "public_voting": False, "competitions_live": False,
        "community_uploads": True, "ai_guide": True, "provider_inquiries": True,
    },
    "ai_policy": {
        "mode": get_settings().ai_default_mode,
        "permitted_modes": ["fully_local", "retrieval_only", "deterministic", "offline"],
        "max_tool_calls_per_turn": 3,
        "max_context_chunks": 8,
    },
}


def get_setting(db: Session, key: str) -> dict:
    row = db.get(SystemSetting, key)
    base = dict(DEFAULTS.get(key, {}))
    if row:
        base.update(row.value)
    return base


def set_setting(db: Session, key: str, value: dict, actor_id=None) -> dict:
    merged = get_setting(db, key)
    merged.update(value)
    stmt = insert(SystemSetting).values(key=key, value=merged, updated_by=actor_id, updated_at=utcnow())
    db.execute(stmt.on_conflict_do_update(index_elements=["key"], set_={"value": merged, "updated_by": actor_id,
                                                                       "updated_at": utcnow()}))
    return merged


def flag(db: Session, name: str) -> bool:
    return bool(get_setting(db, "feature_flags").get(name, False))


def require_flag(db: Session, name: str) -> None:
    if not flag(db, name):
        raise AppError(403, "feature_disabled",
                       f"'{name}' is disabled. It requires institutional, legal and security approval before activation.")


# ---------------------------------------------------------------- jobs

def enqueue(db: Session, kind: str, payload: dict, *, idempotency_key: str | None = None,
            delay_seconds: int = 0, max_attempts: int = 5) -> Job | None:
    """Insert a job in the caller's transaction (outbox pattern). Duplicate idempotency keys are no-ops."""
    stmt = insert(Job).values(kind=kind, payload=payload, idempotency_key=idempotency_key,
                              run_after=utcnow() + timedelta(seconds=delay_seconds), max_attempts=max_attempts,
                              status="queued", attempts=0, created_at=utcnow())
    if idempotency_key:
        stmt = stmt.on_conflict_do_nothing(index_elements=["idempotency_key"])
    res = db.execute(stmt.returning(Job.id))
    jid = res.scalar()
    return db.get(Job, jid) if jid else None


HANDLERS: dict[str, Callable[[Session, dict], None]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn
    return deco


def run_due_jobs(db: Session, limit: int = 20) -> int:
    """Claim and run due jobs. Safe with several concurrent workers (SKIP LOCKED)."""
    rows = db.execute(text("""
        SELECT id FROM jobs WHERE status IN ('queued','failed') AND run_after <= now()
        ORDER BY run_after FOR UPDATE SKIP LOCKED LIMIT :n"""), {"n": limit}).scalars().all()
    done = 0
    for jid in rows:
        job = db.get(Job, jid)
        assert job is not None
        job.status, job.locked_at, job.attempts = "running", utcnow(), job.attempts + 1
        db.flush()
        try:
            with db.begin_nested():
                fn = HANDLERS.get(job.kind)
                if fn is None:
                    raise RuntimeError(f"no handler for job kind {job.kind}")
                fn(db, job.payload)
            job.status, job.finished_at, job.last_error = "done", utcnow(), None
            done += 1
        except Exception as exc:  # noqa: BLE001 - recorded on the job
            log.warning("job %s (%s) failed: %s", job.id, job.kind, exc)
            job.last_error = str(exc)[:2000]
            if job.attempts >= job.max_attempts:
                job.status = "dead"
            else:
                job.status = "failed"
                job.run_after = utcnow() + timedelta(seconds=min(3600, 2 ** job.attempts * 15))
    db.commit()
    return done


# ---------------------------------------------------------------- notifications

def notify(db: Session, *, channel: str, recipient: str, template: str, payload: dict,
           classification: str = "personal", user_id=None, idempotency_key: str | None = None) -> Notification:
    """Queue a notification. Personal data can never be routed to group/Telegram channels."""
    if channel == "telegram" and classification == "personal":
        raise AppError(400, "channel_not_permitted", "Personal information cannot be sent to messaging channels.")
    if channel == "telegram" and recipient not in get_settings().telegram_allowed_chat_ids:
        raise AppError(400, "channel_not_permitted", "Telegram chat is not on the authorised allow-list.")
    n = Notification(channel=channel, recipient=recipient, template=template, payload=payload,
                     classification=classification, user_id=user_id)
    db.add(n)
    db.flush()
    if channel != "inapp":
        enqueue(db, "send_notification", {"notification_id": str(n.id)},
                idempotency_key=idempotency_key or f"notif:{n.id}")
    return n


TEMPLATES = {
    "verify_email": ("Verify your Visit Tigray account", "Confirm your email address: {link}\nThis link expires in 24 hours."),
    "reset_password": ("Reset your Visit Tigray password", "Reset your password: {link}\nThis link expires in 30 minutes. If you did not ask for this, ignore this email."),
    "moderation_decision": ("Your story review result", "Your submission \"{title}\" was {decision}. {note}"),
    "provider_inquiry": ("New visitor inquiry", "You have a new inquiry on Visit Tigray. Sign in to read and reply."),
    "report": ("Visit Tigray report", "{body}"),
}


@handler("send_notification")
def _send_notification(db: Session, payload: dict) -> None:
    n = db.get(Notification, payload["notification_id"])
    if n is None or n.status == "sent":
        return
    subject, body_t = TEMPLATES.get(n.template, ("Visit Tigray", "{body}"))
    body = body_t.format_map(_SafeDict(n.payload))
    s = get_settings()
    if n.channel == "email":
        if not s.smtp_host:
            # Development: emails are not sent; the payload stays in the outbox for local inspection.
            n.status, n.last_error = "suppressed", "SMTP not configured (development)"
            return
        msg = EmailMessage()
        msg["From"], msg["To"], msg["Subject"] = s.mail_from, n.recipient, subject
        msg.set_content(body)
        with smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=15) as smtp:  # pragma: no cover - infra
            smtp.starttls()
            if s.smtp_user:
                smtp.login(s.smtp_user, s.smtp_password or "")
            smtp.send_message(msg)
    elif n.channel == "telegram":
        if not s.telegram_bot_token:
            n.status, n.last_error = "suppressed", "Telegram not configured"
            return
        from app.core.egress import guarded_client  # pragma: no cover - infra

        with guarded_client("notification", "cloud_assisted") as c:  # pragma: no cover
            r = c.post(f"https://api.telegram.org/bot{s.telegram_bot_token}/sendMessage",
                       json={"chat_id": n.recipient, "text": f"{subject}\n\n{body}"[:4000]})
            r.raise_for_status()
    n.status, n.sent_at = "sent", utcnow()
    # Scrub one-time links once delivered.
    if "link" in n.payload:
        n.payload = {**n.payload, "link": "[delivered]"}


class _SafeDict(dict):
    def __missing__(self, key):
        return ""


def pending_jobs(db: Session) -> int:
    return db.execute(select(Job).where(Job.status.in_(["queued", "failed"]))).scalars().all().__len__()

from __future__ import annotations

import hashlib
import json
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.modules.audit.models import AuditEvent

GENESIS = "0" * 64
_LOCK_KEY = 77_420_001  # pg advisory lock serialising chain appends

SENSITIVE_KEYS = {"password", "password_hash", "token", "totp_secret", "totp_secret_enc", "secret", "code"}


def _redact(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: ("[redacted]" if k.lower() in SENSITIVE_KEYS else _redact(v)) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    return value


def _digest(prev_hash: str, e: AuditEvent) -> str:
    payload = json.dumps({
        "prev": prev_hash, "at": e.occurred_at.isoformat(), "actor": str(e.actor_id) if e.actor_id else None,
        "label": e.actor_label, "action": e.action, "rtype": e.resource_type, "rid": e.resource_id,
        "outcome": e.outcome, "ip": e.ip, "rq": e.request_id, "changes": e.changes,
    }, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode()).hexdigest()


def record(db: Session, *, action: str, resource_type: str, resource_id: Any = None, actor: Any = None,
           outcome: str = "success", changes: dict | None = None, request: Any = None) -> AuditEvent:
    """Append an audit event inside the caller's transaction.

    ``actor`` may be a Principal, a User, or None (system). ``request`` (a Starlette Request)
    supplies the IP and request id.
    """
    user = getattr(actor, "user", actor)
    actor_id = getattr(user, "id", None)
    actor_label = getattr(user, "email", None) or (str(actor) if isinstance(actor, str) else "system")
    db.execute(text("SELECT pg_advisory_xact_lock(:k)"), {"k": _LOCK_KEY})
    prev = db.execute(select(AuditEvent.hash).order_by(AuditEvent.seq.desc()).limit(1)).scalar()
    ev = AuditEvent(
        occurred_at=utcnow(), actor_id=actor_id, actor_label=actor_label, action=action,
        resource_type=resource_type, resource_id=str(resource_id) if resource_id is not None else None,
        outcome=outcome, changes=_redact(changes) if changes else None,
        ip=(request.client.host if request is not None and request.client else None),
        request_id=getattr(getattr(request, "state", None), "request_id", None),
        prev_hash=prev or GENESIS,
    )
    ev.hash = _digest(ev.prev_hash, ev)
    db.add(ev)
    db.flush()
    return ev


def verify_chain(db: Session) -> dict:
    prev = GENESIS
    count = 0
    for ev in db.execute(select(AuditEvent).order_by(AuditEvent.seq)).scalars():
        count += 1
        if ev.prev_hash != prev or _digest(prev, ev) != ev.hash:
            return {"valid": False, "checked": count, "broken_at_seq": ev.seq}
        prev = ev.hash
    return {"valid": True, "checked": count, "head": prev}

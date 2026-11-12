from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit.models import AuditEvent
from app.modules.audit.service import verify_chain
from app.modules.identity.deps import require

router = APIRouter(prefix="/api/bureau/audit", tags=["audit"])


@router.get("")
def list_events(resource_type: str | None = None, action: str | None = None, before_seq: int | None = None,
                limit: int = Query(50, le=200), _=Depends(require("audit.view")), db: Session = Depends(get_db)):
    q = select(AuditEvent).order_by(AuditEvent.seq.desc()).limit(limit)
    if resource_type:
        q = q.where(AuditEvent.resource_type == resource_type)
    if action:
        q = q.where(AuditEvent.action.like(f"{action}%"))
    if before_seq:
        q = q.where(AuditEvent.seq < before_seq)
    rows = db.execute(q).scalars().all()
    return {"items": [{"seq": e.seq, "occurred_at": e.occurred_at.isoformat(), "actor": e.actor_label,
                       "action": e.action, "resource_type": e.resource_type, "resource_id": e.resource_id,
                       "outcome": e.outcome, "changes": e.changes, "request_id": e.request_id} for e in rows],
            "next_before_seq": rows[-1].seq if len(rows) == limit else None}


@router.get("/verify")
def verify(_=Depends(require("audit.view")), db: Session = Depends(get_db)):
    return verify_chain(db)

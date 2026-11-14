from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.modules.audit import service as audit
from app.modules.identity.deps import require
from app.modules.platform.service import get_setting, set_setting

router = APIRouter(tags=["platform"])

GUARDED_FLAGS = {"bookings", "payments", "competitions_live", "public_voting"}


@router.get("/api/health")
def health(db: Session = Depends(get_db)):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "app": "Visit Tigray", "stage": "pre-release (not an official government service)"}


@router.get("/metrics", include_in_schema=False)
def metrics():
    return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@router.get("/api/config/public")
def public_config(db: Session = Depends(get_db)):
    flags = get_setting(db, "feature_flags")
    return {"feature_flags": flags, "locales": ["en", "ti", "am"], "default_locale": "en"}


class FlagsIn(BaseModel):
    flags: dict[str, bool]
    justification: str


@router.put("/api/bureau/settings/feature-flags")
def update_flags(body: FlagsIn, request: Request, p=Depends(require("settings.manage")), db: Session = Depends(get_db)):
    from app.core.errors import AppError

    turning_on = {k for k, v in body.flags.items() if v and k in GUARDED_FLAGS}
    if turning_on and len(body.justification.strip()) < 40:
        raise AppError(422, "justification_required",
                       "Enabling bookings/payments/competitions/voting requires a written justification referencing the approvals obtained.")
    before = get_setting(db, "feature_flags")
    after = set_setting(db, "feature_flags", body.flags, actor_id=p.id)
    audit.record(db, action="settings.feature_flags", resource_type="setting", resource_id="feature_flags", actor=p,
                 request=request, changes={"before": before, "after": after, "justification": body.justification})
    db.commit()
    return after

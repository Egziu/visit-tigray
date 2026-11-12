from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import date, timedelta
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.core.ethiopic import is_ethiopic, transliterate
from app.core.security import rate_limit
from app.modules.identity.deps import current_principal
from app.modules.identity.service import Principal
from app.modules.planner.engine import PlanRequest, annotate_manual, build_plan
from app.modules.planner.models import Itinerary, ItineraryVersion

router = APIRouter(prefix="/api", tags=["planner"])


class AccessibilityReq(BaseModel):
    step_free_required: bool = False


class PlanIn(BaseModel):
    days: int = Field(default=3, ge=1, le=14)
    start_slug: str | None = Field(default=None, max_length=100)
    interests: list[str] = Field(default_factory=list, max_length=10)
    pace: Literal["relaxed", "balanced", "full"] = "balanced"
    accessibility: AccessibilityReq = AccessibilityReq()
    group_size: int = Field(default=1, ge=1, le=60)
    locale: Literal["en", "ti", "am"] = "en"
    avoid_slugs: list[str] = Field(default_factory=list, max_length=30)


def _req(body: PlanIn) -> PlanRequest:
    return PlanRequest(days=body.days, interests=body.interests, pace=body.pace, start_slug=body.start_slug,
                       step_free_required=body.accessibility.step_free_required, group_size=body.group_size,
                       locale=body.locale, avoid_slugs=body.avoid_slugs)


@router.post("/planner/plan", dependencies=[Depends(rate_limit("default"))])
def plan(body: PlanIn, db: Session = Depends(get_db)):
    from app.modules.analytics.router import track
    out = build_plan(db, _req(body))
    track(db, "plan_created", locale=body.locale)
    db.commit()
    return out


# ---------------------------------------------------------------- saved itineraries

class SaveIn(BaseModel):
    title: str = Field(min_length=2, max_length=160)
    request: PlanIn
    start_date: date | None = None


class EditIn(BaseModel):
    title: str | None = Field(default=None, min_length=2, max_length=160)
    days: list[list[str]] = Field(max_length=14)
    locale: Literal["en", "ti", "am"] = "en"
    start_date: date | None = None
    note: str = Field(default="", max_length=300)


def _own(db: Session, ident: uuid.UUID, p: Principal) -> Itinerary:
    it = db.get(Itinerary, ident)
    if it is None or it.owner_id != p.id:
        raise not_found("Itinerary")  # object-level authorisation; no existence leak
    return it


def _latest(db: Session, it: Itinerary) -> ItineraryVersion:
    v = db.execute(select(ItineraryVersion).where(ItineraryVersion.itinerary_id == it.id,
                                                  ItineraryVersion.version == it.current_version)).scalar_one()
    return v


def _out(db: Session, it: Itinerary) -> dict:
    v = _latest(db, it)
    return {"id": str(it.id), "title": it.title, "version": it.current_version, "start_date": it.start_date,
            "shared": it.share_token_hash is not None, "updated_at": it.updated_at.isoformat(), "plan": v.plan,
            "request": v.request}


@router.post("/itineraries", status_code=201)
def save(body: SaveIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    # The plan is regenerated server-side: clients cannot store arbitrary "verified" facts.
    plan_doc = build_plan(db, _req(body.request))
    if plan_doc["mode"] != "operational":
        raise AppError(409, "travel_not_advised", "Operational itineraries are disabled by an official advisory.")
    it = Itinerary(owner_id=p.id, title=body.title, start_date=body.start_date.isoformat() if body.start_date else None)
    db.add(it)
    db.flush()
    db.add(ItineraryVersion(itinerary_id=it.id, version=1, request=body.request.model_dump(), plan=plan_doc, note="created"))
    db.commit()
    return _out(db, it)


@router.get("/itineraries")
def list_mine(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(Itinerary).where(Itinerary.owner_id == p.id).order_by(Itinerary.updated_at.desc())).scalars()
    return [{"id": str(i.id), "title": i.title, "version": i.current_version, "updated_at": i.updated_at.isoformat(),
             "shared": i.share_token_hash is not None} for i in rows]


@router.get("/itineraries/{ident}")
def get_one(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return _out(db, _own(db, ident, p))


@router.get("/itineraries/{ident}/versions")
def versions(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    it = _own(db, ident, p)
    rows = db.execute(select(ItineraryVersion).where(ItineraryVersion.itinerary_id == it.id)
                      .order_by(ItineraryVersion.version.desc())).scalars()
    return [{"version": v.version, "note": v.note, "created_at": v.created_at.isoformat()} for v in rows]


@router.put("/itineraries/{ident}")
def edit(ident: uuid.UUID, body: EditIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    it = _own(db, ident, p)
    plan_doc = annotate_manual(db, body.days, body.locale)
    it.current_version += 1
    if body.title:
        it.title = body.title
    if body.start_date:
        it.start_date = body.start_date.isoformat()
    it.updated_at = utcnow()
    db.add(ItineraryVersion(itinerary_id=it.id, version=it.current_version, request={"manual": True, "days": body.days},
                            plan=plan_doc, note=body.note or "edited"))
    db.commit()
    return _out(db, it)


@router.delete("/itineraries/{ident}", status_code=204)
def delete(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    db.delete(_own(db, ident, p))
    db.commit()
    return Response(status_code=204)


@router.post("/itineraries/{ident}/share")
def share(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    it = _own(db, ident, p)
    token = secrets.token_urlsafe(18)
    it.share_token_hash, it.shared_at = hashlib.sha256(token.encode()).hexdigest(), utcnow()  # rotating revokes old link
    db.commit()
    return {"token": token, "url": f"{get_settings().public_base_url}/en/plan/shared/{token}"}


@router.delete("/itineraries/{ident}/share")
def unshare(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    it = _own(db, ident, p)
    it.share_token_hash, it.shared_at = None, None
    db.commit()
    return {"shared": False}


@router.get("/shared-itineraries/{token}", dependencies=[Depends(rate_limit("default"))])
def shared(token: str, db: Session = Depends(get_db)):
    it = db.execute(select(Itinerary).where(Itinerary.share_token_hash == hashlib.sha256(token.encode()).hexdigest())
                    ).scalar_one_or_none()
    if it is None:
        raise not_found("Shared itinerary")
    v = _latest(db, it)
    return {"title": it.title, "version": it.current_version, "start_date": it.start_date, "plan": v.plan}  # no owner data


# ---------------------------------------------------------------- exports

def _ics_escape(s: str) -> str:
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(it: Itinerary, plan_doc: dict, start: date) -> str:
    stamp = utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Visit Tigray//Itinerary//EN", "CALSCALE:GREGORIAN"]
    for day in plan_doc["days"]:
        d0 = start + timedelta(days=day["day"] - 1)
        names = ", ".join(s["name"] for s in day["stops"]) or "Flexible day"
        desc = "\n".join(f"- {s['name']}" for s in day["stops"]) + "\n\n" + plan_doc["notice"]
        summary = f"Day {day['day']}: {names}"
        lines += ["BEGIN:VEVENT", f"UID:{it.id}-{day['day']}@visit-tigray", f"DTSTAMP:{stamp}",
                  f"DTSTART;VALUE=DATE:{d0:%Y%m%d}", f"DTEND;VALUE=DATE:{d0 + timedelta(days=1):%Y%m%d}",
                  f"SUMMARY:{_ics_escape(summary)[:300]}",
                  f"DESCRIPTION:{_ics_escape(desc)[:1500]}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    # RFC 5545: CRLF line endings
    return "\r\n".join(lines) + "\r\n"


@router.get("/itineraries/{ident}/ics")
def ics(ident: uuid.UUID, start_date: date | None = None, p: Principal = Depends(current_principal),
        db: Session = Depends(get_db)):
    it = _own(db, ident, p)
    start = start_date or (date.fromisoformat(it.start_date) if it.start_date else None)
    if start is None:
        raise AppError(422, "start_date_required", "Choose a start date to export to a calendar.")
    body = build_ics(it, _latest(db, it).plan, start)
    return Response(body, media_type="text/calendar; charset=utf-8",
                    headers={"Content-Disposition": f'attachment; filename="itinerary-{it.id.hex[:8]}.ics"'})


FONT_CANDIDATES = ["/usr/share/fonts/truetype/freefont/FreeSerif.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"]


@router.get("/itineraries/{ident}/pdf")
def pdf(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    from fpdf import FPDF

    it = _own(db, ident, p)
    plan_doc = _latest(db, it).plan
    doc = FPDF(format="A4")
    doc.set_margins(18, 18, 18)
    doc.add_page()
    font = next((f for f in FONT_CANDIDATES if Path(f).exists()), None)
    ethiopic_ok = bool(font and "FreeSerif" in font)
    if font:
        doc.add_font("Body", "", font)
        doc.set_font("Body", size=11)
    else:  # pragma: no cover - core font fallback
        doc.set_font("Helvetica", size=11)

    def txt(s: str) -> str:
        return s if (ethiopic_ok or not is_ethiopic(s)) else transliterate(s)

    w = doc.epw
    doc.set_font_size(18)
    doc.multi_cell(w, 9, txt(it.title), new_x="LMARGIN", new_y="NEXT")
    doc.set_font_size(9)
    doc.multi_cell(w, 5, txt(plan_doc["notice"]), new_x="LMARGIN", new_y="NEXT")
    doc.ln(3)
    for day in plan_doc["days"]:
        doc.set_font_size(13)
        doc.multi_cell(w, 7, f"Day {day['day']}", new_x="LMARGIN", new_y="NEXT")
        doc.set_font_size(10)
        for s in day["stops"]:
            t = s.get("travel_from_previous") or {}
            dist = f" — {t['distance_km']} km ({'verified' if t.get('verified') else 'straight-line'})" if t.get("distance_km") else ""
            dur = f"{s['visit_duration_minutes']} min" if s.get("visit_duration_minutes") else "duration unknown"
            doc.multi_cell(w, 5.5, txt(f"• {s['name']} ({s.get('area') or ''}) · {dur} · permit: {s.get('permit_required')}{dist}"),
                           new_x="LMARGIN", new_y="NEXT")
        for u in day.get("unknowns", []):
            doc.multi_cell(w, 5, txt(f"  ! {u}"), new_x="LMARGIN", new_y="NEXT")
        doc.ln(2)
    doc.set_font_size(8)
    doc.multi_cell(w, 4.5, f"Generated {utcnow():%Y-%m-%d %H:%M} UTC by Visit Tigray (pre-release; not an official "
                           "government service).", new_x="LMARGIN", new_y="NEXT")
    return Response(bytes(doc.output()), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="itinerary-{it.id.hex[:8]}.pdf"'})

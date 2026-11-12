"""Tourism intelligence: engagement analytics, measured tourism, reports with provenance."""
from __future__ import annotations

import csv
import io
import re
from datetime import date, datetime, time, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.core.ethiopic import fold_for_search
from app.core.security import rate_limit
from app.modules.analytics.models import AnalyticsEvent, TourismMeasurement
from app.modules.audit import service as audit
from app.modules.community.models import Memory, Report
from app.modules.content.models import Destination
from app.modules.identity.deps import require
from app.modules.identity.service import Principal
from app.modules.platform.service import notify
from app.modules.providers.models import Inquiry
from app.modules.tie.models import Feedback, Message

router = APIRouter(prefix="/api", tags=["analytics"])

EVENT_TYPES = Literal["page_view", "destination_view", "search", "plan_created", "itinerary_saved", "guide_question",
                      "memory_view", "offline_pack_saved", "map_view"]
NOTICE = ("Website engagement counts describe use of this platform, not tourism arrivals. Measured tourism figures "
          "come only from Bureau-recorded sources listed with each value. No forecasts are produced.")


def scrub_term(term: str | None) -> str | None:
    if not term:
        return None
    t = fold_for_search(term)[:60]
    if re.search(r"[\d@]", t) or len(t) < 2:
        return None  # drop anything that could be an email, phone, ID or booking reference
    return t


def track(db: Session, event_type: str, destination_slug: str | None = None, locale: str | None = None,
          source: str = "server") -> None:
    db.add(AnalyticsEvent(occurred_on=date.today(), event_type=event_type, destination_slug=destination_slug,
                          locale=locale, source=source))


class EventIn(BaseModel):
    event_type: EVENT_TYPES
    destination_slug: str | None = Field(default=None, max_length=100)
    locale: Literal["en", "ti", "am"] | None = None
    term: str | None = Field(default=None, max_length=120)
    consent: bool  # the client only sends events after the visitor has accepted analytics


@router.post("/analytics/events", status_code=202, dependencies=[Depends(rate_limit("write", 120))])
def collect(body: EventIn, db: Session = Depends(get_db)):
    if not body.consent:
        return {"status": "ignored"}
    db.add(AnalyticsEvent(occurred_on=date.today(), event_type=body.event_type, destination_slug=body.destination_slug,
                          locale=body.locale, term=scrub_term(body.term) if body.event_type == "search" else None))
    db.commit()
    return {"status": "accepted"}


def _range(frm: date | None, to: date | None) -> tuple[date, date]:
    to = to or date.today()
    frm = frm or (to - timedelta(days=29))
    if frm > to or (to - frm).days > 731:
        raise AppError(422, "invalid_range", "Choose a range of at most two years.")
    return frm, to


def summary(db: Session, frm: date, to: date) -> dict:
    by_type = dict(db.execute(select(AnalyticsEvent.event_type, func.count()).where(AnalyticsEvent.occurred_on.between(frm, to))
                              .group_by(AnalyticsEvent.event_type)).all())
    by_day = [{"day": d.isoformat(), "count": n} for d, n in db.execute(
        select(AnalyticsEvent.occurred_on, func.count()).where(AnalyticsEvent.occurred_on.between(frm, to))
        .group_by(AnalyticsEvent.occurred_on).order_by(AnalyticsEvent.occurred_on)).all()]
    top_dest = [{"slug": s, "views": n} for s, n in db.execute(
        select(AnalyticsEvent.destination_slug, func.count()).where(AnalyticsEvent.occurred_on.between(frm, to),
                                                                    AnalyticsEvent.destination_slug.is_not(None))
        .group_by(AnalyticsEvent.destination_slug).order_by(func.count().desc()).limit(10)).all()]
    locales = dict(db.execute(select(AnalyticsEvent.locale, func.count()).where(AnalyticsEvent.occurred_on.between(frm, to),
                                                                                AnalyticsEvent.locale.is_not(None))
                              .group_by(AnalyticsEvent.locale)).all())
    terms = [{"term": t, "count": n} for t, n in db.execute(
        select(AnalyticsEvent.term, func.count()).where(AnalyticsEvent.occurred_on.between(frm, to),
                                                        AnalyticsEvent.term.is_not(None))
        .group_by(AnalyticsEvent.term).having(func.count() >= 3)  # k-anonymity threshold for search terms
        .order_by(func.count().desc()).limit(20)).all()]
    start = datetime.combine(frm, time.min, tzinfo=timezone.utc)
    end = start + timedelta(days=(to - frm).days + 1)
    conf = dict(db.execute(select(Message.confidence, func.count()).where(Message.role == "assistant",
                                                                         Message.created_at >= start, Message.created_at < end)
                           .group_by(Message.confidence)).all())
    lat = db.execute(select(func.percentile_cont(0.5).within_group(Message.latency_ms),
                            func.percentile_cont(0.95).within_group(Message.latency_ms))
                     .where(Message.role == "assistant", Message.created_at >= start, Message.created_at < end)).one()
    fb = dict(db.execute(select(Feedback.rating, func.count()).where(Feedback.created_at >= start, Feedback.created_at < end)
                         .group_by(Feedback.rating)).all())
    answered = sum(v for k, v in conf.items() if k in ("grounded", "partial"))
    total_ans = sum(conf.values())
    measured = [{"period_start": m.period_start.isoformat(), "period_end": m.period_end.isoformat(),
                 "destination_slug": m.destination_slug, "metric": m.metric, "value": m.value, "source": m.source,
                 "method_note": m.method_note}
                for m in db.execute(select(TourismMeasurement).where(TourismMeasurement.period_end >= frm,
                                                                     TourismMeasurement.period_start <= to)
                                    .order_by(TourismMeasurement.period_start)).scalars()]
    dests = db.execute(select(Destination).where(Destination.status != "archived")).scalars().all()
    return {
        "generated_at": utcnow().isoformat(), "filters": {"from": frm.isoformat(), "to": to.isoformat()}, "notice": NOTICE,
        "website_engagement": {"kind": "website_engagement", "by_event_type": by_type, "by_day": by_day,
                               "top_destinations": top_dest, "locales": locales, "top_search_terms": terms},
        "ai": {"answers_by_confidence": conf, "retrieval_success_rate": round(answered / total_ans, 3) if total_ans else None,
               "latency_ms_p50": lat[0], "latency_ms_p95": lat[1], "feedback": fb},
        "operations": {
            "pending_moderation": db.execute(select(func.count()).select_from(Memory).where(Memory.status == "pending")).scalar(),
            "open_reports": db.execute(select(func.count()).select_from(Report).where(Report.status == "open")).scalar(),
            "provider_inquiries": db.execute(select(func.count()).select_from(Inquiry).where(
                Inquiry.created_at >= start, Inquiry.created_at < end)).scalar(),
            "destinations_never_verified": sum(1 for d in dests if d.verified_at is None),
            "destinations_total": len(dests)},
        "measured_tourism": {"kind": "measured", "items": measured},
        "forecasts": {"kind": "modeled", "items": [], "note": "Not implemented — no validated forecasting model."},
    }


@router.get("/bureau/analytics/summary")
def get_summary(frm: date | None = None, to: date | None = None, _=Depends(require("analytics.view")),
                db: Session = Depends(get_db)):
    a, b = _range(frm, to)
    return summary(db, a, b)


def _rows(s: dict) -> list[list]:
    rows = [["section", "key", "value", "note"]]
    for k, v in s["website_engagement"]["by_event_type"].items():
        rows.append(["website_engagement.events", k, v, "engagement, not arrivals"])
    for d in s["website_engagement"]["top_destinations"]:
        rows.append(["website_engagement.top_destinations", d["slug"], d["views"], ""])
    for k, v in s["ai"]["answers_by_confidence"].items():
        rows.append(["ai.answers_by_confidence", k, v, ""])
    for k, v in s["operations"].items():
        rows.append(["operations", k, v, ""])
    for m in s["measured_tourism"]["items"]:
        rows.append(["measured_tourism", f"{m['metric']}:{m['destination_slug'] or 'region'}:{m['period_start']}",
                     m["value"], f"source: {m['source']}"])
    return rows


@router.get("/bureau/analytics/export")
def export(request: Request, format: Literal["csv", "xlsx", "pdf"] = "csv", frm: date | None = None, to: date | None = None,
           p: Principal = Depends(require("analytics.view", "reports.export")), db: Session = Depends(get_db)):
    a, b = _range(frm, to)
    s = summary(db, a, b)
    provenance = [f"Visit Tigray report — generated {s['generated_at']} by {p.user.email}",
                  f"Filters: from {a} to {b}", NOTICE]
    rows = _rows(s)
    audit.record(db, action="report.export", resource_type="analytics", resource_id=format, actor=p, request=request,
                 changes=s["filters"])
    db.commit()
    name = f"visit-tigray-report-{a}-{b}"
    if format == "csv":
        buf = io.StringIO()
        w = csv.writer(buf)
        for line in provenance:
            w.writerow([f"# {line}"])
        w.writerows(rows)
        return Response(buf.getvalue(), media_type="text/csv; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{name}.csv"'})
    if format == "xlsx":
        from openpyxl import Workbook
        wb = Workbook()
        ws = wb.active
        ws.title = "Report"
        for line in provenance:
            ws.append([line])
        ws.append([])
        for r in rows:
            ws.append(r)
        out = io.BytesIO()
        wb.save(out)
        return Response(out.getvalue(), media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        headers={"Content-Disposition": f'attachment; filename="{name}.xlsx"'})
    from fpdf import FPDF
    doc = FPDF()
    doc.add_page()
    try:
        doc.add_font("Body", "", "/usr/share/fonts/truetype/freefont/FreeSerif.ttf")
        doc.set_font("Body", size=10)
    except (FileNotFoundError, RuntimeError):  # pragma: no cover
        doc.set_font("Helvetica", size=10)
    for line in provenance:
        doc.multi_cell(doc.epw, 5, line, new_x="LMARGIN", new_y="NEXT")
    doc.ln(4)
    for r in rows:
        doc.multi_cell(doc.epw, 5, " | ".join(str(x) for x in r), new_x="LMARGIN", new_y="NEXT")
    return Response(bytes(doc.output()), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="{name}.pdf"'})


class MeasurementIn(BaseModel):
    period_start: date
    period_end: date
    destination_slug: str | None = Field(default=None, max_length=100)
    metric: Literal["visitors", "international_visitors", "domestic_visitors", "guided_groups"]
    value: int = Field(ge=0, le=100_000_000)
    source: str = Field(min_length=5, max_length=300)
    method_note: str = Field(default="", max_length=500)


@router.post("/bureau/analytics/measurements", status_code=201)
def record_measurement(body: MeasurementIn, request: Request, p: Principal = Depends(require("tourism_stats.record")),
                       db: Session = Depends(get_db)):
    if body.period_end < body.period_start:
        raise AppError(422, "invalid_range", "Period end precedes start.")
    m = TourismMeasurement(recorded_by=p.id, **body.model_dump())
    db.add(m)
    audit.record(db, action="analytics.measurement", resource_type="tourism_measurement", resource_id=body.metric,
                 actor=p, request=request, changes=body.model_dump(mode="json"))
    db.commit()
    return {"status": "recorded"}


class SendReportIn(BaseModel):
    channel: Literal["email", "telegram"]
    recipient: str = Field(min_length=3, max_length=320)
    frm: date | None = None
    to: date | None = None


@router.post("/bureau/analytics/send", status_code=202)
def send_report(body: SendReportIn, request: Request, p: Principal = Depends(require("reports.export")),
                db: Session = Depends(get_db)):
    """Aggregate-only report. Never includes personal data; Telegram limited to allow-listed chats."""
    a, b = _range(body.frm, body.to)
    s = summary(db, a, b)
    text = "\n".join(f"{r[0]} · {r[1]}: {r[2]}" for r in _rows(s)[1:40])
    notify(db, channel=body.channel, recipient=body.recipient, template="report", classification="aggregate",
           payload={"body": f"{NOTICE}\nPeriod {a}–{b}\n\n{text}"})
    audit.record(db, action="report.send", resource_type="analytics", resource_id=body.channel, actor=p, request=request,
                 changes={"recipient": body.recipient})
    db.commit()
    return {"status": "queued"}

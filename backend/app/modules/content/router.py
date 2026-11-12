"""Public discovery API and Bureau CMS API for destinations, categories, advisories and events."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field, HttpUrl
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.calendar import EthiopianDate, from_gregorian
from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.core.ethiopic import fold_for_search
from app.core.i18n import norm_locale, pick
from app.modules.audit import service as audit
from app.modules.content import service as svc
from app.modules.content.models import (
    Advisory,
    Category,
    Destination,
    DestinationRevision,
    DestinationTranslation,
    Event,
    PlaceAlias,
    RouteSegment,
)
from app.modules.identity.deps import optional_principal, require
from app.modules.identity.service import Principal

public_router = APIRouter(prefix="/api", tags=["discovery"])
router = APIRouter(prefix="/api/bureau", tags=["cms"])

Locale = Literal["en", "ti", "am"]
TriState = Literal["yes", "no", "unknown"]


# =============================================================== public

@public_router.get("/categories")
def categories(locale: str = "en", db: Session = Depends(get_db)):
    rows = db.execute(select(Category).where(Category.is_active.is_(True)).order_by(Category.sort_order, Category.slug)).scalars()
    return [svc.category_out(c, norm_locale(locale)) for c in rows]


@public_router.get("/destinations")
def list_destinations(locale: str = "en", category: str | None = None, interest: str | None = None,
                      q: str | None = Query(None, max_length=120), limit: int = Query(50, le=100),
                      offset: int = Query(0, ge=0), db: Session = Depends(get_db)):
    advisories = svc.active_advisories(db)
    items = []
    for d in svc.search_published(db, q, category, interest, limit, offset):
        loc = svc.localize_snapshot(d.published_snapshot or {}, locale)
        level, _ = svc.advisory_level_for(advisories, d.id)
        loc.update({"id": str(d.id), "advisory_level": level, "body": None})
        items.append(loc)
    return {"items": items, "limit": limit, "offset": offset}


@public_router.get("/destinations/{slug}")
def get_destination(slug: str, locale: str = "en", db: Session = Depends(get_db),
                    p: Principal | None = Depends(optional_principal)):
    d = db.execute(select(Destination).where(Destination.slug == slug)).scalar_one_or_none()
    if d is None or not d.published_snapshot:  # live snapshot stays visible while a draft is pending
        raise not_found("Destination")
    out = svc.localize_snapshot(d.published_snapshot, locale)
    level, hits = svc.advisory_level_for(svc.active_advisories(db), d.id)
    out.update({"id": str(d.id), "advisory_level": level,
                "advisories": [svc.advisory_out(a, norm_locale(locale)) for a in hits],
                "events": [event_out(e, norm_locale(locale)) for e in db.execute(
                    select(Event).where(Event.destination_id == d.id, Event.status == "published")).scalars()]})
    if p is not None and p.has("heritage.read_restricted"):
        ll = svc.latlng(d.location)
        out["precise_coordinates"] = {"lat": ll[0], "lng": ll[1]} if ll else None
    from app.modules.analytics.router import track
    track(db, "destination_view", destination_slug=slug, locale=norm_locale(locale))
    db.commit()
    return out


@public_router.get("/advisories")
def list_advisories(locale: str = "en", db: Session = Depends(get_db)):
    return [svc.advisory_out(a, norm_locale(locale)) for a in svc.active_advisories(db)]


def event_out(e: Event, locale: str) -> dict:
    eth = None
    if e.starts_on:
        eth = from_gregorian(e.starts_on).format(locale)
    elif e.ethiopian_month and e.ethiopian_day:
        from app.core.calendar import MONTHS
        eth = f"{MONTHS.get(locale, MONTHS['en'])[e.ethiopian_month - 1]} {e.ethiopian_day}"
    return {"id": str(e.id), "slug": e.slug, "title": pick(e.title_i18n, locale)[0],
            "description": pick(e.description_i18n, locale)[0], "kind": e.kind,
            "starts_on": e.starts_on.isoformat() if e.starts_on else None,
            "ends_on": e.ends_on.isoformat() if e.ends_on else None, "ethiopian_date": eth,
            "date_note": pick(e.date_note_i18n, locale)[0],
            "verified_at": e.verified_at.isoformat() if e.verified_at else None, "sources": e.sources,
            "is_synthetic": e.is_synthetic}


@public_router.get("/events")
def list_events(locale: str = "en", db: Session = Depends(get_db)):
    rows = db.execute(select(Event).where(Event.status == "published").order_by(Event.starts_on.nulls_last(),
                                                                               Event.ethiopian_month)).scalars()
    return [event_out(e, norm_locale(locale)) for e in rows]


@public_router.get("/calendar/convert")
def convert(gregorian: date | None = None, eth_year: int | None = None, eth_month: int | None = None,
            eth_day: int | None = None, locale: str = "en"):
    try:
        if gregorian:
            e = from_gregorian(gregorian)
        elif eth_year and eth_month and eth_day:
            e = EthiopianDate(eth_year, eth_month, eth_day)
        else:
            raise AppError(422, "missing_date", "Provide gregorian=YYYY-MM-DD or eth_year/eth_month/eth_day.")
    except ValueError as exc:
        raise AppError(422, "invalid_date", str(exc)) from exc
    return {"gregorian": e.to_gregorian().isoformat(), "ethiopian": {"year": e.year, "month": e.month, "day": e.day},
            "formatted": e.format(norm_locale(locale))}


# =============================================================== bureau CMS

class TranslationIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    eyebrow: str = Field(default="", max_length=160)
    summary: str = Field(default="", max_length=1200)
    body: str = Field(default="", max_length=30000)
    etiquette: str = Field(default="", max_length=5000)
    accessibility_notes: str = Field(default="", max_length=5000)
    machine_generated: bool = False


class SourceIn(BaseModel):
    title: str = Field(max_length=300)
    author: str | None = Field(default=None, max_length=200)
    publisher: str | None = Field(default=None, max_length=200)
    year: str | None = Field(default=None, max_length=20)
    url: HttpUrl | None = None
    note: str | None = Field(default=None, max_length=500)
    knowledge_document_id: uuid.UUID | None = None


class AccessibilityIn(BaseModel):
    step_free: TriState = "unknown"
    terrain: str = Field(default="unknown", max_length=200)
    facilities: str = Field(default="unknown", max_length=500)
    notes: str = Field(default="", max_length=1000)


class DestinationIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,98}$")
    category_slug: str | None = None
    interests: list[str] = Field(default_factory=list, max_length=12)
    area: str = Field(default="", max_length=120)
    en: TranslationIn


class DestinationPatch(BaseModel):
    category_slug: str | None = None
    interests: list[str] | None = Field(default=None, max_length=12)
    area: str | None = Field(default=None, max_length=120)
    visit_duration_minutes: int | None = Field(default=None, ge=5, le=24 * 60)
    accessibility: AccessibilityIn | None = None
    permit_required: TriState | None = None
    permit_authority: str | None = Field(default=None, max_length=200)
    contact: dict[str, str] | None = None
    timeline: list[dict] | None = Field(default=None, max_length=60)
    sources: list[SourceIn] | None = Field(default=None, max_length=60)
    heritage_designations: list[dict] | None = None
    verified: bool | None = None
    review_due: date | None = None
    clear_duration: bool = False


class GeoPatch(BaseModel):
    lat: float | None = Field(default=None, ge=-90, le=90)
    lng: float | None = Field(default=None, ge=-180, le=180)
    sensitivity: Literal["public", "coarse", "hidden"]


def _get(db: Session, ident: uuid.UUID) -> Destination:
    d = db.get(Destination, ident)
    if d is None:
        raise not_found("Destination")
    return d


def _category(db: Session, slug: str | None) -> uuid.UUID | None:
    if not slug:
        return None
    c = db.execute(select(Category).where(Category.slug == slug)).scalar_one_or_none()
    if c is None:
        raise AppError(422, "unknown_category", f"Category {slug} does not exist")
    return c.id


def staff_view(d: Destination) -> dict:
    ll = svc.latlng(d.location)
    return {"id": str(d.id), "slug": d.slug, "status": d.status, "category": d.category.slug if d.category else None,
            "publish_at": d.publish_at.isoformat() if d.publish_at else None,
            "published_at": d.published_at.isoformat() if d.published_at else None,
            "verified_at": d.verified_at.isoformat() if d.verified_at else None,
            "review_due": d.review_due.isoformat() if d.review_due else None,
            "is_synthetic": d.is_synthetic, "updated_at": d.updated_at.isoformat(),
            "working": {**svc.working_copy(d), "lat": ll[0] if ll else None, "lng": ll[1] if ll else None},
            "is_live": d.published_snapshot is not None,
            "has_unpublished_changes": d.status in ("draft", "in_review", "scheduled")}


@router.get("/destinations")
def staff_list(status: str | None = None, _=Depends(require("destinations.read_draft")), db: Session = Depends(get_db)):
    stmt = select(Destination).order_by(Destination.updated_at.desc())
    if status:
        stmt = stmt.where(Destination.status == status)
    return [staff_view(d) for d in db.execute(stmt).scalars()]


@router.get("/destinations/{ident}")
def staff_get(ident: uuid.UUID, _=Depends(require("destinations.read_draft")), db: Session = Depends(get_db)):
    return staff_view(_get(db, ident))


@router.post("/destinations", status_code=201)
def create_destination(body: DestinationIn, request: Request, p: Principal = Depends(require("destinations.edit")),
                       db: Session = Depends(get_db)):
    if db.execute(select(Destination.id).where(Destination.slug == body.slug)).first():
        raise AppError(409, "slug_taken", "A destination with this slug exists.")
    d = Destination(slug=body.slug, category_id=_category(db, body.category_slug), interests=body.interests,
                    area=body.area, created_by=p.id, updated_by=p.id, accessibility={"step_free": "unknown"})
    db.add(d)
    db.flush()
    d.translations.append(DestinationTranslation(destination_id=d.id, locale="en", translated_by=p.id,
                                                 status="machine" if body.en.machine_generated else "draft",
                                                 **body.en.model_dump(exclude={"machine_generated"})))
    db.add(PlaceAlias(destination_id=d.id, name=body.en.name, normalized=fold_for_search(body.en.name), locale="en",
                      kind="official"))
    audit.record(db, action="destination.create", resource_type="destination", resource_id=d.id, actor=p, request=request)
    db.commit()
    return staff_view(d)


@router.patch("/destinations/{ident}")
def update_destination(ident: uuid.UUID, body: DestinationPatch, request: Request,
                       p: Principal = Depends(require("destinations.edit")), db: Session = Depends(get_db)):
    d = _get(db, ident)
    if d.status == "archived":
        raise AppError(409, "archived", "Restore the destination before editing.")
    data = body.model_dump(exclude_unset=True)
    changes: dict[str, Any] = {}
    if "category_slug" in data:
        d.category_id = _category(db, body.category_slug)
        changes["category"] = body.category_slug
    for k in ("interests", "area", "permit_required", "permit_authority", "contact", "timeline", "heritage_designations",
              "review_due"):
        if k in data:
            setattr(d, k, data[k])
            changes[k] = data[k]
    if body.visit_duration_minutes is not None or body.clear_duration:
        d.visit_duration_minutes = None if body.clear_duration else body.visit_duration_minutes
        changes["visit_duration_minutes"] = d.visit_duration_minutes
    if body.accessibility is not None:
        d.accessibility = body.accessibility.model_dump()
        changes["accessibility"] = d.accessibility
    if body.sources is not None:
        d.sources = [s.model_dump(mode="json") for s in body.sources]
        changes["sources"] = len(d.sources)
    if body.verified:
        d.verified_at, d.verified_by = utcnow(), p.id
        changes["verified"] = True
    d.updated_by = p.id
    d.updated_at = utcnow()
    if d.status == "published":
        d.status = "draft"  # published snapshot stays live until re-published
    audit.record(db, action="destination.update", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={k: str(v)[:200] for k, v in changes.items()})
    db.commit()
    return staff_view(d)


@router.put("/destinations/{ident}/geo")
def update_geo(ident: uuid.UUID, body: GeoPatch, request: Request, p: Principal = Depends(require("geo.manage")),
               db: Session = Depends(get_db)):
    d = _get(db, ident)
    svc.set_location(d, body.lat, body.lng)
    d.location_sensitivity = body.sensitivity
    d.updated_at, d.updated_by = utcnow(), p.id
    if d.status == "published":
        d.status = "draft"
    audit.record(db, action="destination.geo", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={"sensitivity": body.sensitivity})  # coordinates deliberately not logged
    db.commit()
    return staff_view(d)


@router.put("/destinations/{ident}/translations/{locale}")
def put_translation(ident: uuid.UUID, locale: Locale, body: TranslationIn, request: Request,
                    p: Principal = Depends(require("translations.edit", "destinations.edit", any_of=True)),
                    db: Session = Depends(get_db)):
    d = _get(db, ident)
    t = next((x for x in d.translations if x.locale == locale), None)
    if t is None:
        t = DestinationTranslation(destination_id=d.id, locale=locale, name=body.name)
        d.translations.append(t)
    for k, v in body.model_dump(exclude={"machine_generated"}).items():
        setattr(t, k, v)
    t.status = "machine" if body.machine_generated else "draft"
    t.translated_by, t.reviewed_by, t.reviewed_at = p.id, None, None
    alias_norm = fold_for_search(body.name)
    if not db.execute(select(PlaceAlias).where(PlaceAlias.destination_id == d.id, PlaceAlias.normalized == alias_norm)).first():
        db.add(PlaceAlias(destination_id=d.id, name=body.name, normalized=alias_norm, locale=locale, kind="official"))
    d.updated_at = utcnow()
    if d.status == "published":
        d.status = "draft"
    audit.record(db, action="translation.update", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={"locale": locale, "status": t.status})
    db.commit()
    return staff_view(d)


@router.post("/destinations/{ident}/translations/{locale}/approve")
def approve_translation(ident: uuid.UUID, locale: Locale, request: Request,
                        p: Principal = Depends(require("translations.approve")), db: Session = Depends(get_db)):
    d = _get(db, ident)
    t = next((x for x in d.translations if x.locale == locale), None)
    if t is None:
        raise not_found("Translation")
    if t.translated_by == p.id:
        raise AppError(403, "four_eyes", "A different reviewer must approve your own translation.")
    t.status, t.reviewed_by, t.reviewed_at = "reviewed", p.id, utcnow()
    d.updated_at = utcnow()
    if d.status == "published":
        d.status = "draft"
    audit.record(db, action="translation.approve", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={"locale": locale})
    db.commit()
    return staff_view(d)


class AliasIn(BaseModel):
    name: str = Field(min_length=1, max_length=160)
    locale: Locale | None = None
    kind: Literal["official", "variant", "transliteration", "historic"] = "variant"


@router.post("/destinations/{ident}/aliases", status_code=201)
def add_alias(ident: uuid.UUID, body: AliasIn, request: Request, p: Principal = Depends(require("destinations.edit")),
              db: Session = Depends(get_db)):
    d = _get(db, ident)
    norm = fold_for_search(body.name)
    if not db.execute(select(PlaceAlias).where(PlaceAlias.destination_id == d.id, PlaceAlias.normalized == norm)).first():
        db.add(PlaceAlias(destination_id=d.id, name=body.name, normalized=norm, locale=body.locale, kind=body.kind))
    d.updated_at = utcnow()
    audit.record(db, action="destination.alias", resource_type="destination", resource_id=d.id, actor=p, request=request,
                 changes={"alias": body.name})
    db.commit()
    return {"aliases": [a.name for a in db.execute(select(PlaceAlias).where(PlaceAlias.destination_id == d.id)).scalars()]}


@router.post("/destinations/{ident}/submit")
def submit_for_review(ident: uuid.UUID, request: Request, p: Principal = Depends(require("destinations.edit")),
                      db: Session = Depends(get_db)):
    d = _get(db, ident)
    d.status = "in_review"
    audit.record(db, action="destination.submit", resource_type="destination", resource_id=d.id, actor=p, request=request)
    db.commit()
    return staff_view(d)


class PublishIn(BaseModel):
    note: str = Field(default="", max_length=500)
    publish_at: datetime | None = None


@router.post("/destinations/{ident}/publish")
def publish_destination(ident: uuid.UUID, body: PublishIn, request: Request,
                        p: Principal = Depends(require("destinations.publish")), db: Session = Depends(get_db)):
    d = _get(db, ident)
    if d.status == "archived":
        raise AppError(409, "archived", "Archived destinations cannot be published.")
    if body.publish_at and body.publish_at > utcnow():
        d.status, d.publish_at = "scheduled", body.publish_at
        audit.record(db, action="destination.schedule", resource_type="destination", resource_id=d.id, actor=p,
                     request=request, changes={"publish_at": body.publish_at.isoformat()})
        db.commit()
        return staff_view(d)
    rev = svc.publish(db, d, p.id, body.note)
    audit.record(db, action="destination.publish", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={"revision": rev.number})
    db.commit()
    return staff_view(d)


@router.post("/destinations/{ident}/archive")
def archive_destination(ident: uuid.UUID, request: Request, p: Principal = Depends(require("destinations.publish")),
                        db: Session = Depends(get_db)):
    """Emergency takedown: removes the destination from public view immediately."""
    d = _get(db, ident)
    d.status, d.published_snapshot, d.published_location = "archived", None, None
    audit.record(db, action="destination.archive", resource_type="destination", resource_id=d.id, actor=p, request=request)
    db.commit()
    return staff_view(d)


@router.get("/destinations/{ident}/revisions")
def revisions(ident: uuid.UUID, _=Depends(require("destinations.read_draft")), db: Session = Depends(get_db)):
    rows = db.execute(select(DestinationRevision).where(DestinationRevision.destination_id == ident)
                      .order_by(DestinationRevision.number.desc())).scalars()
    return [{"number": r.number, "note": r.note, "created_at": r.created_at.isoformat(),
             "created_by": str(r.created_by) if r.created_by else None} for r in rows]


@router.get("/destinations/{ident}/revisions/diff")
def revision_diff(ident: uuid.UUID, a: int, b: int, _=Depends(require("destinations.read_draft")),
                  db: Session = Depends(get_db)):
    revs = {r.number: r for r in db.execute(select(DestinationRevision).where(
        DestinationRevision.destination_id == ident, DestinationRevision.number.in_([a, b]))).scalars()}
    if a not in revs or b not in revs:
        raise not_found("Revision")
    return {"diff": svc.diff_revisions(revs[a].snapshot, revs[b].snapshot)}


@router.post("/destinations/{ident}/rollback/{number}")
def rollback(ident: uuid.UUID, number: int, request: Request, p: Principal = Depends(require("destinations.publish")),
             db: Session = Depends(get_db)):
    d = _get(db, ident)
    rev = svc.rollback(db, d, number, p.id)
    audit.record(db, action="destination.rollback", resource_type="destination", resource_id=d.id, actor=p,
                 request=request, changes={"to": number, "new_revision": rev.number})
    db.commit()
    return staff_view(d)


@router.get("/translations/missing")
def translations_missing(_=Depends(require("destinations.read_draft")), db: Session = Depends(get_db)):
    return svc.missing_translations(db)


@router.get("/content/freshness")
def content_freshness(_=Depends(require("destinations.read_draft")), db: Session = Depends(get_db)):
    """Records that are unverified, stale (>365 days) or past their review date."""
    today = date.today()
    out = []
    for d in db.execute(select(Destination).where(Destination.status != "archived")).scalars():
        reasons = []
        if d.verified_at is None:
            reasons.append("never_verified")
        elif (utcnow() - d.verified_at).days > svc.STALE_AFTER_DAYS:
            reasons.append("verification_stale")
        if d.review_due and d.review_due < today:
            reasons.append("review_overdue")
        if not d.sources:
            reasons.append("no_sources")
        if d.visit_duration_minutes is None:
            reasons.append("duration_unknown")
        if (d.accessibility or {}).get("step_free", "unknown") == "unknown":
            reasons.append("accessibility_unknown")
        if reasons:
            out.append({"id": str(d.id), "slug": d.slug, "reasons": reasons})
    return out


# ---- categories

class CategoryIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,78}$")
    name_i18n: dict[Locale, str]
    description_i18n: dict[Locale, str] = Field(default_factory=dict)
    icon: str | None = Field(default=None, max_length=40)
    sort_order: int = 100
    is_active: bool = True


@router.post("/categories", status_code=201)
def create_category(body: CategoryIn, request: Request, p: Principal = Depends(require("categories.manage")),
                    db: Session = Depends(get_db)):
    if "en" not in body.name_i18n:
        raise AppError(422, "missing_english", "An English category name is required.")
    if db.execute(select(Category.id).where(Category.slug == body.slug)).first():
        raise AppError(409, "slug_taken", "Category exists")
    c = Category(**body.model_dump())
    db.add(c)
    db.flush()
    audit.record(db, action="category.create", resource_type="category", resource_id=c.slug, actor=p, request=request)
    db.commit()
    return svc.category_out(c, "en")


@router.put("/categories/{slug}")
def update_category(slug: str, body: CategoryIn, request: Request, p: Principal = Depends(require("categories.manage")),
                    db: Session = Depends(get_db)):
    c = db.execute(select(Category).where(Category.slug == slug)).scalar_one_or_none()
    if c is None:
        raise not_found("Category")
    for k, v in body.model_dump().items():
        setattr(c, k, v)
    audit.record(db, action="category.update", resource_type="category", resource_id=slug, actor=p, request=request)
    db.commit()
    return svc.category_out(c, "en")


# ---- advisories

class AdvisoryIn(BaseModel):
    title_i18n: dict[Locale, str]
    body_i18n: dict[Locale, str]
    level: Literal["info", "caution", "avoid_nonessential", "travel_not_advised"]
    region_wide: bool = False
    destination_ids: list[uuid.UUID] = Field(default_factory=list)
    issuing_authority: str = Field(min_length=2, max_length=200)
    source_url: HttpUrl | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None


@router.get("/advisories")
def staff_advisories(_=Depends(require("advisories.manage")), db: Session = Depends(get_db)):
    rows = db.execute(select(Advisory).order_by(Advisory.created_at.desc())).scalars()
    return [{**svc.advisory_out(a, "en"), "status": a.status} for a in rows]


@router.post("/advisories", status_code=201)
def create_advisory(body: AdvisoryIn, request: Request, p: Principal = Depends(require("advisories.manage")),
                    db: Session = Depends(get_db)):
    if not body.region_wide and not body.destination_ids:
        raise AppError(422, "no_scope", "Choose region-wide or at least one destination.")
    data = body.model_dump(mode="json")
    data["destination_ids"] = body.destination_ids
    data["effective_from"] = body.effective_from or utcnow()
    data["effective_until"] = body.effective_until
    a = Advisory(**data)
    db.add(a)
    db.flush()
    audit.record(db, action="advisory.create", resource_type="advisory", resource_id=a.id, actor=p, request=request,
                 changes={"level": a.level})
    db.commit()
    return {**svc.advisory_out(a, "en"), "status": a.status}


@router.post("/advisories/{ident}/{action}")
def advisory_action(ident: uuid.UUID, action: Literal["publish", "withdraw"], request: Request,
                    p: Principal = Depends(require("advisories.manage")), db: Session = Depends(get_db)):
    a = db.get(Advisory, ident)
    if a is None:
        raise not_found("Advisory")
    a.status = "published" if action == "publish" else "withdrawn"
    a.published_by = p.id
    if action == "withdraw":
        a.effective_until = utcnow()
    audit.record(db, action=f"advisory.{action}", resource_type="advisory", resource_id=a.id, actor=p, request=request,
                 changes={"level": a.level})
    db.commit()
    return {**svc.advisory_out(a, "en"), "status": a.status}


# ---- events

class EventIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,98}$")
    title_i18n: dict[Locale, str]
    description_i18n: dict[Locale, str] = Field(default_factory=dict)
    kind: str = Field(default="festival", max_length=30)
    starts_on: date | None = None
    ends_on: date | None = None
    ethiopian_month: int | None = Field(default=None, ge=1, le=13)
    ethiopian_day: int | None = Field(default=None, ge=1, le=30)
    date_note_i18n: dict[Locale, str] = Field(default_factory=dict)
    destination_id: uuid.UUID | None = None
    sources: list[SourceIn] = Field(default_factory=list)
    publish: bool = False
    verified: bool = False


@router.post("/events", status_code=201)
def create_event(body: EventIn, request: Request, p: Principal = Depends(require("events.manage")),
                 db: Session = Depends(get_db)):
    if body.ends_on and body.starts_on and body.ends_on < body.starts_on:
        raise AppError(422, "invalid_dates", "End date precedes start date.")
    e = Event(**body.model_dump(exclude={"publish", "verified", "sources"}),
              sources=[s.model_dump(mode="json") for s in body.sources],
              status="published" if body.publish else "draft", verified_at=utcnow() if body.verified else None)
    db.add(e)
    db.flush()
    audit.record(db, action="event.create", resource_type="event", resource_id=e.slug, actor=p, request=request)
    db.commit()
    return event_out(e, "en")


# ---- verified route segments (planner input)

class SegmentIn(BaseModel):
    from_id: uuid.UUID
    to_id: uuid.UUID
    mode: Literal["road", "walk", "air"] = "road"
    distance_km: float | None = Field(default=None, gt=0, le=2000)
    duration_minutes: int | None = Field(default=None, gt=0, le=48 * 60)
    condition_note: str = Field(default="", max_length=500)
    source: str = Field(min_length=3, max_length=300)
    valid_until: datetime | None = None
    bidirectional: bool = True


@router.post("/route-segments", status_code=201)
def upsert_segment(body: SegmentIn, request: Request, p: Principal = Depends(require("geo.manage")),
                   db: Session = Depends(get_db)):
    pairs = [(body.from_id, body.to_id)] + ([(body.to_id, body.from_id)] if body.bidirectional else [])
    for a, b in pairs:
        seg = db.execute(select(RouteSegment).where(RouteSegment.from_id == a, RouteSegment.to_id == b,
                                                    RouteSegment.mode == body.mode)).scalar_one_or_none()
        if seg is None:
            seg = RouteSegment(from_id=a, to_id=b, mode=body.mode, source=body.source, verified_at=utcnow())
            db.add(seg)
        seg.distance_km, seg.duration_minutes = body.distance_km, body.duration_minutes
        seg.condition_note, seg.source, seg.verified_at, seg.valid_until = (body.condition_note, body.source,
                                                                            utcnow(), body.valid_until)
    audit.record(db, action="route_segment.upsert", resource_type="route_segment", resource_id=f"{body.from_id}->{body.to_id}",
                 actor=p, request=request, changes={"source": body.source})
    db.commit()
    return {"status": "ok"}

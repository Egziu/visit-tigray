from __future__ import annotations

import difflib
import json
from datetime import timedelta
from typing import Any

from geoalchemy2.shape import from_shape, to_shape
from shapely.geometry import Point
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.errors import AppError
from app.core.ethiopic import fold_for_search, transliterate
from app.core.i18n import norm_locale
from app.modules.content.models import Advisory, Category, Destination, DestinationRevision, DestinationTranslation, PlaceAlias

COARSE_DECIMALS = 1  # ~11 km at Tigray's latitude
ADVISORY_RANK = {"info": 0, "caution": 1, "avoid_nonessential": 2, "travel_not_advised": 3}
STALE_AFTER_DAYS = 365


# ---------------------------------------------------------------- geometry

def set_location(d: Destination, lat: float | None, lng: float | None) -> None:
    if lat is None or lng is None:
        d.location = None
        return
    if not (-90 <= lat <= 90 and -180 <= lng <= 180):
        raise AppError(422, "invalid_coordinates", "Latitude/longitude out of range.")
    d.location = from_shape(Point(lng, lat), srid=4326)


def latlng(geom) -> tuple[float, float] | None:
    if geom is None:
        return None
    p = to_shape(geom)
    return (p.y, p.x)


def public_coordinates(d: Destination) -> dict | None:
    ll = latlng(d.location)
    if ll is None or d.location_sensitivity == "hidden":
        return None
    if d.location_sensitivity == "coarse":
        return {"lat": round(ll[0], COARSE_DECIMALS), "lng": round(ll[1], COARSE_DECIMALS), "precision": "approximate"}
    return {"lat": round(ll[0], 5), "lng": round(ll[1], 5), "precision": "exact"}


# ---------------------------------------------------------------- snapshots

def translation_dict(t: DestinationTranslation) -> dict:
    return {"name": t.name, "eyebrow": t.eyebrow, "summary": t.summary, "body": t.body, "etiquette": t.etiquette,
            "accessibility_notes": t.accessibility_notes, "status": t.status,
            "reviewed_at": t.reviewed_at.isoformat() if t.reviewed_at else None}


def build_snapshot(db: Session, d: Destination) -> dict:
    cat = d.category
    return {
        "slug": d.slug,
        "category": {"slug": cat.slug, "name_i18n": cat.name_i18n} if cat else None,
        "interests": list(d.interests or []),
        "area": d.area,
        "coordinates": public_coordinates(d),
        "location_sensitivity": d.location_sensitivity,
        "visit_duration_minutes": d.visit_duration_minutes,
        "accessibility": d.accessibility or {},
        "permit_required": d.permit_required,
        "permit_authority": d.permit_authority,
        "contact": d.contact or {},
        "timeline": d.timeline or [],
        "sources": d.sources or [],
        "heritage_designations": d.heritage_designations or [],
        "verified_at": d.verified_at.isoformat() if d.verified_at else None,
        "review_due": d.review_due.isoformat() if d.review_due else None,
        "is_synthetic": d.is_synthetic,
        "translations": {t.locale: translation_dict(t) for t in d.translations},
        "media": media_for_snapshot(db, d),
    }


def media_for_snapshot(db: Session, d: Destination) -> list[dict]:
    try:
        from app.modules.media.service import destination_media_public
    except ImportError:  # pragma: no cover
        return []
    return destination_media_public(db, d.id)


def refresh_search_text(db: Session, d: Destination) -> None:
    parts: list[str] = [d.slug, d.area]
    for t in d.translations:
        parts += [t.name, t.eyebrow, t.summary]
    aliases = db.execute(select(PlaceAlias.name).where(PlaceAlias.destination_id == d.id)).scalars().all()
    parts += aliases
    text = " ".join(p for p in parts if p)
    d.search_text = fold_for_search(text + " " + transliterate(text))


def next_revision_number(db: Session, d: Destination) -> int:
    n = db.execute(select(func.max(DestinationRevision.number)).where(DestinationRevision.destination_id == d.id)).scalar()
    return (n or 0) + 1


def publish(db: Session, d: Destination, actor_id, note: str = "") -> DestinationRevision:
    en = next((t for t in d.translations if t.locale == "en"), None)
    if en is None or not en.name or not en.summary:
        raise AppError(422, "incomplete_content", "An English name and summary are required before publishing.")
    if d.location is not None and d.location_sensitivity not in ("public", "coarse", "hidden"):
        raise AppError(422, "invalid_sensitivity", "Unknown location sensitivity.")
    refresh_search_text(db, d)
    snap = build_snapshot(db, d)
    d.published_snapshot = snap
    d.published_at = utcnow()
    d.status = "published"
    d.publish_at = None
    coords = snap["coordinates"]
    d.published_location = from_shape(Point(coords["lng"], coords["lat"]), srid=4326) if coords else None
    rev = DestinationRevision(destination_id=d.id, number=next_revision_number(db, d), snapshot={
        **snap, "_working": working_copy(d)}, note=note, created_by=actor_id)
    db.add(rev)
    db.flush()
    return rev


def working_copy(d: Destination) -> dict:
    ll = latlng(d.location)
    return {"category_id": str(d.category_id) if d.category_id else None, "interests": list(d.interests or []),
            "area": d.area, "lat": ll[0] if ll else None, "lng": ll[1] if ll else None,
            "location_sensitivity": d.location_sensitivity, "visit_duration_minutes": d.visit_duration_minutes,
            "accessibility": d.accessibility, "permit_required": d.permit_required,
            "permit_authority": d.permit_authority, "contact": d.contact, "timeline": d.timeline,
            "sources": d.sources, "heritage_designations": d.heritage_designations,
            "translations": {t.locale: translation_dict(t) for t in d.translations}}


def rollback(db: Session, d: Destination, number: int, actor_id) -> DestinationRevision:
    rev = db.execute(select(DestinationRevision).where(DestinationRevision.destination_id == d.id,
                                                       DestinationRevision.number == number)).scalar_one_or_none()
    if rev is None:
        raise AppError(404, "not_found", "Revision not found")
    w = rev.snapshot.get("_working", {})
    import uuid as _uuid
    d.category_id = _uuid.UUID(w["category_id"]) if w.get("category_id") else None
    for k in ("interests", "area", "location_sensitivity", "visit_duration_minutes", "accessibility", "permit_required",
              "permit_authority", "contact", "timeline", "sources", "heritage_designations"):
        if k in w:
            setattr(d, k, w[k])
    set_location(d, w.get("lat"), w.get("lng"))
    existing = {t.locale: t for t in d.translations}
    for loc, tv in (w.get("translations") or {}).items():
        t = existing.get(loc) or DestinationTranslation(destination_id=d.id, locale=loc, name=tv["name"])
        for k in ("name", "eyebrow", "summary", "body", "etiquette", "accessibility_notes", "status"):
            setattr(t, k, tv.get(k, ""))
        if loc not in existing:
            d.translations.append(t)
    for loc, t in existing.items():
        if loc not in (w.get("translations") or {}):
            d.translations.remove(t)
    db.flush()
    db.refresh(d)
    return publish(db, d, actor_id, note=f"Rollback to revision {number}")


def diff_revisions(a: dict, b: dict) -> list[str]:
    aj = json.dumps({k: v for k, v in a.items() if k != "_working"}, indent=1, sort_keys=True, ensure_ascii=False).splitlines()
    bj = json.dumps({k: v for k, v in b.items() if k != "_working"}, indent=1, sort_keys=True, ensure_ascii=False).splitlines()
    return list(difflib.unified_diff(aj, bj, "a", "b", lineterm="", n=1))


def publish_due(db: Session) -> int:
    due = db.execute(select(Destination).where(Destination.status == "scheduled", Destination.publish_at <= utcnow())
                     ).scalars().all()
    for d in due:
        publish(db, d, None, note="Scheduled publication")
    return len(due)


# ---------------------------------------------------------------- public views

def localize_snapshot(snap: dict, locale: str) -> dict:
    locale = norm_locale(locale)
    tr = snap.get("translations", {})
    used = locale if locale in tr else ("en" if "en" in tr else next(iter(tr), None))
    t = tr.get(used, {}) if used else {}
    out = {k: v for k, v in snap.items() if k != "translations"}
    out.update({"name": t.get("name", ""), "eyebrow": t.get("eyebrow", ""), "summary": t.get("summary", ""),
                "body": t.get("body", ""), "etiquette": t.get("etiquette", ""),
                "accessibility_notes": t.get("accessibility_notes", ""),
                "locale": used, "requested_locale": locale,
                "translation_status": t.get("status"),
                "available_locales": sorted(tr.keys())})
    if out.get("category"):
        cat = out["category"]
        out["category"] = {"slug": cat["slug"], "name": (cat.get("name_i18n") or {}).get(locale)
                           or (cat.get("name_i18n") or {}).get("en", cat["slug"])}
    if out.get("verified_at"):
        from datetime import datetime
        age = utcnow() - datetime.fromisoformat(out["verified_at"])
        out["is_stale"] = age > timedelta(days=STALE_AFTER_DAYS)
    else:
        out["is_stale"] = True
    return out


def search_published(db: Session, q: str | None, category: str | None, interest: str | None,
                     limit: int = 50, offset: int = 0) -> list[Destination]:
    stmt = select(Destination).where(Destination.published_snapshot.is_not(None))
    if category:
        stmt = stmt.where(Destination.published_snapshot["category"]["slug"].astext == category)
    if interest:
        stmt = stmt.where(Destination.published_snapshot["interests"].contains([interest]))
    if q:
        fq = fold_for_search(q)
        fq_t = fold_for_search(transliterate(q))
        stmt = stmt.where(or_(Destination.search_text.ilike(f"%{fq}%"), Destination.search_text.ilike(f"%{fq_t}%"),
                              func.similarity(Destination.search_text, fq) > 0.08))
        stmt = stmt.order_by(func.similarity(Destination.search_text, fq).desc())
    else:
        stmt = stmt.order_by(Destination.slug)
    return list(db.execute(stmt.limit(limit).offset(offset)).scalars().all())


def active_advisories(db: Session) -> list[Advisory]:
    now = utcnow()
    return list(db.execute(select(Advisory).where(Advisory.status == "published", Advisory.effective_from <= now,
                                                  or_(Advisory.effective_until.is_(None), Advisory.effective_until > now))
                           .order_by(Advisory.effective_from.desc())).scalars().all())


def advisory_level_for(advisories: list[Advisory], destination_id) -> tuple[str | None, list[Advisory]]:
    hits = [a for a in advisories if a.region_wide or destination_id in (a.destination_ids or [])]
    if not hits:
        return None, []
    return max(hits, key=lambda a: ADVISORY_RANK.get(a.level, 0)).level, hits


def advisory_out(a: Advisory, locale: str) -> dict:
    from app.core.i18n import pick
    return {"id": str(a.id), "level": a.level, "title": pick(a.title_i18n, locale)[0], "body": pick(a.body_i18n, locale)[0],
            "region_wide": a.region_wide, "destination_ids": [str(x) for x in a.destination_ids or []],
            "issuing_authority": a.issuing_authority, "source_url": a.source_url,
            "effective_from": a.effective_from.isoformat(),
            "effective_until": a.effective_until.isoformat() if a.effective_until else None,
            "is_synthetic": a.is_synthetic}


def category_out(c: Category, locale: str) -> dict:
    from app.core.i18n import pick
    return {"id": str(c.id), "slug": c.slug, "name": pick(c.name_i18n, locale)[0],
            "description": pick(c.description_i18n, locale)[0], "icon": c.icon, "sort_order": c.sort_order,
            "is_active": c.is_active, "name_i18n": c.name_i18n}


def missing_translations(db: Session) -> list[dict[str, Any]]:
    out = []
    for d in db.execute(select(Destination).where(Destination.status != "archived")).scalars():
        have = {t.locale: t.status for t in d.translations}
        missing = [loc for loc in ("en", "ti", "am") if loc not in have]
        unreviewed = [loc for loc, st in have.items() if st in ("machine", "draft")]
        if missing or unreviewed:
            out.append({"destination_id": str(d.id), "slug": d.slug, "missing": missing, "unreviewed": unreviewed})
    return out

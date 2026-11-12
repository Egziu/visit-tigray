"""Deterministic itinerary engine. No language model is involved in feasibility.

Rules (docs/SYSTEM_ARCHITECTURE.md §Planner):
* Only published destinations, never invented stops.
* Official advisories: a region-wide ``travel_not_advised`` advisory switches the whole plan to
  *virtual* mode (no routing). Destination-level ``travel_not_advised`` / ``avoid_nonessential``
  exclude that stop from operational routing; it is offered as a virtual alternative.
* Accessibility: if step-free access is required, only stops with ``step_free == "yes"`` qualify.
  ``unknown`` is excluded and the reason is stated, never assumed.
* Distances: a verified ``RouteSegment`` gives distance/duration with its source; otherwise only a
  straight-line distance is reported, labelled as such, and travel time is unknown.
* Time budgets per pace use known visit durations and verified travel times; unknown durations are
  listed as unknowns rather than guessed.
* Costs and weather are not estimated: no verified data source exists yet.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.i18n import norm_locale
from app.modules.content.models import Destination, RouteSegment
from app.modules.content.service import active_advisories, advisory_level_for, latlng, localize_snapshot

PACE = {"relaxed": (2, 300), "balanced": (3, 420), "full": (4, 540)}  # (max stops/day, minutes/day)
BLOCKING = {"travel_not_advised", "avoid_nonessential"}

NOTICE = {
    "operational": "Planning aid only — not a travel clearance, safety assessment or booking. Confirm current "
                   "official advisories, permissions, transport and site access with the Tourism Bureau and site "
                   "custodians before travelling.",
    "virtual": "Operational itineraries are disabled because an official advisory currently advises against "
               "travel. Explore these places virtually instead; check official channels for updates.",
}


@dataclass
class PlanRequest:
    days: int = 3
    interests: list[str] = field(default_factory=list)
    pace: str = "balanced"
    start_slug: str | None = None
    step_free_required: bool = False
    group_size: int = 1
    locale: str = "en"
    avoid_slugs: list[str] = field(default_factory=list)


def haversine_km(a: tuple[float, float], b: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    h = math.sin((lat2 - lat1) / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin((lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(h))


def _segments(db: Session, ids: list) -> dict:
    now = utcnow()
    rows = db.execute(select(RouteSegment).where(RouteSegment.from_id.in_(ids), RouteSegment.to_id.in_(ids),
                                                 RouteSegment.mode == "road")).scalars()
    return {(r.from_id, r.to_id): r for r in rows if r.valid_until is None or r.valid_until > now}


def travel_info(seg: RouteSegment | None, a, b) -> dict | None:
    if seg is not None:
        return {"distance_km": seg.distance_km, "duration_minutes": seg.duration_minutes, "verified": True,
                "basis": f"Verified road segment — {seg.source} ({seg.verified_at.date().isoformat()})",
                "condition_note": seg.condition_note or None}
    if a is None or b is None:
        return {"distance_km": None, "duration_minutes": None, "verified": False,
                "basis": "Location not public; distance and travel time unknown"}
    return {"distance_km": round(haversine_km(a, b), 1), "duration_minutes": None, "verified": False,
            "basis": "Straight-line distance only; road distance and travel time unknown"}


def build_plan(db: Session, req: PlanRequest) -> dict:
    locale = norm_locale(req.locale)
    advisories = active_advisories(db)
    dests = list(db.execute(select(Destination).where(Destination.published_snapshot.is_not(None))).scalars())
    region_block = next((a for a in advisories if a.region_wide and a.level == "travel_not_advised"), None)
    interests = {i.lower() for i in req.interests}

    def view(d: Destination) -> dict:
        return localize_snapshot(d.published_snapshot, locale)

    def score(d: Destination) -> int:
        snap = d.published_snapshot
        tags = {*(snap.get("interests") or []), (snap.get("category") or {}).get("slug", "")}
        return len(interests & {t.lower() for t in tags if t})

    ranked = sorted(dests, key=lambda d: (-score(d), view(d)["name"]))
    if interests:
        ranked = [d for d in ranked if score(d) > 0] or ranked

    base = {"request": req.__dict__, "generated_at": utcnow().isoformat(), "weather": "not_considered",
            "costs": "unknown — no verified price data", "group_size": req.group_size}

    if region_block is not None:
        return {**base, "mode": "virtual", "notice": NOTICE["virtual"], "days": [], "excluded": [],
                "advisory": {"id": str(region_block.id), "level": region_block.level,
                             "issuing_authority": region_block.issuing_authority},
                "virtual_alternatives": [{"slug": d.slug, "name": view(d)["name"]} for d in ranked[:8]]}

    excluded, candidates = [], []
    for d in ranked:
        v = view(d)
        level, _ = advisory_level_for(advisories, d.id)
        if d.slug in req.avoid_slugs:
            excluded.append({"slug": d.slug, "name": v["name"], "reason": "You asked to avoid this place"})
        elif level in BLOCKING:
            excluded.append({"slug": d.slug, "name": v["name"], "reason": f"Official advisory: {level}"})
        elif req.step_free_required and (v.get("accessibility") or {}).get("step_free") != "yes":
            sf = (v.get("accessibility") or {}).get("step_free", "unknown")
            excluded.append({"slug": d.slug, "name": v["name"],
                             "reason": "Step-free access not available" if sf == "no" else "Step-free access unknown"})
        else:
            candidates.append((d, v, level))

    max_stops, day_minutes = PACE.get(req.pace, PACE["balanced"])
    selected = candidates[: req.days * max_stops]
    # Geographic ordering: greedy nearest neighbour from the requested start (or best-scoring stop).
    start = next((c for c in selected if c[0].slug == req.start_slug), None)
    if req.start_slug and start is None:
        sd = next((d for d in dests if d.slug == req.start_slug), None)
        start_loc = latlng(sd.location) if sd else None
    else:
        start_loc = latlng(start[0].location) if start else None
    remaining = list(selected)
    ordered = []
    cur = start_loc
    while remaining:
        if cur is None:
            nxt = remaining[0]
        else:
            nxt = min(remaining, key=lambda c: haversine_km(cur, latlng(c[0].location)) if c[0].location is not None else 1e9)
        ordered.append(nxt)
        remaining.remove(nxt)
        cur = latlng(nxt[0].location) if nxt[0].location is not None else cur

    segs = _segments(db, [c[0].id for c in ordered])
    days = [{"day": i + 1, "stops": [], "known_minutes": 0, "unknowns": []} for i in range(req.days)]
    di, prev = 0, None
    for d, v, level in ordered:
        loc = latlng(d.location) if d.location is not None else None
        prev_loc = latlng(prev.location) if prev is not None and prev.location is not None else None
        travel = travel_info(segs.get((prev.id, d.id)) if prev else None, prev_loc, loc) if prev else None
        need = (v.get("visit_duration_minutes") or 0) + ((travel or {}).get("duration_minutes") or 0)
        while di < req.days and (len(days[di]["stops"]) >= max_stops
                                 or (days[di]["stops"] and days[di]["known_minutes"] + need > day_minutes)):
            di += 1
            travel = None if di < req.days else travel  # first stop of a new day: no intra-day leg
            need = (v.get("visit_duration_minutes") or 0)
        if di >= req.days:
            excluded.append({"slug": d.slug, "name": v["name"], "reason": "Does not fit the selected days and pace"})
            continue
        reasons = []
        matched = sorted(interests & {t.lower() for t in [*(v.get("interests") or []), (v.get("category") or {}).get("slug", "")] if t})
        if matched:
            reasons.append("Matches your interests: " + ", ".join(matched))
        if travel and travel.get("distance_km") is not None:
            reasons.append(f"Close to the previous stop ({travel['distance_km']} km, "
                           f"{'verified road distance' if travel['verified'] else 'straight-line'})")
        if v.get("permit_required") != "no":
            reasons.append("Permission may be required — check with " + (v.get("permit_authority") or "the site custodians")
                           if v.get("permit_required") == "yes" else "Permit requirement unknown — verify before visiting")
        if level == "caution":
            reasons.append("Official advisory: caution")
        stop = {"slug": d.slug, "name": v["name"], "area": v.get("area"), "coordinates": v.get("coordinates"),
                "visit_duration_minutes": v.get("visit_duration_minutes"), "permit_required": v.get("permit_required"),
                "advisory_level": level, "accessibility": v.get("accessibility"), "reasons": reasons,
                "travel_from_previous": travel, "verified_at": v.get("verified_at"), "is_stale": v.get("is_stale")}
        day = days[di]
        day["stops"].append(stop)
        day["known_minutes"] += need
        if v.get("visit_duration_minutes") is None:
            day["unknowns"].append(f"Visit duration unknown for {v['name']}")
        if travel and travel["duration_minutes"] is None:
            day["unknowns"].append(f"Travel time to {v['name']} unknown")
        prev = d
    for day in days:
        if not day["stops"]:
            day["unknowns"].append("Rest or flexible day — no stop scheduled")
    return {**base, "mode": "operational", "notice": NOTICE["operational"], "days": days, "excluded": excluded,
            "virtual_alternatives": [{"slug": e["slug"], "name": e["name"]} for e in excluded
                                     if e["reason"].startswith("Official advisory")]}


def annotate_manual(db: Session, day_slugs: list[list[str]], locale: str) -> dict:
    """Validate and annotate a manually edited itinerary (ordered slugs per day).

    Every stop must be a published destination; advisory-blocked stops are rejected. Travel facts are
    recomputed server-side — the client cannot assert distances or durations.
    """
    from app.core.errors import AppError

    locale = norm_locale(locale)
    advisories = active_advisories(db)
    if any(a.region_wide and a.level == "travel_not_advised" for a in advisories):
        raise AppError(409, "travel_not_advised", "An official advisory currently disables operational itineraries.")
    slugs = {s for day in day_slugs for s in day}
    found = {d.slug: d for d in db.execute(select(Destination).where(Destination.slug.in_(slugs),
                                                                     Destination.published_snapshot.is_not(None))).scalars()}
    unknown = sorted(slugs - set(found))
    if unknown:
        raise AppError(422, "unknown_destinations", "Itineraries may only contain published destinations.", unknown)
    segs = _segments(db, [d.id for d in found.values()])
    days = []
    for i, day in enumerate(day_slugs):
        stops, prev, unknowns = [], None, []
        for slug in day:
            d = found[slug]
            v = localize_snapshot(d.published_snapshot, locale)
            level, _ = advisory_level_for(advisories, d.id)
            if level in BLOCKING:
                raise AppError(409, "advisory_blocked", f"{v['name']} is under an official advisory ({level}).")
            travel = travel_info(segs.get((prev.id, d.id)), latlng(prev.location) if prev.location is not None else None,
                                 latlng(d.location) if d.location is not None else None) if prev else None
            if v.get("visit_duration_minutes") is None:
                unknowns.append(f"Visit duration unknown for {v['name']}")
            stops.append({"slug": slug, "name": v["name"], "area": v.get("area"), "coordinates": v.get("coordinates"),
                          "visit_duration_minutes": v.get("visit_duration_minutes"),
                          "permit_required": v.get("permit_required"), "advisory_level": level,
                          "accessibility": v.get("accessibility"), "reasons": ["Added manually"],
                          "travel_from_previous": travel, "verified_at": v.get("verified_at"), "is_stale": v.get("is_stale")})
            prev = d
        days.append({"day": i + 1, "stops": stops, "unknowns": unknowns or (["Rest or flexible day"] if not stops else [])})
    return {"mode": "operational", "notice": NOTICE["operational"], "days": days, "excluded": [],
            "virtual_alternatives": [], "generated_at": utcnow().isoformat(), "edited": True,
            "weather": "not_considered", "costs": "unknown — no verified price data"}

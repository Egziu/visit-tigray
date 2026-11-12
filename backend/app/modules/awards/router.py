from __future__ import annotations

import re
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.core.i18n import norm_locale, pick
from app.core.security import rate_limit
from app.modules.audit import service as audit
from app.modules.awards.models import Competition, CompetitionCategory, Entry, JudgeAssignment, Score, Sponsor, WinnerProposal
from app.modules.community.models import ConsentRecord, CreatorProfile, Memory
from app.modules.identity.deps import current_principal, require, verified_principal
from app.modules.identity.models import User
from app.modules.identity.service import Principal, permissions_for
from app.modules.media.models import MediaAsset
from app.modules.media.service import asset_public, hamming, sign
from app.modules.platform.service import flag

router = APIRouter(prefix="/api", tags=["awards"])
Loc = Literal["en", "ti", "am"]
PUBLIC_STATUSES = ("open", "judging", "results", "closed")


# ---------------------------------------------------------------- helpers

def _comp(db: Session, slug: str) -> Competition:
    c = db.execute(select(Competition).where(Competition.slug == slug)).scalar_one_or_none()
    if c is None:
        raise not_found("Competition")
    return c


def gates(c: Competition) -> dict:
    return {"legal_terms_approved": c.legal_terms_approved_at is not None,
            "funding_confirmed": c.funding_confirmed_at is not None,
            "bureau_authorized": c.bureau_authorized_at is not None}


def comp_out(db: Session, c: Competition, locale: str, staff: bool = False) -> dict:
    cats = db.execute(select(CompetitionCategory).where(CompetitionCategory.competition_id == c.id)).scalars()
    now = utcnow()
    is_live = c.status == "open" and (c.opens_at is None or c.opens_at <= now) and (c.closes_at is None or c.closes_at > now)
    out: dict[str, Any] = {"slug": c.slug, "title": pick(c.title_i18n, locale)[0], "description": pick(c.description_i18n, locale)[0],
           "rules": pick(c.rules_i18n, locale)[0], "eligibility": pick(c.eligibility_i18n, locale)[0],
           "prize_description": pick(c.prize_description_i18n, locale)[0] or None, "status": c.status,
           "opens_at": c.opens_at.isoformat() if c.opens_at else None,
           "closes_at": c.closes_at.isoformat() if c.closes_at else None, "is_live": is_live, "min_age": c.min_age,
           "terms_version": c.terms_version, "anonymous_judging": c.anonymous_judging,
           "categories": [{"key": k.key, "name": pick(k.name_i18n, locale)[0], "rubric": k.rubric} for k in cats],
           "is_synthetic": c.is_synthetic}
    if staff:
        out["gates"] = gates(c)
        out["sponsors"] = [{"name": s.name, "contribution": s.contribution, "agreement_ref": s.agreement_ref}
                           for s in db.execute(select(Sponsor).where(Sponsor.competition_id == c.id)).scalars()]
    return out


def shingles(text: str, k: int = 5) -> set[str]:
    words = re.findall(r"[\wሀ-፿]+", text.lower())
    return {" ".join(words[i:i + k]) for i in range(max(0, len(words) - k + 1))}


def integrity_checks(db: Session, c: Competition, e: Entry) -> list[dict]:
    """Duplicate-image (dHash) and text-overlap (5-gram Jaccard) signals for human review."""
    flags: list[dict[str, Any]] = []
    others = db.execute(select(Entry).where(Entry.competition_id == c.id, Entry.id != e.id)).scalars().all()
    if e.media_id:
        mine = db.get(MediaAsset, e.media_id)
        if mine is not None:
            for o in others:
                if o.media_id:
                    other = db.get(MediaAsset, o.media_id)
                    if other is not None and (other.sha256 == mine.sha256 or hamming(other.phash, mine.phash) <= 6):
                        flags.append({"type": "duplicate_image", "other_entry": str(o.id)})
            # Same image previously published by someone else on the platform
            for a in db.execute(select(MediaAsset).where(MediaAsset.id != mine.id, MediaAsset.owner_id != e.entrant_id)).scalars():
                if a.sha256 == mine.sha256 or hamming(a.phash, mine.phash) <= 4:
                    flags.append({"type": "image_owned_by_other_user", "media_id": str(a.id)})
    s1 = shingles(e.statement)
    for o in others:
        s2 = shingles(o.statement)
        if s1 and s2:
            j = len(s1 & s2) / len(s1 | s2)
            if j >= 0.5:
                flags.append({"type": "text_overlap", "other_entry": str(o.id), "jaccard": round(j, 2)})
    return flags


# ---------------------------------------------------------------- public

@router.get("/competitions")
def list_public(locale: str = "en", db: Session = Depends(get_db)):
    rows = db.execute(select(Competition).where(Competition.status.in_(PUBLIC_STATUSES))
                      .order_by(Competition.opens_at.desc().nulls_last())).scalars()
    return {"items": [comp_out(db, c, norm_locale(locale)) for c in rows],
            "notice": None if flag(db, "competitions_live") else
            "Competitions are not yet open. They require Bureau authorization, approved legal terms and confirmed funding."}


@router.get("/competitions/{slug}")
def get_public(slug: str, locale: str = "en", db: Session = Depends(get_db)):
    c = _comp(db, slug)
    if c.status not in PUBLIC_STATUSES:
        raise not_found("Competition")
    return comp_out(db, c, norm_locale(locale))


class EntryIn(BaseModel):
    category_key: str = Field(max_length=60)
    title: str = Field(min_length=3, max_length=160)
    statement: str = Field(min_length=30, max_length=5000)
    memory_id: uuid.UUID | None = None
    media_id: uuid.UUID | None = None
    rights_confirmed: bool
    accept_terms_version: str


@router.post("/competitions/{slug}/entries", status_code=201, dependencies=[Depends(rate_limit("write"))])
def submit_entry(slug: str, body: EntryIn, request: Request, p: Principal = Depends(verified_principal),
                 db: Session = Depends(get_db)):
    c = _comp(db, slug)
    now = utcnow()
    if not flag(db, "competitions_live") or c.status != "open" or (c.opens_at and c.opens_at > now) \
            or (c.closes_at and c.closes_at <= now):
        raise AppError(409, "competition_closed", "This competition is not accepting entries.")
    if not p.user.age_confirmed_16_plus or c.min_age > 16:
        raise AppError(403, "age_requirement", f"Entrants must be at least {c.min_age}.")
    if p.permissions & {"awards.manage", "awards.judge", "awards.approve_winners", "awards.authorize"}:
        raise AppError(403, "ineligible", "Competition staff and judges cannot enter.")
    if not body.rights_confirmed:
        raise AppError(422, "rights_required", "Confirm you own the rights to your entry.")
    if body.accept_terms_version != c.terms_version:
        raise AppError(409, "terms_changed", "Please review the current terms before entering.")
    if not db.execute(select(CompetitionCategory).where(CompetitionCategory.competition_id == c.id,
                                                        CompetitionCategory.key == body.category_key)).first():
        raise AppError(422, "unknown_category", "Unknown category")
    count = db.execute(select(func.count()).select_from(Entry).where(
        Entry.competition_id == c.id, Entry.category_key == body.category_key, Entry.entrant_id == p.id,
        Entry.status != "withdrawn")).scalar()
    if (count or 0) >= c.max_entries_per_category:
        raise AppError(409, "entry_limit", "You have reached the entry limit for this category.")
    if body.media_id:
        a = db.get(MediaAsset, body.media_id)
        if a is None or a.owner_id != p.id:
            raise AppError(422, "invalid_media", "You can only enter images you uploaded.")
    if body.memory_id:
        m = db.get(Memory, body.memory_id)
        if m is None or m.author_id != p.id:
            raise AppError(422, "invalid_memory", "You can only enter your own story.")
    e = Entry(competition_id=c.id, entrant_id=p.id, terms_version=c.terms_version,
              **body.model_dump(exclude={"accept_terms_version"}))
    db.add(e)
    db.flush()
    e.integrity_flags = integrity_checks(db, c, e)
    db.add(ConsentRecord(user_id=p.id, kind="competition_terms", version=c.terms_version,
                         context={"competition": c.slug, "entry_id": str(e.id)}))
    audit.record(db, action="competition.entry", resource_type="competition_entry", resource_id=e.id, actor=p,
                 request=request, changes={"flags": e.integrity_flags})
    db.commit()
    return {"id": str(e.id), "status": e.status}


@router.get("/competitions/{slug}/results")
def results(slug: str, locale: str = "en", db: Session = Depends(get_db)):
    c = _comp(db, slug)
    if c.status not in ("results", "closed") or c.results_published_at is None:
        raise not_found("Results")
    out = []
    for w in db.execute(select(WinnerProposal).where(WinnerProposal.competition_id == c.id,
                                                     WinnerProposal.status == "approved")
                        .order_by(WinnerProposal.category_key, WinnerProposal.rank)).scalars():
        e = db.get(Entry, w.entry_id)
        prof = db.get(CreatorProfile, e.entrant_id) if e else None
        u = db.get(User, e.entrant_id) if e else None
        media = db.get(MediaAsset, e.media_id) if e and e.media_id else None
        out.append({"category_key": w.category_key, "rank": w.rank, "title": e.title if e else "",
                    "winner": u.display_name if u else "", "handle": prof.handle if prof else None,
                    "media": asset_public(media) if media and media.status == "approved" else None})
    return {"competition": comp_out(db, c, norm_locale(locale)), "winners": out,
            "published_at": c.results_published_at.isoformat()}


@router.get("/me/entries")
def my_entries(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return [{"id": str(e.id), "competition_id": str(e.competition_id), "category_key": e.category_key, "title": e.title,
             "status": e.status} for e in db.execute(select(Entry).where(Entry.entrant_id == p.id)).scalars()]


@router.get("/competitions/{slug}/certificates/{entry_id}")
def certificate(slug: str, entry_id: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    from fpdf import FPDF

    c = _comp(db, slug)
    e = db.get(Entry, entry_id)
    if e is None or e.entrant_id != p.id or e.competition_id != c.id:
        raise not_found("Entry")
    w = db.execute(select(WinnerProposal).where(WinnerProposal.entry_id == e.id, WinnerProposal.status == "approved")).scalar_one_or_none()
    if c.results_published_at is None:
        raise AppError(409, "results_pending", "Certificates are available after results are published.")
    kind = f"Winner — rank {w.rank}" if w else "Certificate of participation"
    doc = FPDF(orientation="L", format="A4")
    doc.add_page()
    font = "/usr/share/fonts/truetype/freefont/FreeSerif.ttf"
    try:
        doc.add_font("Body", "", font)
        doc.set_font("Body", size=28)
    except (FileNotFoundError, RuntimeError):  # pragma: no cover
        doc.set_font("Helvetica", size=28)
    doc.ln(30)
    doc.cell(0, 14, pick(c.title_i18n, "en")[0], align="C", new_x="LMARGIN", new_y="NEXT")
    doc.set_font_size(20)
    doc.cell(0, 12, kind, align="C", new_x="LMARGIN", new_y="NEXT")
    doc.cell(0, 12, p.user.display_name, align="C", new_x="LMARGIN", new_y="NEXT")
    doc.set_font_size(12)
    doc.cell(0, 10, f"“{e.title}” · category {e.category_key}", align="C", new_x="LMARGIN", new_y="NEXT")
    doc.ln(10)
    doc.set_font_size(9)
    doc.cell(0, 8, f"Certificate ID {e.id} · issued {utcnow():%Y-%m-%d}", align="C")
    return Response(bytes(doc.output()), media_type="application/pdf",
                    headers={"Content-Disposition": f'attachment; filename="certificate-{e.id.hex[:8]}.pdf"'})


# ---------------------------------------------------------------- administration

class CategoryIn(BaseModel):
    key: str = Field(pattern=r"^[a-z0-9_]{2,60}$")
    name_i18n: dict[Loc, str]
    rubric: list[dict] = Field(min_length=1, max_length=10)


class CompetitionIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,98}$")
    title_i18n: dict[Loc, str]
    description_i18n: dict[Loc, str] = Field(default_factory=dict)
    rules_i18n: dict[Loc, str] = Field(default_factory=dict)
    eligibility_i18n: dict[Loc, str] = Field(default_factory=dict)
    prize_description_i18n: dict[Loc, str] = Field(default_factory=dict)
    terms_version: str = Field(default="v1", max_length=20)
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    min_age: int = Field(default=16, ge=16, le=99)
    max_entries_per_category: int = Field(default=1, ge=1, le=5)
    anonymous_judging: bool = True
    categories: list[CategoryIn] = Field(min_length=1, max_length=12)
    is_synthetic: bool = False


def _validate_rubric(rubric: list[dict]) -> None:
    total = 0.0
    for r in rubric:
        if not {"key", "label", "weight", "max"} <= set(r) or float(r["weight"]) <= 0 or int(r["max"]) <= 0:
            raise AppError(422, "invalid_rubric", "Each criterion needs key, label, positive weight and max.")
        total += float(r["weight"])
    if abs(total - 1.0) > 1e-6:
        raise AppError(422, "invalid_rubric", "Rubric weights must sum to 1.")


@router.get("/bureau/competitions")
def staff_list(_=Depends(require("awards.manage", "awards.authorize", "awards.finance", "awards.approve_winners", any_of=True)),
               db: Session = Depends(get_db)):
    return [comp_out(db, c, "en", staff=True) for c in db.execute(select(Competition).order_by(Competition.created_at.desc())).scalars()]


@router.post("/bureau/competitions", status_code=201)
def create(body: CompetitionIn, request: Request, p: Principal = Depends(require("awards.manage")), db: Session = Depends(get_db)):
    if db.execute(select(Competition.id).where(Competition.slug == body.slug)).first():
        raise AppError(409, "slug_taken", "Competition exists")
    if body.opens_at and body.closes_at and body.closes_at <= body.opens_at:
        raise AppError(422, "invalid_dates", "Closing must follow opening.")
    for cat in body.categories:
        _validate_rubric(cat.rubric)
    c = Competition(**body.model_dump(exclude={"categories"}), created_by=p.id)
    db.add(c)
    db.flush()
    for cat in body.categories:
        db.add(CompetitionCategory(competition_id=c.id, **cat.model_dump()))
    audit.record(db, action="competition.create", resource_type="competition", resource_id=c.slug, actor=p, request=request)
    db.commit()
    return comp_out(db, c, "en", staff=True)


class GateIn(BaseModel):
    gate: Literal["legal_terms", "funding", "bureau_authorization"]
    reference: str = Field(min_length=5, max_length=500)


@router.post("/bureau/competitions/{slug}/gates")
def record_gate(slug: str, body: GateIn, request: Request, p: Principal = Depends(current_principal),
                db: Session = Depends(get_db)):
    c = _comp(db, slug)
    need = {"legal_terms": "awards.authorize", "funding": "awards.finance", "bureau_authorization": "awards.authorize"}[body.gate]
    if not p.has(need):
        raise AppError(403, "forbidden", "You do not have permission to record this approval.", {"required": [need]})
    if c.created_by == p.id:
        raise AppError(403, "four_eyes", "Approvals must be recorded by someone other than the competition creator.")
    if body.gate == "legal_terms":
        c.legal_terms_approved_by, c.legal_terms_approved_at = p.id, utcnow()
    elif body.gate == "funding":
        c.funding_confirmed_by, c.funding_confirmed_at = p.id, utcnow()
    else:
        if c.legal_terms_approved_by == p.id:
            raise AppError(403, "four_eyes", "Bureau authorization must come from a different person than legal approval.")
        c.bureau_authorized_by, c.bureau_authorized_at = p.id, utcnow()
    audit.record(db, action=f"competition.gate.{body.gate}", resource_type="competition", resource_id=slug, actor=p,
                 request=request, changes={"reference": body.reference})
    db.commit()
    return comp_out(db, c, "en", staff=True)


class SponsorIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    contribution: str = Field(min_length=3, max_length=1000)
    agreement_ref: str = Field(min_length=3, max_length=200)


@router.post("/bureau/competitions/{slug}/sponsors", status_code=201)
def add_sponsor(slug: str, body: SponsorIn, request: Request, p: Principal = Depends(require("awards.finance")),
                db: Session = Depends(get_db)):
    c = _comp(db, slug)
    db.add(Sponsor(competition_id=c.id, recorded_by=p.id, **body.model_dump()))
    audit.record(db, action="competition.sponsor", resource_type="competition", resource_id=slug, actor=p,
                 request=request, changes=body.model_dump())
    db.commit()
    return {"status": "recorded"}


@router.post("/bureau/competitions/{slug}/status/{to}")
def transition(slug: str, to: Literal["open", "judging", "closed", "cancelled"], request: Request,
               p: Principal = Depends(require("awards.manage")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    allowed = {"draft": {"open", "cancelled"}, "open": {"judging", "cancelled"}, "judging": {"cancelled"},
               "results": {"closed"}}.get(c.status, set())
    if to not in allowed:
        raise AppError(409, "invalid_transition", f"Cannot move from {c.status} to {to}.")
    if to == "open":
        missing = [k for k, v in gates(c).items() if not v]
        if not flag(db, "competitions_live"):
            missing.append("feature_flag_competitions_live")
        if not c.opens_at or not c.closes_at:
            missing.append("opening_and_closing_dates")
        if missing:
            raise AppError(409, "gates_incomplete", "The competition cannot open until every approval is recorded.", missing)
    c.status = to
    audit.record(db, action=f"competition.status.{to}", resource_type="competition", resource_id=slug, actor=p, request=request)
    db.commit()
    return comp_out(db, c, "en", staff=True)


@router.get("/bureau/competitions/{slug}/entries")
def staff_entries(slug: str, p: Principal = Depends(require("awards.manage")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    out = []
    for e in db.execute(select(Entry).where(Entry.competition_id == c.id).order_by(Entry.created_at)).scalars():
        scores = db.execute(select(Score).where(Score.entry_id == e.id)).scalars().all()
        out.append({"id": str(e.id), "category_key": e.category_key, "title": e.title, "status": e.status,
                    "integrity_flags": e.integrity_flags, "entrant_id": str(e.entrant_id),
                    "mean_score": round(sum(s.weighted_total for s in scores) / len(scores), 3) if scores else None,
                    "score_count": len(scores)})
    return out


class EntryDecisionIn(BaseModel):
    status: Literal["eligible", "ineligible", "shortlisted", "disqualified"]
    note: str = Field(min_length=3, max_length=1000)


@router.post("/bureau/competitions/{slug}/entries/{entry_id}/status")
def entry_status(slug: str, entry_id: uuid.UUID, body: EntryDecisionIn, request: Request,
                 p: Principal = Depends(require("awards.manage")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    e = db.get(Entry, entry_id)
    if e is None or e.competition_id != c.id:
        raise not_found("Entry")
    e.status, e.review_note = body.status, body.note
    audit.record(db, action=f"entry.{body.status}", resource_type="competition_entry", resource_id=e.id, actor=p,
                 request=request, changes={"note": body.note})
    db.commit()
    return {"status": e.status}


class JudgeIn(BaseModel):
    user_id: uuid.UUID


@router.post("/bureau/competitions/{slug}/judges", status_code=201)
def assign_judge(slug: str, body: JudgeIn, request: Request, p: Principal = Depends(require("awards.manage")),
                 db: Session = Depends(get_db)):
    c = _comp(db, slug)
    u = db.get(User, body.user_id)
    if u is None or "awards.judge" not in permissions_for(db, u):
        raise AppError(422, "not_a_judge", "The user must hold the judge role.")
    db.add(JudgeAssignment(competition_id=c.id, judge_id=u.id))
    audit.record(db, action="competition.judge_assign", resource_type="competition", resource_id=slug, actor=p,
                 request=request, changes={"judge": str(u.id)})
    db.commit()
    return {"status": "assigned"}


def _assignment(db: Session, c: Competition, p: Principal) -> JudgeAssignment:
    a = db.execute(select(JudgeAssignment).where(JudgeAssignment.competition_id == c.id,
                                                 JudgeAssignment.judge_id == p.id)).scalar_one_or_none()
    if a is None:
        raise AppError(403, "not_assigned", "You are not a judge for this competition.")
    return a


class CoiIn(BaseModel):
    conflicted_entry_ids: list[uuid.UUID] = Field(default_factory=list)
    statement: str = Field(min_length=10, max_length=2000)


@router.post("/judging/{slug}/conflicts")
def declare_coi(slug: str, body: CoiIn, request: Request, p: Principal = Depends(require("awards.judge")),
                db: Session = Depends(get_db)):
    c = _comp(db, slug)
    a = _assignment(db, c, p)
    a.coi_declared_at, a.conflicted_entry_ids, a.coi_statement = utcnow(), [str(x) for x in body.conflicted_entry_ids], body.statement
    audit.record(db, action="judging.coi", resource_type="competition", resource_id=slug, actor=p, request=request,
                 changes={"conflicts": a.conflicted_entry_ids})
    db.commit()
    return {"declared": True}


@router.get("/judging/{slug}/entries")
def judge_entries(slug: str, p: Principal = Depends(require("awards.judge")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    a = _assignment(db, c, p)
    if a.coi_declared_at is None:
        raise AppError(409, "coi_required", "Declare any conflicts of interest before judging.")
    if c.status != "judging":
        raise AppError(409, "not_judging", "Judging has not started.")
    out = []
    for e in db.execute(select(Entry).where(Entry.competition_id == c.id, Entry.status.in_(["eligible", "shortlisted"]))).scalars():
        if str(e.id) in (a.conflicted_entry_ids or []):
            continue
        media = db.get(MediaAsset, e.media_id) if e.media_id else None
        item: dict[str, Any] = {"id": str(e.id), "category_key": e.category_key, "title": e.title, "statement": e.statement,
                "media_preview": sign(str(media.id), "lg") if media else None,
                "my_score": None}
        s = db.execute(select(Score).where(Score.entry_id == e.id, Score.judge_id == p.id)).scalar_one_or_none()
        if s:
            item["my_score"] = s.scores
        if not c.anonymous_judging:
            u = db.get(User, e.entrant_id)
            item["entrant"] = u.display_name if u else None
        out.append(item)
    return out


class ScoreIn(BaseModel):
    scores: dict[str, float]
    comment: str | None = Field(default=None, max_length=2000)


@router.put("/judging/{slug}/entries/{entry_id}/score")
def score(slug: str, entry_id: uuid.UUID, body: ScoreIn, request: Request, p: Principal = Depends(require("awards.judge")),
          db: Session = Depends(get_db)):
    c = _comp(db, slug)
    a = _assignment(db, c, p)
    e = db.get(Entry, entry_id)
    if e is None or e.competition_id != c.id or e.status not in ("eligible", "shortlisted"):
        raise not_found("Entry")
    if a.coi_declared_at is None:
        raise AppError(409, "coi_required", "Declare conflicts of interest before judging.")
    if str(e.id) in (a.conflicted_entry_ids or []) or e.entrant_id == p.id:
        raise AppError(403, "conflict_of_interest", "You declared a conflict with this entry.")
    if c.status != "judging":
        raise AppError(409, "not_judging", "Judging is not open.")
    cat = db.execute(select(CompetitionCategory).where(CompetitionCategory.competition_id == c.id,
                                                       CompetitionCategory.key == e.category_key)).scalar_one()
    rubric = {r["key"]: r for r in cat.rubric}
    if set(body.scores) != set(rubric):
        raise AppError(422, "rubric_mismatch", "Score every rubric criterion exactly once.", sorted(rubric))
    total = 0.0
    for k, v in body.scores.items():
        if not 0 <= v <= rubric[k]["max"]:
            raise AppError(422, "score_out_of_range", f"{k} must be between 0 and {rubric[k]['max']}.")
        total += float(rubric[k]["weight"]) * (v / rubric[k]["max"])
    s = db.execute(select(Score).where(Score.entry_id == e.id, Score.judge_id == p.id)).scalar_one_or_none() \
        or Score(entry_id=e.id, judge_id=p.id, scores={}, weighted_total=0)
    s.scores, s.weighted_total, s.comment, s.submitted_at = body.scores, round(total, 4), body.comment, utcnow()
    db.add(s)
    audit.record(db, action="judging.score", resource_type="competition_entry", resource_id=e.id, actor=p, request=request)
    db.commit()
    return {"weighted_total": s.weighted_total}


class ProposalIn(BaseModel):
    category_key: str
    entry_id: uuid.UUID
    rank: int = Field(default=1, ge=1, le=10)
    rationale: str = Field(min_length=10, max_length=2000)


@router.post("/bureau/competitions/{slug}/winners", status_code=201)
def propose_winner(slug: str, body: ProposalIn, request: Request, p: Principal = Depends(require("awards.manage")),
                   db: Session = Depends(get_db)):
    c = _comp(db, slug)
    e = db.get(Entry, body.entry_id)
    if e is None or e.competition_id != c.id or e.category_key != body.category_key:
        raise not_found("Entry")
    if e.status not in ("eligible", "shortlisted"):
        raise AppError(409, "not_eligible", "Only eligible or shortlisted entries can be proposed.")
    unresolved = [f for f in e.integrity_flags if f.get("type") in ("duplicate_image", "image_owned_by_other_user")]
    if unresolved and "integrity reviewed" not in (e.review_note or ""):
        raise AppError(409, "integrity_review_required", "Resolve integrity flags (record 'integrity reviewed' in the entry note).")
    if not db.execute(select(Score).where(Score.entry_id == e.id)).first():
        raise AppError(409, "unscored", "Entries need at least one judge score before proposal.")
    w = WinnerProposal(competition_id=c.id, category_key=body.category_key, entry_id=e.id, rank=body.rank,
                       proposed_by=p.id, rationale=body.rationale)
    db.add(w)
    db.flush()
    audit.record(db, action="competition.winner_propose", resource_type="competition_entry", resource_id=e.id, actor=p,
                 request=request, changes={"rank": body.rank, "rationale": body.rationale})
    db.commit()
    return {"id": str(w.id), "status": w.status}


class ApproveIn(BaseModel):
    decision: Literal["approve", "reject"]
    note: str = Field(min_length=3, max_length=1000)


@router.post("/bureau/competitions/{slug}/winners/{proposal_id}/decision")
def approve_winner(slug: str, proposal_id: uuid.UUID, body: ApproveIn, request: Request,
                   p: Principal = Depends(require("awards.approve_winners")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    w = db.get(WinnerProposal, proposal_id)
    if w is None or w.competition_id != c.id:
        raise not_found("Proposal")
    if w.proposed_by == p.id:
        raise AppError(403, "four_eyes", "Winners must be approved by someone other than the proposer.")
    w.status, w.approved_by, w.approved_at = ("approved" if body.decision == "approve" else "rejected"), p.id, utcnow()
    if body.decision == "approve":
        e = db.get(Entry, w.entry_id)
        if e:
            e.status = "winner"
    audit.record(db, action=f"competition.winner_{body.decision}", resource_type="competition_entry",
                 resource_id=w.entry_id, actor=p, request=request, changes={"note": body.note})
    db.commit()
    return {"status": w.status}


@router.post("/bureau/competitions/{slug}/publish-results")
def publish_results(slug: str, request: Request, p: Principal = Depends(require("awards.manage")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    if c.status != "judging":
        raise AppError(409, "invalid_transition", "Results can only be published after judging.")
    if not db.execute(select(WinnerProposal).where(WinnerProposal.competition_id == c.id, WinnerProposal.status == "approved")).first():
        raise AppError(409, "no_approved_winners", "No approved winners yet.")
    if db.execute(select(WinnerProposal).where(WinnerProposal.competition_id == c.id, WinnerProposal.status == "proposed")).first():
        raise AppError(409, "pending_proposals", "Resolve all pending winner proposals first.")
    c.status, c.results_published_at = "results", utcnow()
    audit.record(db, action="competition.results_publish", resource_type="competition", resource_id=slug, actor=p, request=request)
    db.commit()
    return {"status": c.status}


class FulfilmentIn(BaseModel):
    status: Literal["in_progress", "fulfilled"]
    note: str = Field(min_length=3, max_length=1000)


@router.post("/bureau/competitions/{slug}/winners/{proposal_id}/fulfilment")
def fulfilment(slug: str, proposal_id: uuid.UUID, body: FulfilmentIn, request: Request,
               p: Principal = Depends(require("awards.finance")), db: Session = Depends(get_db)):
    c = _comp(db, slug)
    w = db.get(WinnerProposal, proposal_id)
    if w is None or w.competition_id != c.id or w.status != "approved":
        raise not_found("Approved winner")
    w.fulfilment_status, w.fulfilment_note = body.status, body.note
    audit.record(db, action="competition.fulfilment", resource_type="competition_entry", resource_id=w.entry_id, actor=p,
                 request=request, changes=body.model_dump())
    db.commit()
    return {"fulfilment_status": w.fulfilment_status}

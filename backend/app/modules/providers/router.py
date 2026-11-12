from __future__ import annotations

import uuid
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.core.ethiopic import fold_for_search
from app.core.i18n import norm_locale, pick
from app.core.security import rate_limit
from app.modules.audit import service as audit
from app.modules.identity.deps import current_principal, require, verified_principal
from app.modules.identity.models import User
from app.modules.identity.service import Principal
from app.modules.platform.service import notify, require_flag
from app.modules.providers.models import PROVIDER_TYPES, Inquiry, Provider, ProviderMember, VerificationRequest

router = APIRouter(prefix="/api", tags=["providers"])
ProviderType = Literal[PROVIDER_TYPES]  # type: ignore[valid-type]


def verification(p: Provider) -> dict:
    status = p.verification_status
    if status == "verified" and p.verification_expires and p.verification_expires < date.today():
        status = "expired"
    return {"status": status, "verified_at": p.verified_at.isoformat() if p.verified_at else None,
            "expires": p.verification_expires.isoformat() if p.verification_expires else None,
            "licence_authority": p.licence_authority,
            "contact_changed_since_verification": p.contact_changed_since_verification}


def provider_out(p: Provider, locale: str, full: bool = False) -> dict:
    out = {"slug": p.slug, "name": p.name, "type": p.type, "area": p.area, "summary": pick(p.summary_i18n, locale)[0],
           "verification": verification(p), "languages": p.languages, "destination_slugs": p.destination_slugs,
           "is_synthetic": p.is_synthetic}
    if full:
        out.update({"description": pick(p.description_i18n, locale)[0], "services": p.services, "contact": p.contact,
                    "availability_note": p.availability_note, "licence_number": p.licence_number})
    return out


def _by_slug(db: Session, slug: str) -> Provider:
    p = db.execute(select(Provider).where(Provider.slug == slug)).scalar_one_or_none()
    if p is None:
        raise not_found("Provider")
    return p


def _member(db: Session, prov: Provider, principal: Principal) -> ProviderMember:
    m = db.get(ProviderMember, (prov.id, principal.id))
    if m is None:
        raise not_found("Provider")
    return m


@router.get("/providers")
def directory(type: str | None = None, q: str | None = None, destination: str | None = None, locale: str = "en",
              verified_only: bool = False, db: Session = Depends(get_db)):
    stmt = select(Provider).where(Provider.published.is_(True))
    if type:
        stmt = stmt.where(Provider.type == type)
    if verified_only:
        stmt = stmt.where(Provider.verification_status == "verified",
                          or_(Provider.verification_expires.is_(None), Provider.verification_expires >= date.today()))
    rows = db.execute(stmt.order_by(Provider.verification_status != "verified", Provider.name)).scalars().all()
    if q:
        fq = fold_for_search(q)
        rows = [r for r in rows if fq in fold_for_search(f"{r.name} {r.area} {pick(r.summary_i18n, 'en')[0]}")]
    if destination:
        rows = [r for r in rows if destination in (r.destination_slugs or [])]
    return [provider_out(r, norm_locale(locale)) for r in rows]


@router.get("/providers/{slug}")
def provider(slug: str, locale: str = "en", db: Session = Depends(get_db)):
    p = _by_slug(db, slug)
    if not p.published:
        raise not_found("Provider")
    return provider_out(p, norm_locale(locale), full=True)


class ProviderIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{2,98}$")
    name: str = Field(min_length=2, max_length=160)
    type: ProviderType
    area: str = Field(default="", max_length=120)
    summary_i18n: dict[Literal["en", "ti", "am"], str] = Field(default_factory=dict)
    description_i18n: dict[Literal["en", "ti", "am"], str] = Field(default_factory=dict)
    services: list[str] = Field(default_factory=list, max_length=30)
    contact: dict[str, str] = Field(default_factory=dict)
    availability_note: str = Field(default="", max_length=500)
    languages: list[str] = Field(default_factory=list, max_length=10)
    destination_slugs: list[str] = Field(default_factory=list, max_length=20)


@router.post("/providers", status_code=201, dependencies=[Depends(rate_limit("write"))])
def apply(body: ProviderIn, request: Request, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    if db.execute(select(Provider.id).where(Provider.slug == body.slug)).first():
        raise AppError(409, "slug_taken", "That address is taken.")
    prov = Provider(**body.model_dump())
    db.add(prov)
    db.flush()
    db.add(ProviderMember(provider_id=prov.id, user_id=p.id, role="owner"))
    audit.record(db, action="provider.apply", resource_type="provider", resource_id=prov.slug, actor=p, request=request)
    db.commit()
    return {"slug": prov.slug, "published": False,
            "message": "Profile created. Submit licence details for verification before it is listed."}


@router.put("/providers/{slug}")
def update_profile(slug: str, body: ProviderIn, request: Request, p: Principal = Depends(verified_principal),
                   db: Session = Depends(get_db)):
    prov = _by_slug(db, slug)
    _member(db, prov, p)
    if body.contact != prov.contact and prov.verification_status == "verified":
        prov.contact_changed_since_verification = True  # flagged for re-verification, visible publicly
    for k, v in body.model_dump(exclude={"slug"}).items():
        setattr(prov, k, v)
    audit.record(db, action="provider.update", resource_type="provider", resource_id=slug, actor=p, request=request)
    db.commit()
    return provider_out(prov, "en", full=True)


class VerificationIn(BaseModel):
    licence_number: str = Field(min_length=2, max_length=80)
    licence_authority: str = Field(min_length=2, max_length=200)
    evidence_note: str = Field(default="", max_length=3000)
    document_media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=10)


@router.post("/providers/{slug}/verification", status_code=201)
def request_verification(slug: str, body: VerificationIn, request: Request, p: Principal = Depends(verified_principal),
                         db: Session = Depends(get_db)):
    prov = _by_slug(db, slug)
    _member(db, prov, p)
    db.add(VerificationRequest(provider_id=prov.id, submitted_by=p.id, licence_number=body.licence_number,
                               licence_authority=body.licence_authority, evidence_note=body.evidence_note,
                               document_media_ids=[str(x) for x in body.document_media_ids]))
    prov.verification_status = "pending"
    audit.record(db, action="provider.verification_request", resource_type="provider", resource_id=slug, actor=p,
                 request=request)
    db.commit()
    return {"status": "pending"}


# ---------------------------------------------------------------- inquiries

class InquiryIn(BaseModel):
    message: str = Field(min_length=10, max_length=3000)
    travel_dates: str | None = Field(default=None, max_length=100)
    group_size: int | None = Field(default=None, ge=1, le=200)


@router.post("/providers/{slug}/inquiries", status_code=201, dependencies=[Depends(rate_limit("write"))])
def inquire(slug: str, body: InquiryIn, request: Request, p: Principal = Depends(verified_principal),
            db: Session = Depends(get_db)):
    require_flag(db, "provider_inquiries")
    prov = _by_slug(db, slug)
    if not prov.published:
        raise not_found("Provider")
    q = Inquiry(provider_id=prov.id, visitor_id=p.id, **body.model_dump())
    db.add(q)
    db.flush()
    for m in db.execute(select(ProviderMember).where(ProviderMember.provider_id == prov.id)).scalars():
        owner = db.get(User, m.user_id)
        if owner:
            notify(db, channel="email", recipient=owner.email, template="provider_inquiry", payload={}, user_id=owner.id)
    audit.record(db, action="inquiry.create", resource_type="provider", resource_id=slug, actor=p, request=request)
    db.commit()
    return {"id": str(q.id), "status": q.status}


def inquiry_out(q: Inquiry) -> dict:
    return {"id": str(q.id), "provider_id": str(q.provider_id), "message": q.message, "travel_dates": q.travel_dates,
            "group_size": q.group_size, "status": q.status, "reply": q.reply, "created_at": q.created_at.isoformat(),
            "replied_at": q.replied_at.isoformat() if q.replied_at else None}


@router.get("/me/inquiries")
def my_inquiries(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    return [inquiry_out(q) for q in db.execute(select(Inquiry).where(Inquiry.visitor_id == p.id)
                                               .order_by(Inquiry.created_at.desc())).scalars()]


@router.get("/providers/{slug}/inquiries")
def provider_inbox(slug: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    prov = _by_slug(db, slug)
    _member(db, prov, p)
    return [inquiry_out(q) for q in db.execute(select(Inquiry).where(Inquiry.provider_id == prov.id)
                                               .order_by(Inquiry.created_at.desc())).scalars()]


class ReplyIn(BaseModel):
    reply: str = Field(min_length=2, max_length=3000)


@router.post("/inquiries/{ident}/reply")
def reply(ident: uuid.UUID, body: ReplyIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    q = db.get(Inquiry, ident)
    if q is None or db.get(ProviderMember, (q.provider_id, p.id)) is None:
        raise not_found("Inquiry")
    q.reply, q.replied_at, q.status = body.reply, utcnow(), "replied"
    db.commit()
    return inquiry_out(q)


# ---------------------------------------------------------------- bookings (disabled)

@router.post("/providers/{slug}/booking-requests", status_code=201)
def booking_request(slug: str, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    require_flag(db, "bookings")
    raise AppError(501, "not_implemented", "Reservations are designed but not yet implemented.")  # pragma: no cover



# ---------------------------------------------------------------- bureau verification

@router.get("/bureau/providers")
def staff_list(status: str | None = None, _=Depends(require("providers.verify")), db: Session = Depends(get_db)):
    stmt = select(Provider).order_by(Provider.updated_at.desc())
    if status:
        stmt = stmt.where(Provider.verification_status == status)
    out = []
    for prov in db.execute(stmt).scalars():
        req = db.execute(select(VerificationRequest).where(VerificationRequest.provider_id == prov.id)
                         .order_by(VerificationRequest.created_at.desc())).scalars().first()
        out.append({**provider_out(prov, "en", full=True), "id": str(prov.id), "published": prov.published,
                    "latest_request": {"id": str(req.id), "licence_number": req.licence_number,
                                       "licence_authority": req.licence_authority, "evidence_note": req.evidence_note,
                                       "status": req.status} if req else None})
    return out


class VerifyIn(BaseModel):
    decision: Literal["verify", "reject", "suspend"]
    expires_on: date | None = None
    note: str = Field(min_length=3, max_length=1000)


@router.post("/bureau/providers/{ident}/verify")
def verify(ident: uuid.UUID, body: VerifyIn, request: Request, p: Principal = Depends(require("providers.verify")),
           db: Session = Depends(get_db)):
    prov = db.get(Provider, ident)
    if prov is None:
        raise not_found("Provider")
    if db.get(ProviderMember, (prov.id, p.id)):
        raise AppError(403, "conflict_of_interest", "You cannot verify a provider you belong to.")
    req = db.execute(select(VerificationRequest).where(VerificationRequest.provider_id == prov.id,
                                                       VerificationRequest.status == "pending")).scalars().first()
    if body.decision == "verify":
        if req is None:
            raise AppError(409, "no_request", "There is no pending verification request with licence details.")
        if body.expires_on is None or body.expires_on <= date.today():
            raise AppError(422, "expiry_required", "Set a future verification expiry (licence validity).")
        prov.verification_status, prov.verified_at, prov.verified_by = "verified", utcnow(), p.id
        prov.verification_expires, prov.published = body.expires_on, True
        prov.licence_number, prov.licence_authority = req.licence_number, req.licence_authority
        prov.contact_changed_since_verification = False
    elif body.decision == "reject":
        prov.verification_status = "rejected"
    else:
        prov.verification_status, prov.published = "suspended", False
    prov.verification_note = body.note
    if req:
        req.status, req.reviewer_id, req.decision_note = body.decision, p.id, body.note
    audit.record(db, action=f"provider.{body.decision}", resource_type="provider", resource_id=prov.slug, actor=p,
                 request=request, changes={"expires": str(body.expires_on), "note": body.note})
    db.commit()
    return {**provider_out(prov, "en", full=True), "published": prov.published}

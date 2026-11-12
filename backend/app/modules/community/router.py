from __future__ import annotations

import json
import re
import uuid
from datetime import datetime
from typing import Any, Literal

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy import delete, func, or_, select
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.core.i18n import norm_locale
from app.core.security import rate_limit
from app.modules.audit import service as audit
from app.modules.community.models import (
    Appeal,
    Block,
    Comment,
    ConsentRecord,
    CreatorProfile,
    Follow,
    Memory,
    MemoryMedia,
    Report,
    SavedMemory,
)
from app.modules.community.moderation import HOLD_FLAGS, flags_for
from app.modules.content.models import Destination
from app.modules.content.service import localize_snapshot
from app.modules.identity.deps import current_principal, optional_principal, require, verified_principal
from app.modules.identity.models import User
from app.modules.identity.service import Principal, revoke_all_sessions, verify_password
from app.modules.media.models import MediaAsset
from app.modules.media.service import asset_public, storage
from app.modules.platform.service import notify

router = APIRouter(prefix="/api", tags=["community"])

CONSENT_VERSION = "2026-11-v1"
REPORT_REASONS = Literal["spam", "harassment", "copyright", "privacy", "misinformation", "sacred_content",
                         "impersonation", "other"]


# ---------------------------------------------------------------- helpers

def ensure_profile(db: Session, user: User) -> CreatorProfile:
    prof = db.get(CreatorProfile, user.id)
    if prof is None:
        base = re.sub(r"[^a-z0-9_]", "", user.display_name.lower().replace(" ", "_"))[:24] or "traveller"
        handle, i = base, 1
        while db.execute(select(CreatorProfile).where(CreatorProfile.handle == handle)).first():
            i += 1
            handle = f"{base}{i}"
        prof = CreatorProfile(user_id=user.id, handle=handle)
        db.add(prof)
        db.flush()
    return prof


def blocked_between(db: Session, a, b) -> bool:
    return bool(db.execute(select(Block).where(or_((Block.blocker_id == a) & (Block.blocked_id == b),
                                                   (Block.blocker_id == b) & (Block.blocked_id == a)))).first())


def memory_out(db: Session, m: Memory, locale: str, full: bool = False, viewer: Principal | None = None) -> dict:
    author = db.get(User, m.author_id)
    prof = db.get(CreatorProfile, m.author_id)
    dest = db.get(Destination, m.destination_id) if m.destination_id else None
    media = db.execute(select(MediaAsset).join(MemoryMedia, MemoryMedia.media_id == MediaAsset.id)
                       .where(MemoryMedia.memory_id == m.id).order_by(MemoryMedia.sort_order)).scalars().all()
    show_media = [asset_public(a) for a in media if a.status == "approved" or (viewer and viewer.id == m.author_id)]
    out = {"id": str(m.id), "title": m.title, "excerpt": m.body[:280] + ("…" if len(m.body) > 280 else ""),
           "destination": {"slug": dest.slug, "name": localize_snapshot(dest.published_snapshot, locale)["name"]}
           if dest and dest.published_snapshot else None,
           "author": {"handle": prof.handle if prof else None,
                      "display_name": author.display_name if author and not author.deleted_at else "Deleted user"},
           "media": show_media, "published_at": m.published_at.isoformat() if m.published_at else None,
           "featured": m.featured, "locale": m.locale,
           "comment_count": db.execute(select(func.count()).select_from(Comment).where(
               Comment.memory_id == m.id, Comment.status == "visible")).scalar()}
    if full:
        out["body"] = m.body
    if viewer and (viewer.id == m.author_id or viewer.has("community.moderate")):
        out.update({"status": m.status, "moderation_note": m.moderation_note})
    return out


def _handle(db: Session, user_id) -> str | None:
    prof = db.get(CreatorProfile, user_id)
    return prof.handle if prof else None


def _visible(db: Session, m: Memory | None, viewer: Principal | None) -> Memory:
    if m is None:
        raise not_found("Story")
    if m.status == "approved":
        prof = db.get(CreatorProfile, m.author_id)
        if prof is None or prof.visibility == "public" or (viewer and viewer.id == m.author_id):
            return m
    if viewer and (viewer.id == m.author_id or viewer.has("community.moderate")):
        return m
    raise not_found("Story")


# ---------------------------------------------------------------- public feed

@router.get("/memories")
def feed(destination: str | None = None, featured: bool | None = None, locale: str = "en", cursor: str | None = None,
         limit: int = 20, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    limit = max(1, min(limit, 50))
    q = (select(Memory).join(CreatorProfile, CreatorProfile.user_id == Memory.author_id)
         .where(Memory.status == "approved", CreatorProfile.visibility == "public"))
    if destination:
        q = q.join(Destination, Destination.id == Memory.destination_id).where(Destination.slug == destination)
    if featured:
        q = q.where(Memory.featured.is_(True))
    if cursor:
        try:
            ts, cid = cursor.split("|")
            q = q.where(or_(Memory.published_at < datetime.fromisoformat(ts),
                            (Memory.published_at == datetime.fromisoformat(ts)) & (Memory.id < uuid.UUID(cid))))
        except ValueError as exc:
            raise AppError(422, "bad_cursor", "Invalid cursor") from exc
    if p is not None:
        blocked = select(Block.blocked_id).where(Block.blocker_id == p.id)
        q = q.where(Memory.author_id.not_in(blocked))
    rows = db.execute(q.order_by(Memory.published_at.desc(), Memory.id.desc()).limit(limit)).scalars().all()
    loc = norm_locale(locale)
    last = rows[-1] if rows else None
    nxt = f"{last.published_at.isoformat()}|{last.id}" if last is not None and last.published_at and len(rows) == limit else None
    return {"items": [memory_out(db, m, loc, viewer=p) for m in rows], "next_cursor": nxt}


@router.get("/memories/{ident}")
def get_memory(ident: uuid.UUID, locale: str = "en", db: Session = Depends(get_db),
               p: Principal | None = Depends(optional_principal)):
    m = _visible(db, db.get(Memory, ident), p)
    return memory_out(db, m, norm_locale(locale), full=True, viewer=p)


class MemoryIn(BaseModel):
    title: str = Field(min_length=5, max_length=140)
    body: str = Field(min_length=30, max_length=8000)
    destination_slug: str | None = Field(default=None, max_length=100)
    media_ids: list[uuid.UUID] = Field(default_factory=list, max_length=12)
    locale: Literal["en", "ti", "am"] = "en"
    consent_publish: bool


@router.post("/memories", status_code=201, dependencies=[Depends(rate_limit("write"))])
def submit(body: MemoryIn, request: Request, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    if not body.consent_publish:
        raise AppError(422, "consent_required", "Explicit consent to publish (after review) is required.")
    dest_id = None
    if body.destination_slug:
        d = db.execute(select(Destination).where(Destination.slug == body.destination_slug,
                                                 Destination.published_snapshot.is_not(None))).scalar_one_or_none()
        if d is None:
            raise AppError(422, "unknown_destination", "Choose a published destination or leave it empty.")
        dest_id = d.id
    media = []
    for mid in body.media_ids:
        a = db.get(MediaAsset, mid)
        if a is None or a.owner_id != p.id or a.purpose != "community" or a.status in ("rejected", "infected"):
            raise AppError(422, "invalid_media", "Attach only images you uploaded for your story.")
        media.append(a)
    ensure_profile(db, p.user)
    m = Memory(author_id=p.id, title=body.title, body=body.body, destination_id=dest_id, locale=body.locale,
               consent_publish_at=utcnow(), ai_flags=flags_for(f"{body.title}\n{body.body}"))
    db.add(m)
    db.flush()
    for i, a in enumerate(media):
        db.add(MemoryMedia(memory_id=m.id, media_id=a.id, sort_order=i))
    db.add(ConsentRecord(user_id=p.id, kind="publish_memory", version=CONSENT_VERSION, context={"memory_id": str(m.id)}))
    audit.record(db, action="memory.submit", resource_type="memory", resource_id=m.id, actor=p, request=request,
                 changes={"ai_flags": m.ai_flags})
    db.commit()
    return {"id": str(m.id), "status": "pending",
            "message": "Thank you. Your story will be reviewed by a person before it is published."}


@router.put("/memories/{ident}")
def edit_memory(ident: uuid.UUID, body: MemoryIn, request: Request, p: Principal = Depends(verified_principal),
                db: Session = Depends(get_db)):
    m = db.get(Memory, ident)
    if m is None or m.author_id != p.id:
        raise not_found("Story")
    m.title, m.body, m.locale = body.title, body.body, body.locale
    m.ai_flags = flags_for(f"{body.title}\n{body.body}")
    m.status, m.published_at = "pending", None  # edits are re-reviewed
    audit.record(db, action="memory.edit", resource_type="memory", resource_id=m.id, actor=p, request=request)
    db.commit()
    return {"id": str(m.id), "status": m.status}


@router.delete("/memories/{ident}", status_code=204)
def delete_memory(ident: uuid.UUID, request: Request, p: Principal = Depends(current_principal),
                  db: Session = Depends(get_db)):
    m = db.get(Memory, ident)
    if m is None or m.author_id != p.id:
        raise not_found("Story")
    _purge_memory(db, m)
    audit.record(db, action="memory.delete", resource_type="memory", resource_id=ident, actor=p, request=request)
    db.commit()
    return Response(status_code=204)


def _purge_memory(db: Session, m: Memory) -> None:
    media_ids = db.execute(select(MemoryMedia.media_id).where(MemoryMedia.memory_id == m.id)).scalars().all()
    db.delete(m)
    db.flush()
    for mid in media_ids:
        a = db.get(MediaAsset, mid)
        if a is not None:
            storage().delete_prefix(a.storage_prefix)
            db.delete(a)


# ---------------------------------------------------------------- comments, saves, follows, blocks

class CommentIn(BaseModel):
    body: str = Field(min_length=2, max_length=1500)


@router.get("/memories/{ident}/comments")
def comments(ident: uuid.UUID, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    _visible(db, db.get(Memory, ident), p)
    rows = db.execute(select(Comment).where(Comment.memory_id == ident, Comment.status == "visible")
                      .order_by(Comment.created_at)).scalars()
    out = []
    for c in rows:
        if p is not None and blocked_between(db, p.id, c.author_id):
            continue
        u = db.get(User, c.author_id)
        out.append({"id": str(c.id), "body": c.body, "created_at": c.created_at.isoformat(),
                    "author": {"display_name": u.display_name if u and not u.deleted_at else "Deleted user",
                               "handle": _handle(db, c.author_id)}})
    return out


@router.post("/memories/{ident}/comments", status_code=201, dependencies=[Depends(rate_limit("write"))])
def add_comment(ident: uuid.UUID, body: CommentIn, request: Request, p: Principal = Depends(verified_principal),
                db: Session = Depends(get_db)):
    m = db.get(Memory, ident)
    if m is None or m.status != "approved":
        raise not_found("Story")
    if blocked_between(db, p.id, m.author_id):
        raise AppError(403, "blocked", "You can't comment on this story.")
    ensure_profile(db, p.user)
    flags = flags_for(body.body)
    c = Comment(memory_id=m.id, author_id=p.id, body=body.body, ai_flags=flags,
                status="pending" if set(flags) & HOLD_FLAGS else "visible")
    db.add(c)
    db.flush()
    audit.record(db, action="comment.create", resource_type="comment", resource_id=c.id, actor=p, request=request,
                 changes={"status": c.status, "flags": flags})
    db.commit()
    return {"id": str(c.id), "status": c.status}


@router.post("/memories/{ident}/save")
def toggle_save(ident: uuid.UUID, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    _visible(db, db.get(Memory, ident), p)
    existing = db.get(SavedMemory, (p.id, ident))
    if existing:
        db.delete(existing)
    else:
        db.add(SavedMemory(user_id=p.id, memory_id=ident))
    db.commit()
    return {"saved": existing is None}


@router.get("/me/saved")
def saved(locale: str = "en", p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(Memory).join(SavedMemory, SavedMemory.memory_id == Memory.id)
                      .where(SavedMemory.user_id == p.id, Memory.status == "approved")).scalars()
    return [memory_out(db, m, norm_locale(locale), viewer=p) for m in rows]


def _creator(db: Session, handle: str) -> CreatorProfile:
    prof = db.execute(select(CreatorProfile).where(CreatorProfile.handle == handle)).scalar_one_or_none()
    if prof is None:
        raise not_found("Creator")
    return prof


@router.get("/creators/{handle}")
def creator(handle: str, locale: str = "en", db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    prof = _creator(db, handle)
    is_self = p is not None and p.id == prof.user_id
    if prof.visibility != "public" and not is_self:
        raise not_found("Creator")
    u = db.get(User, prof.user_id)
    stories = db.execute(select(Memory).where(Memory.author_id == prof.user_id, Memory.status == "approved")
                         .order_by(Memory.published_at.desc()).limit(50)).scalars()
    return {"handle": prof.handle, "display_name": u.display_name if u else "", "bio": prof.bio,
            "followers": db.execute(select(func.count()).select_from(Follow).where(Follow.creator_id == prof.user_id)).scalar(),
            "following": bool(p and db.get(Follow, (p.id, prof.user_id))),
            "stories": [memory_out(db, m, norm_locale(locale), viewer=p) for m in stories]}


@router.post("/creators/{handle}/follow")
def toggle_follow(handle: str, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    prof = _creator(db, handle)
    if prof.user_id == p.id:
        raise AppError(422, "self_follow", "You can't follow yourself.")
    if blocked_between(db, p.id, prof.user_id):
        raise AppError(403, "blocked", "You can't follow this creator.")
    f = db.get(Follow, (p.id, prof.user_id))
    if f:
        db.delete(f)
    else:
        db.add(Follow(follower_id=p.id, creator_id=prof.user_id))
    db.commit()
    return {"following": f is None}


@router.post("/creators/{handle}/block")
def toggle_block(handle: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    prof = _creator(db, handle)
    if prof.user_id == p.id:
        raise AppError(422, "self_block", "You can't block yourself.")
    b = db.get(Block, (p.id, prof.user_id))
    if b:
        db.delete(b)
    else:
        db.add(Block(blocker_id=p.id, blocked_id=prof.user_id))
        for f in db.execute(select(Follow).where(or_((Follow.follower_id == p.id) & (Follow.creator_id == prof.user_id),
                                                     (Follow.follower_id == prof.user_id) & (Follow.creator_id == p.id)))).scalars():
            db.delete(f)
    db.commit()
    return {"blocked": b is None}


# ---------------------------------------------------------------- reports & appeals

class ReportIn(BaseModel):
    reason: REPORT_REASONS
    detail: str = Field(default="", max_length=2000)


@router.post("/memories/{ident}/report", status_code=201, dependencies=[Depends(rate_limit("write"))])
def report_memory(ident: uuid.UUID, body: ReportIn, request: Request, db: Session = Depends(get_db),
                  p: Principal | None = Depends(optional_principal)):
    _visible(db, db.get(Memory, ident), p)
    db.add(Report(reporter_id=p.id if p else None, target_kind="memory", target_id=str(ident), reason=body.reason,
                  detail=body.detail))
    audit.record(db, action="report.create", resource_type="memory", resource_id=ident, actor=p, request=request,
                 changes={"reason": body.reason})
    db.commit()
    return {"status": "received"}


@router.post("/comments/{ident}/report", status_code=201, dependencies=[Depends(rate_limit("write"))])
def report_comment(ident: uuid.UUID, body: ReportIn, db: Session = Depends(get_db),
                   p: Principal | None = Depends(optional_principal)):
    if db.get(Comment, ident) is None:
        raise not_found("Comment")
    db.add(Report(reporter_id=p.id if p else None, target_kind="comment", target_id=str(ident), reason=body.reason,
                  detail=body.detail))
    db.commit()
    return {"status": "received"}


class AppealIn(BaseModel):
    target_kind: Literal["memory", "comment", "competition_entry"]
    target_id: uuid.UUID
    statement: str = Field(min_length=20, max_length=3000)


@router.post("/appeals", status_code=201)
def appeal(body: AppealIn, request: Request, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    decider = None
    if body.target_kind == "memory":
        m = db.get(Memory, body.target_id)
        if m is None or m.author_id != p.id or m.status not in ("rejected", "removed"):
            raise AppError(422, "not_appealable", "Only your own rejected or removed stories can be appealed.")
        decider = m.moderated_by
    elif body.target_kind == "comment":
        c = db.get(Comment, body.target_id)
        if c is None or c.author_id != p.id or c.status != "removed":
            raise AppError(422, "not_appealable", "Only your own removed comments can be appealed.")
    if db.execute(select(Appeal).where(Appeal.user_id == p.id, Appeal.target_kind == body.target_kind,
                                       Appeal.target_id == str(body.target_id))).first():
        raise AppError(409, "duplicate_appeal", "You have already appealed this decision.")
    a = Appeal(user_id=p.id, target_kind=body.target_kind, target_id=str(body.target_id), statement=body.statement,
               original_decider=decider)
    db.add(a)
    db.flush()
    audit.record(db, action="appeal.create", resource_type=body.target_kind, resource_id=body.target_id, actor=p, request=request)
    db.commit()
    return {"id": str(a.id), "status": a.status}


# ---------------------------------------------------------------- my data

class ProfileIn(BaseModel):
    display_name: str | None = Field(default=None, min_length=2, max_length=80)
    handle: str | None = Field(default=None, pattern=r"^[a-z0-9_]{3,40}$")
    bio: str | None = Field(default=None, max_length=600)
    visibility: Literal["public", "private"] | None = None
    locale: Literal["en", "ti", "am"] | None = None


@router.get("/me/profile")
def my_profile(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    prof = ensure_profile(db, p.user)
    db.commit()
    return {"handle": prof.handle, "bio": prof.bio, "visibility": prof.visibility, "display_name": p.user.display_name,
            "locale": p.user.locale}


@router.put("/me/profile")
def update_profile(body: ProfileIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    prof = ensure_profile(db, p.user)
    if body.handle and body.handle != prof.handle:
        if db.execute(select(CreatorProfile).where(CreatorProfile.handle == body.handle)).first():
            raise AppError(409, "handle_taken", "That handle is taken.")
        prof.handle = body.handle
    for k in ("bio", "visibility"):
        if getattr(body, k) is not None:
            setattr(prof, k, getattr(body, k))
    if body.display_name:
        p.user.display_name = body.display_name
    if body.locale:
        p.user.locale = body.locale
    db.commit()
    return {"handle": prof.handle, "bio": prof.bio, "visibility": prof.visibility, "display_name": p.user.display_name}


@router.get("/me/memories")
def my_memories(locale: str = "en", p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(Memory).where(Memory.author_id == p.id).order_by(Memory.created_at.desc())).scalars()
    return [memory_out(db, m, norm_locale(locale), full=True, viewer=p) for m in rows]


@router.get("/me/export")
def export_my_data(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """Data portability: everything we hold that is about or created by this user (JSON)."""
    from app.modules.planner.models import Itinerary, ItineraryVersion
    from app.modules.providers.models import Inquiry
    from app.modules.tie.models import Conversation, Message

    u = p.user
    prof = db.get(CreatorProfile, u.id)
    data = {
        "generated_at": utcnow().isoformat(),
        "account": {"email": u.email, "display_name": u.display_name, "locale": u.locale,
                    "created_at": u.created_at.isoformat(), "email_verified": u.email_verified_at is not None,
                    "mfa_enabled": u.mfa_enabled, "roles": [r.key for r in u.roles]},
        "profile": {"handle": prof.handle, "bio": prof.bio, "visibility": prof.visibility} if prof else None,
        "memories": [{"id": str(m.id), "title": m.title, "body": m.body, "status": m.status, "created_at": m.created_at.isoformat(),
                      "media": [str(x) for x in db.execute(select(MemoryMedia.media_id).where(MemoryMedia.memory_id == m.id)).scalars()]}
                     for m in db.execute(select(Memory).where(Memory.author_id == u.id)).scalars()],
        "comments": [{"id": str(c.id), "memory_id": str(c.memory_id), "body": c.body, "created_at": c.created_at.isoformat()}
                     for c in db.execute(select(Comment).where(Comment.author_id == u.id)).scalars()],
        "saved": [str(s.memory_id) for s in db.execute(select(SavedMemory).where(SavedMemory.user_id == u.id)).scalars()],
        "following": [str(f.creator_id) for f in db.execute(select(Follow).where(Follow.follower_id == u.id)).scalars()],
        "consents": [{"kind": c.kind, "version": c.version, "granted_at": c.granted_at.isoformat(),
                      "withdrawn_at": c.withdrawn_at.isoformat() if c.withdrawn_at else None}
                     for c in db.execute(select(ConsentRecord).where(ConsentRecord.user_id == u.id)).scalars()],
        "itineraries": [{"title": i.title, "versions": [v.plan for v in db.execute(select(ItineraryVersion).where(
            ItineraryVersion.itinerary_id == i.id)).scalars()]}
            for i in db.execute(select(Itinerary).where(Itinerary.owner_id == u.id)).scalars()],
        "inquiries": [{"provider_id": str(q.provider_id), "message": q.message, "reply": q.reply,
                       "created_at": q.created_at.isoformat()}
                      for q in db.execute(select(Inquiry).where(Inquiry.visitor_id == u.id)).scalars()],
        "guide_conversations": [{"id": str(c.id), "messages": [{"role": m.role, "content": m.content} for m in db.execute(
            select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at)).scalars()]}
            for c in db.execute(select(Conversation).where(Conversation.owner_id == u.id)).scalars()],
    }
    return Response(json.dumps(data, ensure_ascii=False, indent=1), media_type="application/json",
                    headers={"Content-Disposition": 'attachment; filename="visit-tigray-my-data.json"'})


class DeleteMeIn(BaseModel):
    confirm: Literal["DELETE"]
    password: str | None = None


@router.delete("/me")
def delete_me(body: DeleteMeIn, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    """Erase the account and the user's own content. Audit entries are retained (append-only, security basis)."""
    from app.modules.planner.models import Itinerary
    from app.modules.tie.models import Conversation

    u = p.user
    if u.password_hash and not verify_password(u.password_hash, body.password or ""):
        raise AppError(401, "invalid_credentials", "Password confirmation failed.")
    if p.permissions:
        raise AppError(409, "staff_account", "Staff accounts are removed by a system administrator.")
    for m in db.execute(select(Memory).where(Memory.author_id == u.id)).scalars().all():
        _purge_memory(db, m)
    for a in db.execute(select(MediaAsset).where(MediaAsset.owner_id == u.id)).scalars().all():
        storage().delete_prefix(a.storage_prefix)
        db.delete(a)
    db.execute(delete(Comment).where(Comment.author_id == u.id))
    db.execute(delete(Itinerary).where(Itinerary.owner_id == u.id))
    db.execute(delete(Conversation).where(Conversation.owner_id == u.id))
    db.execute(delete(CreatorProfile).where(CreatorProfile.user_id == u.id))
    for c in db.execute(select(ConsentRecord).where(ConsentRecord.user_id == u.id, ConsentRecord.withdrawn_at.is_(None))).scalars():
        c.withdrawn_at = utcnow()
    revoke_all_sessions(db, u.id)
    u.email = f"deleted-{u.id}@deleted.invalid"
    u.display_name, u.password_hash, u.totp_secret_enc = "Deleted user", None, None
    u.is_active, u.deleted_at, u.oidc_subject = False, utcnow(), None
    audit.record(db, action="account.delete", resource_type="user", resource_id=u.id, actor=p, request=request)
    db.commit()
    return {"status": "deleted"}


# ---------------------------------------------------------------- moderation (bureau)

@router.get("/bureau/moderation/queue")
def queue(_=Depends(require("community.moderate")), db: Session = Depends(get_db)):
    items: list[dict[str, Any]] = []
    for m in db.execute(select(Memory).where(Memory.status == "pending").order_by(Memory.created_at)).scalars():
        u = db.get(User, m.author_id)
        items.append({"kind": "memory", "id": str(m.id), "title": m.title, "body": m.body, "author": u.display_name if u else "",
                      "ai_flags": m.ai_flags, "created_at": m.created_at.isoformat(),
                      "media": [{**asset_public(a), "status": a.status, "had_gps_metadata": a.had_gps_metadata,
                                 "scan_status": a.scan_status}
                                for a in db.execute(select(MediaAsset).join(MemoryMedia, MemoryMedia.media_id == MediaAsset.id)
                                                    .where(MemoryMedia.memory_id == m.id)).scalars()]})
    for c in db.execute(select(Comment).where(Comment.status == "pending")).scalars():
        items.append({"kind": "comment", "id": str(c.id), "title": None, "body": c.body, "ai_flags": c.ai_flags,
                      "created_at": c.created_at.isoformat()})
    reports = [{"id": str(r.id), "target_kind": r.target_kind, "target_id": r.target_id, "reason": r.reason,
                "detail": r.detail, "created_at": r.created_at.isoformat()}
               for r in db.execute(select(Report).where(Report.status == "open").order_by(Report.created_at)).scalars()]
    appeals = [{"id": str(a.id), "target_kind": a.target_kind, "target_id": a.target_id, "statement": a.statement,
                "created_at": a.created_at.isoformat()}
               for a in db.execute(select(Appeal).where(Appeal.status == "open")).scalars()]
    from app.modules.social.router import queue_items
    items += queue_items(db)
    return {"items": items, "reports": reports, "appeals": appeals,
            "notice": "AI flags are advisory signals only. Decisions are made by moderators."}


class DecisionIn(BaseModel):
    decision: Literal["approve", "reject", "remove", "restore", "feature", "unfeature"]
    note: str = Field(default="", max_length=500)


@router.post("/bureau/moderation/{kind}/{ident}/decision")
def decide(kind: Literal["memory", "comment", "journal_post", "journal_comment", "space_message"], ident: str,
           body: DecisionIn, request: Request, p: Principal = Depends(require("community.moderate")),
           db: Session = Depends(get_db)):
    if kind in ("journal_post", "journal_comment", "space_message"):
        from app.modules.social.router import decide as social_decide
        try:
            social_decide(db, kind, ident, body.decision, body.note, p)
        except ValueError as exc:
            raise not_found("Item") from exc
        for r in db.execute(select(Report).where(Report.target_kind == kind, Report.target_id == ident,
                                                 Report.status == "open")).scalars():
            r.status = "actioned" if body.decision in ("reject", "remove") else "dismissed"
            r.resolved_by = p.id
        audit.record(db, action=f"moderation.{body.decision}", resource_type=kind, resource_id=ident, actor=p,
                     request=request, changes={"note": body.note})
        db.commit()
        return {"status": "ok"}
    try:
        ident_uuid = uuid.UUID(ident)
    except ValueError as exc:
        raise not_found("Item") from exc
    if kind == "memory":
        m = db.get(Memory, ident_uuid)
        if m is None:
            raise not_found("Story")
        if m.author_id == p.id:
            raise AppError(403, "conflict_of_interest", "You cannot moderate your own story.")
        if body.decision in ("approve", "restore"):
            m.status, m.published_at = "approved", m.published_at or utcnow()
            for a in db.execute(select(MediaAsset).join(MemoryMedia, MemoryMedia.media_id == MediaAsset.id)
                                .where(MemoryMedia.memory_id == m.id)).scalars():
                if a.status == "clean":
                    a.status, a.reviewed_by = "approved", p.id
                    a.license, a.credit = a.license or "Visitor licence grant " + CONSENT_VERSION, a.credit or "Visitor contribution"
        elif body.decision in ("reject", "remove"):
            m.status = "rejected" if body.decision == "reject" else "removed"
            m.featured = False
        elif body.decision in ("feature", "unfeature"):
            if m.status != "approved":
                raise AppError(409, "not_published", "Only published stories can be featured.")
            m.featured = body.decision == "feature"
        m.moderation_note, m.moderated_by = body.note or m.moderation_note, p.id
        author = db.get(User, m.author_id)
        if author and body.decision in ("approve", "reject", "remove") and not author.deleted_at:
            notify(db, channel="email", recipient=author.email, template="moderation_decision", user_id=author.id,
                   payload={"title": m.title, "decision": {"approve": "published", "reject": "not published",
                                                           "remove": "removed"}[body.decision],
                            "note": body.note or "You can appeal this decision from your account."})
    else:
        c = db.get(Comment, ident_uuid)
        if c is None:
            raise not_found("Comment")
        c.status = "visible" if body.decision in ("approve", "restore") else "removed"
    for r in db.execute(select(Report).where(Report.target_kind == kind, Report.target_id == str(ident),
                                             Report.status == "open")).scalars():
        r.status = "actioned" if body.decision in ("reject", "remove") else "dismissed"
        r.resolved_by = p.id
    audit.record(db, action=f"moderation.{body.decision}", resource_type=kind, resource_id=ident_uuid, actor=p,
                 request=request, changes={"note": body.note})
    db.commit()
    return {"status": "ok"}


class AppealDecisionIn(BaseModel):
    decision: Literal["uphold", "overturn"]
    note: str = Field(min_length=5, max_length=1000)


@router.post("/bureau/appeals/{ident}/decision")
def decide_appeal(ident: uuid.UUID, body: AppealDecisionIn, request: Request,
                  p: Principal = Depends(require("community.moderate")), db: Session = Depends(get_db)):
    a = db.get(Appeal, ident)
    if a is None or a.status != "open":
        raise not_found("Appeal")
    if a.original_decider == p.id:
        raise AppError(403, "independent_review", "An appeal must be decided by a different moderator.")
    a.status, a.decided_by, a.decision_note = ("overturned" if body.decision == "overturn" else "upheld"), p.id, body.note
    if body.decision == "overturn" and a.target_kind == "memory":
        m = db.get(Memory, uuid.UUID(a.target_id))
        if m:
            m.status, m.published_at, m.moderated_by = "approved", utcnow(), p.id
    if body.decision == "overturn" and a.target_kind == "comment":
        c = db.get(Comment, uuid.UUID(a.target_id))
        if c:
            c.status = "visible"
    audit.record(db, action=f"appeal.{body.decision}", resource_type=a.target_kind, resource_id=a.target_id, actor=p,
                 request=request, changes={"note": body.note})
    db.commit()
    return {"status": a.status}

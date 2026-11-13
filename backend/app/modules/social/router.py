"""Journals (Substack-like) and Spaces (Discord-like) APIs.

Safety model
* Journal posts are pre-moderated (nothing is published automatically), like Tigray Memories.
* Space messages are post-moderated for real-time conversation, but messages with risky signals
  (spam terms, abuse, many links) are HELD for a moderator and visible only to their author.
* Verified email + membership required to post; per-user slow mode; rate limits; blocks respected.
* Bodies are plain text; journals use structured blocks. Nothing is rendered as HTML.
"""
from __future__ import annotations

import json
import math
import re
import time
import uuid
from collections.abc import Iterator
from datetime import datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import func, or_, select, text, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, session_factory, utcnow
from app.core.errors import AppError, not_found
from app.core.i18n import norm_locale, pick
from app.core.security import rate_limit
from app.modules.audit import service as audit
from app.modules.community.models import Block, ConsentRecord, CreatorProfile, Report
from app.modules.community.moderation import HOLD_FLAGS, flags_for
from app.modules.community.router import ensure_profile
from app.modules.content.models import Destination
from app.modules.content.service import localize_snapshot
from app.modules.identity.deps import current_principal, optional_principal, require, verified_principal
from app.modules.identity.models import User
from app.modules.identity.service import Principal
from app.modules.media.models import MediaAsset
from app.modules.media.service import asset_public
from app.modules.platform.models import Notification
from app.modules.platform.service import notify
from app.modules.social.models import (
    Channel,
    JournalComment,
    JournalLike,
    JournalPost,
    MessageReaction,
    Publication,
    Space,
    SpaceMember,
    SpaceMessage,
    Subscription,
)

router = APIRouter(prefix="/api", tags=["social"])

CONSENT_VERSION = "2026-11-v1"
ALLOWED_EMOJI = ("👍", "❤️", "🙏", "😂", "😮", "🎉", "🌄", "☕")
EDIT_WINDOW = timedelta(minutes=15)
WORDS_PER_MINUTE = 220
REPORT_REASONS = Literal["spam", "harassment", "copyright", "privacy", "misinformation", "sacred_content", "impersonation", "other"]


# ================================================================== helpers

def _user_label(db: Session, user_id) -> dict:
    u = db.get(User, user_id)
    prof = db.get(CreatorProfile, user_id)
    return {"handle": prof.handle if prof else None,
            "display_name": u.display_name if u and not u.deleted_at else "Deleted user"}


def _media(db: Session, media_id, viewer_id=None) -> dict | None:
    if not media_id:
        return None
    a = db.get(MediaAsset, media_id)
    if a is None:
        return None
    if a.status == "approved" or (viewer_id is not None and a.owner_id == viewer_id):
        return asset_public(a)
    return None


def _blocked_ids(db: Session, viewer: Principal | None) -> set:
    if viewer is None:
        return set()
    rows = db.execute(select(Block.blocker_id, Block.blocked_id).where(
        or_(Block.blocker_id == viewer.id, Block.blocked_id == viewer.id))).all()
    return {b for a, b in rows if a == viewer.id} | {a for a, b in rows if b == viewer.id}


def _publication(db: Session, user: User) -> Publication:
    pub = db.get(Publication, user.id)
    if pub is None:
        pub = Publication(user_id=user.id, name=f"{user.display_name}'s journal")
        db.add(pub)
        db.flush()
    return pub


def _in_app(db: Session, user_id, kind: str, title: str, body: str, link: str) -> None:
    db.add(Notification(channel="inapp", recipient=str(user_id), template=kind, user_id=user_id, classification="personal",
                        status="sent", sent_at=utcnow(), payload={"kind": kind, "title": title[:160], "body": body[:300], "link": link}))


# ================================================================== Journals

class Block_(BaseModel):
    type: Literal["paragraph", "heading", "quote", "image", "divider"]
    text: str | None = Field(default=None, max_length=8000)
    media_id: uuid.UUID | None = None
    caption: str | None = Field(default=None, max_length=300)


class PostIn(BaseModel):
    title: str = Field(min_length=5, max_length=160)
    subtitle: str = Field(default="", max_length=240)
    blocks: list[Block_] = Field(min_length=1, max_length=200)
    cover_media_id: uuid.UUID | None = None
    destination_slug: str | None = Field(default=None, max_length=100)
    tags: list[str] = Field(default_factory=list, max_length=8)
    locale: Literal["en", "ti", "am"] = "en"
    consent_publish: bool
    notify_subscribers: bool = True


def _validate_post(db: Session, body: PostIn, p: Principal) -> tuple[list[dict], uuid.UUID | None, int]:
    if not body.consent_publish:
        raise AppError(422, "consent_required", "Explicit consent to publish (after review) is required.")
    out, words = [], 0
    for b in body.blocks:
        if b.type in ("paragraph", "heading", "quote") and not (b.text or "").strip():
            raise AppError(422, "empty_block", "Text blocks cannot be empty.")
        if b.type == "image":
            a = db.get(MediaAsset, b.media_id) if b.media_id else None
            if a is None or a.owner_id != p.id or a.purpose != "community" or a.status in ("rejected", "infected"):
                raise AppError(422, "invalid_media", "Images must be your own community uploads.")
        words += len((b.text or "").split())
        out.append({k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in b.model_dump().items() if v is not None})
    if words < 30:
        raise AppError(422, "too_short", "Write at least 30 words.")
    if body.cover_media_id:
        a = db.get(MediaAsset, body.cover_media_id)
        if a is None or a.owner_id != p.id:
            raise AppError(422, "invalid_media", "The cover must be your own upload.")
    dest_id = None
    if body.destination_slug:
        d = db.execute(select(Destination).where(Destination.slug == body.destination_slug,
                                                 Destination.published_snapshot.is_not(None))).scalar_one_or_none()
        if d is None:
            raise AppError(422, "unknown_destination", "Choose a published destination or leave it empty.")
        dest_id = d.id
    return out, dest_id, max(1, math.ceil(words / WORDS_PER_MINUTE))


def _tags(tags: list[str]) -> list[str]:
    clean = []
    for t in tags:
        t = re.sub(r"[^\wሀ-፿-]+", "", t.strip().lower())[:40]
        if t and t not in clean:
            clean.append(t)
    return clean


def post_summary(db: Session, post: JournalPost, locale: str, viewer: Principal | None) -> dict:
    dest = db.get(Destination, post.destination_id) if post.destination_id else None
    pub = db.get(Publication, post.author_id)
    first_text = next((b.get("text", "") for b in post.blocks if b.get("type") == "paragraph"), "")
    return {"id": str(post.id), "title": post.title, "subtitle": post.subtitle,
            "excerpt": first_text[:280] + ("…" if len(first_text) > 280 else ""),
            "cover": _media(db, post.cover_media_id, viewer.id if viewer else None),
            "author": _user_label(db, post.author_id),
            "publication": {"handle": _user_label(db, post.author_id)["handle"], "name": pub.name if pub else ""},
            "destination": {"slug": dest.slug, "name": localize_snapshot(dest.published_snapshot, locale)["name"]}
            if dest and dest.published_snapshot else None,
            "tags": post.tags or [], "published_at": post.published_at.isoformat() if post.published_at else None,
            "reading_minutes": post.reading_minutes, "featured": post.featured,
            "like_count": db.execute(select(func.count()).select_from(JournalLike).where(JournalLike.post_id == post.id)).scalar(),
            "comment_count": db.execute(select(func.count()).select_from(JournalComment).where(
                JournalComment.post_id == post.id, JournalComment.status == "visible")).scalar(),
            "liked": bool(viewer and db.get(JournalLike, (viewer.id, post.id)))}


def _visible_post(db: Session, post: JournalPost | None, viewer: Principal | None) -> JournalPost:
    if post is None:
        raise not_found("Story")
    if post.status == "approved":
        prof = db.get(CreatorProfile, post.author_id)
        if (prof is None or prof.visibility == "public") and post.author_id not in _blocked_ids(db, viewer):
            return post
    if viewer and (viewer.id == post.author_id or viewer.has("community.moderate")):
        return post
    raise not_found("Story")


@router.get("/journal")
def journal_feed(feed: Literal["latest", "following", "featured"] = "latest", destination: str | None = None,
                 tag: str | None = None, cursor: str | None = None, locale: str = "en", limit: int = Query(20, ge=1, le=50),
                 db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    q = (select(JournalPost).join(CreatorProfile, CreatorProfile.user_id == JournalPost.author_id)
         .where(JournalPost.status == "approved", CreatorProfile.visibility == "public"))
    if feed == "following":
        if p is None:
            raise AppError(401, "unauthenticated", "Sign in to see stories from publications you follow.")
        q = q.where(JournalPost.author_id.in_(select(Subscription.publication_id).where(Subscription.subscriber_id == p.id)))
    if feed == "featured":
        q = q.where(JournalPost.featured.is_(True))
    if destination:
        q = q.join(Destination, Destination.id == JournalPost.destination_id).where(Destination.slug == destination)
    if tag:
        q = q.where(JournalPost.tags.contains([tag.lower()]))
    blocked = _blocked_ids(db, p)
    if blocked:
        q = q.where(JournalPost.author_id.not_in(blocked))
    if cursor:
        try:
            ts, cid = cursor.split("|")
            q = q.where(or_(JournalPost.published_at < datetime.fromisoformat(ts),
                            (JournalPost.published_at == datetime.fromisoformat(ts)) & (JournalPost.id < uuid.UUID(cid))))
        except ValueError as exc:
            raise AppError(422, "bad_cursor", "Invalid cursor") from exc
    rows = db.execute(q.order_by(JournalPost.published_at.desc(), JournalPost.id.desc()).limit(limit)).scalars().all()
    loc = norm_locale(locale)
    last = rows[-1] if len(rows) == limit else None
    return {"items": [post_summary(db, r, loc, p) for r in rows],
            "next_cursor": f"{last.published_at.isoformat()}|{last.id}" if last and last.published_at else None}


@router.get("/journal/{ident}")
def journal_post(ident: uuid.UUID, locale: str = "en", db: Session = Depends(get_db),
                 p: Principal | None = Depends(optional_principal)):
    post = _visible_post(db, db.get(JournalPost, ident), p)
    viewer_id = p.id if p else None
    blocks = []
    for b in post.blocks:
        item = {k: v for k, v in b.items() if k != "media_id"}
        if b.get("type") == "image":
            item["media"] = _media(db, b.get("media_id"), viewer_id)
        blocks.append(item)
    out = {**post_summary(db, post, norm_locale(locale), p), "blocks": blocks, "is_author": bool(p and p.id == post.author_id)}
    if p and (p.id == post.author_id or p.has("community.moderate")):
        out.update({"status": post.status, "moderation_note": post.moderation_note})
    return out


@router.post("/journal", status_code=201, dependencies=[Depends(rate_limit("write"))])
def create_post(body: PostIn, request: Request, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    blocks, dest_id, minutes = _validate_post(db, body, p)
    ensure_profile(db, p.user)
    _publication(db, p.user)
    text_all = body.title + "\n" + body.subtitle + "\n" + "\n".join(b.get("text", "") for b in blocks)
    post = JournalPost(author_id=p.id, title=body.title, subtitle=body.subtitle, blocks=blocks,
                       cover_media_id=body.cover_media_id, destination_id=dest_id, tags=_tags(body.tags), locale=body.locale,
                       reading_minutes=minutes, consent_publish_at=utcnow(), notify_subscribers=body.notify_subscribers,
                       ai_flags=flags_for(text_all))
    db.add(post)
    db.flush()
    db.add(ConsentRecord(user_id=p.id, kind="publish_journal", version=CONSENT_VERSION, context={"post_id": str(post.id)}))
    audit.record(db, action="journal.submit", resource_type="journal_post", resource_id=post.id, actor=p, request=request,
                 changes={"ai_flags": post.ai_flags})
    db.commit()
    return {"id": str(post.id), "status": "pending",
            "message": "Thank you. A person will review your story before it is published."}


@router.put("/journal/{ident}")
def edit_post(ident: uuid.UUID, body: PostIn, request: Request, p: Principal = Depends(verified_principal),
              db: Session = Depends(get_db)):
    post = db.get(JournalPost, ident)
    if post is None or post.author_id != p.id:
        raise not_found("Story")
    blocks, dest_id, minutes = _validate_post(db, body, p)
    post.title, post.subtitle, post.blocks, post.cover_media_id = body.title, body.subtitle, blocks, body.cover_media_id
    post.destination_id, post.tags, post.locale, post.reading_minutes = dest_id, _tags(body.tags), body.locale, minutes
    post.notify_subscribers = body.notify_subscribers
    post.ai_flags = flags_for(body.title + "\n" + "\n".join(b.get("text", "") for b in blocks))
    post.status, post.published_at, post.featured = "pending", None, False  # edits are re-reviewed
    audit.record(db, action="journal.edit", resource_type="journal_post", resource_id=post.id, actor=p, request=request)
    db.commit()
    return {"id": str(post.id), "status": post.status}


@router.delete("/journal/{ident}", status_code=204)
def delete_post(ident: uuid.UUID, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    post = db.get(JournalPost, ident)
    if post is None or post.author_id != p.id:
        raise not_found("Story")
    db.delete(post)
    audit.record(db, action="journal.delete", resource_type="journal_post", resource_id=ident, actor=p, request=request)
    db.commit()
    return Response(status_code=204)


@router.get("/me/journal")
def my_posts(locale: str = "en", p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(JournalPost).where(JournalPost.author_id == p.id).order_by(JournalPost.created_at.desc())).scalars()
    return [{**post_summary(db, r, norm_locale(locale), p), "status": r.status} for r in rows]


@router.post("/journal/{ident}/like")
def like(ident: uuid.UUID, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    post = _visible_post(db, db.get(JournalPost, ident), p)
    if post.status != "approved":
        raise AppError(409, "not_published", "Only published stories can be liked.")
    existing = db.get(JournalLike, (p.id, post.id))
    if existing:
        db.delete(existing)
    else:
        db.add(JournalLike(user_id=p.id, post_id=post.id))
    db.commit()
    count = db.execute(select(func.count()).select_from(JournalLike).where(JournalLike.post_id == post.id)).scalar()
    return {"liked": existing is None, "like_count": count}


class CommentIn(BaseModel):
    body: str = Field(min_length=2, max_length=2000)
    parent_id: uuid.UUID | None = None


@router.get("/journal/{ident}/comments")
def post_comments(ident: uuid.UUID, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    _visible_post(db, db.get(JournalPost, ident), p)
    blocked = _blocked_ids(db, p)
    rows = db.execute(select(JournalComment).where(JournalComment.post_id == ident, JournalComment.status == "visible")
                      .order_by(JournalComment.created_at)).scalars()
    return [{"id": str(c.id), "parent_id": str(c.parent_id) if c.parent_id else None, "body": c.body,
             "author": _user_label(db, c.author_id), "created_at": c.created_at.isoformat(),
             "can_delete": bool(p and (p.id == c.author_id or p.has("community.moderate")))}
            for c in rows if c.author_id not in blocked]


@router.post("/journal/{ident}/comments", status_code=201, dependencies=[Depends(rate_limit("write"))])
def add_comment(ident: uuid.UUID, body: CommentIn, request: Request, p: Principal = Depends(verified_principal),
                db: Session = Depends(get_db)):
    post = db.get(JournalPost, ident)
    if post is None or post.status != "approved":
        raise not_found("Story")
    if post.author_id in _blocked_ids(db, p):
        raise AppError(403, "blocked", "You can't comment on this story.")
    parent = None
    if body.parent_id:
        parent = db.get(JournalComment, body.parent_id)
        if parent is None or parent.post_id != post.id:
            raise AppError(422, "invalid_parent", "Reply target not found.")
        if parent.parent_id is not None:
            parent = db.get(JournalComment, parent.parent_id)  # keep threads one level deep
    ensure_profile(db, p.user)
    flags = flags_for(body.body)
    c = JournalComment(post_id=post.id, author_id=p.id, parent_id=parent.id if parent else None, body=body.body,
                       ai_flags=flags, status="pending" if set(flags) & HOLD_FLAGS else "visible")
    db.add(c)
    db.flush()
    if c.status == "visible":
        target = parent.author_id if parent else post.author_id
        if target != p.id:
            _in_app(db, target, "journal_comment", f"New comment on “{post.title}”", body.body[:140], f"/journal/{post.id}")
    audit.record(db, action="journal.comment", resource_type="journal_comment", resource_id=c.id, actor=p, request=request,
                 changes={"status": c.status})
    db.commit()
    return {"id": str(c.id), "status": c.status}


@router.delete("/journal-comments/{ident}", status_code=204)
def delete_comment(ident: uuid.UUID, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    c = db.get(JournalComment, ident)
    if c is None or not (c.author_id == p.id or p.has("community.moderate")):
        raise not_found("Comment")
    c.status = "removed"
    audit.record(db, action="journal.comment_remove", resource_type="journal_comment", resource_id=c.id, actor=p, request=request)
    db.commit()
    return Response(status_code=204)


class ReportIn(BaseModel):
    reason: REPORT_REASONS
    detail: str = Field(default="", max_length=2000)


@router.post("/journal/{ident}/report", status_code=201, dependencies=[Depends(rate_limit("write"))])
def report_post(ident: uuid.UUID, body: ReportIn, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    _visible_post(db, db.get(JournalPost, ident), p)
    db.add(Report(reporter_id=p.id if p else None, target_kind="journal_post", target_id=str(ident), reason=body.reason,
                  detail=body.detail))
    db.commit()
    return {"status": "received"}


# ------------------------------------------------------------------ publications & subscriptions

def _pub_by_handle(db: Session, handle: str) -> tuple[Publication, CreatorProfile]:
    prof = db.execute(select(CreatorProfile).where(CreatorProfile.handle == handle)).scalar_one_or_none()
    if prof is None:
        raise not_found("Publication")
    user = db.get(User, prof.user_id)
    if user is None or user.deleted_at:
        raise not_found("Publication")
    return _publication(db, user), prof


@router.get("/publications/{handle}")
def publication(handle: str, locale: str = "en", db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    pub, prof = _pub_by_handle(db, handle)
    if prof.visibility != "public" and not (p and p.id == prof.user_id):
        raise not_found("Publication")
    sub = db.get(Subscription, (p.id, pub.user_id)) if p else None
    posts = db.execute(select(JournalPost).where(JournalPost.author_id == pub.user_id, JournalPost.status == "approved")
                       .order_by(JournalPost.published_at.desc()).limit(50)).scalars()
    db.commit()
    return {"handle": prof.handle, "name": pub.name, "tagline": pub.tagline, "about": pub.about,
            "cover": _media(db, pub.cover_media_id, p.id if p else None), "author": _user_label(db, pub.user_id),
            "subscriber_count": db.execute(select(func.count()).select_from(Subscription).where(
                Subscription.publication_id == pub.user_id)).scalar(),
            "is_subscribed": sub is not None, "email_digest": bool(sub and sub.email_digest),
            "posts": [post_summary(db, x, norm_locale(locale), p) for x in posts]}


class PublicationIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    tagline: str = Field(default="", max_length=200)
    about: str = Field(default="", max_length=4000)
    cover_media_id: uuid.UUID | None = None


@router.put("/me/publication")
def update_publication(body: PublicationIn, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    ensure_profile(db, p.user)
    pub = _publication(db, p.user)
    if body.cover_media_id:
        a = db.get(MediaAsset, body.cover_media_id)
        if a is None or a.owner_id != p.id:
            raise AppError(422, "invalid_media", "The cover must be your own upload.")
    pub.name, pub.tagline, pub.about, pub.cover_media_id = body.name, body.tagline, body.about, body.cover_media_id
    db.commit()
    return {"name": pub.name, "tagline": pub.tagline, "about": pub.about}


class SubscribeIn(BaseModel):
    subscribe: bool = True
    email_digest: bool = False


@router.post("/publications/{handle}/subscribe")
def subscribe(handle: str, body: SubscribeIn, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    pub, prof = _pub_by_handle(db, handle)
    if pub.user_id == p.id:
        raise AppError(422, "self_subscribe", "You can't subscribe to your own publication.")
    if pub.user_id in _blocked_ids(db, p):
        raise AppError(403, "blocked", "You can't subscribe to this publication.")
    sub = db.get(Subscription, (p.id, pub.user_id))
    if body.subscribe:
        if sub is None:
            sub = Subscription(subscriber_id=p.id, publication_id=pub.user_id)
            db.add(sub)
        sub.email_digest = body.email_digest
        if body.email_digest:
            db.add(ConsentRecord(user_id=p.id, kind="email_digest", version=CONSENT_VERSION, context={"publication": handle}))
    elif sub is not None:
        db.delete(sub)
    db.commit()
    count = db.execute(select(func.count()).select_from(Subscription).where(Subscription.publication_id == pub.user_id)).scalar()
    return {"subscribed": body.subscribe, "email_digest": bool(body.subscribe and body.email_digest), "subscriber_count": count}


def on_post_approved(db: Session, post: JournalPost) -> None:
    """Called by moderation: publish, notify author and (once) subscribers."""
    post.status, post.published_at = "approved", post.published_at or utcnow()
    _in_app(db, post.author_id, "journal_published", "Your story is published", post.title, f"/journal/{post.id}")
    if post.notify_subscribers and post.subscribers_notified_at is None:
        pub = db.get(Publication, post.author_id)
        for s in db.execute(select(Subscription).where(Subscription.publication_id == post.author_id)).scalars():
            _in_app(db, s.subscriber_id, "journal_new_post", f"New from {pub.name if pub else 'a journal you follow'}",
                    post.title, f"/journal/{post.id}")
            if s.email_digest:
                u = db.get(User, s.subscriber_id)
                if u and u.is_active and not u.deleted_at:
                    notify(db, channel="email", recipient=u.email, template="journal_new_post", user_id=u.id,
                           payload={"title": post.title, "publication": pub.name if pub else "",
                                    "link": f"{get_settings().public_base_url}/{u.locale}/journal/{post.id}"},
                           idempotency_key=f"journal:{post.id}:{u.id}")
        post.subscribers_notified_at = utcnow()


# ------------------------------------------------------------------ notifications

@router.get("/me/notifications")
def my_notifications(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    rows = db.execute(select(Notification).where(Notification.user_id == p.id, Notification.channel == "inapp")
                      .order_by(Notification.created_at.desc()).limit(50)).scalars().all()
    unread = db.execute(select(func.count()).select_from(Notification).where(
        Notification.user_id == p.id, Notification.channel == "inapp", Notification.read_at.is_(None))).scalar()
    return {"items": [{"id": str(n.id), "kind": n.payload.get("kind", n.template), "title": n.payload.get("title", ""),
                       "body": n.payload.get("body", ""), "link": n.payload.get("link"),
                       "created_at": n.created_at.isoformat(), "read": n.read_at is not None} for n in rows],
            "unread": unread}


class ReadIn(BaseModel):
    ids: list[uuid.UUID] = Field(default_factory=list, max_length=100)


@router.post("/me/notifications/read")
def mark_read(body: ReadIn, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    q = update(Notification).where(Notification.user_id == p.id, Notification.channel == "inapp", Notification.read_at.is_(None))
    if body.ids:
        q = q.where(Notification.id.in_(body.ids))
    db.execute(q.values(read_at=utcnow()))
    db.commit()
    return {"status": "ok"}


# ================================================================== Spaces

def _space(db: Session, slug: str) -> Space:
    s = db.execute(select(Space).where(Space.slug == slug, Space.is_active.is_(True))).scalar_one_or_none()
    if s is None:
        raise not_found("Space")
    return s


def _channel(db: Session, space: Space, slug: str) -> Channel:
    c = db.execute(select(Channel).where(Channel.space_id == space.id, Channel.slug == slug)).scalar_one_or_none()
    if c is None:
        raise not_found("Channel")
    return c


def _membership(db: Session, space_id, p: Principal | None) -> SpaceMember | None:
    return db.get(SpaceMember, (space_id, p.id)) if p else None


def _is_space_mod(p: Principal | None, m: SpaceMember | None) -> bool:
    return bool(p and (p.has("community.moderate") or (m and m.role == "moderator")))


def message_out(db: Session, m: SpaceMessage, viewer: Principal | None, space_role_cache: dict | None = None) -> dict:
    reacts: dict[str, dict] = {}
    for r in db.execute(select(MessageReaction).where(MessageReaction.message_id == m.id)).scalars():
        e = reacts.setdefault(r.emoji, {"emoji": r.emoji, "count": 0, "mine": False})
        e["count"] += 1
        e["mine"] = e["mine"] or bool(viewer and r.user_id == viewer.id)
    reply = None
    if m.reply_to_id:
        ch = db.get(Channel, m.channel_id)
        mod = _is_space_mod(viewer, db.get(SpaceMember, (ch.space_id, viewer.id)) if viewer and ch else None)
        rm = db.execute(_visible_messages(
            select(SpaceMessage).where(SpaceMessage.id == m.reply_to_id, SpaceMessage.channel_id == m.channel_id),
            viewer, mod, _blocked_ids(db, viewer),
        )).scalar_one_or_none()
        if rm is not None:
            reply = {"id": rm.id, "excerpt": "[removed]" if rm.status == "removed" else rm.body[:120],
                     "author": _user_label(db, rm.author_id)["display_name"]}
    ch = db.get(Channel, m.channel_id)
    role = None
    if ch is not None:
        mem = db.get(SpaceMember, (ch.space_id, m.author_id))
        role = mem.role if mem else None
    is_author = bool(viewer and viewer.id == m.author_id)
    mod = _is_space_mod(viewer, db.get(SpaceMember, (ch.space_id, viewer.id)) if viewer and ch else None)
    return {"id": m.id, "author": {**_user_label(db, m.author_id), "role": role},
            "body": "" if m.status == "removed" else m.body, "reply_to": reply,
            "reactions": list(reacts.values()), "created_at": m.created_at.isoformat(),
            "edited_at": m.edited_at.isoformat() if m.edited_at else None, "status": m.status,
            "can_edit": is_author and m.status != "removed" and utcnow() - m.created_at < EDIT_WINDOW,
            "can_delete": (is_author or mod) and m.status != "removed"}


def _visible_messages(q, viewer: Principal | None, mod: bool, blocked: set):
    if not mod:
        cond = SpaceMessage.status != "held"
        if viewer is not None:
            cond = or_(cond, SpaceMessage.author_id == viewer.id)
        q = q.where(cond)
    if blocked:
        q = q.where(SpaceMessage.author_id.not_in(blocked))
    return q


@router.get("/spaces")
def spaces(locale: str = "en", db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    loc = norm_locale(locale)
    out = []
    for s in db.execute(select(Space).where(Space.is_active.is_(True)).order_by(Space.sort_order, Space.slug)).scalars():
        m = _membership(db, s.id, p)
        mod = _is_space_mod(p, m)
        chans = db.execute(select(Channel).where(Channel.space_id == s.id).order_by(Channel.sort_order, Channel.slug)).scalars()
        out.append({"slug": s.slug, "name": pick(s.name_i18n, loc)[0], "description": pick(s.description_i18n, loc)[0],
                    "icon": s.icon, "is_member": m is not None, "my_role": m.role if m else None,
                    "member_count": db.execute(select(func.count()).select_from(SpaceMember).where(
                        SpaceMember.space_id == s.id)).scalar(),
                    "channels": [{"slug": c.slug, "name": pick(c.name_i18n, loc)[0], "topic": pick(c.topic_i18n, loc)[0],
                                  "kind": c.kind, "slow_mode_seconds": c.slow_mode_seconds,
                                  "can_post": bool(m and not (m.banned_until and m.banned_until > utcnow())
                                                   and (c.kind == "text" or mod))} for c in chans]})
    return out


@router.post("/spaces/{slug}/join")
def join(slug: str, request: Request, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    s = _space(db, slug)
    if db.get(SpaceMember, (s.id, p.id)) is None:
        ensure_profile(db, p.user)
        db.add(SpaceMember(space_id=s.id, user_id=p.id))
        db.add(ConsentRecord(user_id=p.id, kind="space_guidelines", version=CONSENT_VERSION, context={"space": slug}))
    db.commit()
    return {"is_member": True}


@router.post("/spaces/{slug}/leave")
def leave(slug: str, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    s = _space(db, slug)
    m = db.get(SpaceMember, (s.id, p.id))
    if m is not None:
        if m.banned_until and m.banned_until > utcnow():
            raise AppError(409, "banned", "You cannot leave and rejoin to bypass a restriction.")
        db.delete(m)
    db.commit()
    return {"is_member": False}


@router.get("/spaces/{slug}/channels/{channel}/messages")
def messages(slug: str, channel: str, before: int | None = None, after: int | None = None,
             limit: int = Query(50, ge=1, le=100), db: Session = Depends(get_db),
             p: Principal | None = Depends(optional_principal)):
    s = _space(db, slug)
    c = _channel(db, s, channel)
    mod = _is_space_mod(p, _membership(db, s.id, p))
    q = _visible_messages(select(SpaceMessage).where(SpaceMessage.channel_id == c.id), p, mod, _blocked_ids(db, p))
    if after is not None:
        rows = db.execute(q.where(SpaceMessage.id > after).order_by(SpaceMessage.id).limit(limit + 1)).scalars().all()
        has_more = len(rows) > limit
        rows = rows[:limit]
    else:
        if before is not None:
            q = q.where(SpaceMessage.id < before)
        rows = db.execute(q.order_by(SpaceMessage.id.desc()).limit(limit + 1)).scalars().all()
        has_more = len(rows) > limit
        rows = list(reversed(rows[:limit]))
    return {"items": [message_out(db, m, p) for m in rows], "has_more": has_more}


class MessageIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)
    reply_to: int | None = None


def _bump(db: Session, m: SpaceMessage) -> None:
    m.revision += 1
    m.updated_seq = db.execute(text("SELECT nextval('space_message_update_seq')")).scalar_one()


@router.post("/spaces/{slug}/channels/{channel}/messages", status_code=201, dependencies=[Depends(rate_limit("write"))])
def post_message(slug: str, channel: str, body: MessageIn, request: Request, p: Principal = Depends(verified_principal),
                 db: Session = Depends(get_db)):
    s = _space(db, slug)
    c = _channel(db, s, channel)
    m = _membership(db, s.id, p)
    if m is None:
        raise AppError(403, "not_a_member", "Join this space to post.")
    if m.banned_until and m.banned_until > utcnow():
        raise AppError(403, "restricted", "You are temporarily restricted from posting in this space.")
    mod = _is_space_mod(p, m)
    if c.kind == "announcements" and not mod:
        raise AppError(403, "read_only", "Only moderators post in announcement channels.")
    if c.slow_mode_seconds and not mod:
        last = db.execute(select(func.max(SpaceMessage.created_at)).where(SpaceMessage.channel_id == c.id,
                                                                        SpaceMessage.author_id == p.id)).scalar()
        if last and (utcnow() - last).total_seconds() < c.slow_mode_seconds:
            wait = int(c.slow_mode_seconds - (utcnow() - last).total_seconds()) + 1
            raise AppError(429, "slow_mode", f"Slow mode is on. You can post again in {wait} s.", {"retry_after": wait})
    reply_to = None
    if body.reply_to is not None:
        rm = db.get(SpaceMessage, body.reply_to)
        if rm is None or rm.channel_id != c.id:
            raise AppError(422, "invalid_reply", "Reply target not found in this channel.")
        reply_to = rm.id
    flags = flags_for(body.body)
    msg = SpaceMessage(channel_id=c.id, author_id=p.id, body=body.body.strip(), reply_to_id=reply_to, ai_flags=flags,
                       status="held" if set(flags) & HOLD_FLAGS else "visible")
    db.add(msg)
    db.flush()
    _bump(db, msg)
    if msg.status == "held":
        audit.record(db, action="space.message_held", resource_type="space_message", resource_id=msg.id, actor=p,
                     request=request, changes={"flags": flags})
    db.commit()
    return message_out(db, msg, p)


class EditIn(BaseModel):
    body: str = Field(min_length=1, max_length=4000)


@router.patch("/space-messages/{ident}")
def edit_message(ident: int, body: EditIn, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    m = db.get(SpaceMessage, ident)
    if m is None or m.author_id != p.id or m.status == "removed":
        raise not_found("Message")
    if utcnow() - m.created_at > EDIT_WINDOW:
        raise AppError(409, "edit_window_closed", "Messages can be edited for 15 minutes.")
    flags = flags_for(body.body)
    m.body, m.edited_at, m.ai_flags = body.body.strip(), utcnow(), flags
    if set(flags) & HOLD_FLAGS:
        m.status = "held"
    _bump(db, m)
    db.commit()
    return message_out(db, m, p)


@router.delete("/space-messages/{ident}", status_code=204)
def delete_message(ident: int, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    m = db.get(SpaceMessage, ident)
    if m is None:
        raise not_found("Message")
    ch = db.get(Channel, m.channel_id)
    mod = _is_space_mod(p, db.get(SpaceMember, (ch.space_id, p.id)) if ch else None)
    if not (m.author_id == p.id or mod):
        raise not_found("Message")
    m.status, m.removed_by = "removed", p.id
    _bump(db, m)
    if m.author_id != p.id:
        audit.record(db, action="space.message_remove", resource_type="space_message", resource_id=m.id, actor=p, request=request)
    db.commit()
    return Response(status_code=204)


class ReactionIn(BaseModel):
    emoji: str = Field(max_length=8)


@router.post("/space-messages/{ident}/reactions")
def react(ident: int, body: ReactionIn, p: Principal = Depends(verified_principal), db: Session = Depends(get_db)):
    if body.emoji not in ALLOWED_EMOJI:
        raise AppError(422, "emoji_not_allowed", "Choose one of the available reactions.", list(ALLOWED_EMOJI))
    m = db.get(SpaceMessage, ident)
    if m is None or m.status != "visible":
        raise not_found("Message")
    ch = db.get(Channel, m.channel_id)
    if ch is None or db.get(SpaceMember, (ch.space_id, p.id)) is None:
        raise AppError(403, "not_a_member", "Join this space to react.")
    existing = db.get(MessageReaction, (m.id, p.id, body.emoji))
    if existing:
        db.delete(existing)
    else:
        db.add(MessageReaction(message_id=m.id, user_id=p.id, emoji=body.emoji))
    db.flush()
    _bump(db, m)
    db.commit()
    return message_out(db, m, p)


@router.post("/space-messages/{ident}/report", status_code=201, dependencies=[Depends(rate_limit("write"))])
def report_message(ident: int, body: ReportIn, db: Session = Depends(get_db), p: Principal | None = Depends(optional_principal)):
    if db.get(SpaceMessage, ident) is None:
        raise not_found("Message")
    db.add(Report(reporter_id=p.id if p else None, target_kind="space_message", target_id=str(ident), reason=body.reason,
                  detail=body.detail))
    db.commit()
    return {"status": "received"}


# ------------------------------------------------------------------ real-time stream (SSE)

STREAM_SECONDS = 55   # clients reconnect with ?after=; keeps proxies and workers healthy
POLL_SECONDS = 1.5


def _sse(event: str, data: Any) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"


@router.get("/spaces/{slug}/channels/{channel}/stream")
def stream(slug: str, channel: str, request: Request, after: int = 0, db: Session = Depends(get_db),
           p: Principal | None = Depends(optional_principal)):
    """Server-Sent Events. Works through the Next.js /api proxy with same-origin cookies and across
    several API workers (state is read from PostgreSQL, not process memory)."""
    s = _space(db, slug)
    c = _channel(db, s, channel)
    viewer_id = p.id if p else None
    space_id = s.id
    update_cursor = db.execute(select(func.coalesce(func.max(SpaceMessage.updated_seq), 0))
                               .where(SpaceMessage.channel_id == c.id)).scalar_one()
    channel_id = c.id
    db.close()  # do not hold the request session for the life of the stream

    def gen() -> Iterator[str]:
        last_id, last_upd, started, last_ping = after, update_cursor, time.monotonic(), time.monotonic()
        yield "retry: 3000\n\n"
        yield _sse("ready", {"after": after})  # lets clients detect a working (unbuffered) stream immediately
        while time.monotonic() - started < STREAM_SECONDS:
            with session_factory()() as s2:
                # Revalidate session, roles and blocks on every poll, including revocation.
                viewer = optional_principal(request, s2)
                if viewer_id is not None and viewer is None:
                    yield _sse("reconnect", {"after": last_id})
                    return
                mod = _is_space_mod(viewer, _membership(s2, space_id, viewer))
                blocked = _blocked_ids(s2, viewer)
                base = _visible_messages(select(SpaceMessage).where(SpaceMessage.channel_id == channel_id), viewer, mod, blocked)
                for m in s2.execute(base.where(SpaceMessage.id > last_id).order_by(SpaceMessage.id).limit(100)).scalars():
                    last_id = max(last_id, m.id)
                    yield _sse("message", message_out(s2, m, viewer))
                for m in s2.execute(select(SpaceMessage).where(SpaceMessage.channel_id == channel_id,
                                                               SpaceMessage.updated_seq > last_upd,
                                                               SpaceMessage.id <= last_id)
                                    .order_by(SpaceMessage.updated_seq).limit(100)).scalars():
                    last_upd = max(last_upd, m.updated_seq)
                    if m.author_id in blocked or (m.status == "held" and not mod and m.author_id != viewer_id):
                        # Remove previously visible content without revealing the hidden body or author.
                        yield _sse("update", {"id": m.id, "status": "removed", "body": "", "reply_to": None,
                                              "reactions": [], "can_edit": False, "can_delete": False})
                    else:
                        yield _sse("update", message_out(s2, m, viewer))
                # Advance only through processed rows; jumping to MAX drops batches over 100.
            if time.monotonic() - last_ping > 15:
                last_ping = time.monotonic()
                yield _sse("ping", {"t": int(time.time())})
            time.sleep(POLL_SECONDS)
        yield _sse("reconnect", {"after": last_id})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-store, no-transform",  # no-transform: proxies/compressors must not gzip-buffer events
                                      "X-Accel-Buffering": "no", "Connection": "keep-alive"})


# ------------------------------------------------------------------ space administration (bureau)

class ChannelIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}$")
    name_i18n: dict[Literal["en", "ti", "am"], str]
    topic_i18n: dict[Literal["en", "ti", "am"], str] = Field(default_factory=dict)
    kind: Literal["text", "announcements"] = "text"
    slow_mode_seconds: int = Field(default=0, ge=0, le=3600)
    sort_order: int = 100


class SpaceIn(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9][a-z0-9-]{1,58}$")
    name_i18n: dict[Literal["en", "ti", "am"], str]
    description_i18n: dict[Literal["en", "ti", "am"], str] = Field(default_factory=dict)
    icon: str = Field(default="✳", max_length=16)
    sort_order: int = 100
    channels: list[ChannelIn] = Field(min_length=1, max_length=30)


@router.post("/bureau/spaces", status_code=201)
def create_space(body: SpaceIn, request: Request, p: Principal = Depends(require("community.moderate")),
                 db: Session = Depends(get_db)):
    if db.execute(select(Space.id).where(Space.slug == body.slug)).first():
        raise AppError(409, "slug_taken", "Space exists")
    s = Space(**body.model_dump(exclude={"channels"}))
    db.add(s)
    db.flush()
    for ch in body.channels:
        db.add(Channel(space_id=s.id, **ch.model_dump()))
    audit.record(db, action="space.create", resource_type="space", resource_id=body.slug, actor=p, request=request)
    db.commit()
    return {"slug": s.slug}


class ChannelSettingsIn(BaseModel):
    slow_mode_seconds: int = Field(ge=0, le=3600)


@router.put("/bureau/spaces/{slug}/channels/{channel}")
def channel_settings(slug: str, channel: str, body: ChannelSettingsIn, request: Request,
                     p: Principal = Depends(require("community.moderate")), db: Session = Depends(get_db)):
    c = _channel(db, _space(db, slug), channel)
    c.slow_mode_seconds = body.slow_mode_seconds
    audit.record(db, action="space.channel_settings", resource_type="space_channel", resource_id=f"{slug}/{channel}", actor=p,
                 request=request, changes=body.model_dump())
    db.commit()
    return {"slow_mode_seconds": c.slow_mode_seconds}


class MemberRoleIn(BaseModel):
    handle: str
    role: Literal["member", "moderator"] | None = None
    restrict_hours: int | None = Field(default=None, ge=0, le=24 * 30)


@router.post("/bureau/spaces/{slug}/members")
def set_member(slug: str, body: MemberRoleIn, request: Request, p: Principal = Depends(require("community.moderate")),
               db: Session = Depends(get_db)):
    s = _space(db, slug)
    prof = db.execute(select(CreatorProfile).where(CreatorProfile.handle == body.handle)).scalar_one_or_none()
    m = db.get(SpaceMember, (s.id, prof.user_id)) if prof else None
    if m is None:
        raise not_found("Member")
    if prof is not None and prof.user_id == p.id:
        raise AppError(403, "self_modification", "You cannot change your own space role or restrictions.")
    if body.role:
        m.role = body.role
    if body.restrict_hours is not None:
        m.banned_until = utcnow() + timedelta(hours=body.restrict_hours) if body.restrict_hours else None
    audit.record(db, action="space.member_update", resource_type="space", resource_id=slug, actor=p, request=request,
                 changes=body.model_dump())
    db.commit()
    return {"role": m.role, "restricted_until": m.banned_until.isoformat() if m.banned_until else None}


# ------------------------------------------------------------------ moderation hooks (used by community router)

def queue_items(db: Session) -> list[dict]:
    items: list[dict[str, Any]] = []
    for post in db.execute(select(JournalPost).where(JournalPost.status == "pending").order_by(JournalPost.created_at)).scalars():
        items.append({"kind": "journal_post", "id": str(post.id), "title": post.title, "subtitle": post.subtitle,
                      "body": "\n\n".join(b.get("text", "") for b in post.blocks if b.get("text")),
                      "blocks": post.blocks, "author": _user_label(db, post.author_id)["display_name"],
                      "ai_flags": post.ai_flags, "created_at": post.created_at.isoformat()})
    for c in db.execute(select(JournalComment).where(JournalComment.status == "pending")).scalars():
        items.append({"kind": "journal_comment", "id": str(c.id), "title": None, "body": c.body, "ai_flags": c.ai_flags,
                      "created_at": c.created_at.isoformat()})
    for m in db.execute(select(SpaceMessage).where(SpaceMessage.status == "held").order_by(SpaceMessage.id)).scalars():
        ch = db.get(Channel, m.channel_id)
        sp = db.get(Space, ch.space_id) if ch else None
        items.append({"kind": "space_message", "id": str(m.id), "title": None, "body": m.body, "ai_flags": m.ai_flags,
                      "context": {"space": sp.slug if sp else None, "channel": ch.slug if ch else None},
                      "author": _user_label(db, m.author_id)["display_name"], "created_at": m.created_at.isoformat()})
    return items


def decide(db: Session, kind: str, ident: str, decision: str, note: str, p: Principal) -> None:
    if kind == "journal_post":
        post = db.get(JournalPost, uuid.UUID(ident))
        if post is None:
            raise not_found("Story")
        if post.author_id == p.id:
            raise AppError(403, "conflict_of_interest", "You cannot moderate your own story.")
        if decision in ("approve", "restore"):
            on_post_approved(db, post)
            for b in post.blocks:
                if b.get("type") == "image" and b.get("media_id"):
                    a = db.get(MediaAsset, uuid.UUID(b["media_id"]))
                    if a is not None and a.status == "clean":
                        a.status, a.reviewed_by = "approved", p.id
                        a.license, a.credit = a.license or "Visitor licence grant " + CONSENT_VERSION, a.credit or "Visitor contribution"
            if post.cover_media_id:
                a = db.get(MediaAsset, post.cover_media_id)
                if a is not None and a.status == "clean":
                    a.status, a.reviewed_by = "approved", p.id
                    a.license, a.credit = a.license or "Visitor licence grant " + CONSENT_VERSION, a.credit or "Visitor contribution"
        elif decision in ("reject", "remove"):
            post.status, post.featured = ("rejected" if decision == "reject" else "removed"), False
            _in_app(db, post.author_id, "journal_decision", "Your story was not published", note or post.title,
                    f"/journal/{post.id}")
        elif decision in ("feature", "unfeature"):
            if post.status != "approved":
                raise AppError(409, "not_published", "Only published stories can be featured.")
            post.featured = decision == "feature"
        post.moderated_by, post.moderation_note = p.id, note or post.moderation_note
    elif kind == "journal_comment":
        c = db.get(JournalComment, uuid.UUID(ident))
        if c is None:
            raise not_found("Comment")
        c.status = "visible" if decision in ("approve", "restore") else "removed"
    elif kind == "space_message":
        m = db.get(SpaceMessage, int(ident))
        if m is None:
            raise not_found("Message")
        if m.author_id == p.id:
            raise AppError(403, "conflict_of_interest", "You cannot moderate your own message.")
        m.status = "visible" if decision in ("approve", "restore") else "removed"
        m.removed_by = None if m.status == "visible" else p.id
        _bump(db, m)

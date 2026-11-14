"""FastAPI dependencies for authentication, CSRF and permission checks."""
from __future__ import annotations

import hmac

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.core.db import get_db, utcnow
from app.core.errors import AppError
from app.modules.identity.models import User
from app.modules.identity.service import Principal, permissions_for, resolve_session

SESSION_COOKIE = "vt_session"
CSRF_COOKIE = "vt_csrf"
CSRF_HEADER = "x-csrf-token"
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def _token_from(request: Request) -> tuple[str | None, str]:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip(), "bearer"
    return request.cookies.get(SESSION_COOKIE), "cookie"


def optional_principal(request: Request, db: Session = Depends(get_db)) -> Principal | None:
    token, via = _token_from(request)
    if not token:
        return None
    sess = resolve_session(db, token)
    if sess is None:
        return None
    user = db.get(User, sess.user_id)
    if user is None or not user.is_active or user.deleted_at:
        return None
    # CSRF: cookie-authenticated state-changing requests must echo the per-session token.
    # Bearer tokens are not sent automatically by browsers, so they are not CSRF-prone.
    if via == "cookie" and request.method not in SAFE_METHODS:
        sent = request.headers.get(CSRF_HEADER, "")
        if not sent or not hmac.compare_digest(sent, sess.csrf_token):
            raise AppError(403, "csrf_failed", "Missing or invalid CSRF token.")
    sess.last_seen_at = utcnow()
    request.state.session_token = token
    return Principal(user=user, session=sess, permissions=permissions_for(db, user))


def current_principal(p: Principal | None = Depends(optional_principal)) -> Principal:
    if p is None:
        raise AppError(401, "unauthenticated", "Please sign in.")
    return p


def verified_principal(p: Principal = Depends(current_principal)) -> Principal:
    """Community actions require a verified email address."""
    if p.user.email_verified_at is None:
        raise AppError(403, "email_unverified", "Please verify your email address first.")
    return p


def require(*perms: str, any_of: bool = False):
    """Dependency: caller must hold the permission(s) AND have completed MFA (staff)."""

    def _dep(p: Principal = Depends(current_principal)) -> Principal:
        held = [x for x in perms if x in p.permissions]
        ok = bool(held) if any_of else len(held) == len(perms)
        if not ok:
            raise AppError(403, "forbidden", "You do not have permission to perform this action.",
                           {"required": list(perms)})
        if not p.mfa_ok:
            raise AppError(403, "mfa_required", "Multi-factor authentication is required for staff actions.")
        return p

    return _dep

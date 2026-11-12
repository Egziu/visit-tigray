from __future__ import annotations

import uuid
from datetime import timedelta
from typing import Literal

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_db, utcnow
from app.core.errors import AppError, not_found
from app.core.security import client_ip, rate_limit
from app.modules.audit import service as audit
from app.modules.identity import oidc
from app.modules.identity import service as svc
from app.modules.identity.deps import (CSRF_COOKIE, SESSION_COOKIE, current_principal, optional_principal,
                                       require)
from app.modules.identity.models import Permission, Role, RolePermission, User, UserRole
from app.modules.identity.service import Principal
from app.modules.platform.service import notify

router = APIRouter(prefix="/api", tags=["identity"])

Locale = Literal["en", "ti", "am"]


class RegisterIn(BaseModel):
    email: EmailStr
    password: str = Field(min_length=12, max_length=256)
    display_name: str = Field(min_length=2, max_length=80)
    locale: Locale = "en"
    age_confirmed_16_plus: bool


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=256)


class TokenIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)


class CodeIn(BaseModel):
    code: str = Field(min_length=6, max_length=8)


class EmailIn(BaseModel):
    email: EmailStr


class ResetIn(BaseModel):
    token: str = Field(min_length=10, max_length=200)
    password: str = Field(min_length=12, max_length=256)


def user_out(p: Principal) -> dict:
    u = p.user
    return {"id": str(u.id), "email": u.email, "display_name": u.display_name, "locale": u.locale,
            "email_verified": u.email_verified_at is not None, "is_staff": u.is_staff,
            "mfa_enabled": u.mfa_enabled, "mfa_verified": bool(p.session and p.session.mfa_verified),
            "permissions": sorted(p.permissions) if p.mfa_ok else [],
            "pending_permissions": sorted(p.permissions) if not p.mfa_ok else [],
            "roles": [r.key for r in u.roles], "csrf_token": p.session.csrf_token if p.session else None}


def _set_cookies(resp: Response, token: str, csrf: str, hours: int) -> None:
    secure = get_settings().effective_cookie_secure
    resp.set_cookie(SESSION_COOKIE, token, httponly=True, secure=secure, samesite="lax", max_age=hours * 3600, path="/")
    resp.set_cookie(CSRF_COOKIE, csrf, httponly=False, secure=secure, samesite="lax", max_age=hours * 3600, path="/")


def _send_verification(db: Session, user: User) -> None:
    raw = svc.issue_token(db, user, "verify_email", timedelta(hours=24))
    link = f"{get_settings().public_base_url}/{user.locale}/account/verify?token={raw}"
    notify(db, channel="email", recipient=user.email, template="verify_email", payload={"link": link}, user_id=user.id)


@router.post("/auth/register", status_code=201, dependencies=[Depends(rate_limit("auth"))])
def register(body: RegisterIn, request: Request, db: Session = Depends(get_db)):
    if not body.age_confirmed_16_plus:
        raise AppError(422, "age_requirement", "Community accounts are available to people aged 16 or older.")
    try:
        user = svc.create_user(db, email=body.email, password=body.password, display_name=body.display_name,
                               locale=body.locale, age_confirmed=True)
    except AppError as e:
        if e.code == "email_taken":
            # Do not reveal account existence: behave as success, but email the owner nothing new.
            return {"status": "verification_sent"}
        raise
    _send_verification(db, user)
    audit.record(db, action="account.register", resource_type="user", resource_id=user.id, actor=user, request=request)
    db.commit()
    return {"status": "verification_sent"}


@router.post("/auth/verify-email", dependencies=[Depends(rate_limit("auth"))])
def verify_email(body: TokenIn, request: Request, db: Session = Depends(get_db)):
    user = svc.consume_token(db, body.token, "verify_email")
    user.email_verified_at = user.email_verified_at or utcnow()
    audit.record(db, action="account.verify_email", resource_type="user", resource_id=user.id, actor=user, request=request)
    db.commit()
    return {"status": "verified"}


@router.post("/auth/resend-verification", status_code=202, dependencies=[Depends(rate_limit("auth"))])
def resend(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if p.user.email_verified_at is None:
        _send_verification(db, p.user)
        db.commit()
    return {"status": "accepted"}


@router.post("/auth/login", dependencies=[Depends(rate_limit("auth"))])
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    try:
        user = svc.authenticate(db, body.email, body.password)
    except AppError as e:
        audit.record(db, action="auth.login", resource_type="user", resource_id=None, actor=f"anon:{body.email[:80]}",
                     outcome="failure", changes={"reason": e.code}, request=request)
        db.commit()
        raise
    token, sess = svc.create_session(db, user, mfa_verified=False, ip=client_ip(request),
                                     user_agent=request.headers.get("user-agent"))
    audit.record(db, action="auth.login", resource_type="user", resource_id=user.id, actor=user, request=request)
    db.commit()
    s = get_settings()
    _set_cookies(response, token, sess.csrf_token, s.staff_session_ttl_hours if user.is_staff else s.session_ttl_hours)
    p = Principal(user=user, session=sess, permissions=svc.permissions_for(db, user))
    return {"user": user_out(p), "mfa_required": user.mfa_enabled,
            "mfa_setup_required": user.is_staff and not user.mfa_enabled and s.require_staff_mfa}


@router.post("/auth/mfa/verify", dependencies=[Depends(rate_limit("auth"))])
def mfa_verify(body: CodeIn, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if not p.user.mfa_enabled or not svc.verify_totp(p.user, body.code):
        audit.record(db, action="auth.mfa_verify", resource_type="user", resource_id=p.user.id, actor=p,
                     outcome="failure", request=request)
        db.commit()
        raise AppError(401, "invalid_code", "The verification code is not valid.")
    assert p.session is not None
    p.session.mfa_verified = True
    audit.record(db, action="auth.mfa_verify", resource_type="user", resource_id=p.user.id, actor=p, request=request)
    db.commit()
    return {"user": user_out(p)}


@router.post("/auth/mfa/setup")
def mfa_setup(p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if p.user.mfa_enabled and not p.mfa_ok:
        raise AppError(403, "mfa_required", "Verify your current second factor before re-enrolling.")
    secret, uri = svc.begin_totp_setup(p.user)
    p.user.mfa_enabled = False
    db.commit()
    return {"otpauth_uri": uri, "secret": secret}


@router.post("/auth/mfa/enable", dependencies=[Depends(rate_limit("auth"))])
def mfa_enable(body: CodeIn, request: Request, p: Principal = Depends(current_principal), db: Session = Depends(get_db)):
    if not svc.verify_totp(p.user, body.code):
        raise AppError(401, "invalid_code", "The verification code is not valid.")
    p.user.mfa_enabled = True
    assert p.session is not None
    p.session.mfa_verified = True
    audit.record(db, action="auth.mfa_enable", resource_type="user", resource_id=p.user.id, actor=p, request=request)
    db.commit()
    return {"user": user_out(p)}


@router.post("/auth/logout")
def logout(request: Request, response: Response, p: Principal | None = Depends(optional_principal),
           db: Session = Depends(get_db)):
    token = getattr(request.state, "session_token", None)
    if token:
        svc.revoke_session(db, token)
        db.commit()
    response.delete_cookie(SESSION_COOKIE, path="/")
    response.delete_cookie(CSRF_COOKIE, path="/")
    return {"status": "signed_out"}


@router.post("/auth/password/forgot", status_code=202, dependencies=[Depends(rate_limit("auth"))])
def forgot(body: EmailIn, db: Session = Depends(get_db)):
    user = db.execute(select(User).where(User.email == svc.normalize_email(body.email))).scalar_one_or_none()
    if user and user.is_active and user.password_hash is not None:
        raw = svc.issue_token(db, user, "reset_password", timedelta(minutes=30))
        notify(db, channel="email", recipient=user.email, template="reset_password",
               payload={"link": f"{get_settings().public_base_url}/{user.locale}/account/reset?token={raw}"},
               user_id=user.id)
        db.commit()
    return {"status": "accepted"}  # identical response whether or not the account exists


@router.post("/auth/password/reset", dependencies=[Depends(rate_limit("auth"))])
def reset(body: ResetIn, request: Request, db: Session = Depends(get_db)):
    user = svc.consume_token(db, body.token, "reset_password")
    svc.validate_password(body.password, user.email)
    user.password_hash = svc.hash_password(body.password)
    user.failed_logins, user.locked_until = 0, None
    svc.revoke_all_sessions(db, user.id)
    audit.record(db, action="auth.password_reset", resource_type="user", resource_id=user.id, actor=user, request=request)
    db.commit()
    return {"status": "password_changed"}


@router.get("/auth/oidc/login")
def oidc_login(db: Session = Depends(get_db)):
    url = oidc.start_login(db)
    db.commit()
    return {"redirect_url": url}


@router.get("/auth/oidc/callback")
def oidc_callback(code: str, state: str, request: Request, db: Session = Depends(get_db)):
    claims = oidc.complete_login(db, code, state)
    s = get_settings()
    user = db.execute(select(User).where(User.oidc_issuer == s.oidc_issuer, User.oidc_subject == claims["sub"])
                      ).scalar_one_or_none()
    if user is None:
        email = claims.get("email")
        if not email or not claims.get("email_verified"):
            raise AppError(403, "oidc_email_unverified", "Your identity provider account needs a verified email.")
        user = db.execute(select(User).where(User.email == svc.normalize_email(email))).scalar_one_or_none()
        if user is None:
            user = svc.create_user(db, email=email, password=None, display_name=claims.get("name") or email.split("@")[0])
            user.email_verified_at = utcnow()
        user.oidc_issuer, user.oidc_subject = s.oidc_issuer, claims["sub"]
    token, sess = svc.create_session(db, user, mfa_verified=claims["_mfa"], method="oidc", ip=client_ip(request),
                                     user_agent=request.headers.get("user-agent"))
    audit.record(db, action="auth.login_oidc", resource_type="user", resource_id=user.id, actor=user, request=request,
                 changes={"mfa_from_idp": claims["_mfa"]})
    db.commit()
    resp = RedirectResponse(f"{s.public_base_url}/en/bureau", status_code=303)
    _set_cookies(resp, token, sess.csrf_token, s.staff_session_ttl_hours)
    return resp


@router.get("/me")
def me(p: Principal = Depends(current_principal)):
    return user_out(p)


# ------------------------------------------------------------------ staff administration

class StaffCreateIn(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=2, max_length=80)
    roles: list[str] = Field(default_factory=list, max_length=10)


class RoleAssignIn(BaseModel):
    roles: list[str] = Field(max_length=20)


class RoleIn(BaseModel):
    key: str = Field(pattern=r"^[a-z][a-z0-9_]{2,59}$")
    name: str = Field(min_length=2, max_length=120)
    description: str = Field(default="", max_length=500)
    permissions: list[str] = Field(default_factory=list)


class RolePermsIn(BaseModel):
    permissions: list[str]


@router.get("/bureau/users")
def list_staff(p: Principal = Depends(require("users.manage")), db: Session = Depends(get_db)):
    users = db.execute(select(User).where(User.is_staff.is_(True)).order_by(User.email)).scalars().all()
    return [{"id": str(u.id), "email": u.email, "display_name": u.display_name, "is_active": u.is_active,
             "mfa_enabled": u.mfa_enabled, "roles": [r.key for r in u.roles]} for u in users]


@router.post("/bureau/users", status_code=201)
def create_staff(body: StaffCreateIn, request: Request, p: Principal = Depends(require("users.manage")),
                 db: Session = Depends(get_db)):
    user = svc.create_user(db, email=body.email, password=None, display_name=body.display_name, is_staff=True)
    user.email_verified_at = utcnow()
    for r in body.roles:
        svc.assign_role(db, user, r, granted_by=p.id)
    raw = svc.issue_token(db, user, "reset_password", timedelta(hours=48))
    notify(db, channel="email", recipient=user.email, template="reset_password",
           payload={"link": f"{get_settings().public_base_url}/en/account/reset?token={raw}"}, user_id=user.id)
    audit.record(db, action="staff.create", resource_type="user", resource_id=user.id, actor=p, request=request,
                 changes={"roles": body.roles})
    db.commit()
    return {"id": str(user.id)}


@router.put("/bureau/users/{user_id}/roles")
def set_roles(user_id: uuid.UUID, body: RoleAssignIn, request: Request, p: Principal = Depends(require("users.manage")),
              db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    if user.id == p.id:
        raise AppError(403, "self_modification", "You cannot change your own roles.")
    before = sorted(r.key for r in user.roles)
    for ur in db.execute(select(UserRole).where(UserRole.user_id == user.id)).scalars():
        db.delete(ur)
    db.flush()
    for r in body.roles:
        svc.assign_role(db, user, r, granted_by=p.id)
    svc.revoke_all_sessions(db, user.id)  # privilege change => re-authenticate
    audit.record(db, action="staff.roles_change", resource_type="user", resource_id=user.id, actor=p, request=request,
                 changes={"before": before, "after": sorted(body.roles)})
    db.commit()
    return {"roles": sorted(body.roles)}


@router.post("/bureau/users/{user_id}/deactivate")
def deactivate(user_id: uuid.UUID, request: Request, p: Principal = Depends(require("users.manage")),
               db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if user is None:
        raise not_found("User")
    if user.id == p.id:
        raise AppError(403, "self_modification", "You cannot deactivate yourself.")
    user.is_active = False
    svc.revoke_all_sessions(db, user.id)
    audit.record(db, action="staff.deactivate", resource_type="user", resource_id=user.id, actor=p, request=request)
    db.commit()
    return {"status": "deactivated"}


@router.get("/bureau/roles")
def list_roles(p: Principal = Depends(require("roles.manage")), db: Session = Depends(get_db)):
    roles = db.execute(select(Role).order_by(Role.key)).scalars().all()
    perms = db.execute(select(Permission).order_by(Permission.key)).scalars().all()
    return {"roles": [{"key": r.key, "name": r.name, "is_system": r.is_system,
                       "permissions": sorted(x.key for x in r.permissions)} for r in roles],
            "permissions": [{"key": x.key, "description": x.description} for x in perms]}


@router.post("/bureau/roles", status_code=201)
def create_role(body: RoleIn, request: Request, p: Principal = Depends(require("roles.manage")),
                db: Session = Depends(get_db)):
    if db.execute(select(Role).where(Role.key == body.key)).first():
        raise AppError(409, "conflict", "Role exists")
    known = set(db.execute(select(Permission.key)).scalars())
    if unknown := set(body.permissions) - known:
        raise AppError(422, "unknown_permission", "Unknown permissions", sorted(unknown))
    role = Role(key=body.key, name=body.name, description=body.description)
    db.add(role)
    db.flush()
    for k in body.permissions:
        db.add(RolePermission(role_id=role.id, permission_key=k))
    audit.record(db, action="role.create", resource_type="role", resource_id=body.key, actor=p, request=request,
                 changes={"permissions": body.permissions})
    db.commit()
    return {"key": role.key}


@router.put("/bureau/roles/{key}/permissions")
def set_role_permissions(key: str, body: RolePermsIn, request: Request, p: Principal = Depends(require("roles.manage")),
                         db: Session = Depends(get_db)):
    role = db.execute(select(Role).where(Role.key == key)).scalar_one_or_none()
    if role is None:
        raise not_found("Role")
    known = set(db.execute(select(Permission.key)).scalars())
    if unknown := set(body.permissions) - known:
        raise AppError(422, "unknown_permission", "Unknown permissions", sorted(unknown))
    if role.key in {r.key for r in p.user.roles} and "roles.manage" not in body.permissions:
        raise AppError(403, "self_lockout", "You cannot remove roles.manage from your own role.")
    before = sorted(x.key for x in role.permissions)
    for rp in db.execute(select(RolePermission).where(RolePermission.role_id == role.id)).scalars():
        db.delete(rp)
    db.flush()
    for k in sorted(set(body.permissions)):
        db.add(RolePermission(role_id=role.id, permission_key=k))
    audit.record(db, action="role.permissions_change", resource_type="role", resource_id=key, actor=p, request=request,
                 changes={"before": before, "after": sorted(set(body.permissions))})
    db.commit()
    return {"key": key, "permissions": sorted(set(body.permissions))}

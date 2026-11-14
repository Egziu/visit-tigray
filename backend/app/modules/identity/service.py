"""Identity: accounts, Argon2id passwords, server-side sessions, TOTP MFA, one-time tokens, RBAC."""
from __future__ import annotations

import base64
import hashlib
import secrets
from dataclasses import dataclass, field
from datetime import timedelta

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import utcnow
from app.core.errors import AppError
from app.modules.identity.models import OneTimeToken, Permission, Role, RolePermission, User, UserRole, UserSession
from app.modules.identity.permissions import PERMISSIONS, ROLES

_ph = PasswordHasher()  # Argon2id, library defaults (RFC 9106 low-memory profile)
_DUMMY_HASH = _ph.hash("timing-equaliser-not-a-password")

COMMON_PASSWORDS = {"password", "password123", "123456789012", "qwertyuiopas", "visittigray", "letmein12345",
                    "iloveyou1234", "welcome12345", "administrator", "aksum1234567"}
# Bases that remain weak however many digits/symbols are appended ("password1234!").
COMMON_BASES = {"password", "passw0rd", "letmein", "welcome", "admin", "administrator", "iloveyou", "monkey",
                "dragon", "football", "sunshine", "princess", "tigray", "aksum", "mekelle", "ethiopia", "visittigray"}
MAX_FAILED_LOGINS = 5
LOCKOUT_MINUTES = 15


def sha256(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _fernet() -> Fernet:
    key = hashlib.sha256(("totp:" + get_settings().secret_key).encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


# ---------------------------------------------------------------- passwords

def validate_password(password: str, email: str) -> None:
    problems = []
    if len(password) < 12:
        problems.append("Use at least 12 characters.")
    if len(password) > 256:
        problems.append("Use at most 256 characters.")
    lowered = password.lower()
    stripped = lowered.rstrip("0123456789!@#$%^&*.?-_ ")
    if (lowered in COMMON_PASSWORDS or stripped in COMMON_BASES or len(set(password)) < 5
            or any(seq in lowered for seq in ("123456", "qwerty", "abcdef"))):
        problems.append("This password is too common or too simple.")
    local = email.split("@")[0].lower()
    if len(local) >= 4 and local in password.lower():
        problems.append("The password must not contain your email name.")
    if problems:
        raise AppError(422, "weak_password", " ".join(problems))


def hash_password(password: str) -> str:
    return _ph.hash(password)


def verify_password(stored: str | None, password: str) -> bool:
    try:
        return _ph.verify(stored or _DUMMY_HASH, password) and stored is not None
    except (VerificationError, InvalidHashError):
        return False


# ---------------------------------------------------------------- accounts

def normalize_email(email: str) -> str:
    return email.strip().lower()


def create_user(db: Session, *, email: str, password: str | None, display_name: str, locale: str = "en",
                is_staff: bool = False, age_confirmed: bool = False) -> User:
    email = normalize_email(email)
    if db.execute(select(User.id).where(User.email == email)).first():
        raise AppError(409, "email_taken", "An account with this email already exists.")
    if password is not None:
        validate_password(password, email)
    user = User(email=email, password_hash=hash_password(password) if password else None, display_name=display_name,
                locale=locale, is_staff=is_staff, age_confirmed_16_plus=age_confirmed)
    db.add(user)
    db.flush()
    return user


def authenticate(db: Session, email: str, password: str) -> User:
    user = db.execute(select(User).where(User.email == normalize_email(email))).scalar_one_or_none()
    generic = AppError(401, "invalid_credentials", "Email or password is incorrect.")
    if user is None:
        verify_password(None, password)  # equalise timing to limit account enumeration
        raise generic
    if user.locked_until and user.locked_until > utcnow():
        raise AppError(423, "account_locked", "Too many failed attempts. Try again later or reset your password.")
    if not user.is_active or user.deleted_at:
        verify_password(None, password)
        raise generic
    if not verify_password(user.password_hash, password):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILED_LOGINS:
            user.locked_until = utcnow() + timedelta(minutes=LOCKOUT_MINUTES)
            user.failed_logins = 0
        db.commit()
        raise generic
    user.failed_logins = 0
    user.locked_until = None
    if _ph.check_needs_rehash(user.password_hash or ""):
        user.password_hash = hash_password(password)
    return user


# ---------------------------------------------------------------- sessions

def create_session(db: Session, user: User, *, mfa_verified: bool, method: str = "password", ip: str | None = None,
                   user_agent: str | None = None) -> tuple[str, UserSession]:
    s = get_settings()
    token = secrets.token_urlsafe(32)
    ttl = s.staff_session_ttl_hours if user.is_staff else s.session_ttl_hours
    sess = UserSession(token_hash=sha256(token), user_id=user.id, csrf_token=secrets.token_urlsafe(24),
                       mfa_verified=mfa_verified, auth_method=method, expires_at=utcnow() + timedelta(hours=ttl),
                       ip=ip, user_agent=(user_agent or "")[:300])
    db.add(sess)
    db.flush()
    return token, sess


def resolve_session(db: Session, token: str) -> UserSession | None:
    sess = db.get(UserSession, sha256(token))
    if sess is None or sess.revoked_at is not None or sess.expires_at <= utcnow():
        return None
    return sess


def revoke_session(db: Session, token: str) -> None:
    sess = db.get(UserSession, sha256(token))
    if sess and not sess.revoked_at:
        sess.revoked_at = utcnow()


def revoke_all_sessions(db: Session, user_id) -> None:
    db.execute(update(UserSession).where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
               .values(revoked_at=utcnow()))


# ---------------------------------------------------------------- one-time tokens

def issue_token(db: Session, user: User, purpose: str, ttl: timedelta) -> str:
    raw = secrets.token_urlsafe(32)
    db.add(OneTimeToken(user_id=user.id, purpose=purpose, token_hash=sha256(raw), expires_at=utcnow() + ttl))
    db.flush()
    return raw


def consume_token(db: Session, raw: str, purpose: str) -> User:
    tok = db.execute(select(OneTimeToken).where(OneTimeToken.token_hash == sha256(raw),
                                                OneTimeToken.purpose == purpose).with_for_update()).scalar_one_or_none()
    if tok is None or tok.used_at is not None or tok.expires_at <= utcnow():
        raise AppError(400, "invalid_token", "This link is invalid or has expired.")
    tok.used_at = utcnow()
    user = db.get(User, tok.user_id)
    assert user is not None
    return user


# ---------------------------------------------------------------- MFA (TOTP)

def begin_totp_setup(user: User) -> tuple[str, str]:
    secret = pyotp.random_base32()
    user.totp_secret_enc = _fernet().encrypt(secret.encode()).decode()
    uri = pyotp.TOTP(secret).provisioning_uri(name=user.email, issuer_name="Visit Tigray")
    return secret, uri


def verify_totp(user: User, code: str) -> bool:
    if not user.totp_secret_enc or not code or not code.isdigit():
        return False
    try:
        secret = _fernet().decrypt(user.totp_secret_enc.encode()).decode()
    except InvalidToken:
        return False
    return pyotp.TOTP(secret).verify(code, valid_window=1)


# ---------------------------------------------------------------- RBAC

@dataclass
class Principal:
    user: User
    session: UserSession | None
    permissions: set[str] = field(default_factory=set)

    @property
    def id(self):
        return self.user.id

    @property
    def mfa_ok(self) -> bool:
        if not get_settings().require_staff_mfa:
            return True
        return bool(self.session and self.session.mfa_verified)

    def has(self, perm: str) -> bool:
        return perm in self.permissions and self.mfa_ok

    def has_any_staff_permission(self) -> bool:
        return bool(self.permissions)


def permissions_for(db: Session, user: User) -> set[str]:
    if not user.is_active or user.deleted_at:
        return set()
    rows = db.execute(select(RolePermission.permission_key).join(UserRole, UserRole.role_id == RolePermission.role_id)
                      .where(UserRole.user_id == user.id)).scalars().all()
    return set(rows)


def sync_rbac_catalog(db: Session) -> None:
    """Insert missing permissions and system roles. Never removes local customisations."""
    existing = set(db.execute(select(Permission.key)).scalars())
    for key, desc in PERMISSIONS.items():
        if key not in existing:
            db.add(Permission(key=key, description=desc))
    db.flush()
    for key, (name, perms) in ROLES.items():
        role = db.execute(select(Role).where(Role.key == key)).scalar_one_or_none()
        if role is None:
            role = Role(key=key, name=name, is_system=True, description=name)
            db.add(role)
            db.flush()
            for p in perms:
                db.add(RolePermission(role_id=role.id, permission_key=p))
    db.flush()


def assign_role(db: Session, user: User, role_key: str, granted_by=None) -> None:
    role = db.execute(select(Role).where(Role.key == role_key)).scalar_one_or_none()
    if role is None:
        raise AppError(404, "not_found", f"Role {role_key} not found")
    if not db.get(UserRole, (user.id, role.id)):
        db.add(UserRole(user_id=user.id, role_id=role.id, granted_by=granted_by))
    user.is_staff = True
    db.flush()


def count_users(db: Session) -> int:
    return db.execute(select(func.count(User.id))).scalar_one()

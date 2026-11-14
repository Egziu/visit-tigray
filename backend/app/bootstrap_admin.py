"""Create the first administrator from environment variables (idempotent; never prints secrets).

BOOTSTRAP_ADMIN_EMAIL / BOOTSTRAP_ADMIN_PASSWORD. The account must enrol TOTP MFA at first sign-in
before any staff permission becomes active. Remove the variables after first use.
"""
from __future__ import annotations

import os

from sqlalchemy import select

from app.core.db import session_factory, utcnow
from app.modules.identity import service as svc
from app.modules.identity.models import User

ROLES = ("system_admin", "content_editor", "heritage_specialist", "tourism_officer", "moderator", "ai_admin",
         "auditor", "geo_officer", "knowledge_curator", "provider_verifier", "competition_admin")


def main() -> None:
    email, password = os.environ.get("BOOTSTRAP_ADMIN_EMAIL"), os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not email or not password:
        print("bootstrap_admin: variables not set; skipping")  # noqa: T201
        return
    db = session_factory()()
    svc.sync_rbac_catalog(db)
    if db.execute(select(User).where(User.email == svc.normalize_email(email))).scalar_one_or_none():
        print("bootstrap_admin: admin already exists; nothing to do")  # noqa: T201
        db.commit()
        return
    u = svc.create_user(db, email=email, password=password, display_name="Bureau Administrator")
    u.email_verified_at = utcnow()
    for r in ROLES:
        svc.assign_role(db, u, r)
    db.commit()
    print("bootstrap_admin: administrator created (MFA enrolment required at first sign-in)")  # noqa: T201


if __name__ == "__main__":
    main()

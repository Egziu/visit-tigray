"""Test harness: a throwaway PostgreSQL database (PostGIS + pgvector) migrated with Alembic.

TEST_DATABASE_ADMIN_URL must point at a server where we may CREATE/DROP DATABASE.
Every test runs against a database truncated to empty, with the RBAC catalogue re-synced.
"""
from __future__ import annotations

import os
import uuid

import email_validator
import pyotp
import pytest
from sqlalchemy import create_engine, text

ADMIN_URL = os.environ.get("TEST_DATABASE_ADMIN_URL", "postgresql+psycopg://postgres@localhost:5432/postgres")
DB_NAME = f"vt_test_{uuid.uuid4().hex[:8]}"
TEST_URL = ADMIN_URL.rsplit("/", 1)[0] + "/" + DB_NAME

os.environ.update({
    "DATABASE_URL": TEST_URL, "ENVIRONMENT": "test", "SECRET_KEY": "test-secret-key-0123456789abcdef",
    "MEDIA_ROOT": f"/tmp/vt-test-media-{DB_NAME}", "REQUIRE_STAFF_MFA": "true", "REDIS_URL": "",
    "RATE_LIMIT_AUTH": "1000", "RATE_LIMIT_WRITE": "1000", "RATE_LIMIT_AI": "1000",
    "AI_DEFAULT_MODE": "fully_local", "EMBEDDING_PROVIDER": "hashing",
})


# RFC 2606 reserves .test for testing; allow it in the test harness only.
if "test" in email_validator.SPECIAL_USE_DOMAIN_NAMES:
    email_validator.SPECIAL_USE_DOMAIN_NAMES.remove("test")


@pytest.fixture(scope="session", autouse=True)
def database():
    admin = create_engine(ADMIN_URL, isolation_level="AUTOCOMMIT")
    with admin.connect() as c:
        c.execute(text(f'CREATE DATABASE "{DB_NAME}"'))
    from alembic import command
    from alembic.config import Config

    cfg = Config(os.path.join(os.path.dirname(__file__), "..", "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(os.path.dirname(__file__), "..", "migrations"))
    command.upgrade(cfg, "head")
    yield cfg
    from app.core.db import reset_engine

    reset_engine()
    with admin.connect() as c:
        c.execute(text(f'DROP DATABASE IF EXISTS "{DB_NAME}" WITH (FORCE)'))
    admin.dispose()


@pytest.fixture(autouse=True)
def clean_db(database):
    from app.core.db import get_engine, session_factory
    from app.core.security import limiter
    from app.modules.identity.service import sync_rbac_catalog

    eng = get_engine()
    with eng.begin() as c:
        tables = c.execute(text("""SELECT tablename FROM pg_tables WHERE schemaname='public'
                                   AND tablename NOT IN ('alembic_version','spatial_ref_sys')""")).scalars().all()
        if tables:
            c.execute(text("TRUNCATE " + ", ".join(f'"{t}"' for t in tables) + " RESTART IDENTITY CASCADE"))
    limiter.reset()
    db = session_factory()()
    sync_rbac_catalog(db)
    db.commit()
    db.close()
    yield


@pytest.fixture
def db():
    from app.core.db import session_factory

    s = session_factory()()
    yield s
    s.rollback()
    s.close()


@pytest.fixture
def app():
    from app.main import app as fastapi_app

    return fastapi_app


@pytest.fixture
def client(app):
    from fastapi.testclient import TestClient

    with TestClient(app) as c:
        yield c


def make_user(db, email=None, password="Correct-Horse-Battery-9", roles=(), verified=True, mfa=True, name="Test User"):
    from app.core.db import utcnow
    from app.modules.identity import service as svc

    email = email or f"user-{uuid.uuid4().hex[:8]}@example.test"
    u = svc.create_user(db, email=email, password=password, display_name=name, age_confirmed=True)
    if verified:
        u.email_verified_at = utcnow()
    for r in roles:
        svc.assign_role(db, u, r)
    secret = None
    if mfa:
        secret, _ = svc.begin_totp_setup(u)
        u.mfa_enabled = True
    db.commit()
    return u, password, secret


def login(app, email, password, secret=None):
    """Return a TestClient signed in (and MFA-verified when a TOTP secret is given) with CSRF header set."""
    from fastapi.testclient import TestClient

    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    c.headers["x-csrf-token"] = r.json()["user"]["csrf_token"]
    if secret:
        r = c.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()})
        assert r.status_code == 200, r.text
    return c


@pytest.fixture
def staff(app, db):
    """Factory: staff(*roles) -> signed-in, MFA-verified client."""

    def _make(*roles, **kw):
        u, pw, secret = make_user(db, roles=roles, **kw)
        c = login(app, u.email, pw, secret)
        c.user = u
        return c

    return _make


@pytest.fixture
def visitor(app, db):
    def _make(verified=True, name="Visitor"):
        u, pw, _ = make_user(db, verified=verified, mfa=False, name=name)
        c = login(app, u.email, pw)
        c.user = u
        return c

    return _make

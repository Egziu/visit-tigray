from __future__ import annotations

import re

import pyotp
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from tests.conftest import login, make_user


def _outbox_link(db, email, template):
    from app.modules.platform.models import Notification

    n = db.execute(select(Notification).where(Notification.recipient == email, Notification.template == template)
                   .order_by(Notification.created_at.desc())).scalars().first()
    assert n is not None
    return re.search(r"token=([\w-]+)", n.payload["link"]).group(1)


def test_register_verify_login_logout(client, db):
    r = client.post("/api/auth/register", json={"email": "Ama@Example.test", "password": "Mountain-Coffee-2026!",
                                                "display_name": "Ama", "age_confirmed_16_plus": True})
    assert r.status_code == 201, r.text
    token = _outbox_link(db, "ama@example.test", "verify_email")
    assert client.post("/api/auth/verify-email", json={"token": token}).status_code == 200
    # tokens are single-use
    assert client.post("/api/auth/verify-email", json={"token": token}).json()["error"]["code"] == "invalid_token"
    r = client.post("/api/auth/login", json={"email": "ama@example.test", "password": "Mountain-Coffee-2026!"})
    assert r.status_code == 200
    assert "httponly" in r.headers["set-cookie"].lower()
    me = client.get("/api/me").json()
    assert me["email_verified"] and me["permissions"] == []
    # logout without CSRF header is refused (cookie auth + unsafe method)
    assert client.post("/api/auth/logout").json()["error"]["code"] == "csrf_failed"
    assert client.post("/api/auth/logout", headers={"x-csrf-token": me["csrf_token"]}).status_code == 200
    assert client.get("/api/me").status_code == 401


def test_registration_rules(client):
    weak = {"email": "x@example.test", "password": "password1234", "display_name": "Xa", "age_confirmed_16_plus": True}
    assert client.post("/api/auth/register", json=weak).json()["error"]["code"] == "weak_password"
    young = {**weak, "password": "Strong-Enough-Pass-77", "age_confirmed_16_plus": False}
    assert client.post("/api/auth/register", json=young).json()["error"]["code"] == "age_requirement"


def test_duplicate_registration_does_not_reveal_account(client, db):
    make_user(db, email="taken@example.test")
    r = client.post("/api/auth/register", json={"email": "taken@example.test", "password": "Another-Strong-Pass-1",
                                                "display_name": "Yo", "age_confirmed_16_plus": True})
    assert r.status_code == 201 and r.json() == {"status": "verification_sent"}


def test_lockout_after_failed_logins(client, db):
    u, pw, _ = make_user(db, email="lock@example.test")
    for _ in range(5):
        assert client.post("/api/auth/login", json={"email": u.email, "password": "wrong-password-xx"}).status_code == 401
    r = client.post("/api/auth/login", json={"email": u.email, "password": pw})
    assert r.status_code == 423


def test_password_reset_revokes_sessions(app, client, db):
    u, pw, _ = make_user(db, email="reset@example.test")
    old = login(app, u.email, pw)
    assert client.post("/api/auth/password/forgot", json={"email": u.email}).status_code == 202
    assert client.post("/api/auth/password/forgot", json={"email": "nobody@example.test"}).status_code == 202
    token = _outbox_link(db, u.email, "reset_password")
    r = client.post("/api/auth/password/reset", json={"token": token, "password": "Brand-New-Secret-555"})
    assert r.status_code == 200
    assert old.get("/api/me").status_code == 401
    login(app, u.email, "Brand-New-Secret-555")


def test_staff_permissions_require_mfa(app, db):
    u, pw, secret = make_user(db, roles=["system_admin"])
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": u.email, "password": pw})
    assert r.json()["mfa_required"] is True
    assert c.get("/api/bureau/users").json()["error"]["code"] == "mfa_required"
    c.headers["x-csrf-token"] = r.json()["user"]["csrf_token"]
    assert c.post("/api/auth/mfa/verify", json={"code": "000000"}).status_code == 401
    assert c.post("/api/auth/mfa/verify", json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert c.get("/api/bureau/users").status_code == 200


def test_staff_mfa_enrolment(app, db):
    u, pw, _ = make_user(db, roles=["auditor"], mfa=False)
    c = TestClient(app)
    r = c.post("/api/auth/login", json={"email": u.email, "password": pw}).json()
    assert r["mfa_setup_required"] is True
    c.headers["x-csrf-token"] = r["user"]["csrf_token"]
    secret = c.post("/api/auth/mfa/setup").json()["secret"]
    assert c.post("/api/auth/mfa/enable", json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    assert c.get("/api/bureau/audit").status_code == 200


def test_visitor_cannot_reach_bureau(visitor):
    v = visitor()
    for path in ["/api/bureau/users", "/api/bureau/roles", "/api/bureau/audit"]:
        assert v.get(path).status_code == 403


def test_roles_are_configurable_and_audited(staff, db):
    admin = staff("system_admin")
    r = admin.post("/api/bureau/roles", json={"key": "festival_editor", "name": "Festival editor",
                                              "permissions": ["events.manage"]})
    assert r.status_code == 201
    assert admin.post("/api/bureau/roles", json={"key": "bad_role", "name": "Bad",
                                                 "permissions": ["does.not.exist"]}).status_code == 422
    created = admin.post("/api/bureau/users", json={"email": "fest@example.test", "display_name": "Fest",
                                                    "roles": ["festival_editor"]})
    assert created.status_code == 201
    uid = created.json()["id"]
    assert admin.put(f"/api/bureau/users/{admin.user.id}/roles", json={"roles": []}).status_code == 403
    assert admin.put(f"/api/bureau/users/{uid}/roles", json={"roles": ["translator"]}).status_code == 200
    actions = [e["action"] for e in admin.get("/api/bureau/audit").json()["items"]]
    assert {"role.create", "staff.create", "staff.roles_change"} <= set(actions)


def test_audit_log_is_append_only_and_tamper_evident(staff, db):
    auditor = staff("auditor")
    assert auditor.get("/api/bureau/audit/verify").json()["valid"] is True
    import pytest
    from sqlalchemy.exc import DBAPIError

    with pytest.raises(DBAPIError):
        db.execute(text("UPDATE audit_events SET action='forged' WHERE seq=1"))
    db.rollback()
    with pytest.raises(DBAPIError):
        db.execute(text("DELETE FROM audit_events"))
    db.rollback()
    # A superuser bypassing the trigger is still detected by the hash chain.
    db.execute(text("ALTER TABLE audit_events DISABLE TRIGGER audit_events_append_only"))
    db.execute(text("UPDATE audit_events SET actor_label='someone-else' WHERE seq=1"))
    db.execute(text("ALTER TABLE audit_events ENABLE TRIGGER audit_events_append_only"))
    db.commit()
    assert auditor.get("/api/bureau/audit/verify").json()["valid"] is False


def test_guarded_feature_flags_need_justification(staff):
    admin = staff("system_admin")
    r = admin.put("/api/bureau/settings/feature-flags", json={"flags": {"bookings": True}, "justification": "yes"})
    assert r.status_code == 422
    r = admin.put("/api/bureau/settings/feature-flags", json={"flags": {"ai_guide": False}, "justification": ""})
    assert r.status_code == 200 and r.json()["ai_guide"] is False


def test_security_headers_and_structured_errors(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    for h in ["x-content-type-options", "content-security-policy", "x-frame-options", "referrer-policy", "x-request-id"]:
        assert h in r.headers
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
    r = client.post("/api/auth/login", json={"email": "not-an-email"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


def test_untrusted_host_rejected(app):
    c = TestClient(app, base_url="http://evil.example")
    assert c.get("/api/health").status_code == 400


def test_rate_limit_returns_429(client, monkeypatch):
    from app.core.config import get_settings

    monkeypatch.setattr(get_settings(), "rate_limit_auth", 3)
    codes = [client.post("/api/auth/password/forgot", json={"email": "a@example.test"}).status_code for _ in range(5)]
    assert codes[:3] == [202, 202, 202] and codes[-1] == 429


def test_body_size_limit(client):
    r = client.post("/api/auth/login", content=b"x" * 10, headers={"content-length": str(10**9),
                                                                    "content-type": "application/json"})
    assert r.status_code == 413

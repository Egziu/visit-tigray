"""Authorization matrix: every staff route rejects anonymous users, plain visitors and MFA-pending staff.

Routes are discovered from the application, so new staff routes are covered automatically.
"""
from __future__ import annotations

import re
import uuid

from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from tests.conftest import make_user

STAFF_PREFIXES = ("/api/bureau", "/api/judging")


def staff_routes(app):
    out = []
    for r in app.routes:
        route = getattr(r, "original_router", None)
        candidates = route.routes if route is not None else [r]
        for x in candidates:
            if isinstance(x, APIRoute) and x.path.startswith(STAFF_PREFIXES):
                for m in x.methods:
                    out.append((m, x.path))
    if not out:  # FastAPI versions that expose routes flat
        out = [(m, x.path) for x in app.router.routes if isinstance(x, APIRoute) and x.path.startswith(STAFF_PREFIXES)
               for m in x.methods]
    return sorted(set(out))


def concrete(path: str) -> str:
    def sub(m):
        name = m.group(1)
        if name in ("locale",):
            return "en"
        if name in ("kind",):
            return "memory"
        if name in ("decision", "action", "to"):
            return {"decision": "approve", "action": "publish", "to": "open"}[name]
        if name in ("slug", "key", "handle"):
            return "x-test"
        if name == "number":
            return "1"
        return str(uuid.uuid4())
    return re.sub(r"\{(\w+)\}", sub, path)


def test_matrix_covers_many_routes(app):
    assert len(staff_routes(app)) >= 60


def test_anonymous_gets_401_everywhere(app):
    c = TestClient(app)
    failures = []
    for method, path in staff_routes(app):
        r = c.request(method, concrete(path), json={})
        if r.status_code != 401:
            failures.append((method, path, r.status_code))
    assert failures == []


def test_visitor_without_permissions_gets_403_everywhere(app, db):
    u, pw, _ = make_user(db, mfa=False)
    c = TestClient(app)
    c.headers["x-csrf-token"] = c.post("/api/auth/login", json={"email": u.email, "password": pw}).json()["user"]["csrf_token"]
    failures = []
    for method, path in staff_routes(app):
        r = c.request(method, concrete(path), json={})
        if r.status_code != 403:
            failures.append((method, path, r.status_code))
    assert failures == []


def test_staff_with_pending_mfa_gets_403_everywhere(app, db):
    u, pw, _ = make_user(db, roles=["system_admin", "content_editor", "heritage_specialist", "moderator",
                                    "competition_admin", "judge", "ai_admin", "provider_verifier", "tourism_officer",
                                    "executive", "geo_officer", "translation_reviewer", "knowledge_curator",
                                    "competition_approver", "finance_officer"], mfa=True)
    c = TestClient(app)
    c.headers["x-csrf-token"] = c.post("/api/auth/login", json={"email": u.email, "password": pw}).json()["user"]["csrf_token"]
    failures = []
    for method, path in staff_routes(app):
        r = c.request(method, concrete(path), json={})
        if r.status_code != 403:
            failures.append((method, path, r.status_code, r.json().get("error", {}).get("code")))
    assert failures == []

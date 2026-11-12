"""Providers, awards, analytics and the Bureau assistant."""
from __future__ import annotations

import io
from datetime import timedelta

from app.core.db import utcnow
from tests.test_media import jpeg_with_gps, upload
from tests.test_tie import seeded  # noqa: F401

PROVIDER = {"slug": "test-guides-co", "name": "Test Guides Co (synthetic)", "type": "guide", "area": "Aksum",
            "summary_i18n": {"en": "Synthetic guide company for tests."}, "contact": {"email": "guides@example.test"}}


# ------------------------------------------------------------------ providers

def test_provider_verification_and_inquiries(visitor, staff, client, db):
    owner = visitor(name="Owner")
    assert owner.post("/api/providers", json=PROVIDER).status_code == 201
    assert client.get("/api/providers/test-guides-co").status_code == 404  # unlisted until verified
    verifier = staff("provider_verifier")
    pid = verifier.get("/api/bureau/providers").json()[0]["id"]
    r = verifier.post(f"/api/bureau/providers/{pid}/verify", json={"decision": "verify", "expires_on": "2030-01-01", "note": "checked"})
    assert r.json()["error"]["code"] == "no_request"
    owner.post("/api/providers/test-guides-co/verification", json={"licence_number": "TEST-123", "licence_authority": "Synthetic authority"})
    assert verifier.post(f"/api/bureau/providers/{pid}/verify", json={"decision": "verify", "note": "checked"}).json()["error"]["code"] == "expiry_required"
    r = verifier.post(f"/api/bureau/providers/{pid}/verify", json={"decision": "verify", "expires_on": "2030-01-01", "note": "licence checked"})
    assert r.json()["verification"]["status"] == "verified"
    listed = client.get("/api/providers?verified_only=true").json()
    assert listed[0]["slug"] == "test-guides-co" and listed[0]["verification"]["licence_authority"] == "Synthetic authority"
    traveller = visitor(name="Traveller")
    assert traveller.post("/api/providers/test-guides-co/inquiries", json={"message": "Do you guide in Tigrinya and English?"}).status_code == 201
    assert visitor(name="Stranger").get("/api/providers/test-guides-co/inquiries").status_code == 404
    inbox = owner.get("/api/providers/test-guides-co/inquiries").json()
    owner.post(f"/api/inquiries/{inbox[0]['id']}/reply", json={"reply": "Yes, both."})
    assert traveller.get("/api/me/inquiries").json()[0]["reply"] == "Yes, both."
    # contact edits after verification are visible as "changed since verification"
    owner.put("/api/providers/test-guides-co", json={**PROVIDER, "contact": {"email": "new@example.test"}})
    assert client.get("/api/providers/test-guides-co").json()["verification"]["contact_changed_since_verification"] is True


def test_bookings_disabled_by_flag(visitor):
    v = visitor()
    v.post("/api/providers", json=PROVIDER)
    r = v.post("/api/providers/test-guides-co/booking-requests")
    assert r.status_code == 403 and r.json()["error"]["code"] == "feature_disabled"


def test_verifier_cannot_verify_own_provider(staff):
    s = staff("provider_verifier")
    s.post("/api/providers", json=PROVIDER)
    pid = s.get("/api/bureau/providers").json()[0]["id"]
    s.post("/api/providers/test-guides-co/verification", json={"licence_number": "T-1", "licence_authority": "Synthetic"})
    r = s.post(f"/api/bureau/providers/{pid}/verify", json={"decision": "verify", "expires_on": "2030-01-01", "note": "self"})
    assert r.json()["error"]["code"] == "conflict_of_interest"


# ------------------------------------------------------------------ awards

COMP = {"slug": "photo-test", "title_i18n": {"en": "Photograph of the Year (synthetic test)"}, "terms_version": "v1",
        "categories": [{"key": "landscape", "name_i18n": {"en": "Landscape"},
                        "rubric": [{"key": "craft", "label": "Craft", "weight": 0.6, "max": 10},
                                   {"key": "story", "label": "Story", "weight": 0.4, "max": 10}]}], "is_synthetic": True}


def _open_competition(staff):
    admin, legal, bureau, finance = staff("competition_admin"), staff("competition_approver"), \
        staff("competition_approver"), staff("finance_officer")
    sysadmin = staff("system_admin")
    now = utcnow()
    body = {**COMP, "opens_at": (now - timedelta(days=1)).isoformat(), "closes_at": (now + timedelta(days=10)).isoformat()}
    assert admin.post("/api/bureau/competitions", json=body).status_code == 201
    r = admin.post("/api/bureau/competitions/photo-test/status/open")
    assert r.json()["error"]["code"] == "gates_incomplete"
    assert set(r.json()["error"]["details"]) >= {"legal_terms_approved", "funding_confirmed", "bureau_authorized",
                                                   "feature_flag_competitions_live"}
    legal.post("/api/bureau/competitions/photo-test/gates", json={"gate": "legal_terms", "reference": "Legal memo TEST-1"})
    same = legal.post("/api/bureau/competitions/photo-test/gates", json={"gate": "bureau_authorization", "reference": "Letter TEST-2"})
    assert same.json()["error"]["code"] == "four_eyes"
    bureau.post("/api/bureau/competitions/photo-test/gates", json={"gate": "bureau_authorization", "reference": "Letter TEST-2"})
    finance.post("/api/bureau/competitions/photo-test/gates", json={"gate": "funding", "reference": "Sponsor agreement TEST-3"})
    finance.post("/api/bureau/competitions/photo-test/sponsors", json={"name": "Synthetic sponsor", "contribution": "Certificates",
                                                                      "agreement_ref": "TEST-3"})
    assert admin.post("/api/bureau/competitions/photo-test/status/open").json()["error"]["details"] == ["feature_flag_competitions_live"]
    sysadmin.put("/api/bureau/settings/feature-flags", json={"flags": {"competitions_live": True},
                                                             "justification": "Synthetic test: all approvals recorded in the gates above (TEST-1..3)."})
    assert admin.post("/api/bureau/competitions/photo-test/status/open").json()["status"] == "open"
    return admin, legal, bureau


def test_competition_full_governed_lifecycle(staff, visitor, client, db):
    assert client.get("/api/competitions").json()["items"] == []
    admin, approver_a, approver_b = _open_competition(staff)
    entrant = visitor(name="Entrant")
    photo = upload(entrant, jpeg_with_gps(), purpose="competition").json()
    e = entrant.post("/api/competitions/photo-test/entries", json={
        "category_key": "landscape", "title": "Cliffs at dusk", "statement": "An original photograph I took on my "
        "journey; it shows the evening light on sandstone.", "media_id": photo["id"], "rights_confirmed": True,
        "accept_terms_version": "v1"})
    assert e.status_code == 201, e.text
    eid = e.json()["id"]
    dup = entrant.post("/api/competitions/photo-test/entries", json={
        "category_key": "landscape", "title": "Again", "statement": "Another original photograph that I took myself on the trip.",
        "media_id": photo["id"], "rights_confirmed": True, "accept_terms_version": "v1"})
    assert dup.json()["error"]["code"] == "entry_limit"
    # A second entrant re-submits the same image -> integrity flag for humans
    thief = visitor(name="Copier")
    stolen = upload(thief, jpeg_with_gps(), purpose="competition").json()
    thief.post("/api/competitions/photo-test/entries", json={
        "category_key": "landscape", "title": "Copy", "statement": "An original photograph I took on my journey; it "
        "shows the evening light on sandstone.", "media_id": stolen["id"], "rights_confirmed": True, "accept_terms_version": "v1"})
    entries = {x["title"]: x for x in admin.get("/api/bureau/competitions/photo-test/entries").json()}
    assert {f["type"] for f in entries["Copy"]["integrity_flags"]} >= {"duplicate_image", "text_overlap"}
    admin.post(f"/api/bureau/competitions/photo-test/entries/{eid}/status", json={"status": "eligible", "note": "integrity reviewed"})
    # judging with COI + anonymity
    judge = staff("judge")
    admin.post("/api/bureau/competitions/photo-test/judges", json={"user_id": str(judge.user.id)})
    admin.post("/api/bureau/competitions/photo-test/status/judging")
    assert judge.get("/api/judging/photo-test/entries").json()["error"]["code"] == "coi_required"
    judge.post("/api/judging/photo-test/conflicts", json={"statement": "No conflicts with any entrant."})
    listing = judge.get("/api/judging/photo-test/entries").json()
    assert listing[0]["id"] == eid and "entrant" not in listing[0]
    bad = judge.put(f"/api/judging/photo-test/entries/{eid}/score", json={"scores": {"craft": 11, "story": 5}})
    assert bad.json()["error"]["code"] == "score_out_of_range"
    assert judge.put(f"/api/judging/photo-test/entries/{eid}/score", json={"scores": {"craft": 8, "story": 5}}).json()["weighted_total"] == 0.68
    # staff and judges cannot enter
    late = judge.post("/api/competitions/photo-test/entries", json={
        "category_key": "landscape", "title": "Judge entry", "statement": "x" * 40, "rights_confirmed": True,
        "accept_terms_version": "v1"})
    assert late.status_code in (403, 409)
    # winner: even a person holding BOTH proposer and approver roles cannot approve their own proposal
    both = staff("competition_admin", "competition_approver")
    prop = both.post("/api/bureau/competitions/photo-test/winners", json={"category_key": "landscape", "entry_id": eid,
                                                                         "rationale": "Highest weighted score"}).json()
    assert both.post(f"/api/bureau/competitions/photo-test/winners/{prop['id']}/decision",
                     json={"decision": "approve", "note": "self"}).json()["error"]["code"] == "four_eyes"
    assert admin.post("/api/bureau/competitions/photo-test/publish-results").json()["error"]["code"] == "no_approved_winners"
    assert approver_a.post(f"/api/bureau/competitions/photo-test/winners/{prop['id']}/decision",
                           json={"decision": "approve", "note": "Verified"}).json()["status"] == "approved"
    assert admin.post("/api/bureau/competitions/photo-test/publish-results").json()["status"] == "results"
    res = client.get("/api/competitions/photo-test/results").json()
    assert res["winners"][0]["title"] == "Cliffs at dusk"
    cert = entrant.get(f"/api/competitions/photo-test/certificates/{eid}")
    assert cert.status_code == 200 and cert.content.startswith(b"%PDF")
    assert thief.get(f"/api/competitions/photo-test/certificates/{eid}").status_code == 404


# ------------------------------------------------------------------ analytics & assistant

def test_analytics_are_privacy_conscious_and_exportable(staff, client, db, seeded):  # noqa: F811
    client.post("/api/analytics/events", json={"event_type": "search", "term": "call me 0911223344", "consent": True})
    client.post("/api/analytics/events", json={"event_type": "search", "term": "Aksum", "consent": True})
    client.post("/api/analytics/events", json={"event_type": "page_view", "consent": False})
    client.get("/api/destinations/aksum")
    client.post("/api/planner/plan", json={"days": 1})
    from app.modules.analytics.models import AnalyticsEvent
    rows = db.query(AnalyticsEvent).all()
    assert {r.term for r in rows if r.event_type == "search"} == {None, "aksum"}  # number-bearing term dropped
    assert len([r for r in rows if r.event_type == "page_view"]) == 0  # no consent, not stored
    cols = set(AnalyticsEvent.__table__.columns.keys())
    assert not cols & {"user_id", "ip", "session_id", "user_agent"}
    officer = staff("tourism_officer")
    officer.post("/api/bureau/analytics/measurements", json={
        "period_start": (utcnow().date() - timedelta(days=10)).isoformat(), "period_end": utcnow().date().isoformat(),
        "metric": "visitors", "value": 10,
        "source": "Synthetic test register"})
    s = officer.get("/api/bureau/analytics/summary").json()
    assert s["website_engagement"]["by_event_type"]["destination_view"] == 1
    assert s["website_engagement"]["top_search_terms"] == []  # k-anonymity threshold (>=3)
    assert s["forecasts"]["items"] == [] and "not tourism arrivals" in s["notice"]
    assert s["measured_tourism"]["items"][0]["source"] == "Synthetic test register"
    exporter = staff("executive")  # analytics.view + reports.export
    csv_r = exporter.get("/api/bureau/analytics/export?format=csv")
    assert csv_r.status_code == 200 and csv_r.text.startswith("# Visit Tigray report")
    xlsx = exporter.get("/api/bureau/analytics/export?format=xlsx")
    from openpyxl import load_workbook
    assert "Visit Tigray report" in load_workbook(io.BytesIO(xlsx.content)).active["A1"].value
    assert exporter.get("/api/bureau/analytics/export?format=pdf").content.startswith(b"%PDF")
    assert officer.get("/api/bureau/analytics/export").status_code == 403  # no reports.export
    r = exporter.post("/api/bureau/analytics/send", json={"channel": "telegram", "recipient": "-100123"})
    assert r.json()["error"]["code"] == "channel_not_permitted"  # chat not allow-listed


def test_bureau_assistant_respects_permissions_and_cannot_write(staff, db, seeded):  # noqa: F811
    officer = staff("tourism_officer")
    a = officer.post("/api/bureau/assistant/ask", json={"question": "Which destinations have missing or outdated information?"}).json()
    assert a["intent"] == "freshness" and a["draft"] is True and "aksum" in a["answer"]
    s = officer.post("/api/bureau/assistant/ask", json={"question": "Summarise tourism activity this month"}).json()
    assert s["intent"] == "summary" and s["generated_by"] == "deterministic"
    m = officer.post("/api/bureau/assistant/ask", json={"question": "How many stories are pending moderation?"})
    assert m.status_code == 403  # tourism officers lack community.moderate
    from app.modules.assistant.router import router as assistant_router
    assert {r.methods.pop() for r in assistant_router.routes} == {"POST"} and len(assistant_router.routes) == 1
    assert staff("translator").post("/api/bureau/assistant/ask", json={"question": "summary"}).status_code == 403


def test_job_queue_idempotency_and_retry(db):
    from app.modules.platform.models import Job
    from app.modules.platform.service import HANDLERS, enqueue, run_due_jobs

    calls = []

    def flaky(_db, payload):
        calls.append(payload)
        if len(calls) == 1:
            raise RuntimeError("transient")

    HANDLERS["test_flaky"] = flaky
    assert enqueue(db, "test_flaky", {"n": 1}, idempotency_key="k1") is not None
    assert enqueue(db, "test_flaky", {"n": 1}, idempotency_key="k1") is None  # duplicate key: no second job
    db.commit()
    run_due_jobs(db)
    job = db.query(Job).filter_by(idempotency_key="k1").one()
    assert job.status == "failed" and job.attempts == 1
    job.run_after = utcnow() - timedelta(seconds=1)
    db.commit()
    run_due_jobs(db)
    db.refresh(job)
    assert job.status == "done" and len(calls) == 2


def test_worker_periodic_housekeeping(db):
    from app.worker import periodic
    out = periodic(db)
    assert set(out) == {"published", "expired_conversations", "expired_sessions"}


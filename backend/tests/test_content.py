from __future__ import annotations

from datetime import date, timedelta

from app.core.db import utcnow


def make_destination(editor, slug="aksum-test", name="Aksum (test)", category="history", publish_with=None,
                     lat=14.13, lng=38.72, sensitivity="public", geo=None):
    if category:
        editor.post("/api/bureau/categories", json={"slug": category, "name_i18n": {"en": category.title()}})
    r = editor.post("/api/bureau/destinations", json={
        "slug": slug, "category_slug": category, "interests": ["history"], "area": "Central (test)",
        "en": {"name": name, "summary": "Synthetic test summary.", "body": "Synthetic body."}})
    assert r.status_code == 201, r.text
    did = r.json()["id"]
    if geo is not None:
        assert geo.put(f"/api/bureau/destinations/{did}/geo", json={"lat": lat, "lng": lng, "sensitivity": sensitivity}).status_code == 200
    if publish_with is not None:
        assert publish_with.post(f"/api/bureau/destinations/{did}/publish", json={}).status_code == 200
    return did


def test_draft_is_never_public_until_published(staff, client):
    editor = staff("content_editor")
    did = make_destination(editor)
    assert client.get("/api/destinations/aksum-test").status_code == 404
    assert client.get("/api/destinations").json()["items"] == []
    assert editor.post(f"/api/bureau/destinations/{did}/publish", json={"note": "first"}).status_code == 200
    d = client.get("/api/destinations/aksum-test").json()
    assert d["name"] == "Aksum (test)" and d["translation_status"] == "draft"
    # Unknown operational facts stay unknown
    assert d["visit_duration_minutes"] is None and d["permit_required"] == "unknown"
    assert d["is_stale"] is True  # never verified
    # Editing a published destination does not change the live version until republished
    editor.put(f"/api/bureau/destinations/{did}/translations/en", json={"name": "Aksum renamed", "summary": "New."})
    assert client.get("/api/destinations/aksum-test").json()["name"] == "Aksum (test)"
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    assert client.get("/api/destinations/aksum-test").json()["name"] == "Aksum renamed"


def test_publish_requires_permission(staff):
    translator = staff("translator")
    editor = staff("content_editor")
    did = make_destination(editor)
    assert translator.post(f"/api/bureau/destinations/{did}/publish", json={}).status_code == 403
    officer = staff("tourism_officer")  # can edit but not publish
    assert officer.post(f"/api/bureau/destinations/{did}/publish", json={}).status_code == 403


def test_rollback_restores_previous_revision(staff, client):
    editor = staff("content_editor")
    did = make_destination(editor, publish_with=editor)
    editor.put(f"/api/bureau/destinations/{did}/translations/en", json={"name": "Wrong name", "summary": "Oops."})
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    assert client.get("/api/destinations/aksum-test").json()["name"] == "Wrong name"
    revs = editor.get(f"/api/bureau/destinations/{did}/revisions").json()
    assert [r["number"] for r in revs] == [2, 1]
    diff = editor.get(f"/api/bureau/destinations/{did}/revisions/diff?a=1&b=2").json()["diff"]
    assert any("Wrong name" in line for line in diff)
    assert editor.post(f"/api/bureau/destinations/{did}/rollback/1").status_code == 200
    assert client.get("/api/destinations/aksum-test").json()["name"] == "Aksum (test)"


def test_editor_created_category_without_code_change(staff, client):
    editor = staff("content_editor")
    r = editor.post("/api/bureau/categories", json={"slug": "coffee-ceremony", "name_i18n": {"en": "Coffee", "ti": "ቡን"}})
    assert r.status_code == 201
    cats = client.get("/api/categories?locale=ti").json()
    assert any(c["slug"] == "coffee-ceremony" and c["name"] == "ቡን" for c in cats)
    make_destination(editor, slug="cafe-test", name="Café test", category="crafts", publish_with=editor)
    assert len(client.get("/api/destinations?category=crafts").json()["items"]) == 1
    assert staff("translator").post("/api/bureau/categories", json={"slug": "x-y", "name_i18n": {"en": "X"}}).status_code == 403


def test_sensitive_coordinates_are_coarsened_for_public(staff, client):
    editor = staff("content_editor")
    geo = staff("geo_officer")
    did = make_destination(editor, slug="sacred-test", geo=geo, lat=13.98765, lng=39.39876, sensitivity="coarse")
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    pub = client.get("/api/destinations/sacred-test").json()
    assert pub["coordinates"] == {"lat": 14.0, "lng": 39.4, "precision": "approximate"}
    assert "precise_coordinates" not in pub
    assert geo.get("/api/destinations/sacred-test").json()["precise_coordinates"]["lat"] == 13.98765
    # editors without geo.manage cannot move coordinates
    assert editor.put(f"/api/bureau/destinations/{did}/geo", json={"lat": 1, "lng": 1, "sensitivity": "public"}).status_code == 403
    geo.put(f"/api/bureau/destinations/{did}/geo", json={"lat": 13.9, "lng": 39.3, "sensitivity": "hidden"})
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    assert client.get("/api/destinations/sacred-test").json()["coordinates"] is None


def test_machine_translation_never_shown_as_reviewed_and_four_eyes(staff, client):
    editor = staff("content_editor")
    did = make_destination(editor, publish_with=None)
    tr = staff("translation_reviewer")
    tr.put(f"/api/bureau/destinations/{did}/translations/ti", json={"name": "ኣክሱም", "summary": "ፈተነ", "machine_generated": True})
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    d = client.get("/api/destinations/aksum-test?locale=ti").json()
    assert d["locale"] == "ti" and d["translation_status"] == "machine"
    # the translator cannot approve their own work
    assert tr.post(f"/api/bureau/destinations/{did}/translations/ti/approve").json()["error"]["code"] == "four_eyes"
    other = staff("translation_reviewer")
    assert other.post(f"/api/bureau/destinations/{did}/translations/ti/approve").status_code == 200
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    assert client.get("/api/destinations/aksum-test?locale=ti").json()["translation_status"] == "reviewed"
    # amharic missing -> English fallback, flagged
    am = client.get("/api/destinations/aksum-test?locale=am").json()
    assert am["locale"] == "en" and am["requested_locale"] == "am"
    missing = editor.get("/api/bureau/translations/missing").json()
    assert missing[0]["missing"] == ["am"]


def test_cross_lingual_search_via_aliases_and_transliteration(staff, client):
    editor = staff("content_editor")
    did = make_destination(editor, name="Aksum")
    editor.put(f"/api/bureau/destinations/{did}/translations/ti", json={"name": "ኣክሱም", "summary": "x"})
    editor.post(f"/api/bureau/destinations/{did}/aliases", json={"name": "Axum", "kind": "variant"})
    editor.post(f"/api/bureau/destinations/{did}/publish", json={})
    for q in ["aksum", "Axum", "ኣክሱም", "አክሱም"]:  # አ/ኣ homophone folding
        items = client.get("/api/destinations", params={"q": q}).json()["items"]
        assert [i["slug"] for i in items] == ["aksum-test"], q
    assert client.get("/api/destinations", params={"q": "zzzz-nothing"}).json()["items"] == []


def test_archive_is_immediate_takedown(staff, client):
    editor = staff("content_editor")
    did = make_destination(editor, publish_with=editor)
    assert client.get("/api/destinations/aksum-test").status_code == 200
    editor.post(f"/api/bureau/destinations/{did}/archive")
    assert client.get("/api/destinations/aksum-test").status_code == 404


def test_scheduled_publication(staff, client, db):
    from app.modules.content.models import Destination
    from app.modules.content.service import publish_due

    editor = staff("content_editor")
    did = make_destination(editor)
    when = (utcnow() + timedelta(hours=1)).isoformat()
    assert editor.post(f"/api/bureau/destinations/{did}/publish", json={"publish_at": when}).json()["status"] == "scheduled"
    assert client.get("/api/destinations/aksum-test").status_code == 404
    d = db.get(Destination, did)
    d.publish_at = utcnow() - timedelta(minutes=1)
    db.commit()
    assert publish_due(db) == 1
    db.commit()
    assert client.get("/api/destinations/aksum-test").status_code == 200


def test_advisories_publish_and_scope(staff, client):
    officer = staff("tourism_officer")
    editor = staff("content_editor")
    did = make_destination(editor, publish_with=editor)
    r = officer.post("/api/bureau/advisories", json={
        "title_i18n": {"en": "Synthetic test advisory"}, "body_i18n": {"en": "Test only."},
        "level": "travel_not_advised", "destination_ids": [did], "issuing_authority": "Test authority (synthetic)"})
    aid = r.json()["id"]
    assert client.get("/api/advisories").json() == []  # drafts invisible
    officer.post(f"/api/bureau/advisories/{aid}/publish")
    assert client.get("/api/destinations/aksum-test").json()["advisory_level"] == "travel_not_advised"
    assert staff("translator").post("/api/bureau/advisories", json={}).status_code in (403, 422)
    officer.post(f"/api/bureau/advisories/{aid}/withdraw")
    assert client.get("/api/destinations/aksum-test").json()["advisory_level"] is None


def test_freshness_report_flags_unknowns(staff):
    editor = staff("content_editor")
    did = make_destination(editor)
    reasons = editor.get("/api/bureau/content/freshness").json()[0]["reasons"]
    assert {"never_verified", "no_sources", "duration_unknown", "accessibility_unknown"} <= set(reasons)
    editor.patch(f"/api/bureau/destinations/{did}", json={
        "verified": True, "visit_duration_minutes": 120, "accessibility": {"step_free": "no"},
        "sources": [{"title": "UNESCO World Heritage List: Aksum", "url": "https://whc.unesco.org/en/list/15"}],
        "review_due": (date.today() - timedelta(days=1)).isoformat()})
    assert editor.get("/api/bureau/content/freshness").json()[0]["reasons"] == ["review_overdue"]


def test_events_with_ethiopian_dates(staff, client):
    officer = staff("tourism_officer")
    r = officer.post("/api/bureau/events", json={
        "slug": "meskel-test", "title_i18n": {"en": "Meskel (test entry)"}, "starts_on": "2024-09-27", "publish": True})
    assert r.status_code == 201
    ev = client.get("/api/events?locale=en").json()[0]
    assert ev["ethiopian_date"] == "Meskerem 17, 2017 E.C."
    conv = client.get("/api/calendar/convert?gregorian=2024-09-11&locale=ti").json()
    assert conv["ethiopian"] == {"year": 2017, "month": 1, "day": 1}
    assert client.get("/api/calendar/convert?eth_year=2016&eth_month=13&eth_day=7").status_code == 422

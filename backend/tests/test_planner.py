from __future__ import annotations

import pytest
from sqlalchemy import select

from tests.test_tie import seeded  # noqa: F401  (fixture)


def plan(client, **kw):
    r = client.post("/api/planner/plan", json={"days": 3, "interests": ["history"], **kw})
    assert r.status_code == 200, r.text
    return r.json()


def test_deterministic_plan_states_unknowns(client, seeded):  # noqa: F811
    p = plan(client)
    assert p["mode"] == "operational" and "not a travel clearance" in p["notice"]
    stops = [s for d in p["days"] for s in d["stops"]]
    assert stops and {s["slug"] for s in stops} <= {"aksum", "gheralta", "mekelle", "wukro", "yeha", "adwa"}
    assert stops[0]["reasons"][0].startswith("Matches your interests")
    legs = [s["travel_from_previous"] for s in stops if s["travel_from_previous"]]
    assert legs and all(not t["verified"] and t["duration_minutes"] is None and "Straight-line" in t["basis"] for t in legs)
    assert any("Visit duration unknown" in u for d in p["days"] for u in d["unknowns"])
    assert p["costs"].startswith("unknown") and p["weather"] == "not_considered"


def test_verified_segment_is_used(client, staff, seeded, db):  # noqa: F811
    from app.modules.content.models import Destination
    ids = {d.slug: str(d.id) for d in db.execute(select(Destination)).scalars()}
    geo = staff("geo_officer")
    assert geo.post("/api/bureau/route-segments", json={"from_id": ids["aksum"], "to_id": ids["adwa"], "distance_km": 50,
                                                        "duration_minutes": 70, "source": "Synthetic test survey"}).status_code == 201
    p = plan(client, days=1, pace="full", start_slug="aksum")
    legs = {s["slug"]: s["travel_from_previous"] for s in p["days"][0]["stops"]}
    assert legs["adwa"]["verified"] is True and legs["adwa"]["duration_minutes"] == 70
    assert "Synthetic test survey" in legs["adwa"]["basis"]


def test_accessibility_unknown_is_excluded_not_assumed(client, seeded):  # noqa: F811
    p = plan(client, accessibility={"step_free_required": True})
    assert all(not d["stops"] for d in p["days"])
    assert all(e["reason"] == "Step-free access unknown" for e in p["excluded"])


def test_advisories_disable_routing(client, staff, seeded, db):  # noqa: F811
    from app.modules.content.models import Destination
    officer = staff("tourism_officer")
    aksum = db.execute(select(Destination).where(Destination.slug == "aksum")).scalar_one()
    a = officer.post("/api/bureau/advisories", json={"title_i18n": {"en": "Synthetic"}, "body_i18n": {"en": "Test"},
                                                     "level": "travel_not_advised", "destination_ids": [str(aksum.id)],
                                                     "issuing_authority": "Synthetic test authority"}).json()
    officer.post(f"/api/bureau/advisories/{a['id']}/publish")
    p = plan(client)
    assert "aksum" not in {s["slug"] for d in p["days"] for s in d["stops"]}
    assert {"slug": "aksum", "name": "Aksum"} in p["virtual_alternatives"]
    region = officer.post("/api/bureau/advisories", json={"title_i18n": {"en": "Synthetic"}, "body_i18n": {"en": "Test"},
                                                          "level": "travel_not_advised", "region_wide": True,
                                                          "issuing_authority": "Synthetic test authority"}).json()
    officer.post(f"/api/bureau/advisories/{region['id']}/publish")
    p = plan(client)
    assert p["mode"] == "virtual" and p["days"] == [] and p["virtual_alternatives"]


def test_saved_itinerary_lifecycle_and_object_level_auth(visitor, client, seeded):  # noqa: F811
    v = visitor()
    other = visitor(name="Other")
    assert client.post("/api/itineraries", json={"title": "Trip", "request": {"days": 2}}).status_code == 401
    it = v.post("/api/itineraries", json={"title": "History trip", "request": {"days": 2, "interests": ["history"]},
                                          "start_date": "2027-01-10"}).json()
    assert other.get(f"/api/itineraries/{it['id']}").status_code == 404
    edited = v.put(f"/api/itineraries/{it['id']}", json={"days": [["aksum", "yeha"], ["adwa"]], "note": "manual"}).json()
    assert edited["version"] == 2 and edited["plan"]["edited"] is True
    assert edited["plan"]["days"][0]["stops"][1]["travel_from_previous"]["verified"] is False
    bad = v.put(f"/api/itineraries/{it['id']}", json={"days": [["atlantis"]]})
    assert bad.status_code == 422 and bad.json()["error"]["code"] == "unknown_destinations"
    assert [x["version"] for x in v.get(f"/api/itineraries/{it['id']}/versions").json()] == [2, 1]
    share = v.post(f"/api/itineraries/{it['id']}/share").json()
    pub = client.get(f"/api/shared-itineraries/{share['token']}").json()
    assert pub["title"] == "History trip" and "owner" not in str(pub)
    v.delete(f"/api/itineraries/{it['id']}/share")
    assert client.get(f"/api/shared-itineraries/{share['token']}").status_code == 404
    ics = v.get(f"/api/itineraries/{it['id']}/ics")
    assert ics.status_code == 200 and "BEGIN:VEVENT" in ics.text and "DTSTART;VALUE=DATE:20270110" in ics.text
    assert "\r\n" in ics.text
    pdf = v.get(f"/api/itineraries/{it['id']}/pdf")
    assert pdf.status_code == 200 and pdf.content.startswith(b"%PDF")
    assert other.get(f"/api/itineraries/{it['id']}/pdf").status_code == 404


@pytest.mark.parametrize("pace,cap", [("relaxed", 2), ("balanced", 3), ("full", 4)])
def test_pace_caps_stops_per_day(client, seeded, pace, cap):  # noqa: F811
    p = plan(client, days=1, interests=[], pace=pace)
    assert len(p["days"][0]["stops"]) <= cap


def test_ai_tool_uses_same_deterministic_planner(db, seeded):  # noqa: F811
    from app.modules.tie.tools import execute
    out = execute(db, None, "en", "plan_itinerary", {"days": 2, "interests": ["history"]})
    assert out["mode"] == "operational" and len(out["days"]) == 2

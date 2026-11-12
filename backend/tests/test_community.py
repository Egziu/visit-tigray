from __future__ import annotations

import json

from tests.test_media import jpeg_with_gps, upload
from tests.test_tie import seeded  # noqa: F401


def story(**kw):
    return {"title": "Morning light at Aksum", "body": "A long and thoughtful account of learning from local people "
            "about their histories and traditions.", "consent_publish": True, "locale": "en", **kw}


def test_story_is_premoderated_and_consent_recorded(visitor, staff, client, seeded, db):  # noqa: F811
    v = visitor()
    photo = upload(v, jpeg_with_gps()).json()
    r = v.post("/api/memories", json=story(destination_slug="aksum", media_ids=[photo["id"]]))
    assert r.status_code == 201 and r.json()["status"] == "pending"
    mid = r.json()["id"]
    assert client.get("/api/memories").json()["items"] == []
    assert client.get(f"/api/memories/{mid}").status_code == 404
    assert v.get(f"/api/memories/{mid}").json()["status"] == "pending"  # author sees own pending story
    mod = staff("moderator")
    q = mod.get("/api/bureau/moderation/queue").json()
    assert q["items"][0]["id"] == mid and q["items"][0]["media"][0]["had_gps_metadata"] is True
    assert mod.post(f"/api/bureau/moderation/memory/{mid}/decision", json={"decision": "approve"}).status_code == 200
    items = client.get("/api/memories").json()["items"]
    assert items[0]["id"] == mid and items[0]["destination"]["slug"] == "aksum"
    assert client.get(items[0]["media"][0]["urls"]["md"]).status_code == 200  # media approved with the story
    from app.modules.community.models import ConsentRecord
    assert db.query(ConsentRecord).filter_by(kind="publish_memory").count() == 1


def test_consent_and_validation_required(visitor, seeded):  # noqa: F811
    v = visitor()
    assert v.post("/api/memories", json=story(consent_publish=False)).json()["error"]["code"] == "consent_required"
    assert v.post("/api/memories", json=story(destination_slug="atlantis")).json()["error"]["code"] == "unknown_destination"
    other = visitor(name="Other")
    photo = upload(other, jpeg_with_gps()).json()
    assert v.post("/api/memories", json=story(media_ids=[photo["id"]])).json()["error"]["code"] == "invalid_media"
    assert visitor(verified=False).post("/api/memories", json=story()).status_code == 403


def test_ai_flags_are_advisory_and_moderator_cannot_self_moderate(visitor, staff, seeded):  # noqa: F811
    v = visitor()
    mid = v.post("/api/memories", json=story(body="Call me on +251 91 123 4567 for a cheap discount tour, coordinates "
                                                "13.98765, 39.39876 near the church.")).json()["id"]
    mod = staff("moderator")
    item = mod.get("/api/bureau/moderation/queue").json()["items"][0]
    assert {"personal_contact_details", "spam_terms", "precise_coordinates"} <= set(item["ai_flags"])
    assert item["id"] == mid  # still pending: flags never auto-reject
    own = mod.post("/api/memories", json=story()).json()["id"]
    r = mod.post(f"/api/bureau/moderation/memory/{own}/decision", json={"decision": "approve"})
    assert r.json()["error"]["code"] == "conflict_of_interest"


def test_comments_blocks_reports_and_appeals(visitor, staff, client, seeded):  # noqa: F811
    author, reader = visitor(name="Author"), visitor(name="Reader")
    mid = author.post("/api/memories", json=story()).json()["id"]
    mod1, mod2 = staff("moderator"), staff("moderator")
    mod1.post(f"/api/bureau/moderation/memory/{mid}/decision", json={"decision": "approve"})
    assert reader.post(f"/api/memories/{mid}/comments", json={"body": "Beautiful, thank you"}).json()["status"] == "visible"
    held = reader.post(f"/api/memories/{mid}/comments", json={"body": "buy now cheap discount click here"}).json()
    assert held["status"] == "pending"
    assert len(client.get(f"/api/memories/{mid}/comments").json()) == 1
    handle = author.get("/api/me/profile").json()["handle"]
    assert author.post(f"/api/creators/{reader.get('/api/me/profile').json()['handle']}/block").json()["blocked"] is True
    assert reader.post(f"/api/memories/{mid}/comments", json={"body": "hello again"}).json()["error"]["code"] == "blocked"
    assert reader.post(f"/api/creators/{handle}/follow").status_code == 403
    assert client.post(f"/api/memories/{mid}/report", json={"reason": "copyright", "detail": "my photo"}).status_code == 201
    assert len(mod1.get("/api/bureau/moderation/queue").json()["reports"]) == 1
    mod1.post(f"/api/bureau/moderation/memory/{mid}/decision", json={"decision": "remove", "note": "copyright claim"})
    assert client.get(f"/api/memories/{mid}").status_code == 404
    ap = author.post("/api/appeals", json={"target_kind": "memory", "target_id": mid,
                                            "statement": "This is my own original photograph and story."}).json()
    assert mod1.post(f"/api/bureau/appeals/{ap['id']}/decision",
                     json={"decision": "overturn", "note": "own review"}).json()["error"]["code"] == "independent_review"
    assert mod2.post(f"/api/bureau/appeals/{ap['id']}/decision", json={"decision": "overturn", "note": "evidence ok"}).status_code == 200
    assert client.get(f"/api/memories/{mid}").status_code == 200


def test_private_profile_hides_stories(visitor, staff, client, seeded):  # noqa: F811
    v = visitor()
    mid = v.post("/api/memories", json=story()).json()["id"]
    staff("moderator").post(f"/api/bureau/moderation/memory/{mid}/decision", json={"decision": "approve"})
    v.put("/api/me/profile", json={"visibility": "private"})
    assert client.get("/api/memories").json()["items"] == []
    assert client.get(f"/api/memories/{mid}").status_code == 404


def test_export_and_delete_my_data(visitor, staff, client, seeded, db):  # noqa: F811
    v = visitor(name="Leaving User")
    photo = upload(v, jpeg_with_gps()).json()
    mid = v.post("/api/memories", json=story(media_ids=[photo["id"]])).json()["id"]
    v.post("/api/itineraries", json={"title": "My trip", "request": {"days": 1}})
    data = json.loads(v.get("/api/me/export").content)
    assert data["memories"][0]["id"] == mid and data["itineraries"][0]["title"] == "My trip"
    assert data["consents"] and "password" not in json.dumps(data)
    assert v.request("DELETE", "/api/me", json={"confirm": "DELETE", "password": "wrong"}).status_code == 401
    assert v.request("DELETE", "/api/me", json={"confirm": "DELETE", "password": "Correct-Horse-Battery-9"}).status_code == 200
    assert v.get("/api/me").status_code == 401
    from app.modules.community.models import Memory
    from app.modules.media.models import MediaAsset
    assert db.get(Memory, mid) is None and db.get(MediaAsset, photo["id"]) is None
    assert staff("system_admin").request("DELETE", "/api/me", json={"confirm": "DELETE",
                                                                    "password": "Correct-Horse-Battery-9"}).status_code == 409

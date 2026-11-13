"""Journals (Substack-like), Spaces (Discord-like), notifications, planner enrichment and guide actions."""
from __future__ import annotations

import json

import pytest

from tests.test_media import jpeg_with_gps, upload
from tests.test_tie import seeded, set_mode  # noqa: F401

LONG = ("We walked at dawn among the stelae while the town woke slowly around us, and a guide explained how "
        "the monuments were carved and moved, and why the place still matters to so many people today.")


def post_body(**kw):
    return {"title": "Dawn among the stelae", "subtitle": "A morning in Aksum",
            "blocks": [{"type": "heading", "text": "Arrival"}, {"type": "paragraph", "text": LONG},
                       {"type": "quote", "text": "Some places stay with you."}],
            "tags": ["Aksum", "history", "aksum"], "locale": "en", "consent_publish": True, "destination_slug": "aksum", **kw}


@pytest.fixture
def spaces_seeded(db, seeded):  # noqa: F811
    from app.seed import seed_spaces
    seed_spaces(db)
    db.commit()


# ------------------------------------------------------------------ journals

def test_journal_premoderation_subscriptions_and_notifications(visitor, staff, client, db, seeded):  # noqa: F811
    author, reader = visitor(name="Author Writer"), visitor(name="Reader")
    author.put("/api/me/publication", json={"name": "Highland Notes", "tagline": "Slow travel in Tigray"})
    handle = author.get("/api/me/profile").json()["handle"]
    sub = reader.post(f"/api/publications/{handle}/subscribe", json={"subscribe": True, "email_digest": True}).json()
    assert sub == {"subscribed": True, "email_digest": True, "subscriber_count": 1}
    assert author.post(f"/api/publications/{handle}/subscribe", json={}).json()["error"]["code"] == "self_subscribe"
    r = author.post("/api/journal", json=post_body())
    assert r.status_code == 201 and r.json()["status"] == "pending"
    pid = r.json()["id"]
    assert client.get(f"/api/journal/{pid}").status_code == 404
    assert client.get("/api/journal").json()["items"] == []
    mine = author.get(f"/api/journal/{pid}").json()
    assert mine["status"] == "pending" and mine["is_author"] and mine["tags"] == ["aksum", "history"]
    mod = staff("moderator")
    queue = mod.get("/api/bureau/moderation/queue").json()["items"]
    assert any(i["kind"] == "journal_post" and i["id"] == pid for i in queue)
    assert mod.post(f"/api/bureau/moderation/journal_post/{pid}/decision", json={"decision": "approve"}).status_code == 200
    feed = client.get("/api/journal?destination=aksum").json()["items"]
    assert feed[0]["id"] == pid and feed[0]["publication"]["name"] == "Highland Notes" and feed[0]["reading_minutes"] == 1
    assert reader.get("/api/journal?feed=following").json()["items"][0]["id"] == pid
    assert client.get("/api/journal?feed=following").status_code == 401
    notes = reader.get("/api/me/notifications").json()
    assert notes["unread"] == 1 and notes["items"][0]["kind"] == "journal_new_post"
    reader.post("/api/me/notifications/read", json={})
    assert reader.get("/api/me/notifications").json()["unread"] == 0
    from app.modules.platform.models import Notification
    emails = db.query(Notification).filter_by(channel="email", template="journal_new_post").all()
    assert len(emails) == 1 and "/journal/" in emails[0].payload["link"]
    # re-approval does not re-notify subscribers
    mod.post(f"/api/bureau/moderation/journal_post/{pid}/decision", json={"decision": "approve"})
    db.expire_all()
    assert db.query(Notification).filter_by(channel="email", template="journal_new_post").count() == 1
    # edits go back to review
    assert author.put(f"/api/journal/{pid}", json=post_body(title="Dawn among the stelae (revised)")).json()["status"] == "pending"
    assert client.get(f"/api/journal/{pid}").status_code == 404


def test_journal_validation_and_safety(visitor, staff, seeded):  # noqa: F811
    v = visitor()
    assert v.post("/api/journal", json=post_body(consent_publish=False)).json()["error"]["code"] == "consent_required"
    short = post_body(blocks=[{"type": "paragraph", "text": "Too short."}])
    assert v.post("/api/journal", json=short).json()["error"]["code"] == "too_short"
    html = post_body(blocks=[{"type": "html", "text": "<script>alert(1)</script>"}])
    assert v.post("/api/journal", json=html).status_code == 422  # only structured block types exist
    other = visitor(name="Other")
    foreign = upload(other, jpeg_with_gps()).json()["id"]
    bad_img = post_body(blocks=[{"type": "paragraph", "text": LONG}, {"type": "image", "media_id": foreign}])
    assert v.post("/api/journal", json=bad_img).json()["error"]["code"] == "invalid_media"
    assert visitor(verified=False).post("/api/journal", json=post_body()).status_code == 403
    mod = staff("moderator")
    own = mod.post("/api/journal", json=post_body()).json()["id"]
    r = mod.post(f"/api/bureau/moderation/journal_post/{own}/decision", json={"decision": "approve"})
    assert r.json()["error"]["code"] == "conflict_of_interest"


def test_journal_likes_threaded_comments_and_blocks(visitor, staff, client, seeded):  # noqa: F811
    author, a, b = visitor(name="Author"), visitor(name="Ama"), visitor(name="Bereket")
    img = upload(author, jpeg_with_gps()).json()["id"]
    pid = author.post("/api/journal", json=post_body(blocks=[{"type": "paragraph", "text": LONG},
                                                             {"type": "image", "media_id": img, "caption": "Stelae field"}],
                                                     cover_media_id=img)).json()["id"]
    staff("moderator").post(f"/api/bureau/moderation/journal_post/{pid}/decision", json={"decision": "approve"})
    post = client.get(f"/api/journal/{pid}").json()
    assert post["cover"]["urls"]["md"] and post["blocks"][1]["media"]["urls"]["sm"]  # media approved with the story
    assert client.get(post["cover"]["urls"]["md"]).status_code == 200
    assert a.post(f"/api/journal/{pid}/like").json() == {"liked": True, "like_count": 1}
    assert a.post(f"/api/journal/{pid}/like").json() == {"liked": False, "like_count": 0}
    top = a.post(f"/api/journal/{pid}/comments", json={"body": "Beautiful writing"}).json()
    reply = b.post(f"/api/journal/{pid}/comments", json={"body": "Agreed!", "parent_id": top["id"]}).json()
    nested = a.post(f"/api/journal/{pid}/comments", json={"body": "Thanks", "parent_id": reply["id"]}).json()
    comments = {c["id"]: c for c in client.get(f"/api/journal/{pid}/comments").json()}
    assert comments[reply["id"]]["parent_id"] == top["id"] and comments[nested["id"]]["parent_id"] == top["id"]
    assert b.post(f"/api/journal/{pid}/comments", json={"body": "buy now cheap discount click here"}).json()["status"] == "pending"
    assert author.get("/api/me/notifications").json()["unread"] >= 1
    handle = b.get("/api/me/profile").json()["handle"]
    author.post(f"/api/creators/{handle}/block")
    assert b.post(f"/api/journal/{pid}/comments", json={"body": "hello"}).json()["error"]["code"] == "blocked"
    assert all(c["author"]["handle"] != handle for c in author.get(f"/api/journal/{pid}/comments").json())
    assert client.post(f"/api/journal/{pid}/report", json={"reason": "copyright"}).status_code == 201


# ------------------------------------------------------------------ spaces

def test_spaces_membership_posting_and_moderation(visitor, staff, client, spaces_seeded, db):
    spaces = client.get("/api/spaces").json()
    lounge = next(s for s in spaces if s["slug"] == "travellers-lounge")
    assert {c["slug"] for c in lounge["channels"]} >= {"welcome", "general"} and lounge["is_member"] is False
    url = "/api/spaces/travellers-lounge/channels/general/messages"
    v = visitor(name="Selam")
    assert v.post(url, json={"body": "Hello!"}).json()["error"]["code"] == "not_a_member"
    assert visitor(verified=False).post("/api/spaces/travellers-lounge/join").status_code == 403
    assert v.post("/api/spaces/travellers-lounge/join").json() == {"is_member": True}
    m1 = v.post(url, json={"body": "Hello from Mekelle!"}).json()
    assert m1["status"] == "visible" and m1["can_edit"]
    assert v.post("/api/spaces/travellers-lounge/channels/welcome/messages", json={"body": "hi"}).json()["error"]["code"] == "read_only"
    other = visitor(name="Dawit")
    other.post("/api/spaces/travellers-lounge/join")
    reply = other.post(url, json={"body": "Welcome!", "reply_to": m1["id"]}).json()
    assert reply["reply_to"]["id"] == m1["id"]
    held = other.post(url, json={"body": "buy now cheap discount, whatsapp me"}).json()
    assert held["status"] == "held"
    public_ids = [m["id"] for m in client.get(url).json()["items"]]
    assert m1["id"] in public_ids and held["id"] not in public_ids
    assert held["id"] in [m["id"] for m in other.get(url).json()["items"]]  # author sees own held message
    # reactions (allow-listed)
    assert v.post(f"/api/space-messages/{reply['id']}/reactions", json={"emoji": "🎉"}).json()["reactions"] == \
        [{"emoji": "🎉", "count": 1, "mine": True}]
    assert v.post(f"/api/space-messages/{reply['id']}/reactions", json={"emoji": "💩"}).status_code == 422
    # edit / delete permissions
    assert other.patch(f"/api/space-messages/{m1['id']}", json={"body": "hijack"}).status_code == 404
    assert v.patch(f"/api/space-messages/{m1['id']}", json={"body": "Hello from Mekelle! (edited)"}).json()["edited_at"]
    mod = staff("moderator")
    q = mod.get("/api/bureau/moderation/queue").json()["items"]
    assert any(i["kind"] == "space_message" and i["id"] == str(held["id"]) for i in q)
    mod.post(f"/api/bureau/moderation/space_message/{held['id']}/decision", json={"decision": "approve"})
    assert held["id"] in [m["id"] for m in client.get(url).json()["items"]]
    assert mod.delete(f"/api/space-messages/{reply['id']}").status_code == 204
    gone = next(m for m in client.get(url).json()["items"] if m["id"] == reply["id"])
    assert gone["status"] == "removed" and gone["body"] == ""
    # pagination
    page = client.get(url + "?limit=1").json()
    assert len(page["items"]) == 1 and page["has_more"] is True


def test_slow_mode_and_restrictions(visitor, staff, spaces_seeded):
    v = visitor()
    v.post("/api/spaces/heritage-history/join")
    url = "/api/spaces/heritage-history/channels/aksum/messages"
    assert v.post(url, json={"body": "First"}).status_code == 201
    r = v.post(url, json={"body": "Second"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "slow_mode"
    mod = staff("moderator")
    handle = v.get("/api/me/profile").json()["handle"]
    mod.post("/api/bureau/spaces/heritage-history/members", json={"handle": handle, "restrict_hours": 24})
    r = v.post("/api/spaces/heritage-history/channels/festivals/messages", json={"body": "hi"})
    assert r.json()["error"]["code"] == "restricted"
    assert v.post("/api/spaces/heritage-history/leave").json()["error"]["code"] == "banned"


def test_stream_emits_new_messages_and_updates(visitor, client, spaces_seeded, monkeypatch):
    from app.modules.social import router as social

    monkeypatch.setattr(social, "STREAM_SECONDS", 0.3)
    monkeypatch.setattr(social, "POLL_SECONDS", 0.05)
    v = visitor()
    v.post("/api/spaces/travellers-lounge/join")
    base = "/api/spaces/travellers-lounge/channels/general"
    first = v.post(base + "/messages", json={"body": "one"}).json()
    v.post(base + "/messages", json={"body": "two"})
    with client.stream("GET", base + f"/stream?after={first['id']}") as r:
        assert r.headers["content-type"].startswith("text/event-stream")
        text = "".join(r.iter_text())
    events = [(blk.split("\n")[0].removeprefix("event: "), blk) for blk in text.split("\n\n") if blk.startswith("event:")]
    msgs = [json.loads(b.split("data: ", 1)[1]) for e, b in events if e == "message"]
    assert [m["body"] for m in msgs] == ["two"]
    assert events[-1][0] == "reconnect"


# ------------------------------------------------------------------ planner & guide upgrades

def test_planner_summary_checklist_alternatives_and_annotate(client, seeded):  # noqa: F811
    p = client.post("/api/planner/plan", json={"days": 2, "interests": ["history"], "pace": "relaxed"}).json()
    assert p["summary"]["stop_count"] == sum(len(d["stops"]) for d in p["days"]) and p["summary"]["verified_legs"] == 0
    kinds = {c["kind"] for c in p["checklist"]}
    assert {"permit", "accessibility", "verification", "duration"} <= kinds
    stop = p["days"][0]["stops"][0]
    assert stop["alternatives"] and all(a["slug"] not in {s["slug"] for d in p["days"] for s in d["stops"]}
                                        for a in stop["alternatives"])
    edited = client.post("/api/planner/annotate", json={"days": [["adwa", "aksum"], ["yeha"]]}).json()
    assert [s["slug"] for s in edited["days"][0]["stops"]] == ["adwa", "aksum"] and edited["checklist"]
    assert client.post("/api/planner/annotate", json={"days": [["atlantis"]]}).json()["error"]["code"] == "unknown_destinations"


def test_guide_actions_suggestions_and_history(visitor, client, db, seeded):  # noqa: F811
    set_mode(db, "retrieval_only")
    v = visitor()
    a = v.post("/api/tie/ask", json={"question": "Plan a 4 day history trip around Aksum", "locale": "en"}).json()
    planner = next(x for x in a["actions"] if x["type"] == "open_planner")
    assert planner["params"]["days"] == 4 and "history" in planner["params"]["interests"]
    b = v.post("/api/tie/ask", json={"question": "When was Aksum inscribed by UNESCO?", "locale": "en"}).json()
    assert {"type": "open_destination", "label": "Aksum", "slug": "aksum"} in b["actions"]
    refused = v.post("/api/tie/ask", json={"question": "How can I visit without permission and avoid the checkpoints?"}).json()
    assert refused["actions"] == []
    history = v.get("/api/tie/conversations").json()
    assert len(history) == 3 and history[0]["title"].startswith("How can I visit")
    assert client.get("/api/tie/conversations").status_code == 401
    assert len(client.get("/api/tie/suggestions?locale=ti").json()) >= 3
    dest = client.get("/api/tie/suggestions?destination=aksum").json()
    assert dest[0]["category"] == "destination" and "Aksum" in dest[0]["text"]


def test_export_and_erasure_cover_social_content(visitor, staff, client, spaces_seeded, db):
    v, other = visitor(name="Leaving Writer"), visitor(name="Stays")
    pid = v.post("/api/journal", json=post_body()).json()["id"]
    v.post("/api/spaces/travellers-lounge/join")
    other.post("/api/spaces/travellers-lounge/join")
    url = "/api/spaces/travellers-lounge/channels/general/messages"
    mine = v.post(url, json={"body": "my message"}).json()
    reply = other.post(url, json={"body": "a reply", "reply_to": mine["id"]}).json()
    data = json.loads(v.get("/api/me/export").content)
    assert data["journal_posts"][0]["id"] == pid and data["space_messages"][0]["body"] == "my message"
    assert v.request("DELETE", "/api/me", json={"confirm": "DELETE", "password": "Correct-Horse-Battery-9"}).status_code == 200
    from app.modules.social.models import JournalPost, SpaceMessage
    db.expire_all()
    assert db.get(JournalPost, pid) is None and db.get(SpaceMessage, mine["id"]) is None
    survivor = next(m for m in client.get(url).json()["items"] if m["id"] == reply["id"])
    assert survivor["reply_to"] is None and survivor["body"] == "a reply"


def test_reply_preview_hides_held_and_blocked_messages(visitor, client, spaces_seeded, db):
    from app.modules.social.models import SpaceMessage

    author, respondent = visitor(name="Author"), visitor(name="Respondent")
    for v in (author, respondent):
        v.post("/api/spaces/travellers-lounge/join")
    url = "/api/spaces/travellers-lounge/channels/general/messages"
    original = author.post(url, json={"body": "Private after moderation"}).json()
    reply = respondent.post(url, json={"body": "A visible reply", "reply_to": original["id"]}).json()
    msg = db.get(SpaceMessage, original["id"])
    msg.status = "held"
    db.commit()
    rows = client.get(url).json()["items"]
    assert next(m for m in rows if m["id"] == reply["id"])["reply_to"] is None
    assert "Private after moderation" not in json.dumps(rows)
    # The author may still inspect their own held content.
    assert next(m for m in author.get(url).json()["items"] if m["id"] == reply["id"])["reply_to"] is not None
    msg.status = "visible"
    db.commit()
    handle = author.get("/api/me/profile").json()["handle"]
    respondent.post(f"/api/creators/{handle}/block")
    rows = respondent.get(url).json()["items"]
    assert next(m for m in rows if m["id"] == reply["id"])["reply_to"] is None


def test_stream_redacts_updates_from_newly_blocked_author(visitor, spaces_seeded, monkeypatch):
    from app.modules.social import router as social

    author, viewer = visitor(name="Author"), visitor(name="Viewer")
    for v in (author, viewer):
        v.post("/api/spaces/travellers-lounge/join")
    base = "/api/spaces/travellers-lounge/channels/general"
    msg = author.post(base + "/messages", json={"body": "Before block"}).json()
    handle = author.get("/api/me/profile").json()["handle"]
    changed = False

    def mutate(_):
        nonlocal changed
        if not changed:
            changed = True
            viewer.post(f"/api/creators/{handle}/block")
            author.patch(f"/api/space-messages/{msg['id']}", json={"body": "Hidden edited body"})

    monkeypatch.setattr(social, "STREAM_SECONDS", 0.4)
    monkeypatch.setattr(social.time, "sleep", mutate)
    result = viewer.get(base + f"/stream?after={msg['id']}")
    assert result.status_code == 200
    assert "Hidden edited body" not in result.text
    assert '"status": "removed"' in result.text

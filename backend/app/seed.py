"""Development seed data. REFUSES to run outside development/test.

Everything created here is labelled ``is_synthetic=True`` ("development seed — not verified by the
Bureau") and has no verification date. It preserves the six destinations of the v0.1 prototype and
their wording, adds machine-draft Tigrinya/Amharic names (status ``machine``), festival entries,
and loads ``evals/corpus`` into the Knowledge Vault through the real ingestion pipeline.

Usage: python -m app.seed [--dev-admin EMAIL]
"""
from __future__ import annotations

import argparse
import hashlib
import re
import secrets
from pathlib import Path

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import session_factory, utcnow
from app.core.ethiopic import fold_for_search
from app.modules.content.models import Category, Destination, DestinationTranslation, Event, PlaceAlias
from app.modules.content.service import publish, set_location
from app.modules.identity import service as idsvc
from app.modules.knowledge import ingestion
from app.modules.knowledge.models import KnowledgeChunk, KnowledgeDocument

CORPUS = Path(__file__).resolve().parents[2] / "evals" / "corpus"

CATEGORIES = [
    ("history", {"en": "History", "ti": "ታሪኽ", "am": "ታሪክ"}),
    ("heritage", {"en": "Living heritage", "ti": "ሕያው ቅርሲ", "am": "ሕያው ቅርስ"}),
    ("culture", {"en": "Culture & city life", "ti": "ባህልን ህይወት ከተማን", "am": "ባህልና የከተማ ሕይወት"}),
    ("adventure", {"en": "Nature & adventure", "ti": "ተፈጥሮን ጀብዱን", "am": "ተፈጥሮና ጀብዱ"}),
]

# (slug, name, eyebrow, summary, area, lat, lng, category, highlights, custodial note, ti name, am name, sensitivity)
# Texts are the v0.1 prototype's editorial copy, preserved verbatim.
DESTINATIONS = [
    ("aksum", "Aksum", "Ancient civilization", "Where stone monuments hold the memory of a civilization.", "Aksum",
     14.122, 38.725, "history", "Ancient obelisks, archaeology and living heritage",
     "Sacred-site photography, site access and historical claims must be reviewed by custodians.", "ኣክሱም", "አክሱም",
     "public", ["Axum"]),
    ("gheralta", "Gheralta Mountains", "Rock-hewn heritage",
     "Sandstone cliffs and centuries of artistic and spiritual tradition.", "Hawzen", 13.98, 39.39, "adventure",
     "Rock-hewn churches, spectacular landscape and art",
     "Access may involve difficult terrain, religious permissions and verified local arrangements.", "ገርዓልታ", "ገርዓልታ",
     "coarse", ["Gheralta", "Geralta"]),
    ("mekelle", "Mekelle", "Creative city", "A living capital of food, conversation, culture and contemporary art.",
     "Mekelle", 13.4967, 39.4753, "culture", "Museums, cafes, craft and urban cultural experiences",
     "Operating details and visitor services require local verification.", "መቐለ", "መቀሌ", "public", ["Mekele", "Makalle"]),
    ("wukro", "Wukro", "Living traditions", "An encounter with exceptional rock-cut architectural traditions.", "Wukro",
     13.793, 39.6, "heritage", "Architecture and community-led heritage interpretation",
     "Church custodians control access and sensitive documentation.", "ውቕሮ", "ውቅሮ", "coarse", []),
    ("yeha", "Yeha", "Ancient origins", "Explore the traces of one of the region’s earliest monumental centers.", "Yeha",
     14.285, 39.019, "history", "Archaeological landscapes and early history",
     "Interpretation and visitor access should be validated by heritage authorities.", "የሓ", "የሐ", "coarse", []),
    ("adwa", "Adwa", "History and memory", "A landscape of enduring historical significance and collective remembrance.",
     "Adwa", 14.17, 38.90, "history", "Historical learning and memorial interpretation",
     "Historical narratives should be community-reviewed.", "ዓድዋ", "ዓድዋ", "public", ["Adowa"]),
]

EVENTS = [
    ("enkutatash", {"en": "Enkutatash (Ethiopian New Year)", "ti": "ርእሰ ዓመት", "am": "እንቁጣጣሽ"}, 1, 1, "festival"),
    ("meskel", {"en": "Meskel", "ti": "መስቀል", "am": "መስቀል"}, 1, 17, "festival"),
    ("timket", {"en": "Timket (Epiphany)", "ti": "ጥምቀት", "am": "ጥምቀት"}, 5, 11, "festival"),
    ("adwa-victory-day", {"en": "Adwa Victory Day", "ti": "በዓል ዓወት ዓድዋ", "am": "የዓድዋ ድል በዓል"}, 6, 23, "commemoration"),
]


def parse_front_matter(text: str) -> tuple[dict, str]:
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if not m:
        return {}, text
    meta = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


def seed_content(db: Session) -> dict[str, Destination]:
    cats = {}
    for slug, names in CATEGORIES:
        c = db.execute(select(Category).where(Category.slug == slug)).scalar_one_or_none()
        if c is None:
            c = Category(slug=slug, name_i18n=names)
            db.add(c)
            db.flush()
        cats[slug] = c
    out = {}
    for (slug, name, eyebrow, summary, area, lat, lng, cat, highlights, note, ti, am, sens, aliases) in DESTINATIONS:
        d = db.execute(select(Destination).where(Destination.slug == slug)).scalar_one_or_none()
        if d is None:
            d = Destination(slug=slug, category_id=cats[cat].id, interests=[cat], area=area, is_synthetic=True,
                            accessibility={"step_free": "unknown", "terrain": "unknown", "facilities": "unknown", "notes": ""},
                            location_sensitivity=sens)
            db.add(d)
            db.flush()
            set_location(d, lat, lng)
            d.translations.append(DestinationTranslation(destination_id=d.id, locale="en", name=name, eyebrow=eyebrow,
                                                         summary=summary, body=f"{summary}\n\nHighlights: {highlights}.",
                                                         etiquette=note, status="draft"))
            for loc, nm in (("ti", ti), ("am", am)):
                d.translations.append(DestinationTranslation(destination_id=d.id, locale=loc, name=nm, summary="",
                                                             status="machine"))
            seen: set[str] = set()
            pairs: list[tuple[str, str | None]] = [(name, "en"), (ti, "ti"), (am, "am"), *[(a, None) for a in aliases]]
            for alias, loc_ in pairs:
                norm = fold_for_search(alias)
                if norm not in seen:
                    seen.add(norm)
                    db.add(PlaceAlias(destination_id=d.id, name=alias, normalized=norm, locale=loc_,
                                      kind="official" if loc_ else "variant"))
            db.flush()
            db.refresh(d)
            publish(db, d, None, note="Development seed")
        out[slug] = d
    for slug, title, month, day, kind in EVENTS:
        if not db.execute(select(Event).where(Event.slug == slug)).first():
            db.add(Event(slug=slug, title_i18n=title, ethiopian_month=month, ethiopian_day=day, kind=kind,
                         status="published", is_synthetic=True,
                         date_note_i18n={"en": "Annual, by the Ethiopian calendar. Confirm local programmes with the Bureau."},
                         sources=[{"title": "Major festivals and the Ethiopian calendar (development seed)"}]))
    db.flush()
    return out


def seed_knowledge(db: Session, corpus: Path = CORPUS) -> int:
    count = 0
    dests = {d.slug: d.id for d in db.execute(select(Destination)).scalars()}
    for f in sorted(corpus.glob("*.md")):
        meta, body = parse_front_matter(f.read_text(encoding="utf-8"))
        if db.execute(select(KnowledgeDocument).where(KnowledgeDocument.title == meta["title"])).first():
            continue
        data = body.encode("utf-8")
        doc = KnowledgeDocument(
            title=meta["title"], author=meta.get("author"), publisher=meta.get("publisher"),
            published_on=meta.get("published_on"), original_language=meta.get("original_language", "und"),
            rights_status=meta.get("rights_status", "unknown"), license_note=meta.get("license_note"),
            url=meta.get("url"), access_classification=meta.get("access_classification", "internal"),
            custodian_approval_ref=meta.get("custodian_approval_ref"), is_synthetic=True, mime="text/markdown",
            sha256=hashlib.sha256(data).hexdigest(), verification_status="unverified",
            destination_ids=[dests[s.strip()] for s in meta.get("destinations", "").split(",") if s.strip() in dests])
        ingestion.transition(doc, "uploaded", None, "development seed")
        db.add(doc)
        db.flush()
        ingestion.process_upload(doc, data)
        doc.reviewed_at = utcnow()
        ingestion.index_document(db, doc)
        db.execute(update(KnowledgeChunk).where(KnowledgeChunk.document_id == doc.id).values(published=True))
        ingestion.transition(doc, "published", None, "development seed (bypasses four-eyes; dev only)")
        count += 1
    db.flush()
    return count


SPACES = [
    ("travellers-lounge", {"en": "Travellers' Lounge", "ti": "መዕረፊ በጻሕቲ", "am": "የተጓዦች ማረፊያ"},
     {"en": "Meet fellow travellers, share tips and plan together.", "ti": "ምስ ካልኦት በጻሕቲ ተራኸቡ።", "am": "ከሌሎች ተጓዦች ጋር ይገናኙ።"}, "🌄",
     [("welcome", {"en": "welcome", "ti": "እንቋዕ ብደሓን መጻእኩም", "am": "እንኳን ደህና መጡ"}, "announcements", 0),
      ("general", {"en": "general", "ti": "ሓፈሻዊ", "am": "አጠቃላይ"}, "text", 0),
      ("trip-planning", {"en": "trip-planning", "ti": "መደብ-ጉዕዞ", "am": "የጉዞ-እቅድ"}, "text", 0),
      ("photography", {"en": "photography", "ti": "ስእሊ", "am": "ፎቶግራፍ"}, "text", 0)]),
    ("heritage-history", {"en": "Heritage & History", "ti": "ቅርስን ታሪኽን", "am": "ቅርስና ታሪክ"},
     {"en": "Respectful, sourced conversation about Tigray's heritage.", "ti": "ብዛዕባ ቅርሲ ትግራይ ብኽብሪ ዝግበር ዘተ።",
      "am": "ስለ ትግራይ ቅርስ በአክብሮት የሚደረግ ውይይት።"}, "🏛",
     [("aksum", {"en": "aksum", "ti": "ኣክሱም", "am": "አክሱም"}, "text", 30),
      ("rock-churches", {"en": "rock-churches", "ti": "ኣብያተ-ክርስቲያናት", "am": "አብያተ-ክርስቲያናት"}, "text", 30),
      ("festivals", {"en": "festivals", "ti": "በዓላት", "am": "በዓላት"}, "text", 0)]),
    ("diaspora-connect", {"en": "Diaspora Connect", "ti": "ርክብ ዲያስፖራ", "am": "የዲያስፖራ ግንኙነት"},
     {"en": "Roots, language and memories across generations.", "ti": "ሱር፡ ቋንቋን ዝኽሪን።", "am": "ሥር፣ ቋንቋና ትዝታ።"}, "🤝",
     [("stories", {"en": "stories", "ti": "ዛንታታት", "am": "ታሪኮች"}, "text", 0),
      ("learn-tigrinya", {"en": "learn-tigrinya", "ti": "ትግርኛ-ምምሃር", "am": "ትግርኛ-መማር"}, "text", 0)]),
]


def seed_spaces(db: Session) -> int:
    from app.modules.social.models import Channel, Space

    n = 0
    for i, (slug, name, desc, icon, channels) in enumerate(SPACES):
        if db.execute(select(Space).where(Space.slug == slug)).first():
            continue
        s = Space(slug=slug, name_i18n=name, description_i18n=desc, icon=icon, sort_order=i * 10)
        db.add(s)
        db.flush()
        for j, (cslug, cname, kind, slow) in enumerate(channels):
            db.add(Channel(space_id=s.id, slug=cslug, name_i18n=cname, kind=kind, slow_mode_seconds=slow, sort_order=j * 10))
        n += 1
    db.flush()
    return n


def run(dev_admin: str | None = None, allow_staging: bool = False) -> None:  # pragma: no cover - CLI
    s = get_settings()
    if s.environment == "production" or (not s.is_dev and not (allow_staging and s.environment == "staging")):
        raise SystemExit("Refusing to seed synthetic data outside development/test "
                         "(staging requires --allow-staging; production is never allowed).")
    db = session_factory()()
    idsvc.sync_rbac_catalog(db)
    seed_content(db)
    seed_spaces(db)
    n = seed_knowledge(db)
    if dev_admin:
        pw = secrets.token_urlsafe(14)
        u = idsvc.create_user(db, email=dev_admin, password=pw + "-Aa1", display_name="Dev Admin")
        u.email_verified_at = utcnow()
        for r in ("system_admin", "content_editor", "heritage_specialist", "tourism_officer", "moderator",
                  "ai_admin", "auditor", "geo_officer", "translation_reviewer", "competition_admin", "provider_verifier"):
            idsvc.assign_role(db, u, r)
        print(f"Dev admin {dev_admin} password: {pw}-Aa1 (MFA enrolment required at first login)")
    db.commit()
    print(f"Seeded destinations/events and {n} knowledge documents (all labelled development seed).")


if __name__ == "__main__":  # pragma: no cover
    ap = argparse.ArgumentParser()
    ap.add_argument("--dev-admin", default=None)
    ap.add_argument("--allow-staging", action="store_true", help="seed a private staging preview (never production)")
    a = ap.parse_args()
    run(a.dev_admin, a.allow_staging)

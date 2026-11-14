"""TIE guide orchestrator.

screen -> retrieve (permission-filtered) -> [generate with allowlisted tools -> validate] -> fallback
Core tourism information never depends on a model: if inference is disabled, blocked or failing,
the guide answers extractively from approved sources (retrieval-only), or says it has no evidence.
"""
from __future__ import annotations

import re
import time
import uuid
from dataclasses import dataclass, field
from datetime import timedelta

from prometheus_client import Counter
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.db import utcnow
from app.core.egress import EgressBlocked
from app.core.errors import AppError
from app.core.i18n import norm_locale
from app.modules.content.models import Destination
from app.modules.knowledge.retrieval import Hit, retrieve
from app.modules.platform.service import get_setting
from app.modules.tie import context as ctx
from app.modules.tie import policy, tools
from app.modules.tie.models import Conversation, Message
from app.modules.tie.providers import ProviderError, get_chain

TIE_ANSWERS = Counter("vt_tie_answers_total", "TIE answers", ["mode", "confidence", "path"])
CONVERSATION_TTL_DAYS = 30
MIN_COVERAGE = 0.3  # share of content terms (after stopwords) a chunk must contain to count as evidence

INTRO = {"en": "Here is what approved sources say:", "ti": "ዝተረጋገጹ ምንጭታት እዚ ይብሉ፦", "am": "የተረጋገጡ ምንጮች የሚሉት ይህ ነው፦"}
FOLLOW_UPS = {
    "en": ["What etiquette should visitors know at {name}?", "What is the history of {name}?"],
    "ti": ["ኣብ {name} በጻሕቲ እንታይ ስርዓት ክፈልጡ ኣለዎም?", "ታሪኽ {name} እንታይ እዩ?"],
    "am": ["በ{name} ጎብኚዎች ምን ሥርዓት ማወቅ አለባቸው?", "የ{name} ታሪክ ምንድን ነው?"],
}


@dataclass
class Answer:
    conversation_id: uuid.UUID
    message_id: uuid.UUID
    answer: str
    confidence: str
    citations: list[dict]
    warnings: list[str] = field(default_factory=list)
    follow_up_questions: list[str] = field(default_factory=list)
    mode_used: str = "retrieval_only"
    provider: dict | None = None
    latency_ms: int = 0

    def as_dict(self) -> dict:
        return {"conversation_id": str(self.conversation_id), "message_id": str(self.message_id), "answer": self.answer,
                "confidence": self.confidence, "citations": self.citations, "warnings": self.warnings,
                "follow_up_questions": self.follow_up_questions, "mode_used": self.mode_used,
                "provider": self.provider, "latency_ms": self.latency_ms}


def effective_mode(db: Session) -> str:
    pol = get_setting(db, "ai_policy")
    mode = pol.get("mode", "fully_local")
    return mode if mode in pol.get("permitted_modes", []) else "retrieval_only"


def citation(n: int, h: Hit) -> dict:
    d = h.doc
    return {"n": n, "chunk_id": str(h.chunk_id), "document_id": d["id"], "document_title": d["title"],
            "author": d.get("author"), "publisher": d.get("publisher"), "published_on": d.get("published_on"),
            "url": d.get("url"), "excerpt": h.text[:400], "verified_at": d.get("verified_at"),
            "verification_status": d.get("verification_status"), "language": h.language,
            "is_synthetic": d.get("is_synthetic", False)}


def _first_sentences(text: str, n: int = 2, limit: int = 420) -> str:
    parts = re.split(r"(?<=[.!?።፧])\s+", text.strip())
    out = " ".join(parts[:n])
    return out if len(out) <= limit else out[:limit].rsplit(" ", 1)[0] + "…"


def extractive(hits: list[Hit], locale: str) -> tuple[str, list[int], str]:
    used = hits[:3]
    lines = [INTRO.get(locale, INTRO["en"])]
    for i, h in enumerate(used, 1):
        lines.append(f"• {_first_sentences(h.text)} [{i}]")
    top_cov = used[0].signals.get("coverage", 0) if used else 0
    return "\n".join(lines), list(range(1, len(used) + 1)), "grounded" if top_cov >= 0.5 else "partial"


def _follow_ups(db: Session, hits: list[Hit], locale: str) -> list[str]:
    """Suggest follow-ups about the first published destination the evidence is linked to."""
    from app.modules.content.service import localize_snapshot
    from app.modules.knowledge.models import KnowledgeChunk

    rows = db.execute(select(KnowledgeChunk.id, KnowledgeChunk.destination_ids)
                      .where(KnowledgeChunk.id.in_([h.chunk_id for h in hits]))).all()
    order = {h.chunk_id: i for i, h in enumerate(hits)}
    for _, dest_ids in sorted(rows, key=lambda r: order[r[0]]):
        for did in dest_ids or []:
            d = db.get(Destination, did)
            if d is not None and d.published_snapshot:
                name = localize_snapshot(d.published_snapshot, locale)["name"]
                return [t.format(name=name) for t in FOLLOW_UPS.get(locale, FOLLOW_UPS["en"])]
    return []


def _conversation(db: Session, conversation_id, principal, locale, persona, channel) -> Conversation:
    if conversation_id:
        conv = db.get(Conversation, conversation_id)
        if conv is None or (conv.owner_id and (principal is None or conv.owner_id != principal.id)) \
                or (conv.expires_at and conv.expires_at < utcnow()):
            raise AppError(404, "not_found", "Conversation not found")
        return conv
    conv = Conversation(owner_id=principal.id if principal else None, locale=locale, persona=persona, channel=channel,
                        expires_at=utcnow() + timedelta(days=CONVERSATION_TTL_DAYS))
    db.add(conv)
    db.flush()
    return conv


def ask(db: Session, *, question: str, locale: str = "en", persona: str = "storyteller", principal=None,
        conversation_id=None, destination_slug: str | None = None, channel: str = "public",
        mode_override: str | None = None) -> Answer:
    t0 = time.perf_counter()
    locale = norm_locale(locale)
    persona = persona if persona in policy.PERSONAS else policy.DEFAULT_PERSONA
    mode = mode_override or effective_mode(db)
    conv = _conversation(db, conversation_id, principal, locale, persona, channel)
    conv.updated_at = utcnow()
    history = [{"role": m.role, "content": m.content} for m in db.execute(
        select(Message).where(Message.conversation_id == conv.id).order_by(Message.created_at)).scalars()]
    db.add(Message(conversation_id=conv.id, role="user", content=question[:4000]))

    screen = policy.screen_input(question)
    warnings = list(screen.warnings)
    if screen.decision == "refuse":
        refusal = policy.REFUSALS[screen.refusal_code or "circumvention"]
        return _finish(db, conv, t0, refusal.get(locale, refusal["en"]),
                       "refused", [], warnings + [f"refused:{screen.refusal_code}"], [], mode, None, "refusal")

    pol = get_setting(db, "ai_policy")
    k = int(pol.get("max_context_chunks", 8))
    dest_ids = None
    if destination_slug:
        d = db.execute(select(Destination).where(Destination.slug == destination_slug)).scalar_one_or_none()
        dest_ids = [d.id] if d else None
    rq = policy.strip_injection(question) if screen.warnings else question
    hits = retrieve(db, rq, principal=principal, k=k, destination_ids=dest_ids, mode=mode)
    if not hits and dest_ids:
        hits = retrieve(db, rq, principal=principal, k=k, mode=mode)
    hits = [h for h in hits if h.signals.get("coverage", 0) >= MIN_COVERAGE]
    if hits and policy.operational_intent(question) and not policy.evidence_has_operational_facts([h.text for h in hits]):
        warnings.append("operational_facts_not_in_sources")
        return _finish(db, conv, t0, policy.INSUFFICIENT.get(locale, policy.INSUFFICIENT["en"]), "insufficient_evidence",
                       [], warnings, _follow_ups(db, hits, locale), mode, None, "no_operational_evidence")
    if not hits:
        return _finish(db, conv, t0, policy.INSUFFICIENT.get(locale, policy.INSUFFICIENT["en"]), "insufficient_evidence",
                       [], warnings, [], mode, None, "no_evidence")
    contested = any(h.doc.get("verification_status") == "disputed" for h in hits)
    if contested:
        warnings.append("sources_disagree")

    chain = get_chain(mode)
    if chain:
        max_tools = int(pol.get("max_tool_calls_per_turn", 3))
        for provider in chain:
            try:
                result = _generate(db, provider, question, hits, locale, persona, history, contested, mode, principal,
                                   max_tools, warnings)
            except EgressBlocked:
                warnings.append("egress_blocked")
                continue
            except (ProviderError, ValueError, tools.ToolError) as exc:
                warnings.append(f"provider_failed:{provider.name}:{type(exc).__name__}")
                continue
            validated, all_hits = result
            cites = [citation(n, all_hits[n - 1]) for n in validated.cited]
            return _finish(db, conv, t0, validated.answer, validated.confidence, cites, warnings + validated.warnings,
                           validated.follow_ups or _follow_ups(db, hits, locale), mode,
                           {"name": provider.name, "model": provider.model, "local": provider.local}, "generated")
        warnings.append("ai_unavailable_fallback_to_sources")

    text, used, conf = extractive(hits, locale)
    cites = [citation(n, hits[n - 1]) for n in used]
    return _finish(db, conv, t0, text, conf, cites, warnings, _follow_ups(db, hits, locale),
                   mode if not chain else "retrieval_only", None, "extractive")


def _generate(db, provider, question, hits, locale, persona, history, contested, mode, principal, max_tools, warnings):
    all_hits = list(hits)
    messages = ctx.build_messages(question, all_hits, locale, persona, history, tools.tools_doc(), contested)
    calls = 0
    while True:
        res = provider.chat(messages, mode=mode)
        data = policy.parse_model_json(res.text)
        if "tool" in data:
            if calls >= max_tools:
                raise ValueError("tool budget exceeded")
            calls += 1
            name = str(data.get("tool"))
            out = tools.execute(db, principal, locale, name, data.get("args"))
            if name == "search_knowledge":
                new = [h for h in out["hits"] if h.chunk_id not in {x.chunk_id for x in all_hits}]
                start = len(all_hits) + 1
                all_hits += new
                out = {"documents": [{"n": start + i, "title": h.doc["title"], "text": h.text} for i, h in enumerate(new)]}
            warnings.append(f"tool:{name}")
            messages = messages + [{"role": "assistant", "content": res.text}, ctx.tool_result_message(name, out)]
            continue
        context_text = "\n".join(h.text for h in all_hits)
        return policy.validate_output(data, len(all_hits), context_text), all_hits


def _finish(db, conv, t0, text, confidence, cites, warnings, follow_ups, mode, provider, path) -> Answer:
    latency = int((time.perf_counter() - t0) * 1000)
    msg = Message(conversation_id=conv.id, role="assistant", content=text, citations=cites, confidence=confidence,
                  mode_used=mode, provider=(provider or {}).get("name"),
                  provider_local=(provider or {}).get("local"), latency_ms=latency, warnings=warnings,
                  policy={"path": path})
    db.add(msg)
    db.flush()
    TIE_ANSWERS.labels(mode, confidence, path).inc()
    return Answer(conv.id, msg.id, text, confidence, cites, warnings, follow_ups, mode, provider, latency)


# ---------------------------------------------------------------------------------------------
# Action chips: deterministic hand-offs from the conversation to the planner and destinations.

PLAN_INTENT = re.compile(r"\b(plan|itinerary|trip|route|days? (in|around|exploring)|weekend|visit .{0,30}\d+\s*days?)\b"
                         r"|ጉዕዞ|ጉዞ|መደብ|ዕቅድ|ፕላን", re.I)
DAYS = re.compile(r"(\d{1,2})\s*(?:-|\s)?(?:days?|nights?|መዓልቲ|ቀን|ቀናት|ለይቲ|ሌሊት)", re.I)
INTEREST_WORDS = {
    "history": ("history", "historic", "ancient", "aksumite", "battle", "ታሪኽ", "ታሪክ", "ጥንታዊ"),
    "heritage": ("church", "churches", "monastery", "heritage", "rock-hewn", "stele", "ቤተ ክርስቲያን", "ገዳም", "ቅርሲ", "ቅርስ"),
    "culture": ("culture", "food", "coffee", "festival", "music", "craft", "market", "ባህሊ", "ባህል", "ቡን", "ቡና", "በዓል"),
    "adventure": ("hike", "hiking", "trek", "climb", "mountain", "adventure", "nature", "landscape", "ጎቦ", "ተራራ"),
}

SUGGESTIONS = {
    "en": [("history", "When was Aksum inscribed as a World Heritage site?"), ("etiquette", "What should I know before visiting a church?"),
           ("festivals", "When is Meskel celebrated, and what happens?"), ("history", "What happened at the Battle of Adwa?"),
           ("planning", "Plan a 3-day history trip"), ("heritage", "Tell me about the rock-hewn churches of Gheralta")],
    "ti": [("history", "ኣክሱም መዓስ ብዩኔስኮ ተመዝጊባ?"), ("etiquette", "ቤተ ክርስቲያን ቅድሚ ምብጻሕ እንታይ ክፈልጥ ኣለኒ?"),
           ("festivals", "በዓል መስቀል መዓስ ይብዓል?"), ("planning", "ናይ 3 መዓልቲ ታሪኻዊ ጉዕዞ ኣዳልወለይ")],
    "am": [("history", "አክሱም በዩኔስኮ መቼ ተመዘገበ?"), ("etiquette", "ቤተ ክርስቲያን ከመጎብኘቴ በፊት ምን ማወቅ አለብኝ?"),
           ("festivals", "የጥምቀት በዓል መቼ ይከበራል?"), ("planning", "የ3 ቀን የታሪክ ጉዞ እቅድ አዘጋጅልኝ")],
}
DEST_SUGGESTIONS = {
    "en": ["What is the history of {name}?", "What etiquette should visitors know at {name}?", "Plan 2 days around {name}"],
    "ti": ["ታሪኽ {name} እንታይ እዩ?", "ኣብ {name} በጻሕቲ እንታይ ስርዓት ክፈልጡ ኣለዎም?"],
    "am": ["የ{name} ታሪክ ምንድን ነው?", "በ{name} ጎብኚዎች ምን ሥርዓት ማወቅ አለባቸው?"],
}


def suggestions(db: Session, locale: str, destination_slug: str | None = None) -> list[dict]:
    from app.modules.content.service import localize_snapshot
    locale = norm_locale(locale)
    if destination_slug:
        d = db.execute(select(Destination).where(Destination.slug == destination_slug)).scalar_one_or_none()
        if d is not None and d.published_snapshot:
            name = localize_snapshot(d.published_snapshot, locale)["name"]
            return [{"text": t.format(name=name), "category": "destination"} for t in DEST_SUGGESTIONS.get(locale, DEST_SUGGESTIONS["en"])]
    return [{"text": t, "category": c} for c, t in SUGGESTIONS.get(locale, SUGGESTIONS["en"])]


def actions_for(db: Session, question: str, answer: dict, locale: str, destination_slug: str | None = None) -> list[dict]:
    """Suggest next steps. Never executes anything; the planner remains deterministic and user-driven."""
    from app.modules.content.service import localize_snapshot
    from app.modules.knowledge.models import KnowledgeChunk

    if answer.get("confidence") == "refused":
        return []
    out: list[dict] = []
    dest = None
    if destination_slug:
        dest = db.execute(select(Destination).where(Destination.slug == destination_slug)).scalar_one_or_none()
    if dest is None:
        for c in answer.get("citations", []):
            chunk = db.get(KnowledgeChunk, uuid.UUID(c["chunk_id"]))
            for did in (chunk.destination_ids if chunk else []) or []:
                d = db.get(Destination, did)
                if d is not None and d.published_snapshot:
                    dest = d
                    break
            if dest:
                break
    q = question.lower()
    if PLAN_INTENT.search(q):
        m = DAYS.search(q)
        days = max(1, min(14, int(m.group(1)))) if m else 3
        interests = sorted(k for k, words in INTEREST_WORDS.items() if any(w in q for w in words))
        params: dict = {"days": days, "interests": interests}
        if dest is not None:
            params["start_slug"] = dest.slug
        label = {"en": f"Open the planner · {days} days", "ti": f"መደብ ጉዕዞ ክፈት · {days} መዓልቲ",
                 "am": f"የጉዞ እቅድ ክፈት · {days} ቀናት"}.get(norm_locale(locale))
        out.append({"type": "open_planner", "label": label, "params": params})
    if dest is not None and dest.published_snapshot:
        name = localize_snapshot(dest.published_snapshot, norm_locale(locale))["name"]
        out.append({"type": "open_destination", "label": name, "slug": dest.slug})
    return out

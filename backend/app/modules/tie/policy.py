"""TIE policy & safety engine: input screening, personas, output validation.

The model is never trusted to enforce policy. Everything here runs outside the model:
* input screening decides refuse / allow-with-warning before retrieval;
* permission filtering happens in SQL (retrieval.clearance_for);
* output validation checks citations against the supplied context and flags operational claims
  (prices, opening hours, phone numbers, permits, road/safety status) that the context does not
  support.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field

PERSONAS: dict[str, dict] = {
    "historian": {"name": {"en": "Historian", "ti": "ታሪኻዊ", "am": "የታሪክ ምሁር"},
                  "style": "Explain chronologically and precisely. Name periods and distinguish evidence from tradition."},
    "storyteller": {"name": {"en": "Cultural storyteller", "ti": "ተዛራቢ ባህሊ", "am": "የባህል ተራኪ"},
                    "style": "Warm narrative tone, vivid but faithful to the sources. Never embellish facts."},
    "academic": {"name": {"en": "Academic researcher", "ti": "ተመራማሪ", "am": "ተመራማሪ"},
                 "style": "Formal and analytical. Note scholarly debate, uncertainty and the nature of each source."},
    "family": {"name": {"en": "Family guide", "ti": "መምርሒ ስድራ", "am": "የቤተሰብ መሪ"},
               "style": "Simple, friendly language suitable for children and families. Short sentences."},
    "adventure": {"name": {"en": "Adventure consultant", "ti": "ኣማኻሪ ጀብዱ", "am": "የጀብዱ አማካሪ"},
                  "style": "Practical and energetic, focused on landscapes and activities. Stress verification of conditions."},
    "food": {"name": {"en": "Food & culture guide", "ti": "መምርሒ መግብን ባህልን", "am": "የምግብና ባህል መሪ"},
             "style": "Focus on cuisine, coffee ceremony, hospitality customs and their cultural meaning."},
    "photography": {"name": {"en": "Photography guide", "ti": "መምርሒ ስእሊ", "am": "የፎቶግራፍ መሪ"},
                    "style": "Focus on light, landscapes and respectful photography etiquette, including when NOT to photograph."},
    "education": {"name": {"en": "Heritage education guide", "ti": "መምርሒ ትምህርቲ ቅርሲ", "am": "የቅርስ ትምህርት መሪ"},
                  "style": "Structured like a lesson with key ideas and a question to think about. Suitable for students."},
}
DEFAULT_PERSONA = "storyteller"

INJECTION = [
    r"ignore (all |any )?(previous|prior|above|your) (instructions|rules|prompts?)",
    r"disregard (the |your )?(system|previous|safety) (prompt|instructions|rules)",
    r"\b(system|developer) prompt\b", r"\bjailbreak\b", r"\bdeveloper mode\b", r"\bDAN\b",
    r"you are (now )?no longer", r"pretend (that )?you (are|have) no (rules|restrictions)",
    r"reveal (your|the) (hidden |system )?(instructions|prompt|rules)",
    r"</?\s*(system|assistant|tool)\s*>",
    # Tigrinya / Amharic: "forget/ignore previous instructions", "reveal your instructions"
    r"መምርሒ(ታት)?\s*(ረሲዕ|ሕደግ|ዕሽሽ)", r"መመሪያ(ዎች|ዎችን)?\s*(ችላ|እርሳ|ተው)", r"ችላ\s*በል",
    r"(ምስጢራዊ|ስውር|የስርዓት)\s*(መምርሒ|መመሪያ)",
]
CIRCUMVENTION = [
    r"(avoid|bypass|evade|sneak (past|through)|get around|skip) (the )?(checkpoints?|police|soldiers|military|permits?|guards?|custodians?|priests?)",
    r"without (a |the )?(permit|permission|authori[sz]ation)",
    r"(enter|visit|go into) .{0,30}(without|despite) .{0,20}(permission|being allowed|ban|closure)",
    r"ብዘይ\s*ፍቓድ", r"ያለ\s*ፈቃድ", r"ኬላ.{0,30}(ምሕላፍ|ምህዳም|ምምላጥ|ማለፍ|ማምለጥ|መሸሽ|ሸሽ)",
]
RESTRICTED_LOCATION = [
    r"(exact|precise|gps|coordinates?|lat(itude)?[ /]+long?(itude)?).{0,40}(church|monastery|sacred|tabot|manuscript|treasury|excavation|dig site|tomb)",
    r"(church|monastery|sacred|tabot|manuscript|treasury|excavation|tomb).{0,40}(exact|precise|gps|coordinates?)",
    r"where (exactly )?(is|are) the (tabot|ark|treasury|manuscripts?) (kept|stored|hidden)",
    r"(ትኽክለኛ|ትክክለኛ|ጂፒኤስ|መጋጠሚያ).{0,40}(ቤተ\s*ክርስቲያን|ገዳም|ታቦት)",
    r"(ቤተ\s*ክርስቲያን|ገዳም|ታቦት).{0,40}(ትኽክለኛ|ትክክለኛ|ጂፒኤስ|መጋጠሚያ)",
]
# Questions about live, operational facts. Unless approved evidence literally contains such facts,
# the guide answers "insufficient evidence" instead of offering loosely related excerpts.
OPERATIONAL_INTENT = [
    r"\b(price|prices|cost|costs|how much|fee|fees|ticket|tariff|rate)\b", r"\bhotel(s)? (room|price|rate|availab)",
    r"\b(opening|open) (hours|times|today|now)\b", r"\bis (it|the \w+) open\b", r"\broad\b.{0,40}\b(open|closed|safe|condition)",
    r"\b(safe|safety|security situation)\b.{0,30}\b(travel|visit|now|today)\b", r"\bavailab(le|ility)\b",
    r"ዋጋ", r"ክንደይ", r"ስንት", r"ክፉት", r"ክፍት", r"መንገዲ.{0,20}(ክፉት|ዕጹው|ውሑስ)", r"መንገድ.{0,20}(ክፍት|ዝግ|ደህንነት)",
]
STOPWORDS = {"the", "and", "what", "when", "where", "which", "who", "how", "does", "did", "was", "were", "are", "is",
             "for", "with", "about", "tell", "from", "into", "this", "that", "have", "has", "can", "should", "you",
             "your", "me", "there", "they", "their", "of", "in", "on", "to", "a", "an", "it", "its", "be", "do",
             "እንታይ", "እዩ", "እያ", "ኣብ", "ናይ", "ምንድን", "ነው", "እና", "ውስጥ", "መቼ", "መዓስ", "ከመይ", "እንዴት"}


def strip_injection(question: str) -> str:
    """Remove sentences containing injection patterns, keeping any legitimate question for retrieval."""
    parts = re.split(r"(?<=[.!?።፧])\s+", question)
    kept = [p for p in parts if not any(re.search(pat, p, re.I) for pat in INJECTION)]
    return " ".join(kept).strip() or question


def operational_intent(question: str) -> bool:
    q = question.lower()
    return any(re.search(p, q) for p in OPERATIONAL_INTENT)


def evidence_has_operational_facts(texts: list[str]) -> bool:
    return any(OPERATIONAL.search(t) for t in texts)
PERSONAL_DATA = [r"(email|phone|address|home) (of|for) (the )?(visitor|user|tourist|person) ", r"who (uploaded|posted|wrote) .{0,40}(real name|address|phone)"]
OPERATIONAL = re.compile(
    r"(\b\d{1,2}[:.]\d{2}\s*(am|pm)?\b|\bopen(s|ing)? (daily|every)\b|\b(ETB|birr|USD|US\$|\$|€)\s?\d|\d+\s?(birr|ETB|USD|dollars)\b"
    r"|\+?251[\s-]?\d{2}|\b0\d{2}[\s-]?\d{3}[\s-]?\d{4}\b|\broad (is|was) (open|closed|safe)\b|\b(it is|it's) (safe|unsafe) to travel\b"
    r"|\bno permit (is )?(needed|required)\b)", re.I)


@dataclass
class ScreenResult:
    decision: str  # allow|refuse
    reasons: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    refusal_code: str | None = None


def screen_input(question: str) -> ScreenResult:
    q = question.lower()
    if any(re.search(p, q) for p in CIRCUMVENTION):
        return ScreenResult("refuse", ["circumvention"], refusal_code="circumvention")
    if any(re.search(p, q) for p in RESTRICTED_LOCATION):
        return ScreenResult("refuse", ["restricted_location"], refusal_code="restricted_location")
    if any(re.search(p, q) for p in PERSONAL_DATA):
        return ScreenResult("refuse", ["personal_data"], refusal_code="personal_data")
    r = ScreenResult("allow")
    if any(re.search(p, q, re.I) for p in INJECTION):
        # Not refused outright: the question may still be legitimate. The injected instruction
        # carries no authority because the system prompt and validators do not change.
        r.warnings.append("prompt_injection_attempt_ignored")
        r.reasons.append("injection_pattern")
    return r


REFUSALS = {
    "circumvention": {
        "en": "I can't help with avoiding checkpoints, permits or custodial permissions. Please follow official guidance and the instructions of site custodians. I can share the cultural history of the place, or help you plan a virtual visit instead.",
        "ti": "ካብ ቼክፖይንት፣ ፍቓድ ወይ ፍቓድ ሓለውቲ ንምህዳም ክሕግዝ ኣይክእልን እየ። በጃኹም መምርሒ ወግዓዊ ኣካላትን ሓለውቲ ቦታን ተኸተሉ።",
        "am": "ከፍተሻ ጣቢያዎች፣ ፈቃዶች ወይም ከጠባቂዎች ፈቃድ ለማምለጥ መርዳት አልችልም። እባክዎ ይፋዊ መመሪያዎችንና የቦታ ጠባቂዎችን ይከተሉ።"},
    "restricted_location": {
        "en": "Precise locations of sacred, archaeological or protected sites are not shared publicly to protect them. Licensed local guides and site custodians can advise visitors directly. I can tell you about the site's history and etiquette.",
        "ti": "ትኽክለኛ ቦታ ቅዱሳትን ጥንታውያንን ቦታታት ንምሕላዎም ብህዝባዊ መንገዲ ኣይውሃብን።",
        "am": "የቅዱሳትና የአርኪኦሎጂ ቦታዎች ትክክለኛ መገኛ ለጥበቃቸው ሲባል በይፋ አይጋራም።"},
    "personal_data": {
        "en": "I can't share personal information about visitors or contributors.",
        "ti": "ብዛዕባ በጻሕቲ ወይ ተሳተፍቲ ውልቃዊ ሓበሬታ ከካፍል ኣይክእልን።",
        "am": "ስለ ጎብኚዎች ወይም አስተዋጽኦ አድራጊዎች የግል መረጃ ማጋራት አልችልም።"},
}
INSUFFICIENT = {
    "en": "I don't have approved sources that answer this yet, so I won't guess. You could ask about a specific destination, its history or etiquette, or contact the Tourism Bureau for official information.",
    "ti": "ነዚ ዝምልስ ዝተረጋገጸ ምንጪ ገና የብለይን፣ ስለዚ ኣይግምትን እየ። ብዛዕባ ፍሉይ መዳረሻ ሕተቱ ወይ ቢሮ ቱሪዝም ተወከሱ።",
    "am": "ይህንን የሚመልስ የተረጋገጠ ምንጭ ገና የለኝም፣ ስለዚህ አልገምትም። ስለ አንድ መዳረሻ ይጠይቁ ወይም የቱሪዝም ቢሮን ያነጋግሩ።",
}


@dataclass
class Validated:
    answer: str
    cited: list[int]
    confidence: str
    follow_ups: list[str]
    warnings: list[str]


def parse_model_json(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        raw = re.sub(r"^```(json)?|```$", "", raw, flags=re.M).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start < 0 or end < start:
        raise ValueError("no JSON object in model output")
    data = json.loads(raw[start:end + 1])
    if not isinstance(data, dict):
        raise ValueError("model output is not an object")
    return data


def validate_output(data: dict, n_context: int, context_text: str) -> Validated:
    warnings: list[str] = []
    answer = str(data.get("answer", "")).strip()
    if not answer:
        raise ValueError("empty answer")
    answer = answer[:4000]
    declared = data.get("citations") or []
    markers = {int(m) for m in re.findall(r"\[(\d{1,2})\]", answer)}
    cited = sorted({int(c) for c in declared if str(c).isdigit()} | markers)
    invalid = [c for c in cited if c < 1 or c > n_context]
    if invalid:
        warnings.append("invalid_citations_removed")
        for c in invalid:
            answer = answer.replace(f"[{c}]", "")
        cited = [c for c in cited if 1 <= c <= n_context]
    confidence = str(data.get("confidence", "partial"))
    if confidence not in ("grounded", "partial", "insufficient_evidence"):
        confidence = "partial"
    if not cited and confidence == "grounded":
        confidence = "partial"
        warnings.append("uncited_answer")
    # Operational claims must be literally supported by the retrieved context.
    ctx = context_text.lower()
    unsupported = [m.group(0) for m in OPERATIONAL.finditer(answer) if m.group(0).lower() not in ctx]
    if unsupported:
        warnings.append("unsupported_operational_claims")
        confidence = "partial" if confidence == "grounded" else confidence
        answer += ("\n\nNote: details such as prices, opening times, contacts, permits or road and safety "
                   "conditions above are not confirmed by approved sources — verify them with official channels.")
    follow = [str(x)[:200] for x in (data.get("follow_up_questions") or [])][:3]
    return Validated(answer, cited, confidence, follow, warnings)

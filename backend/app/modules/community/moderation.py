"""AI-*assisted* moderation signals. They only add flags for human moderators; they never decide.

Heuristics are transparent and auditable (no opaque model). A local classifier can be plugged in
later through the same ``flags_for`` interface; its output must remain advisory.
"""
from __future__ import annotations

import re

LINK = re.compile(r"https?://|www\.", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")
PHONE = re.compile(r"(\+?\d[\d\s-]{8,}\d)")
COORDS = re.compile(r"-?\d{1,2}\.\d{3,}\s*[,;]\s*-?\d{1,3}\.\d{3,}")
SHOUT = re.compile(r"\b[A-Z]{6,}\b")
SPAM_WORDS = re.compile(r"\b(buy now|cheap|discount|crypto|casino|click here|promo code|whatsapp me)\b", re.I)
ABUSE = re.compile(r"\b(idiot|stupid|hate you|kill yourself)\b", re.I)


def flags_for(text: str) -> list[str]:
    flags = []
    if len(LINK.findall(text)) >= 2:
        flags.append("many_links")
    if SPAM_WORDS.search(text):
        flags.append("spam_terms")
    if EMAIL.search(text) or PHONE.search(text):
        flags.append("personal_contact_details")
    if COORDS.search(text):
        flags.append("precise_coordinates")  # may expose a protected site
    if len(SHOUT.findall(text)) >= 3:
        flags.append("shouting")
    if re.search(r"(.)\1{9,}", text):
        flags.append("repeated_characters")
    if ABUSE.search(text):
        flags.append("possible_abuse")
    return flags


HOLD_FLAGS = {"possible_abuse", "spam_terms", "many_links"}  # comments with these wait for a human

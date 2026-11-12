"""Locale helpers for JSONB {locale: text} fields."""
from __future__ import annotations

SUPPORTED = ("en", "ti", "am")
FALLBACK = "en"


def norm_locale(locale: str | None) -> str:
    loc = (locale or FALLBACK).split("-")[0].lower()
    return loc if loc in SUPPORTED else FALLBACK


def pick(values: dict | None, locale: str) -> tuple[str, str | None]:
    """Return (text, locale_used). Falls back to English, then to any available locale."""
    values = values or {}
    for loc in (locale, FALLBACK, *values.keys()):
        v = values.get(loc)
        if v:
            return v, loc
    return "", None

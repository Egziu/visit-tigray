"""Ethiopic-script text utilities: normalization, search folding, transliteration, language guess.

Limitations, stated plainly:
* ``guess_language`` is a lightweight lexical heuristic for routing and analytics. It is **not** a
  validated language-identification model. Short Ethiopic strings often return ``und-Ethi``.
* ``transliterate`` is a simplified SERA-like scheme, used only for search aliases. It is not a
  standard romanization for publication.
* ``fold_for_search`` merges homophonous letters (ሀ/ሐ/ኀ, ሰ/ሠ, አ/ዐ, ጸ/ፀ) that writers use
  interchangeably in modern Amharic and Tigrinya. Folding only affects search keys, never stored text.
"""
from __future__ import annotations

import re
import unicodedata

ETHIOPIC_RE = re.compile(r"[ሀ-፿ᎀ-᎟ⶀ-⷟꬀-꬯]")

# Row base code point -> consonant (Latin), rows of 8 orders in U+1200–U+135A.
_ROWS = {
    0x1200: "h", 0x1208: "l", 0x1210: "h", 0x1218: "m", 0x1220: "s", 0x1228: "r", 0x1230: "s",
    0x1238: "sh", 0x1240: "q", 0x1248: "qw", 0x1250: "qh", 0x1258: "qhw", 0x1260: "b", 0x1268: "v",
    0x1270: "t", 0x1278: "ch", 0x1280: "h", 0x1288: "hw", 0x1290: "n", 0x1298: "ny", 0x12A0: "",
    0x12A8: "k", 0x12B0: "kw", 0x12B8: "kh", 0x12C0: "khw", 0x12C8: "w", 0x12D0: "", 0x12D8: "z",
    0x12E0: "zh", 0x12E8: "y", 0x12F0: "d", 0x12F8: "dd", 0x1300: "j", 0x1308: "g", 0x1310: "gw",
    0x1318: "gg", 0x1320: "t'", 0x1328: "ch'", 0x1330: "p'", 0x1338: "ts'", 0x1340: "ts'", 0x1348: "f",
    0x1350: "p",
}
_VOWELS = ["e", "u", "i", "a", "ie", "", "o", "wa"]

# Search folding: map variant letters (whole rows) to a canonical row.
_FOLD_ROWS = {0x1210: 0x1200, 0x1280: 0x1200, 0x1220: 0x1230, 0x12D0: 0x12A0, 0x1340: 0x1338}

_TI_MARKERS = {"እዩ", "ኢዩ", "ኣብ", "ናይ", "እንታይ", "ከመይ", "ኣሎ", "ኣለዉ", "ዝኾነ", "እዚ", "ኣይ", "ብዛዕባ", "ኣበይ", "ክንደይ", "ትግራይ"}
_AM_MARKERS = {"ነው", "ናቸው", "ውስጥ", "እና", "ምን", "እንዴት", "አለ", "ይህ", "የት", "ስለ", "ምንድን", "ምንድነው", "ነበር", "በጣም"}


def nfc(text: str) -> str:
    return unicodedata.normalize("NFC", text or "")


def is_ethiopic(text: str) -> bool:
    return bool(ETHIOPIC_RE.search(text or ""))


def fold_char(ch: str) -> str:
    cp = ord(ch)
    if 0x1200 <= cp <= 0x1357:
        base, order = cp - (cp - 0x1200) % 8, (cp - 0x1200) % 8
        if base in _FOLD_ROWS:
            return chr(_FOLD_ROWS[base] + order)
    return ch


def fold_for_search(text: str) -> str:
    """Lowercase, NFKC, strip Latin diacritics, fold Ethiopic homophones, unify punctuation."""
    t = unicodedata.normalize("NFKC", text or "").lower()
    t = "".join(c for c in unicodedata.normalize("NFD", t) if unicodedata.category(c) != "Mn" or is_ethiopic(c))
    t = unicodedata.normalize("NFC", t)
    t = "".join(fold_char(c) for c in t)
    t = re.sub(r"[፡-፨]", " ", t)  # Ethiopic wordspace/full stop/comma etc.
    return re.sub(r"\s+", " ", t).strip()


def transliterate(text: str) -> str:
    out = []
    for ch in nfc(text):
        cp = ord(ch)
        if 0x1200 <= cp <= 0x1357:
            base, order = cp - (cp - 0x1200) % 8, (cp - 0x1200) % 8
            cons = _ROWS.get(base)
            if cons is None:
                out.append(ch)
                continue
            vowel = _VOWELS[order]
            if base in (0x12A0, 0x12D0):
                vowel = {0: "a", 3: "a", 5: "e"}.get(order, vowel)
            out.append(cons + vowel)
        elif ch in "፡።":
            out.append(" " if ch == "፡" else ".")
        else:
            out.append(ch)
    return re.sub(r"\s+", " ", "".join(out)).strip()


def tokens(text: str) -> list[str]:
    return [t for t in re.split(r"[^\wሀ-፿]+", fold_for_search(text)) if t]


def guess_language(text: str) -> str:
    """Return 'ti', 'am', 'en', 'und-Ethi' or 'und'."""
    if not text or not text.strip():
        return "und"
    if is_ethiopic(text):
        words = set(re.split(r"[\s፡-፨.,?!:;]+", nfc(text)))
        ti: float = len(words & _TI_MARKERS)
        am: float = len(words & _AM_MARKERS)
        # Tigrinya conventionally spells word-initial /a/ with ኣ (U+12A3), Amharic with አ (U+12A0).
        ti += 0.5 * len(re.findall(r"(?:^|\s)ኣ", text))
        am += 0.5 * len(re.findall(r"(?:^|\s)አ", text))
        if ti > am:
            return "ti"
        if am > ti:
            return "am"
        return "und-Ethi"
    latin = re.findall(r"[A-Za-z]+", text)
    return "en" if latin else "und"

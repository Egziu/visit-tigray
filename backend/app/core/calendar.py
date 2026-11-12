"""Ethiopian (Ge'ez) calendar <-> Gregorian conversion using fixed day numbers (Rata Die).

Algorithm from Reingold & Dershowitz, *Calendrical Calculations*: the Ethiopic epoch is
R.D. 2796 (29 August 8 CE, Julian). Python's ``date.toordinal()`` is R.D. (1 Jan 1 CE = 1).
Ethiopian days start at local dawn in traditional usage; this module converts civil dates.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

ETHIOPIC_EPOCH = 2796

MONTHS = {
    "en": ["Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir", "Yekatit", "Megabit", "Miazia", "Ginbot",
           "Sene", "Hamle", "Nehase", "Pagume"],
    "ti": ["መስከረም", "ጥቅምቲ", "ሕዳር", "ታሕሳስ", "ጥሪ", "ለካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰነ",
           "ሓምለ", "ነሓሰ", "ጳጉሜን"],
    "am": ["መስከረም", "ጥቅምት", "ኅዳር", "ታኅሣሥ", "ጥር", "የካቲት", "መጋቢት", "ሚያዝያ", "ግንቦት", "ሰኔ",
           "ሐምሌ", "ነሐሴ", "ጳጉሜን"],
}


@dataclass(frozen=True)
class EthiopianDate:
    year: int
    month: int
    day: int

    def __post_init__(self) -> None:
        if not 1 <= self.month <= 13:
            raise ValueError("month must be 1..13")
        max_day = 30 if self.month < 13 else (6 if is_leap(self.year) else 5)
        if not 1 <= self.day <= max_day:
            raise ValueError(f"day must be 1..{max_day} for month {self.month}")

    def to_fixed(self) -> int:
        return ETHIOPIC_EPOCH - 1 + 365 * (self.year - 1) + self.year // 4 + 30 * (self.month - 1) + self.day

    def to_gregorian(self) -> date:
        return date.fromordinal(self.to_fixed())

    def format(self, locale: str = "en") -> str:
        names = MONTHS.get(locale, MONTHS["en"])
        suffix = " ዓ.ም." if locale in ("ti", "am") else " E.C."
        return f"{names[self.month - 1]} {self.day}, {self.year}{suffix}"


def is_leap(eth_year: int) -> bool:
    """Ethiopian leap years: year mod 4 == 3 (Pagume has 6 days)."""
    return eth_year % 4 == 3


def from_gregorian(d: date) -> EthiopianDate:
    fixed = d.toordinal()
    year = (4 * (fixed - ETHIOPIC_EPOCH) + 1463) // 1461
    month = (fixed - EthiopianDate(year, 1, 1).to_fixed()) // 30 + 1
    day = fixed + 1 - EthiopianDate(year, month, 1).to_fixed()
    return EthiopianDate(year, month, day)

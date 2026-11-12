from __future__ import annotations

from datetime import date

import pytest

from app.core.calendar import EthiopianDate, from_gregorian, is_leap
from app.core.egress import EgressBlocked, check_url, classify_host, decide
from app.core.ethiopic import fold_for_search, guess_language, transliterate


@pytest.mark.parametrize("greg,eth", [
    (date(2024, 9, 11), (2017, 1, 1)),   # Enkutatash 2017 E.C.
    (date(2023, 9, 12), (2016, 1, 1)),   # after leap year 2015 E.C.
    (date(2024, 1, 20), (2016, 5, 11)),  # Timket shifts to 20 Jan in Gregorian leap years
    (date(2025, 1, 19), (2017, 5, 11)),
    (date(2024, 9, 27), (2017, 1, 17)),  # Meskel
    (date(2023, 9, 11), (2015, 13, 6)),  # Pagume 6 exists in leap year 2015
])
def test_ethiopian_calendar_known_dates(greg, eth):
    e = from_gregorian(greg)
    assert (e.year, e.month, e.day) == eth
    assert EthiopianDate(*eth).to_gregorian() == greg


def test_ethiopian_calendar_round_trip_and_validation():
    d = date(1900, 1, 1)
    for i in range(0, 60000, 7):
        g = date.fromordinal(d.toordinal() + i)
        assert from_gregorian(g).to_gregorian() == g
    assert is_leap(2015) and not is_leap(2016)
    with pytest.raises(ValueError):
        EthiopianDate(2016, 13, 6)
    with pytest.raises(ValueError):
        EthiopianDate(2016, 14, 1)


def test_ethiopic_text_utils():
    assert transliterate("አክሱም") == "aksum"
    assert fold_for_search("ሐውዜን") == fold_for_search("ሀውዜን")
    assert fold_for_search("ጸሓይ") == fold_for_search("ፀሓይ")
    assert guess_language("ኣክሱም ኣበይ እያ ዘላ") == "ti"
    assert guess_language("አክሱም የት ነው") == "am"
    assert guess_language("Where is Aksum?") == "en"
    assert guess_language("ሰላም") == "und-Ethi"  # honest uncertainty on short strings


def test_egress_host_classification():
    assert classify_host("localhost") == "local"
    assert classify_host("10.0.0.5") == "local"
    assert classify_host("ollama") == "local"
    assert classify_host("api.openai.com") == "external"
    assert classify_host("169.254.169.254") == "forbidden"
    assert classify_host("example.local") == "external"  # private zones only if configured


def test_egress_policy_blocks_external_ai_in_local_modes():
    for mode in ("fully_local", "offline", "retrieval_only", "deterministic"):
        assert not decide("https://api.openai.com/v1/chat", "ai_inference", mode).allowed
        assert decide("http://localhost:11434/api/chat", "ai_inference", mode).allowed
    assert decide("https://api.openai.com/v1/chat", "ai_inference", "cloud_assisted").allowed
    assert not decide("http://api.example.com/x", "integration", "cloud_assisted").allowed  # plaintext external
    assert not decide("file:///etc/passwd", "integration", "cloud_assisted").allowed
    with pytest.raises(EgressBlocked):
        check_url("http://169.254.169.254/latest/meta-data", "integration", "cloud_assisted")

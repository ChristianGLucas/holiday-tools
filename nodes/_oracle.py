"""Independent ground truth for the test suite.

Nothing in this module consults the wrapped `holidays` library. Every value
here is derived from a published, authoritative rule — the Gregorian computus
for Easter, plain calendar arithmetic for nth-weekday holidays — or is a
hand-verified constant from an official calendar. That is what makes the tests
an oracle rather than the library grading its own homework.

This file ships with the package; it is small, dependency-free, and importing it
from the handlers is deliberately never done.
"""

from datetime import date, timedelta


def easter_sunday(year: int) -> date:
    """Western (Gregorian) Easter, via the anonymous computus.

    Implemented from the published algorithm, independently of any library, so
    it can be used to check Easter-derived holidays (Good Friday, Easter Monday,
    Corpus Christi) — the classic source of off-by-one errors.
    """
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    lu = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * lu) // 451
    month = (h + lu - 7 * m + 114) // 31
    day = ((h + lu - 7 * m + 114) % 31) + 1
    return date(year, month, day)


def nth_weekday(year: int, month: int, iso_weekday: int, n: int) -> date:
    """The nth occurrence of a weekday in a month, by plain arithmetic.

    iso_weekday follows date.isoweekday(): Monday=1 .. Sunday=7. n is 1-based;
    pass n=-1 for the LAST occurrence in the month.
    """
    if n > 0:
        first = date(year, month, 1)
        offset = (iso_weekday - first.isoweekday()) % 7
        return first + timedelta(days=offset + 7 * (n - 1))
    if month == 12:
        last = date(year, 12, 31)
    else:
        last = date(year, month + 1, 1) - timedelta(days=1)
    offset = (last.isoweekday() - iso_weekday) % 7
    return last - timedelta(days=offset)


def naive_add_weekdays(start: date, days: int) -> date:
    """Advance by business days counting ONLY Saturday/Sunday as non-working.

    This is deliberately holiday-BLIND — it is what a spreadsheet's WORKDAY does
    with no holiday list. Tests use it as a contrast oracle: where the package's
    answer differs from this, the difference must be explained by a real holiday.
    """
    current = start
    step = 1 if days >= 0 else -1
    remaining = abs(days)
    while remaining > 0:
        current += timedelta(days=step)
        if current.isoweekday() <= 5:
            remaining -= 1
    return current


def naive_count_weekdays(start: date, end: date) -> int:
    """Count Mon-Fri days in an inclusive range, holiday-blind. Contrast oracle."""
    total = 0
    current = start
    while current <= end:
        if current.isoweekday() <= 5:
            total += 1
        current += timedelta(days=1)
    return total


# --- Hand-verified constants from official published calendars --------------

# US federal law: when Independence Day (July 4) falls on a Saturday it is
# observed on the preceding Friday. July 4 2026 is a Saturday.
US_INDEPENDENCE_DAY_2026 = date(2026, 7, 4)
US_INDEPENDENCE_DAY_2026_OBSERVED = date(2026, 7, 3)

# Israel, Egypt, Saudi Arabia, Jordan and Qatar rest Friday-Saturday.
FRI_SAT_WEEKEND_COUNTRIES = ("IL", "EG", "SA", "JO", "QA")

# Bavaria (DE-BY) observes Epiphany; the German national calendar does not.
DE_BY_EPIPHANY_2026 = date(2026, 1, 6)

# Texas observes Texas Independence Day; the US federal calendar does not.
US_TX_INDEPENDENCE_2026 = date(2026, 3, 2)

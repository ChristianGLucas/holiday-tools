from datetime import date

from gen.messages_pb2 import Error, HolidayList, HolidayOccurrence, NameQuery
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def _occ(o):
    return HolidayOccurrence(
        date=o["date"], name=o["name"], observed=o["observed"],
        category=o["category"], weekday=o["weekday"],
    )


def find_holiday_by_name(ax: AxiomContext, input: NameQuery) -> HolidayList:
    """Find which DATES a named holiday falls on across a span of years - the
    inverse of asking what falls on a date.

    Answers "when is Thanksgiving in 2026 and 2027?" for a moving feast whose
    date is a rule rather than a fixed day (fourth Thursday of November,
    Easter-derived dates, nth-weekday rules). Matching is case-insensitive and
    substring-based, so "Christmas" finds both "Christmas Day" and "Christmas
    Eve". Both the actual and observed dates are returned and flagged. The year
    span is required and inclusive; a span outside the calendar's coverage is a
    typed YEAR_OUT_OF_RANGE error.
    """
    try:
        cal = cu.resolve(input.calendar)
        needle = (input.name or "").strip()
        if not needle:
            raise cu.CalendarError(
                "INVALID_ARGUMENT",
                "name is required, e.g. 'Thanksgiving'.",
            )
        start_year, end_year = int(input.start_year), int(input.end_year)
        if start_year == 0 or end_year == 0:
            raise cu.CalendarError(
                "INVALID_ARGUMENT",
                "start_year and end_year are both required, e.g. 2026 and 2027.",
            )
        if end_year < start_year:
            raise cu.CalendarError(
                "INVALID_ARGUMENT",
                f"end_year {end_year} precedes start_year {start_year}.",
            )
        cal.check_year(start_year, "start_year")
        cal.check_year(end_year, "end_year")
        start, end = date(start_year, 1, 1), date(end_year, 12, 31)
        lowered = needle.casefold()
        occurrences = []
        for d in cu.daterange(start, end):
            for o in cal.holidays_on(d):
                if lowered in o["name"].casefold():
                    occurrences.append(o)
        occurrences.sort(key=lambda o: (o["date"], o["name"]))
        return HolidayList(
            ok=True,
            holidays=[_occ(o) for o in occurrences],
            count=len(occurrences),
            window_start=cu.iso(start),
            window_end=cu.iso(end),
        )
    except cu.CalendarError as exc:
        return HolidayList(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return HolidayList(ok=False, error=Error(code="INTERNAL", message=str(exc)))

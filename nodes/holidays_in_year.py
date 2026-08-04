from datetime import date

from gen.messages_pb2 import Error, HolidayList, HolidayOccurrence, YearQuery
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def _occ(o):
    return HolidayOccurrence(
        date=o["date"], name=o["name"], observed=o["observed"],
        category=o["category"], weekday=o["weekday"],
    )


def holidays_in_year(ax: AxiomContext, input: YearQuery) -> HolidayList:
    """List every public holiday in one calendar year for a country (optionally
    a subdivision) or a financial market, offline and deterministically.

    Subdivisions genuinely differ - US states, German Laender and Canadian
    provinces each add their own days - so a subdivision code changes the answer
    rather than decorating it, and an unrecognized subdivision is a typed error
    instead of a silent fall back to the national calendar. Each occurrence is
    flagged as an actual or an observed substitute date. A year outside the
    range the calendar actually covers returns a typed YEAR_OUT_OF_RANGE error
    rather than a silently empty list, which would be indistinguishable from a
    year that genuinely has no holidays.
    """
    try:
        cal = cu.resolve(input.calendar)
        year = int(input.year)
        if year == 0:
            raise cu.CalendarError(
                "INVALID_ARGUMENT",
                "year is required, e.g. 2026.",
            )
        cal.check_year(year, "year")
        start, end = date(year, 1, 1), date(year, 12, 31)
        occurrences = []
        for d in cu.daterange(start, end):
            occurrences.extend(cal.holidays_on(d))
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

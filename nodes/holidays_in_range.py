from gen.messages_pb2 import Error, HolidayList, HolidayOccurrence, RangeQuery
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def _occ(o):
    return HolidayOccurrence(
        date=o["date"], name=o["name"], observed=o["observed"],
        category=o["category"], weekday=o["weekday"],
    )


def holidays_in_range(ax: AxiomContext, input: RangeQuery) -> HolidayList:
    """List every public holiday falling inside a caller-supplied date range,
    for a country (optionally a subdivision) or a financial market.

    The range is INCLUSIVE of both endpoints and may span year boundaries. Each
    occurrence is flagged as the holiday's actual date or the substitute weekday
    it is observed on. Use this rather than HolidaysInYear when the window you
    care about is a quarter, a sprint, a payment period, or anything else that
    does not line up with a calendar year. Offline, deterministic, and never
    reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        start = cu.parse_date(input.start_date, "start_date")
        end = cu.parse_date(input.end_date, "end_date")
        cu.check_range(start, end)
        cal.check_date(start, "start_date")
        cal.check_date(end, "end_date")
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

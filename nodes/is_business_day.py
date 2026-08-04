from gen.messages_pb2 import BusinessDayStatus, DateQuery, Error, HolidayOccurrence
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def _occ(o):
    return HolidayOccurrence(
        date=o["date"], name=o["name"], observed=o["observed"],
        category=o["category"], weekday=o["weekday"],
    )


def is_business_day(ax: AxiomContext, input: DateQuery) -> BusinessDayStatus:
    """Report whether one caller-supplied date is a working day on a country or
    financial-market calendar, and when it is not, say exactly why.

    The reason is one of BUSINESS_DAY, WEEKEND, HOLIDAY or WEEKEND_AND_HOLIDAY,
    so a caller can distinguish "the office is shut because it is Saturday" from
    "the office is shut because it is Christmas" - a distinction a bare boolean
    loses. The weekend is the calendar's own real weekend (Friday/Saturday for
    Israel, Egypt and Saudi Arabia; Friday alone for Iran), overridable per
    request. Any holidays landing on the date are returned alongside. Fully
    offline and deterministic; never reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        d = cu.parse_date(input.date, "date")
        cal.check_date(d, "date")
        occurrences = cal.holidays_on(d)
        return BusinessDayStatus(
            ok=True,
            date=cu.iso(d),
            is_business_day=cal.is_business_day(d),
            reason=cal.reason(d),
            weekday=cu.weekday_enum(d),
            holidays=[_occ(o) for o in occurrences],
        )
    except cu.CalendarError as exc:
        return BusinessDayStatus(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return BusinessDayStatus(ok=False, error=Error(code="INTERNAL", message=str(exc)))

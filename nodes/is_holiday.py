from gen.messages_pb2 import DateQuery, Error, HolidayOccurrence, HolidayStatus
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def _occ(o):
    return HolidayOccurrence(
        date=o["date"], name=o["name"], observed=o["observed"],
        category=o["category"], weekday=o["weekday"],
    )


def is_holiday(ax: AxiomContext, input: DateQuery) -> HolidayStatus:
    """Report whether one caller-supplied date is a public holiday on one
    country or financial-market calendar, naming every holiday that lands on it.

    Each returned occurrence says whether it is the holiday's ACTUAL date or the
    substitute weekday it is OBSERVED on when the real date falls on a weekend
    (the classic "Independence Day (observed)" Friday) - both are returned by
    default so the caller can tell them apart. Also reports whether the date is
    a weekend day on that calendar (which is Friday/Saturday in much of the
    Middle East, not universally Saturday/Sunday) and whether it is therefore a
    working day. Fully offline and deterministic: the date is always supplied by
    the caller and this node never reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        d = cu.parse_date(input.date, "date")
        cal.check_date(d, "date")
        occurrences = cal.holidays_on(d)
        return HolidayStatus(
            ok=True,
            date=cu.iso(d),
            is_holiday=bool(occurrences),
            holidays=[_occ(o) for o in occurrences],
            is_weekend=cal.is_weekend(d),
            is_business_day=cal.is_business_day(d),
            weekday=cu.weekday_enum(d),
        )
    except cu.CalendarError as exc:
        return HolidayStatus(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001 - never leak a traceback to a caller
        return HolidayStatus(ok=False, error=Error(code="INTERNAL", message=str(exc)))

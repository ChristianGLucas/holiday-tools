from gen.messages_pb2 import BusinessDayResult, Error, RollQuery
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def roll_to_business_day(ax: AxiomContext, input: RollQuery) -> BusinessDayResult:
    """Adjust a date that is not a business day onto one that is, under a named
    financial roll convention.

    FOLLOWING moves to the next business day, PRECEDING to the previous, and the
    MODIFIED variants do the same but reverse direction rather than cross a
    calendar-month boundary - the convention that keeps a monthly payment inside
    its own month. A date that is already a business day is returned unchanged
    by every convention, with unchanged set true. This is the settlement-date
    adjustment invoice due dates, payment terms and coupon schedules need, and
    unlike a schedule generator it applies to any single date. Offline,
    deterministic, and never reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        d = cu.parse_date(input.date, "date")
        cal.check_date(d, "date")
        result = cal.roll(d, input.convention)
        return BusinessDayResult(
            ok=True,
            date=cu.iso(result),
            start_date=cu.iso(d),
            calendar_days_moved=(result - d).days,
            weekday=cu.weekday_enum(result),
            unchanged=(result == d),
        )
    except cu.CalendarError as exc:
        return BusinessDayResult(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return BusinessDayResult(ok=False, error=Error(code="INTERNAL", message=str(exc)))

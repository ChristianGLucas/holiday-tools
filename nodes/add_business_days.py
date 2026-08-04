from gen.messages_pb2 import AddBusinessDaysQuery, BusinessDayResult, Error
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def add_business_days(ax: AxiomContext, input: AddBusinessDaysQuery) -> BusinessDayResult:
    """Advance or rewind a date by a whole number of BUSINESS days, skipping
    both this calendar's weekend and its public holidays.

    This is the calculation a spreadsheet's WORKDAY cannot do correctly on its
    own: WORKDAY knows only weekends unless the caller hands it a holiday list,
    so three business days after 2026-07-02 in the US is 2026-07-07 to a
    spreadsheet but 2026-07-08 here, because Independence Day is observed on
    Friday 2026-07-03. Positive days count forward, negative count backward, and
    ZERO rolls FORWARD to the nearest business day (inclusive) - so the result is
    always a business day, matching both the wrapped library and WORKDAY(d, 0).
    A result that would land outside the years the calendar covers is a typed
    YEAR_OUT_OF_RANGE error. Never reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        start = cu.parse_date(input.start_date, "start_date")
        cal.check_date(start, "start_date")
        result = cal.step_business_days(start, int(input.days))
        return BusinessDayResult(
            ok=True,
            date=cu.iso(result),
            start_date=cu.iso(start),
            calendar_days_moved=(result - start).days,
            weekday=cu.weekday_enum(result),
            unchanged=(result == start),
        )
    except cu.CalendarError as exc:
        return BusinessDayResult(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return BusinessDayResult(ok=False, error=Error(code="INTERNAL", message=str(exc)))

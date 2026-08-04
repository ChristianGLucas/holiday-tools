from gen.messages_pb2 import BusinessDayCount, Error, RangeQuery
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def count_business_days(ax: AxiomContext, input: RangeQuery) -> BusinessDayCount:
    """Count the working days between two caller-supplied dates on a country or
    financial-market calendar, excluding weekends AND public holidays.

    The range is INCLUSIVE of both endpoints, so a range covering one single
    working day counts 1. Alongside the count it returns the full partition of
    the range - calendar days, weekend days, and the working days actually lost
    to holidays - which always sum back to the calendar-day total, so the answer
    is auditable rather than a bare number. Use it for SLA windows, turnaround
    times, payment terms and accrual periods. Never reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        start = cu.parse_date(input.start_date, "start_date")
        end = cu.parse_date(input.end_date, "end_date")
        cu.check_range(start, end)
        cal.check_date(start, "start_date")
        cal.check_date(end, "end_date")
        business = weekend = holiday = total = 0
        for d in cu.daterange(start, end):
            total += 1
            is_weekend = cal.is_weekend(d)
            is_holiday = cal.is_holiday(d)
            if is_weekend:
                weekend += 1
            elif is_holiday:
                holiday += 1
            else:
                business += 1
        return BusinessDayCount(
            ok=True,
            business_days=business,
            calendar_days=total,
            weekend_days=weekend,
            holiday_days=holiday,
            window_start=cu.iso(start),
            window_end=cu.iso(end),
        )
    except cu.CalendarError as exc:
        return BusinessDayCount(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return BusinessDayCount(ok=False, error=Error(code="INTERNAL", message=str(exc)))

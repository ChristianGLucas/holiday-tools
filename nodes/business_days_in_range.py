from gen.messages_pb2 import (
    BusinessDayList, Error, HolidayOccurrence, NonBusinessDay, RangeQuery,
)
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def business_days_in_range(ax: AxiomContext, input: RangeQuery) -> BusinessDayList:
    """List every working day inside a caller-supplied date range, plus every
    day that was skipped and the reason it was skipped.

    Where CountBusinessDays returns the number, this returns the days themselves
    - the dates to schedule work on, bill for, or iterate over - together with an
    audit trail naming each skipped day as a WEEKEND, a HOLIDAY, or both, and
    the holidays responsible. That makes a surprising count explainable instead
    of merely wrong-looking. The range is inclusive of both endpoints. Offline,
    deterministic, and never reads the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        start = cu.parse_date(input.start_date, "start_date")
        end = cu.parse_date(input.end_date, "end_date")
        cu.check_range(start, end)
        cal.check_date(start, "start_date")
        cal.check_date(end, "end_date")
        business = []
        skipped = []
        for d in cu.daterange(start, end):
            if cal.is_business_day(d):
                business.append(cu.iso(d))
                continue
            skipped.append(
                NonBusinessDay(
                    date=cu.iso(d),
                    reason=cal.reason(d),
                    weekday=cu.weekday_enum(d),
                    holidays=[
                        HolidayOccurrence(
                            date=o["date"], name=o["name"], observed=o["observed"],
                            category=o["category"], weekday=o["weekday"],
                        )
                        for o in cal.holidays_on(d)
                    ],
                )
            )
        return BusinessDayList(
            ok=True,
            business_days=business,
            non_business_days=skipped,
            business_day_count=len(business),
            window_start=cu.iso(start),
            window_end=cu.iso(end),
        )
    except cu.CalendarError as exc:
        return BusinessDayList(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return BusinessDayList(ok=False, error=Error(code="INTERNAL", message=str(exc)))

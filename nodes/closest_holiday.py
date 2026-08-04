from gen.messages_pb2 import ClosestHolidayResult, ClosestQuery, Error, HolidayOccurrence
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def closest_holiday(ax: AxiomContext, input: ClosestQuery) -> ClosestHolidayResult:
    """Find the nearest public holiday before or after a caller-supplied date on
    a country or financial-market calendar.

    The search is STRICT - a holiday falling on the queried date itself is not
    returned - so this answers "what is the next day off after this date?" and,
    searching BACKWARD, "when was the last one?". Returns the holiday plus how
    many calendar days away it is. When the search runs past the end of the
    years the calendar covers without finding one, found is false with ok still
    true, rather than erroring. Offline and deterministic; the starting date is
    always the caller's, never the wall clock.
    """
    try:
        cal = cu.resolve(input.calendar)
        d = cu.parse_date(input.date, "date")
        cal.check_date(d, "date")
        direction = input.direction
        if direction not in (cu.SEARCH_DIRECTION_UNSPECIFIED, cu.FORWARD, cu.BACKWARD):
            raise cu.CalendarError(
                "INVALID_ARGUMENT",
                f"direction={direction} is not a known value. Use FORWARD or BACKWARD.",
            )
        occurrence, days_away = cal.closest_holiday(d, direction)
        if occurrence is None:
            return ClosestHolidayResult(ok=True, found=False)
        return ClosestHolidayResult(
            ok=True,
            found=True,
            holiday=HolidayOccurrence(
                date=occurrence["date"], name=occurrence["name"],
                observed=occurrence["observed"], category=occurrence["category"],
                weekday=occurrence["weekday"],
            ),
            days_away=days_away,
        )
    except cu.CalendarError as exc:
        return ClosestHolidayResult(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return ClosestHolidayResult(ok=False, error=Error(code="INTERNAL", message=str(exc)))

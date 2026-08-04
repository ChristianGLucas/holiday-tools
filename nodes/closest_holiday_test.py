from gen.messages_pb2 import CalendarSpec, ClosestHolidayResult, ClosestQuery
from nodes.closest_holiday import closest_holiday

FORWARD, BACKWARD = 1, 2


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(d, direction=0, **spec_kw):
    return closest_holiday(
        _Ctx(), ClosestQuery(calendar=CalendarSpec(**spec_kw), date=d, direction=direction))


def test_forward_finds_the_next_holiday_with_the_day_gap():
    """From Wednesday 2026-07-01 the next US holiday is the observed
    Independence Day on Friday 2026-07-03, two days later."""
    r = _run("2026-07-01", FORWARD, country="US")
    assert r.ok, r.error
    assert r.found is True
    assert r.holiday.date == "2026-07-03"
    assert r.holiday.observed is True
    assert r.days_away == 2


def test_backward_finds_the_previous_holiday():
    """Looking back from 2026-07-10, the most recent US holiday is 2026-07-04
    itself (the actual date), six days earlier."""
    r = _run("2026-07-10", BACKWARD, country="US")
    assert r.ok, r.error
    assert r.found is True and r.holiday.date == "2026-07-04"
    assert r.days_away == 6


def test_default_direction_is_forward():
    assert _run("2026-07-01", country="US").holiday.date == \
        _run("2026-07-01", FORWARD, country="US").holiday.date


def test_search_is_strict_and_skips_the_queried_date_itself():
    """2026-07-04 IS a holiday, but searching forward from it must return the
    NEXT one, never itself."""
    r = _run("2026-07-04", FORWARD, country="US")
    assert r.ok and r.found is True
    assert r.holiday.date != "2026-07-04"
    assert r.holiday.date > "2026-07-04"
    assert r.days_away > 0


def test_days_away_is_always_positive_in_both_directions():
    for direction in (FORWARD, BACKWARD):
        r = _run("2026-07-10", direction, country="US")
        assert r.ok and r.days_away > 0, direction


def test_running_off_the_calendar_coverage_is_found_false_not_an_error():
    """The last year the US calendar covers is 2100; searching forward from its
    final day must report found=false with ok still true."""
    r = _run("2100-12-31", FORWARD, country="US")
    assert r.ok is True
    assert r.found is False
    assert r.days_away == 0
    assert r.error.code == ""


def test_market_calendar_answers_differently_from_its_country():
    """The NYSE closes on Good Friday 2026-04-03; the US federal calendar does
    not, so searching forward from 2026-04-01 gives different answers."""
    country = _run("2026-04-01", FORWARD, country="US")
    market = _run("2026-04-01", FORWARD, market="NYSE")
    assert country.ok and market.ok
    assert market.holiday.date == "2026-04-03"
    assert market.holiday.name == "Good Friday"
    assert country.holiday.date != "2026-04-03"


def test_bad_input_is_structured():
    assert _run("nope", FORWARD, country="US").error.code == "INVALID_DATE"
    assert _run("2026-07-01", 42, country="US").error.code == "INVALID_ARGUMENT"
    assert _run("2026-07-01", FORWARD, market="NOPE").error.code == "UNKNOWN_MARKET"
    assert isinstance(_run("2026-07-01", FORWARD, country="US"), ClosestHolidayResult)

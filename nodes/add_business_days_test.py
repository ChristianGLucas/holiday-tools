from datetime import date, timedelta

from gen.messages_pb2 import AddBusinessDaysQuery, BusinessDayResult, CalendarSpec, ExtraHoliday
from nodes.add_business_days import add_business_days
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(start, days, **spec_kw):
    return add_business_days(
        _Ctx(),
        AddBusinessDaysQuery(calendar=CalendarSpec(**spec_kw), start_date=start, days=days),
    )


def test_skips_a_holiday_and_a_weekend_together():
    """Thursday 2026-07-02 + 3 US business days.

    Fri 07-03 is Independence Day (observed), Sat 07-04 and Sun 07-05 are the
    weekend, so the three working days are Mon 07-06, Tue 07-07, Wed 07-08.
    """
    r = _run("2026-07-02", 3, country="US")
    assert r.ok, r.error
    assert r.date == "2026-07-08"
    assert r.calendar_days_moved == 6
    assert r.unchanged is False


def test_holiday_awareness_is_what_makes_it_differ_from_a_spreadsheet():
    """A weekend-only calculation (Excel WORKDAY with no holiday list) answers
    2026-07-07. The correct holiday-aware answer is one working day later,
    because Independence Day is observed on Friday 2026-07-03."""
    naive = oracle.naive_add_weekdays(date(2026, 7, 2), 3)
    assert naive == date(2026, 7, 7), "contrast oracle must be the holiday-blind answer"
    r = _run("2026-07-02", 3, country="US")
    assert r.ok and r.date == "2026-07-08"
    assert r.date != naive.strftime("%Y-%m-%d"), "the holiday must actually be counted"


def test_no_holiday_in_the_way_matches_the_naive_oracle():
    """When no holiday intervenes, the answer must agree with plain weekday
    arithmetic — otherwise the weekend logic itself is wrong."""
    start = date(2026, 9, 14)  # a Monday, no US holidays that week
    for n in (1, 2, 3, 4, 5, 10):
        r = _run(start.strftime("%Y-%m-%d"), n, country="US")
        assert r.ok, r.error
        assert r.date == oracle.naive_add_weekdays(start, n).strftime("%Y-%m-%d"), n


def test_negative_days_rewind_and_round_trip():
    forward = _run("2026-07-02", 3, country="US")
    back = _run(forward.date, -3, country="US")
    assert back.ok, back.error
    assert back.date == "2026-07-02", "rewinding must undo the advance exactly"
    assert back.calendar_days_moved == -6


def test_zero_days_on_a_business_day_is_unchanged():
    r = _run("2026-07-06", 0, country="US")
    assert r.ok, r.error
    assert r.date == "2026-07-06"
    assert r.unchanged is True and r.calendar_days_moved == 0


def test_zero_days_on_a_non_business_day_rolls_forward():
    """Documented, tested side of the ambiguity: zero rolls FORWARD to the
    nearest business day, matching the wrapped library and Excel WORKDAY(d, 0).
    2026-07-04 is a Saturday and Independence Day, 07-05 is Sunday."""
    r = _run("2026-07-04", 0, country="US")
    assert r.ok, r.error
    assert r.date == "2026-07-06"
    assert r.unchanged is False


def test_result_is_always_a_business_day():
    from nodes.is_business_day import is_business_day
    from gen.messages_pb2 import DateQuery
    for start, n in (("2026-07-04", 0), ("2026-07-02", 3), ("2026-07-08", -3),
                     ("2026-12-24", 5), ("2026-01-01", 1)):
        r = _run(start, n, country="US")
        assert r.ok, (start, n, r.error)
        check = is_business_day(
            _Ctx(), DateQuery(calendar=CalendarSpec(country="US"), date=r.date))
        assert check.is_business_day is True, (start, n, r.date)


def test_extra_holiday_is_skipped_too():
    """A company shutdown on Monday 2026-07-06 pushes the answer to Tuesday."""
    r = _run("2026-07-02", 1, country="US",
             extra_holidays=[ExtraHoliday(date="2026-07-06", name="Shutdown")])
    assert r.ok, r.error
    assert r.date == "2026-07-07"


def test_crossing_out_of_calendar_coverage_is_typed():
    r = _run("2100-12-20", 30, country="US")
    assert r.ok is False
    assert r.error.code == "YEAR_OUT_OF_RANGE"
    assert "Traceback" not in r.error.message


def test_bad_input_is_structured():
    assert _run("nonsense", 3, country="US").error.code == "INVALID_DATE"
    assert _run("2026-07-02", 3, country="ZZ").error.code == "UNKNOWN_COUNTRY"
    assert _run("2026-07-02", 3).error.code == "INVALID_CALENDAR_SPEC"
    assert isinstance(_run("2026-07-02", 3, country="US"), BusinessDayResult)

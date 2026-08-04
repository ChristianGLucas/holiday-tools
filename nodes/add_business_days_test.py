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


def test_REGRESSION_workday_2026_07_02_plus_3_is_07_08_not_07_07():
    """THE NAMED REGRESSION CASE for this package's reason to exist.

    Ground truth is INDEPENDENT of the wrapped library — it is US federal law
    (5 U.S.C. 6103): a holiday falling on a Saturday is observed on the
    preceding Friday. 2026-07-04 IS a Saturday, so Independence Day 2026 is
    observed on Friday 2026-07-03. Counting three business days from Thursday
    2026-07-02:

        Fri 07-03  observed Independence Day  -> skipped
        Sat 07-04  weekend (and the actual holiday)
        Sun 07-05  weekend
        Mon 07-06  business day 1
        Tue 07-07  business day 2
        Wed 07-08  business day 3   <- correct answer

    The already-published catalog answer for this exact input is WRONG by one
    day and gives no error: christiangeorgelucas/spreadsheet-formula-tools
    Evaluate("WORKDAY(DATE(2026,7,2),3)") was live-invoked on 2026-08-04 and
    returned Excel serial 46210 = 2026-07-07, because Excel's WORKDAY has no
    holiday calendar behind it unless the caller supplies one.

    This single case simultaneously proves the package is correct, proves it is
    not a duplicate of what already exists, and demonstrates the exact silent
    user harm it prevents.
    """
    # Independent ground truth: the actual date is a Saturday, hence observed Friday.
    assert oracle.US_INDEPENDENCE_DAY_2026 == date(2026, 7, 4)
    assert oracle.US_INDEPENDENCE_DAY_2026.isoweekday() == 6, "must be a Saturday"
    assert oracle.US_INDEPENDENCE_DAY_2026_OBSERVED == date(2026, 7, 3)
    assert oracle.US_INDEPENDENCE_DAY_2026_OBSERVED.isoweekday() == 5, "observed Friday"

    # The holiday-blind answer — what a spreadsheet WORKDAY returns (serial 46210).
    naive = oracle.naive_add_weekdays(date(2026, 7, 2), 3)
    assert naive == date(2026, 7, 7), "contrast oracle must be the holiday-blind answer"
    assert _excel_serial(naive) == 46210, "must match the serial observed live"

    # This package's answer.
    r = _run("2026-07-02", 3, country="US")
    assert r.ok, r.error
    assert r.date == "2026-07-08", "the whole reason this package exists"
    assert r.date != naive.strftime("%Y-%m-%d"), "the holiday must actually be counted"

    # And the skipped Friday must be skipped BECAUSE of the observed holiday,
    # not incidentally — otherwise this test could pass for the wrong reason.
    from nodes.is_business_day import is_business_day
    from gen.messages_pb2 import DateQuery
    friday = is_business_day(
        _Ctx(), DateQuery(calendar=CalendarSpec(country="US"), date="2026-07-03"))
    assert friday.ok and friday.is_business_day is False
    assert friday.reason == 3, "HOLIDAY, not WEEKEND — 2026-07-03 is a Friday"
    assert friday.holidays[0].observed is True


def _excel_serial(d: date) -> int:
    """Excel's 1900-system serial number, for comparing against a spreadsheet."""
    return (d - date(1899, 12, 30)).days


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

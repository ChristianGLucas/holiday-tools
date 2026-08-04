from datetime import date

from gen.messages_pb2 import BusinessDayCount, CalendarSpec, RangeQuery
from nodes.count_business_days import count_business_days
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(start, end, **spec_kw):
    return count_business_days(
        _Ctx(), RangeQuery(calendar=CalendarSpec(**spec_kw), start_date=start, end_date=end))


def test_counts_across_a_holiday_and_a_weekend_together():
    """Mon 2026-06-29 .. Fri 2026-07-10 inclusive is 12 calendar days:
    2 weekend days (Sat 07-04, Sun 07-05) and 1 working day lost to the
    observed Independence Day (Fri 07-03), leaving 9 business days."""
    r = _run("2026-06-29", "2026-07-10", country="US")
    assert r.ok, r.error
    assert r.calendar_days == 12
    assert r.weekend_days == 2
    assert r.holiday_days == 1
    assert r.business_days == 9


def test_differs_from_a_holiday_blind_count_by_exactly_the_holidays():
    """A spreadsheet NETWORKDAYS with no holiday list answers 10."""
    naive = oracle.naive_count_weekdays(date(2026, 6, 29), date(2026, 7, 10))
    assert naive == 10
    r = _run("2026-06-29", "2026-07-10", country="US")
    assert r.business_days == naive - r.holiday_days == 9


def test_partition_always_sums_back_to_the_calendar_days():
    """The invariant that makes the count auditable rather than a bare number."""
    for start, end, country in (
        ("2026-01-01", "2026-12-31", "US"),
        ("2026-01-01", "2026-12-31", "IL"),
        ("2026-06-29", "2026-07-10", "US"),
        ("2026-03-01", "2026-03-01", "US"),
        ("2025-12-15", "2026-01-15", "DE"),
    ):
        r = _run(start, end, country=country)
        assert r.ok, (start, end, country, r.error)
        assert r.business_days + r.weekend_days + r.holiday_days == r.calendar_days, \
            (start, end, country)


def test_range_is_inclusive_of_both_endpoints():
    """A single business day counts 1, not 0."""
    one = _run("2026-07-06", "2026-07-06", country="US")
    assert one.ok and one.business_days == 1 and one.calendar_days == 1
    two = _run("2026-07-06", "2026-07-07", country="US")
    assert two.business_days == 2 and two.calendar_days == 2
    # A single non-business day counts 0 business days but 1 calendar day.
    holiday = _run("2026-07-04", "2026-07-04", country="US")
    assert holiday.business_days == 0 and holiday.calendar_days == 1
    assert holiday.weekend_days == 1


def test_fri_sat_weekend_country_counts_differently_over_the_same_range():
    """The same week yields different working days in Israel and the US."""
    us = _run("2026-09-13", "2026-09-19", country="US")
    il = _run("2026-09-13", "2026-09-19", country="IL")
    assert us.ok and il.ok
    assert us.weekend_days == 2 and il.weekend_days == 2
    # Sunday is a working day in Israel and a weekend day in the US, so the
    # weekend days fall on different dates even though the counts match.
    assert us.calendar_days == il.calendar_days == 7
    assert us.business_days != il.business_days or us.holiday_days != il.holiday_days


def test_reversed_range_is_rejected_not_silently_swapped():
    r = _run("2026-07-10", "2026-06-29", country="US")
    assert r.ok is False and r.error.code == "INVALID_DATE_RANGE"
    assert r.business_days == 0


def test_bad_input_is_structured():
    assert _run("bogus", "2026-07-10", country="US").error.code == "INVALID_DATE"
    assert _run("1500-01-01", "1500-12-31", country="US").error.code == "YEAR_OUT_OF_RANGE"
    assert isinstance(_run("2026-07-06", "2026-07-06", country="US"), BusinessDayCount)

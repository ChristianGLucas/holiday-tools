from datetime import date

from gen.messages_pb2 import CalendarSpec, HolidayList, NameQuery
from nodes.find_holiday_by_name import find_holiday_by_name
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(name, start_year, end_year, **spec_kw):
    return find_holiday_by_name(
        _Ctx(), NameQuery(calendar=CalendarSpec(**spec_kw), name=name,
                          start_year=start_year, end_year=end_year))


def test_moving_holiday_dates_match_the_independent_nth_weekday_rule():
    """Thanksgiving is the 4th Thursday of November — a rule, not a fixed date.
    The expected dates are derived arithmetically, not read from the library."""
    r = _run("Thanksgiving", 2026, 2028, country="US")
    assert r.ok, r.error
    expected = [oracle.nth_weekday(y, 11, 4, 4).isoformat() for y in (2026, 2027, 2028)]
    assert expected == ["2026-11-26", "2027-11-25", "2028-11-23"]
    assert [h.date for h in r.holidays] == expected


def test_easter_derived_dates_match_the_computus_across_years():
    for year in (2026, 2027, 2028):
        r = _run("Good Friday", year, year, country="DE")
        assert r.ok, (year, r.error)
        assert r.count == 1, year
        assert r.holidays[0].date == (oracle.easter_sunday(year) -
                                      __import__("datetime").timedelta(days=2)).isoformat()


def test_matching_is_case_insensitive_and_substring():
    lower = _run("thanksgiving", 2026, 2026, country="US")
    upper = _run("THANKSGIVING", 2026, 2026, country="US")
    assert lower.ok and upper.ok
    assert [h.date for h in lower.holidays] == [h.date for h in upper.holidays] == ["2026-11-26"]
    christmas = _run("Christmas", 2026, 2026, country="US")
    assert christmas.ok and christmas.count >= 1
    assert all("christmas" in h.name.casefold() for h in christmas.holidays)


def test_finds_both_actual_and_observed_dates():
    r = _run("Independence", 2026, 2026, country="US")
    assert r.ok, r.error
    dates = {h.date: h.observed for h in r.holidays}
    assert dates.get("2026-07-04") is False
    assert dates.get("2026-07-03") is True


def test_no_match_is_an_empty_success_not_an_error():
    r = _run("Definitely Not A Holiday", 2026, 2026, country="US")
    assert r.ok is True and r.count == 0 and r.error.code == ""


def test_window_reflects_the_year_span():
    r = _run("Christmas", 2026, 2027, country="US")
    assert r.window_start == "2026-01-01" and r.window_end == "2027-12-31"


def test_bad_input_is_structured():
    assert _run("", 2026, 2026, country="US").error.code == "INVALID_ARGUMENT"
    assert _run("Christmas", 2027, 2026, country="US").error.code == "INVALID_ARGUMENT"
    assert _run("Christmas", 0, 0, country="US").error.code == "INVALID_ARGUMENT"
    assert _run("Christmas", 1500, 1600, country="US").error.code == "YEAR_OUT_OF_RANGE"
    assert isinstance(_run("Christmas", 2026, 2026, country="US"), HolidayList)

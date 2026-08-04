from datetime import date

from gen.messages_pb2 import CalendarSpec, HolidayList, YearQuery
from nodes.holidays_in_year import holidays_in_year
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(year, **spec_kw):
    return holidays_in_year(_Ctx(), YearQuery(calendar=CalendarSpec(**spec_kw), year=year))


def _dates(result):
    return {h.date for h in result.holidays}


def test_us_2026_matches_independently_derived_federal_dates():
    """Every date here is derived from the published rule (fixed date, or nth
    weekday computed by plain arithmetic) — never read back from the library."""
    r = _run(2026, country="US")
    assert r.ok, r.error
    expected = {
        "2026-01-01",                                          # New Year's Day
        oracle.nth_weekday(2026, 1, 1, 3).isoformat(),          # MLK, 3rd Mon Jan
        oracle.nth_weekday(2026, 2, 1, 3).isoformat(),          # Washington, 3rd Mon Feb
        oracle.nth_weekday(2026, 5, 1, -1).isoformat(),         # Memorial, last Mon May
        "2026-06-19",                                          # Juneteenth
        "2026-07-04",                                          # Independence Day
        oracle.nth_weekday(2026, 9, 1, 1).isoformat(),          # Labor, 1st Mon Sep
        oracle.nth_weekday(2026, 10, 1, 2).isoformat(),         # Columbus, 2nd Mon Oct
        "2026-11-11",                                          # Veterans Day
        oracle.nth_weekday(2026, 11, 4, 4).isoformat(),         # Thanksgiving, 4th Thu Nov
        "2026-12-25",                                          # Christmas
    }
    missing = expected - _dates(r)
    assert not missing, f"missing federal holidays: {sorted(missing)}"
    # Spot-check two of the derived values so a broken oracle cannot pass.
    assert oracle.nth_weekday(2026, 11, 4, 4) == date(2026, 11, 26)
    assert oracle.nth_weekday(2026, 5, 1, -1) == date(2026, 5, 25)


def test_window_covers_the_whole_calendar_year():
    r = _run(2026, country="US")
    assert r.window_start == "2026-01-01" and r.window_end == "2026-12-31"
    assert r.count == len(r.holidays) > 0
    for h in r.holidays:
        assert h.date.startswith("2026-")


def test_results_are_sorted_by_date():
    r = _run(2026, country="DE")
    assert r.ok and [h.date for h in r.holidays] == sorted(h.date for h in r.holidays)


def test_subdivision_is_a_superset_of_the_national_calendar():
    national = _run(2026, country="DE")
    bavaria = _run(2026, country="DE", subdivision="BY")
    assert national.ok and bavaria.ok
    assert _dates(national) <= _dates(bavaria), "a Land keeps the national holidays"
    extra = _dates(bavaria) - _dates(national)
    assert oracle.DE_BY_EPIPHANY_2026.isoformat() in extra
    assert bavaria.count > national.count


def test_texas_adds_state_holidays_the_federal_calendar_lacks():
    federal = _run(2026, country="US")
    texas = _run(2026, country="US", subdivision="TX")
    assert oracle.US_TX_INDEPENDENCE_2026.isoformat() not in _dates(federal)
    assert oracle.US_TX_INDEPENDENCE_2026.isoformat() in _dates(texas)


def test_subdivision_alias_resolves_like_the_code():
    by_code = _run(2026, country="US", subdivision="TX")
    by_name = _run(2026, country="US", subdivision="Texas")
    assert by_name.ok, by_name.error
    assert _dates(by_code) == _dates(by_name)


def test_observed_rule_changes_the_list():
    both = _run(2026, country="US")
    actual = _run(2026, country="US", observed_rule=2)
    assert both.ok and actual.ok
    assert "2026-07-03" in _dates(both)
    assert "2026-07-03" not in _dates(actual)
    assert "2026-07-04" in _dates(actual)
    assert any(h.observed for h in both.holidays)
    assert not any(h.observed for h in actual.holidays)


def test_year_out_of_range_errors_rather_than_returning_nothing():
    """The whole point: an empty list is indistinguishable from a quiet year."""
    for bad_year in (1500, 2200):
        r = _run(bad_year, country="US")
        assert r.ok is False, bad_year
        assert r.error.code == "YEAR_OUT_OF_RANGE", bad_year
        assert r.count == 0 and len(r.holidays) == 0


def test_bad_input_is_structured():
    assert _run(2026, country="ZZ").error.code == "UNKNOWN_COUNTRY"
    assert _run(0, country="US").error.code == "INVALID_ARGUMENT"
    assert _run(2026, country="US", categories=["nope"]).error.code == "UNSUPPORTED_CATEGORY"
    assert isinstance(_run(2026, country="US"), HolidayList)

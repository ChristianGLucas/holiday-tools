from datetime import timedelta

from gen.messages_pb2 import CalendarSpec, HolidayList, RangeQuery
from nodes.holidays_in_range import holidays_in_range
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(start, end, **spec_kw):
    return holidays_in_range(
        _Ctx(), RangeQuery(calendar=CalendarSpec(**spec_kw), start_date=start, end_date=end))


def test_finds_the_easter_cluster_using_the_independent_computus():
    """Good Friday, Easter Monday and Ascension are all Easter-derived. Easter
    2026 is computed here with the Gregorian computus, not read from the
    library."""
    easter = oracle.easter_sunday(2026)
    r = _run((easter - timedelta(days=7)).isoformat(),
             (easter + timedelta(days=7)).isoformat(), country="DE")
    assert r.ok, r.error
    by_date = {h.date: h.name for h in r.holidays}
    assert by_date.get((easter - timedelta(days=2)).isoformat()) == "Good Friday"
    assert by_date.get((easter + timedelta(days=1)).isoformat()) == "Easter Monday"


def test_range_is_inclusive_of_both_endpoints():
    exact = _run("2026-07-04", "2026-07-04", country="US")
    assert exact.ok and exact.count == 1
    assert exact.holidays[0].name == "Independence Day"


def test_spans_a_year_boundary():
    r = _run("2025-12-24", "2026-01-02", country="US")
    assert r.ok, r.error
    dates = {h.date for h in r.holidays}
    assert "2025-12-25" in dates and "2026-01-01" in dates


def test_excludes_holidays_outside_the_window():
    r = _run("2026-07-06", "2026-07-31", country="US")
    assert r.ok
    assert all("2026-07-06" <= h.date <= "2026-07-31" for h in r.holidays)
    assert "2026-07-04" not in {h.date for h in r.holidays}


def test_empty_window_is_a_valid_empty_answer_not_an_error():
    """A window that genuinely contains no holidays is ok with count 0 — the
    distinction that YEAR_OUT_OF_RANGE exists to preserve."""
    r = _run("2026-08-03", "2026-08-07", country="US")
    assert r.ok is True and r.count == 0 and len(r.holidays) == 0
    assert r.error.code == ""


def test_reversed_range_is_rejected():
    r = _run("2026-07-31", "2026-07-01", country="US")
    assert r.ok is False and r.error.code == "INVALID_DATE_RANGE"


def test_bad_input_is_structured():
    assert _run("2026-99-01", "2026-12-31", country="US").error.code == "INVALID_DATE"
    assert _run("2026-01-01", "2026-12-31", country="US",
                subdivision="NOPE").error.code == "UNKNOWN_SUBDIVISION"
    assert isinstance(_run("2026-07-01", "2026-07-31", country="US"), HolidayList)

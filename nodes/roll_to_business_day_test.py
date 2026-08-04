from gen.messages_pb2 import BusinessDayResult, CalendarSpec, RollQuery
from nodes.roll_to_business_day import roll_to_business_day

FOLLOWING, PRECEDING, MODIFIED_FOLLOWING, MODIFIED_PRECEDING = 1, 2, 3, 4


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(d, convention=0, **spec_kw):
    return roll_to_business_day(
        _Ctx(), RollQuery(calendar=CalendarSpec(**spec_kw), date=d, convention=convention))


def test_following_and_preceding_move_opposite_ways_over_the_same_closure():
    """2026-07-04 is a Saturday; 07-03 carries observed Independence Day and
    07-05 is Sunday, so the nearest business days are 07-02 and 07-06."""
    assert _run("2026-07-04", FOLLOWING, country="US").date == "2026-07-06"
    assert _run("2026-07-04", PRECEDING, country="US").date == "2026-07-02"


def test_default_convention_is_following():
    assert _run("2026-07-04", country="US").date == "2026-07-06"


def test_a_business_day_is_unchanged_under_every_convention():
    for convention in (0, FOLLOWING, PRECEDING, MODIFIED_FOLLOWING, MODIFIED_PRECEDING):
        r = _run("2026-07-06", convention, country="US")
        assert r.ok, r.error
        assert r.date == "2026-07-06" and r.unchanged is True
        assert r.calendar_days_moved == 0


def test_modified_following_reverses_rather_than_crossing_a_month_boundary():
    """Sunday 2026-05-31 is the last day of May. Plain FOLLOWING lands on
    Monday 2026-06-01, in the NEXT month; MODIFIED_FOLLOWING must go back to
    Friday 2026-05-29 to stay inside May."""
    plain = _run("2026-05-31", FOLLOWING, country="US")
    modified = _run("2026-05-31", MODIFIED_FOLLOWING, country="US")
    assert plain.ok and plain.date == "2026-06-01"
    assert modified.ok and modified.date == "2026-05-29"
    assert modified.calendar_days_moved == -2


def test_modified_preceding_reverses_rather_than_crossing_backwards():
    """Sunday 2026-03-01 is the first day of March. Plain PRECEDING lands on
    Friday 2026-02-27, in the PREVIOUS month; MODIFIED_PRECEDING must go
    forward to Monday 2026-03-02 to stay inside March."""
    plain = _run("2026-03-01", PRECEDING, country="US")
    modified = _run("2026-03-01", MODIFIED_PRECEDING, country="US")
    assert plain.ok and plain.date == "2026-02-27"
    assert modified.ok and modified.date == "2026-03-02"


def test_result_is_always_a_business_day():
    from nodes.is_business_day import is_business_day
    from gen.messages_pb2 import DateQuery
    for d in ("2026-07-04", "2026-05-31", "2026-03-01", "2026-12-25", "2026-01-01"):
        for convention in (FOLLOWING, PRECEDING, MODIFIED_FOLLOWING, MODIFIED_PRECEDING):
            r = _run(d, convention, country="US")
            assert r.ok, (d, convention, r.error)
            check = is_business_day(
                _Ctx(), DateQuery(calendar=CalendarSpec(country="US"), date=r.date))
            assert check.is_business_day is True, (d, convention, r.date)


def test_respects_a_fri_sat_weekend():
    """Friday 2026-07-10 is a weekend day in Israel; FOLLOWING rolls to Sunday
    2026-07-12, which is a normal working day there."""
    r = _run("2026-07-10", FOLLOWING, country="IL")
    assert r.ok, r.error
    assert r.date == "2026-07-12"


def test_bad_input_is_structured():
    assert _run("2026-02-30", FOLLOWING, country="US").error.code == "INVALID_DATE"
    assert _run("2026-07-04", 99, country="US").error.code == "INVALID_ARGUMENT"
    assert isinstance(_run("2026-07-04", FOLLOWING, country="US"), BusinessDayResult)

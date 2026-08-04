from gen.messages_pb2 import BusinessDayList, CalendarSpec, RangeQuery
from nodes.business_days_in_range import business_days_in_range
from nodes.count_business_days import count_business_days

WEEKEND, HOLIDAY, WEEKEND_AND_HOLIDAY = 2, 3, 4


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(start, end, **spec_kw):
    return business_days_in_range(
        _Ctx(), RangeQuery(calendar=CalendarSpec(**spec_kw), start_date=start, end_date=end))


def test_lists_the_exact_working_days_of_the_independence_day_week():
    r = _run("2026-06-29", "2026-07-10", country="US")
    assert r.ok, r.error
    assert list(r.business_days) == [
        "2026-06-29", "2026-06-30", "2026-07-01", "2026-07-02",
        "2026-07-06", "2026-07-07", "2026-07-08", "2026-07-09", "2026-07-10",
    ]
    assert r.business_day_count == 9


def test_every_skipped_day_is_explained():
    r = _run("2026-06-29", "2026-07-10", country="US")
    skipped = {n.date: n for n in r.non_business_days}
    assert set(skipped) == {"2026-07-03", "2026-07-04", "2026-07-05"}
    assert skipped["2026-07-03"].reason == HOLIDAY
    assert [h.name for h in skipped["2026-07-03"].holidays] == ["Independence Day (observed)"]
    assert skipped["2026-07-04"].reason == WEEKEND_AND_HOLIDAY
    assert skipped["2026-07-05"].reason == WEEKEND
    assert len(skipped["2026-07-05"].holidays) == 0


def test_agrees_with_count_business_days():
    """The list and the count must never disagree."""
    for start, end, country in (
        ("2026-06-29", "2026-07-10", "US"),
        ("2026-01-01", "2026-03-31", "DE"),
        ("2026-09-13", "2026-09-19", "IL"),
    ):
        listed = _run(start, end, country=country)
        counted = count_business_days(
            _Ctx(), RangeQuery(calendar=CalendarSpec(country=country),
                               start_date=start, end_date=end))
        assert listed.business_day_count == counted.business_days, (start, end, country)
        assert len(listed.business_days) + len(listed.non_business_days) == counted.calendar_days


def test_every_listed_day_is_inside_the_window_and_ascending():
    r = _run("2026-06-29", "2026-07-10", country="US")
    assert r.window_start == "2026-06-29" and r.window_end == "2026-07-10"
    assert list(r.business_days) == sorted(r.business_days)
    for d in r.business_days:
        assert "2026-06-29" <= d <= "2026-07-10"


def test_bad_input_is_structured():
    bad = _run("2026-07-10", "2026-06-29", country="US")
    assert bad.ok is False and bad.error.code == "INVALID_DATE_RANGE"
    assert len(bad.business_days) == 0
    assert isinstance(bad, BusinessDayList)

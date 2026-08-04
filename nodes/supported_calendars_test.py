from gen.messages_pb2 import CalendarCatalog, CalendarCatalogQuery
from nodes.supported_calendars import supported_calendars


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(kind="", contains=""):
    return supported_calendars(_Ctx(), CalendarCatalogQuery(kind=kind, contains=contains))


def test_lists_both_country_and_market_calendars():
    r = _run()
    assert r.ok, r.error
    kinds = {c.kind for c in r.calendars}
    assert kinds == {"country", "market"}
    assert r.count == len(r.calendars)
    # The wrapped library ships hundreds of national calendars and a couple of
    # dozen market ones; assert real scale, not merely non-emptiness.
    assert sum(1 for c in r.calendars if c.kind == "country") > 100
    assert sum(1 for c in r.calendars if c.kind == "market") >= 20


def test_kind_filter_narrows_the_result():
    countries = _run(kind="country")
    markets = _run(kind="market")
    assert countries.ok and markets.ok
    assert all(c.kind == "country" for c in countries.calendars)
    assert all(c.kind == "market" for c in markets.calendars)
    assert countries.count + markets.count == _run().count


def test_contains_filter_matches_code_or_name():
    r = _run(contains="united states")
    assert r.ok and r.count >= 1
    assert any(c.code == "US" for c in r.calendars)
    by_code = _run(contains="XNYS")
    assert by_code.ok and any(c.code == "XNYS" for c in by_code.calendars)


def test_entries_carry_usable_codes_and_real_year_ranges():
    r = _run(contains="united states")
    us = next(c for c in r.calendars if c.code == "US")
    assert us.name == "United States"
    assert us.kind == "country"
    assert us.subdivision_count > 50      # 50 states plus territories
    assert us.start_year == 1777 and us.end_year == 2100
    assert "USA" in us.aliases


def test_market_aliases_include_the_familiar_ticker():
    r = _run(kind="market", contains="new york")
    nyse = next(c for c in r.calendars if c.code == "XNYS")
    assert "NYSE" in nyse.aliases, "the familiar code must be discoverable"


def test_every_listed_code_actually_resolves():
    """A discovery node that returns codes the other nodes reject is worse than
    no discovery node. Spot-check a spread of them end to end."""
    from nodes.calendar_info import calendar_info
    from gen.messages_pb2 import CalendarInfoQuery
    listed = _run().calendars
    sample = listed[::47]
    assert len(sample) > 5
    for entry in sample:
        query = (CalendarInfoQuery(country=entry.code) if entry.kind == "country"
                 else CalendarInfoQuery(market=entry.code))
        detail = calendar_info(_Ctx(), query)
        assert detail.ok, (entry.code, detail.error)
        assert detail.code == entry.code


def test_results_are_sorted_and_deterministic():
    a, b = _run(), _run()
    assert [c.code for c in a.calendars] == [c.code for c in b.calendars]
    assert [(c.kind, c.code) for c in a.calendars] == \
        sorted((c.kind, c.code) for c in a.calendars)


def test_bad_input_is_structured():
    r = _run(kind="planet")
    assert r.ok is False and r.error.code == "INVALID_ARGUMENT"
    assert r.count == 0
    assert isinstance(r, CalendarCatalog)


def test_unmatched_filter_is_an_empty_success():
    r = _run(contains="zzzzz-no-such-calendar")
    assert r.ok is True and r.count == 0 and r.error.code == ""

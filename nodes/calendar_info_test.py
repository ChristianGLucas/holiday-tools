from gen.messages_pb2 import CalendarDetail, CalendarInfoQuery, Weekday
from nodes.calendar_info import calendar_info
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(country="", market=""):
    return calendar_info(_Ctx(), CalendarInfoQuery(country=country, market=market))


def test_reports_the_western_saturday_sunday_weekend():
    r = _run(country="US")
    assert r.ok, r.error
    assert list(r.weekend) == [Weekday.SATURDAY, Weekday.SUNDAY]
    assert r.code == "US" and r.name == "United States" and r.kind == "country"


def test_reports_friday_saturday_weekends_where_they_really_are():
    """The field callers most often get wrong. Every one of these countries
    rests Friday-Saturday, not Saturday-Sunday."""
    for country in oracle.FRI_SAT_WEEKEND_COUNTRIES:
        r = _run(country=country)
        assert r.ok, (country, r.error)
        assert list(r.weekend) == [Weekday.FRIDAY, Weekday.SATURDAY], country


def test_iran_rests_on_friday_alone():
    r = _run(country="IR")
    assert r.ok, r.error
    assert list(r.weekend) == [Weekday.FRIDAY]


def test_subdivisions_carry_codes_and_aliases():
    r = _run(country="US")
    by_code = {s.code: list(s.aliases) for s in r.subdivisions}
    assert "TX" in by_code and "Texas" in by_code["TX"]
    assert "CA" in by_code and "California" in by_code["CA"]
    assert len(r.subdivisions) > 50


def test_german_laender_are_listed():
    r = _run(country="DE")
    codes = {s.code for s in r.subdivisions}
    assert {"BY", "BW", "NW", "SN"} <= codes


def test_year_range_matches_what_the_other_nodes_enforce():
    """CalendarInfo must not advertise a range the query nodes reject."""
    from nodes.holidays_in_year import holidays_in_year
    from gen.messages_pb2 import CalendarSpec, YearQuery
    r = _run(country="US")
    assert r.start_year == 1777 and r.end_year == 2100
    inside = holidays_in_year(
        _Ctx(), YearQuery(calendar=CalendarSpec(country="US"), year=r.end_year))
    assert inside.ok, inside.error
    outside = holidays_in_year(
        _Ctx(), YearQuery(calendar=CalendarSpec(country="US"), year=r.end_year + 1))
    assert outside.ok is False and outside.error.code == "YEAR_OUT_OF_RANGE"


def test_categories_and_languages_are_the_accepted_values():
    r = _run(country="DE")
    assert r.default_category in r.supported_categories
    assert "public" in r.supported_categories
    assert "de" in r.supported_languages
    assert r.default_language in r.supported_languages


def test_market_calendar_detail_and_aliases():
    r = _run(market="NYSE")
    assert r.ok, r.error
    assert r.code == "XNYS" and r.kind == "market"
    assert "NYSE" in r.aliases
    assert list(r.weekend) == [Weekday.SATURDAY, Weekday.SUNDAY]


def test_a_calendar_without_subdivisions_reports_none():
    r = _run(market="NYSE")
    assert len(r.subdivisions) == 0


def test_bad_input_is_structured():
    assert _run(country="ZZ").error.code == "UNKNOWN_COUNTRY"
    assert _run(market="ZZZZ").error.code == "UNKNOWN_MARKET"
    assert _run().error.code == "INVALID_CALENDAR_SPEC"
    assert _run(country="US", market="NYSE").error.code == "INVALID_CALENDAR_SPEC"
    assert isinstance(_run(country="US"), CalendarDetail)

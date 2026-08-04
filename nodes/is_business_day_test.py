from datetime import date

from gen.messages_pb2 import BusinessDayStatus, CalendarSpec, DateQuery, Weekday
from nodes.is_business_day import is_business_day
from nodes import _oracle as oracle

BUSINESS_DAY, WEEKEND, HOLIDAY, WEEKEND_AND_HOLIDAY = 1, 2, 3, 4


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(**kw):
    spec_kw = {k: v for k, v in kw.items() if k != "date"}
    return is_business_day(_Ctx(), DateQuery(calendar=CalendarSpec(**spec_kw), date=kw["date"]))


def test_reason_distinguishes_every_kind_of_non_working_day():
    """A bare boolean loses WHY the office is shut; the reason must not."""
    # 2026-07-06 is a Monday with no holiday.
    assert _run(country="US", date="2026-07-06").reason == BUSINESS_DAY
    # 2026-07-11 is a Saturday with no holiday.
    assert _run(country="US", date="2026-07-11").reason == WEEKEND
    # 2026-07-03 is a Friday carrying the observed Independence Day.
    assert _run(country="US", date="2026-07-03").reason == HOLIDAY
    # 2026-07-04 is a Saturday AND Independence Day itself.
    assert _run(country="US", date="2026-07-04").reason == WEEKEND_AND_HOLIDAY


def test_friday_saturday_weekend_countries_differ_from_the_west():
    """Much of the Middle East rests Friday-Saturday. Hard-coding Sat/Sun gives
    confidently wrong answers there, so this asserts both directions."""
    friday, sunday = "2026-07-10", "2026-07-05"
    # A Friday: a working day in the US, a weekend day in Israel.
    us_fri = _run(country="US", date=friday)
    il_fri = _run(country="IL", date=friday)
    assert us_fri.ok and us_fri.is_business_day is True
    assert il_fri.ok and il_fri.is_business_day is False and il_fri.reason == WEEKEND
    # A Sunday: a weekend day in the US, a working day in Israel.
    us_sun = _run(country="US", date=sunday)
    il_sun = _run(country="IL", date=sunday)
    assert us_sun.ok and us_sun.is_business_day is False and us_sun.reason == WEEKEND
    assert il_sun.ok and il_sun.is_business_day is True and il_sun.reason == BUSINESS_DAY


def test_every_fri_sat_country_treats_friday_as_weekend():
    for country in oracle.FRI_SAT_WEEKEND_COUNTRIES:
        r = _run(country=country, date="2026-07-10")
        assert r.ok, (country, r.error)
        assert r.is_business_day is False, f"{country} should rest on Friday"
        assert r.reason in (WEEKEND, WEEKEND_AND_HOLIDAY), country


def test_weekend_override_models_a_specific_working_week():
    """A six-day operation resting only on Sunday."""
    saturday = "2026-07-11"
    default = _run(country="US", date=saturday)
    assert default.is_business_day is False
    overridden = _run(country="US", date=saturday, weekend_override=[Weekday.SUNDAY])
    assert overridden.ok and overridden.is_business_day is True


def test_market_calendar_differs_from_its_host_country():
    """The NYSE closes on Good Friday; the US federal calendar has no such
    holiday. Same date, same country, different answer."""
    good_friday = (oracle.easter_sunday(2026)).strftime("%Y-%m-%d")
    good_friday = "2026-04-03"
    federal = _run(country="US", date=good_friday)
    market = _run(market="NYSE", date=good_friday)
    assert federal.ok and federal.is_business_day is True
    assert market.ok and market.is_business_day is False
    assert market.reason == HOLIDAY
    assert [h.name for h in market.holidays] == ["Good Friday"]


def test_weekday_field_matches_iso_weekday():
    for iso_date in ("2026-07-06", "2026-07-10", "2026-07-11", "2026-07-12"):
        r = _run(country="US", date=iso_date)
        y, m, d = (int(p) for p in iso_date.split("-"))
        assert r.weekday == date(y, m, d).isoweekday(), iso_date


def test_bad_input_is_structured_never_a_traceback():
    r = _run(country="US", date="2026-02-30")
    assert r.ok is False and r.error.code == "INVALID_DATE"
    assert "Traceback" not in r.error.message
    assert _run(country="XX", date="2026-07-06").error.code == "UNKNOWN_COUNTRY"
    assert isinstance(r, BusinessDayStatus)

from datetime import date, timedelta

from gen.messages_pb2 import CalendarSpec, DateQuery, ExtraHoliday, HolidayStatus
from nodes.is_holiday import is_holiday
from nodes import _oracle as oracle


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _run(**kw):
    spec_kw = {k: v for k, v in kw.items() if k != "date"}
    return is_holiday(_Ctx(), DateQuery(calendar=CalendarSpec(**spec_kw), date=kw["date"]))


def test_fixed_holiday_actual_date():
    """US Independence Day 2026-07-04 — a hand-verified official date."""
    r = _run(country="US", date="2026-07-04")
    assert r.ok, r.error
    assert r.is_holiday is True
    assert [h.name for h in r.holidays] == ["Independence Day"]
    assert r.holidays[0].observed is False
    assert r.holidays[0].category == "public"
    # July 4 2026 is a Saturday, so it is a weekend day and not a business day.
    assert r.weekday == 6 and r.is_weekend is True and r.is_business_day is False


def test_weekend_observed_substitute_is_flagged():
    """Independence Day falls on Saturday 2026-07-04, so US federal law observes
    it on Friday 2026-07-03. The substitute must be flagged, not silently
    conflated with the actual date."""
    r = _run(country="US", date="2026-07-03")
    assert r.ok, r.error
    assert r.is_holiday is True
    assert r.holidays[0].observed is True, "substitute date must be flagged observed"
    assert r.is_weekend is False and r.is_business_day is False
    assert oracle.US_INDEPENDENCE_DAY_2026_OBSERVED == date(2026, 7, 3)


def test_actual_only_rule_drops_the_substitute():
    """ACTUAL_ONLY answers 'when does it really fall', so the Friday substitute
    disappears while the real Saturday date remains."""
    substitute = _run(country="US", date="2026-07-03", observed_rule=2)
    assert substitute.ok and substitute.is_holiday is False
    actual = _run(country="US", date="2026-07-04", observed_rule=2)
    assert actual.ok and actual.is_holiday is True
    assert actual.holidays[0].observed is False


def test_moving_holiday_matches_independent_nth_weekday_rule():
    """US Thanksgiving is the 4th Thursday of November, computed here from plain
    calendar arithmetic rather than from the library."""
    expected = oracle.nth_weekday(2026, 11, 4, 4)
    assert expected == date(2026, 11, 26)
    r = _run(country="US", date=expected.strftime("%Y-%m-%d"))
    assert r.ok, r.error
    assert any("Thanksgiving" in h.name for h in r.holidays)
    # The day before is not Thanksgiving — proves the assertion above can fail.
    before = _run(country="US", date=(expected - timedelta(days=1)).strftime("%Y-%m-%d"))
    assert before.ok and before.is_holiday is False


def test_easter_derived_holiday_matches_independent_computus():
    """Good Friday is Easter Sunday minus two days. Easter 2026 is computed here
    with the Gregorian computus, independently of the wrapped library — the
    classic off-by-one source."""
    easter = oracle.easter_sunday(2026)
    assert easter == date(2026, 4, 5)
    good_friday = easter - timedelta(days=2)
    r = _run(country="DE", date=good_friday.strftime("%Y-%m-%d"))
    assert r.ok, r.error
    assert [h.name for h in r.holidays] == ["Good Friday"]
    easter_monday = _run(country="DE", date=(easter + timedelta(days=1)).strftime("%Y-%m-%d"))
    assert easter_monday.ok and [h.name for h in easter_monday.holidays] == ["Easter Monday"]


def test_subdivision_changes_the_answer_and_never_silently_falls_back():
    """Bavaria observes Epiphany; the German national calendar does not."""
    national = _run(country="DE", date="2026-01-06")
    assert national.ok and national.is_holiday is False
    bavaria = _run(country="DE", subdivision="BY", date="2026-01-06")
    assert bavaria.ok and bavaria.is_holiday is True
    assert [h.name for h in bavaria.holidays] == ["Epiphany"]


def test_unknown_subdivision_is_a_typed_error_not_a_national_fallback():
    r = _run(country="US", subdivision="ZZ", date="2026-07-04")
    assert r.ok is False
    assert r.error.code == "UNKNOWN_SUBDIVISION"
    # The national answer must NOT leak through.
    assert r.is_holiday is False and len(r.holidays) == 0


def test_language_changes_names_not_dates():
    english = _run(country="DE", date="2026-04-03")
    german = _run(country="DE", language="de", date="2026-04-03")
    assert english.ok and german.ok
    assert english.holidays[0].name == "Good Friday"
    assert german.holidays[0].name == "Karfreitag"
    assert english.date == german.date == "2026-04-03"


def test_unsupported_language_is_typed_not_silent_fallback():
    r = _run(country="US", language="zz", date="2026-07-04")
    assert r.ok is False and r.error.code == "UNSUPPORTED_LANGUAGE"


def test_extra_holiday_is_layered_on_top():
    r = _run(country="US", date="2026-07-06",
             extra_holidays=[ExtraHoliday(date="2026-07-06", name="Company Shutdown")])
    assert r.ok, r.error
    assert r.is_holiday is True and r.is_business_day is False
    assert r.holidays[0].name == "Company Shutdown"
    assert r.holidays[0].category == "custom"


def test_year_out_of_range_is_an_error_not_an_empty_list():
    for bad in ("1500-07-04", "2200-07-04"):
        r = _run(country="US", date=bad)
        assert r.ok is False, bad
        assert r.error.code == "YEAR_OUT_OF_RANGE", bad
        assert "1777" in r.error.message or "2100" in r.error.message


def test_malformed_input_returns_structured_error_never_a_traceback():
    cases = {
        "not-a-date": "INVALID_DATE",
        "2026-13-45": "INVALID_DATE",
        "07/04/2026": "INVALID_DATE",
        "2026-7-4": "INVALID_DATE",
        "": "INVALID_DATE",
    }
    for value, code in cases.items():
        r = _run(country="US", date=value)
        assert r.ok is False, value
        assert r.error.code == code, (value, r.error.code)
        assert "Traceback" not in r.error.message


def test_unknown_and_missing_calendar_are_typed():
    assert _run(country="ZZ", date="2026-07-04").error.code == "UNKNOWN_COUNTRY"
    assert _run(date="2026-07-04").error.code == "INVALID_CALENDAR_SPEC"
    assert _run(country="US", market="NYSE", date="2026-07-04").error.code == "INVALID_CALENDAR_SPEC"


def test_is_deterministic():
    a = _run(country="US", date="2026-07-03")
    b = _run(country="US", date="2026-07-03")
    assert a.SerializeToString(deterministic=True) == b.SerializeToString(deterministic=True)


def test_returns_the_declared_type():
    assert isinstance(_run(country="US", date="2026-07-04"), HolidayStatus)


def test_holiday_names_do_not_depend_on_the_process_locale():
    """Regression: the wrapped library resolves an unset language through
    gettext, which consults the process locale — so without an explicit pin the
    same call could return "Neujahr" here and "New Year's Day" in the deployed
    container. Names must be environment-independent."""
    import os
    saved = {k: os.environ.get(k) for k in ("LANG", "LC_ALL", "LANGUAGE")}
    try:
        for locale in ("de_DE.UTF-8", "fr_FR.UTF-8", "C"):
            os.environ["LANG"] = os.environ["LC_ALL"] = os.environ["LANGUAGE"] = locale
            r = _run(country="DE", date="2026-01-01")
            assert r.ok, (locale, r.error)
            assert r.holidays[0].name == "New Year's Day", (
                f"holiday name changed under LANG={locale}: {r.holidays[0].name!r}")
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def test_non_ascii_holiday_names_survive_the_round_trip():
    """Holiday names are text from 250 calendars; many are not ASCII. A name
    that is mangled by an encoding bug is a wrong answer."""
    german = _run(country="DE", language="de", date="2026-12-26")
    assert german.ok, german.error
    assert german.holidays[0].name == "Zweiter Weihnachtstag"
    hebrew = _run(country="IL", language="he", date="2026-04-02")
    assert hebrew.ok, hebrew.error
    assert any(any("֐" <= ch <= "׿" for ch in h.name) for h in hebrew.holidays), \
        f"expected Hebrew script, got {[h.name for h in hebrew.holidays]}"
    thai = _run(country="TH", language="th", date="2026-01-01")
    assert thai.ok, thai.error
    assert any(any("฀" <= ch <= "๿" for ch in h.name) for h in thai.holidays), \
        f"expected Thai script, got {[h.name for h in thai.holidays]}"

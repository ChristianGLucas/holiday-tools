"""Weekend definitions cross-checked against an INDEPENDENT source.

The weekend is this package's most load-bearing non-obvious input: get it wrong
and every business-day answer for that country is silently wrong. So it is
cross-checked against CLDR (via Babel), which is a genuinely independent source
— not the wrapped `holidays` library grading its own homework.

The cross-check found REAL DISAGREEMENT for a handful of countries, and
inspection shows BOTH sources are wrong in different places (see below). This
file pins the current behaviour for every one of them so it can never drift
silently, and documents which side is believed correct. Where they disagree, a
caller who needs certainty should pass CalendarSpec.weekend_override.
"""

from gen.messages_pb2 import CalendarInfoQuery, Weekday
from nodes.calendar_info import calendar_info


class _Ctx:
    class _Log:
        def debug(self, msg, **k): pass
        info = warn = error = debug
    def __init__(self):
        self.log = self._Log()
        self.execution_id = "test-execution-id"


def _weekend(country):
    r = calendar_info(_Ctx(), CalendarInfoQuery(country=country))
    assert r.ok, (country, r.error)
    return list(r.weekend)


FRI, SAT, SUN, THU = Weekday.FRIDAY, Weekday.SATURDAY, Weekday.SUNDAY, Weekday.THURSDAY

# Verified AGREEING with CLDR (checked live against locale-tools/DescribeLocale,
# which wraps Babel's CLDR data). These are the countries this package's shipped
# documentation names by example, so they are the ones that must stay right.
CLDR_AGREES = {
    "US": [SAT, SUN], "DE": [SAT, SUN], "MX": [SAT, SUN], "ID": [SAT, SUN],
    "MY": [SAT, SUN], "NP": [SAT, SUN], "PK": [SAT, SUN], "SO": [SAT, SUN],
    "IL": [FRI, SAT], "EG": [FRI, SAT], "SA": [FRI, SAT], "JO": [FRI, SAT],
    "QA": [FRI, SAT], "OM": [FRI, SAT], "KW": [FRI, SAT], "BH": [FRI, SAT],
    "IQ": [FRI, SAT], "SY": [FRI, SAT], "YE": [FRI, SAT], "SD": [FRI, SAT],
    "AE": [SAT, SUN],   # UAE moved to Sat/Sun in 2022; both sources agree
    "IR": [FRI],        # single-day weekend
}


def test_weekend_matches_cldr_where_the_two_sources_agree():
    for country, expected in CLDR_AGREES.items():
        assert _weekend(country) == expected, country


# Countries where this package (python-holidays) and CLDR DISAGREE. Recorded
# rather than papered over. `ours` is what this package returns today.
CLDR_DISAGREES = {
    #          ours          CLDR         who looks right
    "BD": ([FRI, SAT], [SAT, SUN], "ours — Bangladesh rests Friday-Saturday"),
    "DJ": ([FRI, SAT], [SAT, SUN], "ours — Djibouti rests Friday-Saturday"),
    "MV": ([FRI, SAT], [SAT, SUN], "ours — Maldives rests Friday-Saturday"),
    "BN": ([FRI, SUN], [SAT, SUN], "ours — Brunei's split Friday+Sunday week"),
    # LY and IN are a DIFFERENT KIND of divergence from the four above. Verified
    # 2026-08-04 by reading the library source: holidays.countries.libya and
    # holidays.countries.india declare NO `weekend` attribute at all, so both
    # silently inherit HolidayBase.weekend = {SAT, SUN}. That value is an UNSET
    # DEFAULT, not a considered position on those countries — the neighbouring
    # calendars (IL, EG, SA, IR, BD) all DO set it explicitly and correctly.
    #
    # LY: no source supports Saturday-Sunday. They disagree only on WHICH
    #     Friday-inclusive answer is right:
    #       - ILO NATLEX, Ministerial Order No. 10 of 2012 (primary/legal):
    #         official working days Saturday-Thursday, Friday the weekly rest
    #         day  => FRIDAY ONLY.
    #         https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=93476
    #       - CLDR, and practice reporting (incl. reports of a 2006 shift from a
    #         one-day to a two-day weekend) => FRIDAY-SATURDAY.
    #     Left UN-OVERRIDDEN pending an orchestrator decision: the primary source
    #     does not confirm the Friday-Saturday value CLDR gives, so overriding to
    #     it would be substituting one unverified answer for another.
    # IN: CLDR gives India's official Sunday-only week; Saturday-Sunday is the
    #     common corporate five-day week. Both describe something real.
    "LY": ([SAT, SUN], [FRI, SAT], "NEITHER — Sat-Sun is an unset library "
                                   "default; law says Fri-only, CLDR/practice "
                                   "say Fri-Sat. Escalated, not overridden."),
    "AF": ([FRI, SAT], [THU, FRI], "contested; Afghanistan has shifted over time"),
    "IN": ([SAT, SUN], [SUN], "contested; CLDR gives the official Sunday-only "
                              "week, ours the common corporate five-day week; "
                              "upstream sets no weekend for IN either"),
}


def test_libya_and_india_inherit_an_unset_upstream_default():
    """Pins the ROOT CAUSE for the two sharpest divergences, so it is visible if
    upstream ever fixes it (at which point this test should start failing and
    the override question can be retired).

    Unlike Israel/Egypt/Saudi/Iran/Bangladesh — which all declare an explicit
    `weekend` — the Libya and India calendars declare none and silently inherit
    HolidayBase's Saturday-Sunday. The value is an absence, not an answer.
    """
    import inspect, importlib, re

    def declares_weekend(module_name):
        src = inspect.getsource(importlib.import_module(f"holidays.countries.{module_name}"))
        return any(re.match(r"\s*weekend\s*=", line) for line in src.splitlines())

    for mod in ("israel", "egypt", "saudi_arabia", "iran", "bangladesh"):
        assert declares_weekend(mod), f"{mod} used to declare a weekend explicitly"
    for mod in ("libya", "india"):
        assert not declares_weekend(mod), (
            f"upstream now declares a weekend for {mod} — re-check the divergence "
            "table above; this package may no longer need to document it.")


def test_known_cldr_divergences_are_pinned_not_drifting():
    """These are the countries where an independent source disagrees with the
    wrapped library. This test does not assert either side is correct — it pins
    what this package actually returns, so a library upgrade that silently
    changes a weekend shows up as a failing test rather than as quietly wrong
    business-day arithmetic."""
    for country, (ours, _cldr, _who) in CLDR_DISAGREES.items():
        assert _weekend(country) == ours, (
            f"{country}: weekend changed from the pinned value {ours}. "
            "Re-check against CLDR before accepting the new value.")


def test_weekend_override_is_the_remedy_for_a_contested_country():
    """The documented escape hatch: a caller who needs CLDR's answer for a
    contested country can pin it explicitly and get deterministic results."""
    from gen.messages_pb2 import CalendarSpec, DateQuery
    from nodes.is_business_day import is_business_day

    # 2026-07-11 is a Saturday. India defaults to a Sat/Sun weekend here...
    default = is_business_day(
        _Ctx(), DateQuery(calendar=CalendarSpec(country="IN"), date="2026-07-11"))
    assert default.ok and default.is_business_day is False

    # ...but a caller following CLDR's official Sunday-only week overrides it.
    overridden = is_business_day(
        _Ctx(), DateQuery(
            calendar=CalendarSpec(country="IN", weekend_override=[Weekday.SUNDAY]),
            date="2026-07-11"))
    assert overridden.ok and overridden.is_business_day is True

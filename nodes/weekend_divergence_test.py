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
    "LY": ([SAT, SUN], [FRI, SAT], "CLDR — Libya rests Friday-Saturday"),
    "AF": ([FRI, SAT], [THU, FRI], "contested; Afghanistan has shifted over time"),
    "IN": ([SAT, SUN], [SUN], "contested; CLDR gives the official Sunday-only "
                              "week, ours the common corporate five-day week"),
}


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

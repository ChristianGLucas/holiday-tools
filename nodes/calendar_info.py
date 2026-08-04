from gen.messages_pb2 import CalendarDetail, CalendarInfoQuery, Error, Subdivision
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def calendar_info(ax: AxiomContext, input: CalendarInfoQuery) -> CalendarDetail:
    """Describe one calendar's shape: which weekdays are its WEEKEND, which
    subdivisions it defines, which holiday categories and languages it supports,
    and which years it has data for.

    The weekend is the field that most often surprises callers - it is
    Friday/Saturday for Israel, Egypt, Saudi Arabia, Jordan and Qatar, Friday
    alone for Iran, and Saturday/Sunday across most of the West - so hard-coding
    Saturday/Sunday produces confidently wrong answers for those locales. The
    subdivision list also gives the aliases each code accepts ("Texas" as well as
    "TX"). Call this before building a CalendarSpec so every field is a value the
    calendar actually accepts, rather than discovering it through an error.
    """
    try:
        entry = cu.resolve_calendar_entry(input.country, input.market)
        cls = cu.entity_class(entry)
        aliases_by_code = {}
        for alias, code in (getattr(cls, "subdivisions_aliases", {}) or {}).items():
            aliases_by_code.setdefault(code, []).append(alias)
        subdivisions = [
            Subdivision(code=code, aliases=sorted(aliases_by_code.get(code, [])))
            for code in (getattr(cls, "subdivisions", ()) or ())
        ]
        start_year, end_year = cu.calendar_year_bounds(entry)
        supported_categories = list(getattr(cls, "supported_categories", ()) or ())
        supported_languages = list(getattr(cls, "supported_languages", ()) or ())
        probe = cu.resolve(_spec_for(entry))
        return CalendarDetail(
            ok=True,
            code=entry["code"],
            name=entry["name"],
            kind=entry["kind"],
            weekend=cu.default_weekend(entry),
            start_year=start_year,
            end_year=end_year,
            subdivisions=subdivisions,
            supported_categories=supported_categories,
            default_category=probe.categories[0],
            supported_languages=supported_languages,
            default_language=probe.language,
            aliases=entry["aliases"],
        )
    except cu.CalendarError as exc:
        return CalendarDetail(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return CalendarDetail(ok=False, error=Error(code="INTERNAL", message=str(exc)))


class _Spec:
    """Minimal duck-typed CalendarSpec so the probe reuses the real resolver."""

    def __init__(self, country, market):
        self.country = country
        self.market = market
        self.subdivision = ""
        self.language = ""
        self.categories = []
        self.observed_rule = cu.OBSERVED_RULE_UNSPECIFIED
        self.weekend_override = []
        self.extra_holidays = []


def _spec_for(entry):
    if entry["kind"] == "country":
        return _Spec(entry["code"], "")
    return _Spec("", entry["code"])

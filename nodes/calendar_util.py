"""Shared calendar resolution and business-day arithmetic for holiday-tools.

Everything in this module is deterministic and offline. Nothing here ever reads
the wall clock: every date a node answers about is supplied by the caller.

The wrapped library (`holidays`, MIT) owns the genuinely hard part — WHICH dates
are holidays across 250 national and 21 financial-market calendars, including
Easter-derived moving feasts, nth-weekday rules, and weekend-substitution
("observed") policy. This module owns the contract around it: validating input
up front, layering caller-supplied weekends and extra closures on top, and
walking dates for business-day arithmetic.
"""

from __future__ import annotations

import re
from datetime import date, timedelta

import holidays
from holidays import registry

# ---------------------------------------------------------------------------
# Error contract
# ---------------------------------------------------------------------------


class CalendarError(Exception):
    """A structured, caller-facing failure. Never escapes a node as a traceback."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


# Proto enum values, mirrored here so this module has no dependency on gen/.
WEEKDAY_UNSPECIFIED = 0

OBSERVED_RULE_UNSPECIFIED = 0
INCLUDE_OBSERVED = 1
ACTUAL_ONLY = 2

CONVENTION_UNSPECIFIED = 0
FOLLOWING = 1
PRECEDING = 2
MODIFIED_FOLLOWING = 3
MODIFIED_PRECEDING = 4

NON_BUSINESS_REASON_UNSPECIFIED = 0
BUSINESS_DAY = 1
WEEKEND = 2
HOLIDAY = 3
WEEKEND_AND_HOLIDAY = 4

SEARCH_DIRECTION_UNSPECIFIED = 0
FORWARD = 1
BACKWARD = 2

CUSTOM_CATEGORY = "custom"
DEFAULT_EXTRA_NAME = "Custom holiday"

# How far ClosestHoliday will scan before giving up. Bounded by the calendar's
# own year coverage in practice; this is only a terminating condition for a
# calendar that genuinely has no holidays in the direction searched.
_MAX_CLOSEST_SCAN_DAYS = 800


# ---------------------------------------------------------------------------
# Registry lookup — code/alias -> canonical calendar
# ---------------------------------------------------------------------------


def _pretty(class_name: str) -> str:
    """'NewYorkStockExchange' -> 'New York Stock Exchange'.

    Derived from the class name rather than the registry key, because the key is
    abbreviated ('ny_stock_exchange') and would make the calendar undiscoverable
    by its real name.
    """
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", class_name)
    return re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)


def _build_lookup(reg, kind):
    lookup = {}
    canonical = {}
    for key, aliases in reg.items():
        class_name = aliases[0]
        # aliases = (ClassName, primary_code, other codes...). Prefer the first
        # short code as canonical; fall back to the class name.
        codes = [a for a in aliases[1:]] or [class_name]
        primary = codes[0]
        entry = {
            "key": key,
            "class_name": class_name,
            "code": primary,
            "name": _pretty(class_name),
            "kind": kind,
            # Every other spelling that resolves to this same calendar, so a
            # caller can discover that "NYSE" works as well as the "XNYS" MIC.
            "aliases": sorted({class_name, *codes} - {primary}),
        }
        canonical[primary] = entry
        for alias in (key, class_name, *codes):
            lookup[alias.upper()] = entry
    return lookup, canonical


_COUNTRY_LOOKUP, _COUNTRY_CANONICAL = _build_lookup(registry.COUNTRIES, "country")
_MARKET_LOOKUP, _MARKET_CANONICAL = _build_lookup(registry.FINANCIAL, "market")


def all_calendars():
    """Every calendar this package can answer against, canonical entries only."""
    return list(_COUNTRY_CANONICAL.values()) + list(_MARKET_CANONICAL.values())


def resolve_calendar_entry(country: str, market: str):
    """Resolve exactly one of country/market to a canonical registry entry."""
    country = (country or "").strip()
    market = (market or "").strip()
    if country and market:
        raise CalendarError(
            "INVALID_CALENDAR_SPEC",
            "Supply exactly one of country or market, not both "
            f"(got country={country!r} and market={market!r}).",
        )
    if not country and not market:
        raise CalendarError(
            "INVALID_CALENDAR_SPEC",
            "A calendar is required: set either country (an ISO 3166-1 alpha-2 "
            "code such as 'US') or market (a financial-market code such as "
            "'NYSE'). Call SupportedCalendars for the full list.",
        )
    if country:
        entry = _COUNTRY_LOOKUP.get(country.upper())
        if entry is None:
            raise CalendarError(
                "UNKNOWN_COUNTRY",
                f"No calendar data for country {country!r}. Expected an ISO "
                "3166-1 alpha-2 code such as 'US', 'DE' or 'IL'; call "
                "SupportedCalendars for the full list of accepted codes.",
            )
        return entry
    entry = _MARKET_LOOKUP.get(market.upper())
    if entry is None:
        raise CalendarError(
            "UNKNOWN_MARKET",
            f"No calendar data for market {market!r}. Expected a "
            "financial-market code such as 'NYSE' or 'ECB'; call "
            "SupportedCalendars with kind='market' for the full list.",
        )
    return entry


def entity_class(entry):
    return getattr(holidays, entry["class_name"])


# ---------------------------------------------------------------------------
# Parsing / conversion helpers
# ---------------------------------------------------------------------------


def parse_date(value: str, field: str) -> date:
    """Parse a strict ISO 8601 'YYYY-MM-DD' calendar date."""
    text = (value or "").strip()
    if not text:
        raise CalendarError(
            "INVALID_DATE",
            f"{field} is required and must be an ISO 8601 date, 'YYYY-MM-DD'.",
        )
    # date.fromisoformat accepts other ISO forms on newer Pythons; pin the
    # contract to exactly YYYY-MM-DD so the node's promise is what it does.
    parts = text.split("-")
    if len(parts) != 3 or len(parts[0]) != 4 or len(parts[1]) != 2 or len(parts[2]) != 2:
        raise CalendarError(
            "INVALID_DATE",
            f"{field}={value!r} is not an ISO 8601 date. Expected exactly "
            "'YYYY-MM-DD', e.g. '2026-07-04'.",
        )
    try:
        year, month, day = (int(p) for p in parts)
    except ValueError:
        raise CalendarError(
            "INVALID_DATE",
            f"{field}={value!r} is not an ISO 8601 date. Expected exactly "
            "'YYYY-MM-DD', e.g. '2026-07-04'.",
        ) from None
    try:
        return date(year, month, day)
    except ValueError as exc:
        raise CalendarError(
            "INVALID_DATE",
            f"{field}={value!r} is not a real calendar date ({exc}).",
        ) from None


def iso(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def weekday_enum(d: date) -> int:
    """Proto Weekday value: MONDAY=1 .. SUNDAY=7, matching date.isoweekday()."""
    return d.isoweekday()


def weekday_enum_to_index(value: int, field: str) -> int:
    """Proto Weekday (1..7, Monday-first) -> Python date.weekday() (0..6)."""
    if value < 1 or value > 7:
        raise CalendarError(
            "INVALID_ARGUMENT",
            f"{field} contains {value}, which is not a named weekday. Use "
            "MONDAY..SUNDAY.",
        )
    return value - 1


# ---------------------------------------------------------------------------
# Resolved calendar
# ---------------------------------------------------------------------------


class ResolvedCalendar:
    """A fully-validated calendar plus the caller's overrides, ready to query."""

    def __init__(self, entry, subdiv, categories, include_observed, weekend,
                 extras, start_year, end_year, language, obs_cals, act_cals):
        self.entry = entry
        self.code = entry["code"]
        self.name = entry["name"]
        self.kind = entry["kind"]
        self.subdiv = subdiv
        self.categories = categories
        self.include_observed = include_observed
        self.weekend = weekend  # set of Python weekday ints, Monday=0
        self.extras = extras  # dict[date, str]
        self.start_year = start_year
        self.end_year = end_year
        self.language = language
        self._obs = obs_cals
        self._act = act_cals

    # -- year coverage -----------------------------------------------------

    def check_year(self, year: int, what: str) -> None:
        if year < self.start_year or year > self.end_year:
            raise CalendarError(
                "YEAR_OUT_OF_RANGE",
                f"{what} falls in year {year}, but calendar {self.code} only "
                f"has data for {self.start_year}-{self.end_year}. Returning an "
                "empty result would be indistinguishable from a year with no "
                "holidays, so this is an error instead.",
            )

    def check_date(self, d: date, what: str) -> None:
        self.check_year(d.year, what)

    # -- queries -----------------------------------------------------------

    def is_weekend(self, d: date) -> bool:
        return d.weekday() in self.weekend

    def holidays_on(self, d: date):
        """Every holiday occurrence on d, as plain dicts."""
        out = []
        for category in self.categories:
            actual_names = self._act[category].get_list(d)
            source = self._obs[category] if self.include_observed else self._act[category]
            for name in source.get_list(d):
                out.append(
                    {
                        "date": iso(d),
                        "name": name,
                        # An occurrence is a substitute when the name is not
                        # present on this same date in the no-substitution
                        # calendar. Comparing calendars rather than parsing the
                        # name keeps this correct in every language.
                        "observed": name not in actual_names,
                        "category": category,
                        "weekday": weekday_enum(d),
                    }
                )
        extra_name = self.extras.get(d)
        if extra_name is not None:
            out.append(
                {
                    "date": iso(d),
                    "name": extra_name,
                    "observed": False,
                    "category": CUSTOM_CATEGORY,
                    "weekday": weekday_enum(d),
                }
            )
        out.sort(key=lambda o: (o["name"], o["category"]))
        return out

    def is_holiday(self, d: date) -> bool:
        if d in self.extras:
            return True
        source = self._obs if self.include_observed else self._act
        return any(d in source[c] for c in self.categories)

    def is_business_day(self, d: date) -> bool:
        return not self.is_weekend(d) and not self.is_holiday(d)

    def reason(self, d: date) -> int:
        weekend = self.is_weekend(d)
        holiday = self.is_holiday(d)
        if weekend and holiday:
            return WEEKEND_AND_HOLIDAY
        if weekend:
            return WEEKEND
        if holiday:
            return HOLIDAY
        return BUSINESS_DAY

    # -- business-day arithmetic -------------------------------------------

    def step_business_days(self, start: date, days: int) -> date:
        """Move `days` business days from `start`.

        Positive moves forward, negative moves backward. ZERO rolls FORWARD to
        the nearest business day (inclusive) — so the result is always a
        business day. That matches both the wrapped library's own
        `get_nth_working_day(d, 0)` and Excel's `WORKDAY(d, 0)`.
        """
        current = start
        if days == 0:
            while not self.is_business_day(current):
                current += timedelta(days=1)
                self.check_date(current, "the computed result")
            return current
        step = 1 if days > 0 else -1
        remaining = abs(days)
        while remaining > 0:
            current += timedelta(days=step)
            self.check_date(current, "the computed result")
            if self.is_business_day(current):
                remaining -= 1
        return current

    def roll(self, d: date, convention: int) -> date:
        """Adjust d onto a business day under a named roll convention."""
        if self.is_business_day(d):
            return d
        if convention in (CONVENTION_UNSPECIFIED, FOLLOWING):
            return self._walk(d, 1)
        if convention == PRECEDING:
            return self._walk(d, -1)
        if convention == MODIFIED_FOLLOWING:
            forward = self._walk(d, 1)
            if forward.month != d.month:
                return self._walk(d, -1)
            return forward
        if convention == MODIFIED_PRECEDING:
            backward = self._walk(d, -1)
            if backward.month != d.month:
                return self._walk(d, 1)
            return backward
        raise CalendarError(
            "INVALID_ARGUMENT",
            f"convention={convention} is not a known business-day convention. "
            "Use FOLLOWING, PRECEDING, MODIFIED_FOLLOWING or MODIFIED_PRECEDING.",
        )

    def _walk(self, d: date, step: int) -> date:
        current = d
        while not self.is_business_day(current):
            current += timedelta(days=step)
            self.check_date(current, "the computed result")
        return current

    def closest_holiday(self, d: date, direction: int):
        """Nearest holiday strictly before/after d, or None within coverage."""
        step = -1 if direction == BACKWARD else 1
        current = d
        for _ in range(_MAX_CLOSEST_SCAN_DAYS):
            current += timedelta(days=step)
            if current.year < self.start_year or current.year > self.end_year:
                return None, 0
            occurrences = self.holidays_on(current)
            if occurrences:
                return occurrences[0], abs((current - d).days)
        return None, 0


# ---------------------------------------------------------------------------
# Building a ResolvedCalendar from a CalendarSpec proto message
# ---------------------------------------------------------------------------


def _validate_subdivision(cls, entry, subdiv: str) -> str:
    if not subdiv:
        return ""
    valid = list(getattr(cls, "subdivisions", ()) or ())
    aliases = dict(getattr(cls, "subdivisions_aliases", {}) or {})
    if not valid:
        raise CalendarError(
            "UNKNOWN_SUBDIVISION",
            f"Calendar {entry['code']} ({entry['name']}) defines no "
            f"subdivisions, so subdivision={subdiv!r} cannot be honoured. Leave "
            "subdivision empty to use the national calendar.",
        )
    if subdiv in valid:
        return subdiv
    if subdiv in aliases:
        return aliases[subdiv]
    # Case-insensitive rescue, so "tx" and "Texas" both work.
    lowered = subdiv.casefold()
    for code in valid:
        if code.casefold() == lowered:
            return code
    for alias, code in aliases.items():
        if alias.casefold() == lowered:
            return code
    raise CalendarError(
        "UNKNOWN_SUBDIVISION",
        f"Calendar {entry['code']} ({entry['name']}) has no subdivision "
        f"{subdiv!r}. Valid codes: {', '.join(sorted(valid))}. This is an error "
        "rather than a silent fall back to the national calendar, which would "
        "quietly return the wrong holidays.",
    )


def _validate_language(cls, entry, language: str) -> str:
    if not language:
        return ""
    supported = list(getattr(cls, "supported_languages", ()) or ())
    if language in supported:
        return language
    prefix = language.casefold()
    for code in supported:
        if code.casefold() == prefix or code.casefold().startswith(prefix + "_"):
            return code
    raise CalendarError(
        "UNSUPPORTED_LANGUAGE",
        f"Calendar {entry['code']} ({entry['name']}) does not publish holiday "
        f"names in language {language!r}. Supported: "
        f"{', '.join(supported) if supported else '(none)'}. This is an error "
        "rather than a silent fall back to the default language.",
    )


def _validate_categories(cls, entry, categories):
    supported = list(getattr(cls, "supported_categories", ()) or ())
    default = getattr(cls, "default_category", None) or (
        supported[0] if supported else "public"
    )
    requested = [c.strip() for c in categories if c and c.strip()]
    if not requested:
        return [default]
    resolved = []
    for cat in requested:
        match = None
        for code in supported:
            if code.casefold() == cat.casefold():
                match = code
                break
        if match is None:
            raise CalendarError(
                "UNSUPPORTED_CATEGORY",
                f"Calendar {entry['code']} ({entry['name']}) does not define "
                f"holiday category {cat!r}. Supported: "
                f"{', '.join(supported) if supported else '(none)'}.",
            )
        if match not in resolved:
            resolved.append(match)
    return resolved


def effective_language(cls, requested: str) -> str:
    """Pin the language explicitly so output never depends on the container.

    The wrapped library resolves an unset language through gettext, which
    consults the PROCESS LOCALE — so the same call could return "Neujahr" on one
    machine and "New Year's Day" on another. That would make holiday names
    environment-dependent, which this package promises they are not. So an
    unset language is resolved here, deterministically, to English where the
    calendar publishes it and to the calendar's own authoring language
    otherwise.
    """
    if requested:
        return requested
    supported = list(getattr(cls, "supported_languages", ()) or ())
    if not supported:
        return ""
    if "en_US" in supported:
        return "en_US"
    default = getattr(cls, "default_language", None)
    if default and default in supported:
        return default
    return supported[0]


def _make_calendar(entry, subdiv, category, language, observed):
    kwargs = {
        "subdiv": subdiv or None,
        "observed": observed,
        "categories": (category,),
    }
    if language:
        kwargs["language"] = language
    if entry["kind"] == "country":
        return holidays.country_holidays(entry["code"], **kwargs)
    return holidays.financial_holidays(entry["code"], **kwargs)


def resolve(spec) -> ResolvedCalendar:
    """Validate a CalendarSpec message and build a queryable calendar.

    Every failure mode is raised as a CalendarError with a stable code. Nothing
    here defers a validation error to a later library call, which is how a
    wrapped library ends up leaking a traceback.
    """
    country = getattr(spec, "country", "") if spec is not None else ""
    market = getattr(spec, "market", "") if spec is not None else ""
    entry = resolve_calendar_entry(country, market)
    cls = entity_class(entry)

    subdiv = _validate_subdivision(
        cls, entry, (getattr(spec, "subdivision", "") or "").strip()
    )
    language = _validate_language(
        cls, entry, (getattr(spec, "language", "") or "").strip()
    )
    categories = _validate_categories(
        cls, entry, list(getattr(spec, "categories", []) or [])
    )
    language = effective_language(cls, language)

    observed_rule = getattr(spec, "observed_rule", OBSERVED_RULE_UNSPECIFIED)
    if observed_rule not in (OBSERVED_RULE_UNSPECIFIED, INCLUDE_OBSERVED, ACTUAL_ONLY):
        raise CalendarError(
            "INVALID_ARGUMENT",
            f"observed_rule={observed_rule} is not a known value. Use "
            "INCLUDE_OBSERVED or ACTUAL_ONLY.",
        )
    include_observed = observed_rule != ACTUAL_ONLY

    obs_cals = {}
    act_cals = {}
    try:
        for category in categories:
            obs_cals[category] = _make_calendar(entry, subdiv, category, language, True)
            act_cals[category] = _make_calendar(entry, subdiv, category, language, False)
    except CalendarError:
        raise
    except Exception as exc:  # pragma: no cover - defensive
        raise CalendarError(
            "INTERNAL",
            f"Could not build calendar {entry['code']}: {exc}",
        ) from None

    probe = obs_cals[categories[0]]
    start_year = int(getattr(probe, "start_year", 1))
    end_year = int(getattr(probe, "end_year", 9999))

    # Weekend: the calendar's own real weekend unless the caller overrides it.
    override = list(getattr(spec, "weekend_override", []) or [])
    if override:
        weekend = {weekday_enum_to_index(v, "weekend_override") for v in override}
    else:
        weekend = set(getattr(probe, "weekend", {5, 6}))

    extras = {}
    for item in getattr(spec, "extra_holidays", []) or []:
        d = parse_date(getattr(item, "date", ""), "extra_holidays[].date")
        name = (getattr(item, "name", "") or "").strip() or DEFAULT_EXTRA_NAME
        extras[d] = name


    return ResolvedCalendar(
        entry=entry,
        subdiv=subdiv,
        categories=categories,
        include_observed=include_observed,
        weekend=weekend,
        extras=extras,
        start_year=start_year,
        end_year=end_year,
        language=language,
        obs_cals=obs_cals,
        act_cals=act_cals,
    )


def calendar_year_bounds(entry, subdiv=""):
    """start_year/end_year for a calendar, without a full CalendarSpec."""
    cls = entity_class(entry)
    cal = _make_calendar(entry, subdiv, _default_category(cls), effective_language(cls, ""), True)
    return int(getattr(cal, "start_year", 1)), int(getattr(cal, "end_year", 9999))


def _default_category(cls):
    supported = list(getattr(cls, "supported_categories", ()) or ())
    return getattr(cls, "default_category", None) or (
        supported[0] if supported else "public"
    )


def default_weekend(entry, subdiv=""):
    cls = entity_class(entry)
    cal = _make_calendar(entry, subdiv, _default_category(cls), effective_language(cls, ""), True)
    return sorted(int(w) + 1 for w in getattr(cal, "weekend", {5, 6}))


def check_range(start: date, end: date) -> None:
    if end < start:
        raise CalendarError(
            "INVALID_DATE_RANGE",
            f"end_date {iso(end)} precedes start_date {iso(start)}. The range is "
            "inclusive of both endpoints and must be given in order.",
        )


def daterange(start: date, end: date):
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)

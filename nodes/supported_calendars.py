from gen.messages_pb2 import CalendarCatalog, CalendarCatalogQuery, CalendarSummary, Error
from gen.axiom_context import AxiomContext

from nodes import calendar_util as cu


def supported_calendars(ax: AxiomContext, input: CalendarCatalogQuery) -> CalendarCatalog:
    """List every country and financial-market calendar this package can answer
    against, with the exact code to pass to every other node.

    Each entry reports whether the code belongs in CalendarSpec.country or
    CalendarSpec.market, how many subdivisions it defines, and the span of years
    it actually has data for - the range outside which the other nodes return a
    typed YEAR_OUT_OF_RANGE error. Filter by kind ("country" or "market") or by
    a case-insensitive substring of the code or name. This is the discovery node
    an agent calls first to learn what codes are valid, instead of guessing one.
    """
    try:
        kind = (input.kind or "").strip().casefold()
        if kind in ("", "all"):
            kind = ""
        elif kind not in ("country", "market"):
            raise cu.CalendarError(
                "INVALID_ARGUMENT",
                f"kind={input.kind!r} is not valid. Use 'country', 'market', or "
                "leave it empty for both.",
            )
        contains = (input.contains or "").strip().casefold()
        summaries = []
        for entry in cu.all_calendars():
            if kind and entry["kind"] != kind:
                continue
            if contains and contains not in entry["code"].casefold() \
                    and contains not in entry["name"].casefold():
                continue
            cls = cu.entity_class(entry)
            start_year, end_year = cu.calendar_year_bounds(entry)
            summaries.append(
                CalendarSummary(
                    code=entry["code"],
                    name=entry["name"],
                    kind=entry["kind"],
                    subdivision_count=len(getattr(cls, "subdivisions", ()) or ()),
                    start_year=start_year,
                    end_year=end_year,
                    aliases=entry["aliases"],
                )
            )
        summaries.sort(key=lambda s: (s.kind, s.code))
        return CalendarCatalog(ok=True, calendars=summaries, count=len(summaries))
    except cu.CalendarError as exc:
        return CalendarCatalog(ok=False, error=Error(code=exc.code, message=exc.message))
    except Exception as exc:  # noqa: BLE001
        return CalendarCatalog(ok=False, error=Error(code="INTERNAL", message=str(exc)))

# holiday-tools

Offline public-holiday calendars and business-day arithmetic as composable
[Axiom](https://axiomide.com) nodes — 250 country calendars (with US states,
German Länder, Canadian provinces and other subdivisions) and 21
financial-market calendars, wrapping the MIT-licensed
[`holidays`](https://github.com/vacanza/holidays) library. No network, no rate
limit, no wall clock.

## Use it from your agent or app

Every node in this package is a **live, auto-scaling API endpoint** on the
[Axiom](https://axiomide.com) marketplace — call it from an AI agent or your
own code, with nothing to self-host.

**📦 See it on the marketplace:**
https://dev.axiomide.com/marketplace/christiangeorgelucas/holiday-tools@0.1.0

**Hook it up to an AI agent (MCP).** Add Axiom's hosted MCP server to any MCP
client and every node becomes a typed tool your agent can call — search the
catalog, inspect a schema, and invoke it directly.

```bash
# Claude Code
claude mcp add --transport http axiom https://api.axiomide.com/mcp \
  --header "Authorization: Bearer $AXIOM_API_KEY"
```

Claude Desktop, Cursor, or any config-based client:

```json
{
  "mcpServers": {
    "axiom": {
      "type": "http",
      "url": "https://api.axiomide.com/mcp",
      "headers": { "Authorization": "Bearer YOUR_AXIOM_API_KEY" }
    }
  }
}
```

**Call it from the CLI.**

```bash
axiom invoke christiangeorgelucas/holiday-tools/AddBusinessDays --input '{"calendar":{"country":"US"},"start_date":"2026-07-02","days":3}'
```

**Call it over HTTP.**

```bash
curl -X POST https://api.axiomide.com/invocations/v1/nodes/christiangeorgelucas/holiday-tools/0.1.0/AddBusinessDays \
  -H "Authorization: Bearer $AXIOM_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"calendar":{"country":"US"},"start_date":"2026-07-02","days":3}'
```

### Get started free

Install the CLI:

```bash
# macOS / Linux — Homebrew
brew install axiomide/tap/axiom

# macOS / Linux — install script
curl -fsSL https://raw.githubusercontent.com/AxiomIDE/axiom-releases/main/install.sh | sh
```

**Windows:** download the `windows/amd64` `.zip` from the
[releases page](https://github.com/AxiomIDE/axiom-releases/releases), unzip
it, and put `axiom.exe` on your `PATH`.

Then `axiom version` to verify, `axiom login` (GitHub or Google) to
authenticate, and create an API key under **Console → API Keys**. Docs and
sign-up at **[axiomide.com](https://axiomide.com)**.

## Why this exists

**It knows the holidays.** A spreadsheet's `WORKDAY`/`NETWORKDAYS` only skips
weekends unless you hand it a holiday list. Three business days after Thursday
2026-07-02 in the US:

| | Answer |
|---|---|
| Weekend-only (`WORKDAY`) | `2026-07-07` |
| **holiday-tools** | **`2026-07-08`** |

The difference is Friday 2026-07-03 — Independence Day falls on Saturday
2026-07-04, so it is *observed* on the preceding Friday.

**It is offline.** Every answer is computed locally from bundled calendar data:
no network call, no rate limit, no outage, no API key. That is what makes it
safe inside a deterministic pure-tools flow. The sibling package
[`nager-date-connector`](https://dev.axiomide.com/marketplace/christiangeorgelucas/nager-date-connector@1)
fetches the same kind of data *live* from date.nager.at — reach for that one
when you need the authoritative upstream source, and this one when you need a
computation that cannot fail because a website is down.

**It is clock-free.** Every date-relative node takes a caller-supplied date and
never reads the wall clock, so the same input always produces the same output —
across runs, machines, and months. Holiday names are pinned to an explicit
language rather than the container's locale, for the same reason.

## Things that are easy to get wrong, and are handled here

- **The weekend is not universally Saturday/Sunday.** It is Friday/Saturday in
  Israel, Egypt, Saudi Arabia, Jordan and Qatar, and Friday alone in Iran.
  Every calendar carries its own real weekend, and you can override it per
  request to model a specific organization's working week.

  These weekends are **cross-checked against CLDR** (an independent source, via
  `locale-tools/DescribeLocale`) — 22 countries verified agreeing. The check also
  found **7 countries where the two sources disagree**, and *both* are wrong in
  different places: this package is right for Bangladesh, Djibouti, the Maldives
  and Brunei, while Afghanistan and India are legitimately contested. Every one is
  pinned by a regression test so a library upgrade cannot change a weekend
  silently. **If you need certainty for a contested country, pass
  `weekend_override` and the answer becomes yours, not the library's.**

- **Libya is a deliberate, documented correction to the upstream library.** The
  `holidays` library declares no weekend for Libya (nor for India) and silently
  inherits its Saturday/Sunday default — an *absence* rendering as a confident
  answer. For Libya that default is supported by **no source at all**, so this
  package overrides it. The two authorities that do speak disagree:

  | Source | Libyan weekend |
  |---|---|
  | ILO NATLEX, [Ministerial Order No. 10 of 2012](https://natlex.ilo.org/dyn/natlex2/r/natlex/fe/details?p3_isn=93476) — working days Sat–Thu | **Friday only** |
  | CLDR + practice reporting (and a reported 2006 shift to a two-day weekend) | **Friday–Saturday** |

  **This package returns Friday–Saturday**, because *"is this a working day for
  business purposes"* is a question about observed practice rather than the legal
  status of public administration. If you need the strict legal reading, pass
  `weekend_override: ["FRIDAY"]` and you get it deterministically.

  India is deliberately **not** corrected: it inherits the same unset default, but
  there Saturday/Sunday genuinely matches the common corporate five-day week, so
  it is a defensible answer rather than an unsupported one.
- **Observed vs. actual dates.** A holiday falling on a weekend is often
  observed on an adjacent weekday. Every occurrence is explicitly flagged
  `observed`, determined by comparing calendars rather than parsing the name —
  so it stays correct in every language. Calendars differ in policy: most *add*
  the substitute and keep the actual date, so both come back; a minority (the
  Netherlands, Israel, Chile, Colombia, Argentina…) *relocate* the holiday, so
  only the substitute is a day off. Ask for `ACTUAL_ONLY` to get the real
  calendar date either way.
- **Subdivisions genuinely differ.** Bavaria observes Epiphany; the German
  national calendar does not. Texas observes Texas Independence Day; the US
  federal calendar does not. An unrecognized subdivision is a typed
  `UNKNOWN_SUBDIVISION` error, **never** a silent fall back to the national
  calendar — a silent fallback is a wrong answer with no signal.
- **Year coverage is finite.** The US calendar covers 1777–2100. A year outside
  a calendar's real range is a typed `YEAR_OUT_OF_RANGE` error, not a silently
  empty list that would be indistinguishable from a quiet year.
- **Market calendars are not country calendars.** The NYSE closes on Good
  Friday; the US federal calendar has no such holiday.

## Nodes

Every node returns `ok` plus a structured `error{code,message}` — malformed
input never crashes and never leaks a traceback.

### Holiday calendar

| Node | Does |
|---|---|
| `IsHoliday` | Is this date a holiday? Names every holiday on it, flags actual vs. observed, and reports weekend/business-day status. |
| `IsBusinessDay` | Is this date a working day — and if not, *why*: `WEEKEND`, `HOLIDAY`, or `WEEKEND_AND_HOLIDAY`. |
| `HolidaysInYear` | Every holiday in one calendar year, for a country/subdivision or market. |
| `HolidaysInRange` | Every holiday inside an arbitrary date range (inclusive, may span years). |
| `FindHolidayByName` | Which *dates* a named holiday falls on across a span of years — for moving feasts. |
| `ClosestHoliday` | The nearest holiday before or after a date, with the day gap. |

### Business-day arithmetic

| Node | Does |
|---|---|
| `AddBusinessDays` | Advance/rewind N business days. Negative rewinds; zero rolls forward to the nearest business day. |
| `RollToBusinessDay` | Adjust a date onto a business day under `FOLLOWING` / `PRECEDING` / `MODIFIED_FOLLOWING` / `MODIFIED_PRECEDING`. |
| `CountBusinessDays` | How many working days a range contains, plus the full auditable partition of the range. |
| `BusinessDaysInRange` | The working days themselves, plus every skipped day and the reason it was skipped. |

### Discovery

| Node | Does |
|---|---|
| `SupportedCalendars` | Every country and market calendar, with its code, aliases, subdivision count and year range. |
| `CalendarInfo` | One calendar's weekend, subdivisions (and their aliases), categories, languages and year range. |

## Examples

Is 2026-07-03 a holiday in the US? (It is — the *observed* Independence Day.)

```bash
axiom invoke christiangeorgelucas/holiday-tools/IsHoliday \
  --input '{"calendar":{"country":"US"},"date":"2026-07-03"}'
```

How many working days between 2026-06-29 and 2026-07-10?

```bash
axiom invoke christiangeorgelucas/holiday-tools/CountBusinessDays \
  --input '{"calendar":{"country":"US"},"start_date":"2026-06-29","end_date":"2026-07-10"}'
```

→ `business_days: 9`, `weekend_days: 2`, `holiday_days: 1`, `calendar_days: 12`.

Bavaria's holidays, in German:

```bash
axiom invoke christiangeorgelucas/holiday-tools/HolidaysInYear \
  --input '{"calendar":{"country":"DE","subdivision":"BY","language":"de"},"year":2026}'
```

A company shutdown layered on top of the public calendar:

```bash
axiom invoke christiangeorgelucas/holiday-tools/AddBusinessDays \
  --input '{"calendar":{"country":"US","extra_holidays":[{"date":"2026-07-06","name":"Company Shutdown"}]},"start_date":"2026-07-02","days":1}'
```

## Composes with

- **`invoice-build`** — `ParsePaymentTerms` → `ComputeDueDate` gives a calendar
  due date; `RollToBusinessDay` moves it onto an actual working day.
- **`quant-finance-tools`** — `GenerateSchedule` builds a coupon schedule
  against four built-in calendars; this package covers the other 267 and does
  single-date business-day arithmetic, which schedule generation does not.
- **`interval-tools`** — `BusinessDaysInRange` supplies the working days that
  scheduling set-algebra searches over.
- **`nager-date-connector`** — the live/authoritative counterpart to this
  package's offline/deterministic answers.

## Built with

- [`holidays`](https://github.com/vacanza/holidays) 0.102 — MIT
- [`python-dateutil`](https://github.com/dateutil/dateutil) 2.9.0.post0 —
  Apache-2.0 / BSD-3-Clause (dual)

Both licences were verified from the `LICENSE` file in the actual distribution.

## Development

```bash
axiom validate --json   # static checks
axiom test              # 104 tests, including an independent-oracle suite
axiom dev               # local server (port is printed on startup)
```

The test suite checks holiday dates against **independent ground truth** rather
than against the wrapped library: Easter-derived dates are verified with a
from-scratch Gregorian computus, nth-weekday holidays with plain calendar
arithmetic, and business-day arithmetic against a deliberately holiday-blind
weekday counter (so the difference must be explained by a real holiday).

Built for the [Axiom](https://axiomide.com) marketplace. MIT licensed.

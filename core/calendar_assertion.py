"""Calendar assertion layer — deterministic post-response validation for
weekday/date pairs (Phase 1.5.32).

Architecture mirrors core.hallucination_guard:
- Never rewrites the response.
- Only appends a disclaimer (with concrete correction) + logs a warning.
- Must never raise into the orchestrator (caller wraps in try/except).

Why this exists on top of HallucinationGuard.weekday:
- The existing guard detects "weekday + date nearby" claims and appends a
  generic "nicht verifiziert" disclaimer when no date-tool was called.
- It cannot tell the user WHAT the correct weekday actually is.
- Post-deploy tests on 2026-04-19 reproduced two drift patterns that a
  generic disclaimer doesn't fully solve:
    (a) Historical-recap hallucination: 5 Pilates dates (28.01, 04.02,
        25.02, 11.03, 15.04/2026) all annotated as "Dienstag" — all are
        actually Wednesdays. tool_calls=1, get_weekday_for_date never
        invoked despite the prompt rule.
    (b) Event-to-day drift: 5 Wednesday events bucketed under Tuesday
        section even though DTSTART was correct 22.04.
- For (a) we can verify deterministically in Python via
  `datetime.date().weekday()` — no time-MCP round-trip needed.
- This module focuses on (a). (b) would require parsing tool-output,
  tracked separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from typing import Iterable

import structlog

log = structlog.get_logger("himes.calendar_assertion")


# Map: ISO weekday-index (Mon=0..Sun=6) → German weekday name
_WEEKDAY_DE: dict[int, str] = {
    0: "Montag",
    1: "Dienstag",
    2: "Mittwoch",
    3: "Donnerstag",
    4: "Freitag",
    5: "Samstag",
    6: "Sonntag",
}

# Reverse lookup: normalize weekday strings as they appear in Claude's output.
# Long forms + 2-char short forms ("Mo", "Di", "Mi", "Do", "Fr", "Sa", "So").
_WEEKDAY_LOOKUP: dict[str, int] = {
    "montag": 0, "mo": 0,
    "dienstag": 1, "di": 1,
    "mittwoch": 2, "mi": 2,
    "donnerstag": 3, "do": 3,
    "freitag": 4, "fr": 4,
    "samstag": 5, "sa": 5,
    "sonntag": 6, "so": 6,
}

# Month names (for "24. April" style) — German, covering ae/ä for "März"
_MONTH_DE: dict[str, int] = {
    "januar": 1,
    "februar": 2,
    "märz": 3, "maerz": 3,
    "april": 4,
    "mai": 5,
    "juni": 6,
    "juli": 7,
    "august": 8,
    "september": 9,
    "oktober": 10,
    "november": 11,
    "dezember": 12,
}

# Weekday alternation — long + short forms. Order matters (long first)
# so the regex engine prefers "Montag" over the prefix "Mo".
_WEEKDAY_ALT = (
    r"(?:Montag|Dienstag|Mittwoch|Donnerstag|Freitag|Samstag|Sonntag|"
    r"Mo|Di|Mi|Do|Fr|Sa|So)"
)

# DD.MM.YYYY or DD.MM. (year optional; spaces tolerated)
_DATE_DMY_RE = re.compile(
    r"\b(?P<d>\d{1,2})\.\s?(?P<m>\d{1,2})\.(?:\s?(?P<y>\d{2,4}))?",
)
# ISO 2026-04-24
_DATE_ISO_RE = re.compile(
    r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b",
)
# "24. April" / "24. April 2026" / "24. Maerz"
_MONTH_ALT = (
    r"(?:Januar|Februar|M(?:ä|ae)rz|April|Mai|Juni|Juli|August|"
    r"September|Oktober|November|Dezember)"
)
_DATE_MN_RE = re.compile(
    rf"\b(?P<d>\d{{1,2}})\.\s+(?P<m>{_MONTH_ALT})(?:\s+(?P<y>\d{{2,4}}))?",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WeekdayMismatch:
    """One detected mismatch in the response text."""
    claimed_weekday: str   # e.g. "Dienstag" (as written)
    actual_weekday: str    # e.g. "Mittwoch"
    iso_date: str          # e.g. "2026-01-28"
    display_date: str      # e.g. "28.01.2026" (as written)


def _parse_iso(match: re.Match[str]) -> date | None:
    try:
        return date(int(match["y"]), int(match["m"]), int(match["d"]))
    except (ValueError, KeyError):
        return None


def _parse_dmy(match: re.Match[str], default_year: int) -> date | None:
    try:
        d = int(match["d"])
        m = int(match["m"])
        y_raw = match["y"]
    except (ValueError, KeyError):
        return None
    if y_raw is None:
        year = default_year
    else:
        y = int(y_raw)
        # Accept 2-digit years as 20YY
        year = 2000 + y if y < 100 else y
    try:
        return date(year, m, d)
    except ValueError:
        return None


def _parse_month_name(match: re.Match[str], default_year: int) -> date | None:
    try:
        d = int(match["d"])
    except (ValueError, KeyError):
        return None
    mn = match["m"].lower().replace("ä", "ae")
    # Our table stores both "märz" and "maerz"; normalize to ae
    if mn not in _MONTH_DE:
        # fall back to the ä-form
        mn = match["m"].lower()
    m = _MONTH_DE.get(mn)
    if m is None:
        return None
    y_raw = match["y"]
    if y_raw is None:
        year = default_year
    else:
        y = int(y_raw)
        year = 2000 + y if y < 100 else y
    try:
        return date(year, m, d)
    except ValueError:
        return None


# ── Pair-extraction regexes ────────────────────────────────────────────
# Match a weekday and a date within ~40 chars — both orientations.
# Non-greedy; keep the window tight so "Freitag …lots of text… 24.04" does
# not match spuriously (same design as HallucinationGuard.weekday).
_WINDOW = 40

_PAIR_WD_THEN_DATE_RE = re.compile(
    rf"\b(?P<wd>{_WEEKDAY_ALT})\b"
    rf".{{0,{_WINDOW}}}?"
    rf"(?P<date>"
    rf"\d{{1,2}}\.\s?\d{{1,2}}\.(?:\s?\d{{2,4}})?"
    rf"|\d{{4}}-\d{{2}}-\d{{2}}"
    rf"|\d{{1,2}}\.\s+{_MONTH_ALT}(?:\s+\d{{2,4}})?"
    rf")",
    re.IGNORECASE,
)

_PAIR_DATE_THEN_WD_RE = re.compile(
    rf"(?P<date>"
    rf"\d{{1,2}}\.\s?\d{{1,2}}\.(?:\s?\d{{2,4}})?"
    rf"|\d{{4}}-\d{{2}}-\d{{2}}"
    rf"|\d{{1,2}}\.\s+{_MONTH_ALT}(?:\s+\d{{2,4}})?"
    rf")"
    rf".{{0,{_WINDOW}}}?"
    rf"\b(?P<wd>{_WEEKDAY_ALT})\b",
    re.IGNORECASE,
)


def _parse_date_string(s: str, default_year: int) -> date | None:
    """Try all three date formats on a substring, return the first that parses."""
    m = _DATE_ISO_RE.match(s) or _DATE_ISO_RE.search(s)
    if m:
        d = _parse_iso(m)
        if d is not None:
            return d
    m = _DATE_MN_RE.match(s) or _DATE_MN_RE.search(s)
    if m:
        d = _parse_month_name(m, default_year)
        if d is not None:
            return d
    m = _DATE_DMY_RE.match(s) or _DATE_DMY_RE.search(s)
    if m:
        return _parse_dmy(m, default_year)
    return None


def _normalize_weekday(s: str) -> int | None:
    return _WEEKDAY_LOOKUP.get(s.strip().lower())


def _default_year(today: date | None) -> int:
    return (today or date.today()).year


def _iter_pairs(text: str) -> Iterable[tuple[str, str, int, int]]:
    """Yield (weekday_str, date_str, match_start, match_end) for both orders."""
    for m in _PAIR_WD_THEN_DATE_RE.finditer(text):
        yield m["wd"], m["date"], m.start(), m.end()
    for m in _PAIR_DATE_THEN_WD_RE.finditer(text):
        yield m["wd"], m["date"], m.start(), m.end()


def find_weekday_mismatches(
    text: str,
    today: date | None = None,
) -> list[WeekdayMismatch]:
    """Return all (claimed_weekday, actual_weekday, date) mismatches in `text`.

    Year is required for a conclusive check. If the date has no explicit
    year, we assume `today.year`. Duplicates (same ISO date + same claimed
    weekday) are de-duplicated.
    """
    if not text:
        return []

    year = _default_year(today)
    seen: set[tuple[str, str]] = set()
    out: list[WeekdayMismatch] = []

    for wd_str, date_str, _start, _end in _iter_pairs(text):
        wd_idx = _normalize_weekday(wd_str)
        if wd_idx is None:
            continue
        parsed = _parse_date_string(date_str, year)
        if parsed is None:
            continue
        actual_idx = parsed.weekday()
        if actual_idx == wd_idx:
            continue  # Claim matches reality — no mismatch.

        key = (parsed.isoformat(), wd_str.lower())
        if key in seen:
            continue
        seen.add(key)

        out.append(
            WeekdayMismatch(
                claimed_weekday=_WEEKDAY_DE[wd_idx],  # normalized long form
                actual_weekday=_WEEKDAY_DE[actual_idx],
                iso_date=parsed.isoformat(),
                display_date=date_str.strip(),
            )
        )

    return out


def build_disclaimer(mismatches: list[WeekdayMismatch]) -> str:
    """Render a user-facing disclaimer with one line per mismatch.

    Empty list → empty string.
    """
    if not mismatches:
        return ""
    lines = ["⚠️ _Datum-Korrektur:_"]
    for mm in mismatches:
        lines.append(
            f"• {mm.display_date} ist {mm.actual_weekday} "
            f"(nicht {mm.claimed_weekday})"
        )
    return "\n\n" + "\n".join(lines)


class CalendarAssertion:
    """Post-response deterministic weekday-date validator.

    Usage:
        assertion = CalendarAssertion()
        is_suspect, disclaimer = assertion.check(response_text)
        if is_suspect:
            final = response_text + disclaimer

    Never rewrites, never blocks. If internals raise, caller must swallow
    the exception (orchestrator wraps in try/except like hallucination_guard).
    """

    def __init__(self, today_fn=date.today) -> None:
        # today_fn is injectable for deterministic testing.
        self._today_fn = today_fn

    def check(self, text: str) -> tuple[bool, str]:
        if not text:
            return False, ""

        today = self._today_fn()
        mismatches = find_weekday_mismatches(text, today=today)
        if not mismatches:
            return False, ""

        log.warning(
            "calendar_assertion.weekday_mismatch",
            count=len(mismatches),
            mismatches=[
                {
                    "iso_date": m.iso_date,
                    "claimed": m.claimed_weekday,
                    "actual": m.actual_weekday,
                    "display_date": m.display_date,
                }
                for m in mismatches
            ],
            text_len=len(text),
        )
        return True, build_disclaimer(mismatches)

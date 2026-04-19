"""Unit tests for Phase 1.5.30 time-arithmetic tools in himes-tools.

Tools: get_weekday_for_date, add_days, days_between, next_weekday.

Motivation: real-world bugs on 2026-04-19 showed Claude hallucinating
weekdays (24.04 called "Donnerstag" instead of "Freitag") and drifting
day labels in a week overview (Do 23, Do 24, Fr 25, Sa 26 — off by one
from the 24th onwards). These tools replace LLM mental-math with
deterministic Python zoneinfo calculation.
"""

from __future__ import annotations

import json

from himes_mcp.server import (
    _add_days,
    _days_between,
    _get_weekday_for_date,
    _next_weekday,
)


def _parse(result) -> dict:
    """Extract JSON payload from a single-element TextContent list."""
    assert len(result) == 1
    return json.loads(result[0].text)


class TestGetWeekdayForDate:
    def test_april_24_2026_is_friday(self):
        """The original hallucination: Claude said Donnerstag, real = Freitag."""
        p = _parse(_get_weekday_for_date(iso_date="2026-04-24"))
        assert p["weekday_name"] == "Freitag"
        assert p["weekday_number"] == 4
        assert p["is_weekend"] is False

    def test_april_19_2026_is_sunday(self):
        p = _parse(_get_weekday_for_date(iso_date="2026-04-19"))
        assert p["weekday_name"] == "Sonntag"
        assert p["weekday_number"] == 6
        assert p["is_weekend"] is True

    def test_saturday_is_weekend(self):
        p = _parse(_get_weekday_for_date(iso_date="2026-04-25"))
        assert p["weekday_name"] == "Samstag"
        assert p["is_weekend"] is True

    def test_invalid_date_returns_error(self):
        result = _get_weekday_for_date(iso_date="not-a-date")
        assert "Ungültiges Datum" in result[0].text


class TestAddDays:
    def test_plus_5_from_sunday_is_friday(self):
        """Sun 19.04 + 5 = Fri 24.04 — the 'nächster Freitag' case."""
        p = _parse(_add_days(iso_date="2026-04-19", days=5))
        assert p["result_date"] == "2026-04-24"
        assert p["weekday_name"] == "Freitag"
        assert p["days_added"] == 5

    def test_plus_1_tomorrow(self):
        p = _parse(_add_days(iso_date="2026-04-19", days=1))
        assert p["result_date"] == "2026-04-20"
        assert p["weekday_name"] == "Montag"

    def test_minus_1_yesterday(self):
        p = _parse(_add_days(iso_date="2026-04-19", days=-1))
        assert p["result_date"] == "2026-04-18"
        assert p["weekday_name"] == "Samstag"

    def test_plus_zero_same_day(self):
        p = _parse(_add_days(iso_date="2026-04-19", days=0))
        assert p["result_date"] == "2026-04-19"
        assert p["weekday_name"] == "Sonntag"

    def test_cross_month_boundary(self):
        p = _parse(_add_days(iso_date="2026-04-28", days=7))
        assert p["result_date"] == "2026-05-05"

    def test_cross_year_boundary(self):
        p = _parse(_add_days(iso_date="2026-12-31", days=1))
        assert p["result_date"] == "2027-01-01"
        assert p["weekday_name"] == "Freitag"

    def test_leap_year_feb(self):
        # 2028 is leap year
        p = _parse(_add_days(iso_date="2028-02-28", days=1))
        assert p["result_date"] == "2028-02-29"


class TestDaysBetween:
    def test_consecutive_days(self):
        p = _parse(_days_between(start_date="2026-04-19", end_date="2026-04-20"))
        assert p["days"] == 1
        assert p["is_future"] is True

    def test_sunday_to_friday_is_5(self):
        p = _parse(_days_between(start_date="2026-04-19", end_date="2026-04-24"))
        assert p["days"] == 5

    def test_same_day_zero(self):
        p = _parse(_days_between(start_date="2026-04-19", end_date="2026-04-19"))
        assert p["days"] == 0
        assert p["is_future"] is False

    def test_past_negative(self):
        p = _parse(_days_between(start_date="2026-04-19", end_date="2026-04-17"))
        assert p["days"] == -2
        assert p["is_future"] is False


class TestNextWeekday:
    def test_next_friday_from_sunday_is_5_days(self):
        """Sun 19.04 → next Fri = Fri 24.04 (5 days)."""
        p = _parse(_next_weekday(from_date="2026-04-19", weekday="Freitag"))
        assert p["result_date"] == "2026-04-24"
        assert p["days_until"] == 5
        assert p["weekday_name"] == "Freitag"

    def test_next_sunday_from_sunday_is_today(self):
        """Same-weekday semantics: 'nächster Sonntag' on Sunday = today (0)."""
        p = _parse(_next_weekday(from_date="2026-04-19", weekday="Sonntag"))
        assert p["result_date"] == "2026-04-19"
        assert p["days_until"] == 0

    def test_next_monday_from_sunday_is_tomorrow(self):
        p = _parse(_next_weekday(from_date="2026-04-19", weekday="Montag"))
        assert p["result_date"] == "2026-04-20"
        assert p["days_until"] == 1

    def test_case_insensitive_weekday(self):
        p = _parse(_next_weekday(from_date="2026-04-19", weekday="freitag"))
        assert p["result_date"] == "2026-04-24"

    def test_unknown_weekday_returns_error(self):
        result = _next_weekday(from_date="2026-04-19", weekday="Funday")
        assert "Unbekannter Wochentag" in result[0].text

    def test_invalid_date_returns_error(self):
        result = _next_weekday(from_date="yesterday", weekday="Freitag")
        assert "Ungültiges Datum" in result[0].text


class TestWeekOverviewDriftFix:
    """Regression tests for the 2026-04-19 week-overview weekday drift.

    The bug: Claude generated "Do 23, Do 24, Fr 25, Sa 26" for the week
    of 20.04. Every day from 24.04 onwards was off by one. With these
    tools, Claude can verify each date's weekday individually.
    """

    def test_whole_week_consecutive_correct(self):
        """Mo 20 → Di 21 → Mi 22 → Do 23 → Fr 24 → Sa 25 → So 26."""
        expected = [
            ("2026-04-20", "Montag"),
            ("2026-04-21", "Dienstag"),
            ("2026-04-22", "Mittwoch"),
            ("2026-04-23", "Donnerstag"),
            ("2026-04-24", "Freitag"),
            ("2026-04-25", "Samstag"),
            ("2026-04-26", "Sonntag"),
        ]
        for iso, expected_wd in expected:
            p = _parse(_get_weekday_for_date(iso_date=iso))
            assert p["weekday_name"] == expected_wd, (
                f"{iso} should be {expected_wd}, got {p['weekday_name']}"
            )

"""Unit tests for weekday-halluzinations-guard (Phase 1.5.25).

Real-world trigger (2026-04-18): Claude answered "Musikschule-Termine sind
nicht morgen, sondern nächsten Donnerstag (24. April)" — 24.04.2026 is a
Friday, not Thursday. Time-MCP was never called in that turn.

Behavior:
- Weekday + date nearby (within 40 chars) + no time-MCP → disclaim
- Weekday + date + time-MCP called → no disclaim
- Weekday alone (no date) or date alone (no weekday) → no disclaim
- Global refusal markers short-circuit everything
"""

from __future__ import annotations

from core.hallucination_guard import build_default_guard


class TestWeekdayGuard:
    def test_weekday_with_date_no_time_mcp_triggers(self):
        """The exact bug from 2026-04-18 musikschule chat."""
        guard = build_default_guard()
        text = (
            "Musikschule-Termine sind nicht morgen, sondern nächsten "
            "Donnerstag (24. April) um 16:30."
        )
        tools = ["mcp__caldav__caldav_search_events"]
        suspect, disclaimer = guard.check(text, tools)
        assert suspect is True
        assert "Wochentag" in disclaimer

    def test_weekday_with_date_and_time_mcp_ok(self):
        """Time-MCP was called → claim is backed, no disclaim."""
        guard = build_default_guard()
        text = "Der Termin ist am Donnerstag, 24. April um 17:00."
        tools = [
            "mcp__time__convert_time",
            "mcp__caldav__caldav_get_events",
        ]
        suspect, disclaimer = guard.check(text, tools)
        # Weekday domain shouldn't trigger; other domains shouldn't either
        assert "Wochentag" not in disclaimer

    def test_weekday_alone_no_date_no_trigger(self):
        """Weekday without date → no claim to verify."""
        guard = build_default_guard()
        text = "Der Termin ist am Donnerstag um 17:00."
        tools: list[str] = []
        suspect, disclaimer = guard.check(text, tools)
        assert "Wochentag" not in disclaimer

    def test_date_alone_no_weekday_no_trigger(self):
        """Date without weekday → no claim to verify."""
        guard = build_default_guard()
        text = "Der Termin ist am 24. April um 17:00."
        tools: list[str] = []
        suspect, disclaimer = guard.check(text, tools)
        assert "Wochentag" not in disclaimer

    def test_weekday_before_dmy_date_triggers(self):
        """Weekday precedes DD.MM.YYYY date format."""
        guard = build_default_guard()
        text = "Am Freitag den 24.04.2026 ist Musikschule."
        tools = ["mcp__caldav__caldav_get_events"]
        suspect, disclaimer = guard.check(text, tools)
        assert suspect is True
        assert "Wochentag" in disclaimer

    def test_iso_date_then_weekday_triggers(self):
        """ISO date followed by weekday claim."""
        guard = build_default_guard()
        text = "2026-04-24 ist ein Freitag."
        tools: list[str] = []
        suspect, disclaimer = guard.check(text, tools)
        assert suspect is True
        assert "Wochentag" in disclaimer

    def test_global_refusal_short_circuits(self):
        """If the whole message is a refusal, nothing triggers."""
        guard = build_default_guard()
        text = (
            "Kalender ist nicht verfügbar. Der Termin am Freitag, "
            "24. April kann nicht bestätigt werden."
        )
        tools: list[str] = []
        suspect, disclaimer = guard.check(text, tools)
        assert suspect is False

    def test_get_current_time_prefix_counts_as_backed(self):
        """Both time-MCP tools (get_current_time, convert_time) back the claim."""
        guard = build_default_guard()
        text = "Heute ist Samstag, 18.04.2026."
        tools = ["mcp__time__get_current_time"]
        suspect, disclaimer = guard.check(text, tools)
        assert "Wochentag" not in disclaimer

    def test_multiple_weekday_date_pairs_single_disclaimer(self):
        """Multiple matches → still only one weekday disclaimer (not stacked)."""
        guard = build_default_guard()
        text = (
            "Am Freitag, 24. April und am Samstag, 25. April ist Messe."
        )
        tools: list[str] = []
        suspect, disclaimer = guard.check(text, tools)
        assert suspect is True
        # Disclaimer text for weekday should appear only once
        assert disclaimer.count("Wochentag nicht über time-MCP verifiziert") == 1

    def test_empty_text_no_trigger(self):
        guard = build_default_guard()
        suspect, disclaimer = guard.check("", [])
        assert suspect is False
        assert disclaimer == ""

    def test_weekday_far_from_date_no_trigger(self):
        """Weekday and date >40 chars apart → not co-located, no claim."""
        guard = build_default_guard()
        text = (
            "Freitag war wie immer entspannt, wir haben viel erledigt und "
            "ziemlich spät erst nach Hause gefahren. Am nächsten Tag, "
            "dem 24.04.2026, war es dann ganz anders."
        )
        tools: list[str] = []
        suspect, disclaimer = guard.check(text, tools)
        # Weekday and date are >40 chars apart → no weekday-domain claim
        assert "Wochentag" not in disclaimer

    def test_db_and_weekday_both_trigger_independently(self):
        """Two domains can trigger independently in the same message."""
        guard = build_default_guard()
        text = (
            "RE1 faehrt um 16:47 von Gleis 16 ab. "
            "Und am Freitag, 24. April ist Musikschule."
        )
        tools: list[str] = []  # neither DB nor time tool called
        suspect, disclaimer = guard.check(text, tools)
        assert suspect is True
        assert "Wochentag" in disclaimer
        assert "DB Navigator" in disclaimer or "bahn.de" in disclaimer

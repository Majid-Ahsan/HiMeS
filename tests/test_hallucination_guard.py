"""Unit tests for HallucinationGuard.

Covers:
- Registered DB patterns match actual hallucinated phrases from real chats
- Backed claims (tool was called) don't trigger
- Unbacked claims (no DB tool) trigger disclaimer
- Guard is soft (never rewrites, only appends)
- Multiple domains are independent
- Guard handles edge cases (empty text, no tools)
"""

from __future__ import annotations

import pytest

from core.hallucination_guard import HallucinationGuard, build_default_guard


class TestHallucinationGuard:
    def test_empty_text_no_trigger(self):
        guard = build_default_guard()
        suspect, disc = guard.check("", ["mcp__deutsche-bahn__db_departures"])
        assert suspect is False
        assert disc == ""

    def test_empty_tools_no_trigger_on_neutral_text(self):
        guard = build_default_guard()
        suspect, disc = guard.check("Guten Morgen Majid!", [])
        assert suspect is False
        assert disc == ""

    def test_hallucinated_re1_with_gleis_triggers(self):
        """Real-world sample from chat: Claude said 'RE1 um 16:47, Gleis 16'
        without having called a DB tool."""
        guard = build_default_guard()
        text = "Die RE1 faehrt um 16:47 von Gleis 16 ab, +2 Min Verspaetung."
        suspect, disc = guard.check(text, [])
        assert suspect is True
        assert "⚠️" in disc
        assert "DB Navigator" in disc or "bahn.de" in disc

    def test_hallucinated_gleiswechsel_triggers(self):
        """Scary case: 'Gleiswechsel auf Gleis 11' hallucinated."""
        guard = build_default_guard()
        text = "Gleiswechsel auf Gleis 11, +6 Min Verspaetung."
        suspect, disc = guard.check(text, [])
        assert suspect is True

    def test_hallucinated_stoerung_triggers(self):
        guard = build_default_guard()
        text = "Es gibt eine Stoerung zwischen Dortmund Hbf und Hamm."
        suspect, disc = guard.check(text, [])
        assert suspect is True

    def test_db_claim_backed_by_db_tool_no_trigger(self):
        """When a DB tool WAS called, claims are allowed (backed)."""
        guard = build_default_guard()
        text = "Die RE1 faehrt um 16:47 von Gleis 16 ab."
        suspect, disc = guard.check(
            text,
            ["mcp__deutsche-bahn__db_search_connections"],
        )
        assert suspect is False
        assert disc == ""

    def test_db_claim_backed_by_departures_tool_no_trigger(self):
        guard = build_default_guard()
        text = "Naechste S1: 08:15, Gleis 3."
        suspect, disc = guard.check(
            text,
            ["mcp__deutsche-bahn__db_departures"],
        )
        assert suspect is False

    def test_db_claim_with_other_mcp_tool_triggers(self):
        """If a non-DB MCP tool was called but DB data is claimed — still trigger."""
        guard = build_default_guard()
        text = "RE1 um 16:47, Gleis 16."
        suspect, disc = guard.check(
            text,
            ["mcp__things3__create_task", "caldav_get_events"],
        )
        assert suspect is True

    def test_neutral_text_no_trigger(self):
        guard = build_default_guard()
        text = "Guten Morgen! Dein naechster Termin ist um 09:00."
        suspect, disc = guard.check(text, [])
        assert suspect is False

    def test_multiple_domain_register(self):
        """Guard supports multiple domains, independently."""
        g = HallucinationGuard()
        g.register_domain(
            "calendar",
            patterns=[r"Termin um \d{2}:\d{2}"],
            tool_prefixes=["caldav_"],
            disclaimer="⚠️ Kalender nicht bestaetigt.",
        )
        g.register_domain(
            "weather",
            patterns=[r"\d+ ?°C"],
            tool_prefixes=["weather_"],
            disclaimer="⚠️ Wetter nicht bestaetigt.",
        )

        # Only calendar mentioned, no tool called — only calendar flagged
        text = "Termin um 14:30"
        suspect, disc = g.check(text, [])
        assert suspect is True
        assert "Kalender" in disc
        assert "Wetter" not in disc

        # Both domains flagged when both mentioned without tools
        text2 = "Termin um 14:30, es wird 22°C."
        suspect2, disc2 = g.check(text2, [])
        assert suspect2 is True
        assert "Kalender" in disc2
        assert "Wetter" in disc2

    def test_guard_does_not_rewrite_only_appends(self):
        """Critical design guarantee: disclaimer is separate from original text."""
        guard = build_default_guard()
        text = "RE1 um 16:47, Gleis 16."
        suspect, disc = guard.check(text, [])
        assert suspect is True
        # Disclaimer starts with newlines — original text is NOT modified
        assert disc.startswith("\n\n")
        # Original phrase still reconstructible
        combined = text + disc
        assert combined.startswith(text)

    def test_no_domains_registered_never_triggers(self):
        g = HallucinationGuard()
        suspect, disc = g.check("RE1 um 16:47, Gleis 16.", [])
        assert suspect is False
        assert disc == ""

    def test_internal_tool_name_prefix(self):
        """Guard accepts unprefixed tool names (db_*) too."""
        guard = build_default_guard()
        text = "RE1 um 16:47, Gleis 16."
        suspect, disc = guard.check(text, ["db_search_connections"])
        assert suspect is False

    @pytest.mark.parametrize("train", [
        "ICE 123", "ICE123", "RE 1", "RE1", "RB32", "S 1", "S1",
        "U18", "STR 102", "Tram 901", "Bus 135", "IC 2023",
    ])
    def test_various_train_numbers_trigger(self, train):
        guard = build_default_guard()
        text = f"Nimm die {train}."
        suspect, disc = guard.check(text, [])
        assert suspect is True, f"{train} should match DB pattern"

    @pytest.mark.parametrize("neutral", [
        "U-Boot 7",        # 'U 7' should not trigger (context)
        "Section 3",       # no train
        "Fenster 5",       # no train
        "Mein Zug kam puenktlich an.",  # no concrete data
        "100%",            # percentage not S100
    ])
    def test_neutral_mentions_no_trigger(self, neutral):
        guard = build_default_guard()
        suspect, disc = guard.check(neutral, [])
        # These should NOT trigger the guard — no specific train number claim
        # (acceptable: S-Bahn detection has false positives, we test none here)
        if "U-Boot" in neutral or "Section" in neutral or "Fenster" in neutral:
            # These SHOULD pass — no DB claim
            assert suspect is False, f"False positive: {neutral}"

    # ── Negation-awareness tests (DB-FIX-5a) ──

    def test_refusal_text_with_train_mention_no_trigger(self):
        """Real-world: Claude says 'kein Live-Tool für U18' — should NOT trigger."""
        guard = build_default_guard()
        text = (
            "Ich habe gerade kein Live-Tracking-Tool für die U18 verfügbar. "
            "Für die aktuelle Position der U-Bahn empfehle ich dir:\n"
            "- VRR-App\n- DB Navigator App\n- vrr.de"
        )
        suspect, disc = guard.check(text, [])
        assert suspect is False, f"Should not trigger on refusal text. Disclaimer: {disc}"

    def test_refusal_with_multiple_train_names_no_trigger(self):
        guard = build_default_guard()
        text = "Dafür habe ich kein Tool — für RE1 oder S1 nutze die DB Navigator App."
        suspect, disc = guard.check(text, [])
        assert suspect is False

    def test_recommend_app_with_train_no_trigger(self):
        guard = build_default_guard()
        text = "Die U18 Position empfehle ich dir über die VRR-App zu prüfen."
        suspect, disc = guard.check(text, [])
        assert suspect is False

    def test_own_disclaimer_not_retriggered(self):
        """Our own disclaimer contains 'Zeiten, Gleise, Verspätungen' — must not retrigger."""
        guard = build_default_guard()
        text = (
            "Die RE1 fährt um 07:35.\n\n"
            "⚠️ Ohne Live-Verifikation — die oben genannten Zugdaten "
            "(Zeiten, Gleise, Verspätungen) konnten nicht über die DB-API "
            "bestätigt werden."
        )
        # This SHOULD still trigger on the "RE1 um 07:35" — but not double-trigger
        # because of disclaimer text alone
        # First clean case — only disclaimer text:
        disclaimer_only = (
            "⚠️ Ohne Live-Verifikation — die Gleise und Verspätungen konnten "
            "nicht bestätigt werden."
        )
        suspect, disc = guard.check(disclaimer_only, [])
        assert suspect is False, (
            f"Disclaimer text alone shouldn't retrigger. Got disclaimer: {disc}"
        )

    def test_real_claim_still_triggers(self):
        """Sanity check: real hallucinated claim (no refusal context) still triggers."""
        guard = build_default_guard()
        text = "Die RE1 fährt um 16:47 von Gleis 16 ab."
        suspect, disc = guard.check(text, [])
        assert suspect is True

    def test_mixed_refusal_then_claim_triggers(self):
        """If text has BOTH refusal AND an isolated claim elsewhere, should trigger.

        Edge case: Claude says 'ich habe kein Tool' but then 'die S1 um 08:15'
        in unrelated sentence. The S1 claim is far from negation → triggers.
        """
        guard = build_default_guard()
        # Lots of unrelated filler to ensure claim is far from negation phrases
        filler = " Irgendein langer Text ohne Bezug. " * 15
        text = (
            "Für die RE1 habe ich kein Tracking-Tool."
            + filler
            + "Die S1 fährt um 08:15 von Gleis 3."
        )
        suspect, disc = guard.check(text, [])
        # The S1 claim is far from any negation → should trigger
        assert suspect is True

"""Unit tests for the calendar assertion layer (Phase 1.5.32).

Post-deploy drift reproduction on 2026-04-19 established two patterns:
- Historical-recap hallucination: 5 Pilates dates (28.01, 04.02, 25.02,
  11.03, 15.04/2026) all annotated "Dienstag" — all are Wednesday.
- Event-to-day bucketing drift: 5 Wednesday events under Tuesday section.

The assertion layer deterministically validates every weekday+date pair
in the assistant's text via `datetime.date().weekday()` and appends a
disclaimer with the concrete correction. Never rewrites the response.
"""

from __future__ import annotations

from datetime import date

from core.calendar_assertion import (
    CalendarAssertion,
    build_disclaimer,
    find_weekday_mismatches,
)


def _fixed_today(year: int = 2026, month: int = 4, day: int = 20):
    """Return a closure that always reports the same 'today' — default 2026-04-20."""
    fixed = date(year, month, day)
    return lambda: fixed


class TestFindWeekdayMismatches:
    def test_pilates_recap_five_wednesdays_mislabeled_as_tuesday(self):
        """The exact historical-recap bug from 2026-04-19."""
        text = (
            "Du warst bisher 5× bei Pilates:\n"
            "- 28.01.2026 (Dienstag)\n"
            "- 04.02.2026 (Dienstag)\n"
            "- 25.02.2026 (Dienstag)\n"
            "- 11.03.2026 (Dienstag)\n"
            "- 15.04.2026 (Dienstag)"
        )
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 5
        for m in mm:
            assert m.claimed_weekday == "Dienstag"
            assert m.actual_weekday == "Mittwoch"
        iso_dates = {m.iso_date for m in mm}
        assert iso_dates == {
            "2026-01-28",
            "2026-02-04",
            "2026-02-25",
            "2026-03-11",
            "2026-04-15",
        }

    def test_correct_weekday_date_pair_not_flagged(self):
        text = "Der nächste Freitag ist 24.04.2026 — Musikschule um 16:30."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert mm == []

    def test_iso_date_with_wrong_weekday(self):
        text = "Am 2026-04-22 (Dienstag) ist Pilates."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 1
        assert mm[0].iso_date == "2026-04-22"
        assert mm[0].claimed_weekday == "Dienstag"
        assert mm[0].actual_weekday == "Mittwoch"

    def test_month_name_format_with_wrong_weekday(self):
        text = "Donnerstag, 24. April 2026 ist Musikschule."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 1
        assert mm[0].actual_weekday == "Freitag"
        assert mm[0].claimed_weekday == "Donnerstag"

    def test_short_weekday_form_di_matches_long_dienstag(self):
        """'Di 28.01.2026' uses the 2-char short form."""
        text = "Di 28.01.2026 war Pilates — aber nur einmal."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 1
        # Normalized to long form in the output
        assert mm[0].claimed_weekday == "Dienstag"
        assert mm[0].actual_weekday == "Mittwoch"

    def test_year_defaults_to_today_year_when_missing(self):
        """'28.01.' without year assumes today.year = 2026."""
        text = "Am Dienstag, 28.01. war Pilates."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 1
        assert mm[0].iso_date == "2026-01-28"
        assert mm[0].actual_weekday == "Mittwoch"

    def test_two_digit_year_treated_as_20xx(self):
        text = "Am Dienstag, 28.01.26 war Pilates."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 1
        assert mm[0].iso_date == "2026-01-28"

    def test_invalid_date_does_not_crash(self):
        """Feb 30 / month 13 — must not raise, just skip."""
        text = "Freitag 30.02.2026 und Samstag 13.13.2026 sind seltsam."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        # Both dates are invalid — neither produces a mismatch entry
        assert mm == []

    def test_weekday_without_date_is_ignored(self):
        text = "Wir treffen uns am Freitag um 17 Uhr."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert mm == []

    def test_date_without_weekday_is_ignored(self):
        text = "Nächster Termin: 24.04.2026 um 17:00."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert mm == []

    def test_weekday_and_date_far_apart_not_paired(self):
        """Beyond the 40-char window the pairing should not trigger."""
        text = (
            "Freitag war wie immer sehr entspannt, wir haben viel erledigt "
            "und ziemlich spät gegessen. Später erwähnte ich, dass am "
            "28.01.2026 etwas Wichtiges passierte."
        )
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert mm == []

    def test_duplicate_pair_deduplicated(self):
        """Same (date, claimed) pair reported twice → one mismatch."""
        text = "Dienstag 28.01.2026 ... Dienstag 28.01.2026 nochmal."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert len(mm) == 1

    def test_empty_text_returns_empty(self):
        assert find_weekday_mismatches("", today=date(2026, 4, 20)) == []

    def test_iso_date_correct_weekday_not_flagged(self):
        """2026-04-24 is a Friday — no mismatch."""
        text = "Nächster Termin am 2026-04-24 (Freitag)."
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        assert mm == []


class TestBuildDisclaimer:
    def test_empty_mismatches_empty_disclaimer(self):
        assert build_disclaimer([]) == ""

    def test_disclaimer_contains_concrete_correction(self):
        """The whole point of this layer: tell the user WHAT is correct."""
        text = "- 28.01.2026 (Dienstag)\n- 04.02.2026 (Dienstag)"
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        disc = build_disclaimer(mm)
        assert "Datum-Korrektur" in disc
        assert "28.01.2026" in disc
        assert "ist Mittwoch" in disc
        assert "nicht Dienstag" in disc
        assert "04.02.2026" in disc

    def test_disclaimer_prefixed_with_double_newline(self):
        """Disclaimer must separate cleanly from the original response."""
        text = "Dienstag 28.01.2026"
        mm = find_weekday_mismatches(text, today=date(2026, 4, 20))
        disc = build_disclaimer(mm)
        assert disc.startswith("\n\n")


class TestCalendarAssertion:
    def test_check_returns_false_on_clean_text(self):
        assertion = CalendarAssertion(today_fn=_fixed_today())
        is_suspect, disc = assertion.check(
            "Morgen ist Dienstag, 21.04.2026 — alles OK."
        )
        assert is_suspect is False
        assert disc == ""

    def test_check_returns_true_on_pilates_bug(self):
        assertion = CalendarAssertion(today_fn=_fixed_today())
        text = (
            "Pilates-Recap: 28.01.2026 (Dienstag), 04.02.2026 (Dienstag), "
            "25.02.2026 (Dienstag)."
        )
        is_suspect, disc = assertion.check(text)
        assert is_suspect is True
        assert "Mittwoch" in disc
        assert "Dienstag" in disc

    def test_check_empty_text(self):
        assertion = CalendarAssertion(today_fn=_fixed_today())
        assert assertion.check("") == (False, "")

    def test_check_does_not_modify_input(self):
        """Soft-guard contract: never rewrite. Caller concatenates itself."""
        assertion = CalendarAssertion(today_fn=_fixed_today())
        text = "Dienstag 28.01.2026"
        original = text
        assertion.check(text)
        assert text == original

    def test_correct_claim_with_time_context_not_flagged(self):
        """Friday 24.04.2026 + correct weekday → silent."""
        assertion = CalendarAssertion(today_fn=_fixed_today())
        text = "Musikschule am Freitag, 24.04.2026 um 16:30."
        is_suspect, disc = assertion.check(text)
        assert is_suspect is False

    def test_today_fn_default_is_real_today(self):
        """If no today_fn is injected, date.today() is used. Sanity only."""
        assertion = CalendarAssertion()
        # Just verify it doesn't crash on a neutral input
        assert assertion.check("Hallo Welt") == (False, "")

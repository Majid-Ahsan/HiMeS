"""Tests für post_process_voice_response — Garantie für Transkript-Echo
bei Voice-Antworten, falls die LLM den Format-Hint im System-Prompt
ignoriert (passiert in Multi-Tool-Workflows).
"""

from __future__ import annotations

from input.voice_post_process import post_process_voice_response


def test_voice_post_process_adds_transcript():
    """Voice-Antwort ohne `_` Vorzeile sollte Transkript bekommen."""
    response = "Das Wetter ist 21°C..."
    transcript = "Wie ist das Wetter heute?"
    result = post_process_voice_response(response, transcript)
    assert result.startswith("_„Wie ist das Wetter heute?“_")
    assert "Das Wetter ist 21°C..." in result


def test_voice_post_process_skip_if_already_has():
    """Wenn LLM bereits Transkript zeigt, nicht doppelt einfügen."""
    response = '_„Wie ist das Wetter?“_\n\nEs ist 21°C'
    transcript = "Wie ist das Wetter?"
    result = post_process_voice_response(response, transcript)
    assert result.count("_„") == 1


def test_voice_post_process_blank_line_between():
    """Format: kursive Vorzeile, Leerzeile, Antwort."""
    result = post_process_voice_response("Antwort", "Frage?")
    assert result == "_„Frage?“_\n\nAntwort"


def test_voice_post_process_skip_with_leading_whitespace():
    """LLM-Antwort mit führendem Whitespace + `_` bleibt unverändert."""
    response = "  _„Frage?“_\n\nAntwort"
    result = post_process_voice_response(response, "Frage?")
    assert result.count("_„") == 1

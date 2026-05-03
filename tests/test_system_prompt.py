"""Smoke-Tests für SYSTEM_PROMPT — fängt versehentliche Reverts oder
Trunkierungen. Verhalten wird nicht getestet (das geht nur über
manuellen Bot-Test), aber strukturelle Integrität.
"""

from __future__ import annotations


def _load_prompt() -> str:
    """Lädt SYSTEM_PROMPT, ohne das ganze claude_subprocess-Modul zu
    importieren (das nutzt match/case → Python 3.10+ pflicht, lokal
    auf 3.9 nicht ladbar). Wir extrahieren die Konstante per Slice
    + exec.
    """
    from pathlib import Path
    src = (
        Path(__file__).resolve().parent.parent
        / "core" / "claude_subprocess.py"
    ).read_text(encoding="utf-8")
    lines = src.split("\n")
    start = next(i for i, l in enumerate(lines) if l.startswith("SYSTEM_PROMPT = ("))
    end = next(i for i, l in enumerate(lines[start:], start) if l.strip() == ")")
    block = "\n".join(lines[start : end + 1])
    ns: dict = {}
    exec(block, ns)
    return ns["SYSTEM_PROMPT"]


SYSTEM_PROMPT = _load_prompt()


def test_system_prompt_not_empty():
    assert len(SYSTEM_PROMPT) > 1000


def test_system_prompt_contains_daily_log_workflow():
    """ADR-050: Daily-Log-Workflow muss im Prompt sein."""
    assert "Daily-Log Workflow" in SYSTEM_PROMPT
    assert "log_daily_entry" in SYSTEM_PROMPT
    assert "read_daily_log" in SYSTEM_PROMPT


def test_system_prompt_contains_cognee():
    """Cognee-Tool muss erwähnt sein (sonst weiß Jarvis nicht dass es
    existiert)."""
    assert "cognee_search" in SYSTEM_PROMPT or "Cognee" in SYSTEM_PROMPT


def test_system_prompt_contains_memory_layers():
    """Drei-Schichten-Memory-Konzept im Prompt erwähnt."""
    assert "Short-term" in SYSTEM_PROMPT
    assert "Mid-term" in SYSTEM_PROMPT


def test_system_prompt_contains_routing_separation():
    """Daily-Log vs. Task-Abgrenzung muss im Prompt sein."""
    assert "NICHT Daily-Log" in SYSTEM_PROMPT
    assert "nachfragen" in SYSTEM_PROMPT.lower()


def test_system_prompt_requires_read_before_write():
    """ADR-050 D3: read_daily_log muss als Schritt 0 vor jeder
    log_daily_entry-Aktion gefordert sein."""
    assert "Schritt 0" in SYSTEM_PROMPT
    assert "read_daily_log" in SYSTEM_PROMPT
    lower = SYSTEM_PROMPT.lower()
    assert "ohne vorheriges" in lower or "ohne read_daily_log" in lower


def test_system_prompt_handles_read_failure():
    """ADR-050 D3 + Edge-Case: read_daily_log-Failure muss explizit
    behandelt werden, nicht auto-fallback."""
    # Backticks im Source — Test prüft nur den semantischen Kern.
    assert "selbst fehlschlägt" in SYSTEM_PROMPT
    assert "read_daily_log" in SYSTEM_PROMPT
    lower = SYSTEM_PROMPT.lower()
    assert (
        "soll ich trotzdem versuchen zu speichern" in lower
        or "soll ich trotzdem speichern" in lower
    )


def test_voice_language_hint_present():
    """Voice-Sprach-Hint sollte im System-Prompt sein."""
    assert "99.99" in SYSTEM_PROMPT or "99,99" in SYSTEM_PROMPT
    assert "Deutsch" in SYSTEM_PROMPT
    assert "Farsi" in SYSTEM_PROMPT or "Persisch" in SYSTEM_PROMPT
    assert "Englisch" in SYSTEM_PROMPT


def test_voice_transcript_format_present():
    """Transkript-Format-Anweisung sollte im System-Prompt sein."""
    assert "Transkript" in SYSTEM_PROMPT
    assert "kursiv" in SYSTEM_PROMPT.lower() or "_" in SYSTEM_PROMPT


def test_voice_marker_recognition():
    """System-Prompt sollte Voice-Marker-Erkennung enthalten."""
    assert "Voice-Transkript" in SYSTEM_PROMPT
    assert "🎤" in SYSTEM_PROMPT or "Marker" in SYSTEM_PROMPT


def test_voice_directive_strength():
    """Voice-Block sollte direktive Formulierung enthalten."""
    assert "KRITISCHE REGEL" in SYSTEM_PROMPT or "VORRANG" in SYSTEM_PROMPT
    assert "MUSS" in SYSTEM_PROMPT

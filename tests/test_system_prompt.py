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

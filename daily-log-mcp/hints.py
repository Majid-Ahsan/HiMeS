"""Hint-Extraktor für Daily-Log-Texte.

Echte Implementierung folgt in Phase 2.1 Schritt 8 (Schritt 3 des
ADR-050-Implementierungsplans). Sucht dort nach Datums-Patterns,
Task-Verben und Eigennamen via deterministischen Regex (kein LLM —
Vorschlags-Formulierung passiert im Bot, ADR-050 D7).
"""

from __future__ import annotations


def extract_hints(text: str) -> list[dict]:
    """STUB. Aktuell leere Liste. Echte Implementierung folgt.

    Returns:
        Liste von Hint-Dicts. Künftig z.B.::

            [
                {"type": "date", "value": "Freitag", "context": "..."},
                {"type": "task_verb", "value": "einkaufen", "context": "..."},
                {"type": "person", "value": "Reza", "context": "..."},
            ]
    """
    return []

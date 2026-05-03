"""Post-Processing für Voice-Antworten.

Garantiert kursive Transkript-Vorzeile bei Voice-Inputs, falls die
Bot-LLM den Format-Hint im System-Prompt ignoriert (passiert
zuverlässig in Multi-Tool-Workflows).
"""

from __future__ import annotations


def post_process_voice_response(response: str, transcript: str) -> str:
    """Garantiere kursive Transkript-Vorzeile bei Voice-Antworten.

    Wenn die LLM-Antwort bereits mit einer kursiven Vorzeile (`_`) beginnt,
    wird sie unverändert zurückgegeben. Sonst wird das Transkript als
    `_„<transcript>“_` Vorzeile mit Leerzeile vorangestellt.
    """
    if response.lstrip().startswith("_"):
        return response
    return f'_„{transcript}“_\n\n{response}'

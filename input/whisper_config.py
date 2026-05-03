"""Whisper-Konfiguration via ENV-Vars.

Eigenes Modul (statt config/settings.py) damit Tests es ohne den
pydantic-Stack laden können.

ENV-Vars (alle optional, sinnvolle Defaults):
- WHISPER_MODEL: tiny | base (default) | small | medium | large
- WHISPER_LANGUAGE: ISO-639-1 Code, default 'de'
- WHISPER_INITIAL_PROMPT: Eigennamen-Hint für bessere Erkennung
"""

from __future__ import annotations

import os


WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

WHISPER_LANGUAGE = os.getenv("WHISPER_LANGUAGE", "de")

WHISPER_INITIAL_PROMPT = os.getenv(
    "WHISPER_INITIAL_PROMPT",
    "Majid, Neda, Taha, Hossein, Ali, Newsha, Reza, Fateme, "
    "Mariette, Mülheim, Dortmund, Bottrop, Notion, Things, "
    "CalDAV, Cognee, Jarvis, Echolabor, Herzkatheterlabor.",
)

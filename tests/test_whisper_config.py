"""Tests für Whisper-Konfiguration via ENV-Vars.

Verifiziert sinnvolle Defaults — eigentliche transcribe()-Calls
werden hier nicht getestet (das geht nur in Docker mit installierter
whisper-Library).
"""

from __future__ import annotations

import importlib
import os


def _reload_whisper_config():
    """Re-importiere whisper_config damit os.getenv neu gelesen wird."""
    from input import whisper_config
    return importlib.reload(whisper_config)


def test_whisper_language_default():
    """WHISPER_LANGUAGE-Default sollte 'de' sein."""
    os.environ.pop("WHISPER_LANGUAGE", None)
    cfg = _reload_whisper_config()
    assert cfg.WHISPER_LANGUAGE == "de"


def test_whisper_model_default():
    """WHISPER_MODEL-Default sollte 'base' sein (RAM-bewusst auf VPS)."""
    os.environ.pop("WHISPER_MODEL", None)
    cfg = _reload_whisper_config()
    assert cfg.WHISPER_MODEL == "base"


def test_whisper_initial_prompt_has_family_names():
    """Initial-Prompt sollte Familien-Eigennamen enthalten."""
    cfg = _reload_whisper_config()
    assert "Majid" in cfg.WHISPER_INITIAL_PROMPT
    assert "Mülheim" in cfg.WHISPER_INITIAL_PROMPT
    assert "Mariette" in cfg.WHISPER_INITIAL_PROMPT


def test_whisper_initial_prompt_has_tech_names():
    """Initial-Prompt sollte Tech-Eigennamen enthalten."""
    cfg = _reload_whisper_config()
    assert "Cognee" in cfg.WHISPER_INITIAL_PROMPT
    assert "Jarvis" in cfg.WHISPER_INITIAL_PROMPT


def test_whisper_env_override():
    """WHISPER_LANGUAGE aus ENV überschreibt Default."""
    os.environ["WHISPER_LANGUAGE"] = "en"
    try:
        cfg = _reload_whisper_config()
        assert cfg.WHISPER_LANGUAGE == "en"
    finally:
        os.environ.pop("WHISPER_LANGUAGE", None)
        _reload_whisper_config()

"""Tests fuer pipeline.cognee_search.

Cognee wird vollstaendig gemockt — kein echter Cognee-Aufruf in Tests.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import types
from pathlib import Path
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import cognee_search  # noqa: E402


# ---------- Fixtures ----------

@pytest.fixture
def fake_cognee(monkeypatch):
    """Inject a fake top-level `cognee` module."""
    fake_root = types.ModuleType("cognee")
    fake_root.search = AsyncMock(return_value=["antwort 1", "antwort 2"])
    monkeypatch.setitem(sys.modules, "cognee", fake_root)
    return fake_root


@pytest.fixture
def fake_cognee_dir(tmp_path):
    """A tmp dir mit minimaler .env, damit kein WARNUNG-Noise im Output ist."""
    (tmp_path / ".env").write_text("LLM_API_KEY=test-dummy\n", encoding="utf-8")
    return tmp_path


# ---------- Tests ----------

def test_default_call_invokes_cognee_search(fake_cognee, fake_cognee_dir, capsys):
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "Was hat Majid heute gemacht?",
    ])
    assert rc == 0
    assert fake_cognee.search.call_count == 1
    kwargs = fake_cognee.search.call_args.kwargs
    assert kwargs["query_text"] == "Was hat Majid heute gemacht?"
    assert kwargs["top_k"] == 10
    # query_type wird BEWUSST nicht uebergeben — Cognee-Default (GRAPH_COMPLETION).
    assert "query_type" not in kwargs

    out = capsys.readouterr().out
    assert "Cognee-Verzeichnis" in out
    assert "antwort 1" in out
    assert "antwort 2" in out


def test_query_via_named_flag(fake_cognee, fake_cognee_dir):
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "--query", "Wer ist Reza?",
    ])
    assert rc == 0
    assert fake_cognee.search.call_args.kwargs["query_text"] == "Wer ist Reza?"


def test_json_output_is_valid_json(fake_cognee, fake_cognee_dir, capsys):
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "--json",
        "frage",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    # Header steht vor dem JSON, JSON ist die letzte zusammenhaengende Block.
    # Wir suchen den ersten "[" nach dem Header und parsen ab dort.
    idx = out.index("[")
    parsed = json.loads(out[idx:])
    assert parsed == ["antwort 1", "antwort 2"]


def test_top_k_passed_through(fake_cognee, fake_cognee_dir):
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "--top-k", "5",
        "frage",
    ])
    assert rc == 0
    assert fake_cognee.search.call_args.kwargs["top_k"] == 5


def test_missing_query_errors(fake_cognee, fake_cognee_dir, capsys):
    rc = cognee_search.main(["--cognee-dir", str(fake_cognee_dir)])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Query" in err


def test_empty_results(fake_cognee, fake_cognee_dir, capsys):
    fake_cognee.search.return_value = []
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "frage",
    ])
    assert rc == 0
    out = capsys.readouterr().out
    assert "Keine Ergebnisse gefunden" in out


def test_cognee_missing_exits_with_clear_message(monkeypatch, fake_cognee_dir, capsys):
    # Make `import cognee` raise ModuleNotFoundError(name='cognee')
    # by setting sys.modules entry to None.
    monkeypatch.setitem(sys.modules, "cognee", None)

    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "frage",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cognee Library nicht installiert" in err


def test_internal_module_not_found_propagates(monkeypatch, fake_cognee_dir):
    """Sub-Modul-ImportError aus cognee-Internal wird NICHT maskiert."""
    fake_root = types.ModuleType("cognee")

    async def _search_with_internal_import_error(**_kwargs):
        raise ModuleNotFoundError(
            "No module named 'cognee.shared.data_models'",
            name="cognee.shared.data_models",
        )

    fake_root.search = _search_with_internal_import_error
    monkeypatch.setitem(sys.modules, "cognee", fake_root)

    with pytest.raises(ModuleNotFoundError) as excinfo:
        cognee_search.main([
            "--cognee-dir", str(fake_cognee_dir),
            "frage",
        ])
    assert excinfo.value.name == "cognee.shared.data_models"


def test_runtime_error_propagates(fake_cognee, fake_cognee_dir):
    """Andere Exceptions (z.B. SQLite-Fehler) werden durchgereicht — kein
    irrefuehrender Wrapper-Text mehr."""
    fake_cognee.search.side_effect = RuntimeError("sqlite operational error")
    with pytest.raises(RuntimeError, match="sqlite operational error"):
        cognee_search.main([
            "--cognee-dir", str(fake_cognee_dir),
            "frage",
        ])


def test_subprocess_call_without_pythonpath(tmp_path):
    """Skript-Aufruf von beliebigem CWD ohne PYTHONPATH funktioniert.

    Fuehrt das Skript via subprocess aus /tmp aus, mit gestripptem
    PYTHONPATH. Pipeline-Paket muss trotzdem importierbar sein (sys.path-
    Setup im Skript-Header). Cognee selbst ist hier nicht installiert,
    daher erwarten wir die freundliche Fehlermeldung — entscheidend ist,
    dass es NICHT an `No module named 'pipeline'` scheitert.
    """
    (tmp_path / ".env").write_text("LLM_API_KEY=x\n", encoding="utf-8")
    script = Path(__file__).resolve().parent / "cognee_search.py"

    env = {k: v for k, v in os.environ.items() if k != "PYTHONPATH"}

    result = subprocess.run(
        [
            sys.executable, str(script),
            "--cognee-dir", str(tmp_path),
            "test",
        ],
        cwd="/tmp",
        env=env,
        capture_output=True,
        text=True,
    )

    # Der Pipeline-Import darf NICHT scheitern.
    assert "No module named 'pipeline'" not in result.stderr, (
        f"Pipeline-Import scheitert ohne PYTHONPATH:\n"
        f"stderr: {result.stderr}\nstdout: {result.stdout}"
    )

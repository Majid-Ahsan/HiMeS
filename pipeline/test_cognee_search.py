"""Tests fuer pipeline.cognee_search.

Cognee wird vollstaendig gemockt — kein echter Cognee-Aufruf in Tests.
"""

from __future__ import annotations

import json
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
    """Inject a fake `cognee` module + `cognee.shared.data_models.SearchType`."""
    fake_root = types.ModuleType("cognee")
    fake_root.search = AsyncMock(return_value=["antwort 1", "antwort 2"])

    fake_shared = types.ModuleType("cognee.shared")
    fake_data_models = types.ModuleType("cognee.shared.data_models")

    class _SearchType:
        GRAPH_COMPLETION = "GRAPH_COMPLETION"
        SUMMARIES = "SUMMARIES"
        INSIGHTS = "INSIGHTS"

    fake_data_models.SearchType = _SearchType

    monkeypatch.setitem(sys.modules, "cognee", fake_root)
    monkeypatch.setitem(sys.modules, "cognee.shared", fake_shared)
    monkeypatch.setitem(sys.modules, "cognee.shared.data_models", fake_data_models)
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
    assert kwargs["query_type"] == "GRAPH_COMPLETION"
    assert kwargs["top_k"] == 10

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


def test_search_type_passed_through(fake_cognee, fake_cognee_dir):
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "--search-type", "SUMMARIES",
        "frage",
    ])
    assert rc == 0
    assert fake_cognee.search.call_args.kwargs["query_type"] == "SUMMARIES"


def test_unknown_search_type_errors(fake_cognee, fake_cognee_dir, capsys):
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "--search-type", "DOES_NOT_EXIST",
        "frage",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "DOES_NOT_EXIST" in err


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
    # Make `import cognee` raise ImportError by setting sys.modules entry to None.
    monkeypatch.setitem(sys.modules, "cognee", None)
    monkeypatch.setitem(sys.modules, "cognee.shared", None)
    monkeypatch.setitem(sys.modules, "cognee.shared.data_models", None)

    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "frage",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "cognee nicht verfuegbar" in err


def test_cognee_search_runtime_error_hints_env(fake_cognee, fake_cognee_dir, capsys):
    fake_cognee.search.side_effect = RuntimeError("sqlite operational error")
    rc = cognee_search.main([
        "--cognee-dir", str(fake_cognee_dir),
        "frage",
    ])
    assert rc == 1
    err = capsys.readouterr().err
    assert "Cognee-Suche" in err
    assert ".env" in err

"""Tests fuer pipeline._cognee_env.load_cognee_env."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import _cognee_env  # noqa: E402


# ---------- Helpers ----------

def _write_env(dir_path: Path, content: str) -> Path:
    dir_path.mkdir(parents=True, exist_ok=True)
    env = dir_path / ".env"
    env.write_text(content, encoding="utf-8")
    return env


# Test-Variablen mit eindeutigem Praefix, damit echte System-Vars nicht
# gefaehrdet werden und cleanup eindeutig ist.
PREFIX = "HIMES_TEST_COGNEE_ENV_"


@pytest.fixture(autouse=True)
def _scrub_env(monkeypatch):
    """Stellt sicher, dass keine Test-Variable global nach dem Test bleibt.

    monkeypatch.setenv/delenv werden ohnehin am Test-Ende rueckgaengig gemacht;
    diese Fixture sorgt nur fuer einen sauberen Start, falls ein vorheriger
    Lauf abgebrochen waere.
    """
    import os
    for key in list(os.environ.keys()):
        if key.startswith(PREFIX):
            monkeypatch.delenv(key, raising=False)
    yield


# ---------- Tests ----------

def test_loads_normal_values(tmp_path, monkeypatch):
    _write_env(
        tmp_path,
        f"{PREFIX}A=hello\n{PREFIX}B=world\n",
    )
    resolved = _cognee_env.load_cognee_env(tmp_path)
    import os
    assert resolved == tmp_path
    assert os.environ[f"{PREFIX}A"] == "hello"
    assert os.environ[f"{PREFIX}B"] == "world"


def test_ignores_comments_and_empty_lines(tmp_path, monkeypatch):
    _write_env(
        tmp_path,
        "\n"
        "# Kommentar oben\n"
        "   # eingerueckter Kommentar\n"
        f"{PREFIX}KEY=value\n"
        "\n"
        "# noch ein Kommentar\n",
    )
    _cognee_env.load_cognee_env(tmp_path)
    import os
    assert os.environ[f"{PREFIX}KEY"] == "value"


def test_quoted_values_are_unquoted(tmp_path, monkeypatch):
    _write_env(
        tmp_path,
        f'{PREFIX}DOUBLE="quoted value"\n'
        f"{PREFIX}SINGLE='single quoted'\n"
        f'{PREFIX}JSON={{"max_tokens": 4096}}\n',
    )
    _cognee_env.load_cognee_env(tmp_path)
    import os
    assert os.environ[f"{PREFIX}DOUBLE"] == "quoted value"
    assert os.environ[f"{PREFIX}SINGLE"] == "single quoted"
    # JSON ohne aeussere Quotes bleibt wortwoertlich erhalten.
    assert os.environ[f"{PREFIX}JSON"] == '{"max_tokens": 4096}'


def test_missing_env_warns_no_crash(tmp_path, capsys):
    # tmp_path enthaelt keine .env
    resolved = _cognee_env.load_cognee_env(tmp_path)
    assert resolved == tmp_path
    err = capsys.readouterr().err
    assert "WARNUNG" in err
    assert ".env nicht gefunden" in err


def test_existing_env_var_not_overwritten(tmp_path, monkeypatch):
    monkeypatch.setenv(f"{PREFIX}EXISTING", "user_value")
    _write_env(tmp_path, f"{PREFIX}EXISTING=env_file_value\n")
    _cognee_env.load_cognee_env(tmp_path)
    import os
    assert os.environ[f"{PREFIX}EXISTING"] == "user_value"


def test_export_prefix_stripped(tmp_path, monkeypatch):
    _write_env(tmp_path, f"export {PREFIX}EXP=exported\n")
    _cognee_env.load_cognee_env(tmp_path)
    import os
    assert os.environ[f"{PREFIX}EXP"] == "exported"


def test_resolve_cognee_dir_arg_wins(monkeypatch, tmp_path):
    monkeypatch.setenv(_cognee_env.COGNEE_DIR_ENV, "/tmp/from-env")
    resolved = _cognee_env.resolve_cognee_dir(str(tmp_path))
    assert resolved == Path(str(tmp_path))


def test_resolve_cognee_dir_env_used_when_no_arg(monkeypatch, tmp_path):
    monkeypatch.setenv(_cognee_env.COGNEE_DIR_ENV, str(tmp_path))
    resolved = _cognee_env.resolve_cognee_dir(None)
    assert resolved == tmp_path


def test_resolve_cognee_dir_default_when_unset(monkeypatch):
    monkeypatch.delenv(_cognee_env.COGNEE_DIR_ENV, raising=False)
    resolved = _cognee_env.resolve_cognee_dir(None)
    assert resolved == Path(_cognee_env.DEFAULT_COGNEE_DIR)


def test_lines_without_equal_are_ignored(tmp_path, monkeypatch):
    _write_env(
        tmp_path,
        "garbage line without equals\n"
        f"{PREFIX}OK=fine\n",
    )
    _cognee_env.load_cognee_env(tmp_path)
    import os
    assert os.environ[f"{PREFIX}OK"] == "fine"

"""Tests fuer pipeline.ingest_to_cognee.

Cognee wird vollstaendig gemockt — kein echter Cognee-Aufruf in Tests.
Alle Tests arbeiten in tmp_path — niemals im echten ~/himes-data/.
"""

from __future__ import annotations

import json
import sys
import types
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

# Ensure pipeline/ is importable when pytest is run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import ingest_to_cognee  # noqa: E402


# ---------- Helpers ----------

def _today():
    return datetime.now(ingest_to_cognee.TIMEZONE).date()


def _iso(d):
    return d.isoformat()


def _write_log(tmp_path: Path, date_str: str, user: str = "majid",
               body: str = "Eintrag.") -> Path:
    p = tmp_path / "memory" / "daily-logs" / f"{date_str}_{user}.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        f"---\ntype: daily-log\ndate: {date_str}\nuser: {user}\n---\n\n{body}\n",
        encoding="utf-8",
    )
    return p


def _tracking(tmp_path: Path) -> dict:
    return json.loads((tmp_path / ".ingested.json").read_text(encoding="utf-8"))


@pytest.fixture
def fake_cognee(monkeypatch):
    """Inject a fake `cognee` module before lazy-import in the script."""
    fake = types.ModuleType("cognee")
    fake.add = AsyncMock(return_value=None)
    fake.cognify = AsyncMock(return_value=None)
    monkeypatch.setitem(sys.modules, "cognee", fake)
    return fake


@pytest.fixture
def auto_yes():
    return MagicMock(return_value=True)


@pytest.fixture
def auto_no():
    return MagicMock(return_value=False)


# ---------- New / unchanged / changed ----------

def test_new_file_ingests_and_writes_tracking(tmp_path, fake_cognee, auto_yes):
    p = _write_log(tmp_path, _iso(_today()))
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 1
    assert fake_cognee.cognify.call_count == 1

    track = _tracking(tmp_path)
    assert track["version"] == 1
    key = f"memory/daily-logs/{_iso(_today())}_majid.md"
    assert key in track["files"]
    entry = track["files"][key]
    assert "sha256" in entry and len(entry["sha256"]) == 64
    assert "ingested_at" in entry
    assert "cognee_dataset_id" in entry  # value may be None


def test_unchanged_file_is_skipped(tmp_path, fake_cognee, auto_yes, capsys):
    p = _write_log(tmp_path, _iso(_today()))
    ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    capsys.readouterr()
    fake_cognee.add.reset_mock()
    fake_cognee.cognify.reset_mock()

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 0
    assert fake_cognee.cognify.call_count == 0
    out = capsys.readouterr().out
    assert "skip (unveraendert" in out


def test_changed_file_reingests(tmp_path, fake_cognee, auto_yes, capsys):
    p = _write_log(tmp_path, _iso(_today()), body="Erst.")
    ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    track_before = _tracking(tmp_path)
    capsys.readouterr()

    p.write_text(
        f"---\ntype: daily-log\ndate: {_iso(_today())}\nuser: majid\n---\n\nGeaendert.\n",
        encoding="utf-8",
    )
    fake_cognee.add.reset_mock()
    fake_cognee.cognify.reset_mock()

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 1
    assert fake_cognee.cognify.call_count == 1
    out = capsys.readouterr().out
    assert "re-ingested" in out

    key = f"memory/daily-logs/{_iso(_today())}_majid.md"
    track_after = _tracking(tmp_path)
    assert track_after["files"][key]["sha256"] != track_before["files"][key]["sha256"]


# ---------- Frontmatter / date validation ----------

def test_missing_frontmatter_skips_with_warning(tmp_path, fake_cognee, auto_yes, capsys):
    p = tmp_path / "memory" / "daily-logs" / "kaputt.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("Kein Frontmatter hier, nur Text.\n", encoding="utf-8")

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 0
    err = capsys.readouterr().err
    assert "kein Frontmatter" in err


def test_today_date_no_prompt(tmp_path, fake_cognee):
    p = _write_log(tmp_path, _iso(_today()))
    prompt = MagicMock(return_value=True)
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=prompt,
    )
    assert rc == 0
    assert prompt.call_count == 0
    assert fake_cognee.add.call_count == 1


def test_yesterday_date_prompts_and_ingests_on_yes(tmp_path, fake_cognee):
    yesterday = _today() - timedelta(days=1)
    p = _write_log(tmp_path, _iso(yesterday))
    prompt = MagicMock(return_value=True)

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=prompt,
    )
    assert rc == 0
    assert prompt.call_count == 1
    assert "Frontmatter-Datum" in prompt.call_args.args[0]
    assert "1 Tag in der Vergangenheit" in prompt.call_args.args[0]
    assert fake_cognee.add.call_count == 1


def test_yesterday_date_skipped_on_no(tmp_path, fake_cognee, auto_no, capsys):
    yesterday = _today() - timedelta(days=1)
    p = _write_log(tmp_path, _iso(yesterday))

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_no,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 0
    out = capsys.readouterr().out
    assert "Datum nicht bestaetigt" in out
    assert not (tmp_path / ".ingested.json").exists()


def test_yes_flag_skips_prompt_for_past_date(tmp_path, fake_cognee):
    yesterday = _today() - timedelta(days=1)
    p = _write_log(tmp_path, _iso(yesterday))
    prompt = MagicMock(return_value=True)

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p), "--yes"],
        prompt_func=prompt,
    )
    assert rc == 0
    assert prompt.call_count == 0
    assert fake_cognee.add.call_count == 1


def test_future_date_with_yes_warns_but_ingests(tmp_path, fake_cognee, capsys):
    future = _today() + timedelta(days=3)
    p = _write_log(tmp_path, _iso(future))
    prompt = MagicMock(return_value=True)

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p), "--yes"],
        prompt_func=prompt,
    )
    assert rc == 0
    assert prompt.call_count == 0
    assert fake_cognee.add.call_count == 1
    err = capsys.readouterr().err
    assert "WARNUNG" in err
    assert "ZUKUNFT" in err


def test_far_past_with_yes_warns_but_ingests(tmp_path, fake_cognee, capsys):
    far_past = _today() - timedelta(days=60)
    p = _write_log(tmp_path, _iso(far_past))

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p), "--yes"],
        prompt_func=MagicMock(),
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 1
    err = capsys.readouterr().err
    assert "WARNUNG" in err
    assert "30 Tage" in err


# ---------- Modes: dir / all ----------

def test_dir_mode_finds_all_md(tmp_path, fake_cognee, auto_yes):
    d = tmp_path / "memory" / "daily-logs"
    _write_log(tmp_path, _iso(_today()), user="majid")
    _write_log(tmp_path, _iso(_today()), user="taha")

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--dir", str(d)],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 2


def test_all_mode_walks_data_dir_memory(tmp_path, fake_cognee, auto_yes):
    _write_log(tmp_path, _iso(_today()), user="majid")
    _write_log(tmp_path, _iso(_today()), user="neda")
    # File outside memory/ should be ignored by --all
    other = tmp_path / "elsewhere.md"
    other.write_text("---\ntype: daily-log\ndate: 2026-04-26\n---\n\nx\n", encoding="utf-8")

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--all"],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 2


# ---------- Dry-run ----------

def test_dry_run_makes_no_cognee_calls_and_no_tracking(tmp_path, fake_cognee, auto_yes):
    p = _write_log(tmp_path, _iso(_today()))
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p), "--dry-run"],
        prompt_func=auto_yes,
    )
    assert rc == 0
    assert fake_cognee.add.call_count == 0
    assert fake_cognee.cognify.call_count == 0
    assert not (tmp_path / ".ingested.json").exists()


# ---------- Reset tracking ----------

def test_reset_tracking_with_confirm(tmp_path, fake_cognee, auto_yes):
    # First populate tracking
    p = _write_log(tmp_path, _iso(_today()))
    ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert (tmp_path / ".ingested.json").exists()

    confirm = MagicMock(return_value=True)
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--reset-tracking"],
        prompt_func=confirm,
    )
    assert rc == 0
    assert confirm.call_count == 1
    assert "Tracking-Datei" in confirm.call_args.args[0]
    assert not (tmp_path / ".ingested.json").exists()


def test_reset_tracking_aborts_on_no(tmp_path, fake_cognee, auto_yes, auto_no):
    p = _write_log(tmp_path, _iso(_today()))
    ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--reset-tracking"],
        prompt_func=auto_no,
    )
    assert rc == 1
    assert (tmp_path / ".ingested.json").exists()


def test_reset_tracking_with_yes_skips_prompt(tmp_path, fake_cognee, auto_yes):
    p = _write_log(tmp_path, _iso(_today()))
    ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    prompt = MagicMock()
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--reset-tracking", "--yes"],
        prompt_func=prompt,
    )
    assert rc == 0
    assert prompt.call_count == 0
    assert not (tmp_path / ".ingested.json").exists()


# ---------- Tracking corruption ----------

def test_corrupt_tracking_is_backed_up(tmp_path, fake_cognee, auto_yes, capsys):
    track = tmp_path / ".ingested.json"
    track.write_text("{not-json", encoding="utf-8")

    p = _write_log(tmp_path, _iso(_today()))
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert rc == 0
    err = capsys.readouterr().err
    assert "beschaedigt" in err
    assert any(p.name.startswith(".ingested.json.broken") for p in tmp_path.iterdir())
    assert track.exists()  # neue Tracking-Datei wurde angelegt


# ---------- Cognee error handling ----------

def test_cognee_error_aborts_without_tracking_update(tmp_path, fake_cognee, auto_yes, capsys):
    fake_cognee.add.side_effect = RuntimeError("boom")
    p = _write_log(tmp_path, _iso(_today()))

    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "fehlgeschlagen" in err
    assert not (tmp_path / ".ingested.json").exists()


# ---------- Dataset-name uses file stem ----------

def test_dataset_name_is_filename_stem(tmp_path, fake_cognee, auto_yes):
    p = _write_log(tmp_path, _iso(_today()))
    ingest_to_cognee.main(
        ["--data-dir", str(tmp_path), "--file", str(p)],
        prompt_func=auto_yes,
    )
    expected = f"{_iso(_today())}_majid"
    assert fake_cognee.add.call_args.kwargs["dataset_name"] == expected


# ---------- Missing-mode error ----------

def test_no_mode_errors(tmp_path, fake_cognee, auto_yes, capsys):
    rc = ingest_to_cognee.main(
        ["--data-dir", str(tmp_path)],
        prompt_func=auto_yes,
    )
    assert rc == 1
    assert "--file, --dir oder --all" in capsys.readouterr().err

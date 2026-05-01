"""Tests für pipeline.memo_to_md.

Alle Tests arbeiten in tmp_path — niemals im echten ~/himes-data/.
"""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest

# Ensure pipeline/ is importable when pytest is run from repo root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pipeline import memo_to_md  # noqa: E402


def _run(args: list[str], stdin_text: str | None = None) -> int:
    if stdin_text is None:
        stdin = io.StringIO()
        stdin.isatty = lambda: True  # type: ignore[method-assign]
    else:
        stdin = io.StringIO(stdin_text)
        stdin.isatty = lambda: False  # type: ignore[method-assign]
    return memo_to_md.main(args, stdin=stdin)


def _path(tmp_path: Path, date: str, user: str) -> Path:
    return tmp_path / "memory" / "daily-logs" / f"{date}_{user}.md"


def test_stdin_input_creates_file(tmp_path):
    rc = _run(
        ["--data-dir", str(tmp_path), "--date", "2026-04-25", "--user", "majid"],
        stdin_text="Heute war ein langer Tag.",
    )
    assert rc == 0
    f = _path(tmp_path, "2026-04-25", "majid")
    assert f.exists()
    content = f.read_text()
    assert "type: daily-log" in content
    assert "date: 2026-04-25" in content
    assert "user: majid" in content
    assert "Heute war ein langer Tag." in content
    assert "## " not in content  # kein Header bei einzelnem Memo


def test_file_input_creates_file(tmp_path):
    src = tmp_path / "input.txt"
    src.write_text("Aus Datei gelesen.")
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-25",
            "--user", "majid",
            "--file", str(src),
        ],
    )
    assert rc == 0
    f = _path(tmp_path, "2026-04-25", "majid")
    assert "Aus Datei gelesen." in f.read_text()


def test_text_argument_creates_file(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-25",
            "--user", "majid",
            "--text", "Direkt als Argument.",
        ],
    )
    assert rc == 0
    f = _path(tmp_path, "2026-04-25", "majid")
    assert "Direkt als Argument." in f.read_text()


def test_append_wraps_first_entry_and_adds_header(tmp_path):
    base_args = ["--data-dir", str(tmp_path), "--date", "2026-04-25", "--user", "majid"]
    _run([*base_args, "--text", "Erster Eintrag."])
    rc = _run([*base_args, "--time", "15:30", "--text", "Zweiter Eintrag."])
    assert rc == 0

    content = _path(tmp_path, "2026-04-25", "majid").read_text()
    assert "## (Erster Eintrag)" in content
    assert "Erster Eintrag." in content
    assert "## 15:30" in content
    assert "Zweiter Eintrag." in content
    # Reihenfolge: Erster Eintrag-Block vor 15:30-Block
    assert content.index("## (Erster Eintrag)") < content.index("## 15:30")


def test_third_append_does_not_wrap_again(tmp_path):
    base_args = ["--data-dir", str(tmp_path), "--date", "2026-04-25", "--user", "majid"]
    _run([*base_args, "--text", "Erster."])
    _run([*base_args, "--time", "15:30", "--text", "Zweiter."])
    _run([*base_args, "--time", "20:00", "--text", "Dritter."])

    content = _path(tmp_path, "2026-04-25", "majid").read_text()
    assert content.count("## (Erster Eintrag)") == 1
    assert "## 15:30" in content
    assert "## 20:00" in content


def test_custom_user_is_respected(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-25",
            "--user", "neda",
            "--text", "Test",
        ],
    )
    assert rc == 0
    assert _path(tmp_path, "2026-04-25", "neda").exists()
    assert not _path(tmp_path, "2026-04-25", "majid").exists()


def test_custom_date_is_respected(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2025-12-31",
            "--user", "majid",
            "--text", "Silvester-Memo",
        ],
    )
    assert rc == 0
    f = _path(tmp_path, "2025-12-31", "majid")
    assert f.exists()
    assert "date: 2025-12-31" in f.read_text()


def test_empty_input_errors(tmp_path, capsys):
    rc = _run(
        ["--data-dir", str(tmp_path), "--date", "2026-04-25", "--user", "majid"],
        stdin_text="   \n  \t  \n",
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "Kein Input erhalten" in err or "leer" in err.lower()


def test_no_input_source_errors(tmp_path, capsys):
    rc = _run(
        ["--data-dir", str(tmp_path), "--date", "2026-04-25", "--user", "majid"],
    )
    assert rc == 1
    assert "Kein Input erhalten" in capsys.readouterr().err


def test_invalid_date_errors(tmp_path, capsys):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "25.04.2026",
            "--user", "majid",
            "--text", "egal",
        ],
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "YYYY-MM-DD" in err


def test_invalid_time_errors(tmp_path, capsys):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-25",
            "--time", "25:99",
            "--user", "majid",
            "--text", "egal",
        ],
    )
    assert rc == 1
    assert "HH:MM" in capsys.readouterr().err


def test_invalid_user_errors(tmp_path, capsys):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-25",
            "--user", "../etc/passwd",
            "--text", "exploit",
        ],
    )
    assert rc == 1
    assert "User-Identifier" in capsys.readouterr().err


def test_data_dir_env_var(tmp_path, monkeypatch):
    monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
    rc = _run(
        ["--date", "2026-04-25", "--user", "majid", "--text", "via env"],
    )
    assert rc == 0
    assert _path(tmp_path, "2026-04-25", "majid").exists()


def test_data_dir_arg_overrides_env(tmp_path, monkeypatch):
    other = tmp_path / "ignored"
    monkeypatch.setenv("HIMES_DATA_DIR", str(other))
    used = tmp_path / "used"
    rc = _run(
        [
            "--data-dir", str(used),
            "--date", "2026-04-25",
            "--user", "majid",
            "--text", "via arg",
        ],
    )
    assert rc == 0
    assert (used / "memory" / "daily-logs" / "2026-04-25_majid.md").exists()
    assert not other.exists()


def test_creates_missing_output_directory(tmp_path):
    deep = tmp_path / "does" / "not" / "exist"
    rc = _run(
        [
            "--data-dir", str(deep),
            "--date", "2026-04-25",
            "--user", "majid",
            "--text", "neu",
        ],
    )
    assert rc == 0
    assert (deep / "memory" / "daily-logs" / "2026-04-25_majid.md").exists()


def test_success_output_mentions_path_and_action(tmp_path, capsys):
    args = ["--data-dir", str(tmp_path), "--date", "2026-04-25", "--user", "majid"]

    _run([*args, "--text", "erst"])
    out_created = capsys.readouterr().out
    assert "neu erstellt" in out_created
    assert str(_path(tmp_path, "2026-04-25", "majid")) in out_created

    _run([*args, "--text", "zweit", "--time", "12:00"])
    out_appended = capsys.readouterr().out
    assert "angehängt" in out_appended


# ── ADR-050 D2: schema-compliant frontmatter + datums-anker ────────────────


def test_datums_anker_first_body_line(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30",
            "--user", "majid",
            "--text", "Memo-Inhalt.",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    _, body = content.split("---\n", 2)[1:]
    body_lines = [ln for ln in body.split("\n") if ln.strip()]
    assert body_lines[0] == "Heute ist Donnerstag, der 30. April 2026."


@pytest.mark.parametrize(
    "iso_date,expected_weekday",
    [
        ("2026-04-27", "Montag"),
        ("2026-04-28", "Dienstag"),
        ("2026-04-29", "Mittwoch"),
        ("2026-04-30", "Donnerstag"),
        ("2026-05-01", "Freitag"),
        ("2026-05-02", "Samstag"),
        ("2026-05-03", "Sonntag"),
    ],
)
def test_datums_anker_wochentag(tmp_path, iso_date, expected_weekday):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", iso_date,
            "--user", "majid",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, iso_date, "majid").read_text()
    assert f"Heute ist {expected_weekday}, der" in content


@pytest.mark.parametrize(
    "iso_date,expected_month,expected_day",
    [
        ("2026-01-15", "Januar", "15"),
        ("2026-03-08", "März", "8"),
        ("2026-07-04", "Juli", "4"),
        ("2026-12-31", "Dezember", "31"),
    ],
)
def test_datums_anker_monat(tmp_path, iso_date, expected_month, expected_day):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", iso_date,
            "--user", "majid",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, iso_date, "majid").read_text()
    assert f", der {expected_day}. {expected_month} 2026." in content


def test_tags_serialization(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--tags", "arbeit,familie,gesundheit",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    assert "tags: [arbeit, familie, gesundheit]" in content


def test_entities_serialization(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--entities", "majid,neda,taha",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    assert "entities: [majid, neda, taha]" in content


def test_tags_lowercase_normalization_and_dedupe(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--tags", " Arbeit , FAMILIE, arbeit ,Arbeit",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    assert "tags: [arbeit, familie]" in content


def test_tags_empty_omitted(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    assert "tags:" not in content
    assert "entities:" not in content


def test_tags_empty_string_omitted(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--tags", "  ,  ,",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    assert "tags:" not in content


def test_tags_german_umlauts_allowed(tmp_path):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--tags", "gemüse,straße,übung",
            "--text", "x",
        ],
    )
    assert rc == 0
    content = _path(tmp_path, "2026-04-30", "majid").read_text()
    assert "tags: [gemüse, straße, übung]" in content


def test_invalid_tag_chars_rejected(tmp_path, capsys):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--tags", "arbeit,foo bar",
            "--text", "x",
        ],
    )
    assert rc == 1
    err = capsys.readouterr().err
    assert "Ungültiges Zeichen" in err


def test_invalid_entity_chars_rejected(tmp_path, capsys):
    rc = _run(
        [
            "--data-dir", str(tmp_path),
            "--date", "2026-04-30", "--user", "majid",
            "--entities", "majid,foo@bar",
            "--text", "x",
        ],
    )
    assert rc == 1
    assert "Ungültiges Zeichen" in capsys.readouterr().err

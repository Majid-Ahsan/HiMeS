#!/usr/bin/env python3
"""Voice-Memo-zu-Markdown Mapper für HiMeS Daily-Logs.

Liest Text-Input (Stdin / --file / --text) und schreibt ihn nach
<data-dir>/memory/daily-logs/<YYYY-MM-DD>_<user>.md im Daily-Log-Format
gemäß docs/memory-schema.md (MVP).

Kein Audio, kein Whisper, kein Cognee — nur Text rein, Markdown raus.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_USER = "majid"
DEFAULT_DATA_DIR = "~/himes-data"
DATA_DIR_ENV = "HIMES_DATA_DIR"
TIMEZONE = ZoneInfo("Europe/Berlin")
FIRST_ENTRY_HEADER = "## (Erster Eintrag)"
USER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="voice_to_md",
        description="Schreibe Text-Input als Daily-Log-Markdown.",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", help="Pfad zu einer Text-Datei mit dem Memo")
    src.add_argument("--text", help="Memo-Text als Argument")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"User-Identifier (Default: {DEFAULT_USER})")
    parser.add_argument("--date", help="Datum YYYY-MM-DD (Default: heute, Europe/Berlin)")
    parser.add_argument("--time", help="Uhrzeit HH:MM für Multi-Memo-Header (Default: jetzt, Europe/Berlin)")
    parser.add_argument("--data-dir", help=f"Output-Basispfad (Default: ${DATA_DIR_ENV} oder {DEFAULT_DATA_DIR})")
    return parser


def read_input(args: argparse.Namespace, stdin=sys.stdin) -> str:
    if args.text is not None:
        return args.text
    if args.file is not None:
        return Path(args.file).expanduser().read_text(encoding="utf-8")
    if not stdin.isatty():
        return stdin.read()
    raise ValueError(
        "Kein Input erhalten. Nutze --text, --file oder pipe per Stdin."
    )


def parse_date(s: str) -> str:
    try:
        datetime.strptime(s, "%Y-%m-%d")
    except ValueError as e:
        raise ValueError(
            f"Ungültiges Datum: {s!r}. Erwartet YYYY-MM-DD (z.B. 2026-04-25)."
        ) from e
    return s


def parse_time(s: str) -> str:
    try:
        datetime.strptime(s, "%H:%M")
    except ValueError as e:
        raise ValueError(
            f"Ungültige Uhrzeit: {s!r}. Erwartet HH:MM (z.B. 14:30)."
        ) from e
    return s


def validate_user(user: str) -> str:
    if not USER_PATTERN.match(user):
        raise ValueError(
            f"Ungültiger User-Identifier: {user!r}. Erlaubt: a-z, A-Z, 0-9, _, -."
        )
    return user


def resolve_data_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get(DATA_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_DATA_DIR).expanduser()


def daily_log_path(data_dir: Path, date: str, user: str) -> Path:
    return data_dir / "memory" / "daily-logs" / f"{date}_{user}.md"


def build_frontmatter(date: str, user: str) -> str:
    return f"---\ntype: daily-log\ndate: {date}\nuser: {user}\n---\n"


def _split_frontmatter(content: str) -> tuple[str, str]:
    if not content.startswith("---\n"):
        raise ValueError("Datei hat kein YAML-Frontmatter — kann nicht parsen.")
    end = content.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Frontmatter nicht abgeschlossen — kann nicht parsen.")
    fm = content[: end + len("\n---\n")]
    body = content[end + len("\n---\n") :]
    return fm, body


def _has_entry_headers(body: str) -> bool:
    return any(line.startswith("## ") for line in body.splitlines())


def write_log(
    path: Path,
    date: str,
    user: str,
    time: str,
    text: str,
) -> str:
    """Schreibe oder appende den Log. Gibt 'created' oder 'appended' zurück."""
    text = text.strip()
    if not text:
        raise ValueError("Kein Input erhalten (Text war leer).")

    path.parent.mkdir(parents=True, exist_ok=True)

    if not path.exists():
        frontmatter = build_frontmatter(date, user)
        path.write_text(f"{frontmatter}\n{text}\n", encoding="utf-8")
        return "created"

    content = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(content)
    body = body.strip()
    new_block = f"## {time}\n\n{text}"

    if _has_entry_headers(body):
        new_content = f"{frontmatter}\n{body}\n\n{new_block}\n"
    elif body:
        wrapped = f"{FIRST_ENTRY_HEADER}\n\n{body}"
        new_content = f"{frontmatter}\n{wrapped}\n\n{new_block}\n"
    else:
        new_content = f"{frontmatter}\n{new_block}\n"

    path.write_text(new_content, encoding="utf-8")
    return "appended"


def main(argv: list[str] | None = None, stdin=sys.stdin) -> int:
    args = _build_parser().parse_args(argv)

    try:
        text = read_input(args, stdin=stdin)

        now = datetime.now(TIMEZONE)
        date = parse_date(args.date) if args.date else now.strftime("%Y-%m-%d")
        time = parse_time(args.time) if args.time else now.strftime("%H:%M")
        user = validate_user(args.user)
        data_dir = resolve_data_dir(args.data_dir)
        path = daily_log_path(data_dir, date, user)

        action = write_log(path, date, user, time, text)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Schreib-Fehler: {e}", file=sys.stderr)
        return 1

    label = "neu erstellt" if action == "created" else "angehängt"
    print(f"{path} ({label})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

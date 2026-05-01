#!/usr/bin/env python3
"""Memo-zu-Markdown Mapper für HiMeS Daily-Logs.

Liest Text-Input (Stdin / --file / --text) und schreibt ihn nach
<data-dir>/memory/daily-logs/<YYYY-MM-DD>_<user>.md im Daily-Log-Format
gemäß docs/memory-schema.md (MVP).

Kein Audio, kein Whisper, kein Cognee — nur Text rein, Markdown raus.

Modi (ADR-050 D2):
- write   (Default): schreibt frisch, fail bei existierender Datei
- replace: überschreibt existierende Datei vollständig

Append-Logik wurde entfernt — mehrere Memos pro Tag werden vom Bot
via Read+LLM-Merge zu kohärentem Fließtext verschmolzen (ADR-050 D3).
"""

from __future__ import annotations

import argparse
import os
import re
import sys
from datetime import date as date_cls, datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DEFAULT_USER = "majid"
DEFAULT_DATA_DIR = "~/himes-data"
DATA_DIR_ENV = "HIMES_DATA_DIR"
TIMEZONE = ZoneInfo("Europe/Berlin")
USER_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+$")
TAG_PATTERN = re.compile(r"^[a-zA-Z0-9_äöüÄÖÜß-]+$")
VALID_MODES = ("write", "replace")

WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]
MONTHS_DE = [
    "Januar", "Februar", "März", "April", "Mai", "Juni",
    "Juli", "August", "September", "Oktober", "November", "Dezember",
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="memo_to_md",
        description="Schreibe Text-Input als Daily-Log-Markdown.",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", help="Pfad zu einer Text-Datei mit dem Memo")
    src.add_argument("--text", help="Memo-Text als Argument")
    parser.add_argument("--user", default=DEFAULT_USER, help=f"User-Identifier (Default: {DEFAULT_USER})")
    parser.add_argument("--date", help="Datum YYYY-MM-DD (Default: heute, Europe/Berlin)")
    parser.add_argument("--time", help="Uhrzeit HH:MM (Default: jetzt, Europe/Berlin). Aktuell ohne Effekt auf Datei-Inhalt; reserviert für Voice-Phase 8b.")
    parser.add_argument("--data-dir", help=f"Output-Basispfad (Default: ${DATA_DIR_ENV} oder {DEFAULT_DATA_DIR})")
    parser.add_argument(
        "--tags",
        help="Komma-separierte Tags (z.B. arbeit,familie,gesundheit). Optional.",
    )
    parser.add_argument(
        "--entities",
        help="Komma-separierte Entities/Personen (z.B. majid,neda,taha). Optional.",
    )
    parser.add_argument(
        "--mode",
        choices=VALID_MODES,
        default="write",
        help="write (Default): fail bei existierender Datei. replace: überschreibe.",
    )
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


def normalize_list(raw: str | list[str] | None, kind: str) -> list[str]:
    """Komma-Liste oder Liste → normalisierte Items: lowercase, getrimmt, dedupe.

    Wirft ValueError bei ungültigen Zeichen. Leere Strings werden ignoriert.
    """
    if raw is None:
        return []
    items = raw.split(",") if isinstance(raw, str) else list(raw)
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        norm = item.strip().lower()
        if not norm:
            continue
        if not TAG_PATTERN.match(norm):
            raise ValueError(
                f"Ungültiges Zeichen in {kind}: {item!r}. "
                f"Erlaubt: a-z, A-Z, 0-9, _, -, deutsche Umlaute."
            )
        if norm in seen:
            continue
        seen.add(norm)
        result.append(norm)
    return result


def resolve_data_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get(DATA_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_DATA_DIR).expanduser()


def daily_log_path(
    date: str,
    user: str = DEFAULT_USER,
    data_dir: str | os.PathLike | None = None,
) -> Path:
    """Konstruiert den Pfad zur Daily-Log-Datei für gegebenes Datum + User.

    Auflösung von data_dir: arg → $HIMES_DATA_DIR → ~/himes-data
    (gleiches Pattern wie resolve_data_dir(); siehe auch ADR-050 D4).
    """
    base = resolve_data_dir(str(data_dir) if data_dir is not None else None)
    return base / "memory" / "daily-logs" / f"{date}_{user}.md"


def build_frontmatter(
    date: str,
    user: str,
    tags: list[str] | None = None,
    entities: list[str] | None = None,
) -> str:
    lines = [
        "---",
        "type: daily-log",
        f"date: {date}",
        f"user: {user}",
    ]
    if tags:
        lines.append(f"tags: [{', '.join(tags)}]")
    if entities:
        lines.append(f"entities: [{', '.join(entities)}]")
    lines.append("---\n")
    return "\n".join(lines)


def format_datums_anker(date_str: str) -> str:
    """'Heute ist <Wochentag>, der <D. Monat YYYY>.' (Punkt nach Tag-Zahl)."""
    d = date_cls.fromisoformat(date_str)
    weekday = WEEKDAYS_DE[d.weekday()]
    month = MONTHS_DE[d.month - 1]
    return f"Heute ist {weekday}, der {d.day}. {month} {d.year}."


def _render_file(
    date: str,
    user: str,
    text: str,
    tags: list[str],
    entities: list[str],
) -> str:
    frontmatter = build_frontmatter(date, user, tags, entities)
    anker = format_datums_anker(date)
    return f"{frontmatter}\n{anker}\n\n{text}\n"


def write_memo(
    text: str,
    user: str = DEFAULT_USER,
    date: str | None = None,
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    mode: str = "write",
    data_dir: str | None = None,
) -> dict:
    """Python-API für ADR-050 D4 (Direkt-Import durch daily-log-MCP).

    Returns:
        {"ok": True, "file_path": "<abs>", "action": "geschrieben"|"überschrieben"}

    Raises:
        ValueError: bei Validierungs-Fehlern oder existierender Datei in
            write-Modus.
        OSError: bei Schreib-/Filesystem-Fehlern.
    """
    if mode not in VALID_MODES:
        raise ValueError(
            f"Ungültiger Modus: {mode!r}. Erwartet einen von {VALID_MODES}."
        )

    text = text.strip()
    if not text:
        raise ValueError("Kein Input erhalten (Text war leer).")

    if date is None:
        date = datetime.now(TIMEZONE).strftime("%Y-%m-%d")
    else:
        date = parse_date(date)

    user = validate_user(user)
    norm_tags = normalize_list(tags, "tags")
    norm_entities = normalize_list(entities, "entities")
    path = daily_log_path(date, user, data_dir)

    path.parent.mkdir(parents=True, exist_ok=True)

    if mode == "write" and path.exists():
        raise ValueError(
            f"Datei existiert bereits: {path}. Nutze --mode replace zum Überschreiben."
        )

    content = _render_file(date, user, text, norm_tags, norm_entities)
    action = "überschrieben" if (mode == "replace" and path.exists()) else "geschrieben"
    path.write_text(content, encoding="utf-8")

    return {"ok": True, "file_path": str(path), "action": action}


def main(argv: list[str] | None = None, stdin=sys.stdin) -> int:
    args = _build_parser().parse_args(argv)

    try:
        text = read_input(args, stdin=stdin)
        if args.time is not None:
            parse_time(args.time)  # validate even if unused

        result = write_memo(
            text=text,
            user=args.user,
            date=args.date,
            tags=args.tags,
            entities=args.entities,
            mode=args.mode,
            data_dir=args.data_dir,
        )
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1
    except OSError as e:
        print(f"Schreib-Fehler: {e}", file=sys.stderr)
        return 1

    print(f"{result['file_path']} ({result['action']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())

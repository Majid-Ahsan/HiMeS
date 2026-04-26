#!/usr/bin/env python3
"""HiMeS Markdown-zu-Cognee Ingest (Phase 2.1, Schritt 6).

Liest Daily-Log Markdown-Dateien aus dem HiMeS-Memory-Pfad und uebergibt sie
an Cognee (cognee.add + cognee.cognify). Mit sha256-basiertem Idempotenz-
Tracking pro Datei und Date-Validation aus dem Frontmatter vor jedem Ingest.

Scope: nur Markdown-Lesen, Date-Check, Cognee-Ingest, Tracking-Update —
kein Whisper, keine LLM-Datums-Erkennung, kein MCP, keine Cognee-Visu.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, date as date_cls
from pathlib import Path
from typing import Callable
from zoneinfo import ZoneInfo


DEFAULT_DATA_DIR = "~/himes-data"
DATA_DIR_ENV = "HIMES_DATA_DIR"
TIMEZONE = ZoneInfo("Europe/Berlin")
TRACKING_FILENAME = ".ingested.json"
TRACKING_VERSION = 1
MEMORY_SUBDIR = "memory"
FAR_PAST_THRESHOLD_DAYS = 30

WEEKDAYS_DE = [
    "Montag", "Dienstag", "Mittwoch", "Donnerstag",
    "Freitag", "Samstag", "Sonntag",
]


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ingest_to_cognee",
        description="Ingest Markdown-Dateien aus dem HiMeS-Memory in Cognee.",
    )
    src = parser.add_mutually_exclusive_group()
    src.add_argument("--file", help="Eine einzelne Markdown-Datei")
    src.add_argument("--dir", help="Verzeichnis (rekursiv nach *.md durchsucht)")
    src.add_argument(
        "--all", action="store_true",
        help=f"Alle *.md-Dateien unter <data-dir>/{MEMORY_SUBDIR}/",
    )
    parser.add_argument(
        "--data-dir",
        help=f"Daten-Basispfad (Default: ${DATA_DIR_ENV} oder {DEFAULT_DATA_DIR})",
    )
    parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Skipt alle Confirmation-Prompts (fuer Automation)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Zeigt was passieren wuerde, ohne Cognee oder Tracking zu aendern",
    )
    parser.add_argument(
        "--reset-tracking", action="store_true",
        help="Loescht .ingested.json (mit Bestaetigung)",
    )
    return parser


def resolve_data_dir(arg: str | None) -> Path:
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get(DATA_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_DATA_DIR).expanduser()


def tracking_path(data_dir: Path) -> Path:
    return data_dir / TRACKING_FILENAME


def load_tracking(path: Path) -> dict:
    if not path.exists():
        return {"files": {}, "version": TRACKING_VERSION}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "files" not in data \
                or not isinstance(data["files"], dict):
            raise ValueError("Tracking-Format unerwartet")
        return data
    except (json.JSONDecodeError, ValueError, OSError) as e:
        backup = path.with_suffix(path.suffix + ".broken")
        if backup.exists():
            ts = datetime.now(TIMEZONE).strftime("%Y%m%dT%H%M%S")
            backup = path.with_suffix(f"{path.suffix}.broken.{ts}")
        path.rename(backup)
        print(
            f"WARNUNG: Tracking-Datei {path} beschaedigt ({e}). "
            f"Backup unter {backup}. Neue Tracking-Datei wird angelegt.",
            file=sys.stderr,
        )
        return {"files": {}, "version": TRACKING_VERSION}


def save_tracking(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def compute_hash(content_bytes: bytes) -> str:
    return hashlib.sha256(content_bytes).hexdigest()


def parse_frontmatter(text: str) -> dict | None:
    """Return frontmatter as flat dict or None if missing/malformed.

    Bewusst minimal: wir brauchen nur `date`, kein voller YAML-Parser noetig.
    """
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 4)
    if end == -1:
        return None
    fm_text = text[4:end + 1]
    result: dict = {}
    for line in fm_text.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip()] = value.strip()
    return result


def parse_iso_date(s: str) -> date_cls:
    return datetime.strptime(s, "%Y-%m-%d").date()


def _diff_label(diff_days: int) -> str:
    if diff_days == 0:
        return "heute"
    abs_days = abs(diff_days)
    word = "Tag" if abs_days == 1 else "Tage"
    direction = "in der Vergangenheit" if diff_days > 0 else "in der Zukunft"
    return f"{abs_days} {word} {direction}"


def _format_date_de(d: date_cls) -> str:
    return f"{d.isoformat()} ({WEEKDAYS_DE[d.weekday()]})"


def _interactive_confirm(message: str) -> bool:
    sys.stdout.write(message)
    sys.stdout.flush()
    try:
        answer = input().strip().lower()
    except EOFError:
        return False
    return answer in {"j", "y", "ja", "yes"}


def confirm_date(
    file_label: str,
    file_date: date_cls,
    today: date_cls,
    yes_flag: bool,
    prompt_func: Callable[[str], bool],
) -> bool:
    """True → ingest, False → skip (User hat abgelehnt)."""
    if file_date == today:
        return True

    diff_days = (today - file_date).days
    is_future = diff_days < 0
    is_far_past = diff_days > FAR_PAST_THRESHOLD_DAYS

    if yes_flag:
        if is_future or is_far_past:
            kind = (
                "in der ZUKUNFT" if is_future
                else f"mehr als {FAR_PAST_THRESHOLD_DAYS} Tage in der Vergangenheit"
            )
            print(
                f"WARNUNG: {file_label}: Frontmatter-Datum {file_date.isoformat()} "
                f"liegt {kind} (heute {today.isoformat()}). "
                f"--yes aktiv, ingest faehrt fort.",
                file=sys.stderr,
            )
        return True

    message = (
        f"   Datei: {file_label}\n"
        f"   Frontmatter-Datum: {_format_date_de(file_date)}\n"
        f"   Heute:             {_format_date_de(today)}\n"
        f"   Differenz: {_diff_label(diff_days)}\n"
        f"   Korrekt? [j/n] "
    )
    return prompt_func(message)


def discover_files(args: argparse.Namespace, data_dir: Path) -> list[Path]:
    if args.file:
        p = Path(args.file).expanduser().resolve()
        if not p.is_file():
            raise ValueError(f"Datei nicht gefunden: {p}")
        return [p]
    if args.dir:
        p = Path(args.dir).expanduser().resolve()
        if not p.is_dir():
            raise ValueError(f"Verzeichnis nicht gefunden: {p}")
        return sorted(p.rglob("*.md"))
    if args.all:
        memory = (data_dir / MEMORY_SUBDIR).resolve()
        if not memory.is_dir():
            raise ValueError(f"Memory-Verzeichnis nicht gefunden: {memory}")
        return sorted(memory.rglob("*.md"))
    raise ValueError("Bitte einen Modus angeben: --file, --dir oder --all.")


def tracking_key(file_path: Path, data_dir: Path) -> str:
    """Pfad relativ zu data_dir, sonst Absolutpfad als Fallback."""
    f = file_path.resolve()
    d = data_dir.resolve()
    try:
        return f.relative_to(d).as_posix()
    except ValueError:
        return str(f)


def dataset_name_for(file_path: Path) -> str:
    return file_path.stem


def _extract_dataset_id(result) -> str | None:
    """Best-effort: probiere ein paar Cognee-Result-Shapes ab."""
    if result is None:
        return None
    try:
        if isinstance(result, (list, tuple)):
            if not result:
                return None
            first = result[0]
            if hasattr(first, "id"):
                return str(first.id)
            if isinstance(first, dict) and "id" in first:
                return str(first["id"])
            return None
        if hasattr(result, "id"):
            return str(result.id)
        if isinstance(result, dict) and "id" in result:
            return str(result["id"])
    except Exception:
        return None
    return None


async def _cognee_ingest(text: str, dataset_name: str):
    # Lazy import: cognee laeuft nur auf Server (siehe cognee-setup/README).
    import cognee
    result = await cognee.add(text, dataset_name=dataset_name)
    await cognee.cognify()
    return _extract_dataset_id(result)


async def process_files(
    files: list[Path],
    data_dir: Path,
    yes_flag: bool,
    dry_run: bool,
    prompt_func: Callable[[str], bool],
) -> dict:
    today = datetime.now(TIMEZONE).date()
    track_path = tracking_path(data_dir)
    tracking = load_tracking(track_path) if not dry_run else load_tracking(track_path)

    counts = {
        "new": 0, "skipped_unchanged": 0, "reingested": 0,
        "skipped_user": 0, "warnings": 0,
    }

    for file_path in files:
        display = file_path.name
        key = tracking_key(file_path, data_dir)

        try:
            content_bytes = file_path.read_bytes()
        except OSError as e:
            print(f"WARNUNG: {display} → nicht lesbar ({e})", file=sys.stderr)
            counts["warnings"] += 1
            continue

        try:
            text = content_bytes.decode("utf-8")
        except UnicodeDecodeError as e:
            print(f"WARNUNG: {display} → kein UTF-8 ({e})", file=sys.stderr)
            counts["warnings"] += 1
            continue

        fm = parse_frontmatter(text)
        if fm is None:
            print(f"WARNUNG: {display} → uebersprungen (kein Frontmatter)",
                  file=sys.stderr)
            counts["warnings"] += 1
            continue

        date_value = fm.get("date")
        if not date_value:
            print(
                f"WARNUNG: {display} → uebersprungen (Frontmatter ohne date-Feld)",
                file=sys.stderr,
            )
            counts["warnings"] += 1
            continue
        try:
            file_date = parse_iso_date(date_value)
        except ValueError:
            print(
                f"WARNUNG: {display} → uebersprungen (date '{date_value}' nicht ISO YYYY-MM-DD)",
                file=sys.stderr,
            )
            counts["warnings"] += 1
            continue

        if not confirm_date(display, file_date, today, yes_flag, prompt_func):
            print(f"{display} → uebersprungen (Datum nicht bestaetigt — bitte Markdown korrigieren)")
            counts["skipped_user"] += 1
            continue

        sha = compute_hash(content_bytes)
        prev = tracking["files"].get(key)

        if prev and prev.get("sha256") == sha:
            print(f"{display} → skip (unveraendert, hash matches)")
            counts["skipped_unchanged"] += 1
            continue

        is_reingest = prev is not None
        dataset_name = dataset_name_for(file_path)

        if dry_run:
            verb = "re-ingested" if is_reingest else "eingespielt"
            print(f"{display} → [dry-run] wuerde {verb} (dataset={dataset_name})")
            if is_reingest:
                counts["reingested"] += 1
            else:
                counts["new"] += 1
            continue

        try:
            dataset_id = await _cognee_ingest(text, dataset_name)
        except Exception as e:
            print(
                f"FEHLER: {display} → Cognee-Aufruf fehlgeschlagen: {e}",
                file=sys.stderr,
            )
            print("Tracking nicht aktualisiert. Abbruch.", file=sys.stderr)
            return {"counts": counts, "total": len(files), "aborted": True}

        tracking["files"][key] = {
            "sha256": sha,
            "ingested_at": datetime.now(TIMEZONE).isoformat(timespec="seconds"),
            "cognee_dataset_id": dataset_id,
        }
        save_tracking(track_path, tracking)

        if is_reingest:
            suffix = f", Dataset-ID: {dataset_id}" if dataset_id else ""
            print(f"{display} → re-ingested (hash geaendert{suffix})")
            counts["reingested"] += 1
        else:
            suffix = f" (Dataset-ID: {dataset_id})" if dataset_id else ""
            print(f"{display} → eingespielt{suffix}")
            counts["new"] += 1

    return {"counts": counts, "total": len(files), "aborted": False}


def reset_tracking(
    data_dir: Path,
    yes_flag: bool,
    prompt_func: Callable[[str], bool],
) -> int:
    path = tracking_path(data_dir)
    if not path.exists():
        print(f"Keine Tracking-Datei unter {path} — nichts zu tun.")
        return 0
    if not yes_flag:
        msg = (
            f"Tracking-Datei {path} wird geloescht.\n"
            f"Alle Dateien werden bei naechstem Aufruf neu eingespielt.\n"
            f"Fortfahren? [j/n] "
        )
        if not prompt_func(msg):
            print("Abgebrochen — Tracking unveraendert.")
            return 1
    path.unlink()
    print(f"Tracking-Datei {path} geloescht.")
    return 0


def _print_summary(summary: dict) -> None:
    counts = summary["counts"]
    print()
    print("Zusammenfassung:")
    print(f"  Dateien gefunden:        {summary['total']}")
    print(f"  Neu eingespielt:         {counts['new']}")
    print(f"  Re-ingested:             {counts['reingested']}")
    print(f"  Skip (unveraendert):     {counts['skipped_unchanged']}")
    print(f"  Uebersprungen (User):    {counts['skipped_user']}")
    print(f"  Warnings:                {counts['warnings']}")
    if summary.get("aborted"):
        print("  ABBRUCH wegen Fehler.")


def main(
    argv: list[str] | None = None,
    prompt_func: Callable[[str], bool] | None = None,
) -> int:
    if prompt_func is None:
        prompt_func = _interactive_confirm
    args = _build_parser().parse_args(argv)

    try:
        data_dir = resolve_data_dir(args.data_dir)
        if args.reset_tracking:
            return reset_tracking(data_dir, args.yes, prompt_func)
        files = discover_files(args, data_dir)
    except ValueError as e:
        print(f"Fehler: {e}", file=sys.stderr)
        return 1

    if not files:
        print("Keine Markdown-Dateien gefunden.")
        return 0

    summary = asyncio.run(
        process_files(files, data_dir, args.yes, args.dry_run, prompt_func)
    )
    _print_summary(summary)
    return 1 if summary.get("aborted") else 0


if __name__ == "__main__":
    sys.exit(main())

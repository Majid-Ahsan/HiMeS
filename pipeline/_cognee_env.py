"""Cognee-spezifisches .env-Loading fuer Pipeline-Skripte.

Cognee 1.0.3 liest seine .env-Datei nur, wenn das Skript aus dem
Cognee-Verzeichnis heraus aufgerufen wird (Working-Directory-abhaengig).
Beim Aufruf aus anderen Verzeichnissen faellt Cognee auf seinen Default
zurueck (venv-Pfad), was nach der Daten-Migration in Phase 2.1 Schritt 3
nicht mehr existiert -> SQLite OperationalError.

Workaround: Pipeline-Skripte laden die .env-Datei selbst und setzen die
noetigen Env-Vars BEVOR `cognee` importiert wird. Damit funktionieren die
Skripte aus jedem Working-Directory. Siehe ADR-044.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


DEFAULT_COGNEE_DIR = "/home/ali/cognee"
COGNEE_DIR_ENV = "COGNEE_DIR"


def _strip_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
        return value[1:-1]
    return value


def _parse_env_line(line: str) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        return None
    key, _, value = stripped.partition("=")
    key = key.strip()
    if not key:
        return None
    # Strip optional `export ` prefix that some shells/.env files use.
    if key.startswith("export "):
        key = key[len("export "):].strip()
        if not key:
            return None
    return key, _strip_quotes(value.strip())


def resolve_cognee_dir(arg: str | None = None) -> Path:
    """Cognee-Verzeichnis bestimmen: arg > $COGNEE_DIR > Default."""
    if arg:
        return Path(arg).expanduser()
    env = os.environ.get(COGNEE_DIR_ENV)
    if env:
        return Path(env).expanduser()
    return Path(DEFAULT_COGNEE_DIR)


def load_cognee_env(cognee_dir: str | os.PathLike | None = None) -> Path:
    """Liest <cognee_dir>/.env und setzt fehlende Env-Vars.

    - Variablen die bereits in os.environ stehen werden NICHT ueberschrieben
      (User kann manuell vorgeben).
    - Kommentare (# am Zeilenanfang nach Trim) und leere Zeilen werden ignoriert.
    - Quoting in Werten (basic shell-style: "..." und '...') wird entfernt.
    - Bei fehlender .env: Warning auf stderr, kein Crash.

    Returns: das aufgeloeste cognee_dir (auch wenn keine .env gefunden wurde),
    damit Caller den Pfad fuer Header-Ausgabe nutzen koennen.
    """
    resolved = resolve_cognee_dir(str(cognee_dir) if cognee_dir is not None else None)
    env_path = resolved / ".env"

    if not env_path.is_file():
        print(
            f"WARNUNG: Cognee .env nicht gefunden unter {env_path}. "
            f"Cognee wird auf seinen Default zurueckfallen "
            f"(Env-Vars ggf. anders gesetzt?).",
            file=sys.stderr,
        )
        return resolved

    try:
        text = env_path.read_text(encoding="utf-8")
    except OSError as e:
        print(
            f"WARNUNG: Cognee .env nicht lesbar ({env_path}): {e}",
            file=sys.stderr,
        )
        return resolved

    for raw_line in text.splitlines():
        parsed = _parse_env_line(raw_line)
        if parsed is None:
            continue
        key, value = parsed
        if key in os.environ:
            continue
        os.environ[key] = value

    return resolved

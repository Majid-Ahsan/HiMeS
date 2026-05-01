#!/usr/bin/env python3
"""Daily-Log MCP Server — schreibt und liest Daily-Log-Markdown.

Tools (ADR-050 D9):
- log_daily_entry — schema-konformes MD schreiben + Ingest planen
- read_daily_log  — existierende Datei lesen (für Merge-Workflow D3)

Skeleton-Implementierung: hints.extract_hints und ingest.schedule_ingest
sind aktuell Stubs (Schritte 3 und 4 des Implementierungsplans).
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

# sys.path-Setup VOR allen Repo-Imports (ADR-044).
_REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# .env-Load VOR cognee-Import (ADR-044). memo_to_md selbst braucht cognee
# nicht, aber ingest.py wird in Schritt 4 cognee importieren — Loading muss
# vor jeglichem cognee-Import passieren, also gleich hier oben.
from pipeline._cognee_env import load_cognee_env  # noqa: E402

load_cognee_env()

# Cognee top-level preloaden (ADR-044 + Inspektions-Report Schritt 4b E2):
# der erste cognee-Import dauert mehrere Sekunden und würde sonst beim
# ersten Tool-Aufruf den Event-Loop blockieren. Hier einmalig beim
# MCP-Server-Start, danach ist process_files() im ingest-Worker schnell.
import cognee  # noqa: E402, F401  -- preload, used indirectly via pipeline.ingest_to_cognee

from pipeline.memo_to_md import (  # noqa: E402
    daily_log_path,
    parse_date,
    validate_user,
    write_memo,
)
from mcp.server.fastmcp import FastMCP  # noqa: E402

# Lokale Sub-Module (hints.py / ingest.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import hints  # noqa: E402
import ingest  # noqa: E402


mcp = FastMCP(
    "daily-log",
    host=os.getenv("DAILY_LOG_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("DAILY_LOG_MCP_PORT", "8003")),
)


_FRONTMATTER_LIST_RE = re.compile(r"^\[(.*)\]$")
_HINT_WRITE = "Konnte Daily-Log nicht speichern."
_HINT_READ = "Konnte Daily-Log nicht lesen."
_HINT_FAILURES = "Konnte Failure-Liste nicht lesen."
_HINT_RETRY = "Konnte Retry nicht ausführen."


def _err(exc: Exception, hint: str, retry: bool) -> dict:
    return {
        "ok": False,
        "error": type(exc).__name__,
        "detail": str(exc),
        "user_message_hint": hint,
        "retry_suggested": retry,
    }


def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Parst HiMeS-Daily-Log-Frontmatter (deterministisch, kein PyYAML).

    Erkennt nur die fünf Daily-Log-Felder: type/date/user/tags/entities.
    Listen werden aus ``[a, b, c]``-Format gelesen. Unbekannte Felder werden
    ignoriert. Wirft ValueError bei kaputtem Frontmatter.

    Returns: (frontmatter_dict, body_string).
    """
    if not text.startswith("---\n"):
        raise ValueError("Datei hat kein YAML-Frontmatter.")
    end = text.find("\n---\n", 4)
    if end == -1:
        raise ValueError("Frontmatter nicht abgeschlossen.")
    fm_block = text[4:end]
    body = text[end + len("\n---\n") :]

    fm: dict = {}
    for line in fm_block.splitlines():
        if not line.strip() or ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key not in {"type", "date", "user", "tags", "entities"}:
            continue
        list_match = _FRONTMATTER_LIST_RE.match(value)
        if list_match:
            inner = list_match.group(1).strip()
            fm[key] = [item.strip() for item in inner.split(",") if item.strip()] if inner else []
        else:
            fm[key] = value
    return fm, body


@mcp.tool(
    description=(
        "Speichert einen bereinigten Daily-Log-Eintrag als Markdown und "
        "plant Cognee-Ingest. Modi: write (Default, fail bei existierender "
        "Datei) oder replace (überschreibt)."
    )
)
async def log_daily_entry(
    text: str,
    user: str = "majid",
    date: str | None = None,
    tags: list[str] | None = None,
    entities: list[str] | None = None,
    mode: str = "write",
) -> dict:
    try:
        result = write_memo(
            text=text,
            user=user,
            date=date,
            tags=tags,
            entities=entities,
            mode=mode,
        )
    except ValueError as e:
        return _err(e, _HINT_WRITE, retry=False)
    except OSError as e:
        return _err(e, _HINT_WRITE, retry=True)

    extracted_hints = hints.extract_hints(text)
    ingest_result = ingest.schedule_ingest(result["file_path"])

    return {
        "ok": True,
        "file_path": result["file_path"],
        "action": result["action"],
        "ingest_status": ingest_result["status"],
        "queue_position": ingest_result["queue_position"],
        "extracted_hints": extracted_hints,
    }


@mcp.tool(
    description=(
        "Liest eine existierende Daily-Log-Datei für den Merge-Workflow. "
        "Returnt exists=False ohne Fehler, wenn keine Datei vorhanden ist."
    )
)
async def read_daily_log(date: str, user: str = "majid") -> dict:
    try:
        parse_date(date)
        validate_user(user)
        path = daily_log_path(date, user)
    except ValueError as e:
        return _err(e, _HINT_READ, retry=False)

    if not path.exists():
        return {"ok": True, "exists": False, "file_path": str(path)}

    try:
        content = path.read_text(encoding="utf-8")
        fm, body = _parse_frontmatter(content)
    except OSError as e:
        # IO-Problem (Disk, Permission, …) — Retry kann helfen.
        return _err(e, _HINT_READ, retry=True)
    except ValueError as e:
        # Daten-Problem (kaputtes Frontmatter, Format) — Retry kann
        # nichts ändern, User muss die Datei reparieren.
        return _err(e, _HINT_READ, retry=False)

    return {
        "ok": True,
        "exists": True,
        "file_path": str(path),
        "content": content,
        "frontmatter": fm,
        "body": body,
    }


@mcp.tool(
    description=(
        "Listet Daily-Logs, deren Cognee-Ingest fehlgeschlagen ist. "
        "Liefert für jeden Eintrag file_path, error_type, error_detail, "
        "timestamp und retry_count."
    )
)
async def list_failed_ingests() -> dict:
    try:
        return {"ok": True, "failures": ingest.list_failed()}
    except Exception as e:
        return _err(e, _HINT_FAILURES, retry=True)


@mcp.tool(
    description=(
        "Retried fehlgeschlagene Cognee-Ingests. file_path optional — "
        "ohne Argument werden alle Failures neu in die Queue gelegt."
    )
)
async def retry_failed_ingests(file_path: str | None = None) -> dict:
    try:
        result = await ingest.retry_failed(file_path)
        return {"ok": True, **result}
    except Exception as e:
        return _err(e, _HINT_RETRY, retry=True)


if __name__ == "__main__":
    transport = os.getenv("DAILY_LOG_MCP_TRANSPORT", "sse")
    mcp.run(transport=transport)

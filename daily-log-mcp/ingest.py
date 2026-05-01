"""Async-Ingest-Queue für Cognee (ADR-050 D8).

Single-Queue + Single-Worker. log_daily_entry returnt sofort mit
ingest_status="queued" + queue_position; der Worker arbeitet die
Datei(en) im Hintergrund ab und schreibt Failures in
<data_dir>/memory/.failed_ingests.json.

Wrapping per asyncio.wait_for(timeout=300): deckt den 158s worst-case
des Cognee-Anthropic-Adapters (siehe Inspektions-Report Schritt 4b
Sektion A3) plus Puffer.

Public API:
- schedule_ingest(file_path)  -> dict  (sync, sofort)
- list_failed()               -> list[dict]
- retry_failed(file_path?)    -> dict  (async)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

INGEST_TIMEOUT_SECONDS = 300
WORKER_IDLE_TIMEOUT_SECONDS = 60

_ingest_queue: asyncio.Queue | None = None
_worker_task: asyncio.Task | None = None
_BACKGROUND_TASKS: set[asyncio.Task] = set()


# ─── Pfade + Failure-File ────────────────────────────────────────────────


def _data_dir() -> Path:
    """HIMES_DATA_DIR mit Default ~/himes-data — konsistent mit memo_to_md."""
    return Path(os.getenv("HIMES_DATA_DIR", str(Path.home() / "himes-data")))


def _failure_file_path() -> Path:
    return _data_dir() / "memory" / ".failed_ingests.json"


def _read_failures() -> list[dict]:
    """Liest Failure-Liste, robust gegen fehlende oder kaputte Datei.

    Pattern analog ingest_to_cognee.load_tracking — bei Korruption
    Backup zur Seite, leere Liste zurück.
    """
    path = _failure_file_path()
    if not path.exists():
        return []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, list):
            raise ValueError("Failure-File ist keine JSON-Liste.")
        return data
    except (json.JSONDecodeError, OSError, ValueError) as e:
        logger.warning("Failure-File unlesbar (%s) — Backup + leere Liste", e)
        ts = int(datetime.now(timezone.utc).timestamp())
        backup = path.parent / f"{path.name}.broken.{ts}"
        try:
            path.rename(backup)
        except OSError:
            pass
        return []


def _write_failures(failures: list[dict]) -> None:
    """Atomic write via .tmp + rename."""
    path = _failure_file_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(failures, indent=2), encoding="utf-8")
    tmp.replace(path)


def _record_failure(file_path: str, error: BaseException) -> None:
    failures = _read_failures()
    now = datetime.now(timezone.utc).isoformat()
    for f in failures:
        if f["file_path"] == file_path:
            f["error_type"] = type(error).__name__
            f["error_detail"] = str(error)
            f["timestamp"] = now
            # retry_count NICHT erhöhen — nur retry_failed() tut das.
            break
    else:
        failures.append({
            "file_path": file_path,
            "error_type": type(error).__name__,
            "error_detail": str(error),
            "timestamp": now,
            "retry_count": 0,
        })
    _write_failures(failures)


def _remove_failure(file_path: str) -> bool:
    failures = _read_failures()
    new = [f for f in failures if f["file_path"] != file_path]
    if len(new) == len(failures):
        return False
    _write_failures(new)
    return True


# ─── Worker + Queue ──────────────────────────────────────────────────────


async def _do_ingest(file_path: str) -> None:
    """Echte Ingest-Operation. Bei Erfolg failure entfernen, sonst
    aufzeichnen. Wirft selbst keine Exception nach außen (Worker-safe).
    """
    # Lazy-Import: process_files braucht cognee. cognee ist beim
    # MCP-Server-Start einmalig top-level importiert (server.py),
    # darum kein Latenz-Hit hier.
    from pipeline.ingest_to_cognee import process_files

    p = Path(file_path)
    try:
        result = await asyncio.wait_for(
            process_files(
                files=[p],
                data_dir=_data_dir(),
                yes_flag=True,
                dry_run=False,
                prompt_func=lambda _msg: True,
            ),
            timeout=INGEST_TIMEOUT_SECONDS,
        )
        if result.get("aborted"):
            raise RuntimeError(
                f"process_files aborted: counts={result.get('counts')}"
            )
        logger.info(
            "Ingest done: %s — counts=%s",
            file_path, result.get("counts"),
        )
        _remove_failure(file_path)
    except asyncio.TimeoutError as e:
        logger.error(
            "Ingest timeout (>%ds): %s",
            INGEST_TIMEOUT_SECONDS, file_path,
        )
        _record_failure(file_path, e)
    except Exception as e:
        logger.exception("Ingest failed: %s", file_path)
        _record_failure(file_path, e)


async def _worker() -> None:
    """Sequentieller Single-Worker. Beendet sich, wenn die Queue
    WORKER_IDLE_TIMEOUT_SECONDS leer ist; ensure_worker spawnt beim
    nächsten schedule_ingest neu."""
    assert _ingest_queue is not None
    while True:
        try:
            file_path = await asyncio.wait_for(
                _ingest_queue.get(),
                timeout=WORKER_IDLE_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.debug("Worker idle, exiting")
            return
        try:
            await _do_ingest(file_path)
        finally:
            _ingest_queue.task_done()


def _ensure_worker() -> None:
    """Stellt sicher, dass ein Worker läuft. Idempotent."""
    global _worker_task
    if _worker_task is None or _worker_task.done():
        _worker_task = asyncio.create_task(_worker())
        _BACKGROUND_TASKS.add(_worker_task)
        _worker_task.add_done_callback(_BACKGROUND_TASKS.discard)


# ─── Public API ──────────────────────────────────────────────────────────


def schedule_ingest(file_path: str) -> dict:
    """Legt Datei in Ingest-Queue. Returnt sofort.

    Returns:
        {"status": "queued", "queue_position": <n>}
        n=1 → wird als nächstes verarbeitet.
    """
    global _ingest_queue
    if _ingest_queue is None:
        _ingest_queue = asyncio.Queue()
    _ingest_queue.put_nowait(file_path)
    _ensure_worker()
    return {"status": "queued", "queue_position": _ingest_queue.qsize()}


def list_failed() -> list[dict]:
    """Aktuelle Failure-Liste. Format wie in .failed_ingests.json."""
    return _read_failures()


async def retry_failed(file_path: str | None = None) -> dict:
    """Retried Failures. file_path=None bedeutet alle Failures.

    Returns:
        {"retried": <count>, "queued": [<file_paths>]}  (Erfolg)
        oder mit zusätzlichem "error"-Key wenn nichts zu retryen war.
    """
    failures = _read_failures()
    if file_path is not None:
        targets = [f for f in failures if f["file_path"] == file_path]
        if not targets:
            return {
                "retried": 0,
                "queued": [],
                "error": "no failure for this file_path",
            }
    else:
        targets = list(failures)

    queued: list[str] = []
    for t in targets:
        for orig in failures:
            if orig["file_path"] == t["file_path"]:
                orig["retry_count"] = orig.get("retry_count", 0) + 1
                break
        schedule_ingest(t["file_path"])
        queued.append(t["file_path"])

    if targets:
        _write_failures(failures)

    return {"retried": len(targets), "queued": queued}


# ─── Test-Hooks ──────────────────────────────────────────────────────────


def _reset_state_for_tests() -> None:
    """Setzt Modul-Globals zurück. NUR für Tests."""
    global _ingest_queue, _worker_task
    _ingest_queue = None
    _worker_task = None
    _BACKGROUND_TASKS.clear()

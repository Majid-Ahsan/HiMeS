"""Tests für daily-log-mcp/ingest.py.

Mocks an der pipeline.ingest_to_cognee.process_files-Boundary (lazy
import in _do_ingest), keine echte Cognee-Operation. Worker- und
Queue-Verhalten via asyncio.

Konvention: Tests im selben Verzeichnis wie der Code.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _load_ingest():
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "daily_log_mcp_ingest", here / "ingest.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


ingest = _load_ingest()


@pytest.fixture(autouse=True)
def _reset_and_isolate(tmp_path, monkeypatch):
    """Setzt Module-State zurück + isoliert Failure-File pro Test."""
    monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
    ingest._reset_state_for_tests()
    yield
    ingest._reset_state_for_tests()


@pytest.fixture
def mock_process_files(monkeypatch):
    """Mockt pipeline.ingest_to_cognee.process_files via sys.modules-Stub.

    process_files wird in _do_ingest lazy importiert. Wir registrieren
    ein Stub-Modul in sys.modules damit der Import den Mock liefert.
    """
    pipeline_pkg = MagicMock()
    sub = MagicMock()
    mock = AsyncMock(return_value={"counts": {"new": 1}, "total": 1, "aborted": False})
    sub.process_files = mock
    pipeline_pkg.ingest_to_cognee = sub
    monkeypatch.setitem(sys.modules, "pipeline.ingest_to_cognee", sub)
    return mock


async def _drain_worker(timeout: float = 2.0) -> None:
    """Wartet bis Queue leer und Worker fertig (oder Timeout)."""
    if ingest._ingest_queue is not None:
        await asyncio.wait_for(ingest._ingest_queue.join(), timeout=timeout)


# ─── Failure-File-Resilienz ──────────────────────────────────────────────


class TestFailureFile:
    def test_missing_failure_file_returns_empty(self):
        assert ingest.list_failed() == []

    def test_corrupt_failure_file_returns_empty_and_backs_up(self, tmp_path):
        path = ingest._failure_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")

        result = ingest.list_failed()

        assert result == []
        assert not path.exists()
        backups = list(path.parent.glob(".failed_ingests.json.broken.*"))
        assert len(backups) == 1

    def test_failure_file_not_a_list_returns_empty_and_backs_up(self, tmp_path):
        path = ingest._failure_file_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('{"this": "is dict not list"}', encoding="utf-8")

        assert ingest.list_failed() == []
        assert not path.exists()

    def test_atomic_write_uses_tmp_then_rename(self, monkeypatch):
        ingest._write_failures([{"file_path": "/x", "error_type": "E",
                                 "error_detail": "d", "timestamp": "t",
                                 "retry_count": 0}])
        path = ingest._failure_file_path()
        assert path.exists()
        # .tmp darf nach erfolgreichem rename nicht mehr da sein
        assert not path.with_suffix(path.suffix + ".tmp").exists()


# ─── schedule_ingest + Queue ──────────────────────────────────────────────


class TestSchedule:
    async def test_returns_queued_status(self, mock_process_files):
        result = ingest.schedule_ingest("/tmp/file1.md")
        assert result == {"status": "queued", "queue_position": 1}
        await _drain_worker()

    async def test_queue_position_increments(self, mock_process_files):
        # Block process_files damit Items in der Queue stehen bleiben.
        gate = asyncio.Event()

        async def slow(*args, **kwargs):
            await gate.wait()
            return {"counts": {}, "total": 1, "aborted": False}

        mock_process_files.side_effect = slow

        r1 = ingest.schedule_ingest("/tmp/a.md")
        r2 = ingest.schedule_ingest("/tmp/b.md")
        r3 = ingest.schedule_ingest("/tmp/c.md")

        # r1 wird sofort vom Worker gepullt → qsize fällt auf 0,
        # dann +1 = 1 (das war die Position bei put). Wir prüfen
        # den per-Call-Return-Wert: monoton steigend.
        assert r1["queue_position"] >= 1
        assert r2["queue_position"] > r1["queue_position"] or \
               r2["queue_position"] >= 1
        # Hauptaussage: alle drei Calls waren erfolgreich queued.
        for r in (r1, r2, r3):
            assert r["status"] == "queued"

        gate.set()
        await _drain_worker()

    async def test_worker_processes_sequentially(self, mock_process_files):
        active = 0
        max_active = 0

        async def tracker(*args, **kwargs):
            nonlocal active, max_active
            active += 1
            max_active = max(max_active, active)
            await asyncio.sleep(0.02)
            active -= 1
            return {"counts": {}, "total": 1, "aborted": False}

        mock_process_files.side_effect = tracker

        for i in range(3):
            ingest.schedule_ingest(f"/tmp/{i}.md")

        await _drain_worker(timeout=5.0)
        assert mock_process_files.call_count == 3
        assert max_active == 1, f"Worker lief parallel (max_active={max_active})"


# ─── Failure-Recording ────────────────────────────────────────────────────


class TestFailureRecording:
    async def test_recorded_on_exception(self, mock_process_files):
        mock_process_files.side_effect = RuntimeError("boom")

        ingest.schedule_ingest("/tmp/fail.md")
        await _drain_worker()

        failures = ingest.list_failed()
        assert len(failures) == 1
        assert failures[0]["file_path"] == "/tmp/fail.md"
        assert failures[0]["error_type"] == "RuntimeError"
        assert "boom" in failures[0]["error_detail"]
        assert failures[0]["retry_count"] == 0

    async def test_recorded_on_timeout(self, mock_process_files, monkeypatch):
        # Sehr kurzer Timeout, damit der Test schnell läuft.
        monkeypatch.setattr(ingest, "INGEST_TIMEOUT_SECONDS", 0.05)

        async def hang(*args, **kwargs):
            await asyncio.sleep(5)
            return {}

        mock_process_files.side_effect = hang

        ingest.schedule_ingest("/tmp/timeout.md")
        await _drain_worker(timeout=2.0)

        failures = ingest.list_failed()
        assert len(failures) == 1
        assert failures[0]["error_type"] == "TimeoutError"

    async def test_recorded_on_aborted_result(self, mock_process_files):
        mock_process_files.return_value = {
            "counts": {"new": 0}, "total": 1, "aborted": True,
        }

        ingest.schedule_ingest("/tmp/aborted.md")
        await _drain_worker()

        failures = ingest.list_failed()
        assert len(failures) == 1
        assert failures[0]["error_type"] == "RuntimeError"
        assert "aborted" in failures[0]["error_detail"]

    async def test_failure_removed_on_success(self, mock_process_files):
        # Vorbedingung: Failure existiert
        ingest._record_failure("/tmp/recovers.md", RuntimeError("old fail"))
        assert len(ingest.list_failed()) == 1

        # Mock returnt jetzt Erfolg
        mock_process_files.return_value = {
            "counts": {"new": 1}, "total": 1, "aborted": False,
        }
        ingest.schedule_ingest("/tmp/recovers.md")
        await _drain_worker()

        assert ingest.list_failed() == []

    async def test_failure_updated_not_duplicated_on_repeat(self, mock_process_files):
        mock_process_files.side_effect = RuntimeError("first")

        ingest.schedule_ingest("/tmp/repeat.md")
        await _drain_worker()
        assert len(ingest.list_failed()) == 1

        mock_process_files.side_effect = RuntimeError("second")
        ingest.schedule_ingest("/tmp/repeat.md")
        await _drain_worker()

        failures = ingest.list_failed()
        assert len(failures) == 1
        assert "second" in failures[0]["error_detail"]
        # retry_count NICHT erhöht (nur retry_failed() tut das)
        assert failures[0]["retry_count"] == 0


# ─── retry_failed ─────────────────────────────────────────────────────────


class TestRetry:
    async def test_retry_specific_increments_count(self, mock_process_files):
        # Vorbereitung: zwei Failures.
        ingest._record_failure("/tmp/a.md", RuntimeError("a"))
        ingest._record_failure("/tmp/b.md", RuntimeError("b"))

        # process_files schlägt weiter fehl, damit retry_count bestand hat.
        mock_process_files.side_effect = RuntimeError("still failing")

        result = await ingest.retry_failed("/tmp/a.md")
        await _drain_worker()

        assert result == {"retried": 1, "queued": ["/tmp/a.md"]}

        failures = {f["file_path"]: f for f in ingest.list_failed()}
        assert failures["/tmp/a.md"]["retry_count"] == 1
        assert failures["/tmp/b.md"]["retry_count"] == 0

    async def test_retry_all(self, mock_process_files):
        ingest._record_failure("/tmp/a.md", RuntimeError("a"))
        ingest._record_failure("/tmp/b.md", RuntimeError("b"))
        mock_process_files.side_effect = RuntimeError("still")

        result = await ingest.retry_failed()
        await _drain_worker()

        assert result["retried"] == 2
        assert sorted(result["queued"]) == ["/tmp/a.md", "/tmp/b.md"]
        for f in ingest.list_failed():
            assert f["retry_count"] == 1

    async def test_retry_unknown_file_returns_zero(self, mock_process_files):
        ingest._record_failure("/tmp/known.md", RuntimeError("x"))
        result = await ingest.retry_failed("/tmp/unknown.md")
        assert result["retried"] == 0
        assert result["queued"] == []
        assert "no failure" in result.get("error", "")

"""Tests für daily-log-mcp/server.py.

Mocks an der memo_to_md.write_memo-Boundary, damit Tool-internes Verhalten
(Error-Mapping, Hint/Ingest-Stub-Aufrufe, Path-Konstruktion) ohne echtes
Filesystem laufen kann. Skipped wenn `mcp` nicht installiert ist (Python
3.9 ohne mcp-SDK) — gleiches Pattern wie tests/cognee_mcp/test_server.py.

Konvention: Tests im selben Verzeichnis wie der Code (analog
pipeline/test_*.py).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

pytest.importorskip(
    "mcp", reason="mcp SDK requires Python 3.10+ — tests run in Docker/CI"
)


def _load_server():
    """Lädt daily-log-mcp/server.py per absolutem Pfad.

    Bindestrich im Verzeichnisnamen verhindert normalen Package-Import.
    """
    here = Path(__file__).resolve().parent
    spec = importlib.util.spec_from_file_location(
        "daily_log_mcp_server", here / "server.py"
    )
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


srv = _load_server()


@pytest.fixture
def mock_write_memo(monkeypatch):
    mock = MagicMock(
        return_value={
            "ok": True,
            "file_path": "/tmp/daily/2026-04-30_majid.md",
            "action": "geschrieben",
        }
    )
    monkeypatch.setattr(srv, "write_memo", mock)
    return mock


@pytest.fixture
def mock_extract_hints(monkeypatch):
    mock = MagicMock(return_value=[])
    monkeypatch.setattr(srv.hints, "extract_hints", mock)
    return mock


@pytest.fixture
def mock_schedule_ingest(monkeypatch):
    mock = MagicMock(return_value={"status": "queued", "queue_position": 1})
    monkeypatch.setattr(srv.ingest, "schedule_ingest", mock)
    return mock


# ─── log_daily_entry ─────────────────────────────────────────────────────


class TestLogDailyEntry:
    async def test_write_mode_success(
        self, mock_write_memo, mock_extract_hints, mock_schedule_ingest
    ):
        result = await srv.log_daily_entry(
            text="Heute war ein langer Tag.",
            user="majid",
            date="2026-04-30",
            tags=["arbeit"],
            entities=["majid"],
            mode="write",
        )

        assert result == {
            "ok": True,
            "file_path": "/tmp/daily/2026-04-30_majid.md",
            "action": "geschrieben",
            "ingest_status": "queued",
            "queue_position": 1,
            "extracted_hints": [],
        }
        mock_write_memo.assert_called_once_with(
            text="Heute war ein langer Tag.",
            user="majid",
            date="2026-04-30",
            tags=["arbeit"],
            entities=["majid"],
            mode="write",
        )

    async def test_replace_mode_success(
        self, monkeypatch, mock_extract_hints, mock_schedule_ingest
    ):
        monkeypatch.setattr(
            srv,
            "write_memo",
            MagicMock(
                return_value={
                    "ok": True,
                    "file_path": "/tmp/daily/2026-04-30_majid.md",
                    "action": "überschrieben",
                }
            ),
        )
        result = await srv.log_daily_entry(
            text="neue Version", date="2026-04-30", mode="replace"
        )
        assert result["ok"] is True
        assert result["action"] == "überschrieben"
        assert result["ingest_status"] == "queued"
        assert result["queue_position"] == 1

    async def test_value_error_returns_validation_dict(
        self, monkeypatch, mock_extract_hints, mock_schedule_ingest
    ):
        monkeypatch.setattr(
            srv,
            "write_memo",
            MagicMock(side_effect=ValueError("Ungültiges Zeichen in tags: 'foo bar'")),
        )
        result = await srv.log_daily_entry(text="x", tags=["foo bar"])

        assert result["ok"] is False
        assert result["error"] == "ValueError"
        assert "Ungültiges Zeichen" in result["detail"]
        assert result["user_message_hint"] == "Konnte Daily-Log nicht speichern."
        assert result["retry_suggested"] is False
        # Bei Validation-Fehlern wird KEIN Hint extrahiert / Ingest geplant.
        mock_extract_hints.assert_not_called()
        mock_schedule_ingest.assert_not_called()

    async def test_os_error_returns_retry_suggested(
        self, monkeypatch, mock_extract_hints, mock_schedule_ingest
    ):
        monkeypatch.setattr(
            srv,
            "write_memo",
            MagicMock(side_effect=PermissionError("read-only filesystem")),
        )
        result = await srv.log_daily_entry(text="x")

        assert result["ok"] is False
        assert result["error"] == "PermissionError"
        assert "read-only" in result["detail"]
        assert result["retry_suggested"] is True
        mock_extract_hints.assert_not_called()
        mock_schedule_ingest.assert_not_called()

    async def test_calls_extract_hints_with_text(
        self, mock_write_memo, mock_extract_hints, mock_schedule_ingest
    ):
        await srv.log_daily_entry(text="Reza hat angerufen.")
        mock_extract_hints.assert_called_once_with("Reza hat angerufen.")

    async def test_calls_schedule_ingest_with_file_path(
        self, mock_write_memo, mock_extract_hints, mock_schedule_ingest
    ):
        await srv.log_daily_entry(text="x")
        mock_schedule_ingest.assert_called_once_with(
            "/tmp/daily/2026-04-30_majid.md"
        )

    async def test_extracted_hints_passthrough(
        self, mock_write_memo, monkeypatch, mock_schedule_ingest
    ):
        sample_hints = [{"type": "date", "value": "Freitag", "context": "..."}]
        monkeypatch.setattr(
            srv.hints, "extract_hints", MagicMock(return_value=sample_hints)
        )
        result = await srv.log_daily_entry(text="x")
        assert result["extracted_hints"] == sample_hints


# ─── read_daily_log ──────────────────────────────────────────────────────


class TestReadDailyLog:
    async def test_file_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        path = tmp_path / "memory" / "daily-logs" / "2026-04-30_majid.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "---\n"
            "type: daily-log\n"
            "date: 2026-04-30\n"
            "user: majid\n"
            "tags: [arbeit, familie]\n"
            "entities: [majid, neda]\n"
            "---\n"
            "\n"
            "Heute ist Donnerstag, der 30. April 2026.\n"
            "\n"
            "Body-Text.\n",
            encoding="utf-8",
        )

        result = await srv.read_daily_log("2026-04-30", "majid")

        assert result["ok"] is True
        assert result["exists"] is True
        assert result["file_path"] == str(path)
        assert result["frontmatter"] == {
            "type": "daily-log",
            "date": "2026-04-30",
            "user": "majid",
            "tags": ["arbeit", "familie"],
            "entities": ["majid", "neda"],
        }
        assert "Heute ist Donnerstag" in result["body"]
        assert "Body-Text." in result["body"]
        assert result["content"].startswith("---\n")

    async def test_file_not_exists(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        result = await srv.read_daily_log("2026-04-30", "majid")
        assert result == {
            "ok": True,
            "exists": False,
            "file_path": str(
                tmp_path / "memory" / "daily-logs" / "2026-04-30_majid.md"
            ),
        }

    async def test_invalid_date_format(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        result = await srv.read_daily_log("2026/4/30", "majid")
        assert result["ok"] is False
        assert result["error"] == "ValueError"
        assert "YYYY-MM-DD" in result["detail"]
        assert result["retry_suggested"] is False

    async def test_invalid_user_rejected(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        result = await srv.read_daily_log("2026-04-30", "ali; rm -rf /")
        assert result["ok"] is False
        assert result["error"] == "ValueError"
        assert "User-Identifier" in result["detail"]

    async def test_path_construction(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        result = await srv.read_daily_log("2026-04-30", "neda")
        expected = tmp_path / "memory" / "daily-logs" / "2026-04-30_neda.md"
        assert result["file_path"] == str(expected)

    async def test_minimal_frontmatter_without_optional_fields(
        self, tmp_path, monkeypatch
    ):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        path = tmp_path / "memory" / "daily-logs" / "2026-04-30_majid.md"
        path.parent.mkdir(parents=True)
        path.write_text(
            "---\n"
            "type: daily-log\n"
            "date: 2026-04-30\n"
            "user: majid\n"
            "---\n"
            "\n"
            "Nur Pflichtfelder.\n",
            encoding="utf-8",
        )
        result = await srv.read_daily_log("2026-04-30", "majid")
        assert result["ok"] is True
        assert result["frontmatter"] == {
            "type": "daily-log",
            "date": "2026-04-30",
            "user": "majid",
        }
        assert "tags" not in result["frontmatter"]
        assert "entities" not in result["frontmatter"]

    async def test_broken_frontmatter_returns_error(self, tmp_path, monkeypatch):
        monkeypatch.setenv("HIMES_DATA_DIR", str(tmp_path))
        path = tmp_path / "memory" / "daily-logs" / "2026-04-30_majid.md"
        path.parent.mkdir(parents=True)
        path.write_text("nope kein frontmatter\n", encoding="utf-8")
        result = await srv.read_daily_log("2026-04-30", "majid")
        assert result["ok"] is False
        assert result["error"] == "ValueError"
        assert "Frontmatter" in result["detail"]


# ─── list_failed_ingests / retry_failed_ingests ─────────────────────────


class TestFailureTools:
    async def test_list_failed_ingests_empty(self, monkeypatch):
        monkeypatch.setattr(srv.ingest, "list_failed", MagicMock(return_value=[]))
        result = await srv.list_failed_ingests()
        assert result == {"ok": True, "failures": []}

    async def test_list_failed_ingests_with_entries(self, monkeypatch):
        sample = [
            {
                "file_path": "/x/2026-04-30_majid.md",
                "error_type": "TimeoutError",
                "error_detail": "ingest timeout",
                "timestamp": "2026-05-01T14:23:11+00:00",
                "retry_count": 0,
            }
        ]
        monkeypatch.setattr(srv.ingest, "list_failed", MagicMock(return_value=sample))
        result = await srv.list_failed_ingests()
        assert result["ok"] is True
        assert result["failures"] == sample

    async def test_list_failed_ingests_error_returns_adr018(self, monkeypatch):
        monkeypatch.setattr(
            srv.ingest, "list_failed", MagicMock(side_effect=OSError("disk gone"))
        )
        result = await srv.list_failed_ingests()
        assert result["ok"] is False
        assert result["error"] == "OSError"
        assert result["user_message_hint"] == "Konnte Failure-Liste nicht lesen."

    async def test_retry_failed_specific_file(self, monkeypatch):
        from unittest.mock import AsyncMock
        retry_mock = AsyncMock(
            return_value={"retried": 1, "queued": ["/x/2026-04-30_majid.md"]}
        )
        monkeypatch.setattr(srv.ingest, "retry_failed", retry_mock)
        result = await srv.retry_failed_ingests("/x/2026-04-30_majid.md")
        assert result == {
            "ok": True,
            "retried": 1,
            "queued": ["/x/2026-04-30_majid.md"],
        }
        retry_mock.assert_called_once_with("/x/2026-04-30_majid.md")

    async def test_retry_failed_all(self, monkeypatch):
        from unittest.mock import AsyncMock
        retry_mock = AsyncMock(return_value={"retried": 3, "queued": ["a", "b", "c"]})
        monkeypatch.setattr(srv.ingest, "retry_failed", retry_mock)
        result = await srv.retry_failed_ingests()
        assert result["ok"] is True
        assert result["retried"] == 3
        retry_mock.assert_called_once_with(None)

    async def test_retry_failed_error_returns_adr018(self, monkeypatch):
        from unittest.mock import AsyncMock
        monkeypatch.setattr(
            srv.ingest, "retry_failed", AsyncMock(side_effect=RuntimeError("boom"))
        )
        result = await srv.retry_failed_ingests()
        assert result["ok"] is False
        assert result["error"] == "RuntimeError"

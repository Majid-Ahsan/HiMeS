"""Tests for cognee-setup/mcp/server.py — read-only Cognee MCP search.

Mocks at the cognee.search module boundary (not at tool level), so the
tool-internal logic (top_k cap, ADR-018 error format, kwarg names) is
covered without needing a real Cognee install.

Skipped when the mcp SDK isn't available (Python 3.9 / no mcp install) —
mirrors the pattern in tests/test_server_tools.py. These run in Docker/CI.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

pytest.importorskip(
    "mcp", reason="mcp SDK requires Python 3.10+ — tests run in Docker/CI"
)


def _load_server_with_cognee_stub():
    """Load cognee-setup/mcp/server.py with a stubbed `cognee` module.

    The hyphen in `cognee-setup` makes the directory un-importable as a
    Python package, so we use importlib to load server.py by absolute path.

    Stubbing `cognee` in sys.modules before exec lets the bare `import cognee`
    at the top of server.py succeed without a real Cognee install. The stub
    exposes `search` as an AsyncMock that tests configure per-test.
    """
    cognee_stub = MagicMock()
    cognee_stub.search = AsyncMock()
    sys.modules["cognee"] = cognee_stub

    repo_root = Path(__file__).resolve().parent.parent.parent
    server_path = repo_root / "cognee-setup" / "mcp" / "server.py"
    spec = importlib.util.spec_from_file_location("cognee_mcp_server", server_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


srv = _load_server_with_cognee_stub()


@pytest.fixture(autouse=True)
def _reset_cognee_mock():
    """Reset cognee.search call history + return_value/side_effect between tests."""
    srv.cognee.search.reset_mock(return_value=True, side_effect=True)
    yield


# ─── cognee_search tool ──────────────────────────────────────────────


class TestCogneeSearch:
    async def test_cognee_search_happy_path(self):
        srv.cognee.search.return_value = ["result1", "result2"]

        result = await srv.cognee_search("test query")

        assert result["ok"] is True
        assert result["results"] == ["result1", "result2"]
        srv.cognee.search.assert_called_once_with(
            query_text="test query", top_k=5
        )

    async def test_cognee_search_top_k_caps_results(self):
        srv.cognee.search.return_value = list(range(10))

        result = await srv.cognee_search("q", top_k=3)

        assert result["ok"] is True
        assert len(result["results"]) == 3
        assert result["results"] == [0, 1, 2]

    async def test_cognee_search_passes_top_k_to_cognee(self):
        srv.cognee.search.return_value = []

        await srv.cognee_search("q", top_k=7)

        kwargs = srv.cognee.search.call_args.kwargs
        assert kwargs["top_k"] == 7

    async def test_cognee_search_handles_exception(self):
        srv.cognee.search.side_effect = RuntimeError("boom")

        result = await srv.cognee_search("q")

        assert result["ok"] is False
        assert result["error"] == "RuntimeError"
        assert result["detail"] == "boom"
        assert (
            result["user_message_hint"]
            == "Konnte Gedächtnis gerade nicht abfragen."
        )
        assert result["retry_suggested"] is True

    async def test_cognee_search_does_not_pass_query_type(self):
        # Regression test for ADR-044 #3: SearchType import path is unstable
        # across Cognee versions, so we never pass query_type=.
        srv.cognee.search.return_value = []

        await srv.cognee_search("q")

        kwargs = srv.cognee.search.call_args.kwargs
        assert "query_type" not in kwargs

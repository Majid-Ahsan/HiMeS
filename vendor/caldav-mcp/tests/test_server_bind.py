"""Tests for run_server SSE bind configuration.

The default bind is 127.0.0.1 (loopback only) — exposing the SSE
transport on a public interface is opt-in via --host 0.0.0.0. These
tests pin both the safe default and the override path so the bind
behaviour can't silently regress.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_caldav.server import run_server


@pytest.mark.asyncio
async def test_run_server_sse_default_host_is_loopback():
    """Calling run_server without an explicit host binds to 127.0.0.1."""
    import uvicorn

    fake_server = MagicMock()
    fake_server.serve = AsyncMock(return_value=None)

    with patch.object(uvicorn, "Config") as mock_config, patch.object(
        uvicorn, "Server", return_value=fake_server
    ):
        await run_server(transport="sse", port=8001)

    mock_config.assert_called_once()
    kwargs = mock_config.call_args.kwargs
    assert kwargs.get("host") == "127.0.0.1"
    assert kwargs.get("port") == 8001


@pytest.mark.asyncio
async def test_run_server_sse_explicit_host_passed_through():
    """Explicit host overrides the default — 0.0.0.0 still possible if requested."""
    import uvicorn

    fake_server = MagicMock()
    fake_server.serve = AsyncMock(return_value=None)

    with patch.object(uvicorn, "Config") as mock_config, patch.object(
        uvicorn, "Server", return_value=fake_server
    ):
        await run_server(transport="sse", host="0.0.0.0", port=9999)

    kwargs = mock_config.call_args.kwargs
    assert kwargs.get("host") == "0.0.0.0"
    assert kwargs.get("port") == 9999

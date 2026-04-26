"""Pytest configuration for MCP CalDAV tests."""

from contextlib import contextmanager
from unittest.mock import MagicMock

import pytest

from mcp_caldav.client import CalDAVClient
from mcp_caldav.server import AppContext


@pytest.fixture
def mock_caldav_client():
    """Create a mock CalDAVClient with pre-configured return values."""
    mock_client = MagicMock(spec=CalDAVClient)
    mock_client.url = "https://caldav.yandex.ru/"
    mock_client.username = "test@example.com"

    # Configure common methods
    mock_client.list_calendars.return_value = [
        {
            "index": 0,
            "name": "Test Calendar",
            "url": "https://caldav.yandex.ru/calendars/test",
        }
    ]

    mock_client.create_event.return_value = {
        "success": True,
        "uid": "test-uid-123",
        "title": "Test Event",
        "start_time": "2025-01-20T14:00:00",
        "end_time": "2025-01-20T15:00:00",
        "calendar": "Test Calendar",
    }

    mock_client.get_events.return_value = [
        {
            "title": "Test Event",
            "start": "2025-01-20T14:00:00",
            "end": "2025-01-20T15:00:00",
            "description": "Test description",
            "location": "Test location",
            "all_day": False,
        }
    ]

    mock_client.get_today_events.return_value = []
    mock_client.get_week_events.return_value = []

    return mock_client


@pytest.fixture
def app_context(mock_caldav_client):
    """Create an AppContext with mock client."""
    return AppContext(client=mock_caldav_client)


@contextmanager
def mock_request_context(app_context):
    """Context manager to set the request_ctx context variable."""
    from mcp.server.lowlevel.server import request_ctx
    from mcp.shared.context import RequestContext
    from mcp.shared.session import BaseSession

    mock_session = MagicMock(spec=BaseSession)

    context = RequestContext(
        request_id="test-request-id",
        meta=None,
        session=mock_session,
        lifespan_context=app_context,
    )

    token = request_ctx.set(context)
    try:
        yield
    finally:
        request_ctx.reset(token)

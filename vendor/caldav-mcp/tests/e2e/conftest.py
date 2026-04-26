"""Pytest configuration for e2e tests with real CalDAV server."""

import os
from collections.abc import Generator

import pytest

from mcp_caldav.client import CalDAVClient


@pytest.fixture(scope="module")
def real_caldav_client() -> Generator[CalDAVClient, None, None]:
    """
    Create a real CalDAV client for e2e tests.

    Requires environment variables:
    - CALDAV_URL
    - CALDAV_USERNAME
    - CALDAV_PASSWORD

    If not set, tests will be skipped.
    """
    url = os.getenv("CALDAV_URL")
    username = os.getenv("CALDAV_USERNAME")
    password = os.getenv("CALDAV_PASSWORD")

    if not all([url, username, password]):
        pytest.skip(
            "E2E tests require CALDAV_URL, CALDAV_USERNAME, and CALDAV_PASSWORD "
            "environment variables to be set"
        )

    client = CalDAVClient(
        url=url,
        username=username,
        password=password,
    )
    client.connect()

    yield client

    # Cleanup if needed
    # Note: Individual tests should clean up their own created events


@pytest.fixture(scope="function")
def test_calendar_index(real_caldav_client: CalDAVClient) -> int:
    """Get the first available calendar index for testing."""
    calendars = real_caldav_client.list_calendars()
    if not calendars:
        pytest.skip("No calendars available for testing")
    return 0  # Use first calendar


@pytest.fixture(scope="function")
def cleanup_events(
    real_caldav_client: CalDAVClient, test_calendar_index: int
) -> Generator[list[str], None, None]:
    """
    Fixture to track and clean up events created during tests.

    Usage:
        def test_something(cleanup_events):
            result = client.create_event(...)
            cleanup_events.append(result['uid'])
    """
    created_uids: list[str] = []

    yield created_uids

    # Cleanup: delete all created events
    for uid in created_uids:
        try:
            # Check if event still exists before deleting
            event = real_caldav_client.get_event_by_uid(
                uid=uid, calendar_index=test_calendar_index
            )
            if event:
                real_caldav_client.delete_event(
                    uid=uid, calendar_index=test_calendar_index
                )
        except Exception:
            # Ignore errors during cleanup (event might already be deleted)
            pass

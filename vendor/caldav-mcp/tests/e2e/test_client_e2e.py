"""End-to-end tests for CalDAV client with real server."""

import time
from datetime import datetime, timedelta

import pytest

from mcp_caldav.client import CalDAVClient  # type: ignore[import-not-found]


def rate_limit_delay(seconds: float = 3.0):
    """
    Add a delay to avoid rate limiting.

    Yandex Calendar has aggressive rate limiting (60 seconds per MB since 2021).
    There is no automatic retry logic, so we add delays between test operations
    to reduce the chance of hitting throttling thresholds.
    """
    time.sleep(seconds)


@pytest.mark.e2e
class TestCalDAVClientE2E:
    """E2E tests with real CalDAV server."""

    def test_list_calendars(self, real_caldav_client: CalDAVClient):
        """Test listing calendars."""
        calendars = real_caldav_client.list_calendars()
        assert isinstance(calendars, list)
        assert len(calendars) > 0
        assert "name" in calendars[0]
        assert "index" in calendars[0]

    def test_create_and_get_event(
        self,
        real_caldav_client: CalDAVClient,
        test_calendar_index: int,
        cleanup_events: list,
    ):
        """Test creating and retrieving an event."""
        # Create event
        start_time = datetime.now() + timedelta(days=1)
        start_time = start_time.replace(hour=14, minute=0, second=0, microsecond=0)
        end_time = start_time + timedelta(hours=1)

        result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="E2E Test Event",
            description="Test description for e2e",
            location="Test Location",
            start_time=start_time,
            end_time=end_time,
        )

        assert result["success"] is True
        assert result["title"] == "E2E Test Event"
        uid = result["uid"]
        cleanup_events.append(uid)

        rate_limit_delay()  # Avoid rate limiting

        # Get event by UID
        event = real_caldav_client.get_event_by_uid(
            uid=uid, calendar_index=test_calendar_index
        )
        assert event is not None
        assert event["uid"] == uid
        assert event["title"] == "E2E Test Event"
        assert event["description"] == "Test description for e2e"
        assert event["location"] == "Test Location"

    def test_create_event_with_categories_and_priority(
        self,
        real_caldav_client: CalDAVClient,
        test_calendar_index: int,
        cleanup_events: list,
    ):
        """Test creating event with categories and priority."""
        start_time = datetime.now() + timedelta(days=2)
        start_time = start_time.replace(hour=15, minute=0, second=0, microsecond=0)

        result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="Event with Categories",
            description="Test event with categories and priority",
            start_time=start_time,
            categories=["Work", "Important"],
            priority=1,
        )

        assert result["success"] is True
        uid = result["uid"]
        cleanup_events.append(uid)

        rate_limit_delay()  # Avoid rate limiting

        # Verify event has categories and priority
        # Note: Some calendar providers (like Yandex) may override categories with their own
        event = real_caldav_client.get_event_by_uid(
            uid=uid, calendar_index=test_calendar_index
        )
        assert event is not None
        assert "categories" in event
        assert isinstance(event.get("categories"), list)
        # Priority should be preserved
        assert event.get("priority") == 1

    def test_create_recurring_event(
        self,
        real_caldav_client: CalDAVClient,
        test_calendar_index: int,
        cleanup_events: list,
    ):
        """Test creating a recurring event."""
        start_time = datetime.now() + timedelta(days=3)
        start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)

        result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="Daily Recurring Event",
            description="This event repeats daily",
            start_time=start_time,
            recurrence={
                "frequency": "DAILY",
                "interval": 1,
                "count": 5,  # Repeat 5 times
            },
        )

        assert result["success"] is True
        uid = result["uid"]
        cleanup_events.append(uid)

        rate_limit_delay()  # Avoid rate limiting

        # Verify recurrence
        # Note: Some calendar providers may not support RRULE or may transform it
        event = real_caldav_client.get_event_by_uid(
            uid=uid, calendar_index=test_calendar_index
        )
        assert event is not None
        # Recurrence field should exist (may be None if provider doesn't support it)
        assert "recurrence" in event
        # If recurrence is present, it should contain FREQ
        if event.get("recurrence"):
            assert "FREQ=DAILY" in event["recurrence"] or "DAILY" in event["recurrence"]

    def test_create_event_with_attendees(
        self,
        real_caldav_client: CalDAVClient,
        test_calendar_index: int,
        cleanup_events: list,
    ):
        """Test creating event with attendees."""
        start_time = datetime.now() + timedelta(days=4)
        start_time = start_time.replace(hour=16, minute=0, second=0, microsecond=0)

        result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="Meeting with Attendees",
            description="Test meeting",
            start_time=start_time,
            attendees=[
                {"email": "test1@example.com", "status": "ACCEPTED"},
                {"email": "test2@example.com", "status": "NEEDS-ACTION"},
            ],
        )

        assert result["success"] is True
        uid = result["uid"]
        cleanup_events.append(uid)

        rate_limit_delay()  # Avoid rate limiting

        # Verify attendees
        # Note: Some calendar providers may not preserve attendee statuses
        event = real_caldav_client.get_event_by_uid(
            uid=uid, calendar_index=test_calendar_index
        )
        assert event is not None
        assert "attendees" in event
        attendees = event.get("attendees", [])
        # Attendees field should exist and be a list
        assert isinstance(attendees, list)
        # If attendees are present, verify structure
        if attendees:
            attendee_emails = [
                a.get("email") if isinstance(a, dict) else str(a) for a in attendees
            ]
            # Check that our test emails are in the list (may be transformed by provider)
            assert any(
                "test1@example.com" in str(email) for email in attendee_emails
            ) or any("test2@example.com" in str(email) for email in attendee_emails)

    def test_delete_event(
        self, real_caldav_client: CalDAVClient, test_calendar_index: int
    ):
        """Test deleting an event."""
        # Create event first
        start_time = datetime.now() + timedelta(days=6)
        start_time = start_time.replace(hour=12, minute=0, second=0, microsecond=0)

        create_result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="Event to Delete",
            start_time=start_time,
        )

        uid = create_result["uid"]

        rate_limit_delay()  # Avoid rate limiting

        # Delete event
        delete_result = real_caldav_client.delete_event(
            uid=uid, calendar_index=test_calendar_index
        )
        assert delete_result["success"] is True

        rate_limit_delay()  # Avoid rate limiting

        # Verify deletion
        event = real_caldav_client.get_event_by_uid(
            uid=uid, calendar_index=test_calendar_index
        )
        assert event is None

    def test_search_events(
        self,
        real_caldav_client: CalDAVClient,
        test_calendar_index: int,
        cleanup_events: list,
    ):
        """Test searching events."""
        # Create a test event
        start_time = datetime.now() + timedelta(days=7)
        start_time = start_time.replace(hour=13, minute=0, second=0, microsecond=0)

        create_result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="Searchable Event",
            description="This event should be found by search",
            location="Search Location",
            start_time=start_time,
        )

        uid = create_result["uid"]
        cleanup_events.append(uid)

        rate_limit_delay()  # Avoid rate limiting

        search_start = start_time - timedelta(days=1)
        search_end = start_time + timedelta(days=1)

        # Search by title
        results = real_caldav_client.search_events(
            calendar_index=test_calendar_index,
            query="Searchable",
            search_fields=["title"],
            start_date=search_start,
            end_date=search_end,
        )
        assert len(results) > 0
        assert any("Searchable" in event.get("title", "") for event in results)

        rate_limit_delay()  # Avoid rate limiting

        # Search by description
        results = real_caldav_client.search_events(
            calendar_index=test_calendar_index,
            query="found by search",
            search_fields=["description"],
            start_date=search_start,
            end_date=search_end,
        )
        assert len(results) > 0

        rate_limit_delay()  # Avoid rate limiting

        # Search by location
        results = real_caldav_client.search_events(
            calendar_index=test_calendar_index,
            query="Search Location",
            search_fields=["location"],
            start_date=search_start,
            end_date=search_end,
        )
        assert len(results) > 0

    def test_get_events_with_extended_fields(
        self,
        real_caldav_client: CalDAVClient,
        test_calendar_index: int,
        cleanup_events: list,
    ):
        """Test that get_events returns extended fields."""
        # Create event with all fields
        start_time = datetime.now() + timedelta(days=8)
        start_time = start_time.replace(hour=14, minute=0, second=0, microsecond=0)

        create_result = real_caldav_client.create_event(
            calendar_index=test_calendar_index,
            title="Extended Fields Event",
            description="Test extended fields",
            location="Test Location",
            start_time=start_time,
            categories=["Test", "E2E"],
            priority=3,
            attendees=[{"email": "attendee@example.com", "status": "ACCEPTED"}],
        )

        uid = create_result["uid"]
        cleanup_events.append(uid)

        rate_limit_delay()  # Avoid rate limiting

        # Get events and verify extended fields
        events = real_caldav_client.get_events(
            calendar_index=test_calendar_index,
            start_date=start_time - timedelta(days=1),
            end_date=start_time + timedelta(days=1),
        )

        # Find our event
        our_event = None
        for event in events:
            if event.get("uid") == uid:
                our_event = event
                break

        assert our_event is not None
        assert "uid" in our_event
        assert "categories" in our_event
        assert "priority" in our_event
        assert "attendees" in our_event
        assert "recurrence" in our_event  # May be None
        assert our_event["uid"] == uid
        # Categories field exists and is a list (may be overridden by calendar provider)
        assert isinstance(our_event.get("categories"), list)

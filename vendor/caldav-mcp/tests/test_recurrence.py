"""Unit tests for recurrence-exception handling in get_events (Phase 1.5.29).

Validates the surgical fix: calendar.search(..., event=True, expand=True)
replaces calendar.date_search(...). Behaviour:
- expand=True makes iCloud (or python-caldav fallback) return each
  occurrence as its own VEVENT with overrides applied and EXDATE dropped.
- The parsing loop in get_events works unchanged — each Event object
  now carries exactly one VEVENT (the fully-resolved instance).

Bug context: 2026-04-18 Musikschule-Chat. Apple's iCal payload for a
modified instance of a weekly series:
  Master VEVENT: RRULE:FREQ=WEEKLY, DTSTART:20251010T170000 (Fri 17:00)
                 EXDATE list including 20260417T170000
  Override VEVENT: UID=same, RECURRENCE-ID:20260417T170000 (original slot),
                   DTSTART:20260419T110000 (moved to Sunday 11:00)

Before fix: date_search returned the calendar-object-resource with all
VEVENTs in one blob; event.icalendar_component yielded only the first
VEVENT, losing the override. After fix: expand=True returns the moved
Sunday instance as its own resolved VEVENT.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

from mcp_caldav.client import CalDAVClient


def _mock_vevent(
    summary: str,
    start: datetime,
    end: datetime,
    uid: str,
    recurrence_id: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock icalendar-like component for an expanded VEVENT.

    Mirrors the fields the production code extracts from ical_component.get(...).
    """
    dtstart = MagicMock()
    dtstart.dt = start
    dtend = MagicMock()
    dtend.dt = end
    summary_val = MagicMock()
    summary_val.__str__ = lambda self: summary  # type: ignore[misc]

    comp = MagicMock()

    def get(key, default=None):
        if key == "SUMMARY":
            return summary_val
        if key == "DTSTART":
            return dtstart
        if key == "DTEND":
            return dtend
        if key == "UID":
            return uid
        if key == "RECURRENCE-ID":
            if recurrence_id is None:
                return None
            ri = MagicMock()
            ri.dt = recurrence_id
            return ri
        if key == "RRULE":
            return None  # expanded instances have no RRULE
        return default

    comp.get.side_effect = get
    return comp


def _event_wrapper(ical_component: MagicMock) -> MagicMock:
    ev = MagicMock()
    ev.icalendar_component = ical_component
    return ev


@patch("mcp_caldav.client.caldav.DAVClient")
def test_get_events_uses_expand_true(mock_dav_client):
    """Assert the post-fix code calls search with expand=True, event=True."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = []
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    start = datetime(2026, 4, 13)
    end = datetime(2026, 4, 20)
    client.get_events(calendar_index=0, start_date=start, end_date=end)

    mock_calendar.search.assert_called_once()
    kwargs = mock_calendar.search.call_args.kwargs
    assert kwargs.get("event") is True
    assert kwargs.get("expand") is True
    # Phase 1.5.29b: server window widened by +/-14 days to catch moved
    # recurrence overrides whose RECURRENCE-ID lies outside the user range.
    assert kwargs.get("start") == start - timedelta(days=14)
    assert kwargs.get("end") == end + timedelta(days=14)


@patch("mcp_caldav.client.caldav.DAVClient")
def test_moved_instance_visible_on_narrow_new_date_query(mock_dav_client):
    """Phase 1.5.29b regression: Musikschule moved Fri 17.04 -> Sun 19.04.

    Narrow Sunday-only user query must still see the event even though its
    RECURRENCE-ID (17.04) lies outside [19.04, 20.04). iCloud matches
    overrides against the time-range by RECURRENCE-ID, not DTSTART — so
    the widened server window catches it and the client-side DTSTART
    filter keeps it.
    """
    musik_uid = "4D45A1B2-FEDB-4378-941F-571FB8FBC401"
    moved = _mock_vevent(
        summary="Musikschule",
        start=datetime(2026, 4, 19, 11, 0),
        end=datetime(2026, 4, 19, 11, 30),
        uid=musik_uid,
        recurrence_id=datetime(2026, 4, 17, 17, 0),
    )

    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    # Simulate iCloud: widened server window includes 17.04, so override returned.
    mock_calendar.search.return_value = [_event_wrapper(moved)]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    # User asks for Sunday only — narrow 24h window.
    events = client.get_events(
        calendar_index=0,
        start_date=datetime(2026, 4, 19, 0, 0, 0),
        end_date=datetime(2026, 4, 20, 0, 0, 0),
    )

    assert len(events) == 1
    assert events[0]["start"] == "2026-04-19T11:00:00"
    # And internally the server query was widened to include 17.04 (14d before)
    kwargs = mock_calendar.search.call_args.kwargs
    assert kwargs["start"] == datetime(2026, 4, 5, 0, 0, 0)
    assert kwargs["end"] == datetime(2026, 5, 4, 0, 0, 0)


@patch("mcp_caldav.client.caldav.DAVClient")
def test_widened_query_results_are_filtered_to_user_range(mock_dav_client):
    """Widened server window returns events outside the user's range;
    those MUST be dropped client-side."""
    in_range = _mock_vevent(
        summary="In range",
        start=datetime(2026, 4, 19, 10, 0),
        end=datetime(2026, 4, 19, 11, 0),
        uid="u-in-range",
    )
    before_window = _mock_vevent(
        summary="9 days before",
        start=datetime(2026, 4, 10, 10, 0),
        end=datetime(2026, 4, 10, 11, 0),
        uid="u-before",
    )
    after_window = _mock_vevent(
        summary="6 days after",
        start=datetime(2026, 4, 25, 10, 0),
        end=datetime(2026, 4, 25, 11, 0),
        uid="u-after",
    )

    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = [
        _event_wrapper(before_window),
        _event_wrapper(in_range),
        _event_wrapper(after_window),
    ]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    # User queries just Sunday 19.04 — both out-of-range events must be dropped.
    events = client.get_events(
        calendar_index=0,
        start_date=datetime(2026, 4, 19, 0, 0, 0),
        end_date=datetime(2026, 4, 20, 0, 0, 0),
    )

    assert len(events) == 1
    assert events[0]["title"] == "In range"
    assert events[0]["uid"] == "u-in-range"


@patch("mcp_caldav.client.caldav.DAVClient")
def test_shifted_instance_visible_on_new_date(mock_dav_client):
    """Musikschule moved from Fri 17:00 to Sun 11:00 — Sunday query sees it."""
    musik_uid = "4D45A1B2-FEDB-4378-941F-571FB8FBC401"
    # Server-expanded: the moved instance is its own clean VEVENT.
    moved = _mock_vevent(
        summary="Musikschule",
        start=datetime(2026, 4, 19, 11, 0),  # Sunday 11:00
        end=datetime(2026, 4, 19, 11, 30),
        uid=musik_uid,
        recurrence_id=datetime(2026, 4, 17, 17, 0),  # original Fri 17:00
    )

    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = [_event_wrapper(moved)]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    # Query for Sunday 2026-04-19 only
    sunday_start = datetime(2026, 4, 19, 0, 0, 0)
    sunday_end = datetime(2026, 4, 20, 0, 0, 0)
    events = client.get_events(
        calendar_index=0, start_date=sunday_start, end_date=sunday_end
    )

    assert len(events) == 1
    assert events[0]["title"] == "Musikschule"
    assert events[0]["start"] == "2026-04-19T11:00:00"
    assert events[0]["end"] == "2026-04-19T11:30:00"
    assert events[0]["uid"] == musik_uid


@patch("mcp_caldav.client.caldav.DAVClient")
def test_original_slot_empty_after_move(mock_dav_client):
    """Friday 2026-04-17 query returns nothing — instance moved away."""
    # Server-expanded: for Friday 17.04, no Musikschule exists (moved + EXDATE'd).
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = []  # no events at original slot
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    events = client.get_events(
        calendar_index=0,
        start_date=datetime(2026, 4, 17, 0, 0, 0),
        end_date=datetime(2026, 4, 18, 0, 0, 0),
    )
    assert events == []


@patch("mcp_caldav.client.caldav.DAVClient")
def test_next_week_normal_instance(mock_dav_client):
    """Friday 2026-04-24 (next week, unaffected) has normal Musikschule 17:00."""
    musik_uid = "4D45A1B2-FEDB-4378-941F-571FB8FBC401"
    normal = _mock_vevent(
        summary="Musikschule",
        start=datetime(2026, 4, 24, 17, 0),
        end=datetime(2026, 4, 24, 17, 30),
        uid=musik_uid,
        recurrence_id=datetime(2026, 4, 24, 17, 0),
    )

    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = [_event_wrapper(normal)]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    events = client.get_events(
        calendar_index=0,
        start_date=datetime(2026, 4, 24, 0, 0, 0),
        end_date=datetime(2026, 4, 25, 0, 0, 0),
    )
    assert len(events) == 1
    assert events[0]["start"] == "2026-04-24T17:00:00"


@patch("mcp_caldav.client.caldav.DAVClient")
def test_week_view_has_override_not_original(mock_dav_client):
    """Week 2026-04-13..2026-04-19: Musikschule appears only on Sunday, not Friday."""
    musik_uid = "4D45A1B2-FEDB-4378-941F-571FB8FBC401"
    moved = _mock_vevent(
        summary="Musikschule",
        start=datetime(2026, 4, 19, 11, 0),
        end=datetime(2026, 4, 19, 11, 30),
        uid=musik_uid,
        recurrence_id=datetime(2026, 4, 17, 17, 0),
    )

    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = [_event_wrapper(moved)]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    events = client.get_events(
        calendar_index=0,
        start_date=datetime(2026, 4, 13, 0, 0, 0),
        end_date=datetime(2026, 4, 20, 0, 0, 0),
    )

    assert len(events) == 1
    assert events[0]["start"].startswith("2026-04-19")
    # Nothing on the original 2026-04-17 Friday
    assert not any(e["start"].startswith("2026-04-17") for e in events)


@patch("mcp_caldav.client.caldav.DAVClient")
def test_non_recurring_event_still_works(mock_dav_client):
    """Regression: simple single event (no recurrence) still returns correctly."""
    singleton = _mock_vevent(
        summary="Einmal-Termin",
        start=datetime(2026, 4, 20, 9, 0),
        end=datetime(2026, 4, 20, 10, 0),
        uid="singleton-uid-001",
        recurrence_id=None,  # no RECURRENCE-ID
    )

    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = [_event_wrapper(singleton)]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    events = client.get_events(
        calendar_index=0,
        start_date=datetime(2026, 4, 20, 0, 0, 0),
        end_date=datetime(2026, 4, 21, 0, 0, 0),
    )
    assert len(events) == 1
    assert events[0]["title"] == "Einmal-Termin"


@patch("mcp_caldav.client.caldav.DAVClient")
def test_get_today_events_delegates_to_get_events(mock_dav_client):
    """get_today_events → get_events → search(expand=True). Whole chain."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = []
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()
    client.get_today_events(calendar_index=0)

    mock_calendar.search.assert_called_once()
    assert mock_calendar.search.call_args.kwargs.get("expand") is True


@patch("mcp_caldav.client.caldav.DAVClient")
def test_get_week_events_delegates_to_get_events(mock_dav_client):
    """Week view also uses expand=True."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.search.return_value = []
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()
    client.get_week_events(calendar_index=0)

    mock_calendar.search.assert_called_once()
    assert mock_calendar.search.call_args.kwargs.get("expand") is True

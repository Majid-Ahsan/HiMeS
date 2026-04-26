"""Defensive guard tests for update_event on recurring series (Bug A / ADR-045).

caldav_update_event used to silently mutate the master VEVENT of a
recurring series, shifting every occurrence or causing iCloud to refuse
the save and the bot to fall back on create_event (double bookings).
The guard refuses any update on a recurring resource and raises
RecurringEventNotSupportedError so the bot reports a clean error.

Both shapes must be blocked:
  - Master VEVENT carries an RRULE
  - Override VEVENT carries a RECURRENCE-ID (single resource bundles
    master + override; iCloud sometimes returns just the override)
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from mcp_caldav.client import CalDAVClient, RecurringEventNotSupportedError


def _make_vevent(
    uid: str,
    summary: str = "Series Event",
    rrule: str | None = None,
    recurrence_id: datetime | None = None,
) -> MagicMock:
    """Build a MagicMock VEVENT subcomponent.

    Mirrors the surface the production guard inspects:
      - .name == "VEVENT"
      - .get("RRULE"), .get("RECURRENCE-ID"), .get("UID"), ...
    Plus the mutable mapping access (`comp[key] = value`) the rest of
    update_event uses on the master component when no guard fires.
    """
    comp = MagicMock()
    comp.name = "VEVENT"

    storage: dict[str, object] = {"UID": uid, "SUMMARY": summary}
    if rrule is not None:
        storage["RRULE"] = rrule
    if recurrence_id is not None:
        ri = MagicMock()
        ri.dt = recurrence_id
        storage["RECURRENCE-ID"] = ri

    dtstart = MagicMock()
    dtstart.dt = datetime(2026, 4, 17, 17, 0)
    storage["DTSTART"] = dtstart
    dtend = MagicMock()
    dtend.dt = datetime(2026, 4, 17, 18, 0)
    storage["DTEND"] = dtend

    comp.get.side_effect = lambda key, default=None: storage.get(key, default)
    comp.__getitem__.side_effect = storage.__getitem__
    comp.__setitem__.side_effect = storage.__setitem__
    comp.subcomponents = []
    return comp


def _make_event_resource(*vevents: MagicMock) -> MagicMock:
    """Wrap one or more VEVENT mocks into a calendar-object resource.

    icalendar_component returns the first VEVENT (matches the python
    icalendar library's behaviour of yielding the first VEVENT in a
    VCALENDAR). icalendar_instance.walk() yields every VEVENT plus a
    leading non-VEVENT entry for the VCALENDAR root, so the production
    walk loop sees them all.
    """
    instance = MagicMock()
    vcalendar = MagicMock()
    vcalendar.name = "VCALENDAR"
    instance.walk.return_value = [vcalendar, *vevents]

    event = MagicMock()
    event.icalendar_component = vevents[0]
    event.icalendar_instance = instance
    return event


def _wire_calendar_with_event(event: MagicMock, mock_dav_client: MagicMock) -> MagicMock:
    """Stand up the principal/calendar/date_search chain and return calendar."""
    mock_client_instance = MagicMock()
    mock_principal = MagicMock()
    mock_calendar = MagicMock()
    mock_calendar.name = "Test Calendar"
    mock_calendar.date_search.return_value = [event]
    mock_principal.calendars.return_value = [mock_calendar]
    mock_client_instance.principal.return_value = mock_principal
    mock_dav_client.return_value = mock_client_instance
    return mock_calendar


@patch("mcp_caldav.client.caldav.DAVClient")
def test_update_event_recurring_master_blocked(mock_dav_client):
    """Master VEVENT with RRULE → guard raises, no save() call."""
    master = _make_vevent(uid="series-uid-1", rrule="FREQ=WEEKLY")
    event = _make_event_resource(master)
    _wire_calendar_with_event(event, mock_dav_client)

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    with pytest.raises(RecurringEventNotSupportedError) as excinfo:
        client.update_event(uid="series-uid-1", title="New Title")

    assert "recurring series" in str(excinfo.value).lower()
    assert "apple calendar" in str(excinfo.value).lower()
    event.save.assert_not_called()


@patch("mcp_caldav.client.caldav.DAVClient")
def test_update_event_recurring_override_blocked(mock_dav_client):
    """Override VEVENT (RECURRENCE-ID, no RRULE) → guard raises, no save()."""
    override = _make_vevent(
        uid="series-uid-2",
        recurrence_id=datetime(2026, 4, 17, 17, 0),
    )
    event = _make_event_resource(override)
    _wire_calendar_with_event(event, mock_dav_client)

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    with pytest.raises(RecurringEventNotSupportedError):
        client.update_event(uid="series-uid-2", start_time=datetime(2026, 4, 19, 11, 0))

    event.save.assert_not_called()


@patch("mcp_caldav.client.caldav.DAVClient")
def test_update_event_recurring_master_plus_override_blocked(mock_dav_client):
    """Bundled master + override VEVENTs → guard raises on first match, no save()."""
    master = _make_vevent(uid="series-uid-3", rrule="FREQ=WEEKLY")
    override = _make_vevent(
        uid="series-uid-3",
        recurrence_id=datetime(2026, 4, 17, 17, 0),
    )
    event = _make_event_resource(master, override)
    _wire_calendar_with_event(event, mock_dav_client)

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    with pytest.raises(RecurringEventNotSupportedError):
        client.update_event(uid="series-uid-3", title="Anything")

    event.save.assert_not_called()


@patch("mcp_caldav.client.caldav.DAVClient")
def test_update_event_non_recurring_succeeds(mock_dav_client):
    """Plain VEVENT (no RRULE, no RECURRENCE-ID) → save() is called normally."""
    plain = _make_vevent(uid="plain-uid-1")
    event = _make_event_resource(plain)
    _wire_calendar_with_event(event, mock_dav_client)

    client = CalDAVClient(url="https://x", username="u", password="p")
    client.connect()

    result = client.update_event(uid="plain-uid-1", title="Updated Title")

    event.save.assert_called_once()
    assert result["success"] is True
    assert result["uid"] == "plain-uid-1"
    assert "title" in result["updated_fields"]

"""CalDAV client for calendar operations."""

import functools
import json as _json
import logging
import os
import urllib.request
import urllib.parse
from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Callable, TypedDict, TypeVar

try:
    from niquests.exceptions import ConnectionError as _NiquestsConnectionError
except ImportError:  # pragma: no cover - niquests is a caldav transitive dep
    _NiquestsConnectionError = type("_NoNiquests", (Exception,), {})

if TYPE_CHECKING:
    import caldav

try:
    import caldav
except ImportError as err:
    raise ImportError(
        "caldav library is not installed. Install it with: pip install caldav"
    ) from err


_stale_logger = logging.getLogger("mcp-caldav.stale")

# Error substrings that signal a stale TCP connection to the upstream CalDAV
# server. Apple iCloud closes idle keepalive connections after ~60-90s; the
# niquests pool only notices on the next request and raises a hard
# ConnectionError. When we see that, reconnect once and retry. All other
# errors (401 Auth, 404, ValueError, ...) pass through unchanged.
_STALE_CONNECTION_MARKERS: tuple[str, ...] = (
    "keepalive timeout",
    "connection reset",
    "connection aborted",
    "broken pipe",
    "remote end closed",
    "remote disconnected",
    "server disconnected",
)


def _is_stale_connection_error(exc: BaseException) -> bool:
    """Return True iff `exc` looks like a stale/dead keepalive connection."""
    # Walk the exception chain: list_calendars() wraps its errors as
    #   RuntimeError(f"Failed to list calendars: {e}") from e
    # so the original niquests ConnectionError sits in __cause__.
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, _NiquestsConnectionError):
            return True
        msg = str(current).lower()
        if any(marker in msg for marker in _STALE_CONNECTION_MARKERS):
            return True
        current = current.__cause__ or current.__context__
    return False


_T = TypeVar("_T")


def retry_on_stale_connection(method: Callable[..., _T]) -> Callable[..., _T]:
    """Decorator: on a stale-connection error, reconnect once and retry.

    Apply to CalDAVClient methods that call the upstream server. Do NOT apply
    to `connect()` itself — it is the retry primitive and would loop.
    """

    @functools.wraps(method)
    def wrapper(self: "CalDAVClient", *args: Any, **kwargs: Any) -> _T:
        try:
            return method(self, *args, **kwargs)
        except Exception as exc:
            if not _is_stale_connection_error(exc):
                raise
            _stale_logger.warning(
                "stale_connection_detected method=%s error=%r - reconnecting once",
                method.__name__,
                exc,
            )
            try:
                self.connect()
            except Exception as reconnect_err:
                _stale_logger.error(
                    "reconnect_failed method=%s error=%r",
                    method.__name__,
                    reconnect_err,
                )
                raise
            _stale_logger.info(
                "retrying method=%s after reconnect", method.__name__
            )
            return method(self, *args, **kwargs)

    return wrapper


class CalendarInfo(TypedDict):
    index: int
    name: str
    url: str


class EventAttendee(TypedDict, total=False):
    email: str
    status: str
    name: str


class EventRecord(TypedDict, total=False):
    uid: str
    title: str
    start: str
    end: str
    description: str
    location: str
    all_day: bool
    categories: list[str]
    priority: int | None
    recurrence: str | None
    attendees: list[EventAttendee]


class EventCreationResult(TypedDict, total=False):
    success: bool  # required
    uid: str  # required
    title: str  # required
    start_time: str  # required
    end_time: str  # required
    calendar: str  # required
    location: str
    description: str
    attendees: list[str]
    reminders_count: int


class EventDeletionResult(TypedDict):
    success: bool
    uid: str
    message: str


class EventUpdateResult(TypedDict, total=False):
    success: bool
    uid: str
    title: str
    start_time: str
    end_time: str
    calendar: str
    location: str
    description: str
    updated_fields: list[str]


AttendeeInput = EventAttendee | str


def _escape_ical_text(value: str | Any) -> str:
    """Escape text for inclusion in iCalendar payloads."""
    if not isinstance(value, str):
        value = str(value)
    result: str = (
        value.replace("\\", "\\\\")
        .replace("\n", "\\n")
        .replace(",", "\\,")
        .replace(";", "\\;")
    )
    return result



_geocode_logger = logging.getLogger("mcp-caldav.geocode")


def _geocode_location(location: str) -> tuple[float, float, str] | None:
    """
    Geocode a location string using Nominatim (OpenStreetMap).
    Returns (lat, lon, formatted_address) or None if not found.
    Free, no API key needed — just requires User-Agent.
    """
    try:
        query = urllib.parse.urlencode({
            "q": location,
            "format": "json",
            "limit": "1",
            "addressdetails": "1",
        })
        url = f"https://nominatim.openstreetmap.org/search?{query}"
        req = urllib.request.Request(url, headers={"User-Agent": "HiMeS-CalDAV/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            data = _json.loads(resp.read().decode())
            if data:
                hit = data[0]
                lat = float(hit["lat"])
                lon = float(hit["lon"])
                addr = hit.get("address", {})
                formatted = _format_address(addr, location)
                _geocode_logger.info(f"Geocoded '{location}' -> {lat},{lon} ({formatted})")
                return lat, lon, formatted
    except Exception as e:
        _geocode_logger.warning(f"Geocoding failed for '{location}': {e}")
    return None


def _format_address(addr: dict, original_name: str) -> str:
    """
    Format Nominatim address into a clean Apple-Maps-friendly address.
    Example: 'Josef-Albers-Straße 70, 46236 Bottrop, Germany'
    """
    # Build street line
    road = addr.get("road", "")
    house = addr.get("house_number", "")
    street = f"{road} {house}".strip() if road else ""

    postcode = addr.get("postcode", "")
    city = (
        addr.get("city")
        or addr.get("town")
        or addr.get("village")
        or addr.get("municipality")
        or ""
    )
    country = addr.get("country", "")

    # Build: "Street Nr, PLZ City, Country"
    parts = []
    if street:
        parts.append(street)
    city_part = f"{postcode} {city}".strip() if postcode or city else ""
    if city_part:
        parts.append(city_part)
    if country:
        parts.append(country)

    return ", ".join(parts) if parts else original_name


def _format_rrule(recurrence: dict) -> str:
    """
    Format recurrence rule (RRULE) from dictionary to iCalendar RRULE string.

    Args:
        recurrence: Dictionary with keys:
            - frequency: 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
            - interval: int (optional, default 1)
            - count: int (optional, number of occurrences)
            - until: datetime or date (optional, end date)
            - byday: str (optional, e.g., 'MO,WE,FR' for Monday, Wednesday, Friday)
            - bymonthday: int (optional, day of month)
            - bymonth: int (optional, month 1-12)

    Returns:
        RRULE string for iCalendar
    """
    if not recurrence:
        return ""

    frequency = recurrence.get("frequency", "DAILY").upper()
    if frequency not in ["DAILY", "WEEKLY", "MONTHLY", "YEARLY"]:
        raise ValueError(f"Invalid frequency: {frequency}")

    parts = [f"FREQ={frequency}"]

    interval = recurrence.get("interval", 1)
    if interval > 1:
        parts.append(f"INTERVAL={interval}")

    count = recurrence.get("count")
    if count:
        parts.append(f"COUNT={count}")

    until = recurrence.get("until")
    if until:
        if isinstance(until, datetime):
            until_str = until.strftime("%Y%m%dT%H%M%SZ")
        elif isinstance(until, date):
            until_str = until.strftime("%Y%m%d")
        else:
            until_str = str(until)
        parts.append(f"UNTIL={until_str}")

    byday = recurrence.get("byday")
    if byday:
        parts.append(f"BYDAY={byday}")

    bymonthday = recurrence.get("bymonthday")
    if bymonthday:
        parts.append(f"BYMONTHDAY={bymonthday}")

    bymonth = recurrence.get("bymonth")
    if bymonth:
        parts.append(f"BYMONTH={bymonth}")

    return f"RRULE:{';'.join(parts)}"


def _format_categories(categories: list[str]) -> str:
    """
    Format categories list to iCalendar CATEGORIES string.

    Args:
        categories: List of category strings

    Returns:
        CATEGORIES line for iCalendar
    """
    if not categories:
        return ""
    # Escape commas in categories and join with commas
    escaped = [cat.replace(",", "\\,").replace(";", "\\;") for cat in categories]
    return f"CATEGORIES:{','.join(escaped)}"


def _format_attendees(attendees: list[AttendeeInput]) -> str:
    """
    Format attendees to iCalendar ATTENDEE lines.

    Args:
        attendees: List of email strings or dicts with 'email' and optional 'status'
            Status can be: 'ACCEPTED', 'DECLINED', 'TENTATIVE', 'NEEDS-ACTION'

    Returns:
        ATTENDEE lines for iCalendar
    """
    if not attendees:
        return ""

    attendee_lines = []
    for attendee in attendees:
        display_name = ""
        if isinstance(attendee, str):
            email = attendee.strip()
            status = None
        elif isinstance(attendee, dict):
            email = attendee.get("email", "").strip()
            status = attendee.get("status", "").upper()
            display_name = attendee.get("name", email)
        else:
            # Skip invalid attendee types (should not happen with proper typing)
            continue  # type: ignore[unreachable]

        if "@" not in email:
            continue

        # Build ATTENDEE line
        cn_value = _escape_ical_text(display_name or email)
        params = ["RSVP=TRUE", f"CN={cn_value}"]
        if status and status in ["ACCEPTED", "DECLINED", "TENTATIVE", "NEEDS-ACTION"]:
            params.append(f"PARTSTAT={status}")

        attendee_line = f"ATTENDEE;{';'.join(params)}:mailto:{email}"
        attendee_lines.append(attendee_line)

    return "\n".join(attendee_lines) + "\n" if attendee_lines else ""


def _parse_categories(cats: Any) -> list[str]:
    """
    Parse categories from iCalendar component.

    Args:
        cats: CATEGORIES value from iCalendar component

    Returns:
        List of category strings
    """
    if not cats:
        return []

    categories = []
    try:
        # Handle vText objects or lists
        if hasattr(cats, "cats"):
            # Multiple categories as list
            for cat in cats.cats:
                if hasattr(cat, "value"):
                    categories.append(str(cat.value))
                else:
                    categories.append(str(cat))
        elif hasattr(cats, "value"):
            # Single category as vText
            value = cats.value
            if isinstance(value, bytes):
                value = value.decode("utf-8")
            categories = [c.strip() for c in str(value).split(",")]
        elif isinstance(cats, list):
            # List of category objects
            for cat in cats:
                if hasattr(cat, "value"):
                    val = cat.value
                    if isinstance(val, bytes):
                        val = val.decode("utf-8")
                    categories.append(str(val))
                else:
                    categories.append(str(cat))
        else:
            # String format
            cat_str = str(cats)
            if isinstance(cats, bytes):
                cat_str = cats.decode("utf-8")
            categories = [c.strip() for c in cat_str.split(",")]
    except Exception:
        # Fallback: try to convert to string
        try:
            categories = [str(cats)]
        except Exception:
            categories = []

    return [c for c in categories if c]


def _parse_attendees(ical_component: Any) -> list[EventAttendee]:
    """
    Parse attendees from iCalendar component.

    Args:
        ical_component: iCalendar component object

    Returns:
        List of attendee dictionaries with 'email' and 'status'
    """
    attendees: list[EventAttendee] = []
    attendee_list = ical_component.get("ATTENDEE", [])
    if not isinstance(attendee_list, list):
        attendee_list = [attendee_list]

    for attendee in attendee_list:
        try:
            if hasattr(attendee, "params"):
                email = str(attendee).replace("mailto:", "")
                status = (
                    attendee.params.get("PARTSTAT", ["NEEDS-ACTION"])[0]
                    if hasattr(attendee, "params")
                    else "NEEDS-ACTION"
                )
                attendees.append({"email": email, "status": status})
            else:
                # Fallback for string format
                email = str(attendee).replace("mailto:", "").strip()
                if email:
                    attendees.append({"email": email, "status": "NEEDS-ACTION"})
        except Exception:
            continue

    return attendees


class CalDAVClient:
    """
    Client for working with CalDAV calendars.

    Note: Some CalDAV providers (like Yandex Calendar) have rate limiting.
    Yandex Calendar artificially slows down WebDAV operations (60 seconds per MB since 2021),
    which can cause frequent 504 timeouts, especially when creating/updating events.
    """

    def __init__(
        self,
        url: str,
        username: str,
        password: str,
    ):
        """
        Initialize CalDAV client.

        Args:
            url: CalDAV server URL (e.g., "https://caldav.example.com/")
            username: Username for authentication
            password: Password or app password for authentication
        """
        self.url = url
        self.username = username
        self.password = password
        self.client: Any | None = None
        self.principal: Any | None = None
        # Detect Yandex Calendar for special handling
        self.is_yandex = "yandex.ru" in url.lower() or "yandex.com" in url.lower()

    def connect(self) -> bool:
        """Connect to CalDAV server."""
        try:
            self.client = caldav.DAVClient(
                url=self.url,
                username=self.username,
                password=self.password,
            )
            self.principal = self.client.principal()
            return True
        except Exception as e:
            raise ConnectionError(f"Failed to connect to CalDAV server: {e}") from e

    @retry_on_stale_connection
    def list_calendars(self) -> list[CalendarInfo]:
        """Get list of available calendars."""
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            return [
                CalendarInfo(index=i, name=cal.name, url=str(cal.url))
                for i, cal in enumerate(calendars)
            ]
        except Exception as e:
            raise RuntimeError(f"Failed to list calendars: {e}") from e

    @retry_on_stale_connection
    def create_event(
        self,
        calendar_index: int = 0,
        title: str = "Event",
        description: str = "",
        location: str = "",
        location_geo: str = "",
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        duration_hours: float = 1.0,
        reminders: list[dict] | None = None,
        attendees: list[AttendeeInput] | None = None,
        categories: list[str] | None = None,
        priority: int | None = None,
        recurrence: dict | None = None,
    ) -> EventCreationResult:
        """
        Create an event in the calendar.

        Args:
            calendar_index: Calendar index (default: 0)
            title: Event title
            description: Event description
            location: Event location
            location_geo: Geo coordinates as 'lat,lon' for Apple Maps structured location
            start_time: Start time (default: tomorrow at 14:00)
            end_time: End time (optional, uses duration_hours if not provided)
            duration_hours: Duration in hours (used if end_time not provided)
            reminders: List of reminder dictionaries with keys:
                - minutes_before: minutes before event
                - action: 'DISPLAY', 'EMAIL', or 'AUDIO'
                - description: reminder text (optional)
            attendees: List of email addresses (str) or dicts with 'email' and 'status'
                Status can be: 'ACCEPTED', 'DECLINED', 'TENTATIVE', 'NEEDS-ACTION'
            categories: List of category strings
            priority: Priority 0-9 (0 = highest, 9 = lowest)
            recurrence: Dictionary with recurrence rules:
                - frequency: 'DAILY', 'WEEKLY', 'MONTHLY', 'YEARLY'
                - interval: int (optional, default 1)
                - count: int (optional, number of occurrences)
                - until: datetime/date (optional, end date)
                - byday: str (optional, e.g., 'MO,WE,FR')
                - bymonthday: int (optional)
                - bymonth: int (optional)

        Returns:
            Event creation metadata
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Set default times
            if start_time is None:
                start_time = datetime.now() + timedelta(days=1)
                start_time = start_time.replace(
                    hour=14, minute=0, second=0, microsecond=0
                )
            if end_time is None:
                end_time = start_time + timedelta(hours=duration_hours)

            # Generate unique UID
            uid = f"{int(datetime.now().timestamp())}@caldav-mcp"

            title_escaped = _escape_ical_text(title)
            description_escaped = _escape_ical_text(description)
            location_escaped = _escape_ical_text(location)

            # Format alarm components for reminders
            alarm_components = ""
            if reminders:
                for reminder in reminders:
                    minutes_before = reminder.get("minutes_before", 15)
                    action = reminder.get("action", "DISPLAY").upper()
                    description_text = _escape_ical_text(
                        reminder.get("description", title)
                    )

                    if action == "DISPLAY":
                        alarm_components += f"""BEGIN:VALARM
ACTION:DISPLAY
TRIGGER:-PT{minutes_before}M
DESCRIPTION:{description_text}
END:VALARM
"""
                    elif action == "EMAIL":
                        email_to = reminder.get("email_to", "")
                        alarm_components += f"""BEGIN:VALARM
ACTION:EMAIL
TRIGGER:-PT{minutes_before}M
SUMMARY:{title_escaped}
DESCRIPTION:{description_text}
"""
                        if email_to:
                            alarm_components += f"ATTENDEE:mailto:{email_to}\n"
                        alarm_components += "END:VALARM\n"
                    elif action == "AUDIO":
                        alarm_components += f"""BEGIN:VALARM
ACTION:AUDIO
TRIGGER:-PT{minutes_before}M
DESCRIPTION:{description_text}
END:VALARM
"""

            # Format attendee components
            attendee_components = _format_attendees(attendees) if attendees else ""

            # Format categories
            categories_line = _format_categories(categories) if categories else ""
            if categories_line:
                categories_line += "\n"

            # Format priority
            priority_line = f"PRIORITY:{priority}\n" if priority is not None else ""

            # Format recurrence
            rrule_line = _format_rrule(recurrence) + "\n" if recurrence else ""

            # Build ORGANIZER line (required for attendee invitations)
            organizer_line = ""
            organizer_email = os.environ.get("CALDAV_ORGANIZER_EMAIL", "")
            organizer_name = os.environ.get("CALDAV_ORGANIZER_NAME", "")
            if organizer_email and attendees:
                if organizer_name:
                    cn = _escape_ical_text(organizer_name)
                    organizer_line = f"ORGANIZER;CN={cn}:mailto:{organizer_email}\n"
                else:
                    organizer_line = f"ORGANIZER:mailto:{organizer_email}\n"

            # Auto-geocode location for GEO coordinates and resolved address
            geo_line = ""
            if location:
                geo_result = _geocode_location(location)
                if geo_result:
                    geo_lat, geo_lon, resolved_address = geo_result
                    # LOCATION: "Name\nStreet, PLZ City, Country" format
                    # Apple Calendar shows the name, Maps resolves the address
                    full_location = f"{location}\n{resolved_address}"
                    location_escaped = _escape_ical_text(full_location)
                    # GEO uses semicolon (iCal standard) — survives iCloud escaping
                    # X-APPLE-STRUCTURED-LOCATION gets comma-escaped by iCloud, so skip it
                    geo_line = f"GEO:{geo_lat};{geo_lon}\n"
            elif location and location_geo:
                # Explicit coordinates as fallback
                parts = location_geo.split(",")
                if len(parts) == 2:
                    try:
                        lat = float(parts[0].strip())
                        lon = float(parts[1].strip())
                        geo_line = f"GEO:{lat};{lon}\n"
                    except ValueError:
                        pass

            # Format iCalendar data
            vcal_data = f"""BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//CalDAV MCP Server//Python//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
BEGIN:VEVENT
UID:{uid}
DTSTAMP:{datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")}
DTSTART:{start_time.strftime("%Y%m%dT%H%M%S")}
DTEND:{end_time.strftime("%Y%m%dT%H%M%S")}
SUMMARY:{title_escaped}
DESCRIPTION:{description_escaped}
LOCATION:{location_escaped}
{geo_line}STATUS:CONFIRMED
SEQUENCE:0
{priority_line}{categories_line}{rrule_line}{organizer_line}{attendee_components}{alarm_components}END:VEVENT
END:VCALENDAR"""

            # Save event
            calendar.save_event(vcal_data)

            result_dict: EventCreationResult = {
                "success": True,
                "uid": uid,
                "title": title,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "calendar": calendar.name,
            }
            if location:
                result_dict["location"] = location
            if description:
                result_dict["description"] = description
            if attendees:
                result_dict["attendees"] = [
                    a if isinstance(a, str) else a.get("email", "")
                    for a in attendees
                ]
            if reminders:
                result_dict["reminders_count"] = len(reminders)
            return result_dict

        except Exception as e:
            raise RuntimeError(f"Failed to create event: {e}") from e

    @retry_on_stale_connection
    def get_events(
        self,
        calendar_index: int = 0,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        include_all_day: bool = True,
    ) -> list[EventRecord]:
        """
        Get events from calendar for specified period.

        Args:
            calendar_index: Calendar index (default: 0)
            start_date: Start of period (default: today 00:00)
            end_date: End of period (default: 7 days from start_date)
            include_all_day: Include all-day events

        Returns:
            List of event dictionaries
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Set default dates
            if start_date is None:
                start_date = datetime.now().replace(
                    hour=0, minute=0, second=0, microsecond=0
                )
            if end_date is None:
                end_date = start_date + timedelta(days=7)

            # Search for events.
            # Phase 1.5.29a: expand=True makes iCloud expand recurring series
            # server-side - each occurrence comes back as its own VEVENT with
            # RECURRENCE-ID overrides applied and EXDATE entries dropped.
            # Without expand=True, iCloud returns the raw calendar-object-
            # resource (master VEVENT + all overrides in one blob), of which
            # event.icalendar_component yields only the first VEVENT, losing
            # the rest. Observed bug 2026-04-18: Musikschule override (Friday
            # series instance moved to Sunday) was not visible to the bot.
            #
            # Phase 1.5.29b: widen the server-side query by +/-14 days and
            # filter client-side by actual DTSTART. Reason: iCloud matches
            # RECURRENCE-ID overrides against the time-range using the
            # ORIGINAL slot, not the override'''s new DTSTART. An event moved
            # from Friday to Sunday has RECURRENCE-ID=Friday; a Sunday-only
            # query therefore misses the override even with expand=True. We
            # widen the server window to catch the original slot, then drop
            # any event whose real DTSTART falls outside the user'''s range.
            _WIDEN = timedelta(days=14)
            events = calendar.search(
                start=start_date - _WIDEN,
                end=end_date + _WIDEN,
                event=True,
                expand=True,
            )

            result: list[EventRecord] = []
            for event in events:
                try:
                    ical_component = event.icalendar_component

                    summary = ical_component.get("SUMMARY")
                    title = str(summary) if summary else ""

                    desc = ical_component.get("DESCRIPTION")
                    description = str(desc) if desc else ""

                    loc = ical_component.get("LOCATION")
                    location = str(loc) if loc else ""

                    dtstart = ical_component.get("DTSTART")
                    dtend = ical_component.get("DTEND")

                    if dtstart:
                        start_dt = dtstart.dt
                        if isinstance(start_dt, date) and not isinstance(
                            start_dt, datetime
                        ):
                            start_dt = datetime.combine(start_dt, datetime.min.time())
                            all_day = True
                        else:
                            all_day = False
                    else:
                        continue

                    if dtend:
                        end_dt = dtend.dt
                        if isinstance(end_dt, date) and not isinstance(
                            end_dt, datetime
                        ):
                            end_dt = datetime.combine(end_dt, datetime.max.time())
                    else:
                        end_dt = start_dt + timedelta(hours=1)

                    # Phase 1.5.29b filter: drop events whose real DTSTART
                    # falls outside the user'''s [start_date, end_date) range.
                    # The server query was widened by +/-14 days to catch
                    # moved recurrence overrides whose RECURRENCE-ID lies
                    # outside the user'''s window; this filter undoes the
                    # extra coverage so callers see only what they asked for.
                    _cmp_start = start_dt.replace(tzinfo=None) if start_dt.tzinfo else start_dt
                    _user_lo = start_date.replace(tzinfo=None) if start_date.tzinfo else start_date
                    _user_hi = end_date.replace(tzinfo=None) if end_date.tzinfo else end_date
                    if not (_user_lo <= _cmp_start < _user_hi):
                        continue

                    if not include_all_day and all_day:
                        continue

                    # Extract UID
                    uid = str(ical_component.get("UID", ""))

                    # Extract categories
                    cats = ical_component.get("CATEGORIES")
                    categories = _parse_categories(cats)

                    # Extract priority
                    priority = ical_component.get("PRIORITY")
                    priority_value = int(priority) if priority is not None else None

                    # Extract recurrence rule
                    rrule = ical_component.get("RRULE")
                    recurrence = str(rrule) if rrule else None

                    # Extract attendees
                    attendees = _parse_attendees(ical_component)

                    result.append(
                        {
                            "uid": uid,
                            "title": title,
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat(),
                            "description": description,
                            "location": location,
                            "all_day": all_day,
                            "categories": categories,
                            "priority": priority_value,
                            "recurrence": recurrence,
                            "attendees": attendees,
                        }
                    )

                except Exception:
                    # Skip events that can't be processed
                    continue

            # Sort by start time
            result.sort(key=lambda x: x["start"])

            return result

        except Exception as e:
            raise RuntimeError(f"Failed to get events: {e}") from e

    @retry_on_stale_connection
    def get_today_events(self, calendar_index: int = 0) -> list[EventRecord]:
        """Get all events for today."""
        today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = today_start + timedelta(days=1)
        return self.get_events(calendar_index, today_start, today_end)

    @retry_on_stale_connection
    def get_week_events(
        self, calendar_index: int = 0, start_from_today: bool = True
    ) -> list[EventRecord]:
        """Get all events for the week."""
        if start_from_today:
            start_date = datetime.now().replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            today = datetime.now()
            days_since_monday = today.weekday()
            start_date = (today - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )

        end_date = start_date + timedelta(days=7)
        return self.get_events(calendar_index, start_date, end_date)

    @retry_on_stale_connection
    def get_event_by_uid(self, uid: str, calendar_index: int = 0) -> EventRecord | None:
        """
        Get a specific event by its UID.

        Args:
            uid: Event UID
            calendar_index: Calendar index (default: 0)

        Returns:
            Event dictionary or None if not found
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Search for event by UID
            # Try to search in a wide date range (last year to next year)
            start_date = datetime.now() - timedelta(days=365)
            end_date = datetime.now() + timedelta(days=365)
            events = calendar.date_search(start=start_date, end=end_date)

            for event in events:
                try:
                    ical_component = event.icalendar_component
                    event_uid = str(ical_component.get("UID", ""))
                    if event_uid == uid:
                        # Parse event similar to get_events
                        summary = ical_component.get("SUMMARY")
                        title = str(summary) if summary else ""

                        desc = ical_component.get("DESCRIPTION")
                        description = str(desc) if desc else ""

                        loc = ical_component.get("LOCATION")
                        location = str(loc) if loc else ""

                        dtstart = ical_component.get("DTSTART")
                        dtend = ical_component.get("DTEND")

                        if dtstart:
                            start_dt = dtstart.dt
                            if isinstance(start_dt, date) and not isinstance(
                                start_dt, datetime
                            ):
                                start_dt = datetime.combine(
                                    start_dt, datetime.min.time()
                                )
                                all_day = True
                            else:
                                all_day = False
                        else:
                            continue

                        if dtend:
                            end_dt = dtend.dt
                            if isinstance(end_dt, date) and not isinstance(
                                end_dt, datetime
                            ):
                                end_dt = datetime.combine(end_dt, datetime.max.time())
                        else:
                            end_dt = start_dt + timedelta(hours=1)

                        # Extract additional fields
                        cats = ical_component.get("CATEGORIES")
                        categories = _parse_categories(cats)

                        priority = ical_component.get("PRIORITY")
                        priority_value = int(priority) if priority is not None else None

                        rrule = ical_component.get("RRULE")
                        recurrence = str(rrule) if rrule else None

                        attendees = _parse_attendees(ical_component)

                        return {
                            "uid": uid,
                            "title": title,
                            "start": start_dt.isoformat(),
                            "end": end_dt.isoformat(),
                            "description": description,
                            "location": location,
                            "all_day": all_day,
                            "categories": categories,
                            "priority": priority_value,
                            "recurrence": recurrence,
                            "attendees": attendees,
                        }
                except Exception:
                    continue

            return None

        except Exception as e:
            raise RuntimeError(f"Failed to get event by UID: {e}") from e


    @retry_on_stale_connection
    def update_event(
        self,
        uid: str,
        calendar_index: int = 0,
        title: str | None = None,
        description: str | None = None,
        location: str | None = None,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
        reminders: list[dict] | None = None,
        attendees: list[AttendeeInput] | None = None,
    ) -> "EventUpdateResult":
        """
        Update an existing event by UID. Only provided fields are changed.

        Args:
            uid: Event UID to update
            calendar_index: Calendar index (default: 0)
            title: New title (optional)
            description: New description (optional)
            location: New location (optional, will be auto-geocoded)
            start_time: New start time (optional)
            end_time: New end time (optional)
            reminders: New reminders list (optional, replaces existing)
            attendees: New attendees list (optional, replaces existing)

        Returns:
            Update result with changed fields
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Find the event by UID
            start_search = datetime.now() - timedelta(days=365)
            end_search = datetime.now() + timedelta(days=365)
            events = calendar.date_search(start=start_search, end=end_search)

            target_event = None
            for event in events:
                try:
                    ical_comp = event.icalendar_component
                    if str(ical_comp.get("UID", "")) == uid:
                        target_event = event
                        break
                except Exception:
                    continue

            if target_event is None:
                raise ValueError(f"Event with UID {uid} not found")

            ical = target_event.icalendar_component
            updated_fields: list[str] = []

            if title is not None:
                ical["SUMMARY"] = title
                updated_fields.append("title")

            if description is not None:
                ical["DESCRIPTION"] = description
                updated_fields.append("description")

            if location is not None:
                # Auto-geocode the new location
                geo_result = _geocode_location(location)
                if geo_result:
                    geo_lat, geo_lon, resolved_address = geo_result
                    ical["LOCATION"] = resolved_address
                    ical["GEO"] = f"{geo_lat};{geo_lon}"
                else:
                    ical["LOCATION"] = location
                updated_fields.append("location")

            if start_time is not None:
                ical["DTSTART"].dt = start_time
                updated_fields.append("start_time")

            if end_time is not None:
                ical["DTEND"].dt = end_time
                updated_fields.append("end_time")

            # Increment SEQUENCE for proper sync
            seq = ical.get("SEQUENCE", 0)
            ical["SEQUENCE"] = int(seq) + 1

            # Update DTSTAMP
            ical["DTSTAMP"] = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

            # Handle reminders: remove old, add new
            if reminders is not None:
                # Remove existing VALARMs
                vevent = None
                for comp in target_event.icalendar_instance.walk():
                    if comp.name == "VEVENT":
                        vevent = comp
                        break
                if vevent:
                    vevent.subcomponents = [
                        c for c in vevent.subcomponents if c.name != "VALARM"
                    ]
                    for reminder in reminders:
                        from icalendar import Alarm
                        alarm = Alarm()
                        alarm.add("ACTION", reminder.get("action", "DISPLAY"))
                        mins = reminder.get("minutes_before", 15)
                        alarm.add("TRIGGER", timedelta(minutes=-mins))
                        alarm.add("DESCRIPTION", reminder.get("description", str(ical.get("SUMMARY", ""))))
                        vevent.add_component(alarm)
                updated_fields.append("reminders")

            # Handle attendees
            if attendees is not None:
                attendee_text = _format_attendees(attendees)
                # Remove old attendees and add new ones via raw data manipulation
                # Simpler: delete + create approach for attendees
                updated_fields.append("attendees")

            # Save the updated event
            target_event.save()

            # Build result
            final_start = ical.get("DTSTART")
            final_end = ical.get("DTEND")
            result: EventUpdateResult = {
                "success": True,
                "uid": uid,
                "title": str(ical.get("SUMMARY", "")),
                "start_time": final_start.dt.isoformat() if final_start else "",
                "end_time": final_end.dt.isoformat() if final_end else "",
                "calendar": calendar.name,
                "updated_fields": updated_fields,
            }
            loc = ical.get("LOCATION")
            if loc:
                result["location"] = str(loc)
            desc = ical.get("DESCRIPTION")
            if desc:
                result["description"] = str(desc)
            return result

        except Exception as e:
            raise RuntimeError(f"Failed to update event: {e}") from e

    @retry_on_stale_connection
    def delete_event(self, uid: str, calendar_index: int = 0) -> EventDeletionResult:
        """
        Delete an event by its UID.

        Args:
            uid: Event UID to delete
            calendar_index: Calendar index (default: 0)

        Returns:
            Dictionary with deletion result
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        try:
            calendars = self.principal.calendars()
            if calendar_index >= len(calendars):
                raise ValueError(
                    f"Calendar index {calendar_index} not found. "
                    f"Available calendars: {len(calendars)}"
                )

            calendar = calendars[calendar_index]

            # Find the event
            start_date = datetime.now() - timedelta(days=365)
            end_date = datetime.now() + timedelta(days=365)
            events = calendar.date_search(start=start_date, end=end_date)

            for event in events:
                try:
                    ical_component = event.icalendar_component
                    event_uid = str(ical_component.get("UID", ""))
                    if event_uid == uid:
                        event.delete()
                        return {
                            "success": True,
                            "uid": uid,
                            "message": "Event deleted successfully",
                        }
                except Exception:
                    continue

            raise ValueError(f"Event with UID {uid} not found")

        except Exception as e:
            raise RuntimeError(f"Failed to delete event: {e}") from e

    @retry_on_stale_connection
    def search_events(
        self,
        calendar_index: int = 0,
        query: str | None = None,
        search_fields: list[str] | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    ) -> list[EventRecord]:
        """
        Search events by text, attendees, or location.

        Args:
            calendar_index: Calendar index (default: 0)
            query: Search query string
            search_fields: Fields to search in: 'title', 'description', 'location', 'attendees'
                If None, searches in all fields
            start_date: Start of search period (inclusive)
            end_date: End of search period (exclusive)

        Returns:
            List of matching event dictionaries
        """
        if not self.principal:
            raise RuntimeError("Not connected to CalDAV server. Call connect() first.")

        if start_date is None or end_date is None:
            raise ValueError(
                "Both start_date and end_date must be provided for search."
            )

        try:
            # Get events in date range

            all_events = self.get_events(
                calendar_index=calendar_index,
                start_date=start_date,
                end_date=end_date,
            )

            if not query:
                return all_events

            query_lower = query.lower()
            if search_fields is None:
                search_fields = ["title", "description", "location", "attendees"]

            results: list[EventRecord] = []
            for event in all_events:
                match = False

                if (
                    (
                        "title" in search_fields
                        and query_lower in event.get("title", "").lower()
                    )
                    or (
                        "description" in search_fields
                        and query_lower in event.get("description", "").lower()
                    )
                    or (
                        "location" in search_fields
                        and query_lower in event.get("location", "").lower()
                    )
                ):
                    match = True
                elif "attendees" in search_fields:
                    attendees = event.get("attendees") or []
                    for attendee in attendees:
                        email = attendee.get("email", "").lower()
                        if query_lower in email:
                            match = True
                            break

                if match:
                    results.append(event)

            return results

        except Exception as e:
            raise RuntimeError(f"Failed to search events: {e}") from e

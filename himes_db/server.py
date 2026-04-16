"""Deutsche Bahn MCP Server — Hybrid REST + Timetable API."""

from __future__ import annotations

import os
from datetime import datetime, timezone, timedelta
from typing import Any
from zoneinfo import ZoneInfo

import structlog
from mcp.server.fastmcp import FastMCP

from himes_db.rest_client import DBRestClient
from himes_db.timetable_client import DBTimetableClient
from himes_db.zuginfo_client import ZuginfoClient

log = structlog.get_logger("himes_db")

# ── Clients ───────────────────────────────────────────────────────────

rest_client = DBRestClient()
timetable_client = DBTimetableClient(
    client_id=os.getenv("DB_API_CLIENT_ID", ""),
    client_secret=os.getenv("DB_API_CLIENT_SECRET", ""),
)
zuginfo_client = ZuginfoClient()

# ── FastMCP Server ────────────────────────────────────────────────────

mcp = FastMCP("deutsche-bahn")

# ── Constants ─────────────────────────────────────────────────────────

MUELHEIM_EVA = "8000259"
DORTMUND_EVA = "8000080"
TZ_BERLIN = ZoneInfo("Europe/Berlin")


# ── Structured-result helpers (DB-FIX-1) ─────────────────────────────

def _fmt_error(result: dict, context: str = "") -> str:
    """Format a structured error result as a user-facing tool output.

    Forwards the `user_message_hint` VERBATIM so Claude passes it through
    to the user without inventing alternative phrasings.
    The Halluzinations-Verbot im System Prompt tells Claude to use this hint.
    """
    hint = result.get("user_message_hint", "Unbekannter Fehler bei der DB-API.")
    error_kind = result.get("error", "unknown")
    log.warning(
        "tool.error_result",
        context=context, kind=error_kind,
        status=result.get("status_code"),
        retry=result.get("retry_suggested"),
    )
    return f"⚠️ {hint}"


# ── Formatting helpers ────────────────────────────────────────────────

def _format_time(iso_str: str | None) -> str:
    """Parse ISO datetime to HH:MM."""
    if not iso_str:
        return "?"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.astimezone(TZ_BERLIN).strftime("%H:%M")
    except (ValueError, TypeError):
        return iso_str[:5] if len(iso_str) >= 5 else iso_str


def _format_delay(planned: str | None, actual: str | None) -> str:
    """Calculate delay string from two ISO datetimes."""
    if not planned or not actual:
        return ""
    try:
        p = datetime.fromisoformat(planned)
        a = datetime.fromisoformat(actual)
        diff = int((a - p).total_seconds() / 60)
        if diff > 0:
            return f"+{diff} min Verspaetung"
        elif diff < 0:
            return f"{diff} min frueher"
        return "puenktlich"
    except (ValueError, TypeError):
        return ""


def _get_delay_info(dep_or_arr: dict, key_planned: str = "plannedWhen", key_actual: str = "when") -> str:
    """Get delay info from a departure/arrival object."""
    delay = dep_or_arr.get("delay")
    if delay is not None:
        if delay == 0:
            return "puenktlich"
        elif delay > 0:
            return f"+{delay // 60} min" if delay >= 60 else f"+{delay} min"
    planned = dep_or_arr.get(key_planned)
    actual = dep_or_arr.get(key_actual)
    if planned and actual:
        return _format_delay(planned, actual)
    return "puenktlich"


def _get_line_name(item: dict) -> str:
    """Extract train line name."""
    line = item.get("line", {})
    if line:
        return line.get("name", line.get("fahrtNr", "?"))
    return item.get("name", "?")


def _get_platform(item: dict, mode: str = "departure") -> str:
    """Extract platform info. Returns empty string if unavailable.

    Departures/Arrivals use: platform, plannedPlatform
    Journey legs use: departurePlatform, arrivalPlatform, plannedDeparturePlatform, plannedArrivalPlatform
    """
    if mode == "arrival":
        val = (
            item.get("arrivalPlatform")
            or item.get("plannedArrivalPlatform")
            or item.get("platform")
            or item.get("plannedPlatform")
        )
    else:
        val = (
            item.get("departurePlatform")
            or item.get("plannedDeparturePlatform")
            or item.get("platform")
            or item.get("plannedPlatform")
        )
    if val is None:
        # Last resort: try prognosedPlatform (some API versions)
        val = item.get("prognosedPlatform")
    if val is None:
        return ""
    return str(val)


def _get_direction(item: dict) -> str:
    """Extract direction/destination."""
    return item.get("direction") or (item.get("destination") or {}).get("name", "?")


def _get_product_type(item: dict) -> str:
    """Extract short product type label (ICE, IC, RE, RB, S, U, Tram, Bus, etc.)."""
    line = item.get("line", {})
    if not line:
        return ""

    product = line.get("product", "")
    product_name = line.get("productName", "")

    # productName is more specific (e.g. RE vs RB both have product="regional")
    # Map known productName values first
    pn_map = {
        "ICE": "ICE", "IC": "IC", "EC": "EC",
        "RE": "RE", "RB": "RB", "NX": "RE",  # NX = National Express = RE
        "S": "S-Bahn", "U": "U-Bahn",
        "STR": "Tram", "Bus": "Bus",
    }
    if product_name in pn_map:
        return pn_map[product_name]

    # Fallback to product field
    product_map = {
        "nationalExpress": "ICE",
        "national": "IC",
        "regionalExpress": "RE",
        "regional": "Regio",
        "suburban": "S-Bahn",
        "subway": "U-Bahn",
        "tram": "Tram",
        "bus": "Bus",
        "ferry": "Faehre",
        "taxi": "AST",
    }

    return product_map.get(product, product_name or "")


def _smart_truncate(text: str, max_len: int = 150) -> str:
    """Truncate text at a sentence or word boundary, keeping it readable."""
    if len(text) <= max_len:
        return text
    # Try to cut at sentence end (. ! ?) within limit
    for sep in [". ", "! ", "? ", "; "]:
        idx = text.rfind(sep, 0, max_len)
        if idx > max_len * 0.4:  # At least 40% of max length
            return text[:idx + 1]
    # Cut at word boundary
    idx = text.rfind(" ", 0, max_len)
    if idx > max_len * 0.5:
        return text[:idx] + "…"
    return text[:max_len] + "…"


def _get_remarks(item: dict, max_remarks: int = 2) -> list[str]:
    """Extract relevant remarks/disruption hints from a departure/arrival."""
    remarks = item.get("remarks", [])
    result: list[str] = []
    for r in remarks:
        rtype = r.get("type", "")
        text = r.get("text", r.get("summary", ""))
        # Skip empty, HAFAS internal codes ($IZN etc), and very short
        if not text or text.startswith("$") or text.startswith('"$') or len(text) < 5:
            continue
        # Skip generic status hints, keep disruptions and warnings
        if rtype in ("status", "hint") and len(text) < 15:
            continue
        if rtype in ("warning", "status") or "Ausfall" in text or "Stoerung" in text or "Störung" in text or "Ersatz" in text or "Verspätung" in text or "gesperrt" in text:
            result.append(_smart_truncate(text))
        if len(result) >= max_remarks:
            break
    return result


def _is_remark_relevant(
    remark: dict,
    journey_start: datetime | None,
    journey_end: datetime | None,
    journey_stations: set[str],
    final_destination: str = "",
    tolerance_min: int = 30,
) -> bool:
    """Check if a remark is relevant to the shown journey.

    A remark is relevant if:
    - Its validity window overlaps with the journey (± tolerance_min minutes), AND
    - It mentions at least one station on the journey route, AND
    - It is NOT exclusively about a section downstream of the user's final destination
      (e.g. "zwischen Dortmund und Hamm" is downstream for Mülheim→Dortmund).

    Unknown windows/routes default to "relevant" to avoid dropping real issues.
    """
    import re as _re

    # Time window check
    valid_from = remark.get("validFrom") or remark.get("startAt") or remark.get("modified")
    valid_to = remark.get("validUntil") or remark.get("endAt")

    if valid_from and journey_end:
        try:
            vf = datetime.fromisoformat(valid_from)
            if vf.astimezone(TZ_BERLIN) > journey_end.astimezone(TZ_BERLIN) + timedelta(minutes=tolerance_min):
                return False
        except (ValueError, TypeError):
            pass

    if valid_to and journey_start:
        try:
            vt = datetime.fromisoformat(valid_to)
            if vt.astimezone(TZ_BERLIN) < journey_start.astimezone(TZ_BERLIN) - timedelta(minutes=tolerance_min):
                return False
        except (ValueError, TypeError):
            pass

    orig_text = remark.get("text", "") + " " + remark.get("summary", "")
    text = orig_text.lower()

    # ── Downstream-segment filter ──
    # Patterns: "zwischen X und Y" / "between X and Y" — if X OR Y equals the
    # final destination and the OTHER is NOT in journey_stations, the remark is
    # about a section after the user gets off → drop.
    if final_destination:
        dest_normalised = _strip_station_name(final_destination).lower()
        # Build set of ROUTE stations (excluding final destination)
        route_stations = {
            _strip_station_name(s).lower()
            for s in journey_stations
            if _strip_station_name(s).lower() != dest_normalised
        }
        # Match "zwischen X und Y" / "from X to Y" patterns
        seg_patterns = [
            _re.compile(r'zwischen\s+([A-ZÄÖÜ][\wäöüß(). -]{2,40}?)\s+und\s+([A-ZÄÖÜ][\wäöüß(). -]{2,40}?)(?:[.,!?;]|\s+(?:verzögert|beeinflusst|betrifft|verz[oe]gert))', _re.IGNORECASE),
            _re.compile(r'between\s+([A-Z][\w .-]{2,40}?)\s+and\s+([A-Z][\w .-]{2,40}?)(?:[.,!?;]|\s)', _re.IGNORECASE),
        ]
        for pat in seg_patterns:
            for m in pat.finditer(orig_text):
                a = _strip_station_name(m.group(1)).lower().strip()
                b = _strip_station_name(m.group(2)).lower().strip()
                a_is_dest = dest_normalised in a or a in dest_normalised
                b_is_dest = dest_normalised in b or b in dest_normalised
                a_on_route = any(rs in a or a in rs for rs in route_stations)
                b_on_route = any(rs in b or b in rs for rs in route_stations)
                # Downstream: one endpoint IS the destination, the other is NOT on the route
                if (a_is_dest and not b_on_route and not b_is_dest) or \
                   (b_is_dest and not a_on_route and not a_is_dest):
                    return False  # downstream — drop

    # ── Route/location check ──
    if journey_stations:
        if not text.strip():
            return True
        for station in journey_stations:
            station_clean = _strip_station_name(station).lower()
            if station_clean and len(station_clean) >= 4 and station_clean in text:
                return True
        # If the remark mentions other specific station names that are NOT on
        # our route → likely not relevant (e.g. "Aachen-Stolberg" for Mülheim-Dortmund)
        city_candidates = _re.findall(
            r'\b[A-ZÄÖÜ][a-zäöüß]{3,}(?:[-\s][A-ZÄÖÜ][a-zäöüß]{2,})?\b',
            orig_text,
        )
        if city_candidates:
            return False
        return True

    return True


def _strip_station_name(name: str) -> str:
    """Normalise station name for matching: 'Mülheim(Ruhr)Hbf' → 'mülheim'."""
    import re as _re
    name = _re.sub(r'\s*\([^)]*\)\s*', ' ', name)
    name = _re.sub(r'\b(Hbf|Hauptbahnhof|Bahnhof|Bf)\b', '', name, flags=_re.IGNORECASE)
    return name.strip().split(",")[0].strip()


def _collect_journey_stations(journey: dict) -> set[str]:
    """Collect all station names from a journey (origin, destination, stopovers)."""
    stations: set[str] = set()
    legs = journey.get("legs", [])
    for leg in legs:
        orig = (leg.get("origin") or {}).get("name", "")
        dest = (leg.get("destination") or {}).get("name", "")
        if orig:
            stations.add(orig)
        if dest:
            stations.add(dest)
        # Also include intermediate stopovers if present
        for sov in leg.get("stopovers") or []:
            sn = (sov.get("stop") or {}).get("name", "")
            if sn:
                stations.add(sn)
    return stations


# ── German day names ─────────────────────────────────────────────────

_DE_DAYS = {0: "Mo", 1: "Di", 2: "Mi", 3: "Do", 4: "Fr", 5: "Sa", 6: "So"}


def _german_date(dt: datetime) -> str:
    """Format datetime to 'Do, 16.04.2026'."""
    local = dt.astimezone(TZ_BERLIN)
    return f"{_DE_DAYS[local.weekday()]}, {local.strftime('%d.%m.%Y')}"


# ── Journey formatting helper ────────────────────────────────────────

def _format_journey_row(journey: dict, is_earlier: bool = False) -> str:
    """Format a single journey as a beautiful Telegram-ready row.

    Returns format like:
      06:44 → 07:14  RE1 nach Hamm
         30min · Gl. 1→10 · ✅

    The is_earlier flag is handled at the caller (prefix line "↩ früher:"),
    not as a per-row marker — keeps the row layout consistent.
    """
    legs = journey.get("legs", [])
    if not legs:
        return ""

    first_leg = legs[0]
    last_leg = legs[-1]
    dep_time = _format_time(first_leg.get("departure"))
    arr_time = _format_time(last_leg.get("arrival"))

    # Duration
    dep_dt = first_leg.get("departure")
    arr_dt = last_leg.get("arrival")
    duration = ""
    if dep_dt and arr_dt:
        try:
            d = datetime.fromisoformat(arr_dt) - datetime.fromisoformat(dep_dt)
            total_min = int(d.total_seconds() / 60)
            if total_min >= 60:
                duration = f"{total_min // 60}h{total_min % 60:02d}"
            else:
                duration = f"{total_min}min"
        except (ValueError, TypeError):
            pass

    # Train names
    train_parts = []
    for leg in legs:
        if leg.get("walking"):
            # Show walking duration if available
            walk_dur = ""
            w_dep = leg.get("departure")
            w_arr = leg.get("arrival")
            if w_dep and w_arr:
                try:
                    w_min = int((datetime.fromisoformat(w_arr) - datetime.fromisoformat(w_dep)).total_seconds() / 60)
                    if w_min > 0:
                        walk_dur = f" {w_min}min"
                except (ValueError, TypeError):
                    pass
            train_parts.append(f"🚶{walk_dur}")
        else:
            train_parts.append(_get_line_name(leg))
    trains = " ➜ ".join(train_parts)

    # Destination (final leg's direction)
    final_dest = ""
    for leg in reversed(legs):
        if not leg.get("walking"):
            final_dest = _get_direction(leg)
            break
    # Shorten destination: remove "(Westf)", "(Ruhr)" etc. for display
    import re
    final_dest = re.sub(r'\s*\([^)]*\)\s*', ' ', final_dest).strip()
    if len(final_dest) > 22:
        final_dest = final_dest[:20] + ".."

    # Transfers
    num_transfers = sum(1 for leg in legs if not leg.get("walking")) - 1
    transfer_info = ""
    if num_transfers > 0:
        transfer_info = f"  ·  {num_transfers}x umst."

    # Platforms
    dep_gl = _get_platform(first_leg, mode="departure")
    arr_gl = _get_platform(last_leg, mode="arrival")
    gl_str = ""
    if dep_gl and arr_gl:
        gl_str = f"Gl. {dep_gl}→{arr_gl}"
    elif dep_gl:
        gl_str = f"Gl. {dep_gl}"

    # Delay / status
    delays = []
    cancelled = False
    for leg in legs:
        if leg.get("walking"):
            continue
        delay_val = leg.get("departureDelay") or leg.get("delay") or 0
        if delay_val:
            delays.append(delay_val)
        if leg.get("cancelled"):
            cancelled = True

    if cancelled:
        status_icon = "❌ AUSFALL"
    elif delays:
        max_delay = max(delays)
        if max_delay >= 60:
            status_icon = f"⚠️ +{max_delay // 60}min"
        elif max_delay > 0:
            status_icon = f"⚠️ +{max_delay}min"
        else:
            status_icon = "✅"
    else:
        status_icon = "✅"

    # Remarks — filter by relevance (time window + stations + downstream filter)
    journey_start = _get_journey_dep_dt(journey)
    last_arr_str = last_leg.get("arrival") or last_leg.get("plannedArrival")
    journey_end: datetime | None = None
    if last_arr_str:
        try:
            journey_end = datetime.fromisoformat(last_arr_str)
        except (ValueError, TypeError):
            journey_end = None
    journey_stations = _collect_journey_stations(journey)
    # Final destination of the user's journey = last leg's destination
    final_destination = (last_leg.get("destination") or {}).get("name", "")

    remark_line = ""
    for leg in legs:
        for r in leg.get("remarks", []):
            rtype = r.get("type", "")
            text = r.get("text", r.get("summary", ""))
            if not text or text.startswith("$") or text.startswith('"$') or len(text) < 5:
                continue
            if rtype not in ("warning", "status"):
                continue
            # Relevance filter: time window + station match + downstream filter
            if not _is_remark_relevant(
                r, journey_start, journey_end, journey_stations,
                final_destination=final_destination,
            ):
                continue
            remark_line = f"\n   ⚠️ {_smart_truncate(text)}"
            break
        if remark_line:
            break

    # Build beautiful row — no per-row marker, chronological order + prefix line
    # handles "earlier" semantics at the caller level
    line1 = f"🚆 {dep_time} → {arr_time}  {trains} nach {final_dest}"
    line2_parts = [duration]
    if gl_str:
        line2_parts.append(gl_str)
    line2_parts.append(status_icon)
    line2 = f"   {' · '.join(line2_parts)}{transfer_info}"

    return line1 + "\n" + line2 + remark_line


def _get_journey_dep_dt(journey: dict) -> datetime | None:
    """Extract departure datetime from a journey for sorting/filtering."""
    legs = journey.get("legs", [])
    if not legs:
        return None
    dep_str = legs[0].get("departure") or legs[0].get("plannedDeparture")
    if not dep_str:
        return None
    try:
        return datetime.fromisoformat(dep_str)
    except (ValueError, TypeError):
        return None


def _parse_departure(departure: str | None) -> datetime | None:
    """Parse departure string to a timezone-aware datetime.

    Handles:
      - Full ISO: '2026-04-16T06:30:00+02:00'
      - Date + Time: '2026-04-16 06:30'
      - Time only: '06:30' (assumes today, or tomorrow if time already passed)
    """
    if not departure:
        return None

    now = datetime.now(TZ_BERLIN)

    # Try full ISO first
    try:
        dt = datetime.fromisoformat(departure)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=TZ_BERLIN)
        return dt
    except (ValueError, TypeError):
        pass

    # Try "HH:MM" or "H:MM" format
    import re
    time_match = re.match(r'^(\d{1,2}):(\d{2})$', departure.strip())
    if time_match:
        h, m = int(time_match.group(1)), int(time_match.group(2))
        dt = now.replace(hour=h, minute=m, second=0, microsecond=0)
        # If the time already passed today, use tomorrow
        if dt < now:
            dt += timedelta(days=1)
        return dt

    # Try "YYYY-MM-DD HH:MM" format
    dt_match = re.match(r'^(\d{4}-\d{2}-\d{2})\s+(\d{1,2}):(\d{2})$', departure.strip())
    if dt_match:
        try:
            date_part = datetime.strptime(dt_match.group(1), "%Y-%m-%d")
            dt = date_part.replace(
                hour=int(dt_match.group(2)),
                minute=int(dt_match.group(3)),
                tzinfo=TZ_BERLIN,
            )
            return dt
        except ValueError:
            pass

    return None


# ── Tool 1: db_search_connections ─────────────────────────────────────

@mcp.tool(
    description="Sucht Verbindungen von A nach B (Zug, S-Bahn, U-Bahn, Tram, Bus). "
    "Unterstuetzt Bahnhoefe, Haltestellen, Adressen und Orte (z.B. 'Am Rathaus 15, 45468 Muelheim' oder 'Otto-Pankok-Schule'). "
    "Zeigt 1 fruehere + 4 spaetere Verbindungen ab der gewuenschten Zeit, "
    "kompakt mit Gleis, Dauer und Verspaetung. "
    "WICHTIG: departure MUSS als volle ISO-DateTime mit Datum uebergeben werden, z.B. '2026-04-16T06:30:00+02:00'. "
    "Bei 'morgen'/'uebermorgen' IMMER zuerst mit dem time-MCP die aktuelle Zeit holen und Datum korrekt berechnen!"
)
async def db_search_connections(
    from_station: str,
    to_station: str,
    departure: str | None = None,
    arrival: str | None = None,
    results: int = 4,
    transfers: int | None = None,
    regional_only: bool = False,
) -> str:
    """Search connections A->B. Shows 1 earlier + 4 later connections around the requested time."""
    try:
        from_result = await rest_client.resolve_location(from_station)
        if not from_result.get("ok"):
            return _fmt_error(from_result, context=f"resolve_location:{from_station}")
        from_loc = from_result["data"]

        to_result = await rest_client.resolve_location(to_station)
        if not to_result.get("ok"):
            return _fmt_error(to_result, context=f"resolve_location:{to_station}")
        to_loc = to_result["data"]

        requested_dt: datetime | None = None

        # Parse the requested departure time
        if departure and not arrival:
            requested_dt = _parse_departure(departure)
            if requested_dt:
                departure = requested_dt.isoformat()

        if requested_dt:
            # Smart split via TWO queries:
            # - Query 1: small backward window for 1 "before" journey
            # - Query 2: at requested time for 4 "after" journeys
            # Separate queries avoid the "HAFAS returns 10 locals all before
            # requested_dt" bug that left the 'after' bucket empty.

            # "After" query: from the requested time forward
            after_result = await rest_client.journeys(
                from_loc, to_loc,
                departure=requested_dt.isoformat(),
                results=5,
                transfers=transfers,
                regional_only=regional_only,
            )
            if not after_result.get("ok"):
                return _fmt_error(after_result, context="journeys:after")
            after_journeys = after_result["data"].get("journeys", [])
            # Strictly filter: only journeys at/after requested time
            after = [
                j for j in after_journeys
                if (_get_journey_dep_dt(j) or requested_dt) >= requested_dt
            ][:4]

            # "Before" query: from 20 min earlier, limited results
            earlier_dt = requested_dt - timedelta(minutes=20)
            before_result = await rest_client.journeys(
                from_loc, to_loc,
                departure=earlier_dt.isoformat(),
                results=4,
                transfers=transfers,
                regional_only=regional_only,
            )
            if before_result.get("ok"):
                before_journeys = before_result["data"].get("journeys", [])
                before = [
                    j for j in before_journeys
                    if (_get_journey_dep_dt(j) or requested_dt) < requested_dt
                ]
                # Dedupe: only keep 'before' journeys not already in 'after'
                after_refresh = {j.get("refreshToken") for j in after if j.get("refreshToken")}
                before = [j for j in before if j.get("refreshToken") not in after_refresh]
            else:
                # If before query fails, still show after journeys — don't
                # fail the whole tool call
                before = []
                log.warning(
                    "tool.before_query_failed",
                    error=before_result.get("error"),
                    context="search_connections",
                )

            selected_before = before[-1:] if before else []
            journeys = selected_before + after
        else:
            # Normal query (no time hint → let HAFAS pick)
            journey_result = await rest_client.journeys(
                from_loc, to_loc,
                departure=departure,
                arrival=arrival,
                results=5,
                transfers=transfers,
                regional_only=regional_only,
            )
            if not journey_result.get("ok"):
                return _fmt_error(journey_result, context="journeys:direct")
            data = journey_result["data"]
            journeys = data.get("journeys", [])[:5]
            requested_dt = None

        if not journeys:
            return f"Keine Verbindungen gefunden: {from_station} -> {to_station}"

        # Header — use resolved names for cleaner display
        from_name = from_loc.get("name", from_station) if isinstance(from_loc, dict) else from_station
        to_name = to_loc.get("name", to_station) if isinstance(to_loc, dict) else to_station
        req_time_str = requested_dt.astimezone(TZ_BERLIN).strftime("%H:%M") if requested_dt else ""
        first_dt = _get_journey_dep_dt(journeys[0])
        date_str = _german_date(first_dt) if first_dt else ""

        lines: list[str] = [f"🚆 {from_name} → {to_name}"]
        if date_str:
            lines.append(f"📅 {date_str}")
        lines.append("")

        # Format each journey — consistent layout: prefix line for earlier,
        # ━━━ separator always shown when requested_dt split is active
        separator_shown = False
        earlier_header_shown = False
        for journey in journeys:
            jdt = _get_journey_dep_dt(journey)
            is_earlier = bool(requested_dt and jdt and jdt < requested_dt)

            # Prefix line for earlier alternatives
            if is_earlier and not earlier_header_shown:
                lines.append("↩ frühere Alternativen:")
                earlier_header_shown = True

            # Separator between before/after (always shown when split applies)
            if requested_dt and not separator_shown and jdt and jdt >= requested_dt:
                lines.append(f"━━━ ab {req_time_str} ━━━━━━━━━━")
                separator_shown = True

            row = _format_journey_row(journey, is_earlier=is_earlier)
            lines.append(row)
            lines.append("")  # spacing between journeys

        return "\n".join(lines).rstrip()

    except Exception as e:
        log.exception("tool.search_connections_error")
        return f"Fehler bei Verbindungssuche: {e}"


# ── Tool 2: db_departures ────────────────────────────────────────────

@mcp.tool(
    description="Zeigt die Abfahrtstafel einer Station — Zuege, S-Bahn, U-Bahn, Tram, Bus mit Gleisen, Verspaetungen und Stoerungen."
)
async def db_departures(
    station: str,
    duration: int = 60,
    results: int = 15,
    only_trains: bool = False,
) -> str:
    """Show departures at a station (all transport types: ICE/IC/RE/RB/S-Bahn/U-Bahn/Tram/Bus)."""
    try:
        import re as _re
        try:
            station_id = await rest_client.resolve_station(station)
        except ValueError as ve:
            return f"⚠️ {ve}"

        dep_result = await rest_client.departures(
            station_id, duration=duration, results=results,
            include_local=not only_trains,
        )
        if not dep_result.get("ok"):
            return _fmt_error(dep_result, context=f"departures:{station}")
        deps = dep_result["data"]

        if not deps:
            return f"Keine Abfahrten gefunden: {station}"

        lines: list[str] = [
            f"🚉 Abfahrten {station}",
            f"⏱ Nächste {duration} Minuten",
            "",
        ]

        for dep in deps[:results]:
            dep_time = _format_time(dep.get("when") or dep.get("plannedWhen"))
            line_name = _get_line_name(dep)
            direction = _get_direction(dep)
            platform = _get_platform(dep)
            delay = _get_delay_info(dep)
            product = _get_product_type(dep)
            cancelled = dep.get("cancelled", False)

            # Shorten direction
            direction = _re.sub(r'\s*\([^)]*\)\s*', ' ', direction).strip()
            direction = _re.sub(r',\s+\S+$', '', direction)
            if len(direction) > 22:
                direction = direction[:20] + ".."

            # Status icon
            if cancelled:
                status = "❌"
            elif delay == "puenktlich":
                status = "✅"
            else:
                status = f"⚠️{delay}"

            # Product emoji
            product_emoji = {"S-Bahn": "🔵", "U-Bahn": "🟢", "Tram": "🟡", "Bus": "🚌", "RE": "🔴", "RB": "🔴", "ICE": "⚡", "IC": "⚡", "EC": "⚡"}.get(product, "🔷")

            gl_str = f"Gl.{platform}" if platform else ""

            lines.append(
                f"{product_emoji} {dep_time}  {line_name:<7} → {direction:<20} {gl_str:<5} {status}"
            )

            # Show disruption remarks
            remarks = _get_remarks(dep, max_remarks=1)
            for remark in remarks:
                lines.append(f"   ⚠️ {remark}")

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.departures_error")
        return f"Fehler bei Abfahrten: {e}"


# ── Tool 3: db_arrivals ──────────────────────────────────────────────

@mcp.tool(
    description="Zeigt die Ankunftstafel einer Station — alle Verkehrsmittel inkl. Nahverkehr."
)
async def db_arrivals(
    station: str,
    duration: int = 60,
    results: int = 15,
    only_trains: bool = False,
) -> str:
    """Show arrivals at a station (all transport types)."""
    try:
        try:
            station_id = await rest_client.resolve_station(station)
        except ValueError as ve:
            return f"⚠️ {ve}"

        arr_result = await rest_client.arrivals(
            station_id, duration=duration, results=results,
            include_local=not only_trains,
        )
        if not arr_result.get("ok"):
            return _fmt_error(arr_result, context=f"arrivals:{station}")
        arrs = arr_result["data"]

        if not arrs:
            return f"Keine Ankuenfte gefunden: {station}"

        import re as _re
        lines: list[str] = [
            f"🚉 Ankuenfte {station}",
            f"⏱ Nächste {duration} Minuten",
            "",
        ]

        for arr in arrs[:results]:
            arr_time = _format_time(arr.get("when") or arr.get("plannedWhen"))
            line_name = _get_line_name(arr)
            origin = arr.get("provenance") or (arr.get("origin") or {}).get("name", "?")
            platform = _get_platform(arr)
            delay = _get_delay_info(arr)
            product = _get_product_type(arr)
            cancelled = arr.get("cancelled", False)

            origin = _re.sub(r'\s*\([^)]*\)\s*', ' ', origin).strip()
            if len(origin) > 22:
                origin = origin[:20] + ".."

            if cancelled:
                status = "❌"
            elif delay == "puenktlich":
                status = "✅"
            else:
                status = f"⚠️{delay}"

            product_emoji = {"S-Bahn": "🔵", "U-Bahn": "🟢", "Tram": "🟡", "Bus": "🚌", "RE": "🔴", "RB": "🔴", "ICE": "⚡", "IC": "⚡"}.get(product, "🔷")
            gl_str = f"Gl.{platform}" if platform else ""

            lines.append(
                f"{product_emoji} {arr_time}  {line_name:<7} aus {origin:<20} {gl_str:<5} {status}"
            )

            remarks = _get_remarks(arr, max_remarks=1)
            for remark in remarks:
                lines.append(f"   ⚠️ {remark}")

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.arrivals_error")
        return f"Fehler bei Ankuenften: {e}"


# ── Tool 4: db_find_station ──────────────────────────────────────────

@mcp.tool(
    description="Sucht Bahnhoefe, Haltestellen, Adressen und Orte (inkl. U-Bahn, Tram, Bus-Haltestellen, Strassenadressen, Schulen, POIs)."
)
async def db_find_station(
    query: str,
    results: int = 5,
    include_addresses: bool = False,
) -> str:
    """Search for stations by name (includes local transport stops). Set include_addresses=True for street addresses and POIs."""
    try:
        loc_result = await rest_client.locations(
            query, results=results,
            addresses=include_addresses, poi=include_addresses,
        )
        if not loc_result.get("ok"):
            return _fmt_error(loc_result, context=f"locations:{query}")
        locations = loc_result["data"]

        if not locations:
            return f"Keine Stationen gefunden: {query}"

        lines: list[str] = [f"Stationen fuer '{query}':\n"]

        for loc in locations[:results]:
            name = loc.get("name", "?")
            loc_id = loc.get("id", "?")
            lat = loc.get("location", {}).get("latitude", "?")
            lon = loc.get("location", {}).get("longitude", "?")

            products = loc.get("products", {})
            active = [k for k, v in products.items() if v] if isinstance(products, dict) else []
            products_str = ", ".join(active) if active else "-"

            lines.append(f"- {name} (ID: {loc_id})")
            lines.append(f"  Koordinaten: {lat}, {lon} | Produkte: {products_str}")

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.find_station_error")
        return f"Fehler bei Stationssuche: {e}"


# ── Tool 5: db_nearby_stations ───────────────────────────────────────

@mcp.tool(
    description="Findet Bahnhoefe in der Naehe einer GPS-Position."
)
async def db_nearby_stations(
    latitude: float,
    longitude: float,
    distance: int = 1000,
    results: int = 5,
) -> str:
    """Find stations near a GPS position."""
    try:
        nearby_result = await rest_client.nearby(
            latitude, longitude, distance=distance, results=results
        )
        if not nearby_result.get("ok"):
            return _fmt_error(nearby_result, context=f"nearby:{latitude},{longitude}")
        locations = nearby_result["data"]

        if not locations:
            return f"Keine Stationen im Umkreis von {distance}m gefunden."

        lines: list[str] = [f"Stationen im Umkreis von {distance}m:\n"]

        for loc in locations[:results]:
            name = loc.get("name", "?")
            loc_id = loc.get("id", "?")
            dist = loc.get("distance", "?")
            lines.append(f"- {name} (ID: {loc_id}, {dist}m entfernt)")

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.nearby_stations_error")
        return f"Fehler bei Umkreissuche: {e}"


# ── Tool 6: db_trip_details ──────────────────────────────────────────

@mcp.tool(
    description="Zeigt alle Halte und Details einer bestimmten Zugfahrt."
)
async def db_trip_details(
    trip_id: str,
) -> str:
    """Show details of a specific trip."""
    try:
        trip_result = await rest_client.trip(trip_id)
        if not trip_result.get("ok"):
            return _fmt_error(trip_result, context=f"trip:{trip_id}")
        data = trip_result["data"]

        trip = data.get("trip", data)
        line_name = _get_line_name(trip)
        origin = trip.get("origin", {}).get("name", "?")
        destination = trip.get("destination", {}).get("name", "?")

        lines: list[str] = [f"Fahrt: {line_name} ({origin} -> {destination})\n"]

        stopovers = trip.get("stopovers", [])
        for stop in stopovers:
            stop_name = stop.get("stop", {}).get("name", "?")
            arr = _format_time(stop.get("arrival") or stop.get("plannedArrival"))
            dep = _format_time(stop.get("departure") or stop.get("plannedDeparture"))
            platform = stop.get("platform", stop.get("plannedPlatform", ""))
            delay_arr = stop.get("arrivalDelay", 0) or 0
            delay_dep = stop.get("departureDelay", 0) or 0

            time_str = ""
            if arr and arr != "?":
                time_str += f"an {arr}"
            if dep and dep != "?":
                time_str += f" ab {dep}" if time_str else f"ab {dep}"

            delay_str = ""
            max_delay = max(delay_arr, delay_dep)
            if max_delay > 0:
                delay_str = f" (+{max_delay // 60} min)" if max_delay >= 60 else f" (+{max_delay} min)"

            platform_str = f"Gl. {platform}" if platform else ""
            cancelled = stop.get("cancelled", False)
            cancel_str = " [AUSFALL]" if cancelled else ""

            lines.append(f"  {stop_name:<30} {time_str:<15} {platform_str:<8} {delay_str}{cancel_str}")

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.trip_details_error")
        return f"Fehler bei Fahrtdetails: {e}"


# ── Tool 7: db_pendler_check ─────────────────────────────────────────

@mcp.tool(
    description="Schnellcheck fuer Majids Pendlerstrecke Muelheim Hbf <-> Dortmund Hbf. "
    "Zeigt 1 fruehere + 3 spaetere Verbindungen. "
    "departure als volle ISO-DateTime, z.B. '2026-04-16T06:30:00+02:00'. Bei 'morgen' Datum von morgen berechnen!"
)
async def db_pendler_check(
    direction: str = "hin",
    departure: str | None = None,
) -> str:
    """Quick check for the commute Muelheim <-> Dortmund (1 earlier + 3 later)."""
    try:
        if direction.lower() in ("hin", "hinfahrt", "muelheim", "arbeit"):
            from_name = "Muelheim Hbf"
            to_name = "Dortmund Hbf"
            from_id = MUELHEIM_EVA
            to_id = DORTMUND_EVA
        else:
            from_name = "Dortmund Hbf"
            to_name = "Muelheim Hbf"
            from_id = DORTMUND_EVA
            to_id = MUELHEIM_EVA

        requested_dt: datetime | None = None

        if departure:
            requested_dt = _parse_departure(departure)
            if requested_dt:
                earlier_dt = requested_dt - timedelta(minutes=45)
                earlier_departure = earlier_dt.isoformat()
            else:
                earlier_departure = departure
        else:
            earlier_departure = departure

        if requested_dt:
            journey_result = await rest_client.journeys(
                from_id, to_id, departure=earlier_departure, results=10
            )
            if not journey_result.get("ok"):
                return _fmt_error(journey_result, context="pendler:smart_split")
            data = journey_result["data"]
            all_journeys = data.get("journeys", [])
            before = [j for j in all_journeys if (_get_journey_dep_dt(j) or requested_dt) < requested_dt]
            after = [j for j in all_journeys if (_get_journey_dep_dt(j) or requested_dt) >= requested_dt]
            journeys = before[-1:] + after[:4]
        else:
            journey_result = await rest_client.journeys(
                from_id, to_id, departure=departure, results=5
            )
            if not journey_result.get("ok"):
                return _fmt_error(journey_result, context="pendler:direct")
            data = journey_result["data"]
            journeys = data.get("journeys", [])[:5]

        if not journeys:
            return f"Keine Verbindungen: {from_name} -> {to_name}"

        # Header
        first_dt = _get_journey_dep_dt(journeys[0])
        date_str = _german_date(first_dt) if first_dt else ""

        lines: list[str] = [f"🚆 {from_name} → {to_name}"]
        if date_str:
            lines.append(f"📅 {date_str}")
        lines.append("")

        req_time_str = requested_dt.astimezone(TZ_BERLIN).strftime("%H:%M") if requested_dt else ""
        separator_shown = False
        earlier_header_shown = False

        for journey in journeys:
            jdt = _get_journey_dep_dt(journey)
            is_earlier = bool(requested_dt and jdt and jdt < requested_dt)

            if is_earlier and not earlier_header_shown:
                lines.append("↩ frühere Alternativen:")
                earlier_header_shown = True

            if requested_dt and not separator_shown and jdt and jdt >= requested_dt:
                lines.append(f"━━━ ab {req_time_str} ━━━━━━━━━━")
                separator_shown = True

            lines.append(_format_journey_row(journey, is_earlier=is_earlier))
            lines.append("")

        return "\n".join(lines).rstrip()

    except Exception as e:
        log.exception("tool.pendler_check_error")
        return f"Fehler beim Pendler-Check: {e}"


# ── Tool 8: db_train_live_status ─────────────────────────────────────

@mcp.tool(
    description="Zeigt den LIVE-Status eines bestimmten Zuges (Verspaetung, aktuelles Gleis inkl. "
    "Gleisaenderungen, naechster Halt). Nutze dies bei Fragen wie 'wo ist die RE1', "
    "'Gleis der S1 nochmal pruefen', 'aktuelle Verspaetung U18'. "
    "line: Zug-Linie (z.B. 'RE1', 'S1', 'U18'). "
    "station: Station fuer den Live-Snapshot (default 'Mülheim Hbf'). "
    "Greift auf /trips/:id zu — die einzige Datenquelle fuer Live-Position und Live-Gleis."
)
async def db_train_live_status(
    line: str,
    station: str = "Mülheim Hbf",
    duration: int = 120,
) -> str:
    """Live status for a specific train line at a station.

    Flow: resolve station → departures filtered by line → pick first match →
    /trips/:id for full live details (delay, current platform, next stop).
    """
    try:
        # Resolve station
        try:
            station_id = await rest_client.resolve_station(station)
        except ValueError as ve:
            return f"⚠️ {ve}"

        # Find departures matching the line
        dep_result = await rest_client.departures(
            station_id,
            duration=duration,
            results=20,
            line_name=line,
            include_local=True,
        )
        if not dep_result.get("ok"):
            return _fmt_error(dep_result, context=f"live_status:departures:{line}")
        deps = dep_result["data"]

        # Filter strictly by line name (line_name param may be fuzzy)
        matching = [d for d in deps
                    if d.get("line", {}).get("name", "").replace(" ", "").lower() ==
                       line.replace(" ", "").lower()]
        if not matching:
            return (
                f"⚠️ Keine aktuellen Abfahrten der Linie {line} an {station} in den "
                f"nächsten {duration} Minuten gefunden. Vielleicht läuft sie hier nicht "
                f"oder ist komplett ausgefallen."
            )

        # Pick the next departure
        next_dep = matching[0]
        trip_id = next_dep.get("tripId", "")
        if not trip_id:
            return f"⚠️ Keine Trip-ID für {line} an {station} verfügbar."

        # Fetch full live trip details
        trip_result = await rest_client.trip(trip_id)
        if not trip_result.get("ok"):
            # Fall back to just the departure info we have
            return _format_live_from_departure(next_dep, line, station)
        trip_data = trip_result["data"]
        trip = trip_data.get("trip", trip_data)

        return _format_live_status(trip, next_dep, line, station)

    except Exception as e:
        log.exception("tool.live_status_error")
        return f"⚠️ Fehler beim Live-Status für {line}: {e}"


def _format_live_status(trip: dict, dep: dict, line: str, station: str) -> str:
    """Format the live-status output for a specific train."""
    line_name = _get_line_name(trip) or line
    direction = _get_direction(trip) or _get_direction(dep)
    origin = (trip.get("origin") or {}).get("name", "?")
    destination = (trip.get("destination") or {}).get("name", direction)

    # Current vs planned time at our station
    planned_when = dep.get("plannedWhen")
    actual_when = trip.get("when") or trip.get("departure") or dep.get("when") or planned_when

    # Platform — prefer trip-level (more live)
    planned_platform = (trip.get("plannedPlatform")
                        or dep.get("plannedPlatform")
                        or "")
    actual_platform = (trip.get("platform")
                       or dep.get("platform")
                       or planned_platform)
    platform_changed = bool(
        planned_platform and actual_platform and planned_platform != actual_platform
    )

    # Delay (in seconds → minutes)
    delay_sec = trip.get("delay") or dep.get("delay") or 0
    delay_min = delay_sec // 60 if delay_sec else 0

    cancelled = trip.get("cancelled") or dep.get("cancelled") or False

    # Current location (if train is moving)
    cur_loc = trip.get("currentLocation", {})
    cur_lat = cur_loc.get("latitude") if isinstance(cur_loc, dict) else None
    cur_lon = cur_loc.get("longitude") if isinstance(cur_loc, dict) else None

    # Next stopover
    next_stop_info = ""
    stopovers = trip.get("stopovers", [])
    if stopovers:
        now = datetime.now(TZ_BERLIN)
        for sov in stopovers:
            sov_arr = sov.get("arrival") or sov.get("plannedArrival")
            if not sov_arr:
                continue
            try:
                sov_dt = datetime.fromisoformat(sov_arr)
                if sov_dt.astimezone(TZ_BERLIN) > now:
                    sov_name = sov.get("stop", {}).get("name", "?")
                    sov_time = _format_time(sov_arr)
                    sov_delay = (sov.get("arrivalDelay") or 0) // 60
                    delay_str = f" (+{sov_delay}min)" if sov_delay > 0 else ""
                    next_stop_info = f"{sov_name} — an {sov_time}{delay_str}"
                    break
            except (ValueError, TypeError):
                continue

    # Build output
    lines: list[str] = [f"🚆 LIVE-Status: {line_name} → {destination}"]
    lines.append(f"📍 Abfahrtsstation: {station}")
    lines.append("")

    # Times
    planned_str = _format_time(planned_when)
    actual_str = _format_time(actual_when)
    if cancelled:
        lines.append(f"❌ AUSFALL (planmäßig {planned_str})")
    elif delay_min >= 60:
        lines.append(f"⚠️ +{delay_min // 60}h{delay_min % 60:02d}min Verspätung "
                     f"(planmäßig {planned_str} → jetzt {actual_str})")
    elif delay_min > 0:
        lines.append(f"⚠️ +{delay_min} min Verspätung "
                     f"(planmäßig {planned_str} → jetzt {actual_str})")
    elif delay_min < 0:
        lines.append(f"✅ {delay_min} min früher (planmäßig {planned_str})")
    else:
        lines.append(f"✅ Pünktlich (planmäßig {planned_str})")

    # Platform
    if cancelled:
        pass  # no platform info for cancelled trains
    elif platform_changed:
        lines.append(f"🔀 Gleisänderung: {planned_platform} → **{actual_platform}**")
    elif actual_platform:
        lines.append(f"🛤 Gleis {actual_platform}")
    else:
        lines.append("🛤 Gleis noch nicht bekannt")

    # Next stop
    if next_stop_info:
        lines.append(f"➡️  Nächster Halt: {next_stop_info}")

    # Current position (if available)
    if cur_lat and cur_lon:
        lines.append(f"🗺 Position: {cur_lat:.4f}, {cur_lon:.4f}")

    return "\n".join(lines)


def _format_live_from_departure(dep: dict, line: str, station: str) -> str:
    """Fallback formatter if /trips/:id fails — uses only departure data."""
    line_name = _get_line_name(dep) or line
    direction = _get_direction(dep)
    planned_when = dep.get("plannedWhen")
    actual_when = dep.get("when") or planned_when
    planned_platform = dep.get("plannedPlatform", "") or ""
    actual_platform = dep.get("platform", "") or planned_platform
    platform_changed = bool(
        planned_platform and actual_platform and planned_platform != actual_platform
    )
    delay_sec = dep.get("delay") or 0
    delay_min = delay_sec // 60
    cancelled = dep.get("cancelled", False)

    lines = [f"🚆 {line_name} → {direction}"]
    lines.append(f"📍 Abfahrtsstation: {station} (nur Abfahrtsdaten, volle Trip-Info nicht abrufbar)")
    lines.append("")
    if cancelled:
        lines.append(f"❌ AUSFALL (planmäßig {_format_time(planned_when)})")
    elif delay_min > 0:
        lines.append(f"⚠️ +{delay_min} min Verspätung "
                     f"(planmäßig {_format_time(planned_when)} → jetzt {_format_time(actual_when)})")
    else:
        lines.append(f"✅ Pünktlich ({_format_time(actual_when)})")
    if platform_changed:
        lines.append(f"🔀 Gleisänderung: {planned_platform} → **{actual_platform}**")
    elif actual_platform:
        lines.append(f"🛤 Gleis {actual_platform}")
    return "\n".join(lines)


# ── Tool 9: db_nrw_stoerungen (zuginfo.nrw) ──────────────────────────

@mcp.tool(
    description="Zeigt aktuelle Stoerungen, Ausfaelle und Bauarbeiten im NRW-Nahverkehr (S-Bahn, RE, RB, U-Bahn, Tram). Daten von zuginfo.nrw."
)
async def db_nrw_stoerungen(
    linie: str | None = None,
) -> str:
    """Show current NRW rail/transit disruptions from zuginfo.nrw."""
    try:
        disruptions = await zuginfo_client.get_disruptions(line_filter=linie)

        if not disruptions:
            filter_hint = f" fuer {linie}" if linie else ""
            return f"Keine aktuellen Stoerungen in NRW{filter_hint} gefunden. (Daten von zuginfo.nrw)"

        header = f"NRW Stoerungen"
        if linie:
            header += f" (Filter: {linie})"
        lines: list[str] = [f"{header} — {len(disruptions)} Meldungen:\n"]

        for d in disruptions[:15]:
            line_name = d.get("line", "")
            title = d.get("title", "")
            desc = d.get("description", "")
            period = d.get("period", "")
            dtype = d.get("type", "")

            entry = f"- [{line_name}]" if line_name else "-"
            if title:
                entry += f" {title}"
            if period:
                entry += f" ({period})"
            lines.append(entry)

            if desc and desc != title:
                lines.append(f"  {desc[:200]}")

        lines.append("\nQuelle: zuginfo.nrw")
        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.nrw_stoerungen_error")
        return f"Fehler bei NRW-Stoerungen: {e}"


# ── Tool 9: db_disruptions (Timetable API — needs API keys) ──────────

if timetable_client.is_available:

    @mcp.tool(
        description="Zeigt aktuelle Stoerungen, Ausfaelle und Gleisaenderungen an einer Station."
    )
    async def db_disruptions(
        station: str,
    ) -> str:
        """Show current disruptions at a station."""
        try:
            # Resolve to EVA number if needed
            eva = station.strip()
            if not eva.isdigit():
                eva = await rest_client.resolve_station(station)

            disruptions = await timetable_client.get_disruptions(eva)

            if not disruptions:
                return f"Keine aktuellen Stoerungen an {station}."

            lines: list[str] = [f"Stoerungen an {station} ({len(disruptions)} Aenderungen):\n"]

            for d in disruptions[:20]:
                parts = [d.get("zug", "?"), d.get("typ", "")]
                if d.get("route"):
                    parts.append(f"-> {d['route']}")
                if d.get("status") == "AUSFALL":
                    parts.append("*** AUSFALL ***")
                else:
                    if d.get("verspaetung"):
                        parts.append(d["verspaetung"])
                    if d.get("neue_zeit"):
                        parts.append(f"(neu: {d['neue_zeit']})")
                    if d.get("neues_gleis"):
                        parts.append(f"Gleis: {d.get('plan_gleis', '?')} -> {d['neues_gleis']}")

                lines.append("- " + " | ".join(p for p in parts if p))

            return "\n".join(lines)

        except Exception as e:
            log.exception("tool.disruptions_error")
            return f"Fehler bei Stoerungen: {e}"

    # ── Tool 9: db_parking (BahnPark API) ─────────────────────────────

    @mcp.tool(
        description="Zeigt Parkplaetze und freie Plaetze am Bahnhof."
    )
    async def db_parking(
        station_name: str,
    ) -> str:
        """Show parking at a station."""
        try:
            parking = await timetable_client.get_parking(station_name)

            if not parking:
                return f"Keine Parkplatz-Informationen fuer {station_name}."

            lines: list[str] = [f"Parkplaetze {station_name}:\n"]

            for p in parking:
                name = p.get("name", "?")
                total = p.get("kapazitaet", "?")
                free = p.get("frei", "?")
                cat = p.get("kategorie", "")
                lines.append(f"- {name}: {free}/{total} frei ({cat})")

            return "\n".join(lines)

        except Exception as e:
            log.exception("tool.parking_error")
            return f"Fehler bei Parkplaetzen: {e}"

    # ── Tool 10: db_accessibility (FaSta API) ─────────────────────────

    @mcp.tool(
        description="Zeigt Aufzuege und Rolltreppen an einer Station und deren Status."
    )
    async def db_accessibility(
        station: str,
    ) -> str:
        """Show elevators and escalators at a station."""
        try:
            # Resolve station number (EVA number)
            station_nr = station.strip()
            if not station_nr.isdigit():
                station_nr = await rest_client.resolve_station(station)

            facilities = await timetable_client.get_accessibility(station_nr)

            if not facilities:
                return f"Keine Aufzug-/Rolltreppen-Daten fuer {station}."

            lines: list[str] = [f"Barrierefreiheit {station}:\n"]

            elevators = [f for f in facilities if f.get("typ", "").upper() in ("ELEVATOR", "AUFZUG")]
            escalators = [f for f in facilities if f.get("typ", "").upper() in ("ESCALATOR", "ROLLTREPPE")]
            others = [f for f in facilities if f not in elevators and f not in escalators]

            if elevators:
                lines.append(f"Aufzuege ({len(elevators)}):")
                for f in elevators:
                    status = f.get("status", "?")
                    desc = f.get("beschreibung", "")
                    icon = "OK" if status == "ACTIVE" else "DEFEKT"
                    lines.append(f"  [{icon}] {desc}")

            if escalators:
                lines.append(f"\nRolltreppen ({len(escalators)}):")
                for f in escalators:
                    status = f.get("status", "?")
                    desc = f.get("beschreibung", "")
                    icon = "OK" if status == "ACTIVE" else "DEFEKT"
                    lines.append(f"  [{icon}] {desc}")

            if others:
                lines.append(f"\nSonstige ({len(others)}):")
                for f in others:
                    lines.append(f"  [{f.get('status', '?')}] {f.get('typ', '?')}: {f.get('beschreibung', '')}")

            return "\n".join(lines)

        except Exception as e:
            log.exception("tool.accessibility_error")
            return f"Fehler bei Barrierefreiheit: {e}"

    log.info("db.timetable_tools_registered")
else:
    log.info("db.timetable_tools_skipped", reason="no API keys configured")


# ── Entrypoint ────────────────────────────────────────────────────────

if __name__ == "__main__":
    mcp.run(transport="stdio")

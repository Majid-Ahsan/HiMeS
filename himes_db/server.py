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

log = structlog.get_logger("himes_db")

# ── Clients ───────────────────────────────────────────────────────────

rest_client = DBRestClient()
timetable_client = DBTimetableClient(
    client_id=os.getenv("DB_API_CLIENT_ID", ""),
    client_secret=os.getenv("DB_API_CLIENT_SECRET", ""),
)

# ── FastMCP Server ────────────────────────────────────────────────────

mcp = FastMCP("deutsche-bahn")

# ── Constants ─────────────────────────────────────────────────────────

MUELHEIM_EVA = "8000259"
DORTMUND_EVA = "8000080"
TZ_BERLIN = ZoneInfo("Europe/Berlin")


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


def _get_platform(item: dict) -> str:
    """Extract platform info."""
    return str(item.get("platform", item.get("plannedPlatform", "?")))


def _get_direction(item: dict) -> str:
    """Extract direction/destination."""
    return item.get("direction", item.get("destination", {}).get("name", "?"))


# ── Tool 1: db_search_connections ─────────────────────────────────────

@mcp.tool(
    description="Sucht Zugverbindungen von A nach B. Zeigt Abfahrt, Ankunft, Dauer, Umstiege, Gleis und Verspaetung."
)
async def db_search_connections(
    from_station: str,
    to_station: str,
    departure: str | None = None,
    arrival: str | None = None,
    results: int = 3,
    transfers: int | None = None,
    regional_only: bool = False,
) -> str:
    """Search train connections from A to B."""
    try:
        from_id = await rest_client.resolve_station(from_station)
        to_id = await rest_client.resolve_station(to_station)

        data = await rest_client.journeys(
            from_id, to_id,
            departure=departure,
            arrival=arrival,
            results=results,
            transfers=transfers,
            regional_only=regional_only,
        )

        journeys = data.get("journeys", [])
        if not journeys:
            return f"Keine Verbindungen gefunden: {from_station} -> {to_station}"

        lines: list[str] = [f"Verbindung: {from_station} -> {to_station}\n"]

        for i, journey in enumerate(journeys[:results], 1):
            legs = journey.get("legs", [])
            if not legs:
                continue

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
                        duration = f"{total_min // 60}h {total_min % 60}min"
                    else:
                        duration = f"{total_min} min"
                except (ValueError, TypeError):
                    pass

            num_transfers = len(legs) - 1
            transfer_str = "direkt" if num_transfers == 0 else f"{num_transfers} Umstieg{'e' if num_transfers > 1 else ''}"

            # Train names
            train_names = []
            for leg in legs:
                if leg.get("walking"):
                    train_names.append("Fussweg")
                else:
                    train_names.append(_get_line_name(leg))

            trains = " -> ".join(train_names)
            lines.append(f"{i}. {trains} ({dep_time} -> {arr_time}, {duration}, {transfer_str})")

            # Platform + delay per leg
            leg_details = []
            for leg in legs:
                if leg.get("walking"):
                    continue
                dep_platform = _get_platform(leg)
                delay = _get_delay_info(leg, "plannedDeparture", "departure")
                leg_details.append(f"Gl. {dep_platform}")
                if delay and delay != "puenktlich":
                    leg_details.append(delay)

            arr_platform = _get_platform(last_leg)
            arr_delay = _get_delay_info(last_leg, "plannedArrival", "arrival")

            detail = f"   {' -> '.join(leg_details)} -> Gl. {arr_platform}"
            if arr_delay:
                detail += f" | {arr_delay}"
            lines.append(detail)

            # Remarks (disruptions)
            remarks = journey.get("remarks", [])
            for remark in remarks[:2]:
                remark_text = remark.get("text", "")
                if remark_text:
                    lines.append(f"   Hinweis: {remark_text[:100]}")

            lines.append("")

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.search_connections_error")
        return f"Fehler bei Verbindungssuche: {e}"


# ── Tool 2: db_departures ────────────────────────────────────────────

@mcp.tool(
    description="Zeigt die Abfahrtstafel einer Station mit Zuegen, Gleisen und Verspaetungen."
)
async def db_departures(
    station: str,
    duration: int = 60,
    results: int = 10,
) -> str:
    """Show departures at a station."""
    try:
        station_id = await rest_client.resolve_station(station)
        deps = await rest_client.departures(station_id, duration=duration, results=results)

        if not deps:
            return f"Keine Abfahrten gefunden: {station}"

        lines: list[str] = [f"Abfahrten {station} (naechste {duration} min)\n"]

        for dep in deps[:results]:
            dep_time = _format_time(dep.get("when") or dep.get("plannedWhen"))
            line_name = _get_line_name(dep)
            direction = _get_direction(dep)
            platform = _get_platform(dep)
            delay = _get_delay_info(dep)

            lines.append(
                f"{dep_time}  {line_name:<8} -> {direction:<25} Gl. {platform:<4} {delay}"
            )

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.departures_error")
        return f"Fehler bei Abfahrten: {e}"


# ── Tool 3: db_arrivals ──────────────────────────────────────────────

@mcp.tool(
    description="Zeigt die Ankunftstafel einer Station."
)
async def db_arrivals(
    station: str,
    duration: int = 60,
    results: int = 10,
) -> str:
    """Show arrivals at a station."""
    try:
        station_id = await rest_client.resolve_station(station)
        arrs = await rest_client.arrivals(station_id, duration=duration, results=results)

        if not arrs:
            return f"Keine Ankuenfte gefunden: {station}"

        lines: list[str] = [f"Ankuenfte {station} (naechste {duration} min)\n"]

        for arr in arrs[:results]:
            arr_time = _format_time(arr.get("when") or arr.get("plannedWhen"))
            line_name = _get_line_name(arr)
            origin = arr.get("provenance", arr.get("origin", {}).get("name", "?"))
            platform = _get_platform(arr)
            delay = _get_delay_info(arr)

            lines.append(
                f"{arr_time}  {line_name:<8} aus {origin:<25} Gl. {platform:<4} {delay}"
            )

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.arrivals_error")
        return f"Fehler bei Ankuenften: {e}"


# ── Tool 4: db_find_station ──────────────────────────────────────────

@mcp.tool(
    description="Sucht Bahnhoefe und Haltestellen nach Name."
)
async def db_find_station(
    query: str,
    results: int = 5,
) -> str:
    """Search for stations by name."""
    try:
        locations = await rest_client.locations(query, results=results)

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
        locations = await rest_client.nearby(latitude, longitude, distance=distance, results=results)

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
        data = await rest_client.trip(trip_id)

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
    description="Schnellcheck fuer Majids Pendlerstrecke Muelheim Hbf <-> Dortmund Hbf."
)
async def db_pendler_check(
    direction: str = "hin",
    departure: str | None = None,
) -> str:
    """Quick check for the commute Muelheim <-> Dortmund."""
    try:
        if direction.lower() in ("hin", "hinfahrt", "muelheim", "arbeit"):
            from_name = "Muelheim (Ruhr) Hbf"
            to_name = "Dortmund Hbf"
            from_id = MUELHEIM_EVA
            to_id = DORTMUND_EVA
        else:
            from_name = "Dortmund Hbf"
            to_name = "Muelheim (Ruhr) Hbf"
            from_id = DORTMUND_EVA
            to_id = MUELHEIM_EVA

        data = await rest_client.journeys(
            from_id, to_id,
            departure=departure,
            results=3,
        )

        journeys = data.get("journeys", [])
        if not journeys:
            return f"Keine Verbindungen: {from_name} -> {to_name}"

        lines: list[str] = [f"Pendler-Check: {from_name} -> {to_name}\n"]

        for i, journey in enumerate(journeys[:3], 1):
            legs = journey.get("legs", [])
            if not legs:
                continue

            first_leg = legs[0]
            last_leg = legs[-1]
            dep_time = _format_time(first_leg.get("departure"))
            arr_time = _format_time(last_leg.get("arrival"))

            dep_dt = first_leg.get("departure")
            arr_dt = last_leg.get("arrival")
            duration = ""
            if dep_dt and arr_dt:
                try:
                    d = datetime.fromisoformat(arr_dt) - datetime.fromisoformat(dep_dt)
                    duration = f"{int(d.total_seconds() / 60)} min"
                except (ValueError, TypeError):
                    pass

            num_transfers = len(legs) - 1
            transfer_str = "direkt" if num_transfers == 0 else f"{num_transfers}x umst."

            trains = " -> ".join(
                _get_line_name(leg) for leg in legs if not leg.get("walking")
            )
            dep_platform = _get_platform(first_leg)
            delay = _get_delay_info(first_leg, "plannedDeparture", "departure")

            lines.append(
                f"{i}. {trains} ({dep_time} -> {arr_time}, {duration}, {transfer_str}) "
                f"Gl. {dep_platform} | {delay}"
            )

        return "\n".join(lines)

    except Exception as e:
        log.exception("tool.pendler_check_error")
        return f"Fehler beim Pendler-Check: {e}"


# ── Tool 8: db_disruptions (Timetable API) ───────────────────────────

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

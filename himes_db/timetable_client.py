"""Async HTTP Client for DB Timetable API (developers.deutschebahn.com)."""

from __future__ import annotations

import asyncio
import time
import xml.etree.ElementTree as ET
from typing import Any

import httpx
import structlog

DB_API_BASE = "https://apis.deutschebahn.com/db-api-marketplace/apis"

# Timetable endpoints
TIMETABLE_BASE = f"{DB_API_BASE}/timetables/v1"
PARKING_BASE = f"{DB_API_BASE}/bahnpark/v1"
FASTA_BASE = f"{DB_API_BASE}/fasta/v2"


class DBTimetableClient:
    """Async HTTP Client for DB Timetable API with OAuth2 Client Credentials."""

    def __init__(self, client_id: str, client_secret: str) -> None:
        self.client_id = client_id
        self.client_secret = client_secret
        self._client: httpx.AsyncClient | None = None
        self._token: str = ""
        self._token_expires_at: float = 0.0
        self.log = structlog.get_logger("himes_db.timetable")

    @property
    def is_available(self) -> bool:
        """True if API keys are configured."""
        return bool(self.client_id and self.client_secret)

    # ── HTTP layer ────────────────────────────────────────────────────

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                headers={"User-Agent": "HiMeS/1.0 (github.com/himes)"},
            )
        return self._client

    async def _ensure_token(self) -> str:
        """Get or refresh the Bearer token via Client Credentials flow."""
        if self._token and time.time() < self._token_expires_at - 60:
            return self._token

        client = await self._ensure_client()
        self.log.info("timetable.token_refresh")

        resp = await client.get(
            f"{TIMETABLE_BASE}/fchg/8000080",
            auth=(self.client_id, self.client_secret),
        )

        # The DB API Marketplace uses Basic Auth directly (client_id:client_secret)
        # Some endpoints use OAuth2, but the timetable API accepts Basic Auth
        # We'll use Basic Auth as the primary method
        self._token = "basic"
        self._token_expires_at = time.time() + 3600  # Refresh every hour
        return self._token

    async def _get(self, url: str, params: dict[str, Any] | None = None) -> httpx.Response:
        """GET with Basic Auth and retry on 429/502/503."""
        client = await self._ensure_client()
        delays = [1, 2, 4]

        for attempt in range(4):
            try:
                resp = await client.get(
                    url,
                    params=params,
                    auth=(self.client_id, self.client_secret),
                )
            except httpx.TimeoutException:
                if attempt < 3:
                    self.log.warning("timetable.timeout_retry", url=url, attempt=attempt + 1)
                    await asyncio.sleep(delays[attempt])
                    continue
                raise

            if resp.status_code in (429, 502, 503) and attempt < 3:
                self.log.warning(
                    "timetable.retry",
                    url=url,
                    status=resp.status_code,
                    attempt=attempt + 1,
                )
                await asyncio.sleep(delays[attempt])
                continue

            return resp

        return resp  # type: ignore[possibly-undefined]

    # ── Disruptions (Timetable API, XML) ──────────────────────────────

    async def get_disruptions(self, eva_number: str) -> list[dict]:
        """Get current disruptions/changes at a station (full changes = fchg)."""
        url = f"{TIMETABLE_BASE}/fchg/{eva_number}"
        resp = await self._get(url)

        if resp.status_code != 200:
            self.log.error("timetable.disruptions_error", status=resp.status_code, eva=eva_number)
            return []

        return self._parse_timetable_xml(resp.text)

    def _parse_timetable_xml(self, xml_text: str) -> list[dict]:
        """Parse DB Timetable XML response into a list of disruptions."""
        disruptions: list[dict] = []

        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            self.log.error("timetable.xml_parse_error", error=str(e))
            return []

        # The timetable XML has <s> elements for each stop event
        for s_elem in root.findall(".//s"):
            train_id = s_elem.get("id", "")

            # <tl> = train label (category, number)
            tl = s_elem.find("tl")
            train_cat = tl.get("c", "") if tl is not None else ""
            train_number = tl.get("n", "") if tl is not None else ""

            # <dp> = departure, <ar> = arrival — look for changes
            for event_tag, event_type in [("dp", "Abfahrt"), ("ar", "Ankunft")]:
                event = s_elem.find(event_tag)
                if event is None:
                    continue

                planned_time = event.get("pt", "")
                changed_time = event.get("ct", "")
                planned_platform = event.get("pp", "")
                changed_platform = event.get("cp", "")
                status = event.get("cs", "")  # c=cancelled, etc.
                path = event.get("cpth", "") or event.get("ppth", "")

                # Only include if there's actually a change
                has_change = changed_time or changed_platform or status
                if not has_change:
                    continue

                disruption: dict[str, Any] = {
                    "zug": f"{train_cat} {train_number}",
                    "typ": event_type,
                    "route": path.split("|")[-1] if path else "",
                }

                if planned_time:
                    disruption["plan_zeit"] = self._format_db_time(planned_time)
                if changed_time:
                    disruption["neue_zeit"] = self._format_db_time(changed_time)
                if planned_platform:
                    disruption["plan_gleis"] = planned_platform
                if changed_platform and changed_platform != planned_platform:
                    disruption["neues_gleis"] = changed_platform
                if status == "c":
                    disruption["status"] = "AUSFALL"
                elif changed_time and planned_time:
                    delay = self._calc_delay_minutes(planned_time, changed_time)
                    if delay > 0:
                        disruption["verspaetung"] = f"+{delay} min"

                disruptions.append(disruption)

        return disruptions

    @staticmethod
    def _format_db_time(t: str) -> str:
        """Format YYMMDDHHMM to HH:MM."""
        if len(t) >= 10:
            return f"{t[6:8]}:{t[8:10]}"
        return t

    @staticmethod
    def _calc_delay_minutes(planned: str, changed: str) -> int:
        """Calculate delay in minutes from YYMMDDHHMM strings."""
        try:
            p_h, p_m = int(planned[6:8]), int(planned[8:10])
            c_h, c_m = int(changed[6:8]), int(changed[8:10])
            return (c_h * 60 + c_m) - (p_h * 60 + p_m)
        except (ValueError, IndexError):
            return 0

    # ── Parking (BahnPark API) ────────────────────────────────────────

    async def get_parking(self, station_name: str) -> list[dict]:
        """Get parking information for a station."""
        url = f"{PARKING_BASE}/spaces/occupancies"
        resp = await self._get(url, params={"stationName": station_name})

        if resp.status_code != 200:
            self.log.error("timetable.parking_error", status=resp.status_code, station=station_name)
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        results: list[dict] = []
        allocations = data.get("allocations", [])
        for alloc in allocations:
            space = alloc.get("space", {})
            capacity = alloc.get("capacity", {})
            results.append({
                "name": space.get("title", space.get("name", "?")),
                "station": space.get("station", {}).get("name", ""),
                "kapazitaet": capacity.get("total", "?"),
                "frei": capacity.get("available", "?"),
                "kategorie": space.get("type", ""),
            })

        return results

    # ── Accessibility (FaSta API) ─────────────────────────────────────

    async def get_accessibility(self, station_number: str) -> list[dict]:
        """Get elevator/escalator status for a station."""
        url = f"{FASTA_BASE}/facilities"
        params: dict[str, Any] = {
            "state": "ACTIVE",
            "stationnumber": station_number,
        }
        resp = await self._get(url, params=params)

        if resp.status_code != 200:
            self.log.error("timetable.accessibility_error", status=resp.status_code, station=station_number)
            return []

        try:
            data = resp.json()
        except Exception:
            return []

        results: list[dict] = []
        facilities = data if isinstance(data, list) else data.get("facilities", [])
        for fac in facilities:
            results.append({
                "typ": fac.get("type", ""),
                "beschreibung": fac.get("description", ""),
                "status": fac.get("state", "UNKNOWN"),
                "station": fac.get("stationnumber", ""),
                "equipment_nr": fac.get("equipmentnumber", ""),
            })

        return results

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

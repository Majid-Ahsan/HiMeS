"""Async HTTP Client for db-rest — Deutsche Bahn REST API (self-hosted + public fallback).

Design (DB-FIX-1, Phase 1.5.20):
- All public API methods return structured result dicts:
    Success: {"ok": True, "data": <result>}
    Error:   {"ok": False, "error": "<kind>", "user_message_hint": "<de>",
              "retry_suggested": bool, "status_code": int|None, "detail": str}
- Error kinds: hafas_timeout, hafas_overloaded, hafas_not_found,
  hafas_server_error, network_error, geocoding_failed, empty_result, unknown.
- user_message_hint is a ready-to-use German sentence — tools forward it
  verbatim to Claude, which minimises hallucination (DB-FIX-2 alignment).
- Exceptions are caught internally and converted to error dicts.
  resolve_station() remains legacy: raises ValueError on error for old callers.
"""

from __future__ import annotations

import asyncio
import os
import re
import time
import urllib.parse
import urllib.request
import json as _json
from typing import Any

import httpx
import structlog

# Primary: self-hosted instance (Docker network).  Fallback: public API.
PRIMARY_URL = os.getenv("DB_REST_URL", "http://db-rest:3000")
FALLBACK_URL = "https://v6.db.transport.rest"

# Rate limiting (generous for self-hosted, but still protect against loops)
_RATE_LIMIT = 200
_RATE_WINDOW = 60.0


# ── Structured result helpers ─────────────────────────────────────────────

def _ok(data: Any) -> dict:
    """Build a success result dict."""
    return {"ok": True, "data": data}


def _err(
    kind: str,
    hint: str,
    *,
    retry: bool = False,
    status: int | None = None,
    detail: str = "",
) -> dict:
    """Build an error result dict with standardised fields.

    Args:
        kind: Machine-readable error type (e.g. 'hafas_timeout').
        hint: Ready-to-use German sentence for the user.
        retry: Whether a retry makes sense.
        status: HTTP status code if applicable.
        detail: Free-form debug info (not shown to user).
    """
    return {
        "ok": False,
        "error": kind,
        "user_message_hint": hint,
        "retry_suggested": retry,
        "status_code": status,
        "detail": detail,
    }


# Standard error messages (DE, user-friendly, no tech jargon)
_MSG_TIMEOUT = (
    "Die Fahrplan-API antwortet gerade nicht — versuch's in ein paar Sekunden nochmal."
)
_MSG_OVERLOADED = (
    "Die Fahrplan-API ist gerade überlastet — bitte in 10-20 Sekunden erneut versuchen."
)
_MSG_SERVER_ERROR = (
    "Die Fahrplan-API hat einen Serverfehler gemeldet — "
    "versuch's gleich nochmal oder schau in die DB Navigator App."
)
_MSG_NETWORK = (
    "Keine Verbindung zur Fahrplan-API — bitte Netzwerk prüfen oder in wenigen "
    "Sekunden erneut versuchen."
)
_MSG_NOT_FOUND = (
    "Dafür habe ich nichts in der Fahrplan-API gefunden."
)
_MSG_GEOCODING_FAILED = (
    "Ich konnte diese Adresse nicht zu einem Ort auflösen — "
    "versuch's mit der Straße + Stadt (z.B. 'Am Rathaus 15, Mülheim')."
)


class DBRestClient:
    """Async HTTP Client for db-rest with self-hosted primary + public fallback.

    Public API methods return structured result dicts (see module docstring).
    """

    def __init__(self) -> None:
        self._primary: httpx.AsyncClient | None = None
        self._fallback: httpx.AsyncClient | None = None
        self._station_cache: dict[str, str] = {}
        self._location_cache: dict[str, dict[str, Any]] = {}
        self.log = structlog.get_logger("himes_db.rest")
        self._request_timestamps: list[float] = []
        self._using_fallback = False

    # ── HTTP layer ────────────────────────────────────────────────────

    async def _ensure_clients(self) -> None:
        if self._primary is None or self._primary.is_closed:
            self._primary = httpx.AsyncClient(
                base_url=PRIMARY_URL,
                timeout=httpx.Timeout(10.0),
                headers={"User-Agent": "HiMeS/1.0"},
            )
        if self._fallback is None or self._fallback.is_closed:
            self._fallback = httpx.AsyncClient(
                base_url=FALLBACK_URL,
                timeout=httpx.Timeout(15.0),
                headers={"User-Agent": "HiMeS/1.0"},
            )

    async def _rate_limit(self) -> None:
        now = time.monotonic()
        self._request_timestamps = [
            ts for ts in self._request_timestamps if now - ts < _RATE_WINDOW
        ]
        if len(self._request_timestamps) >= _RATE_LIMIT:
            wait = _RATE_WINDOW - (now - self._request_timestamps[0])
            if wait > 0:
                self.log.warning("rest.rate_limit", wait_s=round(wait, 1))
                await asyncio.sleep(wait)

    async def _robust_get(self, path: str, params: dict[str, Any] | None = None) -> dict:
        """GET with primary→fallback strategy, retry, structured result.

        Returns:
            {"ok": True, "data": <parsed JSON>} on success
            {"ok": False, "error": ..., "user_message_hint": ..., ...} on failure

        NEVER raises — always returns a result dict.
        """
        await self._ensure_clients()
        delays = [1, 2, 4]
        start = time.monotonic()

        last_status: int | None = None
        last_detail: str = ""

        # ── Primary attempts ──
        for attempt in range(3):
            await self._rate_limit()
            self._request_timestamps.append(time.monotonic())
            try:
                resp = await self._primary.get(path, params=params)
                last_status = resp.status_code
                if resp.status_code == 404:
                    # 404 from HAFAS → "not found", no retry
                    self.log.info(
                        "rest.not_found",
                        path=path, status=404,
                        duration_ms=int((time.monotonic() - start) * 1000),
                    )
                    return _err("hafas_not_found", _MSG_NOT_FOUND, status=404)
                if resp.status_code in (429, 502, 503, 504) and attempt < 2:
                    self.log.warning(
                        "rest.primary_retry",
                        path=path, status=resp.status_code,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()
                if self._using_fallback:
                    self.log.info("rest.primary_recovered")
                    self._using_fallback = False
                data = resp.json()
                self.log.info(
                    "rest.primary_ok",
                    path=path, status=resp.status_code,
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                return _ok(data)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_detail = f"{type(e).__name__}: {e}"
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                self.log.warning(
                    "rest.primary_network_exhausted",
                    path=path, error=last_detail, attempts=attempt + 1,
                )
                break
            except httpx.HTTPStatusError as e:
                last_detail = f"HTTPStatusError {e.response.status_code}: {e}"
                last_status = e.response.status_code
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                self.log.warning(
                    "rest.primary_http_exhausted",
                    path=path, status=last_status, attempts=attempt + 1,
                )
                break

        # ── Fallback attempts ──
        if not self._using_fallback:
            self.log.warning("rest.using_fallback", fallback_url=FALLBACK_URL)
            self._using_fallback = True

        for attempt in range(3):
            await self._rate_limit()
            self._request_timestamps.append(time.monotonic())
            try:
                resp = await self._fallback.get(path, params=params)
                last_status = resp.status_code
                if resp.status_code == 404:
                    return _err("hafas_not_found", _MSG_NOT_FOUND, status=404)
                if resp.status_code in (429, 502, 503, 504) and attempt < 2:
                    self.log.warning(
                        "rest.fallback_retry",
                        path=path, status=resp.status_code,
                        attempt=attempt + 1,
                    )
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()
                data = resp.json()
                self.log.info(
                    "rest.fallback_ok",
                    path=path, status=resp.status_code,
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                return _ok(data)
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                last_detail = f"{type(e).__name__}: {e}"
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
            except httpx.HTTPStatusError as e:
                last_detail = f"HTTPStatusError {e.response.status_code}: {e}"
                last_status = e.response.status_code
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue

        # ── Both primary and fallback exhausted — classify error ──
        duration_ms = int((time.monotonic() - start) * 1000)
        self.log.error(
            "rest.all_exhausted",
            path=path, status=last_status, detail=last_detail,
            duration_ms=duration_ms,
        )

        # Classify based on last status / detail
        if last_status in (503, 502, 504) or "overloaded" in last_detail.lower():
            return _err("hafas_overloaded", _MSG_OVERLOADED, retry=True,
                        status=last_status, detail=last_detail)
        if last_status == 429:
            return _err("hafas_overloaded", _MSG_OVERLOADED, retry=True,
                        status=429, detail=last_detail)
        if last_status and 500 <= last_status < 600:
            return _err("hafas_server_error", _MSG_SERVER_ERROR, retry=True,
                        status=last_status, detail=last_detail)
        if "Timeout" in last_detail or "timed out" in last_detail.lower():
            return _err("hafas_timeout", _MSG_TIMEOUT, retry=True,
                        detail=last_detail)
        if "Connect" in last_detail:
            return _err("network_error", _MSG_NETWORK, retry=True,
                        detail=last_detail)

        return _err("unknown", _MSG_SERVER_ERROR, retry=True,
                    status=last_status, detail=last_detail)

    # ── Legacy _get shim (raises for backward compat with resolve_station) ──

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """Legacy: raises on error. Prefer _robust_get() in new code."""
        result = await self._robust_get(path, params)
        if not result.get("ok"):
            raise httpx.HTTPError(
                f"{result.get('error', 'unknown')}: {result.get('detail', '')}"
            )
        return result["data"]

    # ── Station resolution ────────────────────────────────────────────

    async def resolve_station(self, name: str) -> str:
        """Resolve a station name to its ID, using cache. Raises ValueError on failure.

        Legacy API — used by db_pendler_check. Prefer resolve_location() in new code.
        """
        key = name.strip().lower()
        if key in self._station_cache:
            return self._station_cache[key]

        if name.strip().isdigit():
            return name.strip()

        result = await self.locations(name, results=1)
        if not result.get("ok"):
            raise ValueError(
                result.get("user_message_hint") or f"Station nicht gefunden: {name}"
            )
        results_list = result.get("data", [])
        if not results_list:
            raise ValueError(f"Station nicht gefunden: {name}")

        station_id = str(results_list[0].get("id", ""))
        if not station_id:
            raise ValueError(f"Station ohne ID: {name}")

        self._station_cache[key] = station_id
        self.log.debug("rest.station_cached", name=name, station_id=station_id)
        return station_id

    async def resolve_location(self, query: str) -> dict[str, Any]:
        """Resolve a query to a location. Returns structured result dict.

        Success:  {"ok": True, "data": {"id", "type", "name", "latitude", "longitude"}}
        Failure:  {"ok": False, "error": ..., "user_message_hint": ...}

        Strategy:
        1. Station keywords (Hbf, Bahnhof, etc.) → HAFAS station search
        2. Otherwise → Nominatim geocoding for real-world addresses/POIs
        3. Fallback: HAFAS with addresses+POI enabled
        """
        key = query.strip().lower()
        start = time.monotonic()

        # Pure EVA number
        if query.strip().isdigit():
            return _ok({
                "id": query.strip(), "type": "stop", "name": query.strip(),
                "latitude": None, "longitude": None,
            })

        # Cache hit
        if key in self._location_cache:
            self.log.debug("rest.location_cache_hit", query=query)
            return _ok(self._location_cache[key])
        if key in self._station_cache:
            self.log.debug("rest.station_cache_hit", query=query)
            return _ok({
                "id": self._station_cache[key], "type": "stop", "name": query,
                "latitude": None, "longitude": None,
            })

        is_station_query = self._looks_like_station(query)

        if is_station_query:
            # Direct HAFAS station search
            result = await self.locations(query, results=3)
            if result.get("ok"):
                data = result["data"]
                if data:
                    best = data[0]
                    loc_type = best.get("type", "stop")
                    if loc_type in ("stop", "station"):
                        station_id = str(best.get("id", ""))
                        if station_id:
                            self._station_cache[key] = station_id
                            loc_data = best.get("location", {})
                            return _ok({
                                "id": station_id, "type": "stop",
                                "name": best.get("name", query),
                                "latitude": loc_data.get("latitude"),
                                "longitude": loc_data.get("longitude"),
                            })
            elif result.get("error") not in (None, "hafas_not_found"):
                # HAFAS is down — propagate the transport error
                return result

        # Non-station query: Nominatim geocoding
        geo = await self._geocode_nominatim(query)
        if geo:
            lat, lon, formatted_name = geo
            loc_result = {
                "id": f"geocode_{lat}_{lon}",
                "type": "location",
                "name": formatted_name,
                "latitude": lat,
                "longitude": lon,
            }
            self._location_cache[key] = loc_result
            self.log.info(
                "rest.geocoded",
                query=query, name=formatted_name, lat=lat, lon=lon,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
            return _ok(loc_result)

        # Fallback: HAFAS with addresses+POI
        fallback_result = await self.locations(query, results=5, addresses=True, poi=True)
        if not fallback_result.get("ok"):
            # Pass through the HAFAS error
            return fallback_result

        data = fallback_result["data"]
        if data:
            best = data[0]
            loc_type = best.get("type", "stop")
            loc_id = str(best.get("id", ""))
            loc_data = best.get("location", {})
            name = best.get("name", best.get("address", query))

            if loc_type in ("stop", "station"):
                if loc_id:
                    self._station_cache[key] = loc_id
                return _ok({
                    "id": loc_id, "type": "stop", "name": name,
                    "latitude": loc_data.get("latitude"),
                    "longitude": loc_data.get("longitude"),
                })

            return _ok({
                "id": loc_id, "type": "location", "name": name,
                "latitude": best.get("latitude") or loc_data.get("latitude"),
                "longitude": best.get("longitude") or loc_data.get("longitude"),
            })

        return _err(
            "geocoding_failed", _MSG_GEOCODING_FAILED,
            detail=f"Nothing found for query: {query}",
        )

    @staticmethod
    def _looks_like_station(query: str) -> bool:
        """Heuristic: does this query look like a train station / transit stop?"""
        q = query.strip().lower()
        station_kw = ["hbf", "bahnhof", "bf", "hauptbahnhof", "haltestelle",
                       "flughafen", "airport", "bhf"]
        if any(kw in q for kw in station_kw):
            return True
        if re.match(r'^[us]\s+\w', q):
            return True
        address_kw = ["straße", "strasse", "str.", "weg", "platz", "allee",
                       "schule", "kirche", "krankenhaus", "hospital", "klinik",
                       "markt", "ring", "damm", "ufer", "gasse"]
        if any(kw in q for kw in address_kw):
            return False
        if re.search(r'\d', q):
            return False
        words = q.split()
        if len(words) == 1:
            return True
        return False

    async def _geocode_nominatim(self, query: str) -> tuple[float, float, str] | None:
        """Geocode via Nominatim. Returns (lat, lon, formatted_name) or None."""
        start = time.monotonic()
        cache_key = query.strip().lower()

        try:
            search_query = query
            if not any(city in query.lower() for city in ["essen", "dortmund", "duisburg",
                       "düsseldorf", "bochum", "bottrop", "oberhausen", "gelsenkirchen"]):
                if "mülheim" not in query.lower() and "muelheim" not in query.lower():
                    search_query = f"{query}, Mülheim an der Ruhr"

            params = urllib.parse.urlencode({
                "q": search_query,
                "format": "json",
                "limit": "1",
                "addressdetails": "1",
                "countrycodes": "de",
            })
            url = f"https://nominatim.openstreetmap.org/search?{params}"
            req = urllib.request.Request(url, headers={"User-Agent": "HiMeS/1.0"})

            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._fetch_nominatim, req)

            if data:
                hit = data[0]
                lat = float(hit["lat"])
                lon = float(hit["lon"])
                addr = hit.get("address", {})
                formatted = self._format_nominatim_address(addr, hit.get("display_name", query))
                self.log.info(
                    "rest.nominatim_ok",
                    query=cache_key, result=formatted,
                    duration_ms=int((time.monotonic() - start) * 1000),
                )
                return lat, lon, formatted

            self.log.info(
                "rest.nominatim_empty",
                query=cache_key,
                duration_ms=int((time.monotonic() - start) * 1000),
            )
        except Exception as e:
            self.log.warning(
                "rest.nominatim_failed",
                query=cache_key, error=str(e),
                duration_ms=int((time.monotonic() - start) * 1000),
            )

        return None

    @staticmethod
    def _fetch_nominatim(req: urllib.request.Request) -> list[dict]:
        """Synchronous Nominatim fetch (called via run_in_executor)."""
        with urllib.request.urlopen(req, timeout=5) as resp:
            return _json.loads(resp.read().decode())

    @staticmethod
    def _format_nominatim_address(addr: dict, display_name: str) -> str:
        parts = []
        name = addr.get("amenity") or addr.get("building") or addr.get("school") or ""
        if name:
            parts.append(name)
        street = addr.get("road", "")
        house = addr.get("house_number", "")
        if street:
            parts.append(f"{street} {house}".strip())
        city = addr.get("city") or addr.get("town") or addr.get("village") or ""
        if city:
            parts.append(city)
        if parts:
            return ", ".join(parts)
        if len(display_name) > 60:
            return display_name[:57] + "..."
        return display_name

    # ── API methods (all return structured results) ───────────────────

    async def locations(self, query: str, **opts: Any) -> dict:
        """Search locations. Returns {"ok": True, "data": [loc, ...]} or error."""
        params: dict[str, Any] = {"query": query, "results": opts.get("results", 5)}
        params["fuzzy"] = "true"
        params["stops"] = "true"
        params["addresses"] = str(opts.get("addresses", False)).lower()
        params["poi"] = str(opts.get("poi", False)).lower()
        params["language"] = "de"
        return await self._robust_get("/locations", params=params)

    async def nearby(self, lat: float, lon: float, **opts: Any) -> dict:
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "distance": opts.get("distance", 1000),
            "results": opts.get("results", 5),
        }
        return await self._robust_get("/locations/nearby", params=params)

    async def journeys(self, from_loc: str | dict, to_loc: str | dict, **opts: Any) -> dict:
        """Search journeys. from_loc/to_loc: station IDs (str) or location dicts.

        Returns {"ok": True, "data": {"journeys": [...]}} or error.
        """
        params: dict[str, Any] = {"language": "de"}
        self._set_location_params(params, "from", from_loc)
        self._set_location_params(params, "to", to_loc)

        if opts.get("departure"):
            params["departure"] = opts["departure"]
        if opts.get("arrival"):
            params["arrival"] = opts["arrival"]
        if opts.get("results"):
            params["results"] = opts["results"]
        if opts.get("transfers") is not None:
            params["transfers"] = opts["transfers"]
        params.update(self._product_params(include_local=True))
        if opts.get("regional_only"):
            params["nationalExpress"] = "false"
            params["national"] = "false"
        params["stopovers"] = "true"
        params["remarks"] = "true"
        return await self._robust_get("/journeys", params=params)

    @staticmethod
    def _set_location_params(params: dict, prefix: str, loc: str | dict) -> None:
        """Set from/to params for journeys — handles stations and addresses/POIs."""
        if isinstance(loc, str):
            params[prefix] = loc
            return

        loc_type = loc.get("type", "stop")
        loc_id = loc.get("id", "")
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        name = loc.get("name", "")

        if loc_type == "stop":
            params[prefix] = loc_id
        elif lat and lon:
            params[f"{prefix}.type"] = "location"
            params[f"{prefix}.latitude"] = lat
            params[f"{prefix}.longitude"] = lon
            params[f"{prefix}.address"] = name
            if loc_id and not loc_id.startswith("geocode_"):
                params[f"{prefix}.id"] = loc_id
        elif loc_id and not loc_id.startswith("geocode_"):
            params[f"{prefix}.type"] = "location"
            params[f"{prefix}.id"] = loc_id
            params[f"{prefix}.address"] = name
        else:
            params[prefix] = loc_id or name

    @staticmethod
    def _product_params(include_local: bool = True) -> dict[str, str]:
        products = {
            "nationalExpress": "true",
            "national": "true",
            "regionalExpress": "true",
            "regional": "true",
            "suburban": "true",
            "subway": "true",
            "tram": "true",
            "bus": "true",
            "ferry": "true",
            "taxi": "true",
        }
        if not include_local:
            products.update({"subway": "false", "tram": "false", "bus": "false", "taxi": "false"})
        return products

    async def departures(self, stop_id: str, **opts: Any) -> dict:
        """Returns {"ok": True, "data": [dep, ...]} or error."""
        params: dict[str, Any] = {
            "duration": opts.get("duration", 60),
            "results": opts.get("results", 10),
            "remarks": "true",
            "language": "de",
        }
        if opts.get("when"):
            params["when"] = opts["when"]
        if opts.get("line_name"):
            params["lineName"] = opts["line_name"]
        params.update(self._product_params(include_local=opts.get("include_local", True)))
        result = await self._robust_get(f"/stops/{stop_id}/departures", params=params)
        if not result.get("ok"):
            return result
        data = result["data"]
        deps = data.get("departures", data) if isinstance(data, dict) else data
        return _ok(deps)

    async def arrivals(self, stop_id: str, **opts: Any) -> dict:
        params: dict[str, Any] = {
            "duration": opts.get("duration", 60),
            "results": opts.get("results", 10),
            "remarks": "true",
            "language": "de",
        }
        if opts.get("when"):
            params["when"] = opts["when"]
        params.update(self._product_params(include_local=opts.get("include_local", True)))
        result = await self._robust_get(f"/stops/{stop_id}/arrivals", params=params)
        if not result.get("ok"):
            return result
        data = result["data"]
        arrs = data.get("arrivals", data) if isinstance(data, dict) else data
        return _ok(arrs)

    async def trip(self, trip_id: str) -> dict:
        """Fetch full trip details (live delay, platform, current location).

        Returns {"ok": True, "data": {...}} or error.
        """
        # URL-encode the trip ID — it can contain | and other special chars
        encoded = urllib.parse.quote(trip_id, safe="")
        return await self._robust_get(f"/trips/{encoded}")

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._primary and not self._primary.is_closed:
            await self._primary.aclose()
            self._primary = None
        if self._fallback and not self._fallback.is_closed:
            await self._fallback.aclose()
            self._fallback = None

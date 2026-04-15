"""Async HTTP Client for db-rest — Deutsche Bahn REST API (self-hosted + public fallback)."""

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


class DBRestClient:
    """Async HTTP Client for db-rest with self-hosted primary + public fallback."""

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

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """GET with primary → fallback strategy and retry."""
        await self._ensure_clients()
        delays = [1, 2, 4]

        # Try primary first
        for attempt in range(3):
            await self._rate_limit()
            self._request_timestamps.append(time.monotonic())
            try:
                resp = await self._primary.get(path, params=params)
                if resp.status_code in (429, 502, 503) and attempt < 2:
                    self.log.warning("rest.primary_retry", path=path, status=resp.status_code, attempt=attempt + 1)
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()
                if self._using_fallback:
                    self.log.info("rest.primary_recovered")
                    self._using_fallback = False
                return resp.json()
            except (httpx.ConnectError, httpx.TimeoutException, httpx.HTTPStatusError) as e:
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                # Primary exhausted — fall through to fallback
                self.log.warning("rest.primary_failed", path=path, error=str(e))
                break

        # Fallback to public API
        if not self._using_fallback:
            self.log.warning("rest.using_fallback", fallback_url=FALLBACK_URL)
            self._using_fallback = True

        for attempt in range(3):
            await self._rate_limit()
            self._request_timestamps.append(time.monotonic())
            try:
                resp = await self._fallback.get(path, params=params)
                if resp.status_code in (429, 502, 503) and attempt < 2:
                    self.log.warning("rest.fallback_retry", path=path, status=resp.status_code, attempt=attempt + 1)
                    await asyncio.sleep(delays[attempt])
                    continue
                resp.raise_for_status()
                return resp.json()
            except (httpx.ConnectError, httpx.TimeoutException) as e:
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise
            except httpx.HTTPStatusError:
                if attempt < 2:
                    await asyncio.sleep(delays[attempt])
                    continue
                raise

        raise httpx.ConnectError("Weder lokale noch öffentliche DB-API erreichbar")

    # ── Station resolution ────────────────────────────────────────────

    async def resolve_station(self, name: str) -> str:
        """Resolve a station name to its ID, using cache."""
        key = name.strip().lower()
        if key in self._station_cache:
            return self._station_cache[key]

        if name.strip().isdigit():
            return name.strip()

        results = await self.locations(name, results=1)
        if not results:
            raise ValueError(f"Station nicht gefunden: {name}")

        station_id = str(results[0].get("id", ""))
        if not station_id:
            raise ValueError(f"Station ohne ID: {name}")

        self._station_cache[key] = station_id
        self.log.debug("rest.station_cached", name=name, station_id=station_id)
        return station_id

    async def resolve_location(self, query: str) -> dict[str, Any]:
        """Resolve a query to a location dict — supports stations, addresses, and POIs.

        Strategy:
        1. If it looks like a station name (Hbf, Bahnhof, etc.) → HAFAS station search
        2. Otherwise → Nominatim geocoding for real-world addresses/POIs → coordinates for HAFAS
        3. Fallback: HAFAS with addresses+POI enabled

        Returns:
            dict with keys: id, type, name, latitude, longitude
            type is one of: "stop", "location" (address/POI)
        """
        key = query.strip().lower()

        # If it's a pure EVA number, return as station
        if query.strip().isdigit():
            return {"id": query.strip(), "type": "stop", "name": query.strip(),
                    "latitude": None, "longitude": None}

        # Check caches
        if key in self._location_cache:
            return self._location_cache[key]
        if key in self._station_cache:
            return {"id": self._station_cache[key], "type": "stop", "name": query,
                    "latitude": None, "longitude": None}

        # Detect if this looks like a station/stop name vs. a real-world address/POI
        is_station_query = self._looks_like_station(query)

        if is_station_query:
            # Direct HAFAS station search
            results = await self.locations(query, results=3)
            if results:
                best = results[0]
                loc_type = best.get("type", "stop")
                if loc_type in ("stop", "station"):
                    station_id = str(best.get("id", ""))
                    if station_id:
                        self._station_cache[key] = station_id
                        loc_data = best.get("location", {})
                        return {"id": station_id, "type": "stop", "name": best.get("name", query),
                                "latitude": loc_data.get("latitude"),
                                "longitude": loc_data.get("longitude")}

        # For addresses and POIs: use Nominatim geocoding first (like CalDAV does)
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
            self.log.info("rest.geocoded", query=query, name=formatted_name, lat=lat, lon=lon)
            return loc_result

        # Fallback: HAFAS with addresses+POI enabled
        results = await self.locations(query, results=5, addresses=True, poi=True)
        if results:
            best = results[0]
            loc_type = best.get("type", "stop")
            loc_id = str(best.get("id", ""))
            loc_data = best.get("location", {})
            name = best.get("name", best.get("address", query))

            if loc_type in ("stop", "station"):
                if loc_id:
                    self._station_cache[key] = loc_id
                return {"id": loc_id, "type": "stop", "name": name,
                        "latitude": loc_data.get("latitude"),
                        "longitude": loc_data.get("longitude")}

            return {
                "id": loc_id,
                "type": "location",
                "name": name,
                "latitude": best.get("latitude") or loc_data.get("latitude"),
                "longitude": best.get("longitude") or loc_data.get("longitude"),
            }

        raise ValueError(f"Ort nicht gefunden: {query}")

    @staticmethod
    def _looks_like_station(query: str) -> bool:
        """Heuristic: does this query look like a train station / transit stop?

        Be STRICT — only return True for obvious station names.
        Anything ambiguous should go to Nominatim first.
        """
        q = query.strip().lower()
        # Station keywords — must be present
        station_kw = ["hbf", "bahnhof", "bf", "hauptbahnhof", "haltestelle",
                       "flughafen", "airport", "bhf"]
        if any(kw in q for kw in station_kw):
            return True
        # Transit line patterns like "U Mülheim", "S Essen"
        if re.match(r'^[us]\s+\w', q):
            return True
        # Address indicators → definitely NOT a station
        address_kw = ["straße", "strasse", "str.", "weg", "platz", "allee",
                       "schule", "kirche", "krankenhaus", "hospital", "klinik",
                       "markt", "ring", "damm", "ufer", "gasse"]
        if any(kw in q for kw in address_kw):
            return False
        # Has house number (digits) → likely an address
        if re.search(r'\d', q):
            return False
        # Single word without station keyword — could be a city name (e.g. "Essen", "Dortmund")
        words = q.split()
        if len(words) == 1:
            return True
        return False

    async def _geocode_nominatim(self, query: str) -> tuple[float, float, str] | None:
        """Geocode an address/POI using Nominatim (OpenStreetMap).

        Returns (lat, lon, formatted_name) or None.
        Free, no API key needed — just requires User-Agent.
        """
        try:
            # Add "Mülheim an der Ruhr" context if query mentions Mülheim
            # or doesn't have a city — helps Nominatim find local results
            search_query = query
            if not any(city in query.lower() for city in ["essen", "dortmund", "duisburg",
                       "düsseldorf", "bochum", "bottrop", "oberhausen", "gelsenkirchen"]):
                if "mülheim" not in query.lower() and "muelheim" not in query.lower():
                    # No city mentioned — add Mülheim as default context (user's home city)
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

            # Run in executor to not block the event loop
            loop = asyncio.get_event_loop()
            data = await loop.run_in_executor(None, self._fetch_nominatim, req)

            if data:
                hit = data[0]
                lat = float(hit["lat"])
                lon = float(hit["lon"])
                addr = hit.get("address", {})
                formatted = self._format_nominatim_address(addr, hit.get("display_name", query))
                return lat, lon, formatted

        except Exception as e:
            self.log.debug("rest.geocode_failed", query=query, error=str(e))

        return None

    @staticmethod
    def _fetch_nominatim(req: urllib.request.Request) -> list[dict]:
        """Synchronous Nominatim fetch (called via run_in_executor)."""
        with urllib.request.urlopen(req, timeout=5) as resp:
            return _json.loads(resp.read().decode())

    @staticmethod
    def _format_nominatim_address(addr: dict, display_name: str) -> str:
        """Format a Nominatim address dict into a readable name."""
        # Try to build a nice short name
        parts = []

        # Name of the place (school, building, etc.)
        name = addr.get("amenity") or addr.get("building") or addr.get("school") or ""
        if name:
            parts.append(name)

        # Street + house number
        street = addr.get("road", "")
        house = addr.get("house_number", "")
        if street:
            parts.append(f"{street} {house}".strip())

        # City
        city = addr.get("city") or addr.get("town") or addr.get("village") or ""
        if city:
            parts.append(city)

        if parts:
            return ", ".join(parts)

        # Fallback: truncate display_name
        if len(display_name) > 60:
            return display_name[:57] + "..."
        return display_name

    # ── API methods ───────────────────────────────────────────────────

    async def locations(self, query: str, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {"query": query, "results": opts.get("results", 5)}
        params["fuzzy"] = "true"
        params["stops"] = "true"
        params["addresses"] = str(opts.get("addresses", False)).lower()
        params["poi"] = str(opts.get("poi", False)).lower()
        params["language"] = "de"
        return await self._get("/locations", params=params)

    async def nearby(self, lat: float, lon: float, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {
            "latitude": lat,
            "longitude": lon,
            "distance": opts.get("distance", 1000),
            "results": opts.get("results", 5),
        }
        return await self._get("/locations/nearby", params=params)

    async def journeys(self, from_loc: str | dict, to_loc: str | dict, **opts: Any) -> dict:
        """Search journeys. from_loc/to_loc can be station IDs (str) or location dicts from resolve_location()."""
        params: dict[str, Any] = {"language": "de"}

        # Build from/to params — support both station IDs and address locations
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
        # Product filters — include all by default, restrict if regional_only
        params.update(self._product_params(include_local=True))
        if opts.get("regional_only"):
            params["nationalExpress"] = "false"
            params["national"] = "false"
        params["stopovers"] = "true"
        params["remarks"] = "true"
        return await self._get("/journeys", params=params)

    @staticmethod
    def _set_location_params(params: dict, prefix: str, loc: str | dict) -> None:
        """Set from/to params for journeys — handles stations and addresses/POIs.

        HAFAS expects:
        - Station: from=8000259
        - Address/coordinates: from.type=location&from.latitude=X&from.longitude=Y&from.address=Name
        """
        if isinstance(loc, str):
            # Plain station ID
            params[prefix] = loc
            return

        loc_type = loc.get("type", "stop")
        loc_id = loc.get("id", "")
        lat = loc.get("latitude")
        lon = loc.get("longitude")
        name = loc.get("name", "")

        if loc_type == "stop":
            # Station — just pass the ID
            params[prefix] = loc_id
        elif lat and lon:
            # Address/POI with coordinates — HAFAS needs type + lat/lon + address
            params[f"{prefix}.type"] = "location"
            params[f"{prefix}.latitude"] = lat
            params[f"{prefix}.longitude"] = lon
            params[f"{prefix}.address"] = name
            # Only pass id if it's a real HAFAS ID (not our geocode_ prefix)
            if loc_id and not loc_id.startswith("geocode_"):
                params[f"{prefix}.id"] = loc_id
        elif loc_id and not loc_id.startswith("geocode_"):
            # HAFAS location ID without coordinates
            params[f"{prefix}.type"] = "location"
            params[f"{prefix}.id"] = loc_id
            params[f"{prefix}.address"] = name
        else:
            # Last resort: just use whatever we have
            params[prefix] = loc_id or name

    @staticmethod
    def _product_params(include_local: bool = True) -> dict[str, str]:
        """Return product filter params — all transport types enabled by default."""
        products = {
            "nationalExpress": "true",  # ICE
            "national": "true",         # IC/EC
            "regionalExpress": "true",  # RE
            "regional": "true",         # RB
            "suburban": "true",         # S-Bahn
            "subway": "true",           # U-Bahn
            "tram": "true",             # Straßenbahn
            "bus": "true",              # Bus
            "ferry": "true",            # Fähre
            "taxi": "true",             # Rufbus/AST
        }
        if not include_local:
            products.update({"subway": "false", "tram": "false", "bus": "false", "taxi": "false"})
        return products

    async def departures(self, stop_id: str, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {
            "duration": opts.get("duration", 60),
            "results": opts.get("results", 10),
            "remarks": "true",
            "language": "de",
        }
        params.update(self._product_params(include_local=opts.get("include_local", True)))
        data = await self._get(f"/stops/{stop_id}/departures", params=params)
        return data.get("departures", data) if isinstance(data, dict) else data

    async def arrivals(self, stop_id: str, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {
            "duration": opts.get("duration", 60),
            "results": opts.get("results", 10),
            "remarks": "true",
            "language": "de",
        }
        params.update(self._product_params(include_local=opts.get("include_local", True)))
        data = await self._get(f"/stops/{stop_id}/arrivals", params=params)
        return data.get("arrivals", data) if isinstance(data, dict) else data

    async def trip(self, trip_id: str) -> dict:
        return await self._get(f"/trips/{trip_id}")

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._primary and not self._primary.is_closed:
            await self._primary.aclose()
            self._primary = None
        if self._fallback and not self._fallback.is_closed:
            await self._fallback.aclose()
            self._fallback = None

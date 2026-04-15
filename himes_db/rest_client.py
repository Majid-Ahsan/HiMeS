"""Async HTTP Client for db-rest — Deutsche Bahn REST API (self-hosted + public fallback)."""

from __future__ import annotations

import asyncio
import os
import time
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

    # ── API methods ───────────────────────────────────────────────────

    async def locations(self, query: str, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {"query": query, "results": opts.get("results", 5)}
        params["fuzzy"] = "true"
        params["stops"] = "true"
        params["addresses"] = "false"
        params["poi"] = "false"
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

    async def journeys(self, from_id: str, to_id: str, **opts: Any) -> dict:
        params: dict[str, Any] = {"from": from_id, "to": to_id, "language": "de"}
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

"""Async HTTP Client for v6.db.transport.rest — Deutsche Bahn public REST API."""

from __future__ import annotations

import asyncio
import time
from typing import Any

import httpx
import structlog

BASE_URL = "https://v6.db.transport.rest"

# Rate limiting: max 100 requests per minute
_RATE_LIMIT = 100
_RATE_WINDOW = 60.0


class DBRestClient:
    """Async HTTP Client for v6.db.transport.rest with caching and retry."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self._station_cache: dict[str, str] = {}  # normalised name -> station id
        self.log = structlog.get_logger("himes_db.rest")

        # Simple sliding-window rate limiter
        self._request_timestamps: list[float] = []

    # ── HTTP layer ────────────────────────────────────────────────────

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                base_url=BASE_URL,
                timeout=httpx.Timeout(15.0),
                headers={"User-Agent": "HiMeS/1.0 (github.com/himes)"},
            )
        return self._client

    async def _rate_limit(self) -> None:
        """Block until we are within the rate window."""
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
        """GET with retry on 429/502/503, exponential backoff."""
        client = await self._ensure_client()
        delays = [1, 2, 4]

        for attempt in range(4):  # initial + 3 retries
            await self._rate_limit()
            self._request_timestamps.append(time.monotonic())

            try:
                resp = await client.get(path, params=params)
            except httpx.TimeoutException:
                if attempt < 3:
                    self.log.warning("rest.timeout_retry", path=path, attempt=attempt + 1)
                    await asyncio.sleep(delays[attempt])
                    continue
                raise

            if resp.status_code in (429, 502, 503) and attempt < 3:
                self.log.warning(
                    "rest.retry",
                    path=path,
                    status=resp.status_code,
                    attempt=attempt + 1,
                )
                await asyncio.sleep(delays[attempt])
                continue

            resp.raise_for_status()
            return resp.json()

        # Should not reach here, but satisfy type checker
        raise httpx.HTTPStatusError(
            "Max retries exceeded", request=httpx.Request("GET", path), response=resp  # type: ignore[possibly-undefined]
        )

    # ── Station resolution ────────────────────────────────────────────

    async def resolve_station(self, name: str) -> str:
        """Resolve a station name to its ID, using cache."""
        key = name.strip().lower()
        if key in self._station_cache:
            return self._station_cache[key]

        # If it looks like a numeric EVA number already, return as-is
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
        params: dict[str, Any] = {"from": from_id, "to": to_id}
        if opts.get("departure"):
            params["departure"] = opts["departure"]
        if opts.get("arrival"):
            params["arrival"] = opts["arrival"]
        if opts.get("results"):
            params["results"] = opts["results"]
        if opts.get("transfers") is not None:
            params["transfers"] = opts["transfers"]
        if opts.get("regional_only"):
            params["nationalExpress"] = "false"
            params["national"] = "false"
        params["stopovers"] = "true"
        params["remarks"] = "true"
        return await self._get("/journeys", params=params)

    async def departures(self, stop_id: str, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {
            "duration": opts.get("duration", 60),
            "results": opts.get("results", 10),
        }
        data = await self._get(f"/stops/{stop_id}/departures", params=params)
        return data.get("departures", data) if isinstance(data, dict) else data

    async def arrivals(self, stop_id: str, **opts: Any) -> list[dict]:
        params: dict[str, Any] = {
            "duration": opts.get("duration", 60),
            "results": opts.get("results", 10),
        }
        data = await self._get(f"/stops/{stop_id}/arrivals", params=params)
        return data.get("arrivals", data) if isinstance(data, dict) else data

    async def trip(self, trip_id: str) -> dict:
        return await self._get(f"/trips/{trip_id}")

    # ── Cleanup ───────────────────────────────────────────────────────

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

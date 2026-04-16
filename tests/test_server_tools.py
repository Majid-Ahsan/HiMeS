"""Integration tests for MCP tool layer (himes_db/server.py).

Focus: new db_train_live_status tool + error-result passthrough.
Uses respx to mock both db-rest endpoints.

Requires Python 3.10+ (mcp SDK) — skipped on 3.9.
"""

from __future__ import annotations

import pytest
import respx
import httpx

# MCP SDK requires Python 3.10+; skip these tests otherwise.
pytest.importorskip("mcp", reason="mcp SDK requires Python 3.10+ — tests run in Docker/CI")

from himes_db import server as srv  # noqa: E402
from himes_db.rest_client import PRIMARY_URL, FALLBACK_URL  # noqa: E402


@pytest.fixture(autouse=True)
def _reset_client_caches():
    """Clear caches between tests to avoid pollution."""
    srv.rest_client._station_cache.clear()
    srv.rest_client._location_cache.clear()
    yield
    srv.rest_client._station_cache.clear()
    srv.rest_client._location_cache.clear()


# ─── db_train_live_status ─────────────────────────────────────────────

class TestLiveStatus:
    async def test_live_status_punctual_train(self, respx_mock):
        # resolve_station
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim (Ruhr) Hbf", "type": "stop"}]
        )
        # departures filtered by line
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").respond(
            200, json={"departures": [{
                "tripId": "trip-1|abc",
                "line": {"name": "RE1", "product": "regionalExpress"},
                "when": "2026-04-16T10:30:00+02:00",
                "plannedWhen": "2026-04-16T10:30:00+02:00",
                "delay": 0,
                "platform": "5",
                "plannedPlatform": "5",
                "direction": "Hamm",
                "cancelled": False,
            }]}
        )
        # trip details
        respx_mock.get(url__regex=f"{PRIMARY_URL}/trips/.*").respond(
            200, json={"trip": {
                "line": {"name": "RE1"},
                "direction": "Hamm",
                "destination": {"name": "Hamm Hbf"},
                "delay": 0,
                "platform": "5",
                "plannedPlatform": "5",
                "stopovers": [],
            }}
        )
        result = await srv.db_train_live_status(
            line="RE1", station="Mülheim Hbf"
        )
        assert "RE1" in result
        assert "Pünktlich" in result
        assert "Gleis 5" in result
        assert "⚠️" not in result  # no disclaimer/warning

    async def test_live_status_with_platform_change(self, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").respond(
            200, json={"departures": [{
                "tripId": "trip-1|abc",
                "line": {"name": "RE1", "product": "regionalExpress"},
                "when": "2026-04-16T10:36:00+02:00",
                "plannedWhen": "2026-04-16T10:30:00+02:00",
                "delay": 360,
                "platform": "11",
                "plannedPlatform": "5",
                "direction": "Hamm",
                "cancelled": False,
            }]}
        )
        respx_mock.get(url__regex=f"{PRIMARY_URL}/trips/.*").respond(
            200, json={"trip": {
                "line": {"name": "RE1"},
                "direction": "Hamm",
                "destination": {"name": "Hamm Hbf"},
                "delay": 360,
                "platform": "11",
                "plannedPlatform": "5",
                "stopovers": [],
            }}
        )
        result = await srv.db_train_live_status(line="RE1")
        assert "RE1" in result
        assert "Gleisänderung" in result
        assert "5 →" in result
        assert "11" in result
        assert "+6 min" in result  # 360s = 6min

    async def test_live_status_cancelled(self, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").respond(
            200, json={"departures": [{
                "tripId": "trip-1|abc",
                "line": {"name": "S1", "product": "suburban"},
                "plannedWhen": "2026-04-16T10:00:00+02:00",
                "when": None,
                "delay": None,
                "cancelled": True,
                "plannedPlatform": "3",
                "platform": None,
                "direction": "Dortmund Hbf",
            }]}
        )
        respx_mock.get(url__regex=f"{PRIMARY_URL}/trips/.*").respond(
            200, json={"trip": {
                "line": {"name": "S1"},
                "destination": {"name": "Dortmund Hbf"},
                "cancelled": True,
                "stopovers": [],
            }}
        )
        result = await srv.db_train_live_status(line="S1")
        assert "AUSFALL" in result

    async def test_live_status_line_not_found(self, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        # Empty departures
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").respond(
            200, json={"departures": []}
        )
        result = await srv.db_train_live_status(line="RE99")
        assert "⚠️" in result
        assert "Keine aktuellen Abfahrten" in result
        assert "RE99" in result

    async def test_live_status_departures_fails_gracefully(self, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/stops/8000259/departures").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        result = await srv.db_train_live_status(line="RE1")
        assert "⚠️" in result
        # Forwards the user_message_hint verbatim (DB-FIX-1 + DB-FIX-2)
        assert "überlastet" in result or "antwortet gerade nicht" in result

    async def test_live_status_trip_details_fail_falls_back_to_dep(self, respx_mock):
        """If /trips/:id fails, fall back to departure data (don't hallucinate)."""
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").respond(
            200, json={"departures": [{
                "tripId": "trip-1|abc",
                "line": {"name": "S1", "product": "suburban"},
                "when": "2026-04-16T10:05:00+02:00",
                "plannedWhen": "2026-04-16T10:00:00+02:00",
                "delay": 300,
                "platform": "3",
                "plannedPlatform": "3",
                "direction": "Dortmund",
            }]}
        )
        # trips endpoint fails
        respx_mock.get(url__regex=f"{PRIMARY_URL}/trips/.*").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(url__regex=f"{FALLBACK_URL}/trips/.*").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        result = await srv.db_train_live_status(line="S1")
        # Must still have partial data from the departure, not crash
        assert "S1" in result
        assert "+5 min" in result or "Gleis 3" in result


# ─── Tool-layer error passthrough (DB-FIX-1 integration) ───────────

class TestToolErrorPassthrough:
    async def test_search_connections_forwards_hint_on_hafas_error(self, respx_mock):
        # resolve_location finds stations OK for both
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        # But journeys fails
        respx_mock.get(f"{PRIMARY_URL}/journeys").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/journeys").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        result = await srv.db_search_connections(
            from_station="Mülheim Hbf", to_station="Dortmund Hbf"
        )
        assert result.startswith("⚠️")
        assert "überlastet" in result or "antwortet gerade nicht" in result

    async def test_departures_forwards_hint_on_timeout(self, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim Hbf", "type": "stop"}]
        )
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        respx_mock.get(f"{FALLBACK_URL}/stops/8000259/departures").mock(
            side_effect=httpx.TimeoutException("Timeout")
        )
        result = await srv.db_departures(station="Mülheim Hbf")
        assert result.startswith("⚠️")

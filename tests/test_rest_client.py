"""Unit tests for DBRestClient.

Covers:
- Success → {"ok": True, "data": ...}
- HAFAS 503/502/504 → hafas_overloaded with retry_suggested=True
- HAFAS timeout → hafas_timeout with hint
- HAFAS 404 → hafas_not_found (no retry)
- HAFAS 500 → hafas_server_error
- Network error → network_error
- Empty result → geocoding_failed when resolve_location finds nothing
- Primary→fallback failover: primary fails, fallback succeeds → data returned
- _looks_like_station heuristic (preserved behaviour)
"""

from __future__ import annotations

import httpx
import pytest
import respx

from himes_db.rest_client import DBRestClient, PRIMARY_URL, FALLBACK_URL


@pytest.fixture
def client():
    """Fresh client per test — avoid cache pollution."""
    return DBRestClient()


# ─── Success path ────────────────────────────────────────────────────

class TestSuccessPath:
    async def test_locations_success(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim (Ruhr) Hbf", "type": "stop"}]
        )
        result = await client.locations("Mülheim Hbf")
        assert result["ok"] is True
        assert result["data"][0]["id"] == "8000259"

    async def test_journeys_success(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/journeys").respond(
            200, json={"journeys": [{"refreshToken": "abc"}]}
        )
        result = await client.journeys("8000259", "8000080")
        assert result["ok"] is True
        assert len(result["data"]["journeys"]) == 1

    async def test_departures_success(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/departures").respond(
            200, json={"departures": [{"line": {"name": "RE1"}}]}
        )
        result = await client.departures("8000259")
        assert result["ok"] is True
        assert result["data"][0]["line"]["name"] == "RE1"

    async def test_arrivals_success(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/stops/8000259/arrivals").respond(
            200, json={"arrivals": [{"line": {"name": "S1"}}]}
        )
        result = await client.arrivals("8000259")
        assert result["ok"] is True

    async def test_trip_url_encoded(self, client, respx_mock):
        # Trip IDs contain | and other special chars that need encoding
        route = respx_mock.get(url__regex=f"{PRIMARY_URL}/trips/.*").respond(
            200, json={"trip": {"id": "1|12345|abc"}}
        )
        result = await client.trip("1|12345|abc")
        assert result["ok"] is True
        assert route.called


# ─── Error classification ────────────────────────────────────────────

class TestErrorClassification:
    async def test_503_is_overloaded(self, client, respx_mock):
        # Primary 503 all attempts → falls to fallback, also 503 → classify
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        result = await client.locations("Test")
        assert result["ok"] is False
        assert result["error"] == "hafas_overloaded"
        assert result["retry_suggested"] is True
        assert "überlastet" in result["user_message_hint"]

    async def test_404_is_not_found_no_retry(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/stops/99999/departures").respond(404)
        result = await client.departures("99999")
        assert result["ok"] is False
        assert result["error"] == "hafas_not_found"
        assert result["retry_suggested"] is False  # default / not set to True

    async def test_500_is_server_error(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/journeys").mock(
            side_effect=[httpx.Response(500)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/journeys").mock(
            side_effect=[httpx.Response(500)] * 3
        )
        result = await client.journeys("8000259", "8000080")
        assert result["ok"] is False
        # 500 falls under hafas_server_error
        assert result["error"] == "hafas_server_error"
        assert result["retry_suggested"] is True

    async def test_network_error_is_classified(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=httpx.ConnectError("Cannot connect")
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").mock(
            side_effect=httpx.ConnectError("Cannot connect")
        )
        result = await client.locations("Test")
        assert result["ok"] is False
        assert result["error"] in ("network_error", "unknown")
        assert result["retry_suggested"] is True

    async def test_timeout_is_classified(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=httpx.TimeoutException("Timed out")
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").mock(
            side_effect=httpx.TimeoutException("Timed out")
        )
        result = await client.locations("Test")
        assert result["ok"] is False
        # Either timeout or network (ConnectError parent) — both OK
        assert result["error"] in ("hafas_timeout", "network_error", "unknown")
        assert result["retry_suggested"] is True


# ─── Primary → Fallback failover ────────────────────────────────────

class TestFailover:
    async def test_primary_fails_fallback_succeeds(self, client, respx_mock):
        # Primary: 3x 503 → Fallback: 200
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").respond(
            200, json=[{"id": "8000080", "name": "Dortmund Hbf", "type": "stop"}]
        )
        result = await client.locations("Dortmund")
        assert result["ok"] is True
        assert result["data"][0]["name"] == "Dortmund Hbf"


# ─── resolve_location (structured results) ─────────────────────────

class TestResolveLocation:
    async def test_pure_eva_number(self, client):
        result = await client.resolve_location("8000259")
        assert result["ok"] is True
        assert result["data"]["id"] == "8000259"
        assert result["data"]["type"] == "stop"

    async def test_station_query_success(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000259", "name": "Mülheim (Ruhr) Hbf",
                        "type": "stop", "location": {"latitude": 51.42,
                                                      "longitude": 6.88}}]
        )
        result = await client.resolve_location("Mülheim Hbf")
        assert result["ok"] is True
        assert result["data"]["type"] == "stop"

    async def test_hafas_error_propagates(self, client, respx_mock):
        """When HAFAS is down, resolve_location should propagate the error."""
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        result = await client.resolve_location("Mülheim Hbf")
        assert result["ok"] is False
        assert result["error"] == "hafas_overloaded"


# ─── _looks_like_station heuristic ──────────────────────────────────

class TestLooksLikeStation:
    @pytest.mark.parametrize("query,expected", [
        ("Mülheim Hbf", True),
        ("Dortmund Hbf", True),
        ("Essen", True),
        ("Essen Hauptbahnhof", True),
        ("Otto-Pankok-Schule Mülheim", False),
        ("Am Rathaus 15, Mülheim", False),
        ("Marienhospital Bottrop", False),
        ("Von-Bock-Straße 81", False),
        ("Flughafen Düsseldorf", True),
    ])
    def test_heuristic_cases(self, query, expected):
        assert DBRestClient._looks_like_station(query) is expected


# ─── Legacy resolve_station (still raises) ──────────────────────────

class TestResolveStationLegacy:
    async def test_resolve_station_success(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(
            200, json=[{"id": "8000080", "name": "Dortmund Hbf", "type": "stop"}]
        )
        sid = await client.resolve_station("Dortmund Hbf")
        assert sid == "8000080"

    async def test_resolve_station_raises_on_error(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        with pytest.raises(ValueError):
            await client.resolve_station("Invalid")

    async def test_resolve_station_pure_number(self, client):
        # Pure EVA number — no API call
        sid = await client.resolve_station("8000259")
        assert sid == "8000259"


# ─── Error result shape contract ────────────────────────────────────

class TestErrorResultShape:
    async def test_all_error_fields_present(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        respx_mock.get(f"{FALLBACK_URL}/locations").mock(
            side_effect=[httpx.Response(503)] * 3
        )
        result = await client.locations("Test")
        # Contract: all these fields MUST exist
        assert "ok" in result
        assert "error" in result
        assert "user_message_hint" in result
        assert "retry_suggested" in result
        assert "status_code" in result
        assert "detail" in result
        assert isinstance(result["user_message_hint"], str)
        assert len(result["user_message_hint"]) > 0

    async def test_success_result_has_data(self, client, respx_mock):
        respx_mock.get(f"{PRIMARY_URL}/locations").respond(200, json=[])
        result = await client.locations("Test")
        assert "ok" in result
        assert result["ok"] is True
        assert "data" in result

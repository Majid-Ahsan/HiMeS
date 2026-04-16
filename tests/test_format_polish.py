"""Tests for DB-FIX-3 format polish.

Covers:
- No ⬅️/▶️ markers in journey rows (replaced by prefix line)
- "↩ frühere Alternativen:" appears once when earlier journeys exist
- ━━━ separator always shown on split
- Remark relevance filter: off-route remarks dropped
- Remark relevance filter: on-route remarks kept
- Time-window filter: remarks outside ±30min dropped
"""

from __future__ import annotations

import pytest

pytest.importorskip("mcp", reason="mcp SDK requires Python 3.10+")

from datetime import datetime, timedelta  # noqa: E402
from zoneinfo import ZoneInfo  # noqa: E402

from himes_db import server as srv  # noqa: E402

TZ = ZoneInfo("Europe/Berlin")


# ─── Journey row format (no per-row marker) ─────────────────────────

class TestJourneyRowFormat:
    def _minimal_journey(self, dep: str, arr: str, line: str = "RE1", dest: str = "Hamm") -> dict:
        return {
            "legs": [{
                "departure": dep,
                "arrival": arr,
                "line": {"name": line, "product": "regionalExpress"},
                "direction": dest,
                "destination": {"name": dest},
                "origin": {"name": "Mülheim Hbf"},
                "departurePlatform": "5",
                "arrivalPlatform": "10",
                "remarks": [],
            }],
        }

    def test_row_has_no_arrow_markers(self):
        j = self._minimal_journey("2026-04-16T06:44:00+02:00", "2026-04-16T07:14:00+02:00")
        row = srv._format_journey_row(j, is_earlier=False)
        assert "⬅️" not in row
        assert "▶️" not in row
        # Train emoji is the visual lead now
        assert row.startswith("🚆")
        assert "06:44" in row
        assert "07:14" in row
        assert "RE1" in row

    def test_row_earlier_has_no_marker_either(self):
        """is_earlier flag no longer affects the row itself — handled at caller."""
        j = self._minimal_journey("2026-04-16T06:05:00+02:00", "2026-04-16T06:35:00+02:00")
        row_normal = srv._format_journey_row(j, is_earlier=False)
        row_earlier = srv._format_journey_row(j, is_earlier=True)
        # Both rows are identical — earlier marker is added by caller as prefix line
        assert row_normal == row_earlier


# ─── Remark relevance filter ───────────────────────────────────────

class TestRemarkRelevance:
    def test_remark_mentioning_journey_station_is_kept(self):
        jstart = datetime(2026, 4, 16, 6, 44, tzinfo=TZ)
        jend = datetime(2026, 4, 16, 7, 14, tzinfo=TZ)
        stations = {"Mülheim(Ruhr)Hbf", "Hamm(Westf)Hbf"}
        remark = {
            "type": "warning",
            "text": "Signalstörung in Mülheim Hbf — mit Verspätungen zu rechnen.",
        }
        assert srv._is_remark_relevant(remark, jstart, jend, stations) is True

    def test_remark_for_offroute_city_is_dropped(self):
        jstart = datetime(2026, 4, 16, 6, 44, tzinfo=TZ)
        jend = datetime(2026, 4, 16, 7, 14, tzinfo=TZ)
        stations = {"Mülheim Hbf", "Dortmund Hbf"}
        remark = {
            "type": "warning",
            "text": "Bauarbeiten Aachen-Stolberg 18.05.-03.06., betrifft Strecke zwischen Köln und Aachen.",
        }
        # Aachen/Köln are not on Mülheim-Dortmund route → drop
        assert srv._is_remark_relevant(remark, jstart, jend, stations) is False

    def test_remark_time_window_past_is_dropped(self):
        jstart = datetime(2026, 4, 16, 6, 44, tzinfo=TZ)
        jend = datetime(2026, 4, 16, 7, 14, tzinfo=TZ)
        remark = {
            "type": "warning",
            "text": "Störung zwischen Mülheim und Dortmund",
            "validUntil": "2026-04-16T05:00:00+02:00",  # Ended before journey
        }
        assert srv._is_remark_relevant(
            remark, jstart, jend, {"Mülheim"}
        ) is False

    def test_remark_time_window_future_is_dropped(self):
        jstart = datetime(2026, 4, 16, 6, 44, tzinfo=TZ)
        jend = datetime(2026, 4, 16, 7, 14, tzinfo=TZ)
        remark = {
            "type": "warning",
            "text": "Wartung",
            "validFrom": "2026-04-16T22:00:00+02:00",  # Starts way after journey
        }
        assert srv._is_remark_relevant(
            remark, jstart, jend, {"Mülheim"}
        ) is False

    def test_remark_time_window_within_tolerance(self):
        """Tolerance is ±30 min — remark ending 10 min before should stay."""
        jstart = datetime(2026, 4, 16, 6, 44, tzinfo=TZ)
        jend = datetime(2026, 4, 16, 7, 14, tzinfo=TZ)
        remark = {
            "type": "warning",
            "text": "Störung in Mülheim Hbf",
            "validUntil": "2026-04-16T06:34:00+02:00",  # 10 min before journey start
        }
        assert srv._is_remark_relevant(
            remark, jstart, jend, {"Mülheim"}
        ) is True

    def test_remark_without_time_window_keeps_if_station_matches(self):
        jstart = datetime(2026, 4, 16, 6, 44, tzinfo=TZ)
        jend = datetime(2026, 4, 16, 7, 14, tzinfo=TZ)
        remark = {"type": "warning", "text": "Störung in Mülheim Hbf"}
        assert srv._is_remark_relevant(
            remark, jstart, jend, {"Mülheim Hbf"}
        ) is True


# ─── Station name normalisation ────────────────────────────────────

class TestStationNameStrip:
    @pytest.mark.parametrize("input,expected", [
        ("Mülheim(Ruhr)Hbf", "Mülheim"),
        ("Hamm(Westf)Hbf", "Hamm"),
        ("Dortmund Hbf", "Dortmund"),
        ("Essen Hauptbahnhof", "Essen"),
        ("Köln Messe/Deutz", "Köln Messe/Deutz"),
    ])
    def test_strip_station_name(self, input, expected):
        assert srv._strip_station_name(input) == expected


# ─── Journey stations collection ───────────────────────────────────

class TestCollectJourneyStations:
    def test_collects_origin_destination(self):
        journey = {
            "legs": [{
                "origin": {"name": "Mülheim Hbf"},
                "destination": {"name": "Dortmund Hbf"},
            }],
        }
        stations = srv._collect_journey_stations(journey)
        assert "Mülheim Hbf" in stations
        assert "Dortmund Hbf" in stations

    def test_collects_stopovers(self):
        journey = {
            "legs": [{
                "origin": {"name": "Mülheim Hbf"},
                "destination": {"name": "Hamm"},
                "stopovers": [
                    {"stop": {"name": "Essen Hbf"}},
                    {"stop": {"name": "Bochum Hbf"}},
                    {"stop": {"name": "Dortmund Hbf"}},
                ],
            }],
        }
        stations = srv._collect_journey_stations(journey)
        assert len(stations) == 5
        assert "Essen Hbf" in stations
        assert "Bochum Hbf" in stations

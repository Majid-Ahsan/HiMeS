"""Async client for zuginfo.nrw — NRW rail disruption information.

Fetches disruption data from strecken.info (same backend as zuginfo.nrw)
and falls back to HAFAS remarks via db-rest if the page is unavailable.
"""

from __future__ import annotations

import re
from typing import Any

import httpx
import structlog

# strecken.info is the data backend for zuginfo.nrw — provides JSON
ZUGINFO_URL = "https://strecken.info/api/v1/disruptions"
ZUGINFO_FALLBACK = "https://www.zuginfo.nrw"

# NRW region filter (EVA prefixes / bounding box)
NRW_BBOX = {"lat_min": 50.3, "lat_max": 52.5, "lon_min": 5.8, "lon_max": 9.5}


class ZuginfoClient:
    """Async client to fetch NRW rail disruption data."""

    def __init__(self) -> None:
        self._client: httpx.AsyncClient | None = None
        self.log = structlog.get_logger("himes_db.zuginfo")

    async def _ensure_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=httpx.Timeout(15.0),
                headers={
                    "User-Agent": "HiMeS/1.0",
                    "Accept": "text/html,application/json",
                },
                follow_redirects=True,
            )
        return self._client

    async def get_disruptions(self, line_filter: str | None = None) -> list[dict[str, Any]]:
        """Fetch current NRW disruptions.

        Args:
            line_filter: Optional filter like 'RE1', 'S1', 'U18', 'Tram 901'

        Returns:
            List of disruption dicts with keys: line, title, description, period, type
        """
        # Try strecken.info API first (JSON)
        disruptions = await self._fetch_strecken_info(line_filter)
        if disruptions:
            return disruptions

        # Fallback: scrape zuginfo.nrw HTML
        disruptions = await self._scrape_zuginfo_nrw(line_filter)
        return disruptions

    async def _fetch_strecken_info(self, line_filter: str | None = None) -> list[dict[str, Any]]:
        """Try the strecken.info JSON API."""
        client = await self._ensure_client()
        try:
            resp = await client.get(ZUGINFO_URL, params={"region": "nrw"})
            if resp.status_code != 200:
                self.log.debug("zuginfo.strecken_api_unavailable", status=resp.status_code)
                return []

            data = resp.json()
            if not isinstance(data, list):
                data = data.get("disruptions", data.get("data", []))

            results: list[dict[str, Any]] = []
            for item in data:
                entry = {
                    "line": item.get("line", item.get("lineName", "")),
                    "title": item.get("title", item.get("summary", "")),
                    "description": item.get("description", item.get("text", "")),
                    "period": item.get("period", item.get("duration", "")),
                    "type": item.get("type", item.get("category", "Stoerung")),
                }
                if line_filter and line_filter.lower() not in entry["line"].lower():
                    continue
                results.append(entry)

            return results[:30]

        except (httpx.HTTPError, ValueError, KeyError) as e:
            self.log.debug("zuginfo.strecken_api_error", error=str(e))
            return []

    async def _scrape_zuginfo_nrw(self, line_filter: str | None = None) -> list[dict[str, Any]]:
        """Scrape the zuginfo.nrw HTML page for disruption info."""
        client = await self._ensure_client()
        try:
            resp = await client.get(ZUGINFO_FALLBACK)
            if resp.status_code != 200:
                self.log.warning("zuginfo.page_unavailable", status=resp.status_code)
                return []

            html = resp.text
            return self._parse_disruptions_html(html, line_filter)

        except httpx.HTTPError as e:
            self.log.warning("zuginfo.scrape_error", error=str(e))
            return []

    def _parse_disruptions_html(self, html: str, line_filter: str | None = None) -> list[dict[str, Any]]:
        """Extract disruption info from HTML using regex patterns."""
        results: list[dict[str, Any]] = []

        # Try common patterns for disruption entries
        # Pattern 1: <div class="disruption-item"> or similar
        # Pattern 2: Table rows with disruption data
        # Pattern 3: List items with line info

        # Generic pattern: find blocks with line names and disruption text
        # Look for patterns like "RE1", "S1", "RB32", "U18", "Tram 901", "Bus 124"
        line_pattern = r'(?:RE\d+|RB\d+|S\d+|U\d+|ICE?\s*\d+|Tram\s*\d+|Bus\s*\d+|STR\s*\d+)'

        # Try to find structured content
        # Remove HTML tags for text extraction
        text = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        text = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        text = re.sub(r'<[^>]+>', '\n', text)
        text = re.sub(r'\n\s*\n', '\n', text)
        text = re.sub(r'[ \t]+', ' ', text)

        # Find disruption-like blocks: line name followed by description
        blocks = re.findall(
            rf'({line_pattern})\s*[:\-|]\s*(.+?)(?=\n(?:{line_pattern})|\Z)',
            text,
            re.DOTALL | re.IGNORECASE,
        )

        for line_name, description in blocks:
            desc_clean = description.strip()[:300]
            if not desc_clean:
                continue

            if line_filter and line_filter.lower() not in line_name.lower():
                continue

            results.append({
                "line": line_name.strip(),
                "title": desc_clean.split('\n')[0][:100],
                "description": desc_clean,
                "period": "",
                "type": "Stoerung",
            })

        # If regex didn't find structured data, extract any text mentioning disruptions
        if not results:
            keywords = ["Stoerung", "Störung", "Ausfall", "Ersatzverkehr", "Bauarbeiten",
                        "Verspätung", "gesperrt", "Schienenersatz", "SEV"]
            lines_text = text.split('\n')
            for line_text in lines_text:
                line_text = line_text.strip()
                if len(line_text) < 20 or len(line_text) > 500:
                    continue
                if any(kw.lower() in line_text.lower() for kw in keywords):
                    # Try to extract line name
                    line_match = re.search(line_pattern, line_text, re.IGNORECASE)
                    line_name = line_match.group(0) if line_match else "NRW"

                    if line_filter and line_filter.lower() not in line_name.lower():
                        continue

                    results.append({
                        "line": line_name,
                        "title": line_text[:100],
                        "description": line_text,
                        "period": "",
                        "type": "Stoerung",
                    })

        return results[:30]

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

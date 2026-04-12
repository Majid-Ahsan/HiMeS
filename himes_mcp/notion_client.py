"""Async Notion API client with retry, pagination, relation resolution, and schema cache."""

from __future__ import annotations

import asyncio
import os
import time
from typing import Any

import httpx
import structlog

logger = structlog.get_logger(__name__)

NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Central databases page — source DBs for Medical Records linked views.
DATABASES_PAGE_ID = "2da89b37-089f-80e8-a195-f798f499db99"

# Schema cache TTL in seconds.
_SCHEMA_CACHE_TTL = 300


class NotionClient:
    """Thin async wrapper around the Notion REST API."""

    def __init__(self, token: str | None = None):
        self.token = token or os.environ.get("NOTION_TOKEN", "")
        self._headers = {
            "Authorization": f"Bearer {self.token}",
            "Notion-Version": NOTION_VERSION,
            "Content-Type": "application/json",
        }
        self._schema_cache: dict[str, tuple[float, dict]] = {}
        self._relation_title_cache: dict[str, str] = {}

    # ── Core request with retry ─────────────────────────────────────────

    async def _request(
        self,
        method: str,
        endpoint: str,
        json_body: dict | None = None,
        retries: int = 3,
    ) -> dict:
        url = f"{NOTION_BASE}{endpoint}"
        backoff = 1.0
        last_error: Exception | None = None

        for attempt in range(retries):
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    resp = await client.request(
                        method, url, headers=self._headers, json=json_body
                    )

                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", backoff))
                    logger.warning("notion.rate_limited", retry_after=retry_after)
                    await asyncio.sleep(retry_after)
                    backoff *= 2
                    continue

                if resp.status_code >= 500:
                    logger.warning("notion.server_error", status=resp.status_code, attempt=attempt)
                    await asyncio.sleep(backoff)
                    backoff *= 2
                    continue

                if resp.status_code >= 400:
                    body = resp.json()
                    msg = body.get("message", resp.text)
                    raise NotionAPIError(resp.status_code, msg)

                return resp.json()

            except httpx.TimeoutException:
                last_error = TimeoutError(f"Notion API Timeout: {method} {endpoint}")
                logger.warning("notion.timeout", attempt=attempt, endpoint=endpoint)
                await asyncio.sleep(backoff)
                backoff *= 2

        raise last_error or NotionAPIError(0, "Max retries exceeded")

    # ── Pages ───────────────────────────────────────────────────────────

    async def get_page(self, page_id: str) -> dict:
        return await self._request("GET", f"/pages/{page_id}")

    async def create_page(
        self,
        parent: dict,
        properties: dict,
        children: list[dict] | None = None,
        icon: str | None = None,
    ) -> dict:
        body: dict[str, Any] = {"parent": parent, "properties": properties}
        if children:
            body["children"] = children
        if icon:
            body["icon"] = {"type": "emoji", "emoji": icon}
        return await self._request("POST", "/pages", json_body=body)

    async def update_page(self, page_id: str, properties: dict) -> dict:
        return await self._request("PATCH", f"/pages/{page_id}", json_body={"properties": properties})

    async def archive_page(self, page_id: str) -> dict:
        return await self._request("PATCH", f"/pages/{page_id}", json_body={"archived": True})

    # ── Blocks ──────────────────────────────────────────────────────────

    async def get_blocks(self, block_id: str) -> list[dict]:
        """Get ALL child blocks with pagination."""
        blocks: list[dict] = []
        cursor: str | None = None
        while True:
            endpoint = f"/blocks/{block_id}/children?page_size=100"
            if cursor:
                endpoint += f"&start_cursor={cursor}"
            data = await self._request("GET", endpoint)
            blocks.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
        return blocks

    async def append_blocks(self, block_id: str, children: list[dict]) -> dict:
        return await self._request(
            "PATCH", f"/blocks/{block_id}/children", json_body={"children": children}
        )

    async def delete_block(self, block_id: str) -> dict:
        return await self._request("DELETE", f"/blocks/{block_id}")

    # ── Databases ───────────────────────────────────────────────────────

    async def get_database(self, db_id: str) -> dict:
        return await self._request("GET", f"/databases/{db_id}")

    async def query_database(
        self,
        db_id: str,
        filter: dict | None = None,
        sorts: list | None = None,
        limit: int = 0,
    ) -> list[dict]:
        """Query a database with FULL pagination. limit=0 means all results."""
        results: list[dict] = []
        cursor: str | None = None
        while True:
            body: dict[str, Any] = {"page_size": 100}
            if filter:
                body["filter"] = filter
            if sorts:
                body["sorts"] = sorts
            if cursor:
                body["start_cursor"] = cursor
            data = await self._request("POST", f"/databases/{db_id}/query", json_body=body)
            results.extend(data.get("results", []))
            if not data.get("has_more"):
                break
            cursor = data.get("next_cursor")
            if limit and len(results) >= limit:
                results = results[:limit]
                break
        return results

    async def get_database_schema(self, db_id: str) -> dict:
        """Get DB schema with 5-min cache."""
        now = time.time()
        if db_id in self._schema_cache:
            cached_at, schema = self._schema_cache[db_id]
            if now - cached_at < _SCHEMA_CACHE_TTL:
                return schema
        db = await self.get_database(db_id)
        schema = db.get("properties", {})
        self._schema_cache[db_id] = (now, schema)
        return schema

    # ── Search ──────────────────────────────────────────────────────────

    async def search(
        self, query: str, filter_type: str | None = None
    ) -> list[dict]:
        """Search workspace. filter_type: 'page' or 'database'."""
        body: dict[str, Any] = {"query": query, "page_size": 20}
        if filter_type:
            body["filter"] = {"value": filter_type, "property": "object"}
        data = await self._request("POST", "/search", json_body=body)
        return data.get("results", [])

    # ── Relation resolution ─────────────────────────────────────────────

    async def resolve_relation_titles(self, page_ids: list[str]) -> dict[str, str]:
        """Batch-resolve page IDs to their title strings. Uses cache."""
        result: dict[str, str] = {}
        to_fetch: list[str] = []

        for pid in page_ids:
            if pid in self._relation_title_cache:
                result[pid] = self._relation_title_cache[pid]
            else:
                to_fetch.append(pid)

        # Fetch unknown pages (max 10 concurrent)
        sem = asyncio.Semaphore(10)

        async def _fetch_one(pid: str) -> None:
            async with sem:
                try:
                    page = await self.get_page(pid)
                    for pv in page.get("properties", {}).values():
                        if pv.get("type") == "title":
                            title = "".join(
                                t.get("plain_text", "") for t in pv.get("title", [])
                            )
                            result[pid] = title
                            self._relation_title_cache[pid] = title
                            return
                    result[pid] = pid  # no title found
                except Exception:
                    result[pid] = pid

        if to_fetch:
            await asyncio.gather(*[_fetch_one(pid) for pid in to_fetch])

        return result

    # ── Central DB fallback (Medical Records) ───────────────────────────

    async def find_central_database(self, title: str) -> str | None:
        """Find a source database by title in the central Databases page."""
        blocks = await self.get_blocks(DATABASES_PAGE_ID)
        for block in blocks:
            if block.get("type") == "column_list":
                cols = await self.get_blocks(block["id"])
                for col in cols:
                    if col.get("type") == "column":
                        inners = await self.get_blocks(col["id"])
                        for inner in inners:
                            if inner.get("type") == "child_database":
                                db_name = inner["child_database"].get("title", "")
                                if db_name.lower().strip() == title.lower().strip():
                                    logger.info("notion.central_db_found", title=title, id=inner["id"])
                                    return inner["id"]
        return None

    async def get_block_title(self, block_id: str) -> str:
        """Get the title of a child_database or child_page block."""
        try:
            data = await self._request("GET", f"/blocks/{block_id}")
            btype = data.get("type", "")
            if btype == "child_database":
                return data["child_database"].get("title", "")
            if btype == "child_page":
                return data["child_page"].get("title", "")
        except Exception:
            pass
        return ""


class NotionAPIError(Exception):
    def __init__(self, status: int, message: str):
        self.status = status
        self.message = message
        super().__init__(f"Notion API {status}: {message}")

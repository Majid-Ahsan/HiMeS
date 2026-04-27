#!/usr/bin/env python3
"""Cognee MCP Server — read-only search over Cognee Knowledge-Graph."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# sys.path-Setup VOR allen Repo-Imports (ADR-044).
_REPO_ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_REPO_ROOT))

# .env-Load VOR cognee-Import (ADR-044).
from pipeline._cognee_env import load_cognee_env  # noqa: E402

load_cognee_env()

# Erst jetzt cognee + FastMCP importieren.
import cognee  # noqa: E402
from mcp.server.fastmcp import FastMCP  # noqa: E402

mcp = FastMCP(
    "cognee",
    host=os.getenv("COGNEE_MCP_HOST", "127.0.0.1"),
    port=int(os.getenv("COGNEE_MCP_PORT", "8002")),
)


@mcp.tool(
    description="Search the Cognee Knowledge-Graph for memories and context."
)
async def cognee_search(query: str, top_k: int = 5) -> dict:
    """Search the Cognee Knowledge-Graph for memories and context."""
    try:
        results = await cognee.search(query_text=query, top_k=top_k)
        if isinstance(results, list):
            results = results[:top_k]
        return {"ok": True, "results": results}
    except Exception as e:
        import logging
        logging.exception("cognee_search failed for query=%r", query)
        return {
            "ok": False,
            "error": type(e).__name__,
            "detail": str(e),
            "user_message_hint": "Konnte Gedächtnis gerade nicht abfragen.",
            "retry_suggested": True,
        }


if __name__ == "__main__":
    mcp.run(transport=os.getenv("COGNEE_MCP_TRANSPORT", "sse"))

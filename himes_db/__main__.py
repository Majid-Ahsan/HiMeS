"""Entry point for `python -m himes_db`."""

from himes_db.server import mcp

mcp.run(transport="stdio")

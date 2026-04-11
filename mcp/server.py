import aiofiles
import structlog
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from config.settings import settings

logger = structlog.get_logger(__name__)

server = Server("himes-memory")


# ── Memory Tools ────────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="memory_read",
            description="Liest die MEMORY.md Datei mit persistentem Kontext",
            inputSchema={
                "type": "object",
                "properties": {},
            },
        ),
        Tool(
            name="memory_write",
            description="Schreibt Inhalt in die MEMORY.md Datei",
            inputSchema={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "Neuer Inhalt für MEMORY.md"},
                },
                "required": ["content"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info("mcp.tool_call", tool=name, arguments=arguments)

    try:
        match name:
            case "memory_read":
                return await _memory_read()
            case "memory_write":
                return await _memory_write(**arguments)
            case _:
                return [TextContent(type="text", text=f"Unbekanntes Tool: {name}")]
    except Exception as e:
        logger.exception("mcp.tool_error", tool=name)
        return [TextContent(type="text", text=f"Fehler: {e}")]


async def _memory_read() -> list[TextContent]:
    path = settings.memory.file_path
    if not path.exists():
        return [TextContent(type="text", text="MEMORY.md existiert noch nicht.")]

    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()

    return [TextContent(type="text", text=content or "(leer)")]


async def _memory_write(content: str) -> list[TextContent]:
    path = settings.memory.file_path
    path.parent.mkdir(parents=True, exist_ok=True)

    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)

    logger.info("memory.written", path=str(path), size=len(content))
    return [TextContent(type="text", text="MEMORY.md aktualisiert.")]


# ── Entrypoint ──────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("mcp.memory_server_starting")
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

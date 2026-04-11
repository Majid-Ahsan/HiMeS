import json
import os

import aiofiles
import httpx
import structlog
from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from config.settings import settings

logger = structlog.get_logger(__name__)

server = Server("himes-tools")

NOTION_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"

# Central databases page — contains the source databases for Medical Records.
# Child databases under patient pages are linked views of these.
DATABASES_PAGE_ID = "2da89b37-089f-80e8-a195-f798f499db99"


def _notion_headers() -> dict:
    token = os.environ.get("NOTION_TOKEN", "")
    return {
        "Authorization": f"Bearer {token}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ── Tool Registry ──────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="memory_read",
            description="Liest die MEMORY.md Datei mit persistentem Kontext",
            inputSchema={"type": "object", "properties": {}},
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
        Tool(
            name="notion_list_children",
            description=(
                "Listet alle Kind-Blöcke einer Notion-Seite auf (child_page, child_database). "
                "Gibt die ECHTEN Datenbank-IDs zurück. "
                "IMMER nutzen um die richtige DB-ID eines Patienten zu finden, "
                "BEVOR query_database aufgerufen wird."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion Page ID"},
                },
                "required": ["page_id"],
            },
        ),
        Tool(
            name="notion_query_database_full",
            description=(
                "Fragt eine Notion-Datenbank ab und löst Relation-Properties automatisch auf. "
                "Gibt alle Properties inkl. verlinkte Einträge (z.B. Drug Names) zurück. "
                "Bei verlinkten Views (z.B. Diagnoses unter Patienten) wird automatisch "
                "die zentrale Quelldatenbank gesucht und abgefragt. "
                "Optional: patient_name zum Filtern bei zentralen Datenbanken."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Notion Database ID (aus notion_list_children)"},
                    "patient_name": {
                        "type": "string",
                        "description": "Patient-Name zum Filtern (z.B. 'Ahsan, Hossein'). Nur nötig bei zentralen DBs.",
                    },
                },
                "required": ["database_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info("mcp.tool_call", tool=name)

    try:
        match name:
            case "memory_read":
                return await _memory_read()
            case "memory_write":
                return await _memory_write(**arguments)
            case "notion_list_children":
                return await _notion_list_children(**arguments)
            case "notion_query_database_full":
                return await _notion_query_database_full(**arguments)
            case _:
                return [TextContent(type="text", text=f"Unbekanntes Tool: {name}")]
    except Exception as e:
        logger.exception("mcp.tool_error", tool=name)
        return [TextContent(type="text", text=f"Fehler: {e}")]


# ── Memory Tools ────────────────────────────────────────────────────────

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


# ── Notion Tools ───────────────────────────────────────────────────────

async def _notion_list_children(page_id: str) -> list[TextContent]:
    """Lists child blocks of a page, returning real database/page IDs."""
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.get(
            f"{NOTION_BASE}/blocks/{page_id}/children?page_size=100",
            headers=_notion_headers(),
        )
        resp.raise_for_status()

    blocks = resp.json().get("results", [])
    if not blocks:
        return [TextContent(type="text", text="Keine Kind-Blöcke gefunden.")]

    output = []
    for block in blocks:
        block_type = block.get("type", "")
        block_id = block.get("id", "")

        if block_type == "child_database":
            title = block["child_database"].get("title", "?")
            output.append(f"- [database] {title} (ID: {block_id})")
        elif block_type == "child_page":
            title = block["child_page"].get("title", "?")
            output.append(f"- [page] {title} (ID: {block_id})")

    if not output:
        return [TextContent(type="text", text="Keine child_database oder child_page Blöcke gefunden.")]

    return [TextContent(type="text", text="\n".join(output))]


async def _notion_query_database_full(
    database_id: str, patient_name: str = ""
) -> list[TextContent]:
    """Query a database and resolve all relation properties.

    If the database is a linked view (returns 'data sources' error),
    automatically find the central source database with the same name
    and query it instead.
    """
    async with httpx.AsyncClient(timeout=60) as client:
        # First, get the database title (needed for fallback)
        db_title = ""
        try:
            db_meta = await client.get(
                f"{NOTION_BASE}/blocks/{database_id}",
                headers=_notion_headers(),
            )
            if db_meta.status_code == 200:
                meta = db_meta.json()
                if meta.get("type") == "child_database":
                    db_title = meta["child_database"].get("title", "")
        except Exception:
            pass

        # Try querying the database directly
        resp = await client.post(
            f"{NOTION_BASE}/databases/{database_id}/query",
            headers=_notion_headers(),
            json={"page_size": 100},
        )

        # If it fails with "data sources" error, fall back to central DB
        if resp.status_code == 400:
            error_msg = resp.json().get("message", "")
            if "data sources" in error_msg and db_title:
                logger.info(
                    "notion.fallback_to_central",
                    linked_id=database_id,
                    db_title=db_title,
                )
                central_id = await _find_central_database(client, db_title)
                if central_id:
                    return await _query_and_format(
                        client, central_id, patient_name
                    )
                return [TextContent(
                    type="text",
                    text=f"Zentrale Datenbank '{db_title}' nicht gefunden.",
                )]

        resp.raise_for_status()
        results = resp.json().get("results", [])
        return await _format_results(client, results)


async def _find_central_database(
    client: httpx.AsyncClient, title: str
) -> str | None:
    """Find the central database ID by searching the Databases page."""
    # Walk through the Databases page columns to find the DB by title
    page_resp = await client.get(
        f"{NOTION_BASE}/blocks/{DATABASES_PAGE_ID}/children?page_size=100",
        headers=_notion_headers(),
    )
    if page_resp.status_code != 200:
        return None

    # Databases page uses column_list layout — recurse into columns
    blocks = page_resp.json().get("results", [])
    for block in blocks:
        if block.get("type") == "column_list":
            col_resp = await client.get(
                f"{NOTION_BASE}/blocks/{block['id']}/children?page_size=100",
                headers=_notion_headers(),
            )
            if col_resp.status_code != 200:
                continue
            for col in col_resp.json().get("results", []):
                if col.get("type") == "column":
                    inner_resp = await client.get(
                        f"{NOTION_BASE}/blocks/{col['id']}/children?page_size=100",
                        headers=_notion_headers(),
                    )
                    if inner_resp.status_code != 200:
                        continue
                    for inner in inner_resp.json().get("results", []):
                        if inner.get("type") == "child_database":
                            db_name = inner["child_database"].get("title", "")
                            if db_name.lower().strip() == title.lower().strip():
                                logger.info(
                                    "notion.central_db_found",
                                    title=title,
                                    central_id=inner["id"],
                                )
                                return inner["id"]
    return None


async def _query_and_format(
    client: httpx.AsyncClient, database_id: str, patient_name: str = ""
) -> list[TextContent]:
    """Query a database with optional patient name filter."""
    body: dict = {"page_size": 100}

    # If patient_name given, filter by relation or text property
    # We don't know the exact filter property, so we query all and filter client-side
    resp = await client.post(
        f"{NOTION_BASE}/databases/{database_id}/query",
        headers=_notion_headers(),
        json=body,
    )
    resp.raise_for_status()

    results = resp.json().get("results", [])

    # Client-side filter by patient name if provided
    if patient_name and results:
        filtered = []
        for row in results:
            if _row_matches_patient(row, patient_name):
                filtered.append(row)
        if filtered:
            results = filtered
        else:
            # If no match with filter, maybe relation names need resolving first
            # Return all results and let Claude figure it out
            pass

    return await _format_results(client, results)


def _row_matches_patient(row: dict, patient_name: str) -> bool:
    """Check if a database row belongs to a patient (by relation or text)."""
    name_lower = patient_name.lower()
    props = row.get("properties", {})
    for prop in props.values():
        ptype = prop.get("type", "")
        if ptype == "rich_text":
            text = "".join(
                t.get("plain_text", "") for t in prop.get("rich_text", [])
            ).lower()
            if name_lower in text:
                return True
        elif ptype == "title":
            text = "".join(
                t.get("plain_text", "") for t in prop.get("title", [])
            ).lower()
            if name_lower in text:
                return True
    return False


async def _format_results(
    client: httpx.AsyncClient, results: list[dict]
) -> list[TextContent]:
    """Format database results, resolving relations."""
    if not results:
        return [TextContent(type="text", text="Keine Einträge gefunden.")]

    # Collect all relation page IDs to resolve
    relation_ids: set[str] = set()
    for row in results:
        for prop in row.get("properties", {}).values():
            if prop.get("type") == "relation":
                for rel in prop.get("relation", []):
                    relation_ids.add(rel["id"])

    # Resolve relation titles
    relation_titles: dict[str, str] = {}
    for rel_id in relation_ids:
        try:
            rel_resp = await client.get(
                f"{NOTION_BASE}/pages/{rel_id}",
                headers=_notion_headers(),
            )
            if rel_resp.status_code == 200:
                rel_data = rel_resp.json()
                for pv in rel_data.get("properties", {}).values():
                    if pv.get("type") == "title":
                        parts = pv.get("title", [])
                        relation_titles[rel_id] = "".join(
                            t.get("plain_text", "") for t in parts
                        )
                        break
        except Exception:
            pass

    # Format output
    output = []
    for row in results:
        props = row.get("properties", {})
        entry = {}
        for key, prop in props.items():
            ptype = prop.get("type", "")
            if ptype == "title":
                parts = prop.get("title", [])
                entry[key] = "".join(t.get("plain_text", "") for t in parts)
            elif ptype == "rich_text":
                parts = prop.get("rich_text", [])
                entry[key] = "".join(t.get("plain_text", "") for t in parts)
            elif ptype == "number":
                entry[key] = str(prop.get("number", ""))
            elif ptype == "select":
                sel = prop.get("select")
                entry[key] = sel.get("name", "") if sel else ""
            elif ptype == "multi_select":
                entry[key] = ", ".join(
                    s.get("name", "") for s in prop.get("multi_select", [])
                )
            elif ptype == "date":
                d = prop.get("date")
                if d:
                    entry[key] = d.get("start", "")
                    if d.get("end"):
                        entry[key] += f" → {d['end']}"
                else:
                    entry[key] = ""
            elif ptype == "checkbox":
                entry[key] = "Ja" if prop.get("checkbox") else "Nein"
            elif ptype == "relation":
                names = []
                for rel in prop.get("relation", []):
                    names.append(relation_titles.get(rel["id"], rel["id"]))
                entry[key] = ", ".join(names)
            elif ptype == "status":
                st = prop.get("status")
                entry[key] = st.get("name", "") if st else ""

        parts = [f"  {k}: {v}" for k, v in entry.items() if v]
        if parts:
            output.append("\n".join(parts))

    return [TextContent(type="text", text="\n---\n".join(output))]


# ── Entrypoint ──────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("mcp.server_starting")
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="himes-tools",
            server_version="1.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities=None,
            ),
        )
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

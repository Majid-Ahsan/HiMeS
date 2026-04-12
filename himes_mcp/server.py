"""HiMeS Tools MCP Server — Memory + Notion (native API)."""

import os

import aiofiles
import structlog
from mcp.server import Server, InitializationOptions, NotificationOptions
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

from config.settings import settings
from .notion_client import NotionClient, NotionAPIError
from .notion_markdown import blocks_to_markdown, markdown_to_blocks, rich_text_to_markdown
from .notion_properties import to_notion, from_notion, schema_to_markdown

logger = structlog.get_logger(__name__)

server = Server("himes-tools")

# Lazy-initialized client (needs NOTION_TOKEN from env at runtime).
_notion: NotionClient | None = None


def _get_notion() -> NotionClient:
    global _notion
    if _notion is None:
        _notion = NotionClient()
    return _notion


# ── Tool Registry ──────────────────────────────────────────────────────

@server.list_tools()
async def list_tools() -> list[Tool]:
    return [
        # ── Memory ──
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
        # ── Notion: Navigation ──
        Tool(
            name="notion_search",
            description=(
                "Sucht im Notion-Workspace nach Seiten oder Datenbanken. "
                "Gibt Markdown-Liste mit Titeln und IDs zurück."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Suchbegriff"},
                    "filter_type": {
                        "type": "string",
                        "enum": ["page", "database"],
                        "description": "Optional: nur Seiten oder nur Datenbanken suchen",
                    },
                },
                "required": ["query"],
            },
        ),
        Tool(
            name="notion_list_children",
            description=(
                "Listet alle Kind-Blöcke einer Notion-Seite auf (child_page, child_database). "
                "Gibt die ECHTEN Datenbank-IDs zurück. "
                "IMMER nutzen um die richtige DB-ID eines Patienten zu finden, "
                "BEVOR notion_query_database aufgerufen wird."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion Page ID"},
                },
                "required": ["page_id"],
            },
        ),
        # ── Notion: Seiten lesen/schreiben ──
        Tool(
            name="notion_read_page",
            description=(
                "Liest eine Notion-Seite und gibt den Inhalt als Markdown zurück. "
                "Inkl. Properties (mit aufgelösten Relations) und Block-Content."
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
            name="notion_create_page",
            description=(
                "Erstellt eine neue Notion-Seite. Markdown wird zu Blocks konvertiert. "
                "Für DB-Einträge: parent_id = Database ID + properties angeben."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Seitentitel"},
                    "parent_id": {
                        "type": "string",
                        "description": "Parent Page ID oder Database ID. Ohne = Workspace-Root.",
                    },
                    "parent_type": {
                        "type": "string",
                        "enum": ["page_id", "database_id"],
                        "description": "Typ des Parents. Default: page_id",
                    },
                    "markdown": {
                        "type": "string",
                        "description": "Seiteninhalt als Markdown (optional)",
                    },
                    "properties": {
                        "type": "object",
                        "description": "DB-Properties als Key-Value (z.B. {\"Status\": \"Done\"}). Werden automatisch konvertiert.",
                    },
                    "icon": {
                        "type": "string",
                        "description": "Emoji-Icon für die Seite (z.B. '📋')",
                    },
                },
                "required": ["title"],
            },
        ),
        Tool(
            name="notion_update_page",
            description=(
                "Updated eine Notion-Seite. Kann Properties, Titel und Icon ändern."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion Page ID"},
                    "properties": {
                        "type": "object",
                        "description": "Properties als Key-Value (auto-konvertiert anhand Schema)",
                    },
                    "title": {"type": "string", "description": "Neuer Titel"},
                    "icon": {"type": "string", "description": "Neues Emoji-Icon"},
                },
                "required": ["page_id"],
            },
        ),
        Tool(
            name="notion_append_content",
            description=(
                "Fügt Markdown am Ende einer Seite hinzu (ohne bestehenden Content zu löschen)."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion Page ID"},
                    "markdown": {"type": "string", "description": "Markdown-Text zum Anhängen"},
                },
                "required": ["page_id", "markdown"],
            },
        ),
        Tool(
            name="notion_archive_page",
            description="Archiviert (löscht) eine Notion-Seite oder DB-Eintrag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Notion Page ID"},
                },
                "required": ["page_id"],
            },
        ),
        # ── Notion: Datenbanken ──
        Tool(
            name="notion_get_database",
            description=(
                "Gibt das Schema einer Datenbank als Markdown-Tabelle zurück. "
                "Zeigt Properties, Typen und Optionen."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Notion Database ID"},
                },
                "required": ["database_id"],
            },
        ),
        Tool(
            name="notion_query_database",
            description=(
                "Fragt eine Notion-Datenbank ab. Volle Pagination, Relations werden "
                "MIT TITELN aufgelöst. Bei verlinkten Views (data sources error) wird "
                "automatisch die zentrale Quelldatenbank gesucht. "
                "Optional: patient_name zum Filtern bei zentralen Medical-Records-DBs."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Notion Database ID (aus notion_list_children)"},
                    "filter": {
                        "type": "object",
                        "description": "Notion API Filter-Objekt (optional)",
                    },
                    "sorts": {
                        "type": "array",
                        "description": "Notion API Sort-Array (optional)",
                    },
                    "patient_name": {
                        "type": "string",
                        "description": "Patient-Name zum Filtern bei zentralen DBs (z.B. 'Ahsan, Hossein')",
                    },
                },
                "required": ["database_id"],
            },
        ),
        Tool(
            name="notion_add_entry",
            description=(
                "Fügt einen neuen Eintrag in eine Datenbank hinzu. "
                "Properties als einfache Key-Value-Paare, werden automatisch konvertiert."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "database_id": {"type": "string", "description": "Notion Database ID"},
                    "properties": {
                        "type": "object",
                        "description": "Properties als Key-Value (z.B. {\"Name\": \"Test\", \"Status\": \"Active\"})",
                    },
                },
                "required": ["database_id", "properties"],
            },
        ),
        Tool(
            name="notion_update_entry",
            description="Updated einen DB-Eintrag. Properties als Key-Value.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID des Eintrags"},
                    "properties": {
                        "type": "object",
                        "description": "Properties als Key-Value (auto-konvertiert)",
                    },
                },
                "required": ["page_id", "properties"],
            },
        ),
        Tool(
            name="notion_delete_entry",
            description="Archiviert einen Datenbank-Eintrag.",
            inputSchema={
                "type": "object",
                "properties": {
                    "page_id": {"type": "string", "description": "Page ID des Eintrags"},
                },
                "required": ["page_id"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    logger.info("mcp.tool_call", tool=name)

    try:
        match name:
            # Memory
            case "memory_read":
                return await _memory_read()
            case "memory_write":
                return await _memory_write(**arguments)
            # Notion navigation
            case "notion_search":
                return await _notion_search(**arguments)
            case "notion_list_children":
                return await _notion_list_children(**arguments)
            # Notion pages
            case "notion_read_page":
                return await _notion_read_page(**arguments)
            case "notion_create_page":
                return await _notion_create_page(**arguments)
            case "notion_update_page":
                return await _notion_update_page(**arguments)
            case "notion_append_content":
                return await _notion_append_content(**arguments)
            case "notion_archive_page":
                return await _notion_archive_page(**arguments)
            # Notion databases
            case "notion_get_database":
                return await _notion_get_database(**arguments)
            case "notion_query_database":
                return await _notion_query_database(**arguments)
            case "notion_add_entry":
                return await _notion_add_entry(**arguments)
            case "notion_update_entry":
                return await _notion_update_entry(**arguments)
            case "notion_delete_entry":
                return await _notion_delete_entry(**arguments)
            case _:
                return [_text(f"Unbekanntes Tool: {name}")]
    except NotionAPIError as e:
        logger.warning("mcp.notion_api_error", tool=name, status=e.status, msg=e.message)
        return [_text(_friendly_error(e))]
    except Exception as e:
        logger.exception("mcp.tool_error", tool=name)
        return [_text(f"Fehler: {e}")]


def _text(content: str) -> TextContent:
    return TextContent(type="text", text=content)


def _friendly_error(e: NotionAPIError) -> str:
    if e.status == 404:
        return f"Nicht gefunden. Prüfe ob die Integration Zugriff auf diese Seite/DB hat. ({e.message})"
    if e.status == 400:
        return f"Ungültige Anfrage: {e.message}"
    if e.status == 403:
        return f"Kein Zugriff. Die Integration hat keine Berechtigung für diese Ressource. ({e.message})"
    if e.status == 409:
        return f"Konflikt: {e.message}"
    return f"Notion API Fehler {e.status}: {e.message}"


# ── Memory Tools ────────────────────────────────────────────────────────

async def _memory_read() -> list[TextContent]:
    path = settings.memory.file_path
    if not path.exists():
        return [_text("MEMORY.md existiert noch nicht.")]
    async with aiofiles.open(path, "r", encoding="utf-8") as f:
        content = await f.read()
    return [_text(content or "(leer)")]


async def _memory_write(content: str) -> list[TextContent]:
    path = settings.memory.file_path
    path.parent.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(path, "w", encoding="utf-8") as f:
        await f.write(content)
    logger.info("memory.written", path=str(path), size=len(content))
    return [_text("MEMORY.md aktualisiert.")]


# ── Notion: Navigation ─────────────────────────────────────────────────

async def _notion_search(query: str, filter_type: str | None = None) -> list[TextContent]:
    notion = _get_notion()
    results = await notion.search(query, filter_type)
    if not results:
        return [_text(f"Keine Ergebnisse für '{query}'.")]

    lines: list[str] = []
    for item in results:
        obj_type = item.get("object", "")
        item_id = item.get("id", "")
        last_edited = item.get("last_edited_time", "")[:10]

        # Extract title
        title = ""
        if obj_type == "page":
            for pv in item.get("properties", {}).values():
                if pv.get("type") == "title":
                    title = "".join(t.get("plain_text", "") for t in pv.get("title", []))
                    break
            if not title:
                # Try icon + title from page object
                title = item.get("url", item_id)
        elif obj_type == "database":
            title_parts = item.get("title", [])
            title = "".join(t.get("plain_text", "") for t in title_parts)

        icon = "📄" if obj_type == "page" else "📊"
        lines.append(f"- {icon} **{title or '(Ohne Titel)'}** — ID: `{item_id}` — {last_edited}")

    return [_text("\n".join(lines))]


async def _notion_list_children(page_id: str) -> list[TextContent]:
    notion = _get_notion()
    blocks = await notion.get_blocks(page_id)
    if not blocks:
        return [_text("Keine Kind-Blöcke gefunden.")]

    output: list[str] = []
    for block in blocks:
        btype = block.get("type", "")
        bid = block.get("id", "")
        if btype == "child_database":
            title = block["child_database"].get("title", "?")
            output.append(f"- 📊 [database] {title} (ID: `{bid}`)")
        elif btype == "child_page":
            title = block["child_page"].get("title", "?")
            output.append(f"- 📄 [page] {title} (ID: `{bid}`)")

    if not output:
        return [_text("Keine child_database oder child_page Blöcke gefunden.")]
    return [_text("\n".join(output))]


# ── Notion: Pages ──────────────────────────────────────────────────────

async def _notion_read_page(page_id: str) -> list[TextContent]:
    notion = _get_notion()

    # Get page metadata + properties
    page = await notion.get_page(page_id)
    props = page.get("properties", {})

    # Resolve relations in properties
    relation_ids: list[str] = []
    for pv in props.values():
        if pv.get("type") == "relation":
            relation_ids.extend(r["id"] for r in pv.get("relation", []))
    resolved = await notion.resolve_relation_titles(relation_ids) if relation_ids else {}

    # Format properties
    prop_values = from_notion(props, resolved)

    # Extract title
    title = ""
    for pv in props.values():
        if pv.get("type") == "title":
            title = "".join(t.get("plain_text", "") for t in pv.get("title", []))
            break

    # Get page content blocks
    blocks = await notion.get_blocks(page_id)

    # Build output
    parts: list[str] = []
    if title:
        parts.append(f"# {title}")

    # Icon
    icon = page.get("icon", {})
    if icon and icon.get("type") == "emoji":
        parts.append(f"Icon: {icon['emoji']}")

    # Properties (skip title, already shown)
    prop_lines = [f"- **{k}**: {v}" for k, v in prop_values.items() if v and k != title]
    if prop_lines:
        parts.append("\n## Properties\n" + "\n".join(prop_lines))

    # Content
    if blocks:
        md = blocks_to_markdown(blocks)
        if md.strip():
            parts.append("\n## Content\n" + md)

    return [_text("\n".join(parts) if parts else "(Leere Seite)")]


async def _notion_create_page(
    title: str,
    parent_id: str | None = None,
    parent_type: str = "page_id",
    markdown: str | None = None,
    properties: dict | None = None,
    icon: str | None = None,
) -> list[TextContent]:
    notion = _get_notion()

    # Build parent
    if parent_id:
        parent = {parent_type: parent_id}
    else:
        parent = {"page_id": parent_id} if parent_id else {"page_id": ""}

    # Build properties
    if parent_type == "database_id" and properties:
        schema = await notion.get_database_schema(parent_id)
        notion_props = to_notion(properties, schema)
        # Ensure title
        title_key = _find_title_key(schema)
        if title_key and title_key not in notion_props:
            notion_props[title_key] = {"title": [{"type": "text", "text": {"content": title}}]}
    else:
        notion_props = {"title": {"title": [{"type": "text", "text": {"content": title}}]}}

    # Convert markdown to blocks
    children = markdown_to_blocks(markdown) if markdown else None

    result = await notion.create_page(parent, notion_props, children, icon)
    page_id = result.get("id", "")
    url = result.get("url", "")
    return [_text(f"Seite erstellt: **{title}**\nID: `{page_id}`\nURL: {url}")]


async def _notion_update_page(
    page_id: str,
    properties: dict | None = None,
    title: str | None = None,
    icon: str | None = None,
) -> list[TextContent]:
    notion = _get_notion()

    update_props: dict = {}

    if properties:
        # Try to get schema from parent database
        page = await notion.get_page(page_id)
        parent = page.get("parent", {})
        db_id = parent.get("database_id")
        if db_id:
            schema = await notion.get_database_schema(db_id)
            update_props = to_notion(properties, schema)
        else:
            # Page properties — just set title if given
            pass

    if title:
        # Find the title property key
        page = await notion.get_page(page_id)
        for key, pv in page.get("properties", {}).items():
            if pv.get("type") == "title":
                update_props[key] = {"title": [{"type": "text", "text": {"content": title}}]}
                break

    if icon:
        # Icon needs a separate update via the page endpoint
        await notion._request("PATCH", f"/pages/{page_id}", json_body={"icon": {"type": "emoji", "emoji": icon}})

    if update_props:
        await notion.update_page(page_id, update_props)

    return [_text(f"Seite `{page_id}` aktualisiert.")]


async def _notion_append_content(page_id: str, markdown: str) -> list[TextContent]:
    notion = _get_notion()
    blocks = markdown_to_blocks(markdown)
    if not blocks:
        return [_text("Kein Content zum Anhängen.")]
    await notion.append_blocks(page_id, blocks)
    return [_text(f"{len(blocks)} Block(s) an Seite `{page_id}` angehängt.")]


async def _notion_archive_page(page_id: str) -> list[TextContent]:
    notion = _get_notion()
    await notion.archive_page(page_id)
    return [_text(f"Seite `{page_id}` archiviert.")]


# ── Notion: Databases ──────────────────────────────────────────────────

async def _notion_get_database(database_id: str) -> list[TextContent]:
    notion = _get_notion()
    db = await notion.get_database(database_id)

    # Title
    title_parts = db.get("title", [])
    title = "".join(t.get("plain_text", "") for t in title_parts)

    schema = db.get("properties", {})
    md = schema_to_markdown(schema)
    return [_text(f"## {title or 'Datenbank'}\n\n{md}")]


async def _notion_query_database(
    database_id: str,
    filter: dict | None = None,
    sorts: list | None = None,
    patient_name: str = "",
) -> list[TextContent]:
    notion = _get_notion()

    # Get DB title (for fallback)
    db_title = await notion.get_block_title(database_id)

    try:
        results = await notion.query_database(database_id, filter, sorts)
    except NotionAPIError as e:
        # Linked view fallback
        if e.status == 400 and "data sources" in e.message and db_title:
            logger.info("notion.fallback_to_central", linked_id=database_id, db_title=db_title)
            central_id = await notion.find_central_database(db_title)
            if central_id:
                results = await notion.query_database(central_id, filter, sorts)
            else:
                return [_text(f"Zentrale Datenbank '{db_title}' nicht gefunden.")]
        else:
            raise

    # Client-side patient name filter
    if patient_name and results:
        filtered = [r for r in results if _row_matches_patient(r, patient_name)]
        if filtered:
            results = filtered

    return await _format_db_results(notion, results)


async def _notion_add_entry(database_id: str, properties: dict) -> list[TextContent]:
    notion = _get_notion()
    schema = await notion.get_database_schema(database_id)
    notion_props = to_notion(properties, schema)

    result = await notion.create_page(
        parent={"database_id": database_id},
        properties=notion_props,
    )
    page_id = result.get("id", "")
    return [_text(f"Eintrag erstellt: `{page_id}`")]


async def _notion_update_entry(page_id: str, properties: dict) -> list[TextContent]:
    notion = _get_notion()

    # Get parent DB for schema
    page = await notion.get_page(page_id)
    db_id = page.get("parent", {}).get("database_id")
    if not db_id:
        return [_text("Dieser Eintrag gehört zu keiner Datenbank.")]

    schema = await notion.get_database_schema(db_id)
    notion_props = to_notion(properties, schema)
    await notion.update_page(page_id, notion_props)
    return [_text(f"Eintrag `{page_id}` aktualisiert.")]


async def _notion_delete_entry(page_id: str) -> list[TextContent]:
    return await _notion_archive_page(page_id)


# ── Helpers ─────────────────────────────────────────────────────────────

def _row_matches_patient(row: dict, patient_name: str) -> bool:
    """Check if a database row belongs to a patient (by text/title match)."""
    name_lower = patient_name.lower()
    for prop in row.get("properties", {}).values():
        ptype = prop.get("type", "")
        if ptype in ("rich_text", "title"):
            text_parts = prop.get(ptype, [])
            text = "".join(t.get("plain_text", "") for t in text_parts).lower()
            if name_lower in text:
                return True
    return False


async def _format_db_results(notion: NotionClient, results: list[dict]) -> list[TextContent]:
    """Format database query results with resolved relations."""
    if not results:
        return [_text("Keine Einträge gefunden.")]

    # Collect all relation IDs for batch resolution
    all_rel_ids: list[str] = []
    for row in results:
        for prop in row.get("properties", {}).values():
            if prop.get("type") == "relation":
                all_rel_ids.extend(r["id"] for r in prop.get("relation", []))

    resolved = await notion.resolve_relation_titles(all_rel_ids) if all_rel_ids else {}

    # Format each row
    output: list[str] = []
    for row in results:
        props = from_notion(row.get("properties", {}), resolved)
        parts = [f"  {k}: {v}" for k, v in props.items() if v]
        if parts:
            output.append("\n".join(parts))

    return [_text("\n---\n".join(output))]


def _find_title_key(schema: dict) -> str | None:
    """Find the title property name in a DB schema."""
    for key, prop in schema.items():
        if prop.get("type") == "title":
            return key
    return None


# ── Entrypoint ──────────────────────────────────────────────────────────

async def main() -> None:
    logger.info("mcp.server_starting")
    async with stdio_server() as (read_stream, write_stream):
        init_options = InitializationOptions(
            server_name="himes-tools",
            server_version="2.0.0",
            capabilities=server.get_capabilities(
                notification_options=NotificationOptions(),
                experimental_capabilities=None,
            ),
        )
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())

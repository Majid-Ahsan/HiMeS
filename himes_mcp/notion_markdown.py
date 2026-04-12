"""Bidirectional conversion between Notion API blocks and GitHub Flavored Markdown."""

from __future__ import annotations

import re
from typing import Any


# ── Notion Blocks → Markdown ───────────────────────────────────────────


def blocks_to_markdown(blocks: list[dict], indent: int = 0) -> str:
    """Convert Notion block list to GFM Markdown string."""
    lines: list[str] = []
    prefix = "  " * indent

    i = 0
    while i < len(blocks):
        block = blocks[i]
        btype = block.get("type", "")

        match btype:
            case "paragraph":
                text = _rich_text_to_md(block["paragraph"].get("rich_text", []))
                lines.append(f"{prefix}{text}")

            case "heading_1":
                text = _rich_text_to_md(block["heading_1"].get("rich_text", []))
                lines.append(f"{prefix}# {text}")

            case "heading_2":
                text = _rich_text_to_md(block["heading_2"].get("rich_text", []))
                lines.append(f"{prefix}## {text}")

            case "heading_3":
                text = _rich_text_to_md(block["heading_3"].get("rich_text", []))
                lines.append(f"{prefix}### {text}")

            case "bulleted_list_item":
                text = _rich_text_to_md(block["bulleted_list_item"].get("rich_text", []))
                lines.append(f"{prefix}- {text}")
                children = block["bulleted_list_item"].get("children", block.get("children", []))
                if children:
                    lines.append(blocks_to_markdown(children, indent + 1))

            case "numbered_list_item":
                text = _rich_text_to_md(block["numbered_list_item"].get("rich_text", []))
                lines.append(f"{prefix}1. {text}")
                children = block["numbered_list_item"].get("children", block.get("children", []))
                if children:
                    lines.append(blocks_to_markdown(children, indent + 1))

            case "to_do":
                text = _rich_text_to_md(block["to_do"].get("rich_text", []))
                checked = "x" if block["to_do"].get("checked") else " "
                lines.append(f"{prefix}- [{checked}] {text}")

            case "code":
                text = _rich_text_to_md(block["code"].get("rich_text", []))
                lang = block["code"].get("language", "")
                lines.append(f"{prefix}```{lang}")
                lines.append(f"{prefix}{text}")
                lines.append(f"{prefix}```")

            case "quote":
                text = _rich_text_to_md(block["quote"].get("rich_text", []))
                for line in text.split("\n"):
                    lines.append(f"{prefix}> {line}")

            case "callout":
                text = _rich_text_to_md(block["callout"].get("rich_text", []))
                icon = block["callout"].get("icon", {})
                emoji = icon.get("emoji", "💡") if icon.get("type") == "emoji" else "💡"
                lines.append(f"{prefix}> {emoji} {text}")

            case "divider":
                lines.append(f"{prefix}---")

            case "toggle":
                text = _rich_text_to_md(block["toggle"].get("rich_text", []))
                lines.append(f"{prefix}<details>")
                lines.append(f"{prefix}<summary>{text}</summary>")
                lines.append("")
                children = block["toggle"].get("children", block.get("children", []))
                if children:
                    lines.append(blocks_to_markdown(children, indent))
                lines.append(f"{prefix}</details>")

            case "image":
                img = block["image"]
                url = ""
                if img.get("type") == "external":
                    url = img["external"].get("url", "")
                elif img.get("type") == "file":
                    url = img["file"].get("url", "")
                caption = _rich_text_to_md(img.get("caption", []))
                lines.append(f"{prefix}![{caption}]({url})")

            case "bookmark":
                url = block["bookmark"].get("url", "")
                caption = _rich_text_to_md(block["bookmark"].get("caption", []))
                lines.append(f"{prefix}[{caption or url}]({url})")

            case "table":
                # Table rows come as children — need to be fetched separately
                # If children are embedded, render them
                children = block.get("children", [])
                if children:
                    lines.append(_render_table(children, prefix))

            case "child_page":
                title = block["child_page"].get("title", "?")
                lines.append(f"{prefix}📄 **{title}** (ID: {block['id']})")

            case "child_database":
                title = block["child_database"].get("title", "?")
                lines.append(f"{prefix}📊 **{title}** (ID: {block['id']})")

            case "file":
                file_data = block["file"]
                url = ""
                if file_data.get("type") == "external":
                    url = file_data["external"].get("url", "")
                elif file_data.get("type") == "file":
                    url = file_data["file"].get("url", "")
                caption = _rich_text_to_md(file_data.get("caption", []))
                lines.append(f"{prefix}[📎 {caption or 'Datei'}]({url})")

            case "pdf":
                pdf_data = block["pdf"]
                url = ""
                if pdf_data.get("type") == "external":
                    url = pdf_data["external"].get("url", "")
                elif pdf_data.get("type") == "file":
                    url = pdf_data["file"].get("url", "")
                lines.append(f"{prefix}[📎 PDF]({url})")

            case "embed":
                url = block["embed"].get("url", "")
                lines.append(f"{prefix}[Embed]({url})")

            case "equation":
                expr = block["equation"].get("expression", "")
                lines.append(f"{prefix}$${expr}$$")

            case "link_to_page":
                ltp = block["link_to_page"]
                pid = ltp.get("page_id", ltp.get("database_id", ""))
                lines.append(f"{prefix}🔗 Link: {pid}")

            # Skip unsupported types silently
            case _:
                pass

        i += 1

    return "\n".join(lines)


def _render_table(rows: list[dict], prefix: str) -> str:
    """Render table_row blocks as GFM pipe table."""
    if not rows:
        return ""

    table_data: list[list[str]] = []
    for row in rows:
        if row.get("type") == "table_row":
            cells = row["table_row"].get("cells", [])
            table_data.append([_rich_text_to_md(cell) for cell in cells])

    if not table_data:
        return ""

    # Header + separator + data rows
    lines = []
    header = table_data[0]
    lines.append(f"{prefix}| " + " | ".join(header) + " |")
    lines.append(f"{prefix}|" + "|".join("---" for _ in header) + "|")
    for row in table_data[1:]:
        # Pad row to header length
        while len(row) < len(header):
            row.append("")
        lines.append(f"{prefix}| " + " | ".join(row) + " |")

    return "\n".join(lines)


# ── Rich Text ↔ Markdown ──────────────────────────────────────────────


def _rich_text_to_md(rich_text: list[dict]) -> str:
    """Convert Notion rich_text array to Markdown string."""
    parts: list[str] = []
    for segment in rich_text:
        text = segment.get("plain_text", "")
        annotations = segment.get("annotations", {})
        href = segment.get("href")

        # Mentions
        if segment.get("type") == "mention":
            mention = segment.get("mention", {})
            mtype = mention.get("type", "")
            if mtype == "user":
                name = mention.get("user", {}).get("name", "User")
                text = f"@{name}"
            elif mtype == "page":
                text = f"[{text}](notion://page/{mention['page']['id']})"
                parts.append(text)
                continue
            elif mtype == "date":
                date = mention.get("date", {})
                text = date.get("start", "")
                if date.get("end"):
                    text += f" → {date['end']}"

        # Apply formatting (innermost first)
        if annotations.get("code"):
            text = f"`{text}`"
        if annotations.get("bold"):
            text = f"**{text}**"
        if annotations.get("italic"):
            text = f"*{text}*"
        if annotations.get("strikethrough"):
            text = f"~~{text}~~"
        if href and segment.get("type") != "mention":
            text = f"[{text}]({href})"

        parts.append(text)

    return "".join(parts)


def rich_text_to_markdown(rich_text: list[dict]) -> str:
    """Public alias for _rich_text_to_md."""
    return _rich_text_to_md(rich_text)


# ── Markdown → Notion Blocks ──────────────────────────────────────────


def markdown_to_blocks(markdown: str) -> list[dict]:
    """Convert GFM Markdown to Notion API block objects."""
    lines = markdown.split("\n")
    blocks: list[dict] = []
    i = 0

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Code block
        if stripped.startswith("```"):
            lang = stripped[3:].strip() or "plain text"
            code_lines: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code_lines.append(lines[i])
                i += 1
            i += 1  # skip closing ```
            blocks.append({
                "type": "code",
                "code": {
                    "rich_text": [{"type": "text", "text": {"content": "\n".join(code_lines)}}],
                    "language": lang,
                },
            })
            continue

        # Divider
        if stripped in ("---", "***", "___"):
            blocks.append({"type": "divider", "divider": {}})
            i += 1
            continue

        # Headings
        if stripped.startswith("### "):
            blocks.append(_text_block("heading_3", stripped[4:]))
            i += 1
            continue
        if stripped.startswith("## "):
            blocks.append(_text_block("heading_2", stripped[3:]))
            i += 1
            continue
        if stripped.startswith("# "):
            blocks.append(_text_block("heading_1", stripped[2:]))
            i += 1
            continue

        # To-do
        m = re.match(r"^- \[([ xX])\] (.+)$", stripped)
        if m:
            checked = m.group(1).lower() == "x"
            blocks.append({
                "type": "to_do",
                "to_do": {
                    "rich_text": _md_to_rich_text(m.group(2)),
                    "checked": checked,
                },
            })
            i += 1
            continue

        # Bulleted list
        if stripped.startswith("- ") or stripped.startswith("* "):
            blocks.append(_text_block("bulleted_list_item", stripped[2:]))
            i += 1
            continue

        # Numbered list
        m = re.match(r"^\d+\.\s+(.+)$", stripped)
        if m:
            blocks.append(_text_block("numbered_list_item", m.group(1)))
            i += 1
            continue

        # Quote
        if stripped.startswith("> "):
            quote_lines: list[str] = []
            while i < len(lines) and lines[i].strip().startswith("> "):
                quote_lines.append(lines[i].strip()[2:])
                i += 1
            blocks.append(_text_block("quote", "\n".join(quote_lines)))
            continue

        # Image
        m = re.match(r"^!\[([^\]]*)\]\(([^)]+)\)$", stripped)
        if m:
            blocks.append({
                "type": "image",
                "image": {
                    "type": "external",
                    "external": {"url": m.group(2)},
                    "caption": [{"type": "text", "text": {"content": m.group(1)}}] if m.group(1) else [],
                },
            })
            i += 1
            continue

        # Table (pipe syntax)
        if stripped.startswith("|"):
            table_rows: list[list[str]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row_text = lines[i].strip()
                # Skip separator row
                if re.match(r"^\|[\s\-:|]+\|$", row_text):
                    i += 1
                    continue
                cells = [c.strip() for c in row_text.strip("|").split("|")]
                table_rows.append(cells)
                i += 1

            if table_rows:
                width = max(len(r) for r in table_rows)
                children = []
                for row in table_rows:
                    while len(row) < width:
                        row.append("")
                    children.append({
                        "type": "table_row",
                        "table_row": {
                            "cells": [[{"type": "text", "text": {"content": c}}] for c in row]
                        },
                    })
                blocks.append({
                    "type": "table",
                    "table": {
                        "table_width": width,
                        "has_column_header": True,
                        "has_row_header": False,
                        "children": children,
                    },
                })
            continue

        # Default: paragraph
        blocks.append(_text_block("paragraph", stripped))
        i += 1

    return blocks


def _text_block(block_type: str, text: str) -> dict:
    """Create a simple text block."""
    return {
        "type": block_type,
        block_type: {"rich_text": _md_to_rich_text(text)},
    }


def _md_to_rich_text(text: str) -> list[dict]:
    """Parse inline Markdown formatting into Notion rich_text array."""
    segments: list[dict] = []

    # Regex for inline patterns: bold, italic, strikethrough, code, links
    pattern = re.compile(
        r"(?P<bold>\*\*(?P<bold_text>.+?)\*\*)"
        r"|(?P<italic>\*(?P<italic_text>[^*]+?)\*)"
        r"|(?P<strike>~~(?P<strike_text>.+?)~~)"
        r"|(?P<code>`(?P<code_text>[^`]+?)`)"
        r"|(?P<link>\[(?P<link_text>[^\]]+?)\]\((?P<link_url>[^)]+?)\))"
    )

    pos = 0
    for m in pattern.finditer(text):
        # Plain text before this match
        if m.start() > pos:
            plain = text[pos : m.start()]
            if plain:
                segments.append({"type": "text", "text": {"content": plain}})

        if m.group("bold"):
            segments.append({
                "type": "text",
                "text": {"content": m.group("bold_text")},
                "annotations": {"bold": True},
            })
        elif m.group("italic"):
            segments.append({
                "type": "text",
                "text": {"content": m.group("italic_text")},
                "annotations": {"italic": True},
            })
        elif m.group("strike"):
            segments.append({
                "type": "text",
                "text": {"content": m.group("strike_text")},
                "annotations": {"strikethrough": True},
            })
        elif m.group("code"):
            segments.append({
                "type": "text",
                "text": {"content": m.group("code_text")},
                "annotations": {"code": True},
            })
        elif m.group("link"):
            segments.append({
                "type": "text",
                "text": {
                    "content": m.group("link_text"),
                    "link": {"url": m.group("link_url")},
                },
            })

        pos = m.end()

    # Remaining plain text
    if pos < len(text):
        remaining = text[pos:]
        if remaining:
            segments.append({"type": "text", "text": {"content": remaining}})

    if not segments:
        segments.append({"type": "text", "text": {"content": text}})

    return segments


def markdown_to_rich_text(text: str) -> list[dict]:
    """Public alias for _md_to_rich_text."""
    return _md_to_rich_text(text)

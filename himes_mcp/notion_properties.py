"""Convert between simple key-value dicts and Notion API property format."""

from __future__ import annotations

import re
from typing import Any

from .notion_markdown import rich_text_to_markdown


# ── Simple dict → Notion API properties ────────────────────────────────


def to_notion(properties: dict[str, Any], schema: dict[str, Any]) -> dict[str, Any]:
    """Convert simple key-value properties to Notion API format using the DB schema.

    Example input:  {"Status": "Done", "Priority": "High", "Due": "2025-03-20"}
    Example output: {"Status": {"select": {"name": "Done"}}, ...}
    """
    result: dict[str, Any] = {}

    for key, value in properties.items():
        if key not in schema:
            continue

        prop_schema = schema[key]
        ptype = prop_schema.get("type", "")

        match ptype:
            case "title":
                result[key] = {"title": [{"type": "text", "text": {"content": str(value)}}]}

            case "rich_text":
                result[key] = {"rich_text": [{"type": "text", "text": {"content": str(value)}}]}

            case "number":
                result[key] = {"number": _to_number(value)}

            case "select":
                result[key] = {"select": {"name": str(value)}}

            case "multi_select":
                items = value if isinstance(value, list) else [v.strip() for v in str(value).split(",")]
                result[key] = {"multi_select": [{"name": str(v)} for v in items]}

            case "date":
                if isinstance(value, dict):
                    result[key] = {"date": value}
                elif isinstance(value, str) and " → " in value:
                    start, end = value.split(" → ", 1)
                    result[key] = {"date": {"start": start.strip(), "end": end.strip()}}
                else:
                    result[key] = {"date": {"start": str(value)}}

            case "checkbox":
                result[key] = {"checkbox": _to_bool(value)}

            case "url":
                result[key] = {"url": str(value)}

            case "email":
                result[key] = {"email": str(value)}

            case "phone_number":
                result[key] = {"phone_number": str(value)}

            case "status":
                result[key] = {"status": {"name": str(value)}}

            case "relation":
                ids = value if isinstance(value, list) else [value]
                result[key] = {"relation": [{"id": str(rid)} for rid in ids]}

            case "people":
                ids = value if isinstance(value, list) else [value]
                result[key] = {"people": [{"id": str(uid)} for uid in ids]}

            # Read-only / computed types — skip
            case "formula" | "rollup" | "created_time" | "last_edited_time" | \
                 "created_by" | "last_edited_by" | "unique_id" | "files":
                pass

    return result


# ── Notion API properties → simple dict ────────────────────────────────


def from_notion(
    properties: dict[str, Any],
    resolved_relations: dict[str, str] | None = None,
) -> dict[str, str]:
    """Convert Notion API properties to simple key-value strings.

    resolved_relations: mapping of page_id → title for relation properties.
    """
    result: dict[str, str] = {}
    resolved = resolved_relations or {}

    for key, prop in properties.items():
        ptype = prop.get("type", "")

        match ptype:
            case "title":
                result[key] = "".join(t.get("plain_text", "") for t in prop.get("title", []))

            case "rich_text":
                result[key] = "".join(t.get("plain_text", "") for t in prop.get("rich_text", []))

            case "number":
                num = prop.get("number")
                if num is not None:
                    result[key] = str(num)

            case "select":
                sel = prop.get("select")
                if sel:
                    result[key] = sel.get("name", "")

            case "multi_select":
                names = [s.get("name", "") for s in prop.get("multi_select", [])]
                if names:
                    result[key] = ", ".join(names)

            case "date":
                d = prop.get("date")
                if d:
                    val = d.get("start", "")
                    if d.get("end"):
                        val += f" → {d['end']}"
                    result[key] = val

            case "checkbox":
                result[key] = "Ja" if prop.get("checkbox") else "Nein"

            case "url":
                url = prop.get("url")
                if url:
                    result[key] = url

            case "email":
                email = prop.get("email")
                if email:
                    result[key] = email

            case "phone_number":
                phone = prop.get("phone_number")
                if phone:
                    result[key] = phone

            case "status":
                st = prop.get("status")
                if st:
                    result[key] = st.get("name", "")

            case "relation":
                rels = prop.get("relation", [])
                if rels:
                    names = [resolved.get(r["id"], r["id"]) for r in rels]
                    result[key] = ", ".join(names)

            case "rollup":
                rollup = prop.get("rollup", {})
                rtype = rollup.get("type", "")
                if rtype == "number":
                    num = rollup.get("number")
                    if num is not None:
                        result[key] = str(num)
                elif rtype == "array":
                    items = rollup.get("array", [])
                    vals = []
                    for item in items:
                        itype = item.get("type", "")
                        if itype == "title":
                            vals.append("".join(t.get("plain_text", "") for t in item.get("title", [])))
                        elif itype == "rich_text":
                            vals.append("".join(t.get("plain_text", "") for t in item.get("rich_text", [])))
                        elif itype == "number" and item.get("number") is not None:
                            vals.append(str(item["number"]))
                    if vals:
                        result[key] = ", ".join(vals)

            case "formula":
                formula = prop.get("formula", {})
                ftype = formula.get("type", "")
                if ftype == "string" and formula.get("string"):
                    result[key] = formula["string"]
                elif ftype == "number" and formula.get("number") is not None:
                    result[key] = str(formula["number"])
                elif ftype == "boolean":
                    result[key] = "Ja" if formula.get("boolean") else "Nein"
                elif ftype == "date" and formula.get("date"):
                    result[key] = formula["date"].get("start", "")

            case "files":
                files = prop.get("files", [])
                if files:
                    urls = []
                    for f in files:
                        if f.get("type") == "external":
                            urls.append(f["external"].get("url", ""))
                        elif f.get("type") == "file":
                            urls.append(f["file"].get("url", ""))
                        elif f.get("name"):
                            urls.append(f["name"])
                    result[key] = ", ".join(urls)

            case "people":
                people = prop.get("people", [])
                if people:
                    names = [p.get("name", p.get("id", "")) for p in people]
                    result[key] = ", ".join(names)

            case "created_time":
                result[key] = prop.get("created_time", "")

            case "last_edited_time":
                result[key] = prop.get("last_edited_time", "")

            case "created_by":
                cb = prop.get("created_by", {})
                result[key] = cb.get("name", cb.get("id", ""))

            case "last_edited_by":
                lb = prop.get("last_edited_by", {})
                result[key] = lb.get("name", lb.get("id", ""))

            case "unique_id":
                uid = prop.get("unique_id", {})
                prefix = uid.get("prefix", "")
                number = uid.get("number", "")
                if number:
                    result[key] = f"{prefix}-{number}" if prefix else str(number)

    return result


def schema_to_markdown(schema: dict[str, Any]) -> str:
    """Format a DB schema as a Markdown table for display."""
    lines = ["| Property | Typ | Optionen |", "|---|---|---|"]
    for name, prop in schema.items():
        ptype = prop.get("type", "")
        options = ""

        if ptype == "select":
            opts = prop.get("select", {}).get("options", [])
            if opts:
                options = ", ".join(o.get("name", "") for o in opts[:10])
                if len(opts) > 10:
                    options += f" (+{len(opts) - 10})"
        elif ptype == "multi_select":
            opts = prop.get("multi_select", {}).get("options", [])
            if opts:
                options = ", ".join(o.get("name", "") for o in opts[:10])
                if len(opts) > 10:
                    options += f" (+{len(opts) - 10})"
        elif ptype == "relation":
            rel = prop.get("relation", {})
            options = f"→ DB: {rel.get('database_id', '?')}"
        elif ptype == "status":
            groups = prop.get("status", {}).get("groups", [])
            all_opts = []
            for g in groups:
                all_opts.extend(o.get("name", "") for o in g.get("options", []))
            if not all_opts:
                all_opts = [o.get("name", "") for o in prop.get("status", {}).get("options", [])]
            if all_opts:
                options = ", ".join(all_opts)
        elif ptype == "formula":
            options = prop.get("formula", {}).get("expression", "")[:50]
        elif ptype == "rollup":
            r = prop.get("rollup", {})
            options = f"{r.get('function', '')} von {r.get('relation_property_name', '')}.{r.get('rollup_property_name', '')}"

        lines.append(f"| {name} | {ptype} | {options} |")

    return "\n".join(lines)


# ── Helpers ─────────────────────────────────────────────────────────────


def _to_number(value: Any) -> float | int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return value
    try:
        s = str(value).replace(",", ".")
        return float(s) if "." in s else int(s)
    except (ValueError, TypeError):
        return None


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "ja", "yes", "1", "x")
    return bool(value)

#!/usr/bin/env python3
"""Cognee-Suche aus beliebigem Working-Directory.

Laedt Cognees .env (siehe ADR-044) BEVOR cognee importiert wird, sodass
SYSTEM_ROOT_DIRECTORY/DATA_ROOT_DIRECTORY/LLM_API_KEY korrekt gesetzt sind.
Dann ruft `cognee.search(query, top_k=...)` auf und gibt das Ergebnis lesbar
(oder als JSON) aus.

SearchType weggelassen: Cognee Default (GRAPH_COMPLETION) liefert beste
Antworten fuer natural-language Queries und ist versionsstabil. Der konkrete
Import-Pfad fuer SearchType variiert zwischen Cognee-Versionen
(z.B. cognee.shared.data_models in <1.0 vs cognee.modules.search.types
in 1.0.3) — lieber gar nicht setzen und auf Default verlassen. Falls in
Schritt 7 (MCP-Server) spezifische SearchTypes noetig werden: dort als
optionalen Parameter wieder einbauen.

Beispiel:
    python pipeline/cognee_search.py "Was hat Majid heute gemacht?"
    python pipeline/cognee_search.py --query "..." --json --top-k 5
"""

from __future__ import annotations

import sys
from pathlib import Path

# Damit das Skript von ueberall aufgerufen werden kann (auch ohne PYTHONPATH).
_repo_root = Path(__file__).resolve().parent.parent
if str(_repo_root) not in sys.path:
    sys.path.insert(0, str(_repo_root))

import argparse
import asyncio
import json
import os
from typing import Any

from pipeline._cognee_env import load_cognee_env


DEFAULT_TOP_K = 10


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cognee_search",
        description="Cognee-Suche aus beliebigem Working-Directory.",
    )
    parser.add_argument(
        "query_positional", nargs="?", default=None,
        help="Such-Query (alternativ via --query)",
    )
    parser.add_argument("--query", help="Such-Query")
    parser.add_argument(
        "--cognee-dir",
        help="Cognee-Verzeichnis fuer .env-Loading (Default: $COGNEE_DIR oder /home/ali/cognee)",
    )
    parser.add_argument(
        "--top-k", type=int, default=DEFAULT_TOP_K,
        help=f"Anzahl Top-Ergebnisse (Default: {DEFAULT_TOP_K})",
    )
    parser.add_argument(
        "--json", action="store_true", dest="as_json",
        help="Output als JSON statt formatiert",
    )
    return parser


def _print_header(cognee_dir: Path) -> None:
    system_root = os.environ.get("SYSTEM_ROOT_DIRECTORY", "<nicht gesetzt>")
    if system_root != "<nicht gesetzt>":
        db_path = f"{system_root.rstrip('/')}/databases"
    else:
        db_path = "<nicht gesetzt — Cognee nutzt Default>"
    print(f"Cognee-Verzeichnis: {cognee_dir}")
    print(f"Datenbank-Pfad: {db_path}")
    print()


async def _run_search(query: str, top_k: int) -> Any:
    import cognee  # type: ignore
    return await cognee.search(query_text=query, top_k=top_k)


def _format_results(results: Any) -> str:
    if results is None:
        return "Keine Ergebnisse gefunden"
    if isinstance(results, (list, tuple)):
        if not results:
            return "Keine Ergebnisse gefunden"
        lines = []
        for i, r in enumerate(results, start=1):
            lines.append(f"[{i}] {r}")
        return "\n".join(lines)
    return str(results)


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)

    query = args.query or args.query_positional
    if not query:
        print(
            "Fehler: Bitte Query angeben (positional oder --query).",
            file=sys.stderr,
        )
        return 1

    cognee_dir = load_cognee_env(args.cognee_dir)
    _print_header(cognee_dir)

    try:
        results = asyncio.run(_run_search(query, args.top_k))
    except ModuleNotFoundError as e:
        # Nur das Top-Level-cognee-Paket maskieren wir mit einer freundlichen
        # Meldung. Sub-Modul-Fehler aus cognees Innereien werden durchgereicht
        # (voller Stack-Trace), damit der User die echte Ursache sieht.
        if e.name == "cognee":
            print(
                "Fehler: cognee Library nicht installiert. "
                "Bitte cognee-venv aktivieren.",
                file=sys.stderr,
            )
            return 1
        raise

    if args.as_json:
        try:
            print(json.dumps(results, indent=2, default=str, ensure_ascii=False))
        except (TypeError, ValueError):
            # Fallback: stringify the whole structure
            print(json.dumps(str(results), ensure_ascii=False))
    else:
        print(_format_results(results))

    return 0


if __name__ == "__main__":
    sys.exit(main())

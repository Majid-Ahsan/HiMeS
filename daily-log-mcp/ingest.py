"""Async-Wrapper für Cognee-Ingest.

STUB-Implementierung. Echte Variante (ADR-050 D8) folgt in Schritt 4
und nutzt asyncio.create_task + ingest_to_cognee.process_files() für
nicht-blockierende Indexierung.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def schedule_ingest(file_path: str) -> str:
    """STUB. Loggt nur, kein echter Ingest.

    Args:
        file_path: Absoluter Pfad zur frisch geschriebenen MD-Datei.

    Returns:
        ``"scheduled"`` — wird unverändert in ``log_daily_entry`` als
        ``ingest_status`` zurückgereicht.
    """
    logger.info("Ingest scheduled (STUB): %s", file_path)
    return "scheduled"

# Daily-Log MCP Server

Read/write MCP-Server für persönliche Daily-Logs. Schreibt schema-konforme
Markdown-Dateien (siehe `docs/memory-schema.md`) und plant Cognee-Ingest
im Hintergrund. Designentscheidungen: ADR-050.

## Topologie

T1 (separater VPS-Host-Service im Cognee-venv, Bot-Container greift via SSE
zu — analog `cognee-setup/mcp/`). Pipeline-Module (`memo_to_md`,
`ingest_to_cognee`) leben im Cognee-CWD-Kontext (ADR-044), darum kann
dieser Server nicht im Bot-Container laufen.

## Tools

| Tool | Zweck |
| --- | --- |
| `log_daily_entry` | Bereinigten Daily-Log-Eintrag als MD speichern + Ingest in Single-Queue legen (ADR-050 D8). Modi `write` (fail bei existierender Datei) oder `replace`. Returnt `extracted_hints`, `ingest_status="queued"`, `queue_position`. |
| `read_daily_log` | Existierende MD-Datei für Merge-Workflow (ADR-050 D3) lesen. Returnt `exists: False` ohne Fehler, wenn keine Datei vorhanden. |
| `list_failed_ingests` | Listet alle Daily-Logs, deren Cognee-Ingest fehlschlug. Tracking in `<data_dir>/memory/.failed_ingests.json`. |
| `retry_failed_ingests` | Legt fehlgeschlagene Ingests neu in die Queue. Optional `file_path` für Einzel-Retry, sonst alle. Erhöht `retry_count` pro Aufruf. |

## Async-Ingest

`log_daily_entry` returnt sofort nach dem MD-Schreiben. `schedule_ingest` legt
den Pfad in eine asyncio-Queue, ein Single-Worker arbeitet sie sequentiell ab
(verhindert parallele `cognee.cognify`-Calls). Der Worker beendet sich nach
60s Idle und wird beim nächsten `schedule_ingest` neu gespawnt. Jeder
Ingest-Call ist mit `asyncio.wait_for(timeout=300)` gewrappt — deckt den
158s worst-case des Cognee-Anthropic-Adapters (Memory-Note
`cognee_anthropic_max_tokens_workaround`).

Bei Fehler/Timeout/aborted: Eintrag in `.failed_ingests.json`, sichtbar via
`list_failed_ingests`, retrybar via `retry_failed_ingests`.

## Run (lokal / manueller Smoke-Test)

```bash
cd /home/ali/HiMeS                         # CWD egal — sys.path-Setup im Skript
/home/ali/cognee/.venv/bin/python \
    /home/ali/HiMeS/daily-log-mcp/server.py
```

Defaults: `127.0.0.1:8003`, Transport `sse`. Endpoint dann unter
`http://127.0.0.1:8003/sse`.

## ENV-Vars

| Variable | Default | Zweck |
| --- | --- | --- |
| `DAILY_LOG_MCP_HOST` | `127.0.0.1` | Bind-Adresse (Loopback-only by default) |
| `DAILY_LOG_MCP_PORT` | `8003` | Port |
| `DAILY_LOG_MCP_TRANSPORT` | `sse` | `sse` oder `stdio` |
| `HIMES_DATA_DIR` | `~/himes-data` | Daily-Log-Basispfad (geteilt mit `pipeline/memo_to_md.py`) |
| `COGNEE_DIR` | `/home/ali/cognee` | Cognee-Verzeichnis für `.env`-Loading (ADR-044) |

## Deploy (VPS, geplant — Schritt 9)

systemd-Unit `jarvis-daily-log.service` analog `jarvis-cognee.service` —
eigener Service, der den Server im Cognee-venv startet, Bind auf
`127.0.0.1:8003`. Caddy-Reverse-Proxy auf `daily-log-ahsan.duckdns.org`
mit `header_up Host {upstream_hostport}` (FastMCP HTTP-421-Workaround,
siehe Sektion 13a). `_ALLOWED_TOOLS` in `core/sdk_client.py` muss um
`mcp__daily-log` erweitert werden (Schritt 6, ADR-049-Pattern).

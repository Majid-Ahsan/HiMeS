# Cognee MCP Server

Read-only MCP-Server, der den Cognee-Knowledge-Graph für Jarvis abfragbar
macht. Aufklärung und Designentscheidungen siehe MASTER-REFERENCE Phase 2.1
Schritt 7.

## Topologie

T1 (separater VPS-Host-Service im Cognee-venv, Bot-Container greift via SSE
zu — analog CalDAV-Pattern). Cognee selbst läuft nicht im Bot-Container,
darum kann dieser Server auch nicht im Container laufen.

## Build

Lebt im HiMeS-Repo unter `cognee-setup/mcp/`, läuft aber im Cognee-venv
(`/home/ali/cognee/.venv` auf VPS), weil dort `cognee` installiert ist.

```bash
# Einmalig im Cognee-venv: mcp-SDK installieren (falls noch nicht da)
source /home/ali/cognee/.venv/bin/activate
pip install mcp
```

## Run (lokal / manueller Smoke-Test)

```bash
cd /home/ali/HiMeS                         # CWD egal — sys.path-Setup im Skript
/home/ali/cognee/.venv/bin/python \
    /home/ali/HiMeS/cognee-setup/mcp/server.py
```

Defaults: `127.0.0.1:8002`, Transport `sse`. Endpoint dann unter
`http://127.0.0.1:8002/sse`.

## ENV-Vars

| Variable | Default | Zweck |
| --- | --- | --- |
| `COGNEE_MCP_HOST` | `127.0.0.1` | Bind-Adresse (Loopback-only by default) |
| `COGNEE_MCP_PORT` | `8002` | Port |
| `COGNEE_MCP_TRANSPORT` | `sse` | `sse` oder `stdio` |
| `COGNEE_DIR` | `/home/ali/cognee` | Cognee-Verzeichnis für `.env`-Loading (ADR-044) |

Cognee-spezifische ENV (`LLM_API_KEY`, `SYSTEM_ROOT_DIRECTORY`,
`DATA_ROOT_DIRECTORY`, …) werden aus `<COGNEE_DIR>/.env` geladen, BEVOR
`cognee` importiert wird (siehe `pipeline/_cognee_env.py`, ADR-044).

## Deploy (VPS, geplant)

systemd-Unit analog `jarvis-caldav.service` — eigener Service, der den
Server im Cognee-venv startet, Bind auf `127.0.0.1:8002`. Reverse-Proxy
oder Bot-internes `mcp-remote` zeigt darauf. Tool-Naming für die
LLM-Tool-Liste: `mcp__cognee__cognee_search`.

`_ALLOWED_TOOLS`-Whitelist in `core/sdk_client.py` muss um den Tool-Namen
erweitert werden (ADR-027), sonst bleibt der Server für Jarvis unsichtbar.

# HiMeS — MASTER REFERENCE
> **Version:** v24 · **Stand:** 2026-04-16 · **Pfad:** `docs/MASTER-REFERENCE.md`
> **Nutzung:** `Lies docs/MASTER-REFERENCE.md und fahre fort mit Phase [X.Y]: [Task].`
> **Nach Task:** Status in dieser Datei updaten + committen.

---

## 1. AKTUELLER STATUS — LIES DAS ZUERST

**Phase:** 1.5 Stabilisierung · **6 MCP aktiv** · **VPS läuft** · **GitHub v11 (14 Commits)**

| # | Task | Status | Nächste Aktion |
|---|---|---|---|
| 1.5.1 | VPS Deployment | ✅ | — |
| 1.5.11 | Bugfixes (5 bekannte) | ✅ | Alle 5 Bugs gefixt (BUG-1 bis BUG-5) |
| 1.5.2 | Message Splitting | ⬜ | Telegram 4096 char limit |
| 1.5.3 | Error Recovery | ⬜ | Retry bei 529/503/Timeout |
| 1.5.4 | Session Cleanup | ⬜ | TTL 30min + max 5 Sessions |
| 1.5.5 | Config Sync + MCPs | 🔶 | Filesystem MCP ⬜, .gitignore ⬜, max_tool_calls sync ⬜ (Time MCP ✅) |
| 1.5.6 | MEMORY.md Init | ⬜ | Auto-Erstellung bei Startup |
| 1.5.7 | System Prompt extern | 🔶 | In prompts/system.md auslagern (Prompt selbst ✅, dynamisches Datum ✅) |
| 1.5.8 | Health Monitoring | ⬜ | Self-Check + Telegram Alert |
| 1.5.9 | Brave Search MCP | ⬜ | mcp_config.json + BRAVE_API_KEY |
| 1.5.10 | Latenz-Optimierung | ✅ | Typing-Indikator ✅ (4s-Loop), Pre-Classification ✅ (Instant Replies), claude-code-sdk Integration ✅ (persistenter Singleton-Client, Subprocess-Fallback, Daily-Restart via date.today(), ResultMessage.result als Source-of-Truth). Gemessen: Folge-Nachrichten ~15s statt ~30s, kurze Frage ohne Tool ~4s. **1.5.10e (ToolSearch-Off via env-Var) reverted — offen für 2. Anlauf mit allowed_tools-Whitelist.** |
| 1.5.12 | Rich Media Output | ✅ | Deployed+getestet: Notion-Fotos ✅, PDF/Audio/Location Parser bereit (Maps MCP fehlt noch) |
| 1.5.14 | Notion Query Bugs | ✅ | 5 Bugs: Relation-Filter, DB-Zuordnung, Query-Strategie, Fallback, Parent-Kontext |
| 1.5.15 | Kalender-Bugs | ✅ | 3 Bugs: Bestätigung nach Erstellung, Apple-Maps-Ort, ORGANIZER für Einladungen |
| 1.5.16 | Crash-Handling + Begrüßung | ✅ | Differenzierte Fehlermeldungen, Auto-Retry bei transienten Fehlern, kurze Begrüßung |
| 1.5.17 | Kalender Update + Adresse | ✅ | caldav_update_event Tool, Abkürzungen→volle Namen im Prompt, Geocoding für Adressen |
| 1.5.18 | Multi-Format I/O | ✅ | Foto/Dokument/Voice Input, Media-Output Prompt-Regel, Whisper-Caching |
| 1.5.19 | DB + VRR Nahverkehr | ✅ | Self-hosted db-rest, VRR-Produkte (U/Tram/Bus), Gleis-Fix, 1+4 Verbindungen, Telegram-Design, zuginfo.nrw, Adress-Routing |
| 1.5.20 | DB-MCP Stabilisierung + Halluzinations-Schutz | ✅ | 4 Bugs gefixt (DB-FIX-1 bis DB-FIX-4): HallucinationGuard, strukturierte Error-Dicts, Live-Status-Tool, Format-Polish |
| 1.5.21 | CalDAV Stabilität | ✅ | 3 Bugs gefixt (in caldav-mcp Repo): Starlette-SSE-Route returnt Response statt None, Phase-1.5.15-Extensions committet (Nominatim/update_event/ORGANIZER), Retry-Decorator auf 9 Apple-facing Methoden bei keepalive timeout. 95 Unit-Tests + 1 E2E-Smoke-Test, live mit injiziertem NiqConnError verifiziert. |
| 1.5.22 | Zukunfts-Architektur vorbereiten | ⬜ | Rückwärtskompatible Vorbereitungen für Phase 2: ClaudeBackend-Interface, UserContext durchreichen, MCP-Kategorisierung, Deployment-Standard. Macht Multi-User/Sub-Agents/Dynamic-MCP später ohne großes Refactoring möglich. Siehe Sektion 2a. |

**Empfohlene Reihenfolge:** ~~1.5.11~~ → ~~1.5.12~~ → ~~1.5.14~~ → ~~1.5.15~~ → ~~1.5.16~~ → ~~1.5.17~~ → ~~1.5.18~~ → ~~1.5.19~~ → ~~1.5.20~~ → ~~1.5.10~~ → ~~1.5.21~~ → **1.5.22** → 1.5.5 → 1.5.6 → 1.5.7 → 1.5.9 → 1.5.2 → 1.5.3 → 1.5.4 → 1.5.8

---

## 1a. HEUTE (2026-04-16) — WAS WURDE GEMACHT

### Phase 1.5.10 Latenz-Optimierung (komplett deployed, stabil)

- **1.5.10a Typing Indicator**: async Task alle 4s `send_chat_action("typing")`, gestoppt in `finally`. `input/telegram_adapter.py`.
- **1.5.10b Pre-Classification**: regex `_INSTANT_REPLIES` für Grüße/Danke/Bestätigungen (`^…$`-Anker) umgehen Claude komplett → <100ms Antwort für "hallo", "danke", "ok". `input/telegram_adapter.py`.
- **1.5.10c SDK-Kompatibilitätstest**: `test_sdk.py` + `test_sdk_v2.py` verifizierten Session-Persistenz von `ClaudeSDKClient` — Claude erinnerte "42" über 4 Nachrichten, Warmstart 3.32s vs Kaltstart 5.46s.
- **1.5.10d SDK-Integration**: neuer `core/sdk_client.py` mit persistentem Singleton `ClaudeSDKClient` — einmal beim Bot-Start verbinden, alle Messages teilen denselben warmen Subprocess. Feature-Flag `CLAUDE_USE_SDK_CLIENT` (default `True`). Bei jedem SDK-Fehler transparenter Fallback auf den alten `ClaudeSubprocess` (Code unverändert). Zwei Post-Deploy-Fixes: (1) `date.today()`-Vergleich statt Prompt-String-Vergleich — Uhrzeit im Prompt triggerte Reconnect pro Minute. (2) `ResultMessage.result` als Source of Truth — Claude's Denk-Zwischentexte ("Ich lade jetzt das Tool…") ausgefiltert.
- **1.5.10e ToolSearch-Off**: VERSUCHT mit `env={"ENABLE_TOOL_SEARCH":"false"}`, **REVERTED** wegen vermeintlichem False-Positive bei CalDAV — stellte sich später als 3 unabhängige CalDAV-Bugs heraus (siehe 1.5.21). **Offen für 2. Anlauf** mit explizitem `allowed_tools`-Whitelist statt env-Var.

### Phase 1.5.21 CalDAV Stabilität (komplett deployed, live-verifiziert)

Drei unabhängige Bugs im separaten `caldav-mcp` Repo:

- **Bug A — Starlette /sse Route gab `None` zurück** → `TypeError` bei jedem neuen SSE-Request (604 Exceptions in 2 Tagen Laufzeit). Tolerierbar solange `mcp-remote` im Bot-Container eine einmal etablierte SSE-Session poolte; brach bei jedem `docker compose up --build`. **Fix**: `return Response()` + `debug=False`. Commit `3802c56`.
- **Bug B — Uncommitted Phase-1.5.15-Extensions**: 420 Zeilen (Nominatim-Geocoding, `update_event`-Tool, ORGANIZER-Feld) lagen seit April 13 als `M` im VPS working-tree ungetrackt — gingen fast verloren beim Debug. Gesichert als eigener Commit `93608f1` bevor weitergearbeitet wurde.
- **Bug C — keepalive timeout**: Apple iCloud schließt idle TCP-Verbindungen nach ~60-90s; `niquests` Pool wirft dann `ConnectionError("keepalive timeout")` statt transparent zu reconnecten. **Fix**: `@retry_on_stale_connection` Decorator auf 9 Apple-facing Methoden (`list_calendars`, `create_event`, `get_events`, `get_today_events`, `get_week_events`, `get_event_by_uid`, `update_event`, `delete_event`, `search_events`). `_STALE_CONNECTION_MARKERS` walkt Exception-Chain nach `NiquestsConnectionError` oder Substring-Markers. Diskriminiert von 401/404/ValueError (die unverändert durchgereicht werden). `connect()` bewusst NICHT dekoriert (Loop-Risiko). Ein-Schuss-Retry. Commit `86ce5e3`.

**Verifikation**: 95 Unit-Tests grün (86 alt + 9 neu in `tests/test_retry.py`) + 1 E2E-Smoke-Test in `tests/e2e/test_stale_reconnect_e2e.py` mit injiziertem `NiqConnError` (Commit `45af46f`). 2 reale Telegram-Tests (Termine morgen + Wochenübersicht) + 1 Live-Reproduktion zeigt `stale_connection_detected → reconnect (635ms) → retrying → OK 1.44s gesamt`.

### Aktuelle Performance-Zahlen

| Szenario | Vorher | Jetzt |
|---|---|---|
| "Danke"/"Hallo" (Pre-Classification) | ~15s | **<0.1s** |
| Einfache Frage ohne Tool | ~15-30s | **~4s** |
| Mit einem Tool (Wetter, Things3) | ~20s | **5-10s** |
| CalDAV Tages-Übersicht (10+ Kalender einzeln) | ~30s | **~30s** (gewünscht, limitiert durch Apple-Round-Trips) |
| CalDAV Wochen-Übersicht | ~40s | **~40s** |
| DB Zug-Verbindung | ~20s | **~20s** (HAFAS intrinsisch langsam) |
| Erste Nachricht nach Bot-Start | ~30s | **~30s** (MCP Cold-Start, eager loading) |

Verbesserung **70-80%** bei normalen Nachrichten. Bei tool-lastigen Calls limitiert durch externe APIs.

### Offene Punkte aus heute

1. **caldav-mcp Remote-Strategie**: Commits `93608f1`, `3802c56`, `86ce5e3`, `45af46f` liegen nur auf VPS (`/home/ali/caldav-mcp/`). Remote ist `madbonez/caldav-mcp` (Upstream-Fork, nicht Majids). **Drei Optionen**:
   - **A** Eigenes Fork auf `Majid-Ahsan/caldav-mcp`, Remote umstellen, pushen — **empfohlen**
   - B Als git-Submodule in HiMeS einbinden
   - C `vendor/caldav-mcp/` in HiMeS einchecken
   
   Morgen entscheiden.

2. **`docs/himes-dashboard.html`**: Untracked seit Tagen, Herkunft unklar. Committen oder in `.gitignore`?

3. **Phase 1.5.10e zweiter Anlauf**: ToolSearch-Overhead (5-7s pro Tool-Call) eliminierbar. Jetzt wo CalDAV stabil ist wieder machbar. Diesmal mit explizitem `allowed_tools`-Whitelist statt `ENABLE_TOOL_SEARCH`. Nicht kritisch — kann warten.

---

### Bekannte Bugs (Phase 1.5.11)

| # | Bug | Schwere | Vermutete Ursache |
|---|---|---|---|
| BUG-1 | ~~CalDAV lädt nicht alle Termine~~ | ✅ FIXED | System Prompt: JEDEN Kalender einzeln abfragen, Schritt-für-Schritt erzwungen |
| BUG-2 | ~~Things 3 erstellt Cron-Jobs statt echte Tasks~~ | ✅ FIXED | System Prompt: KRITISCHE Regel — CronCreate/TodoWrite explizit verboten |
| BUG-3 | ~~himes-memory MCP Status "failed"~~ | ✅ FIXED | NotificationOptions()+Rename himes-tools, PTY stdin fix |
| BUG-4 | ~~cost_usd=0.0 immer~~ | ✅ FIXED | Feld war `total_cost_usd` statt `cost_usd` — korrigiert |
| BUG-5 | ~~Antwortet manchmal auf Englisch~~ | ✅ FIXED | System Prompt: explizite Sprachregeln, Tool-Ergebnisse auf Deutsch formulieren |

### Notion Query Bugs (Phase 1.5.14)

| # | Bug | Schwere | Fix |
|---|---|---|---|
| NOTION-1 | ~~Falsche Daten-Zuordnung (21 statt 3 Diagnosen)~~ | ✅ FIXED | System Prompt: Zentrale DBs IMMER mit Relation-Filter, nie ungefiltert |
| NOTION-2 | ~~Leeres Ergebnis bei falscher DB~~ | ✅ FIXED | System Prompt: DB-Zuordnung (zentral vs. patientenspezifisch) definiert |
| NOTION-3 | ~~Inkonsistente Query-Strategie~~ | ✅ FIXED | System Prompt: Deterministische 3-Schritt-Strategie erzwungen |
| NOTION-4 | ~~Kein Fallback bei leerem Ergebnis~~ | ✅ FIXED | server.py: Hinweis mit DB-Typ-Empfehlung + Fallback-Kette im Prompt |
| NOTION-5 | ~~DB-Listing ohne Patienten-Zuordnung~~ | ✅ FIXED | server.py: Parent-Page-Titel wird aufgelöst und angezeigt |

### Kalender-Bugs (Phase 1.5.15)

| # | Bug | Schwere | Fix |
|---|---|---|---|
| KAL-1 | ~~Keine Bestätigung nach Terminerstellung~~ | ✅ FIXED | EventCreationResult erweitert: location, description, attendees, reminders_count im Return |
| KAL-2 | ~~Ort nicht klickbar in Apple Kalender~~ | ✅ FIXED | Auto-Geocoding (Nominatim), GEO-Property + aufgelöste Adresse in LOCATION. X-APPLE-STRUCTURED-LOCATION entfernt (iCloud escaped Komma in geo-URI). iPhone zeigt Karte+Pin. |
| KAL-3 | ~~Einladungen an Teilnehmer funktionieren nicht~~ | ✅ FIXED | ORGANIZER-Feld + METHOD:REQUEST im VCALENDAR, Env-Vars CALDAV_ORGANIZER_EMAIL/NAME |

### DB-MCP Stabilisierung (Phase 1.5.20)

| # | Bug | Schwere | Fix |
|---|---|---|---|
| DB-FIX-1 | ~~Sporadischer "MCP nicht verfügbar"-Fehler~~ | ✅ FIXED | rest_client.py: `_robust_get()` mit strukturierten Error-Dicts `{ok, error, user_message_hint, retry_suggested, status_code, detail}`. Alle public Methoden retournieren Dict statt zu raisen. Tools in server.py forwarden `user_message_hint` verbatim. MCP_FAILED ErrorType + retryable. |
| DB-FIX-2 | ~~Halluzinierte Zugdaten bei Tool-Fehlern~~ | ✅ FIXED | `core/hallucination_guard.py` (HallucinationGuard Klasse, modular, soft-check). Registriert DB-Domain (Patterns: RE/S/U/Bus/Gleis/Verspätung/Gleiswechsel; Tool-Prefixes: mcp__deutsche-bahn__). Trigger-Fall: Patterns matchen + kein DB-Tool in Turn aufgerufen → Disclaimer anhängen + Warning-Log (niemals Text rewriten). SYSTEM_PROMPT-Regel: NIEMALS konkrete Zugdaten erfinden, Tool-Errors wortwörtlich übernehmen. |
| DB-FIX-3 | ~~Formatierungs-Inkonsistenzen (⬅️ verwirrt, irrelevante Baustellen)~~ | ✅ FIXED | `_format_journey_row` ohne `⬅️`/`▶️`, stattdessen Prefix-Zeile `↩ frühere Alternativen:` + immer ━━━ Separator. `_is_remark_relevant()` filtert Remarks nach Zeit-Fenster (±30min Toleranz) und Stations-Matching (Off-Route-Hinweise wie "Bauarbeiten Aachen-Stolberg" bei Mülheim-Dortmund werden gedroppt). |
| DB-FIX-4 | ~~Live-Status-Queries halluziniert (RE1 wo gerade, Verspätung erfunden)~~ | ✅ FIXED | Neues Tool `db_train_live_status(line, station="Mülheim Hbf", duration=120)`. Flow: departures mit `line_name`-Filter → tripId → `/trips/:id` für Live-Daten (Verspätung, aktuelles Gleis vs. planned, Gleisänderungen mit 🔀, nächster Halt, GPS-Position wenn verfügbar, Ausfall-Erkennung). Graceful Fallback auf Departure-Daten wenn /trips/:id failed. |
| DB-FIX-5a | ~~Guard False-Positive auf Refusal-Text ("U18... kein Tool")~~ | ✅ FIXED | `HallucinationGuard._is_near_negation()`: prüft ±150 Zeichen um Pattern-Match auf Negations-Phrasen ("kein Tool", "nicht verfügbar", "empfehle", "DB Navigator" etc.). Match in Refusal-Kontext → zählt nicht als Claim. Eigene Disclaimer-Text triggert nicht re-entrant. |
| DB-FIX-5b | ~~Claude nutzt ToolSearch statt direkt DB-MCP-Tool bei pending-Status~~ | ✅ FIXED | SYSTEM_PROMPT erweitert: alle 9 DB-Tools explizit mit vollem Namen `mcp__deutsche-bahn__*` aufgelistet. Anweisung: "DB-Tools sind NICHT deferred, IMMER direkt aufrufen, auch bei pending-Status. KEIN ToolSearch!" |
| DB-FIX-5c | ~~Downstream-Remarks (Dortmund↔Hamm bei Mülheim→Dortmund) nicht gefiltert~~ | ✅ FIXED | `_is_remark_relevant()` um `final_destination`-Param erweitert. Regex-Pattern "zwischen X und Y": wenn X oder Y = final destination UND der andere NICHT auf Route → downstream, droppen. |
| DB-FIX-6a | ~~Guard False-Positive bei langen Refusal-Texten (S3 3× erwähnt, letzte außerhalb ±150 Zeichen Negation)~~ | ✅ FIXED | 2-Tier Negation: Tier 1 `_GLOBAL_REFUSAL_MARKERS` (Short-Circuit wenn Text "nicht verfügbar"/"DB Navigator App"/"dafür habe ich kein"/unser eigener Disclaimer-Sentinel enthält — ganze Message → Refusal → skip). Tier 2 bleibt lokaler ±150-Zeichen-Check. False-Negatives > UX-zerstörende Disclaimer. |
| DB-FIX-6b | ~~Claude refused "wo ist S3 jetzt" mit "Tools nicht verfügbar" (MCP pending, Tools nicht in Claude's Tool-Liste)~~ | ✅ FIXED | `ClaudeResponse.pending_mcps` Feld. Orchestrator erkennt Pattern (pending_mcps + 0 tool_calls + Refusal-Text via `_TOOL_REFUSAL_MARKERS`) → Auto-Retry 1× mit frischer Session + 2s Pause (MCPs haben Zeit fertig zu starten). Transparent für User. |
| DB-FIX-7a | ~~Smart-Split zeigte nur 1 Verbindung statt 1+4 (VRR-Lokalbusse: HAFAS gab alle 10 im -45min-Fenster zurück, "after"-Bucket leer)~~ | ✅ FIXED | Zwei separate Queries statt einer: (1) "after" mit `departure=requested`, `results=5`, filter `>=requested`, take 4. (2) "before" mit `departure=requested-20min`, `results=4`, filter `<requested`, take 1. Dedupe via refreshToken. Before-Query-Fehler = graceful Fallback ohne earlier-Zeile. |
| DB-FIX-7b | ~~"📍 Snapshot ab Mülheim Hbf" verwirrend (User fragte "was bedeutet Snapshot")~~ | ✅ FIXED | Umbenannt zu "📍 Abfahrtsstation: Mülheim Hbf" in `_format_live_status` und Fallback-Formatter. |

**Latenz-Problem (10-20s pro Request):**
```
PTY spawn ~1-2s + CLI Kaltstart ~3-5s + MCP Warmup ~2-4s + API Denkzeit ~3-8s = 10-20s
→ Mit persistentem Prozess (1.5.10): nur noch ~4-9s
```

---

## 2. ARCHITEKTUR

```
Telegram → Identity → Mega-Agent (Orchestrator)
                            ↓
               ┌────────────┼────────────┐
          Research Agent  Task Agent  Custom Agent (dynamisch)
               └────────────┼────────────┘
                            ↓
                Tool Layer (MCP + Skills)
      Time · Filesystem · Things3 · CalDAV · Memory · Brave · Gmail · HA · ...
                            ↓
          ┌─────────────────┼─────────────────┐
     Short-term          Mid-term          Long-term
     MEMORY.md        Cognee Graph      SQLite + Markdown
          └─────────────────┼─────────────────┘
                            ↓
          Dream Phase (Cron 03:00 + Threshold) ←→ Self-Improvement (Reflexion Loop)
                            ↓
                    Eval System (Tests)
```

---

## 2a. ZUKUNFTS-ARCHITEKTUR — Phase 1.5.22

**Problem-Kontext:**
Die aktuelle Architektur (Singleton `SDKClient`, alle MCPs eager loaded, anonyme Nachrichten) ist für Single-User (Majid) optimal, blockiert aber Phase-2-Features:

- **Phase 2.5 (Dream Phase)**: Dream-Background-Job konkurriert mit User um den einen Client
- **Phase 2.6 (Sub-Agents)**: Kein paralleles Spawnen möglich — alles durch den Singleton-Lock serialisiert
- **Phase 2.9 (Dynamic MCP)**: Alle MCPs immer geladen → bei 20+ MCPs Cold-Start ~30s, auch wenn Nachricht nur einen MCP braucht
- **Phase 2.10 (Multi-User)**: Client geteilt, Lock serialisiert User, Context/Memory gemischt

**Lösung: 3 rückwärtskompatible Vorbereitungen jetzt stellen, nicht Phase 2 neu bauen.**

### Vorbereitung 1 — `ClaudeBackend` Protocol

Abstraktes Interface einführen, `SDKClient` darauf anpassen. Kein Funktions-Change, nur Shape.

```python
# core/backends/base.py
from typing import Protocol, AsyncGenerator

class ClaudeBackend(Protocol):
    async def start(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def process_message(
        self,
        user_id: str,           # Multi-User ready (Phase 2.10)
        session_id: str,        # Pro User/Agent getrennte Sessions
        user_message: str,
        system_prompt: str,
        agent_type: str = "default",  # Sub-Agents (Phase 2.6)
    ) -> AsyncGenerator[Event, None]: ...
```

`SingletonSDKBackend` = aktueller `SDKClient` mit diesem Interface (ignoriert `user_id`/`agent_type` erstmal).
Später: `PoolSDKBackend`, `AgentSDKBackend`.

**Aufwand**: 1-2 Stunden. **Gewinn**: Implementierung austauschbar ohne Orchestrator-Change.

### Vorbereitung 2 — `UserContext` durchreichen

```python
@dataclass
class UserContext:
    user_id: str              # telegram_chat_id als String (stable identifier)
    display_name: str         # "Majid"
    telegram_chat_id: int
    preferences: dict = field(default_factory=dict)
```

`UserContext` in `telegram_adapter` bauen, durch Orchestrator bis zum Backend reichen. Logik darf erstmal `user_id` ignorieren (Single-User bleibt funktional identisch).

**Aufwand**: 2-3 Stunden. **Gewinn**: Phase 2.10 braucht keine Code-Rewrites — nur Logik umflippen.

### Vorbereitung 3 — MCP-Kategorisierung

`mcp_config.json` strukturieren nach Kategorien, auch wenn heute alle immer geladen werden:

```json
{
  "categories": {
    "core":     ["time", "himes-tools"],
    "personal": ["caldav", "things3"],
    "transport":["deutsche-bahn"],
    "home":     ["weather", "home-assistant"],
    "medical":  []
  },
  "mcpServers": { /* unverändert */ }
}
```

Settings-Flag `MCP_LAZY_LOADING: bool = False` hinzufügen (default = alle laden wie bisher). Wenn in Phase 2.9 Lazy-Loading aktiviert wird, entscheidet die Nachricht welche Kategorien aktiv sind.

**Aufwand**: 1 Stunde. **Gewinn**: Skalierung auf 20+ MCPs ohne Cold-Start-Explosion.

### Vorbereitung 4 — Deployment-Standard dokumentieren

Aktuell gemischt: docker-compose (HiMeS, db-rest), systemd (jarvis-caldav), npm (mcp-remote), Caddy. Für Phase 2 werden mehr Services dazukommen (Cognee/Qdrant, Scheduler für Dream Phase, Whisper-Service, Skill-Repo).

Entscheidung treffen und in einem ADR dokumentieren:

- **Option A** — Alles nach docker-compose migrieren (auch jarvis-caldav containerisieren)
- **Option B** — Bleiben wie aktuell, aber klare Trennung: "docker-compose für stateful Services, systemd für langlaufende Prozesse, npm für Node-basierte"
- **Option C** — Kubernetes (overkill für Single-Host, aber zukunftssicher)

**Empfehlung A**. Ein einziges `docker-compose.yml`, alle Services, gemeinsame Logs, gemeinsames Netzwerk. `jarvis-caldav` wird zu einem Container.

**Aufwand**: ADR schreiben = 30 Min. Migration `jarvis-caldav` → Docker = 2-3 Stunden (optional, kann auch später).

**Wichtig**: Diese 4 Vorbereitungen machen **nichts langsamer, nichts kaputt, keine Feature-Änderung**. Sie sind Investment in die Zukunft. Phase 2.1-2.5 (Cognee, Dream, Audio) können ohne sie gebaut werden — aber ab Phase 2.6 (Sub-Agents) sind sie nötig.

---

## 3. TECH STACK

Python 3.11 · Claude Code CLI (stream-json Subprocess) · python-telegram-bot · aiohttp · asyncio · Docker + docker-compose (himes + db-rest) · Hetzner VPS · Pydantic BaseSettings · structlog · openai-whisper (lokal) · derhuerst/db-rest:6 (self-hosted HAFAS)

**CLI Flags:**
```bash
# PTY nur auf stdin (pty.openpty()), stdout/stderr als saubere PIPE
claude --output-format stream-json --dangerously-skip-permissions \
  --mcp-config /path/to/mcp_config.json --verbose \
  --model MODEL --max-turns 25 --system-prompt "..." \
  --resume SESSION_ID --print 'USER_MESSAGE'
```
- `pty.openpty()` statt `script` Wrapper (kein ANSI/Line-Wrap-Corruption)
- `--dangerously-skip-permissions` (ersetzt acceptEdits + allowedTools)
- `--max-turns 25` (erhöht von 10, für komplexe Notion-Abfragen)
- Session-ID aus `system` Event · Failed Sessions NICHT resumed
- `result` Event als Text · `error_max_turns` Handling · OAuth via `CLAUDE_CODE_OAUTH_TOKEN` env
- System Prompt mit dynamischem Datum (Wochentag + Datum live) + Notion-Struktur

---

## 4. DATEISTRUKTUR

```
himes/
├── docker-compose.yml · Dockerfile · requirements.txt
├── .env · .env.example · .gitignore
├── docs/MASTER-REFERENCE.md        ← diese Datei
├── config/settings.py · mcp_config.json
├── prompts/system.md               ← System Prompt (extern, hot-reload)
├── input/telegram_adapter.py       ← Text/Voice/Photo Handler + Rich Media Output
├── input/media_parser.py           ← Erkennt Bilder/PDFs/Audio/Locations/Buttons in Antworten
├── himes_mcp/                      ← HiMeS Tools MCP (14 Tools)
│   ├── server.py                   ← MCP Server + Tool-Handler
│   ├── notion_client.py            ← Notion API Client (retry, pagination, cache)
│   ├── notion_markdown.py          ← Markdown ↔ Notion Blocks Konvertierung
│   ├── notion_properties.py        ← Property-Konvertierung (Key-Value ↔ Notion API)
├── himes_db/                       ← Deutsche Bahn + VRR MCP (FastMCP, stdio)
│   ├── server.py · rest_client.py · timetable_client.py · zuginfo_client.py
├── core/orchestrator.py · claude_subprocess.py · hallucination_guard.py
├── tests/                          ← Unit + Integration Tests (pytest + respx)
│   ├── conftest.py · test_rest_client.py · test_hallucination_guard.py
│   └── test_server_tools.py · test_format_polish.py
├── pytest.ini · requirements-dev.txt
├── skills/                         ← Phase 2: Self-evolving Skills
├── evals/                          ← Phase 2: Eval System
├── data/MEMORY.md                  ← Short-term Memory
└── logs/
```

---

## 5. MCP-KATALOG

### Aktiv (6)

| Server | Transport | Tools | Status |
|---|---|---|---|
| HiMeS Tools | stdio Python | memory (2) + notion (12): search, read_page, create_page, update_page, append_content, archive_page, list_children, get_database, query_database, add_entry, update_entry, delete_entry | ✅ |
| Things 3 | SSE | create_task, list_today, complete_task | ✅ |
| CalDAV | SSE | create_event, update_event, delete_event, get_events, search (+ Auto-Geocoding, ORGANIZER) | ✅ |
| Time | stdio Python | current_time, convert_time (Europe/Berlin) | ✅ |
| Weather | stdio TS | forecast, current_conditions, alerts | ✅ |
| Deutsche Bahn + VRR | stdio Python | db_search_connections (1+4 Verbindungen, alle Verkehrsmittel, Adressen+POIs), db_departures, db_arrivals, db_find_station, db_nearby_stations, db_trip_details, db_pendler_check, **db_train_live_status** (Live-Tracking: Verspätung, aktuelles Gleis, Gleiswechsel, nächster Halt), db_nrw_stoerungen (zuginfo.nrw) + 3 Timetable-API-Tools (optional). Strukturierte Error-Dicts + HallucinationGuard. | ✅ |

### Nächste (KRITISCH → HOCH)

| Server | Prio | Transport | API-Key | Zweck |
|---|---|---|---|---|
| Filesystem | KRITISCH | stdio TS | Nein | Skills/Logs/Configs lesen+schreiben |
| Brave Search | KRITISCH | stdio TS | Ja (2000/Mo free) | Web-Suche, Faktencheck |
| Telegram MCP | HOCH | stdio Python | Ja | Voller MTProto-Zugriff |
| Gmail | HOCH | SSE/HTTP TS | Ja (OAuth) | Inbox, Drafts, senden |
| Reminder | HOCH | stdio/HTTP TS | Ja | Erinnerungen planen |
| Google Maps | HOCH | stdio TS | Ja | Routen, Places, Entfernungen |
| ~~Deutsche Bahn~~ | ~~HOCH~~ | ~~stdio/SSE~~ | ~~Ja~~ | ✅ Implementiert (himes_db) |
| Home Assistant | HOCH | SSE/HTTP Python | Ja (Token) | Smart Home steuern |
| CardDAV (dav-mcp) | HOCH | stdio TS | Nein (iCloud Auth) | Kontakte lesen/erstellen/suchen via iCloud CardDAV. Für: Visitenkarten, Kontaktkarten, "Wie ist Nedas Nummer?" |
| Google Drive | HOCH | SSE/HTTP TS | Ja (OAuth) | Dateien suchen/hochladen/organisieren. Für: Dokument-Ablage, Personal Vault, "Schick mir mein Dokument X" |

### Später (MITTEL → OPTIONAL)

WhatsApp (Twilio) · Exa Search · Firecrawl · Spotify · Currency (Frankfurter) · GitHub · SQLite (→Phase 2.2) · iMessage · Slack · Azure Translator · Whisper (→Phase 2.4) · TTS ElevenLabs · Apify

**Regeln:** stdio = im Docker-Container · SSE = separat/extern · API-Keys in `.env` · Neue Server in `mcp_config.json`

---

## 6. PERSÖNLICHE KONFIGURATION

### Majid (Hauptnutzer)
Majid Ahsan · geb. 23.07.1985 · Am Rathaus 15, 45468 Mülheim an der Ruhr · Facharzt Kardiologie (FA 2023) · Arbeitsort: St. Johannes Hospital, Dortmund · Pendel: Mülheim Hbf → Dortmund Hbf · Interessen: KI, Mathematik, Smart Home · Lernzeit: 30-60 min/Tag + Kardiologie-Podcasts im Arbeitsweg · Zeitzone: Europe/Berlin

### Neda (Ehefrau)
Neda Naghavi · geb. 07.07.1985 · Assistenzärztin Gynäkologie · Arbeitsort: Marienhospital Bottrop

### Kinder
Taha Ahsan · geb. 21.10.2012 · Gymnasium Otto-Pankok-Schule · Klavier 6 Jahre (1h/Tag) · Schwimmverein 3x/Woche · Spanisch
Hossein Ahsan · geb. 17.07.2018 · Städt. Grundschule am Saarnberg

### Geburtstage
Neda 7. Juli · Hossein 17. Juli · Majid 23. Juli · Taha 21. Oktober

### Kalender-Zuordnung

| Kalender | Zweck | Zugriff |
|---|---|---|
| Majid's Appointments | Persönliche Termine | Schreiben |
| Majid's Work | Arbeit, Dienste (ZNA, Visitendienst) | Schreiben |
| Health | Arzttermine ganze Familie | Schreiben |
| Neda's Appointments / Work | Nedas Termine | Schreiben |
| Hossein's Appointments | Hosseins Termine | Schreiben |
| Taha's Appointments | Tahas Termine (Schule, Klavier, Schwimmen) | Schreiben |
| My Calendar | Auffang (Apple Events etc.) | Schreiben |
| Parties | Einladungen | Schreiben |
| Ali's Appointments | Schwager Ali, Kinderbetreuung, Bürotage | Nur lesen |
| German Class · Reminders | — | Ignorieren |

**Intelligenz:** Health-Keywords (Arzt, Dr., Impfung) → Health-Kalender VOR Personennamen. "Zahnarzt Hossein" → Health, nicht Hossein's.

### Sprachregeln
- Telegram: in der Sprache die Majid schreibt (DE/EN/FA)
- Things 3: immer Deutsch
- Eigennamen/Abkürzungen (EACVI, EKG, CT, MRT) nie übersetzen

### Standorte
| Zweck | Ort |
|---|---|
| Zuhause / Wetter | Am Rathaus 15, 45468 Mülheim an der Ruhr |
| Arbeit Majid | St. Johannes Hospital, Dortmund |
| Arbeit Neda | Marienhospital Bottrop |
| DB Heimat → Arbeit | Mülheim (Ruhr) Hbf → Dortmund Hbf |

---

## 7. PHASE 1 — ERLEDIGT

1. requirements.txt · docker-compose.yml · Dockerfile (Python 3.11, Node.js 20, Claude CLI, non-root)
2. config/settings.py (Pydantic) · mcp_config.json (6 MCP Server)
3. input/telegram_adapter.py · himes_mcp/server.py · core/orchestrator.py · core/claude_subprocess.py
4. Proaktiver System Prompt (Tool-Crossover) · Dynamisches Datum · MCP Health Check
5. --dangerously-skip-permissions · OAuth Fix · Deploy-Workflow (rsync + docker compose)
6. GitHub v1-v3 gepusht · 26+ Bugfixes

---

## 8. PHASE 2 — GEPLANT

| # | Feature | Abhängig von | MCP benötigt | Beschreibung |
|---|---|---|---|---|
| 2.1 | Cognee | — | — | Mid-term Memory (Knowledge Graph) |
| 2.2 | Long-term DB | — | SQLite | Persistente Rules, Patterns, Profile |
| 2.3 | Model Selection | — | — | Haiku/Sonnet/Opus dynamisch |
| 2.4 | Audio-Tagebuch | 2.1 | Whisper | Whisper → Extraktion → Cognee |
| 2.5 | Dream Phase | 2.1, 2.2 | — | Cron 03:00 + Threshold (>10KB) |
| 2.6 | Sub-Agents | 2.3 | — | Dynamisch spawnen |
| 2.7 | Self-Improvement | 2.1, 2.5 | Filesystem | Reflexion Loop + Skill Evolution |
| 2.8 | Eval System | 2.7 | — | Tests + Benchmarks + Rollback |
| 2.9 | Dynamic MCP | 2.6 | GitHub | Tools erkennen + installieren |
| 2.10 | Multi-User | 2.2 | — | /users/{id}/ |
| 2.11 | Morning Report | — | Time, Weather, CalDAV, Things3 | 06:00 Telegram: Wetter+Termine+Tasks+Bahn |
| 2.12 | Telegram Mini App | 2.11 | — | PWA in Telegram für Rich UI: Dashboards, Kalender, Task-Board, Settings. Telegram bleibt Chat, Mini App für visuelle Interaktion |
| 2.13 | Intelligent Document Processing | — | CardDAV, Google Drive | Foto/PDF → automatisch handeln: Dienstplan→Kalender, Visitenkarte→Kontakt, Arztbrief→Notion+Kalender, Rechnung→Google Drive. Claude Vision eingebaut |
| 2.14 | Personal Vault | — | Google Drive | iCloud↔Google Drive Sync + Google Drive MCP = universeller Dateizugriff. "Schick mir meinen Personalausweis" → sucht in Drive → sendet per Telegram |

Parallel: HOCH-MCPs einrichten (Gmail, Google Drive, CardDAV, Maps, HA)

---

## 9. PHASE 3 — VISION

Weitere Inputs (WhatsApp, iMessage, Voice) · Bildverarbeitung · Voice I/O (Whisper+TTS) · Claude API Migration evaluieren · Medien (Spotify, Apify)

---

## 10. SELF-IMPROVEMENT (Phase 2.7)

**Prinzip:** `[Task] → [Evaluieren] → [Skill updaten/erstellen] → [Repeat]`

**Skill Library** (`/skills/`): Jeder Task = eine .md Datei mit Ausführungsstil, Patterns, optimierte Prompts, Erfolgsrate.
**Reflexion Loop:** Erfolg → Metriken updaten. Fehlschlag → Prompt rewriten. Kein Match → neuen Skill erstellen.
**Skill Router:** Wählt nach Verhalten (nicht Semantik), lernt aus Feedback.
**Dream Phase:** Nächtlich Skills mit niedriger Rate überarbeiten, neue Patterns konsolidieren.

---

## 11. EVAL SYSTEM (Phase 2.8)

**Code Eval:** pytest, Integration Tests, MCP Tool Tests, Docker Build, Smoke Test.
**Skill Eval:** A/B neue vs. alte Version, Rollback bei Verschlechterung.
**Agent Eval:** Benchmark-Tasks, Response-Qualität, Latenz, Cost-Tracking.

---

## 12. DESIGN-PRINZIPIEN

Async throughout · Kein Hardcoding (.env) · Logging (structlog) · Circuit Breaker (max 25 turns, max_tool_calls) · Docker-ready · Modular · MCP-basiert · System Prompt extern · Health Monitoring · Eval-gated

---

## 13. ADR (Architektur-Entscheidungen)

| # | Entscheidung | Status |
|---|---|---|
| 001 | Claude Code CLI statt API (Session-Mgmt, MCP OOTB) | Aktiv |
| 002 | Things 3 für Tasks (MCP stabil) | Aktiv |
| 003 | Markdown Memory (einfach, Claude-freundlich) | Aktiv |
| 004 | Docker (reproduzierbar, isoliert) | Aktiv |
| 005 | Hetzner VPS (24/7, günstig) | Aktiv |
| 006 | stream-json (programmatisch parsbar) | Aktiv |
| 007 | System Prompt als externe Datei | Geplant |
| 008 | Dream Phase: Cron + Threshold | Geplant |
| 009 | Claude API langfristig evaluieren | Phase 3 |
| 010 | Time + Filesystem als KRITISCH | Phase 1.5 |
| 011 | Persistenter CLI-Prozess | Phase 1.5 |
| 012 | pty.openpty() statt script-Wrapper (kein JSON-Corruption) | Aktiv |
| 013 | ~~Hybrid Notion: easy-notion-mcp + custom Tools~~ → Ersetzt durch ADR-014 | Ersetzt |
| 014 | Notion Native: eigener Python-Client statt easy-notion-mcp (14 Tools, Relation-Auflösung, Schema-Cache, Markdown I/O, keine externe Dependency) | Aktiv |
| 015 | 3-Layer Memory: Short-term MEMORY.md + Mid-term Cognee Graph + Long-term Rules. Skaliert besser als flaches 2-Dateien-System, semantischer Graph baut Beziehungen auf, Rules ändern sich selten | Geplant |
| 016 | Google Drive als Dateispeicher statt iCloud-Direktzugriff. iCloud hat keine API, Google Drive MCP existiert, iCloud↔Drive Sync als Brücke | Geplant |
| 017 | DB self-hosted + VRR: derhuerst/db-rest:6 im Docker-Network (Primary) mit v6.db.transport.rest (Fallback). Alle Produkte explizit aktiviert (subway, tram, bus). Journey-Plattformen via departurePlatform/arrivalPlatform. Telegram-optimiertes Output mit Emojis. zuginfo.nrw für NRW-Störungen. Adress-Routing: resolve_location() (Stationen+Adressen+POIs), journeys mit from.type=location für Nicht-Stationen | Aktiv |
| 018 | Strukturierte Tool-Error-Dicts statt Exception-Propagation: `{ok, error, user_message_hint, retry_suggested, status_code, detail}`. Ersetzt generische "Fehler bei..." Meldungen durch ready-to-use deutsche Hints die Claude verbatim durchreicht → Halluzinations-Reduktion | Aktiv |
| 019 | Hallucination Guard als Defense-in-Depth: Prompt-Regel (primary) + Regex-Pattern-Guard (safety net). Modulare Domain-Registration (DB, später Kalender/Notion/Weather). Soft-Guard — niemals Text rewriten, nur Disclaimer anhängen + Warning-Log, damit False-Positives nicht UX zerstören | Aktiv |

---

## 14. PROMPT-TEMPLATES

### Phase 1.5.12 — Rich Media Output
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.12 — Rich Media Output für Telegram.

Problem: HiMeS kann nur Text an Telegram senden. Bilder, Dokumente, Standorte werden als URL-Text angezeigt statt als echte Medien.

Aufgabe — telegram_adapter.py erweitern:

1. ANTWORT-PARSER: Bevor die Antwort an Telegram gesendet wird, parse den Text auf:
   - Bild-URLs (.jpg, .jpeg, .png, .gif, .webp) → send_photo()
   - Notion-Bilder (secure.notion-static.com, prod-files-secure) → send_photo()
   - PDF-URLs (.pdf) → send_document()
   - Google Maps Links → Koordinaten extrahieren → send_location()
   - Standort-Erwähnungen mit Koordinaten → send_location()
   - Audio-URLs (.mp3, .ogg, .wav) → send_audio()

2. MIXED CONTENT: Eine Antwort kann Text + Medien enthalten.
   Beispiel: "Hier ist das Bild aus deiner Notion-Seite: https://...image.png"
   → Sende zuerst den Text (ohne URL), dann das Bild als send_photo()
   → Wenn nur eine URL ohne Text: nur das Medium senden

3. INLINE BUTTONS (Bonus): Wenn Claude Optionen vorschlägt ("Soll ich A oder B?"),
   erkenne das Pattern und sende InlineKeyboardMarkup mit Buttons statt Text.
   User tippt auf Button → Antwort wird als neue Nachricht gesendet.

4. FEHLERBEHANDLUNG:
   - URL nicht erreichbar → Fallback: URL als klickbaren Link senden
   - Bild zu groß (>10MB Telegram Limit) → als Dokument senden
   - Timeout beim Download → Link senden mit Hinweis

5. CAPTION: Wenn Text + Bild zusammen kommen, nutze caption-Parameter
   von send_photo() statt separater Textnachricht (sauberer).

Teste mit:
- "Zeig mir das Wetter" → prüfe ob Weather MCP eine Bild-URL liefert
- Sende manuell eine Notion-Bild-URL im Antwort-String → muss als Foto ankommen
- Sende einen Google Maps Link → muss als Location ankommen

Status in docs/MASTER-REFERENCE.md updaten.
Regeln: Async, Logging, Fallback bei jedem Fehler, kein Crash.
```

### Phase 1.5.11 — Bugfixes (PRIORITÄT)
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.11 — Bekannte Bugs fixen.

5 Bugs zu untersuchen und fixen:

BUG-1 (HOCH): CalDAV lädt nicht alle Termine — nur erste paar werden angezeigt.
→ Prüfe CalDAV MCP: Pagination? Limit? Datumsbereich zu eng? Teste mit caldav_get_events für eine volle Woche.

BUG-2 (HOCH): Things 3 erstellt Cron-Jobs statt echte Tasks.
→ Prüfe wie Things 3 MCP aufgerufen wird. Liegt es am Tool-Aufruf oder am System Prompt? Teste things_create_task direkt.

BUG-3 (HOCH): himes-memory MCP Status "failed" nach Rename mcp/ → himes_mcp/.
→ Prüfe mcp_config.json: Pfad zum Server-Script. Prüfe Import-Pfade in himes_mcp/server.py. Teste memory_read/memory_write.

BUG-4 (NIEDRIG): cost_usd=0.0 wird immer angezeigt.
→ Prüfe welche stream-json Events ein cost-Feld haben. Wenn keins: Feld entfernen oder aus usage-Event berechnen.

BUG-5 (MITTEL): Antwortet manchmal auf Englisch statt Deutsch.
→ Verstärke Sprachregel im System Prompt: "Antworte IMMER in der Sprache die der User verwendet. Standard: Deutsch."
→ Prüfe ob Follow-ups den Sprachkontext verlieren.

Reihenfolge: BUG-3 → BUG-1 → BUG-2 → BUG-5 → BUG-4
Status in docs/MASTER-REFERENCE.md updaten (pro Bug).
```

### Phase 1.5.5 — Config Sync + KRITISCH MCPs
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.5 — Config Sync + KRITISCH MCPs.

1. Erstelle .gitignore (.env, data/, logs/, __pycache__/, .venv/)
2. Sync max_tool_calls zwischen .env.example und settings.py
3. Prüfe alle .env.example Variablen → settings.py
4. Filesystem MCP in mcp_config.json (modelcontextprotocol/servers filesystem, stdio TS)
   Erlaubte Verzeichnisse: /app/data, /app/skills, /app/prompts, /app/logs
5. Status in docs/MASTER-REFERENCE.md updaten

Regeln: Konsistenz, kein Hardcoding, Logging.
```

### Phase 1.5.6 — MEMORY.md Init
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.6 — MEMORY.md Init.

Bei Startup: prüfen ob data/MEMORY.md existiert, falls nein erstellen mit Datum + leeren Sections.
Status in docs/MASTER-REFERENCE.md updaten.

Regeln: Async, Logging, kein Crash bei fehlendem File.
```

### Phase 1.5.7 — System Prompt extern
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.7 — System Prompt externalisieren.

1. prompts/system.md erstellen mit aktuellem System Prompt
2. orchestrator.py: Prompt aus Datei laden, Pfad via settings.py/.env
3. Hot-Reload: bei jedem Request neu lesen
4. Status in docs/MASTER-REFERENCE.md updaten

Regeln: Kein Hardcoding, Logging, Fallback.
```

### Phase 1.5.9 — Brave Search MCP
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.9 — Brave Search MCP.

1. Brave Search in mcp_config.json (modelcontextprotocol/servers brave-search, stdio TS, BRAVE_API_KEY)
2. BRAVE_API_KEY in .env.example
3. Status in docs/MASTER-REFERENCE.md updaten

Regeln: Konsistenz mit bestehender MCP-Config.
```

### Phase 1.5.10 — Latenz-Optimierung
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.10 — Latenz-Optimierung.

Problem: 10-20s pro Request (CLI Kaltstart + MCP Warmup bei jedem Request).

1. Persistenter Claude Code Prozess (CLI einmal starten, --resume wiederverwenden, auto-restart)
2. Telegram Typing-Indikator (sofort send_chat_action typing, alle 4s erneuern)
3. Optional: Streaming-Antwort (erste Chunks sofort senden, Rest als Edit)
4. Status in docs/MASTER-REFERENCE.md updaten

Ziel: 10-20s → 4-9s. Regeln: Async, Logging, Fallback bei Crash.
```

### Phase 1.5.22 — Zukunfts-Architektur vorbereiten
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.22 — Zukunfts-Architektur vorbereiten (rückwärtskompatibel).

Ziel: Weichen für Phase 2 stellen ohne aktuelle Funktion zu ändern.
Siehe Sektion 2a für Kontext und Begründung.

Reihenfolge:
1. ClaudeBackend Protocol einführen (core/backends/base.py), SDKClient als 
   SingletonSDKBackend refactoren. Interface, keine Logik-Änderung.
2. UserContext dataclass einführen und durch Telegram→Orchestrator→Backend 
   reichen. Logik ignoriert user_id erstmal.
3. mcp_config.json kategorisieren, MCP_LAZY_LOADING Setting einführen (default=False).
4. Deployment-ADR schreiben: Option A (alles docker-compose) empfohlen.
   jarvis-caldav Container-Migration ist optional, separate Task.

WICHTIG:
- Keine Verhaltensänderung für User. Telegram-Tests müssen exakt gleich funktionieren.
- Feature-Flags wo sinnvoll (z.B. MCP_LAZY_LOADING=False default)
- Tests grün halten (pytest)
- Jeder Teilschritt eigener Commit

Regeln: Async, Typen-Hints, structlog, settings.py, .env. Status in 
docs/MASTER-REFERENCE.md updaten.
```

### Phase 1.5.2 — Message Splitting
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.2 — Message Splitting.

telegram_adapter.py: Antworten >4096 Zeichen an Absatz/Satz-Grenzen splitten, sequentiell senden.
Status in docs/MASTER-REFERENCE.md updaten.

Regeln: Async, Error Handling, Logging.
```

### Phase 1.5.3 — Error Recovery
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.3 — Error Recovery.

claude_subprocess.py: Retry bei 529/503/Timeout. Exponential Backoff 1s/2s/4s, max 3.
User sieht "Einen Moment..." bei Retry. Circuit Breaker nach 3 Fails.
Status in docs/MASTER-REFERENCE.md updaten.

Regeln: Async, Logging, Config aus settings.py.
```

### Phase 1.5.4 — Session Cleanup
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.4 — Session Cleanup.

Orchestrator: TTL 30min Inaktivität → neue Session. Max 5 Sessions/User, älteste löschen.
Config aus settings.py/.env. Status in docs/MASTER-REFERENCE.md updaten.

Regeln: Async, Logging, .env-konfigurierbar.
```

### Phase 1.5.8 — Health Monitoring
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.8 — Health Monitoring.

Self-Check alle 5min (Docker, CLI, Token). Fehler → Telegram an TELEGRAM_ADMIN_CHAT_ID.
Startup: "HiMeS ist online". Anti-Spam: 1 Alert/Fehlertyp/Stunde.
Status in docs/MASTER-REFERENCE.md updaten.

Regeln: Async, Logging, .env-konfigurierbar.
```

---

## 15. CHANGELOG

| Datum | v | Änderung |
|---|---|---|
| 2026-04-11 | 1 | Initiales Dokument |
| 2026-04-11 | 2 | +Prompt-Templates, +Changelog, +Phase 2 Abhängigkeiten, +Self-Improvement, +Eval, +ADR |
| 2026-04-11 | 3 | +MCP-Katalog (24 Server), +Time/Filesystem KRITISCH, +Brave Search 1.5.9 |
| 2026-04-11 | 3.1 | +Latenz-Optimierung 1.5.10, +Latenz-Analyse, +ADR-011 |
| 2026-04-11 | 4 | Status: VPS ✅, Time ✅, Weather ✅, Prompt ✅, Datum ✅, Health Check ✅, Rename ✅, OAuth ✅, GitHub v1-v3 ✅ |
| 2026-04-11 | 5 | +Persönliche Konfiguration (Familie, Kalender, Sprachregeln, Standorte), +Morning Report 2.11 |
| 2026-04-11 | 6 | Komplett-Rebuild: Status als Kapitel 1, Token-optimiert, Pfad docs/MASTER-REFERENCE.md |
| 2026-04-11 | 6.1 | +Phase 1.5.11 Bugfixes (5 bekannte Bugs mit Priorität), Bug-Tabelle im Status, Prompt-Template, Reihenfolge: Bugs zuerst |
| 2026-04-12 | 6.2 | +Phase 1.5.12 Rich Media Output (Bilder/Docs/Standorte/Buttons in Telegram), Prompt-Template, Reihenfolge: nach Bugs |
| 2026-04-11 | 7 | PTY-Fix (pty.openpty statt script), Notion-Integration (easy-notion-mcp + custom himes-tools), notion_list_children + notion_query_database_full (Relation-Auflösung, Central-DB-Fallback), BUG-3 ✅ (NotificationOptions + himes-tools Rename), BUG-4 ✅ (total_cost_usd), max_turns 10→25, error_max_turns Handling, System Prompt mit Notion-Struktur, 6 MCP aktiv, ADR-012+013 |
| 2026-04-12 | 8 | Alle 5 Bugs ✅ gefixt: BUG-1 (CalDAV alle Kalender), BUG-2 (Things3 statt CronCreate/TodoWrite), BUG-5 (Sprachregeln DE/EN/FA). Zeitzone ZoneInfo("Europe/Berlin") statt UTC (auto Sommer/Winterzeit). Woche=Mo-So explizit im Prompt. Uhrzeit im Datum-Kontext. System Prompt: Sprach-Sektion, KRITISCHE Regeln, Kalender-Schritte |
| 2026-04-12 | 9 | Phase 1.5.12 ✅: Rich Media Output — media_parser.py (Notion-Bilder, PDFs, Audio, Google/Apple Maps, Inline-Buttons), telegram_adapter.py (reply_photo/document/audio/location, Caption-Optimierung, Fallback-Kette, aiohttp Download, CallbackQueryHandler), +aiohttp in requirements.txt. Deployed+getestet: Notion-Fotos funktionieren ✅ |
| 2026-04-12 | 10 | Deutsche Bahn MCP ✅: himes_db/ (FastMCP, stdio) — 7 REST-Tools (v6.db.transport.rest) + 3 Timetable-API-Tools (optional). db_search_connections, db_departures, db_arrivals, db_find_station, db_nearby_stations, db_trip_details, db_pendler_check (Mülheim↔Dortmund). Station-Cache, Retry+Backoff, Rate-Limiting, Graceful Degradation. 7 MCP aktiv. |
| 2026-04-12 | 11 | Phase 1.5.13 ✅: Notion Native Integration — easy-notion-mcp komplett ersetzt durch eigenen Python-Client. 3 neue Module: notion_client.py (API Client, Retry, Pagination, Schema-Cache, Relation-Resolution), notion_markdown.py (Blocks↔Markdown bidirektional), notion_properties.py (Key-Value↔Notion API). 14 Tools total (2 Memory + 12 Notion). ADR-014. 6 MCP aktiv (1 weniger, aber mehr Tools). |
| 2026-04-12 | 12 | Deutsche Bahn MCP Fix: __main__.py erstellt (Entry Point), mcp_config himes_db.server→himes_db, Dockerfile chown -R /app (Permission Fix für himes User), orchestrator DB env vars Rendering. DB MCP jetzt connected+funktional (503 = externe API, nicht unser Code). |
| 2026-04-13 | 13 | Phase 1.5.14 ✅: 5 Notion Query Bugs gefixt. System Prompt: Zentral vs. patientenspezifisch DB-Zuordnung, deterministische 3-Schritt Query-Strategie, IMMER Relation-Filter bei zentralen DBs, Fallback-Kette bei 0 Ergebnissen. server.py: Hinweis mit DB-Typ-Empfehlung bei leerem Ergebnis, Parent-Page-Titel in list_children Ausgabe. |
| 2026-04-13 | 14 | Phase 1.5.15 ✅: 3 Kalender-Bugs gefixt. CalDAV client.py: EventCreationResult erweitert (location, description, attendees, reminders_count), ORGANIZER-Feld für iMIP-Einladungen (CALDAV_ORGANIZER_EMAIL/NAME aus .env), METHOD:REQUEST im VCALENDAR. CalDAV server.py: location_geo Parameter im Tool-Schema. System Prompt: Anweisung location_geo zu nutzen + Bestätigungsdetails nach Erstellung. |
| 2026-04-13 | 15 | CalDAV Auto-Geocoding: Nominatim-Integration für automatische Adressauflösung (Ortsname→Straße+PLZ+Stadt+Koordinaten). GEO-Property statt X-APPLE-STRUCTURED-LOCATION (iCloud escaped Komma in geo-URI). LOCATION mit "Name\nAdresse" Format. iPhone zeigt Karte+Pin korrekt. caldav-mcp lokal gespiegelt (/caldav-mcp/). |
| 2026-04-13 | 16 | Phase 2 Roadmap erweitert: +2.12 Telegram Mini App, +2.13 Intelligent Document Processing (Claude Vision), +2.14 Personal Vault (Google Drive). MCP-Katalog: +CardDAV (dav-mcp), +Google Drive. ADR-015 (3-Layer Memory), ADR-016 (Google Drive statt iCloud). |
| 2026-04-14 | 17 | Phase 1.5.16 ✅: 2 Bugs gefixt. BUG-1: Differenzierte Fehlermeldungen (Timeout/API-Overload/max_turns/Tool-Limit/Session-Crash je eigene User-Meldung), Auto-Retry bei transienten Fehlern (Timeout, 503/529, Crash → 1x Retry mit neuer Session), ClaudeErrorType-Enum, verbessertes Error-Logging (Stacktrace+Prompt+Session-ID). BUG-2: Begrüßung auf max 1-2 Sätze beschränkt, keine Feature-Listen. |
| 2026-04-14 | 18 | Phase 1.5.17 ✅: caldav_update_event Tool + Adressauflösung. CalDAV client.py: update_event() (UID-basiert, nur geänderte Felder, SEQUENCE++, Auto-Geocoding bei neuem Ort). CalDAV server.py: caldav_update_event Tool-Schema (uid required, optional: title/description/location/start_time/end_time/reminders/attendees). System Prompt: TERMIN-ÄNDERUNG Regel (erst suchen, dann updaten, nie neu erstellen), Abkürzungen→volle Namen (JoHo→St. Johannes Hospital, MHB→Marienhospital Bottrop, OPS→Otto-Pankok-Schule). |
| 2026-04-14 | 19 | Phase 1.5.18 ✅: Multi-Format I/O. Foto-Input: Temp-Datei in /tmp/himes/uploads/ + Pfad an Claude (Read-Tool liest Bilder). Dokument-Input: Neuer Telegram-Handler für PDF/Word/Excel/etc., gleiche Temp-Datei-Logik. Voice-Input: 3 Fixes — download_to_drive statt download_to_memory, Whisper-Modell gecacht (1x laden), Transkription in Thread-Pool (run_in_executor, blockiert Event Loop nicht mehr). Media-Output: System Prompt Regel — Notion-Bilder IMMER als ![alt](url) ausgeben. orchestrator.py: _process_claude() extrahiert, try/finally für Temp-Cleanup. |
| 2026-04-15 | 20 | Phase 1.5.19 ✅: DB+VRR Nahverkehr komplett. Self-hosted db-rest:6, alle HAFAS-Produkte (ICE/IC/RE/RB/S/U/Tram/Bus), Gleis-Fix (departurePlatform/arrivalPlatform), 1+4 Verbindungen, Telegram-Design (Emojis, Farbcodes, _german_date), _smart_truncate, zuginfo.nrw Client, _parse_departure (auto-tomorrow), System Prompt DB-Regeln (time-MCP Pflicht). ADR-017. |
| 2026-04-15 | 21 | DB Adress-Routing: resolve_location() ersetzt resolve_station() in db_search_connections — unterstützt jetzt Straßenadressen und POIs (Schulen, Gebäude) zusätzlich zu Bahnhöfen. rest_client: locations() mit addresses/poi Params, _set_location_params() für HAFAS from.type=location, journeys() akzeptiert str|dict. Fußwege als 🚶 mit Dauer. db_find_station mit include_addresses Option. |
| 2026-04-16 | 22 | DB Nominatim-Geocoding: HAFAS löste Adressen falsch auf (Otto-Pankok-Schule→Schule Blücherstr., Am Rathaus→Rathausmarkt). Fix: Nominatim-Geocoding (wie CalDAV) in resolve_location() integriert. _looks_like_station() Heuristik: Station-Keywords→HAFAS, Adress-Keywords (Schule/Straße/Hospital/Klinik)→Nominatim, Ziffern→Nominatim. _geocode_nominatim() async via run_in_executor, Mülheim als Default-Stadt-Kontext, _location_cache. _set_location_params() mit from.address statt from.name, keine Fake-IDs an HAFAS. |
| 2026-04-16 | 23.1 | Phase 1.5.20 Follow-up: 3 Edge-Cases gefixt nach Telegram-Test. DB-FIX-5a (Guard _is_near_negation erkennt Refusal-Kontext "kein Tool"/"empfehle App" → kein False-Positive-Disclaimer mehr), DB-FIX-5b (SYSTEM_PROMPT listet alle 9 DB-Tools mit vollem mcp__deutsche-bahn__-Präfix + Anweisung "nicht deferred, IMMER direkt aufrufen, kein ToolSearch" — Root Cause: Claude nutzte ToolSearch wenn MCP-Status "pending", fand nichts, halluzinierte "kein Tool"), DB-FIX-5c (_is_remark_relevant(final_destination=...) droppt "zwischen X und Y" wenn eine Station = final destination und andere off-route = downstream). +10 Tests. |
| 2026-04-16 | 23.2 | DB-FIX-6 (Pending-MCP Race + Global Refusal Short-Circuit): DB-FIX-6a — Guard Tier-1 `_GLOBAL_REFUSAL_MARKERS` Short-Circuit (Text mit "nicht verfügbar"/"DB Navigator App"/"ohne live-verifikation" etc. → ganze Message = Refusal → skip alle Domain-Checks). Löst S3-Refusal mit 3× Mention wo letzte außerhalb ±150-Zeichen-Fenster war. DB-FIX-6b — `ClaudeResponse.pending_mcps` Feld in claude_subprocess.py, Orchestrator Auto-Retry wenn (pending_mcps + 0 tool_calls + refusal-text via `_TOOL_REFUSAL_MARKERS`) → 2s Pause + fresh Session. Transparente Lösung für MCP-Race-Condition bei erstem Call. +3 Tests (94/94 Docker). |
| 2026-04-17 | 27 | Phase 1.5.21 ✅: CalDAV Stabilität. Debugged ausgehend von User-Report "Bot hängt bei Termin-Abfrage". Drei unabhängige Bugs im caldav-mcp Repo (separates Projekt, bisher ungetracktes Basis-Fork von madbonez) identifiziert und behoben. (a) **Starlette-SSE-Route** (commit 3802c56): handle_sse() gab None zurück, Starlette 0.50 erwartet aber Response-Objekt → TypeError bei jedem /sse Request (604 Exceptions in 2 Tagen Laufzeit). Der Bug war tolerierbar solange mcp-remote (im Bot-Container) eine einmal etablierte SSE-Session poolte — brach aber bei jedem docker compose up --build. Fix: `return Response()` nach connect_sse-Block + debug=False. (b) **Ungetrackte Phase-1.5.15-Extensions** (commit 93608f1): 420 Zeilen Nominatim-Geocoding + update_event-Tool + ORGANIZER-Feld waren seit April 13 im VPS working-tree uncommitted — gingen fast verloren beim Debug. Gesichert als eigener commit bevor weitergearbeitet wurde. (c) **keepalive timeout** (commit 86ce5e3): Apple iCloud schließt idle HTTP-keepalives nach ~60-90s; niquests connection pool merkt's erst beim nächsten Request → hard ConnectionError. Retry-Decorator `@retry_on_stale_connection` auf 9 Apple-facing CalDAVClient-Methoden (list_calendars, create_event, get_events, get_today_events, get_week_events, get_event_by_uid, update_event, delete_event, search_events). Walkt Exception-Chain nach NiquestsConnectionError oder Substring-Markers (keepalive timeout, connection reset, remote end closed, …). Diskriminiert von 401/404/ValueError die unverändert durchgereicht werden. connect() bewusst NICHT dekoriert (Loop-Risiko). (d) **Prozess-Management**: jarvis-caldav.service (systemd, Port 8001) als einziger Persistenz-Mechanismus — mit Auto-Restart bei pkill. Caddy proxyed https://caldav-ahsan.duckdns.org/sse → localhost:8001. **Tests**: 95 Unit-Tests grün (86 alt + 9 neu in tests/test_retry.py) + 1 E2E-Smoke-Test in tests/e2e/test_stale_reconnect_e2e.py (NiqConnError-Injection via monkey-patch der principal.calendars). **Live-Verifikation**: Stale-Path mit injiziertem NiqConnError getriggert → Log zeigte "stale_connection_detected → reconnect (635ms) → retrying → OK 1.44s gesamt". **Offen**: caldav-mcp remote ist upstream madbonez Fork, 4 neue Commits liegen nur auf VPS — entweder eigenes GitHub-Fork anlegen oder lokaler Mirror manuell syncen. | |
| 2026-04-16 | 26 | Phase 1.5.10e REVERTED: Versuch ENABLE_TOOL_SEARCH=false via ClaudeCodeOptions.env zu setzen (offizieller Anthropic-Switch bei <10 Tools empfohlen; wir haben ~25 auf 6 MCPs). Messung: Things 22s→8.5s (-13.5s, super), Zug ähnlich (17.6s→22.7s, Varianz), aber CalDAV produzierte User-sichtbare "Verbindungsunterbrechung"-Fehlermeldungen obwohl Tools laut Log aufgerufen wurden (caldav_list_calendars ×2, caldav_create_event ×2 = Claude-Retries nach Error-Response). Remote-Server HTTP 200, Kausalität ungeklärt — möglicherweise MCP-Handshake-Race mit dem Tool-Search-Disable. Laut Task-Regel "Qualität > Speed → REVERT" env-Setting entfernt. Latenz-Reduktion bei Things wäre attraktiv (60% weniger), aber nur mit CalDAV-Stabilität verhandelbar. Offen für 2. Anlauf mit explizitem allowed_tools whitelist statt Env-Var. | |
| 2026-04-16 | 25 | Phase 1.5.10 ✅: Latenz-Optimierung komplett. (a) Telegram Typing-Indikator als async Task der alle 4s send_action("typing") ruft, gestoppt im finally (telegram_adapter.py). (b) Pre-Classification: regex-basierte _INSTANT_REPLIES für Grüße/Danke/Bestätigungen (^...$ Anker) umgehen Claude komplett — "hallo", "danke", "ok" antworten <100ms ohne API-Call. (c) claude-code-sdk Integration: neuer core/sdk_client.py mit persistentem Singleton ClaudeSDKClient (connect einmal beim Bot-Start, alle Messages nutzen denselben warmen Subprocess). Feature-Flag CLAUDE_USE_SDK_CLIENT (default true). Orchestrator ruft _send_to_claude() → SDK zuerst, bei SUBPROCESS_CRASH oder Exception transparenter Fallback auf ClaudeSubprocess (unverändert). Retries gehen immer über robusten Subprocess-Pfad. Zwei post-deploy Fixes: (1) date.today()-Vergleich statt Prompt-String-Vergleich — verhinderte ~4.3s-Reconnect pro Minute weil Uhrzeit im Prompt drin war. (2) ResultMessage.result als Source of Truth statt akkumulierter TextBlocks — verhinderte Claude's Denk-Zwischentexte ("Ich lade zuerst das Tool-Schema...") in der Antwort. Monkey-Patch für SDK-0.0.25-Bug (rate_limit_event). Gemessen: erste Nachricht ~30s (MCP Cold-Start), Folge-Nachrichten ~15s, kurze Frage ohne Tool ~4s. Session-Continuity bestätigt (test_sdk_v2.py: Claude erinnerte "42" über 4 Nachrichten). Alle 6 MCPs verifiziert (caldav, weather, things3, time, deutsche-bahn, himes-tools/notion+memory), keine Funktionsregression. |
| 2026-04-16 | 24 | DB-FIX-7 (Smart-Split + UX-Polish): DB-FIX-7a — db_search_connections machte EINE Query mit `departure=requested-45min, results=10` → bei lokalen Bussen lieferte HAFAS 10 Ergebnisse ALLE im Rückwärts-Fenster, "after"-Bucket blieb leer. Fix: ZWEI separate Queries — (1) after: departure=requested, results=5, filter >=requested, take 4. (2) before: departure=requested-20min, results=4, filter <requested, take 1. Dedupe via refreshToken. Verifiziert gegen VRR-App-Screenshot: Am Rathaus 15 → Otto-Pankok-Schule zeigt jetzt Bus 131 20:29, Bus 151 20:35, Bus 130 20:48, STR 102 20:51 korrekt. DB-FIX-7b — "📍 Snapshot" → "📍 Abfahrtsstation" (User fragte "was bedeutet Snapshot"). |
| 2026-04-16 | 23 | Phase 1.5.20 ✅: DB-MCP Stabilisierung + Halluzinations-Schutz. 4 Bugs gefixt — DB-FIX-1 (rest_client._robust_get mit strukturierten Error-Dicts {ok, error, user_message_hint, retry_suggested, status_code, detail}, alle public Methoden retournieren Dict statt raisen, server.py-Tools forwarden user_message_hint verbatim, neuer MCP_FAILED ErrorType als retryable), DB-FIX-2 (core/hallucination_guard.py: modulare HallucinationGuard Klasse mit registrierbaren Domains, DB-Patterns für RE/S/U/Bus/Gleis/Verspätung/Gleiswechsel, soft-check appended nur Disclaimer + Warning-Log, Orchestrator-Integration, harte SYSTEM_PROMPT-Regel "NIEMALS konkrete Zugdaten erfinden"), DB-FIX-4 (neues Tool db_train_live_status — /trips/:id Live-Daten: Verspätung, Gleis vs. planned, Gleisänderungen 🔀, nächster Halt, GPS; graceful fallback), DB-FIX-3 (↩ Prefix-Zeile statt ⬅️ Marker im Row, immer ━━━ Separator, _is_remark_relevant filtert Baustellen nach Zeit±30min + Stations-Matching). ADR-018, ADR-019. Tests-Infrastruktur: pytest.ini, tests/ mit respx HTTPX-Mocking, requirements-dev.txt. 60+ Unit+Integration Tests (alle grün lokal + Docker). |

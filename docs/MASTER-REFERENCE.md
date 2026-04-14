# HiMeS — MASTER REFERENCE
> **Version:** v17 · **Stand:** 2026-04-14 · **Pfad:** `docs/MASTER-REFERENCE.md`
> **Nutzung:** `Lies docs/MASTER-REFERENCE.md und fahre fort mit Phase [X.Y]: [Task].`
> **Nach Task:** Status in dieser Datei updaten + committen.

---

## 1. AKTUELLER STATUS — LIES DAS ZUERST

**Phase:** 1.5 Stabilisierung · **6 MCP aktiv** · **VPS läuft** · **GitHub v9 (12 Commits)**

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
| 1.5.10 | Latenz-Optimierung | ⬜ | Persistenter CLI-Prozess + Typing-Indikator |
| 1.5.12 | Rich Media Output | ✅ | Deployed+getestet: Notion-Fotos ✅, PDF/Audio/Location Parser bereit (Maps MCP fehlt noch) |
| 1.5.14 | Notion Query Bugs | ✅ | 5 Bugs: Relation-Filter, DB-Zuordnung, Query-Strategie, Fallback, Parent-Kontext |
| 1.5.15 | Kalender-Bugs | ✅ | 3 Bugs: Bestätigung nach Erstellung, Apple-Maps-Ort, ORGANIZER für Einladungen |
| 1.5.16 | Crash-Handling + Begrüßung | ✅ | Differenzierte Fehlermeldungen, Auto-Retry bei transienten Fehlern, kurze Begrüßung |

**Empfohlene Reihenfolge:** ~~1.5.11~~ → ~~1.5.12~~ → ~~1.5.14~~ → ~~1.5.15~~ → ~~1.5.16~~ → 1.5.5 → 1.5.6 → 1.5.7 → 1.5.9 → 1.5.10 → 1.5.2 → 1.5.3 → 1.5.4 → 1.5.8

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

## 3. TECH STACK

Python 3.11 · Claude Code CLI (stream-json Subprocess) · python-telegram-bot · aiohttp · asyncio · Docker + docker-compose · Hetzner VPS · Pydantic BaseSettings · structlog · openai-whisper (lokal)

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
├── himes_db/                       ← Deutsche Bahn MCP (FastMCP, stdio)
│   ├── server.py · rest_client.py · timetable_client.py
├── core/orchestrator.py · claude_subprocess.py
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
| CalDAV | SSE | create_event (+ location_geo, ORGANIZER), get_events (Start/End), search | ✅ |
| Time | stdio Python | current_time, convert_time (Europe/Berlin) | ✅ |
| Weather | stdio TS | forecast, current_conditions, alerts | ✅ |
| Deutsche Bahn | stdio Python | db_search_connections, db_departures, db_arrivals, db_find_station, db_nearby_stations, db_trip_details, db_pendler_check + 3 Timetable-API-Tools (optional) | ✅ |

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

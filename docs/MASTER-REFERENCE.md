# HiMeS — MASTER REFERENCE
> **Version:** v25.13 · **Stand:** 2026-04-26 · **Pfad:** `docs/MASTER-REFERENCE.md`
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
| 1.5.8 | Health Monitoring | ⬜ | **Reihenfolge kritisch**: ZUERST /health-Endpoint in `core.orchestrator` implementieren (aiohttp, Port 8080), DANN healthcheck-Block in `docker-compose.yml` reaktivieren. Endpoint MUSS vor healthcheck existieren, sonst Container-Restart-Loop. Der Block wurde am 2026-04-17 entfernt weil curl auf Port 8080 fehlschlug (Bot hatte keinen HTTP-Server). Zusätzlich: Self-Check alle 5min + Telegram-Alert an TELEGRAM_ADMIN_CHAT_ID, Anti-Spam 1 Alert/Fehlertyp/Stunde. |
| 1.5.9 | Search MCP (Tavily + Exa) | ⬜ | Brave Search verworfen (kein Free Tier mehr seit Feb 2026, siehe Verworfen-Sektion). Ersetzt durch Tavily + Exa (beide Free Tier ohne CC). API Keys noch nicht geholt. mcp_config.json + TAVILY_API_KEY + EXA_API_KEY. Redundanz durch zwei Provider reduziert Ausfall-Risiko. |
| 1.5.10 | Latenz-Optimierung | ✅ KOMPLETT | 1.5.10 abgeschlossen. Pre-Classification, Typing-Indikator, SDK-Singleton, ToolSearch-Off (v2a Whitelist + v2b Env-Var, Commits 15da656 + 3c316b2). Gesamtergebnis: -20 bis -77% Latenz je nach Szenario. Tool-heavy limitiert durch externe APIs (iCloud/HAFAS). Phase 1.5.10f (Streaming) durch SDK-Limit nicht als Token-Stream machbar — umgedeutet zu Tool-Progress-Updates (siehe 1.5.10f). |
| 1.5.10f | Tool-Progress-Updates | ⬜ Optional | Umdeutung von ursprünglich geplantem Token-Streaming (durch SDK-Limit nicht machbar, ADR-024). Neu: Bei ToolUseBlock-Events editierbare Status-Zeile in Telegram ("🔧 CalDAV wird abgefragt…"). Macht tool-heavy Anfragen (Wochenübersicht 40s) subjektiv erträglich. NACH 1.5.22 und 1.5.26. |
| 1.5.12 | Rich Media Output | ✅ | Deployed+getestet: Notion-Fotos ✅, PDF/Audio/Location Parser bereit (Maps MCP fehlt noch) |
| 1.5.14 | Notion Query Bugs | ✅ | 5 Bugs: Relation-Filter, DB-Zuordnung, Query-Strategie, Fallback, Parent-Kontext |
| 1.5.15 | Kalender-Bugs | ✅ | 3 Bugs: Bestätigung nach Erstellung, Apple-Maps-Ort, ORGANIZER für Einladungen |
| 1.5.16 | Crash-Handling + Begrüßung | ✅ | Differenzierte Fehlermeldungen, Auto-Retry bei transienten Fehlern, kurze Begrüßung |
| 1.5.17 | Kalender Update + Adresse | ✅ | caldav_update_event Tool, Abkürzungen→volle Namen im Prompt, Geocoding für Adressen |
| 1.5.18 | Multi-Format I/O | ✅ | Foto/Dokument/Voice Input, Media-Output Prompt-Regel, Whisper-Caching |
| 1.5.19 | DB + VRR Nahverkehr | ✅ | Self-hosted db-rest, VRR-Produkte (U/Tram/Bus), Gleis-Fix, 1+4 Verbindungen, Telegram-Design, zuginfo.nrw, Adress-Routing |
| 1.5.20 | DB-MCP Stabilisierung + Halluzinations-Schutz | ✅ | 4 Bugs gefixt (DB-FIX-1 bis DB-FIX-4): HallucinationGuard, strukturierte Error-Dicts, Live-Status-Tool, Format-Polish |
| 1.5.21 | CalDAV Stabilität | ✅ | 3 Bugs gefixt (in caldav-mcp Repo): Starlette-SSE-Route returnt Response statt None, Phase-1.5.15-Extensions committet (Nominatim/update_event/ORGANIZER), Retry-Decorator auf 9 Apple-facing Methoden bei keepalive timeout. 95 Unit-Tests + 1 E2E-Smoke-Test, live mit injiziertem NiqConnError verifiziert. |
| 1.5.22 | Zukunfts-Architektur vorbereiten | ⬜ | **PRIORITÄT HOCH — kritischer Pfad.** ClaudeBackend-Protocol so designen, dass späterer Wechsel zu API/Hybrid/Realtime ohne Refactoring möglich ist. Muss VOR 1.5.4 und 1.5.2 gebaut werden, damit diese Features direkt ins neue Protocol einfließen. Siehe Sektion 2a + 1b + 1c + ADR-026. |
| 1.5.23 | MCP: Time + Filesystem | ⬜ Offen | time + filesystem MCP in mcp_config.json + Dockerfile (npx) |
| 1.5.24 | MCP Warmup Reihenfolge | ⬜ Offen | Warmup priorisiert: kritische MCPs zuerst, optional lazy |
| 1.5.25 | Wochentag-Halluzinations-Schutz | ✅ → ersetzt durch 1.5.32 (2026-04-20) | Commit `068837f` (2026-04-19). System-Prompt-Regel "Wochentag-Regel (KRITISCH)" top-level eingefügt. HallucinationGuard-Domain `weekday` mit 2 Patterns (Wochentag+Datum within 40 chars). Phase 1.5.32-Cleanup hat die `weekday`-Domain entfernt nachdem CalendarAssertion live verifiziert war — die Domain produzierte 3 False-Positives in 10min weil sie nur Tool-Calls im aktuellen Turn checkte, nicht aber Antworten aus Session-Memory abdeckte. CalendarAssertion (deterministisch via `datetime.date.weekday()`) ersetzt sie funktional und ist präziser. |
| 1.5.26 | Tool-Manifest + Proaktivitäts-Regel | ⬜ | Jarvis bekommt aktive Selbstkenntnis über seine Werkzeuge und Skills. prompts/tool_manifest.md + prompts/skill_manifest.md (auto-generiert aus mcp_config.json). System-Prompt-Erweiterung mit Cross-Over-Regel (Kalender+Wetter, Bahn+Kalender, Notion+Kalender, etc.). Fundament für Phase 2.7 Self-Improvement. Reihenfolge: NACH 1.5.22, VOR 1.5.4. Siehe Sektion 1d. |
| 1.5.27 | Tool-Loop-Guard im Orchestrator | ⬜ | Mittlere Priorität. Im selben Turn ein Tool mit identischen Args >2× → synthetisches Error-Result zurückgeben ("Tool wurde bereits X-fach mit diesen Args aufgerufen, Ergebnis war: …"), statt echten Call zu wiederholen. Beleg: Log vom 2026-04-17 zeigt `caldav_get_today_events` 11× hintereinander in einem Turn (turns=13, Kosten $0.18). Würde CalDAV-Latenz bei Wochenübersichten senken. Reihenfolge: NACH 1.5.4 (Session-Store liefert die History). |
| 1.5.28 | things-mcp Härtung | ⬜ | 2026-04-20: Schicht 1 (Reaktivierung) durchgeführt nach Cultured Code Cloud-Cleanup. `docker start things-mcp` + `restart=unless-stopped`, HiMeS-Bot restart. 4 manuelle Tests erfolgreich (2 reads + 2 writes, Tasks in App sichtbar, keine Crashes). Schicht 2 (Härtung: Input-Sanitization, Unicode-Filter, Dry-Run-Mode) weiterhin offen, Priorität niedrig solange keine neuen Incidents. Reihenfolge: NACH 1.5.3 (Error Recovery). |
| 1.5.29 | CalDAV Recurrence-Exception-Handling | ✅ | caldav-mcp Commits `eddfab6` (1.5.29a: `date_search` → `search(expand=True)` — iCloud expandiert Serien server-side) + `1870046` (1.5.29b: widen server window ±14 Tage, filter client-side nach DTSTART — weil iCloud Overrides nach RECURRENCE-ID matched, nicht neue DTSTART). Motivation: Musikschule-Bug 2026-04-19 (verschobene Fr-Instanz auf So unsichtbar). Technisch verifiziert gegen echten iCloud-Kalender. 10 neue Tests, 105/105 grün. |
| 1.5.30 | Time-Arithmetic Tools + Strict Event-Bucketing | ✅ | HiMeS Commit `da69a25`. 4 neue Tools in `himes-tools` (`get_weekday_for_date`, `add_days`, `days_between`, `next_weekday`) ersetzen Claude's Mental-Math. System-Prompt erweitert (Wochentag-Regel zeigt explizit auf diese Tools) + strikte Event-zu-Tag-Bucketing-Regel für Wochenübersichten. HallucinationGuard weekday-Domain erweitert um himes-tools-Prefixes. 22 neue Tests. Verifiziert: "Nächste Musikschule = Fr 24.04", Wochentags-Labels korrekt. |
| 1.5.32 | Calendar Assertion-Layer | ✅ Check A | Check A (Wochentag-Validierung) deployed 2026-04-20 (zweiter Anlauf nach reverted V1). `core/calendar_assertion.py` validiert deterministisch via `datetime.date().weekday()` — bei Mismatch konkrete Korrektur ("28.01.2026 ist Mittwoch (nicht Dienstag)"). Cleanup-Begleitung: HallucinationGuard.weekday-Domain entfernt (3 False-Positives/10min), `tests/test_weekday_guard.py` gelöscht. Pip-Lock-File (`requirements.lock`) eingeführt um Versions-Drift bei Rebuilds zu verhindern (`mcp 1.9.2 → 1.27.0` war wahrscheinliche Ursache der V1-Regression). Live verifiziert: CalDAV-Suche unverändert, beide Test-Cases (Pilates-Recap + Wochenübersicht) korrekt, Assertion silent bei korrekten Antworten. Check B (Event-zu-Tag-Bucketing gegen DTSTART aus Tool-Output) bleibt offen. |
| 1.5.33 | Home Assistant MCP Integration | 🔶 In Progress | Parallele Integration in separatem Chat gestartet. Status 2026-04-20: (a) Entscheidung ha-mcp (homeassistant-ai/ha-mcp) nach Vergleich von 5 Alternativen (offizieller HA MCP, voska/hass-mcp, tevonsb/homeassistant-mcp, mtebusi/HA_MCP). (b) HA OS Add-on installiert auf HA Green (v7.1.0, 34 Module, 86 Tools). (c) LAN-Endpoint verifiziert: http://192.168.178.89:9583/private_<REDACTED>. (d) Claude Desktop via mcp-proxy verbunden (Running). OFFENE SCHRITTE: (1) Domain himes-home.uk bei Cloudflare registrieren (war temporär blockiert, Alternative .org), (2) Cloudflare Tunnel auf HA Green einrichten, (3) Claude Desktop Funktionstest ("Welche Geräte habe ich?"), (4) VPS-Integration: mcp_config.json + settings.py + Dockerfile + System-Prompt + .env (HA_MCP_URL), (5) Claude-Code-Prompt `himes-ha-mcp-integration-prompt.md` existiert, wartet auf finale HTTPS-URL. |
| 1.5.34 | Telegram Attribution in Replies | ⬜ | Niedrige Priorität, UX-Verbesserung. In allen Tool-Action-Bestätigungen (Task erstellt, Termin angelegt, etc.) Trigger-Quelle + Zeitstempel mitschicken. Beispiel: `✓ Task erstellt via Telegram, 18:47` oder `✓ Termin angelegt via Sprach-Nachricht, 14:32`. Motivation: Things-3-Crash-Incident 2026-04-17 — Majid konnte nicht unterscheiden ob Jarvis autonom gehandelt oder auf seinen Trigger reagiert hat (Schreck-Moment). Transparenz verhindert Misstrauen und hilft bei Debugging. Aufwand: ~1h (nur Telegram-Adapter anpassen, Prompt-Regel ergänzen). Reihenfolge: niedrige Prio, nach Kern-Phasen. |

**Empfohlene Reihenfolge:** ~~1.5.11~~ → ~~1.5.12~~ → ~~1.5.14~~ → ~~1.5.15~~ → ~~1.5.16~~ → ~~1.5.17~~ → ~~1.5.18~~ → ~~1.5.19~~ → ~~1.5.20~~ → ~~1.5.10~~ → ~~1.5.21~~ → ~~1.5.10e v2~~ → **1.5.22 (kritischer Pfad)** → **1.5.26 (Tool-Manifest)** → 1.5.4 (Session-Store) → 1.5.27 (Tool-Loop-Guard) → 1.5.2 (Message-Splitting) → 1.5.6 → 1.5.7 → 1.5.3 → 1.5.28 (things-mcp Härtung) → 1.5.8 → 1.5.5 → 1.5.9 → 1.5.10f (optional) → 1.5.23 → 1.5.24

**Rationale:** 1.5.22 ist kritischer Pfad, weil es die Architektur für spätere API-Migration vorbereitet. 1.5.26 direkt danach, damit Skills und Tool-Manifest vor Session-Store und Feature-Entwicklung stehen — sonst müssen Features später nachgezogen werden.

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

### Aktuelle Performance-Zahlen (nach 1.5.10e v2, Stand 2026-04-19)

| Szenario | Pre-1.5.10 | 1.5.10d | v2-Final | Δ gesamt |
|---|---|---|---|---|
| Pre-Classification ("danke") | ~15s | <0.1s | <0.1s | -99% |
| Kein Tool, kurz ("wie spät") | ~20s | 11.6s | **7.3s** | -63% |
| Kein Tool, mittel ("kardiomyopathie") | ~30s | 8.5s | **6.8s** | -77% |
| 1 Tool (Wetter, Things3) | ~20s | 7-8s | 5-7s | -65-75% |
| CalDAV Tag (~11 Tools) | ~30s | 35.3s | **32.9s** | ~-10% (Apple-limited) |
| CalDAV Woche (~10 Tools) | ~40s | — | **39.4s** | Apple-limited |
| Notion komplex (3 Tools) | — | — | **37.0s** | Session-state (Hinweis 1.5.4) |
| Erste Nachricht nach Bot-Start | ~30s | ~30s | ~30s | MCP Cold-Start |

**Verbesserung gesamt**: -20% bis -99% je nach Szenario. Einfache Nachrichten massiv, tool-heavy limitiert durch externe APIs (iCloud, HAFAS). Weitere Latenz-Gewinne nur durch API-Migration (ADR-009/026) oder parallele Tool-Execution (erst mit API möglich).

### Offene Punkte aus heute

1. **caldav-mcp Remote-Strategie**: Commits `93608f1`, `3802c56`, `86ce5e3`, `45af46f` liegen nur auf VPS (`/home/ali/caldav-mcp/`). Remote ist `madbonez/caldav-mcp` (Upstream-Fork, nicht Majids). **Drei Optionen**:
   - **A** Eigenes Fork auf `Majid-Ahsan/caldav-mcp`, Remote umstellen, pushen — **empfohlen**
   - B Als git-Submodule in HiMeS einbinden
   - C `vendor/caldav-mcp/` in HiMeS einchecken
   
   Morgen entscheiden.

2. **`docs/himes-dashboard.html`**: Untracked seit Tagen, Herkunft unklar. Committen oder in `.gitignore`?

3. **Phase 1.5.10e zweiter Anlauf**: ToolSearch-Overhead (5-7s pro Tool-Call) eliminierbar. Jetzt wo CalDAV stabil ist wieder machbar. Diesmal mit explizitem `allowed_tools`-Whitelist statt `ENABLE_TOOL_SEARCH`. Nicht kritisch — kann warten.

---

## 1b. UPDATE 2026-04-19 — Strategische Neuausrichtung

### Analyse-Session Ergebnisse

Nach ausführlichem Latenz-Debug und Vergleich mit Hermes Agent (NousResearch/hermes-agent) wurden vier Erkenntnisse erarbeitet:

**1. SDK-Streaming-Limit bestätigt (Event-Log-basiert)**

Event-Log von 5 realen Telegram-Anfragen am 17.-18.04.2026 zeigte:
- "wie spät": 1× TextBlock (text_len=87) bei elapsed=11569ms von 11645ms
- "kardiomyopathie": 1× TextBlock (text_len=594) bei 8241ms von 8520ms
- "termine morgen": 1× TextBlock (text_len=225) bei 35256ms von 35344ms (88ms Puffer!)
- "musikschule?": 1× TextBlock (text_len=368) bei 25262ms von 25275ms
- "wetter?": 1× TextBlock (text_len=354) bei 23514ms von 23727ms

→ `claude-agent-sdk==0.0.25` aggregiert Content-Blöcke im MessageParser. Token-für-Token-Streaming zu Telegram ist nicht möglich ohne SDK-Bypass bzw. API-Migration.

**2. Strategie-Entscheidung: CLI/SDK bleibt**

Majid bleibt bei CLI/SDK aus Kosten-Gründen (Abo deckt Testing ab, API würde bei hohem Test-Volumen Kosten verursachen). Migration auf API bewusst aufgeschoben — aber Architektur wird jetzt vorbereitet (Phase 1.5.22).

**3. Phase 1.5.22 wird kritischer Pfad**

ClaudeBackend-Protocol muss so designed werden, dass:
- CLI/SDK heute läuft (kein Kosten-Impact)
- API-Backend später als zweites Backend einhängbar ist
- Realtime-Backend (wenn Anthropic es bringt) als drittes Backend einhängbar ist
- Umschaltung = Feature-Flag, kein Refactoring

Je länger Features ohne dieses Protocol gebaut werden, desto mehr doppelter Anpassungsaufwand später.

**4. Phase 1.5.10f umgedeutet**

Ursprünglich "Token-Streaming an Telegram" geplant, durch SDK-Limit (siehe Punkt 1) nicht realisierbar. Neu: "Tool-Progress-Updates" — bei ToolUseBlock-Events editierbare Status-Nachricht in Telegram. Macht tool-heavy Anfragen subjektiv erträglich. Optional, nach 1.5.22 und 1.5.26.

### Phase 1.5.10e v2 — heute abgeschlossen

**v2a (Whitelist, Commit 15da656):**
- `allowed_tools`-Whitelist in `ClaudeCodeOptions`
- Automatische Tool-Discovery aus `mcp_config.json`
- Security-Gewinn: CronCreate/TodoWrite/Bash/Edit/Write hart verhindert (BUG-2 aus 1.5.11 jetzt architektonisch ausgeschlossen, nicht nur per Prompt)

**v2b (Env-Var, Commit 3c316b2):**
- `ENABLE_TOOL_SEARCH=false` in ClaudeCodeOptions.env
- ToolSearch aus `tools_used` komplett verschwunden
- Weitere ~1s pro Anfrage, Cleanness in Tools-Liste

**Messergebnisse siehe Performance-Tabelle in 1a.**

**Gelernte Lektionen:**
- Erhoffte "+4-5s pro Tool-Call" nicht eingetreten. Real: +1-2s.
- Der große Win kam von v2a (Whitelist → eager schema loading), nicht v2b (ToolSearch-Kill).
- Bei tool-heavy Anfragen (CalDAV 10×, Notion 3×) ist Bottleneck externe APIs (iCloud-Round-Trips, HAFAS), nicht ToolSearch.
- **Nebenfund**: Session-Kosten-Kurve beobachtet (persistent SDK-Client sammelt Context über Anfragen, cost_usd stieg auf $0.43 über Session). Hinweis auf Bedarf für Phase 1.5.4 Session-Cleanup.

### Neue Prioritäten-Reihenfolge

1. **1.5.22** — Zukunfts-Architektur mit API-Migrations-Vorbereitung (~1 Woche)
2. **1.5.26** — Tool-Manifest + Proaktivitäts-Regel (1-2 Tage)
3. **1.5.4** — Session-Store SQLite+FTS5 (direkt ins neue Protocol, 3-5 Tage)
4. **1.5.2** — Message-Splitting (platform-aware, 1-2 Tage)
5. 1.5.6, 1.5.7, 1.5.3, 1.5.8 — kleinere Features (je 1-2 Tage)
6. 1.5.10f — Tool-Progress-Updates (optional)

### Offene Sub-Tickets (nicht vergessen)

- **Kalender-Halluzinations-Bug (Musikschule)**: In Anfrage "musikschule?" (2026-04-18) antwortete Claude mit "nächsten Donnerstag" für Event 2026-04-24 — aber 2026-04-24 ist ein Freitag. Vermutung: Wochentag aus Datum halluziniert statt time-MCP-Gegencheck. **Separates Mini-Ticket** (Phase 1.5.25): System-Prompt-Regel ergänzen ("Bei Wochentag-Angabe IMMER time-MCP oder Python-Rechnung, nie aus Datum raten"). Eventuell HallucinationGuard um Wochentag-Pattern erweitern. 15-30 min Aufwand.

- **caldav-mcp Remote-Strategie** (aus 1.5.21): Commits 93608f1, 3802c56, 86ce5e3, 45af46f liegen nur auf VPS. Entscheidung offen (Fork vs Submodule vs vendor/).

- **docs/himes-dashboard.html**: Untracked, Entscheidung committen oder .gitignore.

---

## 1c. KOSTEN-STRATEGIE + VOICE-PFAD (2026-04-19)

### Heute

- **Claude Code CLI mit OAuth-Token** (Abo-basiert)
- **0€ API-Kosten** — alle LLM-Calls gehen über Abo-Quota
- Testing während Entwicklung unbegrenzt ohne Kostensorge

### Morgen (optional, Majid entscheidet)

- **Hybrid-Modus** möglich: einfache Fragen über API (schnell, kostet pro Request), tool-heavy über CLI (Abo-gedeckt, langsamer aber gratis)
- Feature-Flag `CLAUDE_BACKEND=sdk|api|hybrid`
- Umschaltung ohne Code-Änderung (vorbereitet durch Phase 1.5.22)

### Zukunft (wenn Anthropic Realtime-API bringt)

- Neues Backend `RealtimeBackend` einhängen
- Voice-Pfad: Telegram Voice → Whisper streaming → RealtimeBackend → TTS streaming
- Zielzeit: 2-4s Ende-zu-Ende (ChatGPT-Niveau 300ms nicht erreichbar ohne WebRTC)

### Voice: aktuell NICHT möglich

Mit heutigem Stack (CLI-SDK, 15-40s Latenz) ist Voice-Konversation unbenutzbar. Voice-Features warten explizit auf:
- (a) Anthropic Realtime-API ODER
- (b) API-Migration + WebSocket-Layer (Whisper streaming + Claude streaming + TTS streaming)

Nicht vor Phase 3.

---

## 1d. PHASE 1.5.26 — Tool-Manifest + Proaktivitäts-Regel

### Ziel

Jarvis hat aktive Selbstkenntnis über seine Werkzeuge und Skills. Bei einer Aufgabe prüft er: "Welche meiner Tools helfen hier? Welche Skills passen? Kann ich Cross-Over machen?"

### Vision

Beispiel: User fragt "Plan morgen für Marien-Hospital Bottrop"

Jarvis denkt strukturiert:
- Kalender → welche Termine morgen?
- Wetter → Regen? → beeinflusst Transport-Entscheidung
- Bahn → Mülheim → Bottrop Verbindung zum ersten Termin
- Notion → gibt es Vorbereitungs-Notes?

Cross-Over: Wenn Bahn um 07:30 fährt aber erster Termin 08:00 ist → proaktiv vorschlagen "nächste Bahn 07:15 kommt, 10min Puffer für Fußweg zum Hospital".

### Implementierung

**Datei 1: `prompts/tool_manifest.md`** — auto-generiert bei Bot-Start aus `mcp_config.json`:

```markdown
# Verfügbare Werkzeuge (auto-generiert)

## Kalender (caldav) — Terminmanagement
- caldav_list_calendars: Alle Kalender auflisten
- caldav_get_today_events: Termine heute pro Kalender
- caldav_get_week_events: Wochen-Übersicht
- caldav_create_event: Neuen Termin (mit Geocoding+ORGANIZER)
- caldav_update_event: Termin ändern (UID-basiert)
- caldav_delete_event: Termin löschen
- caldav_search_events: Suche nach Text/Teilnehmer/Ort

## Wetter — aktuell + Vorhersage
- get_current_conditions: Jetzt-Wetter
- get_forecast: Vorhersage N Tage

## Bahn + VRR — Verkehr NRW
- db_search_connections: 1+4 Verbindungen mit allen Verkehrsmitteln
- db_departures / db_arrivals: Live-Abfahrten/Ankünfte
- db_find_station: Station-Suche
- db_trip_details: Fahrt-Details
- db_pendler_check: Mülheim↔Dortmund
- db_train_live_status: Live-Tracking (Gleis, Verspätung)
- db_nrw_stoerungen: zuginfo.nrw

## Notion — Second Brain
- search: Volltextsuche
- read_page / create_page / update_page / append_content / archive_page
- list_children / get_database / query_database
- add_entry / update_entry / delete_entry

## Zeit
- get_current_time: Jetzt (Europe/Berlin)
- convert_time: Zeitzonen

## Aufgaben (Things3)
- create_task: Neue Aufgabe
- list_today: Heute-Liste
- complete_task: Als erledigt markieren

## Memory
- memory_read: MEMORY.md lesen
- memory_write: MEMORY.md aktualisieren
```

**Datei 2: `prompts/skill_manifest.md`** — initial leer, füllt sich in Phase 2:

```markdown
# Skills (erlernte Muster)

Noch keine Skills registriert. Wird in Phase 2.7 (Self-Improvement) automatisch gefüllt.

## Template für neue Skills

### Skill-Name
- **Trigger**: Welche Anfragen aktivieren diesen Skill
- **Werkzeuge**: Welche Tools werden kombiniert
- **Pattern**: Konkrete Schritt-für-Schritt-Logik
- **Erfolgsrate**: Gemessen über N Anwendungen
```

**Datei 3: System-Prompt-Erweiterung** in `prompts/system.md`:

```markdown
## Tool-Selbstkenntnis und Proaktivität

Du hast Zugriff auf die in `prompts/tool_manifest.md` gelisteten Werkzeuge und die in `prompts/skill_manifest.md` gelisteten Skills. Bei JEDER komplexen Anfrage:

1. **Frage dich zuerst**: "Welche meiner Werkzeuge passen hier?"
2. **Denke in Kombinationen**: Nutze mehrere Tools parallel wenn sinnvoll
3. **Sei proaktiv mit Cross-Over**:
   - Kalender + Wetter → bei Outdoor-/Reise-Terminen
   - Bahn + Kalender → bei Terminen außerhalb Mülheims
   - Notion + Kalender → bei Patienten-/Arbeitsterminen
   - Things3 + Kalender → bei Deadline-basierten Aufgaben
   - Bahn + Wetter → bei Pendel-Entscheidungen
   - Notion + Notion → Cross-Datenbank-Verknüpfungen über Relations

4. **Pro-aktive Hinweise**: Wenn du bei einer Anfrage siehst, dass ein zweites Tool relevant wäre, erwähne es ("Übrigens: morgen regnet es, vielleicht willst du Bahn statt Auto nehmen?").

5. **Grenzen anerkennen**: Wenn ein Tool fehlt das nötig wäre, sage das klar statt zu halluzinieren.
```

### Aufwand

- Auto-Discovery-Mechanismus: 2-3h (Python-Script, bei Bot-Start mcp_config.json einlesen, Schemas von MCPs abrufen, Manifest generieren)
- Skill-Manifest-Template: 30 min
- System-Prompt-Erweiterung: 1h
- Tests (5 Szenarien mit Cross-Over): 2h

**Gesamt: 1-2 Tage.**

### Warum jetzt (nach 1.5.22)

- **Vor 1.5.4** Session-Store: Skills brauchen evtl. Session-State
- **Vor Phase 2.7** Self-Improvement: Skills müssen erst als Manifest existieren bevor sie verbessert werden können
- **Nach 1.5.22** Backend-Protocol: Manifest wird pro Backend unterschiedlich sein (SDK-MCPs vs. API-Tools), muss ins Protocol integriert sein

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

## 1e. KALENDER-KOMPLETT-FIX-SESSION (2026-04-19)

Musikschule-Bug-Incident vom 18./19.04. hat drei zusammenhängende Bug-Klassen offengelegt. In einer Session gefixt (Commits `eddfab6`, `1870046`, `068837f`, `da69a25`):

### Bug 1 — Wochentag-Halluzination (Phase 1.5.25 ✅)
Claude sagte "24.04 ist Donnerstag" (tatsächlich Freitag). Zwei Ebenen: System-Prompt-Regel "Wochentag-Regel (KRITISCH)" domain-übergreifend eingefügt. HallucinationGuard `weekday`-Domain (2 Patterns, Wochentag+Datum ≤40 Zeichen Abstand) registriert Claims, triggert bei fehlendem Datum-Tool-Call Soft-Disclaimer.

### Bug 2 — CalDAV Recurrence-Exception-Handling (Phase 1.5.29 ✅)
Verschobene Einzelinstanzen einer wiederkehrenden Serie waren unsichtbar. Zwei-Schicht-Fix:

**1.5.29a** (Commit `eddfab6` in caldav-mcp): `calendar.date_search()` → `calendar.search(event=True, expand=True)`. Grund: iCloud gab sonst Multi-VEVENT-Blobs zurück (Master+alle Overrides in einem Calendar-Resource), `event.icalendar_component` las nur ersten VEVENT, Rest ging verloren.

**1.5.29b** (Commit `1870046`): widen server window ±14 Tage, filter client-side nach echtem DTSTART. Grund: iCloud matched Overrides gegen die Time-Range per RECURRENCE-ID (Original-Slot), nicht neue DTSTART. Moved-Fri-17.04→Sun-19.04 Override war so bei Sonntag-only-Query unsichtbar. Verifiziert gegen Taha's iCloud-Kalender.

Apple iCal-Struktur dokumentiert: Master-VEVENT mit RRULE+EXDATE-Liste, Override-VEVENTs mit gleicher UID + RECURRENCE-ID (Original-Slot) + neuer DTSTART. Bei RECURRENCE-ID ≠ DTSTART = echte Verschiebung.

### Bug 3 — Datum-Arithmetik-Fehler und Event-Drift (Phase 1.5.30 ✅)
Real-World-Tests zeigten: nach Bug 1+2-Fix blieb Claude bei zwei Problemen:

**Problem A**: "Nächster Freitag" falsch berechnet. Obwohl time-MCP aufgerufen, kam "25.04 Freitag" raus (25.04 ist Samstag, nächster Freitag = 24.04).

**Problem B**: Wochenübersicht-Drift. Claude listete Tage korrekt Mo-So, aber ab 24.04 verschoben: "Do 24, Fr 25, Sa 26" statt "Fr 24, Sa 25, So 26".

**Problem C**: Event-zu-Tag-Drift. 5 Mittwoch-Events (Pilates, Keine Schule, Kinderschwimm, Office Day, Leistungssport Schwimmen) landeten unter Dienstag-Section obwohl DTSTART klar 22.04 sagte.

**Fixes in 1.5.30**:
- 4 deterministische Datum-Tools in himes-tools (`get_weekday_for_date`, `add_days`, `days_between`, `next_weekday`) — ersetzen LLM-Mental-Math
- System-Prompt-Regel neu: listet diese Tools als Pflicht-Werkzeuge für Datum/Wochentag-Claims, mit konkreten Anwendungs-Beispielen
- Strikte Event-zu-Tag-Bucketing-Regel für Wochenübersichten mit Beleg-Bug-Referenz
- HallucinationGuard `weekday`-Domain erweitert um himes-tools-Prefixes

**Nach-Verifikation (2026-04-19 nach Deploy)**:
- "Nächste Musikschule" → "Freitag 24.04.2026" ✓
- Wochentags-Labels Mo 20 bis So 26 alle korrekt ✓
- Event-zu-Tag-Bucketing: **nicht vollständig behoben** — Problem C tritt bei sehr langen Wochenübersichten weiter auf. Prompt-Regel reduziert Frequenz, ersetzt aber keine echte Validierung. **Phase 1.5.32 Check A** ✅ deployed 2026-04-20 (V2 mit `requirements.lock`-Mitigation). HallucinationGuard.weekday-Domain als Folge entfernt (3 False-Positives/10min). CalendarAssertion übernimmt alleinigen Wochentag-Schutz, deterministisch und ohne Session-Memory-False-Positives.

### Tests

- caldav-mcp: 105/105 grün (95 alt + 10 neu in `test_recurrence.py`)
- HiMeS: 73/73 grün (39 HallucinationGuard + 12 weekday_guard + 22 time_tools)

### Deployment-Reihenfolge

1. caldav-mcp: pkill → systemd auto-restart → verify via direct Python call
2. HiMeS-Container: `docker compose up -d --build himes` (braucht Rebuild für neue himes-tools)
3. Guard + Whitelist beim Startup geloggt: `guard.domain_registered domain=weekday` + `allowed_tools_active count=7`

### Post-Deploy User-Testing (Ergebnisse)

Nach Deploy hat Majid eine Reihe realer Anfragen gestellt. Befunde:

**Core-Bugs weg** ✅:
- "Musikschule heute?" (So 19.04) → korrekt, verschobene Instanz sichtbar
- "Nächste Musikschule?" → korrekt "Freitag 24.04" (vorher: "Donnerstag 24.04")
- Wochen-Übersicht Tages-Header Mo 20 – So 26 konsistent korrekt (vorher: Do-Drift)
- Claude ruft `mcp__himes-tools__get_weekday_for_date` aktiv auf bei direkten Wochentag-Fragen

**Zwei Drift-Muster bestätigt** ⚠️ — Phase 1.5.32 wird damit Pflicht:

1. **Event-zu-Tag-Drift** bei langen Wochenübersichten: 5 Mi-Events (Pilates, Keine Schule, Kinderschwimm, Office Day, Leistungssport) landeten unter Dienstag-Section obwohl DTSTART korrekt 22.04 sagte. Wochentags-Labels korrekt, aber Events strikt falsch zugeordnet. System-Prompt-Regel "strikte DTSTART-Gruppierung" wurde nicht befolgt.

2. **Historische-Recap-Halluzinationen**: Anfrage "wie viele Pilates bisher?" lieferte 5 Daten (28.01, 04.02, 25.02, 11.03, 15.04) mit **allen als Dienstag** annotiert — tatsächlich **alle Mittwoche** (Pilates ist seit 2026-01-01 wöchentlich mittwochs). Claude's Meta-Kommentar "normalerweise dienstags, ausnahmsweise nächste Woche Mittwoch" ist komplett rückwärts halluziniert. Kritisch: tool_calls=1 (nur caldav_search_events), **kein get_weekday_for_date**-Aufruf — trotz expliziter System-Prompt-Regel.

**Was der Guard aufgefangen hat** ✅:
- Beide Muster wurden von HallucinationGuard `weekday`-Domain als `unbacked_claim` erkannt
- Disclaimer "⚠️ Wochentag nicht über time-MCP verifiziert" wurde beim Pilates-Recap korrekt angehängt
- Guard-Log zeigt matched-Patterns wie `['28.01.2026** (Dienstag', '04.02.2026** (Dienstag', …]`
- Sicherheitsnetz funktioniert — User bekommt Warnung zum Gegencheck

**Schlussfolgerung**: Prompt-Layer allein reicht nicht. Claude befolgt die "IMMER get_weekday_for_date aufrufen"-Regel nicht zuverlässig, besonders bei historischen Recaps / Meta-Kommentaren wo "Datum nennen" nicht als "Wochentag-Claim" empfunden wird. Der Soft-Guard ist das einzige verlässliche Sicherheitsnetz. Für echte Prävention braucht's Phase 1.5.32 Calendar Assertion-Layer mit **deterministischer Korrektur-Empfehlung** im Disclaimer ("Claude sagte Dienstag, 28.01.2026 ist tatsächlich Mittwoch").

### Offenes aus dieser Session

- **Phase 1.5.32 Check A** ✅ deployed 2026-04-20 (V2). Verlauf:
  - V1-Deploy: CalendarAssertion + Container-Rebuild → CalDAV-Suche-Regression (0 Termine statt 5). Revert hat Verhalten sauber wiederhergestellt; kein Code-Pfad der Assertion-Layer konnte die Tool-Suche direkt beeinflussen.
  - Root-Cause-Analyse zeigte: `requirements.txt` mit losen Pins (`mcp>=1.9.2` etc.), running container hatte `mcp 1.27.0` — V1-Rebuild hat eine andere Version gezogen die mit caldav-mcp-Server inkompatibel war.
  - V2-Deploy: erst `pip freeze` → `requirements.lock`, Dockerfile auf Lock-File umgestellt, dann CalendarAssertion-Code rein → live verifiziert: CalDAV-Suche unverändert, Wochentag-Validierung silent bei korrekten Antworten.
  - Cleanup: HallucinationGuard.weekday-Domain entfernt (produzierte 3 False-Positives/10min bei Session-Memory-Antworten ohne Tool-Call), `tests/test_weekday_guard.py` gelöscht. CalendarAssertion deckt den Fall deterministisch ab.
- **Check B** (Event-zu-Tag-Bucketing gegen DTSTART aus strukturiertem Tool-Output) bleibt offen — braucht Zugriff auf Tool-Result im selben Turn, separates Follow-up.
- **caldav-mcp Remote**: weiterhin unpushbar (upstream-Fork `madbonez/caldav-mcp`). 6 Commits auf VPS (eddfab6, 1870046 aus dieser Session plus 4 aus 1.5.21). Fork-Entscheidung offen.
- **docs/himes-dashboard.html**: weiterhin untracked.

---

## 1f. UPDATE 2026-04-23 — Strategische Neuausrichtung — HiMeS-Scope-Klärung

Während der Memory-Schema-Design-Sessions wurde grundlegend geklärt 
welche Rolle HiMeS in der Tool-Landschaft spielt:

HiMeS ist kein universelles Gedächtnis sondern spezialisiert auf 
Daten die in keinem anderen Tool existieren:
- Persönlicher Gedanken-Strom (Daily-Log)
- Persönliche Sicht auf Menschen (Entity-Person mit Anchor-System)
- Erschlossene Charaktermuster (Insights)
- Gesprächs-Gedächtnis mit Jarvis selbst (Conversation)

Was nicht in HiMeS gespeichert wird:
- Termine: bleiben in Calendar (CalDAV)
- Strukturierte Daten wie Medikamente, Projekte: bleiben in Notion
- Tasks: bleiben in Things3
- Research-Notizen: bleiben in Notion oder externe Bibliothek

Jarvis als Orchestrator kennt alle Quellen und routet Anfragen dorthin 
wo die Daten sind. HiMeS Memory ist eine Quelle unter mehreren, nicht 
die einzige.

Konsequenz: Memory-Typen reduziert von 8 auf 4 (siehe ADR-035). 
Initial-Daten-Strategie passiv (siehe ADR-036). Drei-Schichten-
Gedächtnis-Konzept mit Dreaming-Phase eingebracht, noch in Diskussion 
(siehe ADR-037).

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

### Vorbereitung 5 — API-Migrations-Hook im Protocol (ADR-026)

Das ClaudeBackend-Protocol wird so designed, dass zukünftige Backends (API, Realtime) ohne Refactoring einhängbar sind:

```python
# core/backends/base.py
class ClaudeBackend(Protocol):
    async def start(self) -> None: ...
    async def shutdown(self) -> None: ...
    async def process_message(
        self,
        user_context: UserContext,
        session_id: str,
        user_message: str,
        system_prompt: str,
        allowed_tools: list[str] | None = None,  # aus 1.5.10e v2
        stream: bool = False,                     # für späteres API-Streaming
    ) -> AsyncGenerator[BackendEvent, None]: ...
```

**Heute**: SDKBackend implementiert Protocol. `stream=True` wird ignoriert (SDK kann's nicht, ADR-024).

**Später (API-Aktivierung, optional)**: APIBackend nutzt `stream=True` für echtes Token-Streaming. Orchestrator-Code unverändert.

**Noch später (Realtime)**: RealtimeBackend mit WebSocket-Layer. Gleiches Protocol.

**Aufwand zusätzlich zu Vorbereitungen 1-4**: 30 min (nur Interface-Design, keine API-Implementation).

**Wichtig**: Diese 5 Vorbereitungen machen **nichts langsamer, nichts kaputt, keine Feature-Änderung**. Sie sind Investment in die Zukunft. Phase 2.1-2.5 (Cognee, Dream, Audio) können ohne sie gebaut werden — aber ab Phase 2.6 (Sub-Agents) sind sie nötig.

---

## 2b. ENTWICKLUNGS-WORKFLOW (Stage 2)

HiMeS folgt einem Stage-2-Feature-Branch-Workflow seit 2026-04-23 (siehe ADR-038). Frühere Workflows sind im historischen Abschnitt bei der ursprünglichen Sektion dokumentiert (siehe "Historisch — Uncommitted-VPS-State (bis Phase 1.5.21)").

### Drei-Orte-Architektur

- **Mac** (`/Users/ahsan/Documents/Claude/HiMeS`): Development-Umgebung. Hier werden alle Änderungen entwickelt und getestet.
- **GitHub** (`Majid-Ahsan/HiMeS`): Quelle der Wahrheit (single source of truth). Alle Änderungen müssen über GitHub laufen.
- **VPS** (`/home/ali/HiMeS` auf `116.203.134.101`): Production-Umgebung. VPS pullt von GitHub, niemals direkter Edit auf VPS.

### Standard-Workflow für Code-Änderungen

1. Auf Mac: `git checkout -b feature/branch-name`
2. Änderungen entwickeln und testen
3. `git commit`, `git push origin feature/branch-name`
4. Auf GitHub: Branch reviewen
5. Auf Mac: `git checkout main`, `git merge --no-ff feature/branch`
6. `git push origin main`
7. Auf VPS: `git pull origin main`
8. Falls nötig: `docker-compose rebuild`

### Standard-Workflow für reine Doku-Änderungen

Identisch wie oben. VPS-Pull optional bei reiner Doku.

### Verboten

- Direkte Code-Edits auf VPS (außer Notfall-Hotfix)
- Direktes Pushen zu main ohne Feature-Branch (außer triviale Doku)
- Konfigurationen oder Code auf VPS ohne Spiegelung im Repo

### Ausnahme: Geheimnisse

Geheime Konfigurations-Werte wie API-Keys leben nur auf VPS in `.env`-Dateien (via `.gitignore` ausgeschlossen). Im Repo nur `.env.example` mit Platzhaltern.

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
| Weather (`@dangahagan/weather-mcp`) | stdio TS | forecast, current_conditions, alerts | ✅ |
| Deutsche Bahn + VRR | stdio Python | db_search_connections (1+4 Verbindungen, alle Verkehrsmittel, Adressen+POIs), db_departures, db_arrivals, db_find_station, db_nearby_stations, db_trip_details, db_pendler_check, **db_train_live_status** (Live-Tracking: Verspätung, aktuelles Gleis, Gleiswechsel, nächster Halt), db_nrw_stoerungen (zuginfo.nrw) + 3 Timetable-API-Tools (optional). Strukturierte Error-Dicts + HallucinationGuard. | ✅ |

### Nächste (KRITISCH → HOCH)

| Server | Prio | Transport | API-Key | Zweck |
|---|---|---|---|---|
| Filesystem | KRITISCH | stdio TS | Nein | Skills/Logs/Configs lesen+schreiben |
| Tavily + Exa (Search) | KRITISCH | stdio TS | Ja (Free Tier ohne CC) | Web-Suche, Faktencheck. Ersetzt Brave Search (Free Tier Feb 2026 eingestellt, siehe Verworfen). Zwei-Provider-Redundanz. Siehe Phase 1.5.9 + ADR-033. |
| Telegram MCP | HOCH | stdio Python | Ja | Voller MTProto-Zugriff |
| Gmail (`ArtyMcLabin/Gmail-MCP-Server`) | HOCH 🔶 pausiert | SSE/HTTP TS | Ja (OAuth) | Inbox, Drafts, senden. Security-Pause: 100 Sterne, Code-Review pending bevor Deploy. Alternative zu prüfen: `google_workspace_mcp`. |
| Reminder | HOCH | stdio/HTTP TS | Ja | Erinnerungen planen |
| Google Maps (`modelcontextprotocol/server-google-maps`, offiziell Anthropic) | HOCH 🔶 | stdio TS | Ja | Routen, Places, Entfernungen. API-Key-Setup angefangen, pausiert wegen Billing-Account (wartet auf Unterstützung von Majids Vater). |
| ~~Deutsche Bahn~~ | ~~HOCH~~ | ~~stdio/SSE~~ | ~~Ja~~ | ✅ Implementiert (himes_db) |
| Home Assistant (`homeassistant-ai/ha-mcp`) | HOCH 🔶 | SSE/HTTP via mcp-proxy | Ja (Token) | Smart Home steuern. 2026-04-20: `ha-mcp` Add-on auf HA Green installiert (86 Tools in 34 Modulen), Claude Desktop verbunden. VPS-Integration pending — wartet auf Cloudflare Tunnel + Domain. Siehe Phase 1.5.33 + ADR-032. |
| CardDAV (dav-mcp) | HOCH | stdio TS | Nein (iCloud Auth) | Kontakte lesen/erstellen/suchen via iCloud CardDAV. Für: Visitenkarten, Kontaktkarten, "Wie ist Nedas Nummer?" |
| Google Drive | HOCH | SSE/HTTP TS | Ja (OAuth) | Dateien suchen/hochladen/organisieren. Für: Dokument-Ablage, Personal Vault, "Schick mir mein Dokument X" |

### Später (MITTEL → OPTIONAL)

WhatsApp (Twilio) · Firecrawl · Spotify · Currency (Frankfurter) · GitHub · SQLite (→Phase 2.2) · iMessage · Slack · Azure Translator · Whisper (→Phase 2.4) · TTS ElevenLabs · Apify

### Verworfen

| Server | Grund | Entschieden |
|---|---|---|
| Apple Reminders MCP | Läuft nicht auf VPS (nur lokal Mac/iPhone, kein Server-Deployment möglich) | 2026-04-14 |
| Apple Maps MCP | Keine strukturierten Daten im Response (rein visuelle Integration, für LLM nicht verwertbar) | 2026-04-14 |
| Brave Search | Free Tier im Februar 2026 eingestellt. Ersatz durch Tavily + Exa (siehe Phase 1.5.9 + ADR-033) | 2026-04-14 |
| Perplexity MCP | Kostenmodell nicht kompatibel mit Abo-basierter Kostenstrategie (siehe ADR-023) | 2026-04-14 |

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
| 2.2 | Long-term DB | — | SQLite | Persistente Rules, Patterns, Profile + SQLite MCP Server |
| 2.3 | Model Selection | — | — | Haiku/Sonnet/Opus dynamisch |
| 2.4 | Audio-Tagebuch | 2.1 | Whisper | Whisper → Extraktion → Cognee + Whisper MCP Server |
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
| 2.15 | MCP Welle 2: Kernfunktionen | ⬜ Geplant | 1.5.23 | Maps, DB, Wetter, Search, Reminder, Notion, Gmail, HA |
| 2.16 | MCP Welle 3: Erweiterungen | ⬜ Geplant | 2.15 | Telegram, Spotify, Twilio, Currency, Exa, Firecrawl, GitHub |
| 2.17 | Eigener DB-MCP (transport.rest) | 1.5.19 | — | Erweiterung des aktuellen self-hosted `db-rest` (PaulvonBerg). Eigener MCP auf `transport.rest`-API für erweitertes A→B-Routing mit Geo-Awareness, Multi-Modal-Alternativen und Deutschland-weiter Verkehrsintegration. NACH Phase 1.5-Abschluss. Aufwand geschätzt 2-3 Wochen. |

### Phase 2.1 — Cognee-Evaluierung (2026-04-15)

Cognee läuft auf VPS als Docker Container:
- Image: `cognee/cognee:latest`, Port 8000
- Keine GPU nötig, 2-4 GB RAM reichen
- Nutzt Claude API für Extraktion (Haiku, kostengünstig)
- Nativer MCP Server: `cognee-mcp`
- 4 Operationen: `remember`/`recall`/`forget`/`improve`
- Session-Memory eingebaut (`session_id`-Parameter)

Integration-Abhängigkeitskette: Phase 1.5.6 (MEMORY.md) → 1.5.4 (Session-Cleanup) → 2.1 (Cognee) → 2.5 (Dream Phase). Nicht vor Phase 2.1 aktivieren — Cognee braucht Session-State als Input.

#### Phase 2.1 Vorarbeit — Memory-Schema ✓ (2026-04-23)

Konzeptionelle Design-Arbeit für das Memory-Schema abgeschlossen. 
10 Grundregeln festgelegt, Anchor-basiertes Beziehungs-System 
definiert, Multi-User-Vorbereitung über Anchor-Wechsel zur Query-Zeit.

Volle Spezifikation: docs/memory-schema.md

Dies ist die Grundlage für die eigentliche Cognee-Implementation 
in Phase 2.1. Die Memory-Markdown-Dateien die später von Cognee 
indexiert werden, folgen dem in memory-schema.md definierten Format.

Noch offen für folgende Sessions bevor Cognee installiert wird:
- Beziehungs-Vokabular (welche Werte für rel_to_anchor erlaubt sind)
- Ableitungs-Regeln (was Jarvis automatisch schließen darf)
- Initial-Daten-Strategie (Setup-Skript vs passives Lernen)
- Konkrete Templates pro Memory-Typ (7 Typen identifiziert)
- Erste Beispiel-Dateien mit echten Daten
- Prompt-Regeln in prompts/rules.md die Regel 9 umsetzen

Update 2026-04-23: Daily-Log-Schema als erster konkreter Memory-Typ 
definiert (siehe docs/memory-schema.md, Abschnitt "Memory-Typ 1: 
Daily-Log").

Update 2026-04-23: Entity-Person-Schema (Memory-Typ 2) und 
Insights-Datei-Schema (Memory-Typ 2a) definiert. Anchor-System 
mit Default/Query-Anchor-Unterscheidung. Dual-Datei-Prinzip 
(entities/ + insights/) für Fakten vs Charakter-Muster.

Update 2026-04-23 (Vokabular und Strategie): Beziehungs-Vokabular 
vollständig definiert (44 Werte in 9 Gruppen für rel_to_anchor, 
4 Werte für rel_via). Strategische Neuausrichtung: Memory-Typen 
reduziert von 8 auf 4 (Daily-Log, Entity-Person, Insights, Conversation). 
HiMeS speichert nur was nirgendwo anders existiert — Calendar, Notion, 
Things3 bleiben Quelle für ihre jeweiligen Daten. Initial-Daten-
Strategie: passive Erfassung über Daily-Logs.

Update 2026-04-25 (Cognee installiert und ins Repo eingefangen): 
Cognee als eigenständiger Service auf VPS installiert (siehe Phase 
2.1 Ausführung Schritt 1). Setup-Skripte und Doku ins Repo eingefangen 
unter cognee-setup/ (siehe Schritt 2). Erste echte Code-Schritte nach 
abgeschlossenem Schema-Design. Drei wichtige Erkenntnisse als ADRs 
dokumentiert (039-041).

##### Offene Konzept-Arbeit

Folgende Themen sind noch zu designen bevor die Implementierung weitergeht:

- Memory-Typ 4 (Conversation) designen und dokumentieren
- Drei-Schichten-Gedächtnis-Architektur ausarbeiten (siehe ADR-037)
- Tool-Routing-Regeln definieren (wann Calendar, wann Notion, wann Memory)
- Ableitungs-Regeln für Anchor-Graph-Traversal
- Jarvis-Prompt-Regeln für selektive Antworten (Regel 9 Umsetzung)
- Erste Anchor-Datei majid-ahsan.md erstellen

Diese Punkte können parallel zu den Implementierungs-Schritten 3-8 angegangen werden.

#### Phase 2.1 Ausführung

Nach abgeschlossenem Schema-Design startet die Implementierung. Cognee wird als Memory-Backend für HiMeS aufgesetzt.

##### Schritt 1 — Cognee installiert (2026-04-25) ✓

Cognee als eigenständiger Service auf VPS installiert.

Setup-Details:
- Pfad: /home/ali/cognee/ (separates venv, parallel zu HiMeS)
- Cognee Version: 1.0.3 via uv pip install
- LLM-Provider: Anthropic Claude (claude-haiku-4-5-20251001), nutzt bestehenden API-Key
- Embedding-Provider: Fastembed lokal (sentence-transformers/all-MiniLM-L6-v2)
- Datenbanken: SQLite + LanceDB + Kuzu (file-based, default)

Smoke-Test: erfolgreich. Cognee hat aus 4-Satz-Familientext einen Knowledge Graph mit 17 Knoten und 28 Kanten gebaut. Frage Wer ist Reza wurde korrekt beantwortet inklusive Onkel-Beziehung, Wohnort Teheran, Beruf Arzt, Diabetes-Medikation seit 2019.

Drei nicht-triviale Probleme bei der Installation gelöst:
- OAuth-Tokens funktionieren nicht für Tool-Use → klassischer API-Key nötig (ADR-041)
- Cognee 1.0.3 reicht max_tokens nicht durch → LLM_ARGS-Workaround nötig (ADR-040)
- Cognee braucht nur LLM_API_KEY, nicht ANTHROPIC_API_KEY (transitive Dependencies haben Fallback)

##### Schritt 2 — Cognee-Setup ins Repo eingefangen (2026-04-25) ✓

Setup-Skripte und Dokumentation aus dem VPS-only-Zustand ins Repo gebracht (gemäß Stage-2-Workflow ADR-038).

Neue Dateien unter cognee-setup/:
- install.sh: idempotentes Server-Installationsskript
- .env.example: Konfigurations-Template mit erklärenden Kommentaren
- smoke_test.py: Server-side Validierungs-Test
- README.md: Setup-Anleitung mit dokumentierten Bug-Workarounds und ANTHROPIC_API_KEY-Klarstellung
- .gitignore: schützt .env und Runtime-Daten

Validierung gegen VPS-Originale durchgeführt: einzige bewusste Abweichung ist ANTHROPIC_API_KEY (Legacy-Doppelung auf VPS aus Bug-Debugging, im Repo als Optional dokumentiert). Reproduzierbarkeit hergestellt: bei VPS-Verlust kann Cognee aus dem Repo neu aufgesetzt werden.

##### Schritt 3 — DBs aus venv nach /home/ali/cognee/data/ verschoben (2026-04-25) ✓

Cognee-Datenbanken aus dem venv-Verzeichnis in einen persistenten Pfad ausserhalb des venvs verschoben — damit ein venv-Recreate keinen Datenverlust mehr verursacht.

Pfad-Wechsel:
- Vorher: DBs unter `.venv/...` innerhalb von `/home/ali/cognee/`
- Nachher: `/home/ali/cognee/data/.cognee_system/databases/`
- `.env` um `SYSTEM_ROOT_DIRECTORY` und `DATA_ROOT_DIRECTORY` ergänzt, damit Cognee die neuen Pfade nutzt

Backup vor Migration angelegt unter `/home/ali/cognee/backup/20260425-093128/` (Migrations-Skript, idempotent).

Verifikation:
- Smoke-Test grün: 17 Knoten / 29 Kanten, Frage „Wer ist Reza?" korrekt beantwortet
- Cognee-Logs bestätigen `Database storage: /home/ali/cognee/data/.cognee_system/databases`

Erkenntnis aus der Vorklärung als ADR-042 dokumentiert: bei zukünftiger Migration von `DATA_ROOT_DIRECTORY` (nicht aktuell, weil DBs vor Move leer waren) müssten zusätzlich die absoluten Pfade in der `Data`-Tabelle (`raw_data_location`, `original_data_location`) umgeschrieben werden.

##### Schritt 4 — Multi-User-Access-Control Default akzeptiert (2026-04-25) ✓

Cognee bietet `ENABLE_BACKEND_ACCESS_CONTROL` als Schalter für die automatische User-Trennung. Default ist AN. Entscheidung: bleibt AN.

Begründung:
- Aktuell Single-User (nur Majid). Default ist sicher und bringt für einen User keinen relevanten Overhead.
- Default ist bereits multi-user-ready für späteren Ausbau (Telegram-Multi-User mit Neda/Taha/Hossein). Kein späteres Refactoring nötig.
- Konsistent mit ADR-035 (Anchor-System multi-user-vorbereitet via Anchor-Wechsel zur Query-Zeit).

Blockiert nichts: bei zukünftigem Bedarf kann der Schalter ohne Datenverlust revidiert werden (Konfigurations-Änderung in `.env`, kein Schema-Bruch).

Volle Begründung als ADR-043 dokumentiert.

##### Schritt 5 — Voice-Memo-zu-Markdown-Pipeline (2026-04-25) ✓

Mapper-Skript baut/erweitert tagesweise Daily-Log-Markdown-Dateien aus Whisper-Transkripten. Stdlib-only (kein pyyaml), kompatibel mit dem in `docs/memory-schema.md` definierten Daily-Log-Format.

Skripte und Tests:
- `pipeline/voice_to_md.py` — Mapper, drei Aufruf-Modi (Stdin, `--file`, `--text`)
- `pipeline/test_voice_to_md.py` — 16 Tests, alle grün
- Branch: `feature/pipeline-voice-to-md`

Optionen:
- `--user` (Default `majid`, validiert gegen `^[a-zA-Z0-9_-]+$` als Path-Traversal-Schutz)
- `--date` (Default heute Berlin-TZ), `--time`, `--data-dir`

Verhalten:
- Output-Pfad: `<data-dir>/memory/daily-logs/<YYYY-MM-DD>_<user>.md`
- Pflicht-Frontmatter `type/date/user` wird beim ersten Append erzeugt
- Erster Eintrag bekommt `## (Erster Eintrag)`-Heading, Folge-Einträge `## HH:MM`

VPS-Test (2026-04-25): drei Erfolgskriterien-Tests grün — neue Datei korrekt erzeugt (Frontmatter + erster Eintrag), Append in bestehende Datei korrekt platziert, expliziter `--date` und `--time` werden respektiert.

##### Schritt 6 — Markdown-zu-Cognee-Pipeline (2026-04-26) ✓

Daily-Logs werden via SHA-Hash-Tracking in den Cognee-Knowledge-Graph eingespeist. Re-Ingest passiert automatisch wenn sich der Hash ändert (Option Y aus der Vorklärung), Tracking-State liegt in `<data-dir>/.ingested.json` (Option A).

Skripte und Tests:
- `pipeline/ingest_to_cognee.py` — Ingest-Skript, drei Modi (`--file`, `--dir`, `--all`), Date-Validation-Prompt vor jedem Ingest, `--yes` für Automation
- `pipeline/cognee_search.py` — CLI-Suche aus beliebigem CWD (Bonus aus der Bugfix-Runde)
- `pipeline/_cognee_env.py` — Helper, lädt `cognee/.env` BEVOR cognee importiert wird
- 56 Pipeline-Tests grün (16 voice_to_md + 20 ingest + 10 env + 10 search)
- Branches: `feature/pipeline-ingest-to-cognee`, `fix/cognee-env-loading`, `fix/cognee-search-bugs`

Cognee-Aufrufe pro Datei: `cognee.add()` + `cognee.cognify()`.

VPS-Verifikation (2026-04-26):
- Test-Daily-Log → 25 Knoten / 46 Kanten extrahiert
- `cognee_search.py "Was hat Majid heute gemacht?"` liefert strukturierten Tagesablauf
- Knowledge-Graph-Beziehungen korrekt extrahiert (z.B. `majid --[family_member]--> neda`)
- Visualisierung via `cognee.visualize_graph()` funktioniert
- Pipeline funktioniert von beliebigem CWD aus (nach Bugfixes)

Bugfix-Runde während Schritt 6 — drei Bugs gefunden und behoben, alle in ADR-044 dokumentiert: (1) Cognee 1.0.3 lädt `.env` CWD-abhängig → `_cognee_env.py` löst es vor dem Cognee-Import; (2) `cognee_search.py` SearchType-Import-Pfad variiert zwischen Cognee-Versionen → SearchType komplett rausgenommen, Cognee-Default (GRAPH_COMPLETION) reicht für natural-language Queries; (3) Skripte funktionierten nicht ohne `PYTHONPATH` → sys.path-Setup am Skript-Header (`Path(__file__).resolve().parent.parent` in sys.path).

##### Verbleibende Schritte (offen)

- Schritt 7: Cognee als MCP-Tool für Jarvis registrieren (Memory-Queries aus Chat)
- Schritt 8: End-to-End-Test (Voice-Memo abends → morgens Frage stellen → korrekte Antwort)

##### Bekannte technische Schuld

- ANTHROPIC_API_KEY auf VPS doppelt gesetzt (Debug-Artefakt). Optional aufräumen wenn gewünscht.

### Phase 2.13 — Use-Case: WebUntis-Integration (Tahas Stundenplan)

Kein fertiger MCP verfügbar (Stand 2026-04-16). Drei Optionen für zukünftige Implementierung:

1. **iCal-Export → CalDAV-Abo**: Einfachste Option, WebUntis bietet iCal-URL pro Schüler. Abo in iCloud-Kalender, dann via bestehendem CalDAV-MCP sichtbar. **Vermutlich ausreichend**, Phase 2.13 nicht nötig.
2. **Eigener Untis-MCP**: Basierend auf `python-webuntis` Library. Aufwand ~1 Woche, nur wenn Phase-2-Skills mehr als nur Lesen brauchen.
3. **Foto via Vision**: Stundenplan-Foto → Claude Vision → Notion. Teil von Phase 2.13 IDP. Weniger reliable als iCal, aber ohne MCP-Overhead.

Empfehlung: Option 1 (iCal) zuerst probieren, bei Bedarf eskalieren.

Parallel: HOCH-MCPs einrichten (Gmail, Google Drive, CardDAV, Maps, HA)

---

## 9. PHASE 3 — VISION

Weitere Inputs (WhatsApp, iMessage, Voice) · Bildverarbeitung · Voice I/O (Whisper+TTS) · Claude API Migration evaluieren · Medien (Spotify, Apify)

| # | Feature | Beschreibung |
|---|---|---|
| 3.5 | MCP: Voice Output (TTS) | Text-to-Speech via ElevenLabs/OpenAI für Telegram Voice |

---

## 10. SELF-IMPROVEMENT (Phase 2.7)

**Prinzip:** `[Task] → [Evaluieren] → [Skill updaten/erstellen] → [Repeat]`

**Skill Library** (`/skills/`): Jeder Task = eine .md Datei mit Ausführungsstil, Patterns, optimierte Prompts, Erfolgsrate.
**Reflexion Loop:** Erfolg → Metriken updaten. Fehlschlag → Prompt rewriten. Kein Match → neuen Skill erstellen.
**Skill Router:** Wählt nach Verhalten (nicht Semantik), lernt aus Feedback.
**Dream Phase:** Nächtlich Skills mit niedriger Rate überarbeiten, neue Patterns konsolidieren.

### Skills-Aktivierungs-Kette

Phase 2.7 Self-Improvement braucht als Voraussetzungen in dieser Reihenfolge:

1. **Phase 1.5.5**: Filesystem-MCP (Skills als Dateien lesen/schreiben)
2. **Phase 1.5.7**: System-Prompt extern in `prompts/system.md` (damit Prompt-Teile durch Skills ergänzt werden können)
3. **Phase 1.5.6**: MEMORY.md Init (Skills brauchen Context aus Memory)
4. **Phase 1.5.4**: Session-Cleanup (Skill-State braucht Session-Boundary)
5. **Phase 2.1**: Cognee (Skills generieren neue Memories)
6. **Phase 2.7**: Self-Improvement aktiv

Reihenfolge strikt einhalten — vorzeitige Aktivierung führt zu Skill-State-Korruption.

---

## 11. EVAL SYSTEM (Phase 2.8)

**Code Eval:** pytest, Integration Tests, MCP Tool Tests, Docker Build, Smoke Test.
**Skill Eval:** A/B neue vs. alte Version, Rollback bei Verschlechterung.
**Agent Eval:** Benchmark-Tasks, Response-Qualität, Latenz, Cost-Tracking.

---

## 12. DESIGN-PRINZIPIEN

Async throughout · Kein Hardcoding (.env) · Logging (structlog) · Circuit Breaker (max 25 turns, max_tool_calls) · Docker-ready · Modular · MCP-basiert · System Prompt extern · Health Monitoring · Eval-gated

---

## 12a. OPS-NOTES

### Container-Stop vor Reboots

**Standard-Prozedur**: `docker compose stop` vor VPS-Reboots, **nicht** `docker compose down`.

- `stop` — hält Container an, behält Konfiguration/Netzwerke/Volumes. Nach `up -d` sofort wieder da, keine Neuerstellung.
- `down` — entfernt Container und Netzwerke. Nächstes `up -d` erzeugt alles neu (Container-IDs wechseln, Netzwerk-IPs wechseln, in-memory State verloren, MCP-Warmup läuft komplett von vorne).

Für regelmäßige Restarts (Code-Deploys) bleibt `docker compose up -d --build himes` — das ersetzt nur den einen Service. `down` nur bei strukturellen Änderungen (docker-compose.yml, Netzwerke, Volumes).

### Healthcheck-History

- **Bis 2026-04-17**: `docker-compose.yml` hatte einen `healthcheck`-Block der `curl -f http://localhost:8080/health` auf den Bot feuerte.
- **2026-04-17**: Block entfernt, weil der Bot keinen HTTP-Server hatte — Container ging in Restart-Loop.
- **Reaktivierung**: erst wenn Phase 1.5.8 den /health-Endpoint implementiert hat (siehe Status-Tabelle). Reihenfolge strikt: erst Endpoint, dann Healthcheck-Block zurück in compose.

### Historisch — Uncommitted-VPS-State (bis Phase 1.5.21)

Bis Phase 1.5.21 hat das Projekt einen VPS-First-Workflow verwendet (VPS als Working-Copy, Sync-Richtung VPS → Local → GitHub). Dies war pragmatisch für die frühe Entwicklung, wurde aber 2026-04-23 durch den Stage-2-Feature-Branch-Workflow abgelöst (siehe Sektion 2b und ADR-038).

Original-Doku zur historischen Referenz:

> **Uncommitted-VPS-State als Design-Pattern (nicht Bug)**
>
> Mehrere Phasen haben historisch Code direkt auf der VPS eingecheckt (nicht via git) und erst später auf Local/GitHub nachgezogen. Das ist dokumentiert in Phase 1.5.21 und hier bewusst akzeptiert — VPS ist Working-Copy, Local ist Canonical Repository, GitHub ist Remote of Record. Bei jedem größeren Update-Zyklus: VPS → Local → GitHub sync.

### Home Assistant Remote-Zugriff (Phase 1.5.33, pending)

Strategie: Cloudflare Tunnel statt DuckDNS/Nabu Casa.
- Domain: himes-home.uk ($5.30/Jahr bei Cloudflare, Registrierung pending)
- Alternative: himes-home.org falls .uk blockiert bleibt
- Tunnel-Route: himes-home.uk → HA Green :9583 (ha-mcp Add-on)
- Authentifizierung: Secret Path (/private_<REDACTED>)
- VPS-Zugriff: mcp-proxy wandelt HTTP-MCP in stdio für Claude SDK/CLI

**.env-Variable (Phase 1.5.33)**: `HA_MCP_URL` — URL des ha-mcp-Endpoints via Cloudflare Tunnel. Format: `https://himes-home.uk/private_<REDACTED>` (pending bis Domain + Tunnel aktiv).

### Tool-Errors strukturieren, nicht raisen

Erkenntnis aus Phase 1.5.20 (DB-FIX-1): Wenn Tool-Funktionen bei Fehlern Exceptions werfen oder unstrukturierte Error-Strings zurückgeben, halluziniert Claude die Error-Meldungen (z.B. "MCP-Server getrennt" wurde von Claude erfunden, war nirgends hardcoded).

**Pattern für alle MCP-Tools**:
```python
# Statt Exception raisen:
return {
    "ok": False,
    "error": "connection_timeout",
    "user_message_hint": "⚠️ Deutsche Bahn API aktuell nicht erreichbar. "
                          "Bitte gleich nochmal versuchen.",
    "retry_suggested": True,
    "status_code": 503,
    "detail": "Timeout nach 8s bei /journeys"
}
```

Claude übernimmt `user_message_hint` wortwörtlich → keine Halluzinationen, konsistente UX. Gilt für `himes_db`, `himes_mcp`, zukünftige eigene MCPs. Siehe ADR-018 + ADR-019.

### Python-Version: Lokal 3.9 vs Docker 3.11

Development-Umgebung von Majid hat Python 3.9 systemweit. HiMeS-Docker-Container nutzt 3.11. Das `mcp`-SDK braucht Python 3.10+.

**Konsequenzen**:
- Tests die `match`-Statement oder 3.10+-Syntax nutzen: conditional skippen via `pytest.mark.skipif(sys.version_info < (3, 10))`
- Für lokales Testen: Docker-Container nutzen (`docker compose exec himes pytest`) statt lokal `pytest`
- Bei neuen Features: 3.10+-Syntax OK, aber explizit in Test-Setup dokumentieren

**Alternativ**: Lokal `pyenv` mit 3.11 einrichten. Noch nicht gemacht, Priorität niedrig (Docker-Tests reichen).

### Ad-hoc-Scripts dürfen nicht stdlib überschatten

Rare Bug aus Phase 1.5.10: `/tmp/inspect.py` (ein Ad-hoc-Debug-Script) wurde bei `import inspect` anstelle der Python-stdlib geladen, weil `/tmp` im PYTHONPATH landete.

**Regel**: Ad-hoc-Scripts im Container oder auf VPS dürfen NIEMALS Python-stdlib-Namen haben (`inspect`, `os`, `sys`, `json`, `time`, etc.).

Prefix verwenden: `/tmp/debug_inspect.py`, `/tmp/himes_check.py`. Oder sofort nach Nutzung löschen.

### Zombie-Prozesse bei Service-Migration

Bei Phase 1.5.21 hat ein alter `mcp-caldav`-Prozess (vor systemd-Migration manuell gestartet) 2 Tage parallel zum neuen Service weitergelaufen trotz normaler `kill`-Signale. Port 8001 war belegt, neuer systemd-Service konnte nicht binden.

**Lösung**: `pkill -9 -f <pattern>` zwingt den Prozess ab. Beispiel:
```bash
pkill -9 -f mcp-caldav
# Danach systemd-Service starten, saubere Übernahme
```

**Prävention**: Bei Phase 1.5.22 (Deployment-Migration jarvis-caldav → Docker) vor dem ersten Container-Start:
```bash
ps aux | grep -E "mcp-caldav|jarvis-caldav" | grep -v grep
# Wenn Prozesse da sind: pkill -9 vor docker-compose up
```

### SDK-Usage: ClaudeSDKClient bevorzugt über query()

Aus Phase 1.5.10d-Debug: Die zwei SDK-Interfaces haben sehr unterschiedliches Verhalten.

| Interface | Verhalten | Use-Case |
|---|---|---|
| `query()` | Neuer Subprocess pro Call, ~12s Overhead | Einmalige Tasks |
| `ClaudeSDKClient` (async with) | Ein Subprocess, Session-Continuity | Dauer-Prozesse |

**Regel**: Für Jarvis-artige Anwendungen (Multi-Turn-Conversation, persistente Session) IMMER `ClaudeSDKClient` im `async with`-Block. `query()` nur für One-Off-Tasks (z.B. isolierte Analyse-Jobs).

Referenz: GitHub Issue #34 des claude-agent-sdk-Repos. Relevant für Phase 1.5.22 Backend-Protocol-Design (SDKBackend nutzt ClaudeSDKClient, APIBackend wird eigenes Pattern haben).

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
| 009 | Claude API langfristig evaluieren | Phase 3 oder früher bei Bedarf, vorbereitet durch ADR-026 |
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
| 020 | MCP Wellenmodell: Basis → Kern → Erweiterung statt alles auf einmal | Geplant |
| 021 | Open-Meteo statt kommerzieller Wetter-API: Kostenlos, kein API-Key, global | Geplant |
| 022 | PaulvonBerg/db-mcp-server für DB: Python, umfassender, Cloud-ready | Geplant |
| 023 | Claude Code CLI/SDK bleibt Primär-Backend (nicht API) wegen Testing-Kosten. Abo-basiert unbegrenzt, API wird nur bei Bedarf als Zweit-Backend gehängt. Revision in 6 Monaten oder bei Voice-Bedarf. | Aktiv |
| 024 | SDK-Streaming-Limit: `claude-agent-sdk==0.0.25` aggregiert TextBlocks, keine Token-Deltas. Event-Log-Analyse 2026-04-18: finale TextBlocks kommen 88-300ms vor Response-Ende als Ein-Block. Token-Streaming erst mit API-Migration (ADR-009) möglich. | Aktiv |
| 025 | Tool-Progress-Updates statt Token-Streaming (Phase 1.5.10f): Bei ToolUseBlock-Events editierbare Status-Nachricht in Telegram. Ersetzt ursprünglichen 1.5.10f-Plan (durch ADR-024 nicht realisierbar). Optional, nach 1.5.22 + 1.5.26. | Geplant |
| 026 | ClaudeBackend-Protocol als Pflicht-Vorbereitung (Phase 1.5.22): Protocol so designed, dass CLI/API/Realtime als austauschbare Backends implementierbar sind. Spätere Migration = Feature-Flag, kein Refactoring. Kritischer Pfad vor 1.5.4 und 1.5.2. | Geplant |
| 027 | Tool-Whitelist als Latenz + Security-Strategie (Phase 1.5.10e v2): `allowed_tools` in ClaudeCodeOptions (v2a) + ENABLE_TOOL_SEARCH=false (v2b). Ergebnis: -1-2s Latenz + harte Security-Absicherung (CronCreate/Bash/Edit physisch ausgeschlossen). Commits 15da656 + 3c316b2. | Aktiv |
| 028 | Tool-Manifest + Proaktivitäts-Regel (Phase 1.5.26): Jarvis hat aktive Selbstkenntnis über Werkzeuge + Skills, kombiniert proaktiv Cross-Over (Kalender+Wetter, Bahn+Kalender, etc.). Auto-generiert aus mcp_config.json. Fundament für Phase 2.7. | Geplant |
| 029 | Wochentag-Halluzinations-Schutz (Phase 1.5.25 + 1.5.30): Zwei-Schicht. System-Prompt-Regel domain-übergreifend pflicht auf time-MCP bzw. himes-tools Datum-Tools (`get_weekday_for_date`/`add_days`/`days_between`/`next_weekday`). HallucinationGuard `weekday`-Domain als Safety-Net. **Ersetzt durch ADR-031** (2026-04-20): weekday-Domain produzierte False-Positives bei Session-Memory-Antworten (Tool im aktuellen Turn nicht gerufen, aber Antwort faktisch korrekt). CalendarAssertion (deterministisch via Python-stdlib) löst beide Probleme. Prompt-Regel + Datum-Tools bleiben weiterhin aktiv (primary defense), nur das Tool-Tracking-Safety-Net wurde entfernt. | Ersetzt durch ADR-031 |
| 030 | CalDAV Recurrence-Handling (Phase 1.5.29): `calendar.search(expand=True)` server-side + widen ±14 Tage + client-side DTSTART-Filter. Nötig weil iCloud Overrides per RECURRENCE-ID (Original-Slot) match, nicht neuer DTSTART. Unterstützt moved/shifted Instanzen für Narrow-Range-Queries (z.B. get_today_events an verschobenem Tag). Kosten: ~28× mehr Daten bei Tages-Query — iCloud-Latenz dominiert, Payload-Overhead vernachlässigbar. | Aktiv |
| 031 | Calendar Assertion-Layer (Phase 1.5.32) — Check A live seit 2026-04-20: deterministische Wochentag-Validierung via `datetime.date.weekday()` statt Tool-Call-Tracking. Disclaimer enthält konkrete Korrektur statt nur "nicht verifiziert". Ersetzt ADR-029 weekday-Tracking-Domain. Vorteil: funktioniert auch bei Session-Memory-Antworten (kein Tool-Call im Turn nötig). Begleit-Maßnahme: `requirements.lock` für reproduzierbare Builds (Deploy-V1 hatte CalDAV-Regression durch Pip-Versions-Drift, V2 mit Lock erfolgreich). Check B (DTSTART-Bucketing-Validierung) bleibt offen. | Aktiv |
| 032 | ha-mcp (homeassistant-ai) als Home Assistant MCP-Server statt offizieller HA MCP-Integration. Entscheidung basiert auf: (a) HA OS Add-on verfügbar (simple Installation), (b) 86 Tools über 34 Module (umfassend), (c) aktive Entwicklung, (d) HTTP-Transport kompatibel mit mcp-proxy für Remote-Zugriff. Alternativen geprüft: voska/hass-mcp (weniger Tools), tevonsb/homeassistant-mcp (abandoned), mtebusi/HA_MCP (kleiner Scope). Phase 1.5.33. | Aktiv |
| 033 | Search MCP: Tavily + Exa statt Brave Search. Brave Search hat Free Tier im Februar 2026 eingestellt. Tavily und Exa bieten beide kostenlose Tiers ohne Credit-Card-Requirement. Redundanz durch zwei Provider reduziert Ausfall-Risiko, erhöht Query-Qualität bei schwierigen Suchen. Aktivierung: Phase 1.5.9. | Geplant |
| 034 | Anchor-basiertes Memory-Schema (Phase 2.1 Vorarbeit, 2026-04-23): Personen-Beziehungen werden relativ zum Primary User (Majid) im Frontmatter-Feld `rel_to_anchor` definiert statt redundant in jeder Entity-Datei. Multi-User über temporären Anchor-Wechsel zur Query-Zeit. Abgeleitete Beziehungen via Graph-Traversal (`anchor.son.mother`, `anchor.spouse.mother`). Skalierbar für große Familien, Multi-User-ready ohne späteres Refactoring. Volle Spezifikation + 10 Grundregeln in docs/memory-schema.md. | Akzeptiert |
| 035 | Memory-Typen reduziert auf 4 (Phase 2.1 Vorarbeit, 2026-04-23): HiMeS speichert nur Daily-Log, Entity-Person, Insights, Conversation — also nur das was in keinem anderen Tool existiert (Gedanken-Strom, persönliche Sicht auf Menschen, Charaktermuster, Jarvis-Gespräche). Ort, Medikament, Konzept, Meeting, Research werden in Calendar/Notion/etc. gespeichert, nicht in HiMeS. Vermeidet Doppel-Speicherung; Jarvis als Orchestrator routet Anfragen zur richtigen Quelle. | Akzeptiert |
| 036 | Initial-Daten-Strategie passiv (Phase 2.1 Vorarbeit, 2026-04-23): Familien-Daten werden nicht initial via Setup-Skript eingegeben. Jarvis erstellt Entity-Dateien organisch beim Erkennen in Daily-Logs und fragt bei Bedarf nach. Nur die Anchor-Datei `majid-ahsan.md` wird initial erstellt. Vermeidet Cold-Start-Datenpflege-Aufwand und liefert nur Daten die tatsächlich gebraucht werden. | Akzeptiert |
| 037 | Drei-Schichten-Gedächtnis mit Dreaming-Phase (2026-04-23): Konzept eingebracht von Majid: Kurzzeit/Mittelzeit/Langzeit-Gedächtnis mit nächtlicher Sortierung um 3:30 Uhr durch Jarvis. Architektur betrifft alle Memory-Typen (Memory-Typ 4 Conversation eng verbunden). Verhältnis zu ADR-015 (3-Layer Memory: MEMORY.md + Cognee Graph + Rules) noch zu klären. Volle Spezifikation steht aus. | In Diskussion |
| 038 | Stage-2-Feature-Branch-Workflow als Standard (2026-04-25): Mac entwickelt, GitHub ist Quelle der Wahrheit, VPS pullt. Direkte VPS-Edits verboten (außer Notfall-Hotfix). Feature-Branches für alle nicht-trivialen Änderungen, `--no-ff` Merges. Löst den früheren VPS-First-Workflow ab (siehe Phase 1.5.21 Doku, jetzt historisiert). Volle Spezifikation in Sektion 2b. | Akzeptiert |
| 039 | Cognee-Setup mit Anthropic + Fastembed (2026-04-25): Cognee 1.0.3 als separater Service unter /home/ali/cognee/ (eigenes venv parallel zu HiMeS). LLM-Provider Anthropic Claude (Modell claude-haiku-4-5-20251001, kostengünstig für Knowledge-Graph-Extraktion), Embedding-Provider Fastembed lokal (sentence-transformers/all-MiniLM-L6-v2, keine externe API-Kosten). Datenbanken SQLite + LanceDB + Kuzu file-based (default, kein zusätzlicher DB-Server). Setup-Skripte im Repo unter cognee-setup/ für Reproduzierbarkeit. | Akzeptiert |
| 040 | Cognee 1.0.3 Anthropic-Adapter Bug-Workaround (2026-04-25): Cognee 1.0.3 reicht `max_tokens` nicht an Anthropic-API durch. Resultat: 128s Tenacity-Retry-Loop ohne klaren Fehler, der wie Timeout aussieht. Workaround: `LLM_ARGS={"max_tokens":4096}` in .env. Bei zukünftigen Cognee-Updates prüfen ob Bug gefixt und Workaround entfernen. | Akzeptiert (Workaround) |
| 041 | OAuth-Token nicht für Cognee verwendbar (2026-04-25): Anthropic OAuth-Tokens (`sk-ant-oat01-`) funktionieren nur für simple Messages, nicht für Tool-Use/Function-Calling. Cognee braucht klassischen API-Key (`sk-ant-api03-`). Konsequenz: HiMeS und Cognee teilen denselben klassischen API-Key. Bei zukünftiger Multi-User-Erweiterung über Telegram möglicherweise pro-User-Keys nötig. | Akzeptiert (Erkenntnis) |
| 042 | Cognee speichert absolute Pfade in Data-Metadata (2026-04-25): Die SQLite-Tabelle `Data` (cognee/modules/data/models/Data.py) enthält die Spalten `raw_data_location` und `original_data_location` mit absoluten Pfaden zu ingestierten Dateien. Diese zeigen typischerweise unter `DATA_ROOT_DIRECTORY`. Konsequenz: bei zukünftiger Migration von `DATA_ROOT_DIRECTORY` (im Gegensatz zu `SYSTEM_ROOT_DIRECTORY`, das nur DB-Container-Pfade beeinflusst) reicht ein `mv` der Daten-Dateien nicht — die Pfade in der SQLite-Metadata müssen ebenfalls umgeschrieben werden, sonst zeigen `raw_data_location`/`original_data_location` ins Leere. Aktuell (Phase 2.1 Schritt 3) irrelevant, weil DBs leer sind und Erstbefuellung nach Move passiert. Erkenntnis aus Phase-A-Aufklärung der Daten-Dir-Migration. | Akzeptiert (Erkenntnis) |
| 043 | Cognee Multi-User-Access-Control Default akzeptiert (Phase 2.1 Schritt 4, 2026-04-25): `ENABLE_BACKEND_ACCESS_CONTROL` bleibt AN (Cognee-Default). Cognee verwaltet User-Trennung damit automatisch. Aktuell Single-User (nur Majid), aber Default ist bereits multi-user-ready für späteren Ausbau (Telegram-Multi-User mit Neda/Taha/Hossein). Konsistent mit ADR-035 (Anchor-System multi-user-vorbereitet). Blockiert nichts: Schalter kann bei zukünftigem Bedarf ohne Datenverlust revidiert werden. | Akzeptiert |
| 044 | Cognee lädt .env CWD-abhängig + Skript-Path-Setup + SearchType weggelassen (2026-04-26): Cognee 1.0.3 liest seine .env-Datei nur aus dem aktuellen Working-Directory. Pipeline-Skripte (ingest_to_cognee.py, cognee_search.py) lösen das dreifach: (1) eigenes .env-Loading via pipeline/_cognee_env.py BEVOR cognee importiert wird; (2) sys.path-Manipulation am Skript-Header (`Path(__file__).resolve().parent.parent` in sys.path), damit das `pipeline`-Paket auch ohne PYTHONPATH gefunden wird, wenn das Skript von beliebigem CWD aus aufgerufen wird (`python3 /pfad/zu/cognee_search.py "query"` aus / oder /tmp); (3) `cognee.search()` wird OHNE `query_type=` aufgerufen — Cognee-Default (GRAPH_COMPLETION) liefert beste Antworten für natural-language Queries und der konkrete SearchType-Import-Pfad variiert zwischen Cognee-Versionen (cognee.shared.data_models in <1.0 vs cognee.modules.search.types.SearchType in 1.0.3), darum für MVP weggelassen. ImportError-Behandlung wurde entsprechend verschärft: nur `ModuleNotFoundError` mit `e.name == "cognee"` wird mit freundlicher Meldung maskiert, alle anderen ImportErrors aus Cognee-Internals werden durchgereicht (voller Stack-Trace), damit echte Ursachen sichtbar bleiben. Konsequenz für später: MCP-Server (Schritt 7) und Whisper-Pipeline müssen dasselbe Pattern (env-Loading + sys.path-Setup) nutzen; falls dort spezifische SearchTypes nötig werden, dort als optionaler Parameter wieder einbauen. Test: cognee_search.py aus / aufgerufen findet die DBs korrekt und liefert sinnvolle Antworten. | Akzeptiert (Workaround) |

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

### Phase 1.5.22 — ClaudeBackend-Protocol mit API-Migrations-Vorbereitung
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.22 — ClaudeBackend-Protocol + MCP-Kategorisierung + Deployment-Standard.

Ziel: Architektur so vorbereiten, dass späterer Switch zu API/Hybrid/Realtime ohne Refactoring möglich ist. Siehe Sektion 2a + 1b + 1c + ADR-026.

Scope:
1. ClaudeBackend-Protocol (core/backends/base.py) — abstraktes Interface
2. SDKBackend (core/backends/sdk_backend.py) — aktueller SDKClient adaptiert
3. APIBackend (core/backends/api_backend.py) — NUR Stub mit Interface, NICHT implementieren
4. UserContext-Dataclass durchreichen
5. MCP-Kategorisierung in mcp_config.json (core/personal/transport/home)
6. ADR-026 schreiben (docs/adr/026-backend-protocol.md)

Scope NICHT drin:
- Tatsächliche API-Implementation
- MCP-Bridge für API (später)
- Code-Änderungen an MCPs selbst

Aufwand: ~1 Woche. Kritischer Pfad vor 1.5.26 und 1.5.4.
```

### Phase 1.5.26 — Tool-Manifest + Proaktivitäts-Regel
```
Lies docs/MASTER-REFERENCE.md. Du bist Lead Developer für HiMeS.
Task: Phase 1.5.26 — Tool-Manifest + Proaktivitäts-Regel.

Ziel: Jarvis bekommt aktive Selbstkenntnis über Werkzeuge und Skills, kombiniert proaktiv Cross-Over bei komplexen Anfragen. Siehe Sektion 1d + ADR-028.

Scope:
1. Auto-Discovery-Script (core/tool_manifest_generator.py) — liest bei Bot-Start mcp_config.json + MCP-Schemas, generiert prompts/tool_manifest.md
2. prompts/skill_manifest.md — initial leeres Template mit Struktur
3. prompts/system.md erweitern — Proaktivitäts-Regel + Cross-Over-Beispiele + Tool-Manifest-Referenz
4. Settings-Flag TOOL_MANIFEST_AUTO_UPDATE: bool = True (Default)
5. Tests: 5 Cross-Over-Szenarien (Kalender+Wetter, Bahn+Kalender, Notion+Kalender, Things3+Kalender, Bahn+Wetter)
6. ADR-028 schreiben

Scope NICHT drin:
- Skill-Befüllung (kommt in Phase 2.7)
- Automatische Skill-Erkennung aus Nutzung (Phase 2.7)

Reihenfolge: NACH 1.5.22 (weil Manifest ins Backend-Protocol integriert wird), VOR 1.5.4.

Aufwand: 1-2 Tage.
```

### Phase 1.5.25 — Wochentag-Halluzinations-Schutz (Mini-Ticket)
```
Lies docs/MASTER-REFERENCE.md Sektion 1b (Musikschule-Bug).

Task: Wochentag-Halluzinations-Schutz.

Minimal-Scope:
1. System-Prompt-Regel ergänzen: "Bei Wochentag-Angabe aus einem Datum IMMER time-MCP convert_time nutzen, NIE aus dem Kopf berechnen"
2. Beispiel einbauen: "2026-04-24 → time-MCP fragen → 'Freitag', nie raten"
3. Optional: HallucinationGuard-Pattern für Wochentag-Claims ohne vorhergehenden time-MCP-Call

Aufwand: 15-30 Min.
```

---

## 15a. OFFENE FRAGEN

- [ ] Google Maps API Key: Welches Billing-Modell?
- [ ] Deutsche Bahn API: Client-ID beantragen bei developers.deutschebahn.com
- [ ] Home Assistant: Cloudflare Tunnel oder direkte Anbindung?
- [ ] Notion MCP: Integration Token erstellen
- [ ] MCP Gateway: Brauchen wir einen zentralen MCP-Proxy bei >10 Servern?

---

## 15. CHANGELOG

| Datum | v | Änderung |
|---|---|---|
| 2026-04-26 | 25.13 | Phase 2.1 Schritte 5+6 ✓. Schritt 5 (Voice-Memo→Markdown, 2026-04-25, Branch `feature/pipeline-voice-to-md`): `pipeline/voice_to_md.py` (stdlib-only, drei Aufruf-Modi Stdin/`--file`/`--text`, `--user`/`--date`/`--time`/`--data-dir`, Path-Traversal-Schutz für `--user`, `## (Erster Eintrag)`/`## HH:MM` Append-Pattern), 16 Tests grün, drei VPS-Erfolgskriterien-Tests verifiziert. Schritt 6 (Markdown→Cognee, 2026-04-26, Branches `feature/pipeline-ingest-to-cognee` + `fix/cognee-env-loading` + `fix/cognee-search-bugs`): `pipeline/ingest_to_cognee.py` (drei Modi `--file`/`--dir`/`--all`, SHA-Hash-Tracking in `<data-dir>/.ingested.json`, Re-Ingest bei Hash-Änderung, Date-Validation-Prompt mit `--yes`-Override), `pipeline/cognee_search.py` (CLI-Suche aus beliebigem CWD), `pipeline/_cognee_env.py` (lädt cognee/.env vor cognee-Import), 56 Pipeline-Tests grün (16+20+10+10), VPS-verifiziert: 25 Knoten/46 Kanten aus Test-Daily-Log, Knowledge-Graph-Beziehungen korrekt extrahiert (`majid --[family_member]--> neda`), `cognee.visualize_graph()` funktioniert. Drei Bugs während Schritt 6 gefunden und gefixt (alle in ADR-044): Cognee-CWD-abhängiges .env-Loading, SearchType-Import-Pfad versions-instabil → ohne `query_type=` aufrufen, sys.path-Setup am Skript-Header für CWD-unabhängige Aufrufe. Schritte 5 und 6 aus „Verbleibende Schritte" entfernt — offen bleiben Schritt 7 (Cognee als MCP-Tool für Jarvis) und Schritt 8 (End-to-End-Test). Keine neue technische Schuld. |
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
| 2026-04-20 | 35 | Architektur-Notizen aus Strategie-Chat (v6-v24) nachgetragen: (a) Cognee-Evaluierung bei Phase 2.1 (Docker, 2-4GB RAM, cognee-mcp existiert, 4 Operationen). (b) Skills-Abhängigkeitskette bei Phase 2.7 (6 Phasen-Reihenfolge dokumentiert). (c) WebUntis-Integration als optionaler Use-Case bei 2.13 (3 Optionen: iCal/MCP/Vision, Empfehlung iCal). |
| 2026-04-20 | 34 | OPS-NOTES aus Phase-1.5.10/1.5.21-Debrief ergänzt: (a) Ad-hoc-Scripts dürfen nicht stdlib überschatten (rare Bug). (b) Zombie-Prozesse bei systemd-Migration via `pkill -9` beenden (relevant für Phase 1.5.22 jarvis-caldav-Migration). (c) SDK-Usage ClaudeSDKClient vs query() dokumentiert (GitHub Issue #34). |
| 2026-04-20 | 33 | Neue Phase 1.5.34 (Telegram Attribution in Replies) aus Phase-1.5.20-Debrief-Chat: UX-Verbesserung, Trigger-Quelle in Bestätigungen mitschicken. Motivation: Things-3-Crash-Incident, Majid wollte Autonomie-Level klarer sehen können. |
| 2026-04-20 | 32 | OPS-NOTES ergänzt aus Phase 1.5.20 Debrief: (a) Tool-Error-Strukturierung als Halluzinations-Prävention (Lehre aus DB-FIX-1). (b) Python-Version-Mismatch 3.9/3.11 dokumentiert (mcp-SDK braucht 3.10+). Beide als OPS-Pattern für zukünftige MCP-Entwicklung. |
| 2026-04-20 | 31 | **Parallel-Chat-Sync (HA-MCP + MCP-Recherche).** (a) Phase 1.5.33 Home Assistant MCP Integration neu angelegt (🔶 In Progress): ha-mcp Add-on auf HA Green installiert (86 Tools in 34 Modulen), Claude Desktop via mcp-proxy verbunden, VPS-Integration pending — wartet auf Cloudflare-Domain (himes-home.uk) + Tunnel. (b) Phase 1.5.9 umbenannt Brave Search → Tavily+Exa (Brave kein Free Tier mehr seit Feb 2026). (c) MCP-Katalog präzisiert: konkrete Package-Namen für Weather (`@dangahagan/weather-mcp`), Gmail (`ArtyMcLabin/Gmail-MCP-Server`, 🔶 pausiert wegen Security-Review), Google Maps (`modelcontextprotocol/server-google-maps` offiziell Anthropic, 🔶 pausiert wegen Billing-Account). (d) Neue Verworfen-Sektion: Apple Reminders (VPS-inkompatibel), Apple Maps (keine strukturierten Daten), Brave Search (kein Free Tier), Perplexity (Kostenmodell inkompatibel mit ADR-023). (e) Eigener DB-MCP auf transport.rest als Phase 2.17 angelegt (2-3 Wochen Aufwand, nach Phase 1.5-Abschluss). (f) ADR-032 (ha-mcp-Wahl) + ADR-033 (Tavily+Exa statt Brave). (g) OPS-NOTES: Home-Assistant-Remote-Zugriff-Strategie (Cloudflare Tunnel, Secret Path in .env nicht committed). |
| 2026-04-20 | 30 | Phase 1.5.28 Schicht 1: things-mcp reaktiviert nach Cultured Code Cloud-Cleanup (Ticket vom 2026-04-17 beantwortet, vergiftete History-Indices bereinigt; initial sync nach Reaktivierung: 2 changes). `docker start things-mcp` + `restart=unless-stopped`. HiMeS-Bot restart. 4 manuelle Test-Szenarien erfolgreich (2 reads: `things_list_today/inbox/anytime/upcoming/completed`; 2 writes: "einkaufen" als ASCII + "neda anrufen morgen" mit Datum-Tool-Berechnung via `time__get_current_time`+`himes-tools__add_days`). things-mcp-Log zeigt beide Writes als saubere `action=0` (neue Tasks, Indices 7402+7403), keine Rapid-Fire-Schleife wie am 17.04 (damals 7× `action=1` auf selbe UUID in 2s). Tasks in Things3-App auf Mac+iPhone sichtbar, keine Crashes. Schicht 2 (Härtung: Input-Sanitization, Unicode-Filter, Dry-Run-Mode) weiterhin offen, Priorität niedrig solange keine neuen Incidents. |
| 2026-04-20 | 29.3 | Post-Deploy User-Testing der 2026-04-19-Kalender-Session dokumentiert in Sektion 1e. Core-Bugs bestätigt weg (verschobene Musikschule sichtbar, "nächste Musikschule Fr 24.04", Wochentags-Labels Mo-So konsistent). Zwei Drift-Muster bestätigt die 1.5.32 erzwingen: Event-zu-Tag-Drift (5 Mi-Events unter Di gelandet) + Historische-Recap-Halluzination (Pilates: alle 5 Daten als Dienstag annotiert, alle sind Mittwoch; tool_calls=1, `get_weekday_for_date` nicht aufgerufen trotz Pflicht-Regel). Guard-Disclaimer fiel korrekt in beiden Fällen. 1.5.32 Status-Zeile auf **PFLICHT** präzisiert mit konkreter Scope-Definition aus Test-Befunden. Kein Code-Change. |
| 2026-04-19 | 29.2 | Kalender-Komplett-Fix-Session nach Musikschule-Bug-Incident. Vier Commits über zwei Repos: (a) caldav-mcp `eddfab6` — date_search→search(expand=True), löst Multi-VEVENT-Blob-Parse-Fehler; (b) caldav-mcp `1870046` — widen ±14 Tage + client-side DTSTART-Filter, löst iCloud-RECURRENCE-ID-Matching-Quirk der moved Instanzen für Narrow-Range-Queries unsichtbar machte; (c) HiMeS `068837f` — Phase 1.5.25 Wochentag-Halluzinations-Schutz (Prompt-Regel + HallucinationGuard weekday-Domain); (d) HiMeS `da69a25` — Phase 1.5.30 Time-Arithmetic Tools in himes-tools (`get_weekday_for_date`/`add_days`/`days_between`/`next_weekday`) + strikte Event-zu-Tag-Bucketing-Regel. Reale Bugs verifiziert: Musikschule am Sonntag 19.04 erscheint jetzt korrekt, "nächster Freitag" korrekt 24.04 statt 25.04, Wochentags-Labels Mo 20–So 26 konsistent. Restproblem: Event-zu-Tag-Drift bei langen Wochenübersichten (5 Mi-Events unter Di gelandet) nur teilweise durch Prompt reduziert, Phase 1.5.32 Calendar Assertion-Layer als offenes Folge-Ticket dokumentiert. Neue Sektion 1e mit vollem Session-Protokoll, neue Zeilen für Phase 1.5.29/1.5.30/1.5.32 in Status-Tabelle, ADRs 029/030/031. Tests: caldav-mcp 105/105 grün, HiMeS 73/73 grün. |
| 2026-04-19 | 29.1 | Backlog-Items aus 17.04-Incident nachgetragen. (a) Phase 1.5.8 Health Monitoring präzisiert: ZUERST /health-Endpoint in core.orchestrator (aiohttp Port 8080), DANN healthcheck-Block in docker-compose.yml reaktivieren. Reihenfolge kritisch — der Block war am 17.04. entfernt worden weil Bot keinen HTTP-Server hatte, sonst Container-Restart-Loop. (b) Neue Phase 1.5.27 Tool-Loop-Guard im Orchestrator (mittlere Priorität, nach 1.5.4): identische Tool-Args >2× im selben Turn → synthetisches Error-Result statt Wiederholung. Beleg aus 17.04-Log: caldav_get_today_events 11× hintereinander in einem Turn. (c) Neue Phase 1.5.28 things-mcp Härtung (niedrige Priorität, nach 1.5.3): Input-Sanitization Unicode-Control-Chars + Date-Format-Validation + Dry-Run-Mode, wartet auf Cultured Code Support. (d) Neue Sektion 12a OPS-NOTES: `docker compose stop` vs `down` Semantik, Healthcheck-History, Uncommitted-VPS-State als akzeptiertes Design-Pattern. Reihenfolge-Zeile erweitert um 1.5.27 + 1.5.28. |
| 2026-04-19 | 29 | Strategische Neuausrichtung + Phase 1.5.10e v2 Abschluss. Vier parallele Stränge: (a) Phase 1.5.10e v2 deployed — v2a allowed_tools-Whitelist (Commit 15da656) + v2b ENABLE_TOOL_SEARCH=false (Commit 3c316b2). ToolSearch komplett eliminiert, -1-2s pro Anfrage on top von v2a's eager-schema-loading. Gesamt-Latenz-Verbesserung seit 1.5.10d: -20 bis -77% je Szenario. Tool-heavy (CalDAV/Notion) limitiert durch externe APIs, nicht mehr durch ToolSearch. (b) SDK-Streaming-Limit bestätigt durch Event-Log-Analyse von 5 realen Anfragen — claude-agent-sdk==0.0.25 aggregiert TextBlocks, keine Token-Deltas (finale Blocks kommen 88-300ms vor Response-Ende). Token-Streaming erst mit API-Migration möglich (ADR-024). (c) Strategie-Entscheidung: CLI/SDK bleibt Primär-Backend (Abo-gedeckt, Testing unbegrenzt, 0€ API-Kosten). API wird bei Bedarf als Zweit-Backend eingehängt (ADR-023). Phase 1.5.22 wird kritischer Pfad vor 1.5.4/1.5.2. (d) Phase 1.5.10f umgedeutet von Token-Streaming → Tool-Progress-Updates (ADR-025). Neue Phasen 1.5.25 (Wochentag-Halluzination, 15-30min Mini-Ticket nach Musikschule-Bug am 18.04) und 1.5.26 (Tool-Manifest + Proaktivitäts-Regel, 1-2 Tage, Fundament für Phase 2.7). Neue ADRs 023-028. Neue Sektionen 1b (Strategische Neuausrichtung), 1c (Kosten-Strategie + Voice-Pfad), 1d (Phase 1.5.26 Detail-Spezifikation), 2a Vorbereitung 5 (API-Migrations-Hook im Protocol). Neue Prompt-Templates 1.5.22, 1.5.26, 1.5.25. |
| 2026-04-17 | 28 | +MCP Erweiterungsplan (25 Server, 4 Wellen), +Phase 2.15/2.16, +Phase 1.5.23/1.5.24, +Phase 3.5, +ADR-020/021/022, +MCP Tabelle erweitert |
| 2026-04-17 | 27 | Phase 1.5.21 ✅: CalDAV Stabilität. Debugged ausgehend von User-Report "Bot hängt bei Termin-Abfrage". Drei unabhängige Bugs im caldav-mcp Repo (separates Projekt, bisher ungetracktes Basis-Fork von madbonez) identifiziert und behoben. (a) **Starlette-SSE-Route** (commit 3802c56): handle_sse() gab None zurück, Starlette 0.50 erwartet aber Response-Objekt → TypeError bei jedem /sse Request (604 Exceptions in 2 Tagen Laufzeit). Der Bug war tolerierbar solange mcp-remote (im Bot-Container) eine einmal etablierte SSE-Session poolte — brach aber bei jedem docker compose up --build. Fix: `return Response()` nach connect_sse-Block + debug=False. (b) **Ungetrackte Phase-1.5.15-Extensions** (commit 93608f1): 420 Zeilen Nominatim-Geocoding + update_event-Tool + ORGANIZER-Feld waren seit April 13 im VPS working-tree uncommitted — gingen fast verloren beim Debug. Gesichert als eigener commit bevor weitergearbeitet wurde. (c) **keepalive timeout** (commit 86ce5e3): Apple iCloud schließt idle HTTP-keepalives nach ~60-90s; niquests connection pool merkt's erst beim nächsten Request → hard ConnectionError. Retry-Decorator `@retry_on_stale_connection` auf 9 Apple-facing CalDAVClient-Methoden (list_calendars, create_event, get_events, get_today_events, get_week_events, get_event_by_uid, update_event, delete_event, search_events). Walkt Exception-Chain nach NiquestsConnectionError oder Substring-Markers (keepalive timeout, connection reset, remote end closed, …). Diskriminiert von 401/404/ValueError die unverändert durchgereicht werden. connect() bewusst NICHT dekoriert (Loop-Risiko). (d) **Prozess-Management**: jarvis-caldav.service (systemd, Port 8001) als einziger Persistenz-Mechanismus — mit Auto-Restart bei pkill. Caddy proxyed https://caldav-ahsan.duckdns.org/sse → localhost:8001. **Tests**: 95 Unit-Tests grün (86 alt + 9 neu in tests/test_retry.py) + 1 E2E-Smoke-Test in tests/e2e/test_stale_reconnect_e2e.py (NiqConnError-Injection via monkey-patch der principal.calendars). **Live-Verifikation**: Stale-Path mit injiziertem NiqConnError getriggert → Log zeigte "stale_connection_detected → reconnect (635ms) → retrying → OK 1.44s gesamt". **Offen**: caldav-mcp remote ist upstream madbonez Fork, 4 neue Commits liegen nur auf VPS — entweder eigenes GitHub-Fork anlegen oder lokaler Mirror manuell syncen. | |
| 2026-04-16 | 26 | Phase 1.5.10e REVERTED: Versuch ENABLE_TOOL_SEARCH=false via ClaudeCodeOptions.env zu setzen (offizieller Anthropic-Switch bei <10 Tools empfohlen; wir haben ~25 auf 6 MCPs). Messung: Things 22s→8.5s (-13.5s, super), Zug ähnlich (17.6s→22.7s, Varianz), aber CalDAV produzierte User-sichtbare "Verbindungsunterbrechung"-Fehlermeldungen obwohl Tools laut Log aufgerufen wurden (caldav_list_calendars ×2, caldav_create_event ×2 = Claude-Retries nach Error-Response). Remote-Server HTTP 200, Kausalität ungeklärt — möglicherweise MCP-Handshake-Race mit dem Tool-Search-Disable. Laut Task-Regel "Qualität > Speed → REVERT" env-Setting entfernt. Latenz-Reduktion bei Things wäre attraktiv (60% weniger), aber nur mit CalDAV-Stabilität verhandelbar. Offen für 2. Anlauf mit explizitem allowed_tools whitelist statt Env-Var. | |
| 2026-04-16 | 25 | Phase 1.5.10 ✅: Latenz-Optimierung komplett. (a) Telegram Typing-Indikator als async Task der alle 4s send_action("typing") ruft, gestoppt im finally (telegram_adapter.py). (b) Pre-Classification: regex-basierte _INSTANT_REPLIES für Grüße/Danke/Bestätigungen (^...$ Anker) umgehen Claude komplett — "hallo", "danke", "ok" antworten <100ms ohne API-Call. (c) claude-code-sdk Integration: neuer core/sdk_client.py mit persistentem Singleton ClaudeSDKClient (connect einmal beim Bot-Start, alle Messages nutzen denselben warmen Subprocess). Feature-Flag CLAUDE_USE_SDK_CLIENT (default true). Orchestrator ruft _send_to_claude() → SDK zuerst, bei SUBPROCESS_CRASH oder Exception transparenter Fallback auf ClaudeSubprocess (unverändert). Retries gehen immer über robusten Subprocess-Pfad. Zwei post-deploy Fixes: (1) date.today()-Vergleich statt Prompt-String-Vergleich — verhinderte ~4.3s-Reconnect pro Minute weil Uhrzeit im Prompt drin war. (2) ResultMessage.result als Source of Truth statt akkumulierter TextBlocks — verhinderte Claude's Denk-Zwischentexte ("Ich lade zuerst das Tool-Schema...") in der Antwort. Monkey-Patch für SDK-0.0.25-Bug (rate_limit_event). Gemessen: erste Nachricht ~30s (MCP Cold-Start), Folge-Nachrichten ~15s, kurze Frage ohne Tool ~4s. Session-Continuity bestätigt (test_sdk_v2.py: Claude erinnerte "42" über 4 Nachrichten). Alle 6 MCPs verifiziert (caldav, weather, things3, time, deutsche-bahn, himes-tools/notion+memory), keine Funktionsregression. |
| 2026-04-16 | 24 | DB-FIX-7 (Smart-Split + UX-Polish): DB-FIX-7a — db_search_connections machte EINE Query mit `departure=requested-45min, results=10` → bei lokalen Bussen lieferte HAFAS 10 Ergebnisse ALLE im Rückwärts-Fenster, "after"-Bucket blieb leer. Fix: ZWEI separate Queries — (1) after: departure=requested, results=5, filter >=requested, take 4. (2) before: departure=requested-20min, results=4, filter <requested, take 1. Dedupe via refreshToken. Verifiziert gegen VRR-App-Screenshot: Am Rathaus 15 → Otto-Pankok-Schule zeigt jetzt Bus 131 20:29, Bus 151 20:35, Bus 130 20:48, STR 102 20:51 korrekt. DB-FIX-7b — "📍 Snapshot" → "📍 Abfahrtsstation" (User fragte "was bedeutet Snapshot"). |
| 2026-04-16 | 23 | Phase 1.5.20 ✅: DB-MCP Stabilisierung + Halluzinations-Schutz. 4 Bugs gefixt — DB-FIX-1 (rest_client._robust_get mit strukturierten Error-Dicts {ok, error, user_message_hint, retry_suggested, status_code, detail}, alle public Methoden retournieren Dict statt raisen, server.py-Tools forwarden user_message_hint verbatim, neuer MCP_FAILED ErrorType als retryable), DB-FIX-2 (core/hallucination_guard.py: modulare HallucinationGuard Klasse mit registrierbaren Domains, DB-Patterns für RE/S/U/Bus/Gleis/Verspätung/Gleiswechsel, soft-check appended nur Disclaimer + Warning-Log, Orchestrator-Integration, harte SYSTEM_PROMPT-Regel "NIEMALS konkrete Zugdaten erfinden"), DB-FIX-4 (neues Tool db_train_live_status — /trips/:id Live-Daten: Verspätung, Gleis vs. planned, Gleisänderungen 🔀, nächster Halt, GPS; graceful fallback), DB-FIX-3 (↩ Prefix-Zeile statt ⬅️ Marker im Row, immer ━━━ Separator, _is_remark_relevant filtert Baustellen nach Zeit±30min + Stations-Matching). ADR-018, ADR-019. Tests-Infrastruktur: pytest.ini, tests/ mit respx HTTPX-Mocking, requirements-dev.txt. 60+ Unit+Integration Tests (alle grün lokal + Docker). |

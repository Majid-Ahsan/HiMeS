# ADR-050 — Daily-Log Text-Pipeline (MVP, Phase 2.1 Schritt 8)

**Status:** Akzeptiert
**Datum:** 2026-05-01
**Phase:** 2.1 Schritt 8 (Text-Variante; Voice folgt in Schritt 8b)
**Verwandt:** ADR-018 (Tool-Error-Format), ADR-044 (cognee-CWD-.env),
              ADR-047 (T1-Topologie), ADR-048 (Env-Var-Konfig),
              ADR-049 (Whitelist-Prefix)

## Kontext

Phase 2.1 Schritt 8 schließt die persönliche Memo-Pipeline ab. Vor der
Voice-Variante implementieren wir den Text-MVP: User schickt Telegram-
Text → Jarvis bereinigt sprachlich + extrahiert Tags/Entities → Markdown-
Speicherung schema-konform → Cognee-Ingest async im Hintergrund.

Repo-Inspektion am 2026-05-01 hat drei Lücken zwischen Schema-Soll
(memory-schema.md + Beispiele 2026-04-13/14/15) und Skript-Ist
(voice_to_md.py) aufgedeckt:

1. Skript schreibt nur `type/date/user` ins Frontmatter — Schema fordert
   zusätzlich `tags` + `entities`.
2. Schema-Beispiele beginnen mit Datums-Anker-Zeile ("Heute ist Montag,
   der 13. April 2026.") — Skript schreibt diese nicht.
3. Skript nutzt `## HH:MM`-Append-Stack mit Sonderfall `## (Erster
   Eintrag)`-Wrap — Schema-Beispiele zeigen einen kohärenten Fließtext
   pro Tag ohne Zeitstempel-Headings.

ADR-050 löst diese Diskrepanzen.

## Entscheidungen

### D1 — Topologie T1 für daily-log-MCP

Eigener systemd-Service `jarvis-daily-log.service` auf VPS, im Cognee-
venv (`/home/ali/cognee/.venv`), Port 8003, Caddy-Proxy auf
`daily-log-ahsan.duckdns.org`. Pattern 1:1 von ADR-047.

**Begründung:** memo_to_md + ingest_to_cognee leben im Cognee-CWD-
Kontext (ADR-044). T2 (Bot-Container) wurde in ADR-047 wegen Image-
Bloat verworfen — bleibt verworfen.

### D2 — voice_to_md.py wird zu memo_to_md.py umbenannt + erweitert

Neue Verantwortung: schema-konformes MD schreiben für Text- und (später)
Voice-Quellen. Konkrete Änderungen:

- **Datei umbenennen:** `pipeline/voice_to_md.py` → `pipeline/memo_to_md.py`
- **Frontmatter erweitern:** `tags: [...]` und `entities: [...]` werden
  geschrieben, wenn als Argumente übergeben (neue CLI-Flags `--tags`,
  `--entities`).
- **Datums-Anker:** Wird bei neu erzeugten Dateien als erste Body-Zeile
  geschrieben: `Heute ist <Wochentag>, der <D. Monat YYYY>.`
- **Zwei Modi statt Append-Logik:**
  - `--mode write` (Default): schreibt frisch, schlägt fehl bei
    existierender Datei
  - `--mode replace`: überschreibt existierende Datei vollständig
- **Append-Logik komplett entfernt** inkl. `## (Erster Eintrag)`-Wrap.
- **Tests anpassen:** Bestehende 16 Tests aus Phase 2.1 Schritt 5 müssen
  für neues Verhalten überarbeitet werden.

**Begründung:** Schema fordert Tags/Entities/Datums-Anker — entweder
Skript erweitern oder Jarvis baut komplettes MD. Skript-Erweiterung
hält die Verantwortung an einer Stelle und macht Tests deterministisch.

### D3 — Append-Strategie: Merge per LLM, nicht Append-Stack

Bei zweitem Telegram-Eintrag desselben Tages:
1. Jarvis ruft `read_daily_log(date, user)` auf → liest aktuelle MD
2. Jarvis merged sprachlich neuen Inhalt mit altem zu kohärentem
   Fließtext, erweitert Frontmatter (Tags/Entities)
3. Jarvis zeigt User Preview, wartet auf Bestätigung
4. Jarvis ruft `log_daily_entry(...mode="replace")` auf

**Begründung:**
- Schema-Beispiele zeigen einen Fließtext pro Tag, kein Zeitstempel-
  Stack. Append würde dauerhaft vom Schema abweichen.
- Cognee-Knowledge-Graph profitiert von kohärentem Tageskontext —
  Append fragmentiert.
- `## (Erster Eintrag)`-Sonderfall fällt weg.

**Akzeptierter Trade-off:** LLM-Aufruf für Merge kostet Tokens. Für
~2-3 Telegram-Texte pro Tag tolerierbar.

### D4 — voice_to_md/ingest_to_cognee via Direkt-Import, nicht Subprocess

MCP importiert `pipeline.memo_to_md` und `pipeline.ingest_to_cognee` als
Python-Module. `process_files()` ist bereits async und gibt strukturiertes
dict zurück.

**Begründung:**
- T1-Topologie → MCP läuft im Cognee-venv → `pipeline/` im Python-Pfad
  → kein Venv-Konflikt
- Direkt-Import vermeidet stdout-Parsing für Pfad-Extraktion und Exit-
  Code-Mapping
- async-nativ, passt zu FastMCP

### D5 — Text-Bereinigung im Bot, nicht im MCP

Jarvis (LLM im Bot) bereinigt Telegram-Text und extrahiert Tags/Entities
*bevor* `log_daily_entry` aufgerufen wird. Der MCP empfängt fertige
Inputs und schreibt sie 1:1.

**Begründung:**
- Rückfragen (Transkriptions-Korrektur, mehrdeutige Begriffe) sind im
  Bot-Dialog natürlich, im MCP würden sie State-Machines erfordern.
- Single LLM-Layer — kein zweiter API-Call im MCP.
- MCP bleibt deterministisch und testbar.

### D6 — Preview + Bestätigung Pflicht

Vor jedem `log_daily_entry`-Call zeigt Jarvis dem User den bereinigten
Text und wartet auf "ja / ändere / nein". Auch bei kleinen Korrekturen.
Auch bei Merge-Fall.

**Begründung:** Cognee-Ingest erzeugt Knowledge-Graph-Knoten — falsche
Inputs verschmutzen die Graph-Inferenz dauerhaft.

### D7 — Hints im MCP, Vorschlags-Formulierung im Bot

Der MCP läuft deterministischen Regex-Extraktor (Datums-Patterns,
Task-Verben, Eigennamen) und gibt `extracted_hints` zurück. Der Bot
formuliert daraus *nach Speicher-Bestätigung* einen proaktiven
Vorschlag (zweite Telegram-Nachricht, ~2.5s Pause).

**Begründung:**
- Hint-Extraktion ist deterministisch → gehört nicht ins LLM
- Vorschlags-Formulierung ist Sprache → gehört ins LLM
- Trennung erleichtert Phase 1.5.26 und 2.18

### D8 — Async-Ingest, Sofort-Bestätigung

`log_daily_entry` returnt sofort nach `memo_to_md`-Abschluss mit
`ingest_status: "scheduled"`. Cognee-Ingest läuft via
`asyncio.create_task` mit `process_files()` im Hintergrund.

**Begründung:** UX. User soll nicht 30s+ warten. Ingest-Failure soll
Bot nicht blockieren — Re-Ingest manuell möglich.

### D9 — MCP-Tool-Set

Der `daily-log`-MCP exponiert zwei Tools:

1. `log_daily_entry(text, user="majid", date=None, tags=None,
   entities=None, mode="write") -> dict`
2. `read_daily_log(date, user="majid") -> dict`

**Begründung:** Read-Tool ist Voraussetzung für D3 (Merge). Trennt
Read- und Write-Verantwortung.

## Nicht-Ziele

- **Keine Voice-Eingabe in dieser Phase** — Whisper-Integration kommt
  in Schritt 8b nach Text-MVP-Verifikation. memo_to_md.py wird so
  gebaut, dass Voice-Pfad nur Whisper als Vor-Stufe braucht.
- **Keine automatische Termin-/Task-Anlage.** Hints sind Vorschläge.
- **Keine Multi-Day-Splits.** Ein Telegram-Text → eine Datei (heutiger
  Tag). Multi-Day kommt mit Voice (Schritt 8b).
- **Kein State-Management für ausstehende Logs.** Wenn User auf
  Preview nicht antwortet, verfällt der Vorschlag.

## Akzeptierte Schuld

- **MCP-Config Render-Pattern bleibt dirty-tree** (Sektion 13a) —
  daily-log-Server-Block ebenfalls. Saubere Lösung in Phase 2.18.
- **Ingest-Failure ist silent** — landet nur in journalctl, User
  bekommt keine Fehler-Nachricht.
- **Bestehende voice_to_md-Tests müssen umgeschrieben werden** —
  Schritt 5 hatte 16 grüne Tests, Subset wird durch Refactor
  obsolet/anders.
- **Merge-Cost** — bei mehreren Logs pro Tag fällt zusätzlicher
  LLM-Call für sprachliches Verschmelzen an.

## Konsequenzen

**Positiv:**
- Voice-Phase reduziert sich auf "Whisper vor memo_to_md.py einhängen"
- Schema-Compliance: erzeugte Files matchen 2026-04-13/14/15-Beispiele
- Pattern für weitere persönliche MCPs etabliert
- Cognee-Wissensbasis wächst aus echten Daily-Logs

**Negativ:**
- Vierter MCP-Service auf VPS — Caddy-Config wächst
- Drei bis vier LLM-Turns pro Log (Intent → Bereinigung → ggf. Merge →
  Bestätigung) — höhere Token-Kosten als direkt-speichern
- Bestehender voice_to_md-Code wird umstrukturiert — Bug-Risiko

## Offene Fragen

- Repo-Lage des MCP: `daily-log-mcp/` als Top-Level (analog
  `cognee-setup/`) oder `pipeline/daily-log-mcp/`? Default: Top-Level.
- Locking bei gleichzeitigen Schreibvorgängen — falls Bot mehrere
  Sessions parallel hat. Annahme MVP: single-user, irrelevant.

## Update 2026-05-02 — D4 revidiert

D4 ("Direct-Import von process_files in daily-log-MCP statt
Subprocess") ist mit der bestehenden Two-Process-Cognee-Architektur
strukturell unvereinbar. Kuzu (Cognee Graph-Backend) ist
single-process-only via flock(2). Beide Cognee-Process-Instanzen
streiten um exklusive Locks auf dieselben DB-Files.

Fix-Strategie: D3 (Subprocess-Ingest, ursprünglich verworfen) wird
re-aktiviert. asyncio.create_subprocess_exec() startet kurzlebigen
Ingest-Process, Lock wird automatisch beim Process-Exit freigegeben.
Trade-off: ~1-2s Spawn-Latenz pro Ingest, akzeptabel da Ingest
ohnehin async im Hintergrund läuft.

D4 bleibt im Repo als historischer Beleg, ist aber durch D3
abgelöst — siehe Sektion 13a für vollständige Diagnose.

## Update 2026-05-03 — D3 implementiert + verifiziert

PR #14 (commit 0480fe1) hat D3 (Subprocess-basierter Ingest)
implementiert. End-to-End-Verifikation mit echtem Tagebuch-Eintrag
am 2026-05-03:

- Tagebuch-Eintrag 2026-04-21 (2580 Zeichen, viele Personen + Themen)
- Schritt 0 (read_daily_log) → Bereinigung → Preview → Speichern
- log_daily_entry triggert subprocess-basierten Ingest
- Subprocess endet nach ~6 Sekunden mit "Ingest done" auf stdout
- Lock auf Kuzu-DB wird via Process-Exit automatisch freigegeben
- Cognee-Search findet den Eintrag ~30-60s später (Index-Lag) ohne
  irgendeinen Service-Restart

Damit ist ADR-050 D3 vs. D4 final entschieden: D3 ist die korrekte
Architektur für daily-log-MCP-Ingest. D4 (Direct-Import) bleibt im
historischen Repo-Stand für Kontext, ist aber durch D3 in Code
abgelöst.

Trade-off bestätigt akzeptabel: ~6s Subprocess-Spawn-Latenz pro
Ingest, irrelevant da Ingest async im Hintergrund läuft. User merkt
nur die ~5-10s Speichern-Bestätigung, nicht die Subprocess-Lifetime.

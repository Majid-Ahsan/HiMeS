# Cognee Setup für HiMeS

Cognee ist die Memory-Layer-Komponente von HiMeS — sie indexiert Daily-Logs und andere Memory-Dateien in einen Knowledge Graph für semantische Suche.

WICHTIG: Cognee läuft AUSSCHLIESSLICH auf dem VPS, niemals auf Mac. Mac dient nur als Development-Umgebung für Setup-Skripte und Code.

## Architektur

Cognee läuft als separater Service parallel zu HiMeS auf dem VPS:

- HiMeS-Container: bleibt unverändert
- Cognee venv: unter `$HOME/cognee/.venv/`
- Cognee Datenbanken: file-based (SQLite + LanceDB + Kuzu)
- LLM-Provider: Anthropic Claude (gleicher API-Key wie HiMeS)
- Embedding-Provider: Fastembed lokal (kein externer Service)

## Installation (NUR auf Server)

### Voraussetzungen

- Server mit Python 3.10+
- Internet-Zugang (für pip-Pakete und ersten Embedding-Modell-Download)
- Anthropic API-Key (klassisch, `sk-ant-api03-...`)

### Schritte

1. Auf Server: Skript ausführen:
   ```
   bash install.sh
   ```

2. Auf Server: `.env`-Datei aus Template erstellen:
   ```
   cp .env.example .env
   chmod 600 .env
   ```

3. Auf Server: Anthropic API-Key in `.env` eintragen

4. Auf Server: Smoke-Test ausführen:
   ```
   cd ~/cognee
   source .venv/bin/activate
   python smoke_test.py
   ```

5. Bei Erfolg: Cognee ist betriebsbereit

## Bekannte Probleme und Workarounds

### Problem 1: OAuth-Token funktioniert nicht

Anthropic OAuth-Tokens (`sk-ant-oat01-`) sind nur für simple Messages. Cognee braucht Tool-Use (Function-Calling), das funktioniert nur mit klassischen API-Keys (`sk-ant-api03-`).

Lösung: Klassischen API-Key über console.anthropic.com erstellen.

### Problem 2: Cognee 1.0.3 max_tokens-Bug

Der Anthropic-Adapter in Cognee 1.0.3 reicht `max_tokens` nicht durch. Ohne Workaround: Cognee hängt 128 Sekunden bevor es als Timeout abbricht.

Lösung: In `.env` folgende Variable setzen:
```
LLM_ARGS={"max_tokens": 4096}
```

Bei zukünftigen Cognee-Updates prüfen ob der Bug gefixt ist.

### ANTHROPIC_API_KEY ist optional

Cognee liest `LLM_API_KEY` und reicht es an die Anthropic-API durch. Die Standard-SDK-Variable `ANTHROPIC_API_KEY` wird von Cognee selbst nicht gelesen, aber von transitiven Dependencies (anthropic-SDK, LiteLLM) als Fallback genutzt wenn kein expliziter Key übergeben wird. Für ein sauberes Cognee-Setup ist nur `LLM_API_KEY` nötig.

Hinweis zur VPS-Realität: Auf dem aktuellen VPS sind beide Variablen gesetzt (Legacy aus Bug-Debugging in Schritt 1). Bei zukünftigem Cleanup kann `ANTHROPIC_API_KEY` entfernt werden.

## Konfigurations-Optionen

Siehe `.env.example` für alle Variablen. Wichtigste:

- `LLM_MODEL`: aktuell `claude-haiku-4-5-20251001` (günstig, schnell). Alternativen: `claude-3-5-haiku-20241022` (älter, robuster), `claude-sonnet-4-5` (teurer, qualitativ besser)
- `EMBEDDING_MODEL`: aktuell `sentence-transformers/all-MiniLM-L6-v2` (klein, lokal)

## Datenbanken-Speicherort

Cognee speichert SQLite + LanceDB + Kuzu standardmässig **innerhalb des venv** unter `<site-packages>/cognee/.cognee_system/databases/`. Das ist suboptimal — bei venv-Recreate (uv pip reinstall, Cognee-Update) gehen die Daten verloren.

Lösung: `SYSTEM_ROOT_DIRECTORY` und `DATA_ROOT_DIRECTORY` in `.env` zeigen nach `$HOME/cognee/data/...`. Cognee leitet alle drei Provider-Pfade aus `SYSTEM_ROOT_DIRECTORY` ab (siehe `cognee/infrastructure/databases/{relational,vector,graph}/config.py`).

Default-Pfade nach Migration:
```
$HOME/cognee/data/.cognee_system/databases/cognee_db          # SQLite
$HOME/cognee/data/.cognee_system/databases/cognee.lancedb     # LanceDB
$HOME/cognee/data/.cognee_system/databases/cognee_graph_kuzu  # Kuzu
$HOME/cognee/data/.data_storage/                              # ingestierte Rohdaten
```

### Migration für bestehende Installationen

Wenn Cognee schon läuft und Daten im venv-Pfad liegen, einmalig das Migrations-Skript ausführen:

```
cd ~/cognee
bash /pfad/zum/repo/cognee-setup/migrate-data-dir.sh
```

Das Skript ist idempotent:
- Erst-Setup ohne Daten: legt nur die neuen Pfade an
- Volle alte DBs: Backup nach `$HOME/cognee/backup/<timestamp>/`, dann Move + Verify
- Schon migriert (neue Pfade gefüllt, alte leer): meldet "nichts zu tun" und endet
- Doppelter Zustand (beide Seiten gefüllt): bricht ab, kein Auto-Merge

Anschliessend `.env` prüfen, dass `SYSTEM_ROOT_DIRECTORY` und `DATA_ROOT_DIRECTORY` gesetzt sind, dann Cognee neu starten und Smoke-Test laufen lassen.

### Hinweis zur zukünftigen Migration von `data_root_directory`

Die SQLite-Tabelle `Data` enthält Spalten `raw_data_location` und `original_data_location` mit absoluten Pfaden zu ingestierten Dateien. Wenn später nur `DATA_ROOT_DIRECTORY` umgezogen wird (nicht `SYSTEM_ROOT_DIRECTORY`), reicht ein `mv` nicht — diese Pfade in der Metadata müssen ebenfalls umgeschrieben werden. Siehe ADR-042.

## Verzeichnis-Struktur (auf Server nach Installation)

```
$HOME/cognee/
├── .venv/                    # Python venv mit Cognee
├── .env                      # Konfiguration (NICHT in Git)
├── .env.example              # Template (in Git)
├── install.sh                # Setup-Skript
├── migrate-data-dir.sh       # Einmalige Migration aus venv-Pfad
├── smoke_test.py             # Validierungs-Test
├── data/
│   ├── .cognee_system/       # SQLite + LanceDB + Kuzu
│   └── .data_storage/        # Ingestierte Rohdaten + Loader-Cache
└── backup/                   # Migrations-Backups (nach Bedarf)
```

## Versionen

Diese Setup-Konfiguration wurde validiert mit:
- Cognee: 1.0.3
- Python: 3.12
- Fastembed: 0.8.0
- Anthropic: 0.97.0

## Verbindung zu HiMeS

Aktueller Stand: Cognee läuft eigenständig auf VPS, ist NICHT in HiMeS integriert.

Phase 2.1 Schritt 3 wird Cognee als MCP-Tool in HiMeS einbinden.

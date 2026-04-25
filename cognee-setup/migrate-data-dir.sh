#!/bin/bash
# Cognee Data-Dir Migration (Phase 2.1, Schritt 3)
#
# Verschiebt Cognees Datenbanken aus dem venv-Default-Pfad
#   $COGNEE_DIR/.venv/lib/pythonX.Y/site-packages/cognee/.cognee_system
#   $COGNEE_DIR/.venv/lib/pythonX.Y/site-packages/cognee/.data_storage
# in stabile Pfade ausserhalb des venv:
#   $COGNEE_DIR/data/.cognee_system
#   $COGNEE_DIR/data/.data_storage
#
# Damit ueberleben die Daten ein venv-Recreate (uv pip reinstall,
# Cognee-Update). Nach der Migration muessen SYSTEM_ROOT_DIRECTORY
# und DATA_ROOT_DIRECTORY in .env gesetzt sein (siehe .env.example).
#
# Idempotent: Mehrfache Ausfuehrung ist sicher.
# - Neue Pfade existieren leer: weiter (nichts zu verlieren)
# - Neue Pfade existieren mit Inhalt UND alte sind leer: Migration
#   gilt als erledigt, Skript meldet "schon migriert" und endet 0
# - Neue Pfade existieren mit Inhalt UND alte auch: Abbruch mit
#   klarer Meldung (nicht ueberschreiben, kein Halb-Zustand)
#
# WICHTIG: Dieses Skript ist NUR fuer Server gedacht, NICHT fuer Mac.

set -euo pipefail

COGNEE_DIR="${COGNEE_DIR:-$HOME/cognee}"
NEW_SYSTEM="$COGNEE_DIR/data/.cognee_system"
NEW_DATA="$COGNEE_DIR/data/.data_storage"
BACKUP_ROOT="$COGNEE_DIR/backup"
TS="$(date +%Y%m%d-%H%M%S)"
BACKUP_DIR="$BACKUP_ROOT/$TS"

echo "=== Cognee Data-Dir Migration ==="
echo "Cognee-Verzeichnis: $COGNEE_DIR"

# 1. venv und Python-Version finden, daraus alte Pfade ableiten.
#    Cognees Default-Layout ist <site-packages>/cognee/.cognee_system
#    bzw. .data_storage (siehe cognee/base_config.py).
if [ ! -d "$COGNEE_DIR/.venv" ]; then
    echo "FEHLER: kein venv unter $COGNEE_DIR/.venv gefunden." >&2
    echo "Bitte erst install.sh ausfuehren." >&2
    exit 1
fi

# Python-Version-Verzeichnis (z.B. python3.12) im venv finden — toleriert
# unterschiedliche Minor-Versionen, ohne sie hart zu kodieren.
SITE_PACKAGES=$(find "$COGNEE_DIR/.venv/lib" -maxdepth 2 -type d -name site-packages 2>/dev/null | head -n 1 || true)
if [ -z "$SITE_PACKAGES" ]; then
    echo "FEHLER: kein site-packages unter $COGNEE_DIR/.venv/lib gefunden." >&2
    exit 1
fi

OLD_SYSTEM="$SITE_PACKAGES/cognee/.cognee_system"
OLD_DATA="$SITE_PACKAGES/cognee/.data_storage"

echo "Alt: $OLD_SYSTEM"
echo "     $OLD_DATA"
echo "Neu: $NEW_SYSTEM"
echo "     $NEW_DATA"
echo ""

# Hilfsfunktion: hat ein Verzeichnis nicht-triviale Inhalte?
# (Existiert nicht oder leer => 1, hat irgendwas drin => 0)
has_content() {
    local dir="$1"
    if [ ! -d "$dir" ]; then
        return 1
    fi
    # find -mindepth 1 -print -quit gibt erste Datei aus, sonst nichts
    if [ -z "$(find "$dir" -mindepth 1 -print -quit 2>/dev/null)" ]; then
        return 1
    fi
    return 0
}

OLD_SYSTEM_HAS_CONTENT=0; has_content "$OLD_SYSTEM" && OLD_SYSTEM_HAS_CONTENT=1
OLD_DATA_HAS_CONTENT=0;   has_content "$OLD_DATA"   && OLD_DATA_HAS_CONTENT=1
NEW_SYSTEM_HAS_CONTENT=0; has_content "$NEW_SYSTEM" && NEW_SYSTEM_HAS_CONTENT=1
NEW_DATA_HAS_CONTENT=0;   has_content "$NEW_DATA"   && NEW_DATA_HAS_CONTENT=1

# 2. Idempotenz: wenn neue Pfade Inhalt haben und alte nicht, ist
#    Migration schon erledigt. Sauber beenden.
if [ "$NEW_SYSTEM_HAS_CONTENT" = 1 ] || [ "$NEW_DATA_HAS_CONTENT" = 1 ]; then
    if [ "$OLD_SYSTEM_HAS_CONTENT" = 0 ] && [ "$OLD_DATA_HAS_CONTENT" = 0 ]; then
        echo "Migration bereits erfolgt: neue Pfade haben Inhalt, alte sind leer."
        echo "Nichts zu tun."
        exit 0
    fi
    # Beide gefuellt — gefaehrlich, kein Auto-Merge.
    echo "FEHLER: Sowohl alte ALS auch neue Daten-Verzeichnisse enthalten Inhalt." >&2
    echo "Das deutet auf einen halb-migrierten oder doppelten Zustand hin." >&2
    echo "Manuell pruefen, eines davon weg-archivieren, dann Skript erneut starten." >&2
    echo "  alt:" >&2
    [ "$OLD_SYSTEM_HAS_CONTENT" = 1 ] && echo "    $OLD_SYSTEM (Inhalt vorhanden)" >&2
    [ "$OLD_DATA_HAS_CONTENT"   = 1 ] && echo "    $OLD_DATA (Inhalt vorhanden)" >&2
    echo "  neu:" >&2
    [ "$NEW_SYSTEM_HAS_CONTENT" = 1 ] && echo "    $NEW_SYSTEM (Inhalt vorhanden)" >&2
    [ "$NEW_DATA_HAS_CONTENT"   = 1 ] && echo "    $NEW_DATA (Inhalt vorhanden)" >&2
    exit 2
fi

# 3. Pruefen ob ein Cognee-Prozess laeuft. Falls ja, abbrechen —
#    eine laufende SQLite/LanceDB-Verbindung waere ein Korruptions-
#    Risiko bei einem mv.
#    Pattern verlangt 'python' im Kommando, damit das Skript sich
#    nicht selbst matcht (Skript-Pfad enthaelt 'cognee').
COGNEE_PROC_RE='python.*cognee|python.*smoke_test\.py'
if pgrep -f "$COGNEE_PROC_RE" > /dev/null 2>&1; then
    echo "FEHLER: Cognee-Prozess laeuft (pgrep -f '$COGNEE_PROC_RE')." >&2
    echo "Bitte erst stoppen, dann Skript erneut starten." >&2
    pgrep -af "$COGNEE_PROC_RE" >&2 || true
    exit 3
fi

# 4. Spezialfall: Beide alten Pfade leer (oder nicht existent).
#    Dann gibt es nichts zu migrieren. Wir legen nur die neuen
#    Pfade an, damit .env-Eintraege auch ohne vorherige Cognee-
#    Nutzung funktionieren.
if [ "$OLD_SYSTEM_HAS_CONTENT" = 0 ] && [ "$OLD_DATA_HAS_CONTENT" = 0 ]; then
    echo "Keine Cognee-Daten im venv vorhanden (Erst-Setup oder bereits aufgeraeumt)."
    echo "Lege neue Pfade an, ohne Backup."
    mkdir -p "$NEW_SYSTEM" "$NEW_DATA"
    # Alte leere Stub-Verzeichnisse koennen bleiben — Cognee wuerde
    # sie ohnehin neu anlegen, wenn die Env-Vars nicht greifen.
    echo "Fertig. Sicherstellen, dass .env SYSTEM_ROOT_DIRECTORY und"
    echo "DATA_ROOT_DIRECTORY auf die neuen Pfade zeigt."
    exit 0
fi

# 5. Echter Migrations-Pfad: mindestens eines der alten Verzeichnisse
#    hat Inhalt. Backup anlegen, dann verschieben.
echo "Migrations-Modus: alte Daten gefunden, fuehre Backup + Move aus."
mkdir -p "$BACKUP_DIR"
echo "Backup-Ziel: $BACKUP_DIR"

backup_dir() {
    local src="$1"
    local label="$2"
    if has_content "$src"; then
        echo "  Backup $label: $src -> $BACKUP_DIR/$label"
        cp -a "$src" "$BACKUP_DIR/$label"
    fi
}

backup_dir "$OLD_SYSTEM" ".cognee_system"
backup_dir "$OLD_DATA"   ".data_storage"

# Move (rename) wenn moeglich, sonst copy+delete. Ein einfaches mv
# ist atomar im selben Filesystem; der Pfad-Wechsel von
# .venv/.../cognee/.cognee_system nach $COGNEE_DIR/data/.cognee_system
# bleibt typisch im selben FS.
mkdir -p "$(dirname "$NEW_SYSTEM")" "$(dirname "$NEW_DATA")"

move_dir() {
    local src="$1"
    local dst="$2"
    local label="$3"
    if has_content "$src"; then
        echo "  Verschiebe $label: $src -> $dst"
        # Zielelternverzeichnis existiert (mkdir -p oben), Ziel selber
        # darf nicht existieren oder leer sein — beides ist garantiert
        # weil wir oben "neue Pfade haben Inhalt" schon ausgeschlossen
        # haben. rmdir-leerer-Dst, falls install.sh den Stub angelegt hat.
        if [ -d "$dst" ]; then
            rmdir "$dst" 2>/dev/null || {
                echo "FEHLER: Ziel $dst existiert und ist nicht leer." >&2
                exit 4
            }
        fi
        mv "$src" "$dst"
    elif [ ! -d "$dst" ]; then
        mkdir -p "$dst"
    fi
}

move_dir "$OLD_SYSTEM" "$NEW_SYSTEM" ".cognee_system"
move_dir "$OLD_DATA"   "$NEW_DATA"   ".data_storage"

# 6. Verifikation: Inhaltsgroesse Backup vs. neue Pfade muss matchen.
verify_size() {
    local label="$1"
    local backup="$BACKUP_DIR/$label"
    local new="$2"
    if [ ! -d "$backup" ]; then
        return 0  # nichts gesichert, also auch nichts zu pruefen
    fi
    local b n
    b=$(du -sb "$backup" 2>/dev/null | awk '{print $1}')
    n=$(du -sb "$new"    2>/dev/null | awk '{print $1}')
    if [ "$b" != "$n" ]; then
        echo "FEHLER: Groessen-Mismatch fuer $label: backup=$b neu=$n" >&2
        exit 5
    fi
    echo "  OK $label: $b Bytes (Backup == neu)"
}

echo ""
echo "Verifikation:"
verify_size ".cognee_system" "$NEW_SYSTEM"
verify_size ".data_storage"  "$NEW_DATA"

echo ""
echo "Migration abgeschlossen."
echo "Backup: $BACKUP_DIR"
echo "Neuer System-Pfad: $NEW_SYSTEM"
echo "Neuer Data-Pfad:   $NEW_DATA"
echo ""
echo "Naechster Schritt: in .env sicherstellen, dass"
echo "  SYSTEM_ROOT_DIRECTORY=$NEW_SYSTEM"
echo "  DATA_ROOT_DIRECTORY=$NEW_DATA"
echo "gesetzt sind, dann Cognee neu starten und smoke_test.py ausfuehren."

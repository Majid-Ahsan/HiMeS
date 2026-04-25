#!/bin/bash
# Cognee Installation Script für HiMeS
# Idempotent: kann mehrmals ausgeführt werden ohne Schaden
# Voraussetzungen: Python 3.10+, Internet-Zugang
# WICHTIG: Dieses Skript ist NUR für Server-Setup gedacht, NICHT für Mac

set -e  # bei Fehler stoppen

COGNEE_DIR="${COGNEE_DIR:-$HOME/cognee}"

echo "=== Cognee Installation für HiMeS ==="
echo "Installations-Verzeichnis: $COGNEE_DIR"

# Prüfe Python-Version
PYTHON_VERSION=$(python3 --version | awk '{print $2}')
echo "Python-Version: $PYTHON_VERSION"

# Installiere uv falls nicht vorhanden
if ! command -v uv &> /dev/null; then
    echo "uv nicht gefunden, installiere..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    source $HOME/.local/bin/env
fi

# Verzeichnis anlegen wenn nicht vorhanden
mkdir -p "$COGNEE_DIR"
cd "$COGNEE_DIR"

# venv anlegen wenn nicht vorhanden
if [ ! -d ".venv" ]; then
    echo "Erstelle venv mit Python 3.12..."
    uv venv --python 3.12
else
    echo "venv existiert bereits, überspringe"
fi

# Aktivieren
source .venv/bin/activate

# Cognee installieren oder updaten
echo "Installiere Cognee mit Anthropic + Fastembed..."
uv pip install 'cognee[anthropic,fastembed]'

# .env-Datei prüfen
if [ ! -f ".env" ]; then
    echo ""
    echo "=== Wichtig ==="
    echo ".env-Datei fehlt. Bitte:"
    echo "1. Kopiere .env.example zu .env"
    echo "2. Trage deinen Anthropic API-Key ein (klassisch sk-ant-api03-)"
    echo "3. Setze chmod 600 .env"
    echo ""
fi

# Verifikation
echo ""
echo "=== Installation abgeschlossen ==="
python -c "import cognee; print(f'Cognee Version: {cognee.__version__}')"
echo ""
echo "Nächster Schritt: smoke_test.py ausführen wenn .env konfiguriert ist"

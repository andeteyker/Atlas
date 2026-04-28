#!/bin/bash
# ATLAS Swarm — globales Kommando
# Nach Installation: atlas "dein task"

ATLAS_DIR="$(dirname "$(realpath "$0")")"
cd "$ATLAS_DIR" || exit 1

if [ ! -f "venv/bin/activate" ]; then
    echo "[ATLAS] Erstelle venv..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -q -r requirements.txt
else
    source venv/bin/activate
fi

python -m atlas_run.atlas "$@"

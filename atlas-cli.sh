#!/usr/bin/env bash
# ATLAS CLI — Agent Command Interface Launcher
# Usage: ./atlas-cli.sh
#        oder: ln -sf $(pwd)/atlas-cli.sh /usr/local/bin/atlas-cli

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Python aus venv wenn vorhanden, sonst system python3
if [ -f "$SCRIPT_DIR/venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/venv/bin/python"
elif [ -f "$SCRIPT_DIR/.venv/bin/python" ]; then
    PYTHON="$SCRIPT_DIR/.venv/bin/python"
else
    PYTHON="python3"
fi

cd "$SCRIPT_DIR"
exec "$PYTHON" -m atlas_cli "$@"

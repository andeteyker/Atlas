"""
ATLAS CLI — Einstiegspunkt.

Startet den Launcher in einer Loop: nach jedem Tool-Lauf kehrt
der Benutzer automatisch zum Launcher zurück.

Usage:
    python -m atlas_cli
    atlas-cli
"""

from __future__ import annotations

import os
import shlex
import subprocess
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
COMMANDS_FILE = BASE_DIR / "commands.yaml"


def _launch(cmd: str, args: list[str], extra: str, env_extra: dict) -> None:
    """
    Startet ein Command als Subprocess.
    Bei prompt-Commands wird extra als letztes Argument angehängt.
    """
    full_args: list[str] = [cmd] + args

    if extra:
        # extra kann mehrere Wörter enthalten (z.B. "run 'task text'" → shlex splitten)
        try:
            extra_parts = shlex.split(extra)
        except ValueError:
            extra_parts = [extra]
        full_args += extra_parts

    env = {**os.environ, **env_extra}

    try:
        subprocess.run(full_args, env=env)
    except FileNotFoundError:
        print(f"\n  ✗  Befehl nicht gefunden: '{cmd}'")
        print(f"     Stelle sicher dass '{cmd}' installiert und im PATH ist.\n")
        input("  [Enter] zurück zum Launcher")
    except KeyboardInterrupt:
        pass


def _open_editor(file: Path) -> None:
    """Öffnet eine Datei im Standard-Editor."""
    editor = os.environ.get("EDITOR") or os.environ.get("VISUAL") or "nano"
    try:
        subprocess.run([editor, str(file)])
    except FileNotFoundError:
        # Fallback-Editoren
        for fallback in ("nano", "vim", "vi", "notepad"):
            try:
                subprocess.run([fallback, str(file)])
                return
            except FileNotFoundError:
                continue
        print(f"\n  ✗  Kein Editor gefunden. Öffne manuell:\n     {file}\n")
        input("  [Enter] zurück zum Launcher")


def main() -> None:
    """
    Haupt-Loop: Launcher anzeigen → Command ausführen → zurück zum Launcher.
    Beendet sich wenn der Benutzer 'Q' drückt oder Ctrl+C eingibt.
    """
    from atlas_cli.app import AtlasLauncher

    while True:
        try:
            app = AtlasLauncher()
            result = app.run()
        except KeyboardInterrupt:
            break

        # User hat 'Q' gedrückt oder Fenster geschlossen
        if result is None:
            break

        # Edit Config
        if result == ("EDIT_CONFIG", "") or (isinstance(result, tuple) and result[0] == "EDIT_CONFIG"):
            _open_editor(COMMANDS_FILE)
            continue

        # Normaler Command-Start
        if isinstance(result, tuple) and len(result) == 2:
            cmd_obj, extra = result
            if hasattr(cmd_obj, "cmd"):
                _launch(
                    cmd=cmd_obj.cmd,
                    args=cmd_obj.args,
                    extra=extra,
                    env_extra=cmd_obj.env,
                )
            continue

        break

    # Sauberer Exit
    print()


if __name__ == "__main__":
    main()

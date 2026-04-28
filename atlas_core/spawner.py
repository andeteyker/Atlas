"""
ATLAS Agent Spawner — generiert neue Hermes-Agenten dynamisch.

Mit optionalem Bestätigungsschritt (ATLAS_SPAWN_CONFIRM=true).
Generiert alle 4 Agent-Dateien via LLM.
"""

from __future__ import annotations

import os
from pathlib import Path

from atlas_core.blackboard import consume_signal, read_signals, register_agent
from atlas_core.llm import chat

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "atlas_agents"

_FILE_MARKERS = {
    "===SYSTEM.MD===": "system.md",
    "===MEMORY.MD===": "memory.md",
    "===EXAMPLES.MD===": "examples.md",
    "===SKILLS.MD===": "skills.md",
}


def _generate_agent_files(name: str, description: str, skills: list[str]) -> dict[str, str]:
    """Generiert alle 4 Agent-Dateien via LLM."""
    skills_str = ", ".join(skills) if skills else description

    prompt = f"""Du bist der ATLAS Meta-Agent. Generiere einen vollständigen neuen Hermes-Agenten.

Name: {name}
Beschreibung: {description}
Skills: {skills_str}

ATLAS-Kontext: Dezentrales AIOS für PLM-Koordination und Schiffbau.

Generiere genau diese 4 Dateien im exakten Format:

===SYSTEM.MD===
Du bist atlas.{name} — [Rolle in 1 Satz].

## Deine Rolle
[2-3 Sätze Rollenbeschreibung]

## Domänenwissen
[Relevante Fachbereiche]

## Arbeitsweise
[3-5 konkrete Arbeitsschritte]

## Ausgabeformat
[Erwartetes Output-Format]

===MEMORY.MD===
# {name} Memory

- [Initiale Faustregel 1]
- [Initiale Faustregel 2]
- [Initiale Faustregel 3]

===EXAMPLES.MD===
# {name} Beispiele

## Beispiel 1

**Input:** [konkretes Beispiel-Input]

**Output:**
[konkreter Beispiel-Output]

===SKILLS.MD===
# {name} Skills

## Kernfähigkeiten
- **[Skill 1]**: [kurze Erklärung]
- **[Skill 2]**: [kurze Erklärung]

## Tools
[Welche Tools/Systeme genutzt werden]

## Grenzen
[Was dieser Agent NICHT macht — klar delegieren an andere]
"""

    result = chat(
        [
            {
                "role": "system",
                "content": "Generiere ATLAS Agent-Dateien. Halte dich exakt an das Marker-Format.",
            },
            {"role": "user", "content": prompt},
        ],
        agent_name="spawner",
    )

    files: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []

    for line in result.splitlines():
        stripped = line.strip()
        if stripped in _FILE_MARKERS:
            if current_key:
                files[_FILE_MARKERS[current_key]] = "\n".join(current_lines).strip()
            current_key = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_key:
        files[_FILE_MARKERS[current_key]] = "\n".join(current_lines).strip()

    return files


def spawn_agent(
    name: str,
    description: str,
    skills: list[str],
    confirmed: bool = False,
) -> bool:
    """
    Spawnt einen neuen Agenten.
    Bei ATLAS_SPAWN_CONFIRM=true: zuerst Vorschau + Bestätigung.
    """
    confirm_required = os.getenv("ATLAS_SPAWN_CONFIRM", "true").lower() == "true"

    if confirm_required and not confirmed:
        print(f"\n[ATLAS SPAWN] Neuer Agent vorgeschlagen:")
        print(f"  Name        : {name}")
        print(f"  Beschreibung: {description}")
        print(f"  Skills      : {', '.join(skills) or '(keine)'}")
        try:
            answer = input("\nAgent spawnen? [j/N]: ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[SPAWN] Abgebrochen.")
            return False
        if answer not in ("j", "ja", "y", "yes"):
            print("[SPAWN] Abgebrochen.")
            return False

    agent_dir = AGENTS_DIR / name
    agent_dir.mkdir(parents=True, exist_ok=True)

    print(f"[SPAWN] Generiere Agent '{name}'...")
    try:
        files = _generate_agent_files(name, description, skills)
    except Exception as e:
        print(f"[SPAWN] ✗ LLM-Fehler: {e}")
        return False

    if not files:
        print("[SPAWN] ✗ Keine Dateien generiert — LLM-Format-Fehler?")
        return False

    for filename, content in files.items():
        (agent_dir / filename).write_text(content, encoding="utf-8")
        print(f"  ✓ {filename}")

    register_agent(name=name, description=description, skills=skills, spawned_by="spawner")
    print(f"[SPAWN] ✓ Agent '{name}' ist aktiv und im Schwarm registriert.")
    return True


def process_spawn_requests():
    """Verarbeitet ausstehende Spawn-Anfragen vom Blackboard."""
    signals = read_signals(signal_type="spawn_request")
    if not signals:
        return

    for signal in signals:
        content = signal.get("content", {})
        description = content.get("description", "")
        trigger = content.get("trigger_input", "")

        if not description:
            consume_signal(signal["id"])
            continue

        # Agent-Name aus Beschreibung ableiten
        name_prompt = [
            {
                "role": "system",
                "content": (
                    "Erstelle einen kurzen snake_case Namen (max. 3 Wörter) für diesen Agenten. "
                    "Nur der Name — kein Kommentar, kein Punkt, kein Sonderzeichen außer _."
                ),
            },
            {
                "role": "user",
                "content": f"Beschreibung: {description}\nTrigger: {trigger}",
            },
        ]
        try:
            raw_name = chat(name_prompt, agent_name="spawner").strip().lower()
        except Exception:
            raw_name = "unknown_agent"

        # Bereinigen
        agent_name = (
            raw_name
            .replace(" ", "_")
            .replace("-", "_")
            .replace(".", "")
        )
        agent_name = "".join(c for c in agent_name if c.isalnum() or c == "_")[:40]
        agent_name = agent_name or "unknown_agent"

        spawned = spawn_agent(
            name=agent_name,
            description=description,
            skills=[description],
        )
        if spawned:
            consume_signal(signal["id"])

"""
ATLAS Agent Spawner — generiert neue Hermes-Agenten dynamisch.
Mit optionalem Bestätigungsschritt (ATLAS_SPAWN_CONFIRM=true).
"""

import os
from pathlib import Path

from atlas_core.blackboard import consume_signal, read_signals, register_agent
from atlas_core.llm import chat

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "atlas_agents"


def _generate_agent_files(name: str, description: str, skills: list[str]) -> dict:
    """Lässt das LLM die Agent-Dateien generieren."""

    prompt = f"""Du bist der ATLAS Meta-Agent. Generiere einen neuen Hermes-Agenten.

Name: {name}
Beschreibung: {description}
Skills: {', '.join(skills)}

Generiere genau diese 4 Dateien im folgenden Format:

===SYSTEM.MD===
<Inhalt der system.md — Rolle, Fokus, Regeln>

===MEMORY.MD===
# {name} Memory
<3-5 initiale Faustregeln für diesen Agenten>

===EXAMPLES.MD===
<1 konkretes Beispiel: Input → Output>

===SKILLS.MD===
# {name} Skills
<Liste der Fähigkeiten mit kurzer Erklärung>
"""

    result = chat(
        [{"role": "system", "content": "Du generierst ATLAS Agent Dateien. Halte dich exakt an das Format."}, {"role": "user", "content": prompt}],
        agent_name="spawner",
    )

    files = {}
    sections = {"===SYSTEM.MD===": "system.md", "===MEMORY.MD===": "memory.md", "===EXAMPLES.MD===": "examples.md", "===SKILLS.MD===": "skills.md"}

    current_key = None
    current_lines = []

    for line in result.splitlines():
        stripped = line.strip()
        if stripped in sections:
            if current_key:
                files[sections[current_key]] = "\n".join(current_lines).strip()
            current_key = stripped
            current_lines = []
        else:
            current_lines.append(line)

    if current_key:
        files[sections[current_key]] = "\n".join(current_lines).strip()

    return files


def spawn_agent(name: str, description: str, skills: list[str], confirmed: bool = False) -> bool:
    """
    Spawnt einen neuen Agenten.
    Bei ATLAS_SPAWN_CONFIRM=true wird zuerst eine Vorschau gezeigt.
    """
    confirm_required = os.getenv("ATLAS_SPAWN_CONFIRM", "true").lower() == "true"

    if confirm_required and not confirmed:
        print(f"\n[ATLAS SPAWN] Neuer Agent vorgeschlagen:")
        print(f"  Name        : {name}")
        print(f"  Beschreibung: {description}")
        print(f"  Skills      : {', '.join(skills)}")
        answer = input("\nAgent spawnen? [j/N]: ").strip().lower()
        if answer not in ("j", "ja", "y", "yes"):
            print("[SPAWN] Abgebrochen.")
            return False

    agent_dir = AGENTS_DIR / name
    agent_dir.mkdir(parents=True, exist_ok=True)

    print(f"[SPAWN] Generiere Agent '{name}'...")
    files = _generate_agent_files(name, description, skills)

    for filename, content in files.items():
        (agent_dir / filename).write_text(content, encoding="utf-8")
        print(f"  ✓ {filename}")

    register_agent(name=name, description=description, skills=skills, spawned_by="spawner")
    print(f"[SPAWN] Agent '{name}' ist aktiv und im Schwarm registriert.")
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

        # Name aus Beschreibung ableiten
        name_prompt = [
            {"role": "system", "content": "Erstelle einen kurzen snake_case Namen (max 3 Wörter) für diesen Agenten. Nur der Name, nichts anderes."},
            {"role": "user", "content": f"Beschreibung: {description}\nTrigger: {trigger}"},
        ]
        raw_name = chat(name_prompt, agent_name="spawner").strip().lower().replace(" ", "_").replace("-", "_")
        agent_name = "".join(c for c in raw_name if c.isalnum() or c == "_")[:40]

        skills = [description]

        spawned = spawn_agent(name=agent_name, description=description, skills=skills)
        if spawned:
            consume_signal(signal["id"])

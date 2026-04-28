"""
ATLAS Memory — privater Agent-Stack + automatische Destillation in den globalen Pool.

Verbesserungen:
- Vector Memory (ChromaDB) parallel zu memory.md
- Semantisches Dedup: Zu ähnliche Regeln werden ignoriert
- Memory-Zusammenfassung wenn memory.md zu groß wird (>50 Einträge)
- Run-History als JSON + semantisch durchsuchbar
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path

from atlas_core.blackboard import append_learning, pin_signal
from atlas_core.llm import chat
from atlas_core import vector_memory as vm

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "atlas_agents"
HISTORY_DIR = BASE_DIR / "atlas_memory" / "history"

# memory.md wird zusammengefasst wenn mehr als diese Anzahl an Regeln
MEMORY_CONDENSE_THRESHOLD = 40


def _agent_dir(agent_name: str) -> Path:
    return AGENTS_DIR / agent_name


def read_agent_memory(agent_name: str) -> str:
    path = _agent_dir(agent_name) / "memory.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_agent_memory(agent_name: str, content: str):
    path = _agent_dir(agent_name) / "memory.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _count_memory_entries(memory: str) -> int:
    return sum(1 for line in memory.splitlines() if line.strip().startswith("-"))


def _condense_memory(agent_name: str, memory: str) -> str:
    """
    Fasst eine zu groß gewordene memory.md in kompakte Kernregeln zusammen.
    Inspiriert vom mem0-Ansatz: periodische Destillation statt unbegrenztes Wachstum.
    """
    condense_prompt = [
        {
            "role": "system",
            "content": (
                "Du bist ein Wissensdestillator für ATLAS-Agenten. "
                "Fasse die folgende Memory-Liste auf die 15 wichtigsten, einzigartigen Regeln zusammen. "
                "Format: Eine Regel pro Zeile, beginnend mit '- '. "
                "Redundante oder zu ähnliche Regeln zusammenführen. "
                "Behalte die konkretesten und nützlichsten Regeln."
            ),
        },
        {
            "role": "user",
            "content": f"Agent: {agent_name}\n\nAktuelle Memory:\n{memory}",
        },
    ]
    try:
        result = chat(condense_prompt, agent_name="learner")
        header = f"# {agent_name} Memory\n*(kondensiert am {datetime.now().strftime('%Y-%m-%d')})*\n\n"
        return header + result.strip()
    except Exception:
        return memory  # Fallback: unverändert


def save_history(agent: str, user_input: str, output: str, feedback: str | None = None) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    run_id = str(uuid.uuid4())
    entry = {
        "id": run_id,
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "input": user_input,
        "output": output,
        "feedback": feedback,
    }
    path = HISTORY_DIR / f"{run_id}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")

    # Auch im Vector Store speichern
    vm.add_session_entry(agent=agent, user_input=user_input, output=output, run_id=run_id)

    return path


def auto_learn(agent: str, user_input: str, output: str):
    """
    Destilliert nach jedem Lauf automatisch eine Regel aus Input+Output.
    - Schreibt in private memory.md (mit Kondensierung wenn nötig)
    - Schreibt in globalen JSONL-Pool
    - Schreibt in ChromaDB Vector Store (mit semantischem Dedup)
    - Pinnt Signal auf Blackboard
    """
    current_memory = read_agent_memory(agent)

    distill_prompt = [
        {
            "role": "system",
            "content": (
                "Du bist ein Meta-Lern-System für ATLAS-Agenten. "
                "Analysiere Input und Output und extrahiere genau eine neue, konkrete Regel "
                "die der Agent beim nächsten ähnlichen Task besser machen würde. "
                "Format: Beginne mit 'REGEL:' gefolgt von max. 2 Sätzen. "
                "Wenn keine sinnvolle neue Regel ableitbar ist (z.B. zu allgemein oder bereits bekannt), "
                "antworte nur mit: KEINE."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Agent: {agent}\n\n"
                f"Input:\n{user_input[:800]}\n\n"
                f"Output:\n{output[:1000]}\n\n"
                f"Aktuelle Memory (Auszug):\n{current_memory[-500:]}"
            ),
        },
    ]

    try:
        result = chat(distill_prompt, agent_name="learner")
    except Exception:
        return

    stripped = result.strip()
    if stripped.upper().startswith("KEINE") or not stripped.upper().startswith("REGEL:"):
        return

    rule = stripped[len("REGEL:"):].strip()
    if len(rule) < 10:
        return

    timestamp = datetime.now().strftime("%Y-%m-%d")
    new_entry = f"- [{timestamp}] {rule}"

    # In private memory.md schreiben
    if current_memory:
        new_memory = current_memory.rstrip() + f"\n{new_entry}"
    else:
        new_memory = f"# {agent} Memory\n\n{new_entry}"

    # Kondensieren wenn zu viele Einträge
    if _count_memory_entries(new_memory) > MEMORY_CONDENSE_THRESHOLD:
        new_memory = _condense_memory(agent, new_memory)

    write_agent_memory(agent, new_memory)

    # In globalen JSONL-Pool schreiben (Fallback-Persistenz)
    append_learning(agent=agent, rule=rule, context=user_input[:300], confidence=0.75)

    # In ChromaDB Vector Store (mit semantischem Dedup)
    vm.add_global_learning(agent=agent, rule=rule, context=user_input[:300])
    vm.add_memory(agent=agent, content=rule, metadata={"type": "auto_learned"})

    # Blackboard-Signal
    pin_signal(
        agent=agent,
        signal_type="learning",
        content={"rule": rule, "context": user_input[:200]},
    )

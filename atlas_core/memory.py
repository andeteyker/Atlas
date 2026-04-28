"""
ATLAS Memory — privater Agent-Stack + automatische Destillation in den globalen Pool.
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

from atlas_core.blackboard import append_learning, pin_signal
from atlas_core.llm import chat

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "atlas_agents"
HISTORY_DIR = BASE_DIR / "atlas_memory" / "history"


def _agent_dir(agent_name: str) -> Path:
    return AGENTS_DIR / agent_name


def read_agent_memory(agent_name: str) -> str:
    path = _agent_dir(agent_name) / "memory.md"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def write_agent_memory(agent_name: str, content: str):
    path = _agent_dir(agent_name) / "memory.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def save_history(agent: str, user_input: str, output: str, feedback: str = None) -> Path:
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "input": user_input,
        "output": output,
        "feedback": feedback,
        "learned_rule": None,
    }
    path = HISTORY_DIR / f"{entry['id']}.json"
    path.write_text(json.dumps(entry, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def auto_learn(agent: str, user_input: str, output: str):
    """
    Destilliert nach jedem Lauf automatisch eine Regel aus Input+Output
    und schreibt sie in die private memory.md und den globalen Lernpool.
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
                "Wenn keine sinnvolle Regel ableitbar ist, antworte nur mit: KEINE."
            ),
        },
        {
            "role": "user",
            "content": f"Agent: {agent}\n\nInput:\n{user_input}\n\nOutput:\n{output}\n\nAktuelle Memory:\n{current_memory}",
        },
    ]

    try:
        result = chat(distill_prompt, agent_name="learner")
    except Exception:
        return

    if result.strip().startswith("KEINE") or not result.strip().startswith("REGEL:"):
        return

    rule = result.strip().removeprefix("REGEL:").strip()

    # In private memory.md schreiben
    timestamp = datetime.now().strftime("%Y-%m-%d")
    new_memory = current_memory.rstrip() + f"\n\n- [{timestamp}] {rule}"
    write_agent_memory(agent, new_memory)

    # In globalen Pool destillieren
    append_learning(agent=agent, rule=rule, context=user_input[:300], confidence=0.75)

    # Signal auf Blackboard pinnen (andere Agenten können reagieren)
    pin_signal(
        agent=agent,
        signal_type="learning",
        content={"rule": rule, "context": user_input[:200]},
    )

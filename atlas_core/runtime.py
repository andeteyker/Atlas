"""
ATLAS Hermes Runtime — lädt den vollständigen privaten Agent-Stack
und baut den Schwarm-Kontext aus dem globalen Pool zusammen.
"""

from pathlib import Path

from atlas_core.blackboard import read_learnings, load_skill_index
from atlas_core.llm import chat

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "atlas_agents"
GLOBAL_KNOWLEDGE = BASE_DIR / "atlas_memory" / "global" / "atlas_knowledge.md"


def _read(path: Path, fallback: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def load_agent_stack(agent_name: str) -> dict:
    """Lädt den vollständigen privaten Stack eines Agenten."""
    agent_dir = AGENTS_DIR / agent_name
    return {
        "system": _read(agent_dir / "system.md"),
        "memory": _read(agent_dir / "memory.md"),
        "examples": _read(agent_dir / "examples.md"),
        "skills": _read(agent_dir / "skills.md"),
    }


def build_global_context() -> str:
    """Baut den globalen Schwarm-Kontext aus Knowledge + Learnings + Skill-Index."""
    knowledge = _read(GLOBAL_KNOWLEDGE)

    learnings = read_learnings(limit=30)
    learning_text = ""
    if learnings:
        learning_text = "\n\nGLOBALE SCHWARM-ERKENNTNISSE (neueste zuerst):\n"
        for l in reversed(learnings[-10:]):
            learning_text += f"- [{l['agent']}] {l['rule']}\n"

    skill_index = load_skill_index()
    skill_text = ""
    if skill_index:
        skill_text = "\n\nSCHWARM SKILL-INDEX (welcher Agent was kann):\n"
        for name, info in skill_index.items():
            skill_text += f"- {name}: {info.get('description', '')}\n"

    return knowledge + learning_text + skill_text


def run_agent(agent_name: str, task: str, delegation_context: str = "") -> str:
    """
    Führt einen Hermes-Agenten aus.
    Lädt privaten Stack + globalen Schwarm-Kontext.
    """
    stack = load_agent_stack(agent_name)
    global_context = build_global_context()

    delegation_block = ""
    if delegation_context:
        delegation_block = f"\n\nDELEGATIONS-KONTEXT (von anderem Agenten):\n{delegation_context}"

    system_prompt = f"""Du bist ein autonomer Hermes-Agent im ATLAS-Schwarm.
ATLAS ist ein dezentrales AIOS für PLM-Koordination, Prozessanalyse, Automatisierung und technische Arbeitsorganisation im Schiffbau.

═══ GLOBALER SCHWARM-KONTEXT ═══
{global_context}

═══ DEIN PRIVATER AGENT-STACK ═══

DEINE ROLLE UND REGELN:
{stack['system']}

DEIN ERLERNTES WISSEN (privat):
{stack['memory']}

DEINE FÄHIGKEITEN:
{stack['skills']}

GUTE BEISPIELE AUS DEINER ERFAHRUNG:
{stack['examples']}
{delegation_block}

ARBEITSREGELN:
- Trenne Fakten, Annahmen, Risiken und nächste Schritte klar.
- Erfinde keine fehlenden Informationen — markiere Lücken.
- Wenn ein anderer Agent besser geeignet ist, schreibe am Ende: DELEGATION: <agent_name> | <subtask>
- Gib verwertbare, technisch präzise Ergebnisse.
"""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    return chat(messages, agent_name=agent_name)

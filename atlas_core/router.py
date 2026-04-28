"""
ATLAS Swarm Dispatcher — wählt den passenden Agenten anhand des Skill-Index.
Erkennt wenn kein Agent passt und löst ggf. einen Spawn aus.
"""

from atlas_core.blackboard import load_agent_registry, load_skill_index, pin_signal
from atlas_core.llm import chat


def _build_agent_list() -> tuple[dict, str]:
    """Kombiniert statische + dynamisch registrierte Agenten."""
    registry = load_agent_registry()
    agent_lines = []
    for name, info in registry.items():
        if info.get("active", True):
            agent_lines.append(f"- {name}: {info.get('description', '')}")
    return registry, "\n".join(agent_lines)


def validate_input(text: str) -> tuple[bool, str]:
    """Einfache Input-Validierung vor dem Routing."""
    if len(text.strip()) < 10:
        return False, "Input zu kurz — bitte mehr Kontext angeben."
    return True, ""


def route_task(text: str) -> tuple[str, bool]:
    """
    Wählt den passenden Agenten.
    Gibt (agent_name, spawn_needed) zurück.
    """
    registry, agent_list = _build_agent_list()

    if not registry:
        return "plm_coordinator", False

    prompt = f"""Du bist der ATLAS Swarm Dispatcher.
Wähle den passendsten Agenten für diesen Input.

Verfügbare Agenten:
{agent_list}

Input:
{text}

Antworte NUR mit:
- Dem exakten Agentennamen aus der Liste, ODER
- "SPAWN_NEEDED: <kurze Beschreibung des benötigten neuen Agenten>" wenn kein Agent passt.
"""

    result = chat(
        [
            {"role": "system", "content": "Du bist ein präziser Router. Antworte nur mit dem Agentennamen oder SPAWN_NEEDED."},
            {"role": "user", "content": prompt},
        ],
        agent_name="router",
    ).strip()

    if result.startswith("SPAWN_NEEDED:"):
        description = result.removeprefix("SPAWN_NEEDED:").strip()
        pin_signal(
            agent="dispatcher",
            signal_type="spawn_request",
            content={"description": description, "trigger_input": text[:300]},
        )
        return "plm_coordinator", True

    if result not in registry:
        return "plm_coordinator", False

    return result, False

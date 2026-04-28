"""
ATLAS Swarm Dispatcher — wählt den passenden Agenten anhand des Skill-Index.

Zweistufiges Routing:
  1. Keyword-Match (kein LLM-Call, schnell)
  2. LLM-Fallback (wenn unklar)
  3. Spawn-Request (wenn wirklich nichts passt)

Wenn der Schwarm leer ist: RuntimeError("ATLAS_EMPTY_SWARM") —
der Aufrufer (atlas.py) leitet dann zum Bootstrap-Flow weiter.
"""

from __future__ import annotations

from atlas_core.blackboard import load_agent_registry, pin_signal
from atlas_core.llm import chat


def _build_agent_list() -> tuple[dict, str]:
    registry = load_agent_registry()
    lines = []
    for name, info in registry.items():
        if info.get("active", True):
            skills = ", ".join(info.get("skills", [])[:4])
            lines.append(f"- {name}: {info.get('description', '')} [{skills}]")
    return registry, "\n".join(lines)


def validate_input(text: str) -> tuple[bool, str]:
    text = text.strip()
    if len(text) < 5:
        return False, "Input zu kurz — bitte mehr Kontext angeben (min. 5 Zeichen)."
    if len(text) > 20_000:
        return False, f"Input zu lang ({len(text)} Zeichen) — max. 20.000 Zeichen."
    return True, ""


def _keyword_route(text: str, registry: dict) -> str | None:
    """
    Schnelles Keyword-Routing ohne LLM-Aufruf.
    Baut Keywords dynamisch aus dem Skill-Index statt hardcoded-Listen.
    Gibt Agentennamen zurück wenn klarer Match, sonst None.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    for agent_name, info in registry.items():
        if not info.get("active", True):
            continue
        # Skills und Description als Keywords nutzen
        keywords: list[str] = []
        for skill in info.get("skills", []):
            keywords.append(skill.lower())
        desc = info.get("description", "").lower()
        # Einzelne signifikante Wörter aus der Description
        keywords += [w for w in desc.split() if len(w) > 4]

        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[agent_name] = score

    if not scores:
        return None

    best = max(scores, key=lambda k: scores[k])
    if scores[best] >= 2 or len(scores) == 1:
        return best
    return None


def route_task(text: str) -> tuple[str, bool]:
    """
    Wählt den passenden Agenten.

    Returns:
        (agent_name, spawn_needed)

    Raises:
        RuntimeError("ATLAS_EMPTY_SWARM") wenn keine Agenten registriert sind.
    """
    registry, agent_list = _build_agent_list()

    if not registry:
        raise RuntimeError("ATLAS_EMPTY_SWARM")

    # Schritt 1: Keyword-Routing (ohne LLM)
    keyword_match = _keyword_route(text, registry)
    if keyword_match:
        return keyword_match, False

    # Schritt 2: LLM-Routing
    prompt = f"""Du bist der ATLAS Swarm Dispatcher. Wähle den exakt passendsten Agenten.

VERFÜGBARE AGENTEN:
{agent_list}

AUFGABE:
{text[:500]}

Antworte NUR mit:
- Dem EXAKTEN Agentennamen aus der Liste
- ODER: SPAWN_NEEDED: <eine Zeile Beschreibung des benötigten Agenten>

Deine Antwort:"""

    try:
        result = chat(
            [
                {
                    "role": "system",
                    "content": "Antworte ausschließlich mit dem Agentennamen oder SPAWN_NEEDED:...",
                },
                {"role": "user", "content": prompt},
            ],
            agent_name="router",
        ).strip()
    except Exception:
        # Fallback: ersten aktiven Agenten nehmen
        first = next(iter(registry))
        return first, False

    if result.upper().startswith("SPAWN_NEEDED:"):
        description = result[len("SPAWN_NEEDED:"):].strip()
        pin_signal(
            agent="dispatcher",
            signal_type="spawn_request",
            content={"description": description, "trigger_input": text[:300]},
        )
        first = next(iter(registry))
        return first, True

    clean = result.strip().strip("'\"").split("\n")[0].strip()
    if clean in registry:
        return clean, False

    for name in registry:
        if name in clean.lower() or clean.lower() in name:
            return name, False

    first = next(iter(registry))
    return first, False

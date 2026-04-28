"""
ATLAS Swarm Dispatcher — wählt den passenden Agenten anhand des Skill-Index.

Verbesserungen:
- Zweistufiges Routing: zuerst Keyword-Match, dann LLM-Fallback
- Skill-Index wird für schnelle Vorauswahl genutzt
- Spawn-Request nur wenn wirklich kein Agent passt
- Input-Validierung mit detaillierten Fehlermeldungen
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
    Gibt Agentennamen zurück wenn ein klarer Match gefunden, sonst None.
    """
    text_lower = text.lower()
    scores: dict[str, int] = {}

    keyword_map: dict[str, list[str]] = {
        "sr_writer": [
            "service request", "sr erstell", "bug report", "fehlermeldung",
            "fehler melden", "ticket", "expected result", "actual result",
            "workaround", "bug", "fehler in"
        ],
        "demand_writer": [
            "it demand", "demand", "business case", "roi", "management",
            "entscheidungsvorlage", "antrag", "investition", "nutzen"
        ],
        "automation_engineer": [
            "python", "power automate", "vba", "autohotkey", "skript", "script",
            "automatisier", "pipeline", "excel makro", "shell", "automatisch"
        ],
        "daily_briefing": [
            "tagesplan", "briefing", "priorität", "heute", "morning",
            "aufgaben heute", "was steht an", "tagesübersicht"
        ],
        "plm_coordinator": [
            "catia", "enovia", "3dexperience", "3dx", "sap", "p&id",
            "product structure", "jlm", "item-id", "plm", "attribute"
        ],
    }

    for agent_name, keywords in keyword_map.items():
        if agent_name not in registry or not registry[agent_name].get("active", True):
            continue
        score = sum(1 for kw in keywords if kw in text_lower)
        if score > 0:
            scores[agent_name] = score

    if not scores:
        return None

    best = max(scores, key=lambda k: scores[k])
    # Nur wenn klarer Vorsprung (mind. 2 Treffer, oder einziger Treffer)
    if scores[best] >= 2 or len(scores) == 1:
        return best
    return None


def route_task(text: str) -> tuple[str, bool]:
    """
    Wählt den passenden Agenten.
    1. Keyword-Match (schnell, kein LLM-Call)
    2. LLM-Fallback (wenn unklar)
    3. Spawn-Request (wenn wirklich nichts passt)

    Returns:
        (agent_name, spawn_needed)
    """
    registry, agent_list = _build_agent_list()

    if not registry:
        return "plm_coordinator", False

    # Schritt 1: Keyword-Routing (ohne LLM)
    keyword_match = _keyword_route(text, registry)
    if keyword_match:
        return keyword_match, False

    # Schritt 2: LLM-Routing mit kompaktem Prompt
    prompt = f"""Du bist der ATLAS Swarm Dispatcher. Wähle den exakt passendsten Agenten.

VERFÜGBARE AGENTEN:
{agent_list}

AUFGABE:
{text[:500]}

Antworte NUR mit:
- Dem EXAKTEN Agentennamen aus der Liste (kein Kommentar, kein Punkt)
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
        return "plm_coordinator", False

    # Spawn-Anfrage
    if result.upper().startswith("SPAWN_NEEDED:"):
        description = result[len("SPAWN_NEEDED:"):].strip()
        pin_signal(
            agent="dispatcher",
            signal_type="spawn_request",
            content={"description": description, "trigger_input": text[:300]},
        )
        return "plm_coordinator", True

    # Bereinigen und validieren
    clean = result.strip().strip("'\"").split("\n")[0].strip()
    if clean in registry:
        return clean, False

    # Fuzzy: enthält ein bekannter Name den Result-String?
    for name in registry:
        if name in clean.lower() or clean.lower() in name:
            return name, False

    return "plm_coordinator", False

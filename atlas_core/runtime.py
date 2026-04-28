"""
ATLAS Hermes Runtime — lädt den vollständigen privaten Agent-Stack
und baut den Schwarm-Kontext aus dem globalen Pool zusammen.

Verbesserungen:
- Semantische Memory-Suche (ChromaDB) statt vollständigem Text-Dump
- Tool-Use-Loop (function calling) für befähigte Agenten
- Streaming-Support mit Callback
- Strukturiertes Response-Parsing (AgentResponse)
- Context-Budget: Globale Erkenntnisse semantisch gefiltert
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Callable, Optional

from atlas_core.blackboard import read_learnings, load_skill_index
from atlas_core.llm import chat, chat_stream, chat_with_tools
from atlas_core.schema import AgentResponse
from atlas_core.tools import get_tools_for_agent
from atlas_core import vector_memory as vm

BASE_DIR = Path(__file__).resolve().parents[1]
AGENTS_DIR = BASE_DIR / "atlas_agents"
GLOBAL_KNOWLEDGE = BASE_DIR / "atlas_memory" / "global" / "atlas_knowledge.md"

# Max. Zeichen für globalen Kontext im System-Prompt
GLOBAL_CONTEXT_BUDGET = 3_000
# Max. Zeichen für Memory-Sektion im System-Prompt
MEMORY_BUDGET = 1_500


def _read(path: Path, fallback: str = "") -> str:
    return path.read_text(encoding="utf-8") if path.exists() else fallback


def load_agent_stack(agent_name: str) -> dict:
    agent_dir = AGENTS_DIR / agent_name
    return {
        "system": _read(agent_dir / "system.md"),
        "memory": _read(agent_dir / "memory.md"),
        "examples": _read(agent_dir / "examples.md"),
        "skills": _read(agent_dir / "skills.md"),
    }


def build_global_context(query: str = "") -> str:
    """
    Baut den globalen Schwarm-Kontext.
    Wenn ChromaDB verfügbar: semantisch gefilterte Erkenntnisse.
    Fallback: neueste N Erkenntnisse aus learnings.jsonl.
    """
    knowledge = _read(GLOBAL_KNOWLEDGE)
    if len(knowledge) > GLOBAL_CONTEXT_BUDGET:
        knowledge = knowledge[:GLOBAL_CONTEXT_BUDGET] + "\n[...]"

    # Semantisch relevante Erkenntnisse (wenn query verfügbar)
    learning_text = ""
    if query:
        semantic_learnings = vm.search_global_learnings(query, n=8)
        if semantic_learnings:
            learning_text = "\n\nRELEVANTE SCHWARM-ERKENNTNISSE:\n"
            for l in semantic_learnings[:6]:
                agent = l.get("agent", "?")
                rule = l.get("rule", "")
                learning_text += f"- [{agent}] {rule}\n"

    if not learning_text:
        # Fallback: letzte Erkenntnisse aus JSONL
        raw_learnings = read_learnings(limit=10)
        if raw_learnings:
            learning_text = "\n\nGLOBALE SCHWARM-ERKENNTNISSE (neueste):\n"
            for l in reversed(raw_learnings[-5:]):
                learning_text += f"- [{l['agent']}] {l['rule']}\n"

    # Skill-Index (kompakt)
    skill_index = load_skill_index()
    skill_text = ""
    if skill_index:
        skill_text = "\n\nSCHWARM SKILL-INDEX:\n"
        for name, info in skill_index.items():
            skill_text += f"- {name}: {info.get('description', '')[:80]}\n"

    return (knowledge + learning_text + skill_text).strip()


def _build_memory_section(agent_name: str, query: str) -> str:
    """
    Baut die Memory-Sektion für den System-Prompt.
    Semantische Suche wenn ChromaDB verfügbar, sonst volle memory.md.
    """
    agent_dir = AGENTS_DIR / agent_name

    # Semantisch relevante Memories
    if query:
        semantic_hits = vm.search_memory(agent_name, query, n=5)
        if semantic_hits:
            block = "\n".join(f"• {m}" for m in semantic_hits)
            return f"RELEVANTE ERINNERUNGEN (semantisch):\n{block}"

    # Fallback: komplette memory.md (mit Budget-Limit)
    raw = _read(agent_dir / "memory.md")
    if len(raw) > MEMORY_BUDGET:
        raw = raw[:MEMORY_BUDGET] + "\n[...]"
    return raw


def run_agent(
    agent_name: str,
    task: str,
    delegation_context: str = "",
    stream_callback: Optional[Callable[[str], None]] = None,
) -> AgentResponse:
    """
    Führt einen Hermes-Agenten aus.

    Args:
        agent_name: Name des Agenten (z.B. "plm_coordinator")
        task: Der User-Task
        delegation_context: Optionaler Kontext von delegierendem Agenten
        stream_callback: Funktion(chunk) für Live-Streaming (optional)

    Returns:
        AgentResponse mit strukturiertem Output
    """
    stack = load_agent_stack(agent_name)
    global_context = build_global_context(query=task)
    memory_section = _build_memory_section(agent_name, query=task)

    delegation_block = ""
    if delegation_context:
        delegation_block = f"\n\nDELEGATIONS-KONTEXT:\n{delegation_context}"

    tools = get_tools_for_agent(agent_name)
    tool_hint = ""
    if tools:
        tool_names = [t["function"]["name"] for t in tools]
        tool_hint = f"\n\nVERFÜGBARE TOOLS: {', '.join(tool_names)} — nutze sie wenn sinnvoll."

    system_prompt = f"""Du bist ein autonomer Hermes-Agent im ATLAS-Schwarm.
ATLAS ist ein dezentrales AIOS für PLM-Koordination, Prozessanalyse, Automatisierung und Arbeitsorganisation im Schiffbau.

═══ GLOBALER SCHWARM-KONTEXT ═══
{global_context}

═══ DEIN PRIVATER AGENT-STACK ═══

DEINE ROLLE:
{stack['system']}

DEIN ERLERNTES WISSEN:
{memory_section}

DEINE FÄHIGKEITEN:
{stack['skills']}

BEISPIELE:
{stack['examples']}
{delegation_block}{tool_hint}

ARBEITSREGELN:
- Trenne Fakten, Annahmen, Risiken und nächste Schritte klar.
- Erfinde keine fehlenden Informationen — markiere Lücken explizit.
- Wenn ein anderer Agent deutlich besser geeignet ist, schreibe am Ende eine neue Zeile:
  DELEGATION: <agent_name> | <subtask beschreibung>
- Wissenslücken: GAP: <thema> | <warum unklar>
- Gib verwertbare, technisch präzise Ergebnisse."""

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": task},
    ]

    start = time.monotonic()

    if tools:
        raw_text, tool_log = chat_with_tools(
            messages=messages,
            tools=tools,
            agent_name=agent_name,
            stream_callback=stream_callback,
        )
    elif stream_callback:
        chunks: list[str] = []
        for chunk in chat_stream(messages, agent_name=agent_name):
            stream_callback(chunk)
            chunks.append(chunk)
        raw_text = "".join(chunks)
    else:
        raw_text = chat(messages, agent_name=agent_name)

    duration_ms = int((time.monotonic() - start) * 1000)

    response = AgentResponse.from_raw_text(raw_text, agent_name=agent_name)
    return response

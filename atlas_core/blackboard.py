"""
ATLAS Blackboard — zentraler Schwarm-Wissensspeicher.

Agenten pinnen Ergebnisse, Signale und Wissenslücken hier ab.
Andere Agenten reagieren autonom darauf (Stigmergy-Prinzip).
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parents[1]
BLACKBOARD_DIR = BASE_DIR / "atlas_memory" / "blackboard"
SKILL_INDEX = BASE_DIR / "atlas_memory" / "global" / "skill_index.json"
AGENT_REGISTRY = BASE_DIR / "atlas_memory" / "global" / "agent_registry.json"
LEARNINGS = BASE_DIR / "atlas_memory" / "global" / "learnings.jsonl"


def _ensure_dirs():
    BLACKBOARD_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "atlas_memory" / "global").mkdir(parents=True, exist_ok=True)


# ── Blackboard: Signals ──────────────────────────────────────────────────────

def pin_signal(agent: str, signal_type: str, content: dict) -> str:
    """Agent hinterlässt ein Signal auf dem Blackboard (Pheromon-Prinzip)."""
    _ensure_dirs()
    signal = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "type": signal_type,   # "learning" | "gap" | "delegation" | "spawn_request"
        "content": content,
        "consumed": False,
    }
    path = BLACKBOARD_DIR / f"{signal['id']}.json"
    path.write_text(json.dumps(signal, indent=2, ensure_ascii=False), encoding="utf-8")
    return signal["id"]


def read_signals(signal_type: str = None, unconsumed_only: bool = True) -> list:
    """Liest alle Signale vom Blackboard, optional gefiltert."""
    _ensure_dirs()
    signals = []
    for f in sorted(BLACKBOARD_DIR.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if unconsumed_only and s.get("consumed"):
                continue
            if signal_type and s.get("type") != signal_type:
                continue
            signals.append(s)
        except Exception:
            continue
    return signals


def consume_signal(signal_id: str):
    """Markiert ein Signal als verarbeitet."""
    path = BLACKBOARD_DIR / f"{signal_id}.json"
    if path.exists():
        s = json.loads(path.read_text(encoding="utf-8"))
        s["consumed"] = True
        path.write_text(json.dumps(s, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Learnings: globaler Wissenspool ─────────────────────────────────────────

def append_learning(agent: str, rule: str, context: str, confidence: float = 0.8):
    """Schreibt eine neue Erkenntnis in den globalen Lernpool."""
    _ensure_dirs()
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "rule": rule,
        "context": context,
        "confidence": confidence,
    }
    with LEARNINGS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_learnings(limit: int = 50) -> list:
    """Liest die letzten N Erkenntnisse aus dem globalen Pool."""
    if not LEARNINGS.exists():
        return []
    lines = LEARNINGS.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except Exception:
            continue
    return entries


# ── Skill Index ──────────────────────────────────────────────────────────────

def load_skill_index() -> dict:
    if not SKILL_INDEX.exists():
        return {}
    return json.loads(SKILL_INDEX.read_text(encoding="utf-8"))


def register_skill(agent: str, skills: list[str], description: str):
    """Registriert oder aktualisiert Skills eines Agenten im globalen Index."""
    _ensure_dirs()
    index = load_skill_index()
    index[agent] = {
        "skills": skills,
        "description": description,
        "updated": datetime.now().isoformat(timespec="seconds"),
    }
    SKILL_INDEX.write_text(json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Agent Registry ───────────────────────────────────────────────────────────

def load_agent_registry() -> dict:
    if not AGENT_REGISTRY.exists():
        return {}
    return json.loads(AGENT_REGISTRY.read_text(encoding="utf-8"))


def register_agent(name: str, description: str, skills: list[str], spawned_by: str = "human"):
    """Registriert einen neuen oder aktualisierten Agenten."""
    _ensure_dirs()
    registry = load_agent_registry()
    registry[name] = {
        "description": description,
        "skills": skills,
        "spawned_by": spawned_by,
        "registered": datetime.now().isoformat(timespec="seconds"),
        "active": True,
    }
    AGENT_REGISTRY.write_text(json.dumps(registry, indent=2, ensure_ascii=False), encoding="utf-8")
    register_skill(name, skills, description)

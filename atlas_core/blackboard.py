"""
ATLAS Blackboard — zentraler Schwarm-Wissensspeicher.

Agenten pinnen Ergebnisse, Signale und Wissenslücken hier ab.
Andere Agenten reagieren autonom darauf (Stigmergy-Prinzip).

Verbesserungen:
- File-Locking via filelock (verhindert Race Conditions bei parallelen Läufen)
- TTL: Signale verfallen automatisch nach konfigurierbarer Zeit
- Prioritäten (1-10) für Signal-Verarbeitung
- Atomisches Schreiben (write + rename statt direktem write)
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
BLACKBOARD_DIR = BASE_DIR / "atlas_memory" / "blackboard"
SKILL_INDEX = BASE_DIR / "atlas_memory" / "global" / "skill_index.json"
AGENT_REGISTRY = BASE_DIR / "atlas_memory" / "global" / "agent_registry.json"
LEARNINGS = BASE_DIR / "atlas_memory" / "global" / "learnings.jsonl"

# Standard-TTL für verschiedene Signal-Typen (None = kein Verfall)
DEFAULT_TTL: dict[str, Optional[int]] = {
    "learning": None,       # Lernregeln verfallen nicht
    "gap": 48,              # Wissenslücken nach 48h
    "delegation": 72,       # Delegationen nach 72h
    "spawn_request": 168,   # Spawn-Anfragen nach 1 Woche
}


def _ensure_dirs():
    BLACKBOARD_DIR.mkdir(parents=True, exist_ok=True)
    (BASE_DIR / "atlas_memory" / "global").mkdir(parents=True, exist_ok=True)


def _atomic_write(path: Path, data: dict):
    """Schreibt atomisch via temporäre Datei + rename (crash-safe)."""
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def _try_lock(path: Path):
    """Gibt einen Filelock-Kontext zurück oder einen Null-Kontext als Fallback."""
    try:
        from filelock import FileLock
        return FileLock(str(path) + ".lock", timeout=5)
    except ImportError:
        from contextlib import nullcontext
        return nullcontext()


def _is_expired(signal: dict) -> bool:
    """Prüft ob ein Signal seinen TTL überschritten hat."""
    ttl_hours = signal.get("ttl_hours")
    if ttl_hours is None:
        return False
    ts = signal.get("timestamp", "")
    try:
        created = datetime.fromisoformat(ts)
        return datetime.now() > created + timedelta(hours=ttl_hours)
    except (ValueError, TypeError):
        return False


# ── Blackboard: Signals ──────────────────────────────────────────────────────

def pin_signal(
    agent: str,
    signal_type: str,
    content: dict,
    priority: int = 5,
    ttl_hours: Optional[int] = None,
) -> str:
    """
    Agent hinterlässt ein Signal auf dem Blackboard.

    Args:
        agent: Name des sendenden Agenten
        signal_type: "learning" | "gap" | "delegation" | "spawn_request"
        content: Beliebiger JSON-serialisierbarer Inhalt
        priority: 1 (niedrig) bis 10 (hoch)
        ttl_hours: Stunden bis zum Verfall (None = kein Verfall)
    """
    _ensure_dirs()
    if ttl_hours is None:
        ttl_hours = DEFAULT_TTL.get(signal_type)

    signal = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "type": signal_type,
        "content": content,
        "consumed": False,
        "priority": max(1, min(10, priority)),
        "ttl_hours": ttl_hours,
    }
    path = BLACKBOARD_DIR / f"{signal['id']}.json"
    with _try_lock(path):
        _atomic_write(path, signal)
    return signal["id"]


def read_signals(
    signal_type: str | None = None,
    unconsumed_only: bool = True,
    min_priority: int = 1,
) -> list[dict]:
    """
    Liest Signale vom Blackboard, optional gefiltert.
    Automatisch abgelaufene Signale werden übersprungen und bereinigt.
    Sortiert nach Priorität (hoch zuerst).
    """
    _ensure_dirs()
    signals = []
    to_cleanup: list[Path] = []

    for f in sorted(BLACKBOARD_DIR.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            # Abgelaufene Signale markieren
            if _is_expired(s):
                to_cleanup.append(f)
                continue
            if unconsumed_only and s.get("consumed"):
                continue
            if signal_type and s.get("type") != signal_type:
                continue
            if s.get("priority", 5) < min_priority:
                continue
            signals.append(s)
        except (json.JSONDecodeError, OSError):
            continue

    # Abgelaufene Signale als consumed markieren
    for f in to_cleanup:
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            s["consumed"] = True
            s["expired"] = True
            with _try_lock(f):
                _atomic_write(f, s)
        except Exception:
            pass

    # Nach Priorität sortieren (hoch zuerst), dann nach Timestamp
    signals.sort(key=lambda s: (-s.get("priority", 5), s.get("timestamp", "")))
    return signals


def consume_signal(signal_id: str):
    """Markiert ein Signal als verarbeitet."""
    path = BLACKBOARD_DIR / f"{signal_id}.json"
    if not path.exists():
        return
    with _try_lock(path):
        try:
            s = json.loads(path.read_text(encoding="utf-8"))
            s["consumed"] = True
            s["consumed_at"] = datetime.now().isoformat(timespec="seconds")
            _atomic_write(path, s)
        except Exception:
            pass


def get_signal_stats() -> dict:
    """Gibt Statistiken über den Blackboard-Zustand zurück."""
    _ensure_dirs()
    total = consumed = expired = 0
    by_type: dict[str, int] = {}
    for f in BLACKBOARD_DIR.glob("*.json"):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            total += 1
            if s.get("consumed"):
                consumed += 1
            if _is_expired(s):
                expired += 1
            stype = s.get("type", "unknown")
            by_type[stype] = by_type.get(stype, 0) + 1
        except Exception:
            pass
    return {
        "total": total,
        "consumed": consumed,
        "active": total - consumed,
        "expired": expired,
        "by_type": by_type,
    }


# ── Learnings: globaler Wissenspool ─────────────────────────────────────────

def append_learning(agent: str, rule: str, context: str, confidence: float = 0.8):
    """Schreibt eine neue Erkenntnis in den globalen JSONL-Lernpool (Fallback-Persistenz)."""
    _ensure_dirs()
    entry = {
        "id": str(uuid.uuid4()),
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "agent": agent,
        "rule": rule,
        "context": context,
        "confidence": confidence,
    }
    with _try_lock(LEARNINGS):
        with LEARNINGS.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def read_learnings(limit: int = 50) -> list[dict]:
    if not LEARNINGS.exists():
        return []
    lines = LEARNINGS.read_text(encoding="utf-8").strip().splitlines()
    entries = []
    for line in lines[-limit:]:
        try:
            entries.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return entries


# ── Skill Index ──────────────────────────────────────────────────────────────

def load_skill_index() -> dict:
    if not SKILL_INDEX.exists():
        return {}
    try:
        return json.loads(SKILL_INDEX.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def register_skill(agent: str, skills: list[str], description: str):
    _ensure_dirs()
    with _try_lock(SKILL_INDEX):
        index = load_skill_index()
        index[agent] = {
            "skills": skills,
            "description": description,
            "updated": datetime.now().isoformat(timespec="seconds"),
        }
        _atomic_write(SKILL_INDEX, index)


# ── Agent Registry ───────────────────────────────────────────────────────────

def load_agent_registry() -> dict:
    if not AGENT_REGISTRY.exists():
        return {}
    try:
        return json.loads(AGENT_REGISTRY.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def register_agent(name: str, description: str, skills: list[str], spawned_by: str = "human"):
    _ensure_dirs()
    with _try_lock(AGENT_REGISTRY):
        registry = load_agent_registry()
        registry[name] = {
            "description": description,
            "skills": skills,
            "spawned_by": spawned_by,
            "registered": datetime.now().isoformat(timespec="seconds"),
            "active": True,
        }
        _atomic_write(AGENT_REGISTRY, registry)
    register_skill(name, skills, description)

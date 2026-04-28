"""
ATLAS Vector Memory — semantische Suche für Agent-Memory und globale Erkenntnisse.

Basiert auf ChromaDB (chroma-core/chroma) mit lokalem PersistentClient:
- Kein Server nötig — alles lokal auf Disk
- Default-Embedding: all-MiniLM-L6-v2 via onnxruntime (wird beim ersten Aufruf geladen)
- Semantisches Dedup für globale Erkenntnisse (Distanz-Schwelle < 0.15)
- Privater Namespace pro Agent + globaler Schwarm-Pool
- Graceful Fallback wenn ChromaDB nicht verfügbar
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

BASE_DIR = Path(__file__).resolve().parents[1]
CHROMA_DIR = BASE_DIR / "atlas_memory" / "chroma"

# Ähnlichkeitsschwelle für semantisches Dedup (L2-Distanz, kleiner = ähnlicher)
DEDUP_DISTANCE_THRESHOLD = 0.25

_client = None
_available: Optional[bool] = None


def _check_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        import chromadb  # noqa: F401
        _available = True
    except ImportError:
        _available = False
    return _available


def _get_client():
    global _client
    if _client is None:
        import chromadb
        CHROMA_DIR.mkdir(parents=True, exist_ok=True)
        _client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    return _client


def _get_collection(name: str):
    """Gibt eine ChromaDB-Collection zurück (oder erstellt sie)."""
    from chromadb.utils.embedding_functions import DefaultEmbeddingFunction
    client = _get_client()
    safe_name = name.replace("-", "_").replace(" ", "_")[:63]
    return client.get_or_create_collection(
        name=safe_name,
        embedding_function=DefaultEmbeddingFunction(),
        metadata={"hnsw:space": "l2"},
    )


# ── Private Agent Memory ──────────────────────────────────────────────────────

def add_memory(agent: str, content: str, metadata: dict | None = None) -> bool:
    """
    Fügt eine Erinnerung zum privaten Agenten-Speicher hinzu.
    Gibt True zurück wenn erfolgreich, False bei Fehler.
    """
    if not _check_available() or not content.strip():
        return False
    try:
        col = _get_collection(f"agent_{agent}")
        doc_id = str(uuid.uuid4())
        col.add(
            documents=[content.strip()],
            ids=[doc_id],
            metadatas=[{
                **(metadata or {}),
                "agent": agent,
                "ts": datetime.now().isoformat(timespec="seconds"),
            }],
        )
        return True
    except Exception:
        return False


def search_memory(agent: str, query: str, n: int = 5) -> list[str]:
    """
    Sucht semantisch in der privaten Memory eines Agenten.
    Gibt die relevantesten Dokumente zurück, leer bei Fehler.
    """
    if not _check_available() or not query.strip():
        return []
    try:
        col = _get_collection(f"agent_{agent}")
        count = col.count()
        if count == 0:
            return []
        results = col.query(
            query_texts=[query.strip()],
            n_results=min(n, count),
        )
        docs = results.get("documents", [[]])[0]
        return [d for d in docs if d]
    except Exception:
        return []


def memory_count(agent: str) -> int:
    """Gibt die Anzahl der gespeicherten Memories zurück."""
    if not _check_available():
        return 0
    try:
        return _get_collection(f"agent_{agent}").count()
    except Exception:
        return 0


# ── Global Learnings Pool ─────────────────────────────────────────────────────

def add_global_learning(agent: str, rule: str, context: str = "") -> bool:
    """
    Fügt eine Erkenntnis zum globalen Schwarm-Pool hinzu.
    Semantisches Dedup: Zu ähnliche Regeln werden ignoriert.
    """
    if not _check_available() or not rule.strip():
        return False
    try:
        col = _get_collection("global_learnings")
        # Semantisches Dedup
        if col.count() > 0:
            existing = col.query(query_texts=[rule.strip()], n_results=1)
            distances = (existing.get("distances") or [[]])[0]
            if distances and distances[0] < DEDUP_DISTANCE_THRESHOLD:
                return False  # Zu ähnlich — ignorieren
        col.add(
            documents=[rule.strip()],
            ids=[str(uuid.uuid4())],
            metadatas=[{
                "agent": agent,
                "context": context[:300],
                "ts": datetime.now().isoformat(timespec="seconds"),
            }],
        )
        return True
    except Exception:
        return False


def search_global_learnings(query: str, n: int = 10) -> list[dict]:
    """
    Sucht semantisch im globalen Erkenntnispool.
    Gibt Liste von {rule, agent, context, ts} zurück.
    """
    if not _check_available() or not query.strip():
        return []
    try:
        col = _get_collection("global_learnings")
        count = col.count()
        if count == 0:
            return []
        results = col.query(
            query_texts=[query.strip()],
            n_results=min(n, count),
        )
        docs = results.get("documents", [[]])[0]
        metas = results.get("metadatas", [[]])[0]
        return [
            {"rule": d, **(m or {})}
            for d, m in zip(docs, metas)
            if d
        ]
    except Exception:
        return []


def global_learning_count() -> int:
    if not _check_available():
        return 0
    try:
        return _get_collection("global_learnings").count()
    except Exception:
        return 0


# ── Session History ───────────────────────────────────────────────────────────

def add_session_entry(agent: str, user_input: str, output: str, run_id: str = "") -> bool:
    """Speichert einen Lauf in der semantisch durchsuchbaren Session-History."""
    if not _check_available():
        return False
    try:
        col = _get_collection("session_history")
        combined = f"Agent: {agent}\nInput: {user_input[:500]}\nOutput: {output[:500]}"
        col.add(
            documents=[combined],
            ids=[run_id or str(uuid.uuid4())],
            metadatas=[{
                "agent": agent,
                "input_preview": user_input[:200],
                "ts": datetime.now().isoformat(timespec="seconds"),
            }],
        )
        return True
    except Exception:
        return False


def search_history(query: str, n: int = 5) -> list[dict]:
    """Sucht semantisch in der gesamten Session-History."""
    if not _check_available() or not query.strip():
        return []
    try:
        col = _get_collection("session_history")
        count = col.count()
        if count == 0:
            return []
        results = col.query(
            query_texts=[query.strip()],
            n_results=min(n, count),
        )
        metas = results.get("metadatas", [[]])[0]
        return list(metas)
    except Exception:
        return []


# ── Diagnostik ───────────────────────────────────────────────────────────────

def vector_stats() -> dict:
    """Gibt Statistiken über den Vector-Store zurück."""
    if not _check_available():
        return {"available": False, "reason": "chromadb nicht installiert"}
    try:
        return {
            "available": True,
            "global_learnings": global_learning_count(),
            "session_history": _get_collection("session_history").count(),
        }
    except Exception as e:
        return {"available": True, "error": str(e)}

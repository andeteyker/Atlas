"""
ATLAS Delegation — asynchrone Agent-zu-Agent Aufgabenübergabe.

Agenten delegieren Subtasks asynchron via Blackboard-Signale.
Beim nächsten Lauf werden offene Delegationen verarbeitet.

Kompatibel mit dem neuen AgentResponse-System.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from atlas_core.blackboard import pin_signal, read_signals, consume_signal

BASE_DIR = Path(__file__).resolve().parents[1]
DELEGATION_DIR = BASE_DIR / "atlas_memory" / "blackboard"


def delegate(from_agent: str, to_agent: str, task: str, context: str = "") -> str:
    """
    Delegiert einen Subtask asynchron an einen anderen Agenten.
    Gibt die Signal-ID zurück.
    """
    delegation_id = pin_signal(
        agent=from_agent,
        signal_type="delegation",
        content={
            "to_agent": to_agent,
            "task": task,
            "context": context,
            "status": "pending",
            "result": None,
        },
        priority=6,
    )
    print(f"[DELEGATION] {from_agent} → {to_agent}: eingereiht (ID: {delegation_id[:8]})")
    return delegation_id


def process_delegations():
    """
    Verarbeitet alle ausstehenden Delegationen.
    Wird beim nächsten `atlas run` automatisch ausgeführt.
    """
    from atlas_core.runtime import run_agent
    from atlas_core.memory import auto_learn, save_history

    pending = read_signals(signal_type="delegation")
    if not pending:
        return

    for signal in pending:
        content = signal.get("content", {})
        if content.get("status") != "pending":
            continue

        to_agent = content.get("to_agent", "plm_coordinator")
        task = content.get("task", "")
        context = content.get("context", "")

        print(f"[DELEGATION] Verarbeite → {to_agent}: {task[:60]}...")
        try:
            response = run_agent(to_agent, task, delegation_context=context)
            output_text = response.output

            content["status"] = "done"
            content["result"] = output_text[:2000]  # Limit für Blackboard-Storage
            content["completed_at"] = datetime.now().isoformat(timespec="seconds")

            path = DELEGATION_DIR / f"{signal['id']}.json"
            signal["content"] = content
            path.write_text(json.dumps(signal, indent=2, ensure_ascii=False), encoding="utf-8")

            save_history(to_agent, task, output_text)
            auto_learn(to_agent, task, output_text)

            print(f"[DELEGATION] ✓ {to_agent} fertig")
        except Exception as e:
            print(f"[DELEGATION] ✗ Fehler bei {to_agent}: {e}")
            content["status"] = "error"
            content["error"] = str(e)
            try:
                path = DELEGATION_DIR / f"{signal['id']}.json"
                signal["content"] = content
                path.write_text(json.dumps(signal, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception:
                pass


def get_delegation_results(agent: str | None = None) -> list[dict]:
    """Gibt abgeschlossene Delegationsergebnisse zurück."""
    results = []
    for f in sorted(DELEGATION_DIR.glob("*.json")):
        try:
            s = json.loads(f.read_text(encoding="utf-8"))
            if s.get("type") != "delegation":
                continue
            if s["content"].get("status") != "done":
                continue
            if agent and s["content"].get("to_agent") != agent:
                continue
            results.append(s)
        except Exception:
            continue
    return results

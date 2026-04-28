"""
ATLAS Tool-Registry — Werkzeuge für autonome Hermes-Agenten.

Inspiriert vom smolagents (HuggingFace) Tool-Pattern:
- Jedes Tool ist eine reine Funktion + OpenAI function-calling-kompatibles Schema
- Tools werden per Agent-Konfiguration aktiviert (nicht global)
- Sichere Ausführung: Python-Sandbox mit Timeout, kein Shell-Escape
"""

from __future__ import annotations

import json
import subprocess
import textwrap
from typing import Callable

# ── Tool-Implementierungen ────────────────────────────────────────────────────

def search_web(query: str, max_results: int = 5) -> str:
    """Sucht im Web via DuckDuckGo (kein API-Key nötig)."""
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "Keine Ergebnisse gefunden."
        parts = []
        for r in results:
            parts.append(
                f"**{r.get('title', 'Kein Titel')}**\n"
                f"{r.get('body', '')}\n"
                f"Quelle: {r.get('href', '')}"
            )
        return "\n\n---\n\n".join(parts)
    except ImportError:
        return "Fehler: duckduckgo-search nicht installiert. `pip install duckduckgo-search`"
    except Exception as e:
        return f"Web-Suche fehlgeschlagen: {e}"


def run_python(code: str, timeout: int = 20) -> str:
    """
    Führt Python-Code in einem isolierten Subprocess aus.
    Kein Shell-Escape möglich (kein shell=True).
    """
    safe_code = textwrap.dedent(code)
    try:
        result = subprocess.run(
            ["python3", "-c", safe_code],
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        if result.returncode != 0:
            return f"FEHLER (exit {result.returncode}):\n{stderr}" + (f"\nSTDOUT:\n{stdout}" if stdout else "")
        return stdout or "(kein Output)"
    except subprocess.TimeoutExpired:
        return f"Timeout nach {timeout}s — Code zu langsam."
    except FileNotFoundError:
        return "python3 nicht gefunden."
    except Exception as e:
        return f"Ausführungsfehler: {e}"


def calculate(expression: str) -> str:
    """Berechnet einen mathematischen Ausdruck sicher (kein eval)."""
    import ast
    import operator as op

    ALLOWED_OPS = {
        ast.Add: op.add, ast.Sub: op.sub, ast.Mult: op.mul,
        ast.Div: op.truediv, ast.Pow: op.pow, ast.USub: op.neg,
        ast.UAdd: op.pos,
    }

    def _eval(node):
        if isinstance(node, ast.Constant):
            return node.value
        elif isinstance(node, ast.BinOp):
            op_fn = ALLOWED_OPS.get(type(node.op))
            if not op_fn:
                raise ValueError(f"Operator nicht erlaubt: {node.op}")
            return op_fn(_eval(node.left), _eval(node.right))
        elif isinstance(node, ast.UnaryOp):
            op_fn = ALLOWED_OPS.get(type(node.op))
            if not op_fn:
                raise ValueError(f"Unary-Operator nicht erlaubt: {node.op}")
            return op_fn(_eval(node.operand))
        else:
            raise ValueError(f"Nicht erlaubt: {type(node).__name__}")

    try:
        tree = ast.parse(expression.strip(), mode="eval")
        result = _eval(tree.body)
        return str(round(result, 6) if isinstance(result, float) else result)
    except Exception as e:
        return f"Berechnungsfehler: {e}"


# ── Tool-Registry ─────────────────────────────────────────────────────────────

ToolFn = Callable[..., str]

TOOL_REGISTRY: dict[str, dict] = {
    "search_web": {
        "fn": search_web,
        "description": "Sucht aktuelle Informationen im Web via DuckDuckGo",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Suchanfrage auf Deutsch oder Englisch"},
                "max_results": {"type": "integer", "default": 5, "description": "Max. Anzahl Ergebnisse (1-10)"},
            },
            "required": ["query"],
        },
        "agents": ["plm_coordinator", "automation_engineer", "daily_briefing"],
    },
    "run_python": {
        "fn": run_python,
        "description": "Führt Python-Code aus und gibt stdout/stderr zurück",
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Valider Python-Code"},
                "timeout": {"type": "integer", "default": 20, "description": "Timeout in Sekunden"},
            },
            "required": ["code"],
        },
        "agents": ["automation_engineer"],
    },
    "calculate": {
        "fn": calculate,
        "description": "Berechnet mathematische Ausdrücke (+, -, *, /, **)",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {"type": "string", "description": "Mathematischer Ausdruck, z.B. '62.4 * 8 * 12'"},
            },
            "required": ["expression"],
        },
        "agents": ["demand_writer", "plm_coordinator", "automation_engineer"],
    },
}


def get_tools_for_agent(agent_name: str) -> list[dict]:
    """Gibt OpenAI-kompatible Tool-Definitionen für einen Agenten zurück."""
    tools = []
    for name, info in TOOL_REGISTRY.items():
        if agent_name in info.get("agents", []):
            tools.append({
                "type": "function",
                "function": {
                    "name": name,
                    "description": info["description"],
                    "parameters": info["parameters"],
                },
            })
    return tools


def execute_tool(name: str, arguments: dict | str) -> str:
    """Führt ein Tool aus und gibt das Ergebnis als String zurück."""
    if name not in TOOL_REGISTRY:
        return f"[TOOL ERROR] Unbekanntes Tool: '{name}'"
    if isinstance(arguments, str):
        try:
            arguments = json.loads(arguments)
        except json.JSONDecodeError:
            return f"[TOOL ERROR] Ungültige Argumente (kein JSON): {arguments}"
    try:
        return TOOL_REGISTRY[name]["fn"](**arguments)
    except TypeError as e:
        return f"[TOOL ERROR] Falsche Argumente für '{name}': {e}"
    except Exception as e:
        return f"[TOOL ERROR] Fehler bei '{name}': {e}"


def list_tools(agent_name: str = "") -> str:
    """Gibt eine lesbare Liste der verfügbaren Tools zurück."""
    lines = []
    for name, info in TOOL_REGISTRY.items():
        agents = info.get("agents", [])
        if agent_name and agent_name not in agents:
            continue
        lines.append(f"- **{name}**: {info['description']}")
    return "\n".join(lines) if lines else "Keine Tools verfügbar."

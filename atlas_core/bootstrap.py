"""
ATLAS Swarm Bootstrap — der Schwarm-Architekt.

Wenn der Schwarm leer ist, analysiert dieser Modul das eingebrachte Thema
und erstellt automatisch ein passendes Team von Agenten mit Persönlichkeiten.

Inspiriert von:
- DRTAG (Dynamic Real-Time Agent Generation)
- CrewAI Team-Building Pattern
- AutoGen AgentChat Gruppenkonzept

Zwei Wege:
  1. atlas run "Thema"   → Bootstrap greift automatisch wenn kein Agent existiert
  2. atlas init "Domain" → Expliziter Team-Aufbau für eine Domäne
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt
from rich.table import Table

from atlas_core.llm import chat
from atlas_core.spawner import spawn_agent

BASE_DIR = Path(__file__).resolve().parents[1]
KNOWLEDGE_FILE = BASE_DIR / "atlas_memory" / "global" / "atlas_knowledge.md"

console = Console()


# ── Domain-Analyse ────────────────────────────────────────────────────────────

def propose_team(topic: str) -> list[dict]:
    """
    Analysiert ein Thema via LLM und schlägt ein optimales Agenten-Team vor.
    Gibt eine Liste von Agent-Specs zurück:
      {name, description, personality, skills, focus}
    """
    prompt = f"""Du bist der ATLAS Swarm Architekt.
Analysiere das folgende Thema und entwirf ein optimales Team von autonomen KI-Agenten.

THEMA / DOMÄNE:
{topic}

Erstelle 3 bis 6 Agenten die sich sinnvoll ergänzen und die Domäne vollständig abdecken.
Jeder Agent soll eine klare Rolle, eine eigene Persönlichkeit und konkrete Fähigkeiten haben.

Antworte AUSSCHLIESSLICH mit einem validen JSON-Array. Kein Text davor oder danach.

Format:
[
  {{
    "name": "snake_case_name",
    "description": "Eine Satz: Was ist die Kernaufgabe dieses Agenten?",
    "personality": "Wie kommuniziert und denkt dieser Agent? (z.B. analytisch und präzise, kreativ und lösungsorientiert, empathisch und strukturiert)",
    "skills": ["Skill 1", "Skill 2", "Skill 3"],
    "focus": "Hauptfokus in 1-2 Wörtern"
  }}
]

Regeln:
- Namen in snake_case, aussagekräftig (z.B. "code_reviewer", "customer_success", "data_analyst")
- Keine Überlappungen — jeder Agent hat eine klare Nische
- Persönlichkeiten sollen sich unterscheiden und ergänzen
- Skills konkret und domänenspezifisch"""

    result = chat(
        [
            {
                "role": "system",
                "content": "Du bist ein KI-Architekt. Antworte NUR mit validem JSON-Array.",
            },
            {"role": "user", "content": prompt},
        ],
        agent_name="bootstrap",
    )

    # JSON aus der Antwort extrahieren (robust gegen Markdown-Wrapper)
    clean = result.strip()
    if clean.startswith("```"):
        clean = re.sub(r"^```(?:json)?\s*", "", clean)
        clean = re.sub(r"\s*```$", "", clean.strip())

    try:
        agents = json.loads(clean)
        if not isinstance(agents, list):
            raise ValueError("Kein Array")
        return [_validate_spec(a) for a in agents]
    except (json.JSONDecodeError, ValueError) as e:
        raise RuntimeError(
            f"Bootstrap-LLM hat kein valides JSON geliefert: {e}\n\nAntwort war:\n{result[:400]}"
        ) from e


def _validate_spec(spec: dict) -> dict:
    """Stellt sicher dass alle Pflichtfelder vorhanden und bereinigt sind."""
    name = re.sub(r"[^a-z0-9_]", "_", str(spec.get("name", "agent")).lower())[:40]
    name = name.strip("_") or "agent"
    skills = spec.get("skills", [])
    if isinstance(skills, str):
        skills = [s.strip() for s in skills.split(",")]
    return {
        "name": name,
        "description": str(spec.get("description", "Autonomer ATLAS-Agent"))[:200],
        "personality": str(spec.get("personality", "direkt und lösungsorientiert"))[:200],
        "skills": [str(s) for s in skills[:8]],
        "focus": str(spec.get("focus", "Allgemein"))[:50],
    }


# ── Preview & Bestätigung ─────────────────────────────────────────────────────

def _show_preview(agents: list[dict]) -> None:
    """Zeigt das vorgeschlagene Team als Rich-Tabelle."""
    table = Table(
        title="Vorgeschlagenes Agenten-Team",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("Name", style="cyan", min_width=20)
    table.add_column("Fokus", min_width=12)
    table.add_column("Persönlichkeit", max_width=35)
    table.add_column("Skills", max_width=40)

    for a in agents:
        table.add_row(
            a["name"],
            a["focus"],
            a["personality"][:60],
            ", ".join(a["skills"][:3]),
        )
    console.print(table)


# ── Knowledge Base aktualisieren ──────────────────────────────────────────────

def _update_knowledge(topic: str, agents: list[dict]) -> None:
    """Hängt Domain-Kontext an die globale Wissensbasis an."""
    existing = KNOWLEDGE_FILE.read_text(encoding="utf-8") if KNOWLEDGE_FILE.exists() else ""

    agent_lines = "\n".join(
        f"| `{a['name']}` | {a['focus']} | {a['description'][:60]} |"
        for a in agents
    )

    section = f"""
## Aktive Domäne

**Thema:** {topic}

### Agenten-Team

| Agent | Fokus | Aufgabe |
|-------|-------|---------|
{agent_lines}

"""
    # Alten Domain-Block ersetzen wenn vorhanden
    if "## Aktive Domäne" in existing:
        before = existing[: existing.index("## Aktive Domäne")]
        KNOWLEDGE_FILE.write_text(before.rstrip() + "\n" + section, encoding="utf-8")
    else:
        KNOWLEDGE_FILE.write_text(existing.rstrip() + "\n" + section, encoding="utf-8")


# ── Haupt-Einstiegspunkt ──────────────────────────────────────────────────────

def bootstrap_swarm(topic: str, auto: bool = False) -> list[str]:
    """
    Analysiert ein Thema, zeigt das vorgeschlagene Team und erstellt alle Agenten.

    Args:
        topic: Das Thema / die Domäne (Freitext)
        auto:  True = keine Bestätigung nötig

    Returns:
        Liste der erfolgreich gespawnten Agenten-Namen
    """
    console.print(Panel.fit(
        f"[bold]ATLAS Swarm Architekt[/bold]\n"
        f"[dim]Analysiere Domäne und entwerfe optimales Agenten-Team...[/dim]",
        border_style="yellow",
    ))

    with console.status("[yellow]Swarm-Architekt analysiert...[/yellow]", spinner="dots"):
        try:
            agents = propose_team(topic)
        except RuntimeError as e:
            console.print(f"[red]Bootstrap fehlgeschlagen:[/red] {e}")
            return []

    _show_preview(agents)

    if not auto:
        console.print()
        answer = Prompt.ask(
            "[yellow]Team so erstellen?[/yellow] [bold][Y/n/neu][/bold]",
            default="y",
        ).strip().lower()

        if answer in ("n", "nein", "no"):
            console.print("[dim]Bootstrap abgebrochen.[/dim]")
            return []

        if answer in ("neu", "new", "e", "edit"):
            new_topic = Prompt.ask("Neues Thema / Korrekturen")
            return bootstrap_swarm(new_topic, auto=auto)

    spawned: list[str] = []
    console.print()

    for spec in agents:
        console.print(f"  [dim]Spawne[/dim] [cyan]{spec['name']}[/cyan]...", end=" ")
        # Persönlichkeit in die Description einbetten damit spawner.py sie in system.md aufnimmt
        enriched_desc = f"{spec['description']} Persönlichkeit: {spec['personality']}"
        ok = spawn_agent(
            name=spec["name"],
            description=enriched_desc,
            skills=spec["skills"],
            confirmed=True,  # Bootstrap übernimmt die Bestätigung
        )
        if ok:
            console.print("[green]✓[/green]")
            spawned.append(spec["name"])
        else:
            console.print("[red]✗[/red]")

    if spawned:
        _update_knowledge(topic, agents)
        console.print(Panel.fit(
            f"[green]Schwarm bereit![/green] {len(spawned)} Agenten aktiv: "
            + ", ".join(f"[cyan]{n}[/cyan]" for n in spawned),
            border_style="green",
        ))

    return spawned

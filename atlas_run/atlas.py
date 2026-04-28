"""
ATLAS Swarm CLI — Haupteinstiegspunkt.

Verbesserungen:
- `run`: Live-Streaming mit Rich Markdown-Rendering
- `chat`: Interaktiver Multi-Turn Chat-Modus
- `history`: Letzte Läufe anzeigen und durchsuchen
- `tools`: Tool-Status und verfügbare Werkzeuge
- `vector`: Vector-Store Statistiken
- Delegations werden inline angezeigt
- Farbige Confidence-Anzeige
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.live import Live
from rich.markdown import Markdown
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt

from atlas_core.router import route_task, validate_input
from atlas_core.runtime import run_agent
from atlas_core.memory import save_history, auto_learn
from atlas_core.blackboard import (
    load_agent_registry, read_signals, read_learnings,
    get_signal_stats,
)
from atlas_core.delegation import process_delegations
from atlas_core.spawner import process_spawn_requests, spawn_agent
from atlas_core.schema import AgentResponse

app = typer.Typer(
    help="ATLAS Swarm — Dezentrales AIOS für PLM-Koordination und Schiffbau",
    no_args_is_help=True,
)
console = Console()

BASE_DIR = Path(__file__).resolve().parents[1]
HISTORY_DIR = BASE_DIR / "atlas_memory" / "history"


# ── Helpers ───────────────────────────────────────────────────────────────────

def _confidence_color(c: float) -> str:
    if c >= 0.8:
        return "green"
    if c >= 0.6:
        return "yellow"
    return "red"


def _show_response(response: AgentResponse, agent_name: str, streamed: bool = False):
    """Zeigt eine AgentResponse schön formatiert an."""
    if not streamed:
        console.print(Panel(
            Markdown(response.output),
            title=f"[bold cyan]{agent_name}[/bold cyan]",
            border_style="cyan",
        ))

    # Confidence
    conf_color = _confidence_color(response.confidence)
    console.print(
        f"  Confidence: [{conf_color}]{response.confidence:.0%}[/{conf_color}]"
        + (f"  |  Tags: {', '.join(response.tags[:5])}" if response.tags else "")
    )

    # Delegationen
    if response.delegations:
        console.print("\n[yellow]Delegation(en):[/yellow]")
        for d in response.delegations:
            console.print(f"  → [cyan]{d.to_agent}[/cyan]: {d.task}")

    # Wissenslücken
    if response.gaps:
        console.print("\n[red]Wissenslücken:[/red]")
        for g in response.gaps:
            console.print(f"  ⚠ {g.topic}" + (f": {g.reason}" if g.reason else ""))


def _run_task(
    text: str,
    agent: str = "auto",
    no_learn: bool = False,
    process_queue: bool = True,
) -> AgentResponse | None:
    """Führt einen Task aus (wiederverwendbar für run und chat)."""

    if process_queue:
        process_delegations()
        process_spawn_requests()

    valid, error = validate_input(text)
    if not valid:
        console.print(f"[red]Input ungültig:[/red] {error}")
        return None

    # Agent wählen
    if agent == "auto":
        with console.status("[dim]Router wählt Agenten...[/dim]", spinner="dots"):
            selected_agent, spawn_needed = route_task(text)
        if spawn_needed:
            console.print("[yellow]⚡ Kein passender Agent — Spawn-Anfrage eingereiht.[/yellow]")
    else:
        selected_agent = agent

    console.print(f"[dim]Agent: [cyan]{selected_agent}[/cyan][/dim]")

    # Streaming-Output
    streamed_text: list[str] = []
    panel_started = False

    def stream_cb(chunk: str):
        nonlocal panel_started
        if not panel_started:
            console.print(f"\n[bold cyan]{selected_agent}[/bold cyan]")
            console.rule(style="cyan dim")
            panel_started = True
        console.print(chunk, end="", highlight=False)
        streamed_text.append(chunk)

    try:
        response = run_agent(selected_agent, text, stream_callback=stream_cb)
    except Exception as e:
        console.print(f"\n[red]Fehler beim Ausführen von '{selected_agent}':[/red] {e}")
        return None

    # Newline nach Streaming
    if streamed_text:
        console.print()
        console.rule(style="cyan dim")

    _show_response(response, selected_agent, streamed=bool(streamed_text))

    # History
    saved = save_history(selected_agent, text, response.output)
    console.print(f"[dim]  ↳ {saved.name}[/dim]")

    # Auto-Lernen
    if not no_learn:
        try:
            auto_learn(selected_agent, text, response.output)
        except Exception:
            pass

    return response


# ── Commands ──────────────────────────────────────────────────────────────────

@app.command()
def run(
    text: str = typer.Argument(..., help="Dein Input für den Schwarm"),
    agent: str = typer.Option("auto", "--agent", "-a", help="Agent: auto oder spezifischer Name"),
    no_learn: bool = typer.Option(False, "--no-learn", help="Kein automatisches Lernen"),
    no_queue: bool = typer.Option(False, "--no-queue", help="Delegations-Queue nicht verarbeiten"),
):
    """Führt einen Task im ATLAS-Schwarm aus (mit Live-Streaming)."""
    _run_task(text, agent=agent, no_learn=no_learn, process_queue=not no_queue)


@app.command()
def chat(
    agent: str = typer.Option("auto", "--agent", "-a", help="Agent (auto = automatisch)"),
    no_learn: bool = typer.Option(False, "--no-learn", help="Kein automatisches Lernen"),
):
    """Interaktiver Multi-Turn Chat mit dem ATLAS-Schwarm (Ctrl+C zum Beenden)."""
    console.print(Panel.fit(
        "[bold]ATLAS Swarm Chat[/bold]\n"
        "[dim]Ctrl+C oder 'exit' zum Beenden | ':agent <name>' zum Wechseln | ':status' für Status[/dim]",
        border_style="cyan",
    ))

    current_agent = agent
    turn = 0

    while True:
        try:
            user_input = Prompt.ask(
                f"\n[bold green]Du[/bold green] [dim](Agent: {current_agent})[/dim]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Chat beendet.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", "bye", ":exit"):
            console.print("[dim]Chat beendet.[/dim]")
            break
        if user_input.startswith(":agent "):
            new_agent = user_input[7:].strip()
            current_agent = new_agent
            console.print(f"[yellow]Agent gewechselt zu: {current_agent}[/yellow]")
            continue
        if user_input == ":status":
            _print_status()
            continue
        if user_input == ":agents":
            _print_agents()
            continue

        turn += 1
        _run_task(
            user_input,
            agent=current_agent,
            no_learn=no_learn,
            process_queue=(turn == 1),  # Queue nur beim ersten Turn verarbeiten
        )


@app.command()
def status():
    """Zeigt den aktuellen Schwarm-Status."""
    _print_status()


def _print_status():
    registry = load_agent_registry()
    bb_stats = get_signal_stats()

    # Agenten-Tabelle
    table = Table(title="ATLAS Schwarm", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="cyan", min_width=20)
    table.add_column("Skills", max_width=50)
    table.add_column("Status", justify="center")

    for name, info in registry.items():
        status_str = "[green]aktiv[/green]" if info.get("active") else "[red]inaktiv[/red]"
        skills = ", ".join(info.get("skills", [])[:3])
        table.add_row(name, skills, status_str)

    console.print(table)

    # Blackboard-Stats
    console.print(
        f"\n[bold]Blackboard:[/bold] "
        f"{bb_stats['active']} aktive Signale | "
        f"{bb_stats['consumed']} verbraucht | "
        f"{bb_stats.get('expired', 0)} abgelaufen"
    )
    by_type = bb_stats.get("by_type", {})
    if by_type:
        type_str = " · ".join(f"{t}={n}" for t, n in by_type.items())
        console.print(f"  Typen: [dim]{type_str}[/dim]")

    # Lernpool
    all_learnings = read_learnings(limit=9999)
    console.print(f"[bold]Lernpool:[/bold] {len(all_learnings)} globale Erkenntnisse")


def _print_agents():
    registry = load_agent_registry()
    for name, info in registry.items():
        if info.get("active"):
            console.print(f"  [cyan]{name}[/cyan]: {info.get('description', '')[:60]}")


@app.command()
def spawn(
    name: str = typer.Argument(..., help="Agent-Name (snake_case)"),
    description: str = typer.Option(..., "--desc", "-d", help="Was kann dieser Agent?"),
    skills: str = typer.Option("", "--skills", "-s", help="Komma-getrennte Skills"),
    auto: bool = typer.Option(False, "--auto", help="Ohne Bestätigung spawnen"),
):
    """Spawnt einen neuen Agenten manuell."""
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    spawn_agent(name=name, description=description, skills=skill_list, confirmed=auto)


@app.command()
def learn():
    """Zeigt globale Erkenntnisse aus dem Schwarm-Lernpool."""
    learnings = read_learnings(limit=30)
    if not learnings:
        console.print("[dim]Noch keine Erkenntnisse im Pool.[/dim]")
        return

    table = Table(title="Schwarm-Erkenntnisse", show_header=True, header_style="bold")
    table.add_column("Agent", style="cyan", min_width=15)
    table.add_column("Regel", max_width=70)
    table.add_column("Datum", style="dim", min_width=10)

    for l in reversed(learnings[-20:]):
        ts = l.get("timestamp", "")[:10]
        table.add_row(l.get("agent", "?"), l.get("rule", "")[:70], ts)

    console.print(table)


@app.command()
def history(
    limit: int = typer.Option(10, "--limit", "-n", help="Anzahl anzuzeigender Einträge"),
    agent: str = typer.Option("", "--agent", "-a", help="Filter nach Agent"),
):
    """Zeigt vergangene Läufe aus der History."""
    HISTORY_DIR.mkdir(parents=True, exist_ok=True)
    files = sorted(HISTORY_DIR.glob("*.json"), reverse=True)

    entries = []
    for f in files:
        try:
            e = json.loads(f.read_text(encoding="utf-8"))
            if agent and e.get("agent") != agent:
                continue
            entries.append(e)
            if len(entries) >= limit:
                break
        except Exception:
            continue

    if not entries:
        console.print("[dim]Keine History-Einträge gefunden.[/dim]")
        return

    table = Table(title="ATLAS History", show_header=True, header_style="bold")
    table.add_column("Zeit", style="dim", min_width=19)
    table.add_column("Agent", style="cyan", min_width=15)
    table.add_column("Input", max_width=50)
    table.add_column("Output (Vorschau)", max_width=60)

    for e in entries:
        ts = e.get("timestamp", "")[:19]
        ag = e.get("agent", "?")
        inp = e.get("input", "")[:50]
        out = e.get("output", "")[:60].replace("\n", " ")
        table.add_row(ts, ag, inp, out)

    console.print(table)


@app.command()
def tools():
    """Zeigt verfügbare Tools pro Agent."""
    from atlas_core.tools import TOOL_REGISTRY
    table = Table(title="ATLAS Tools", show_header=True, header_style="bold")
    table.add_column("Tool", style="cyan")
    table.add_column("Beschreibung")
    table.add_column("Agenten")

    for name, info in TOOL_REGISTRY.items():
        agents = ", ".join(info.get("agents", []))
        table.add_row(name, info["description"], agents)

    console.print(table)


@app.command()
def vector():
    """Zeigt Vector-Store Statistiken."""
    from atlas_core import vector_memory as vm
    stats = vm.vector_stats()

    if not stats.get("available"):
        console.print(f"[yellow]Vector Store nicht verfügbar:[/yellow] {stats.get('reason', 'chromadb fehlt')}")
        console.print("[dim]Installieren: pip install chromadb[/dim]")
        return

    console.print(Panel.fit(
        f"[green]ChromaDB aktiv[/green]\n"
        f"Globale Erkenntnisse: [cyan]{stats.get('global_learnings', 0)}[/cyan]\n"
        f"Session-History: [cyan]{stats.get('session_history', 0)}[/cyan]",
        title="Vector Memory",
        border_style="green",
    ))


if __name__ == "__main__":
    app()

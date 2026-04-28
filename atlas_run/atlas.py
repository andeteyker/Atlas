"""
ATLAS Swarm CLI — Haupteinstiegspunkt.
"""

import typer
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from atlas_core.router import route_task, validate_input
from atlas_core.runtime import run_agent
from atlas_core.memory import save_history, auto_learn
from atlas_core.blackboard import load_agent_registry, read_signals, read_learnings
from atlas_core.delegation import process_delegations
from atlas_core.spawner import process_spawn_requests, spawn_agent

app = typer.Typer(help="ATLAS Swarm — Dezentrales AIOS für PLM und Schiffbau")
console = Console()


@app.command()
def run(
    text: str = typer.Argument(..., help="Dein Input für den Schwarm"),
    agent: str = typer.Option("auto", help="Agent: auto oder spezifischer Name"),
    no_learn: bool = typer.Option(False, "--no-learn", help="Kein automatisches Lernen"),
    process_queue: bool = typer.Option(True, "--queue/--no-queue", help="Delegations-Queue verarbeiten"),
):
    """Führt einen Task im ATLAS-Schwarm aus."""

    # Delegations-Queue verarbeiten (async Ergebnisse vom letzten Lauf)
    if process_queue:
        process_delegations()
        process_spawn_requests()

    # Input validieren
    valid, error = validate_input(text)
    if not valid:
        console.print(f"[red]Input ungültig:[/red] {error}")
        raise typer.Exit(1)

    # Agent wählen
    if agent == "auto":
        selected_agent, spawn_needed = route_task(text)
        if spawn_needed:
            console.print("[yellow]Kein passender Agent — Spawn-Anfrage eingereiht.[/yellow]")
    else:
        selected_agent = agent

    console.print(Panel.fit(f"[bold]ATLAS Agent:[/bold] {selected_agent}", title="ATLAS Schwarm"))

    # Agent ausführen
    try:
        output = run_agent(selected_agent, text)
    except Exception as e:
        console.print(f"[red]Fehler:[/red] {e}")
        raise typer.Exit(1)

    console.print(Panel(output, title=f"OUTPUT · {selected_agent}"))

    # History speichern
    saved = save_history(selected_agent, text, output)
    console.print(f"[dim]History: {saved}[/dim]")

    # Automatisch lernen
    if not no_learn:
        auto_learn(selected_agent, text, output)
        console.print("[green]✓[/green] Schwarm-Lernschritt abgeschlossen")


@app.command()
def status():
    """Zeigt den aktuellen Schwarm-Status."""
    registry = load_agent_registry()
    signals = read_signals(unconsumed_only=True)
    learnings = read_learnings(limit=5)

    table = Table(title="ATLAS Schwarm", show_header=True, header_style="bold")
    table.add_column("Agent", style="cyan")
    table.add_column("Skills")
    table.add_column("Status")

    for name, info in registry.items():
        status_str = "[green]aktiv[/green]" if info.get("active") else "[red]inaktiv[/red]"
        skills_str = ", ".join(info.get("skills", [])[:3])
        table.add_row(name, skills_str, status_str)

    console.print(table)
    console.print(f"\n[yellow]{len(signals)}[/yellow] offene Blackboard-Signale")
    console.print(f"[blue]{len(read_learnings(limit=9999))}[/blue] globale Erkenntnisse im Pool\n")

    if learnings:
        console.print("[bold]Letzte Erkenntnisse:[/bold]")
        for l in reversed(learnings):
            console.print(f"  [{l['agent']}] {l['rule'][:80]}")


@app.command()
def spawn(
    name: str = typer.Argument(..., help="Agent-Name (snake_case)"),
    description: str = typer.Option(..., "--desc", help="Was kann dieser Agent?"),
    skills: str = typer.Option("", "--skills", help="Komma-getrennte Skills"),
    auto: bool = typer.Option(False, "--auto", help="Ohne Bestätigung spawnen"),
):
    """Spawnt einen neuen Agenten manuell."""
    skill_list = [s.strip() for s in skills.split(",") if s.strip()]
    spawn_agent(name=name, description=description, skills=skill_list, confirmed=auto)


@app.command()
def learn():
    """Verarbeitet Blackboard-Signale und zeigt globale Erkenntnisse."""
    signals = read_signals(signal_type="learning")
    console.print(f"[blue]{len(signals)}[/blue] neue Lern-Signale auf dem Blackboard")
    learnings = read_learnings(limit=20)
    for l in learnings:
        console.print(f"  [{l['agent']}] {l['rule']}")


if __name__ == "__main__":
    app()

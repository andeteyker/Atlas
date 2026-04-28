"""
ATLAS Swarm CLI — Haupteinstiegspunkt.

Commands:
  run    — Task ausführen (Bootstrap wenn Schwarm leer)
  init   — Schwarm für eine Domäne initialisieren
  chat   — Interaktiver Multi-Turn Chat
  status — Schwarm-Status
  spawn  — Einzelnen Agenten manuell hinzufügen
  learn  — Globale Erkenntnisse anzeigen
  history — Vergangene Läufe
  tools  — Verfügbare Tools
  vector — Vector-Store Statistiken
"""

from __future__ import annotations

import json
from pathlib import Path

import typer
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.table import Table

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
    help="ATLAS Swarm — Domänen-agnostisches dezentrales AIOS",
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
    if not streamed:
        console.print(Panel(
            Markdown(response.output),
            title=f"[bold cyan]{agent_name}[/bold cyan]",
            border_style="cyan",
        ))

    conf_color = _confidence_color(response.confidence)
    meta = f"  Confidence: [{conf_color}]{response.confidence:.0%}[/{conf_color}]"
    if response.tags:
        meta += f"  |  Tags: {', '.join(response.tags[:5])}"
    console.print(meta)

    if response.delegations:
        console.print("\n[yellow]Delegationen:[/yellow]")
        for d in response.delegations:
            console.print(f"  → [cyan]{d.to_agent}[/cyan]: {d.task}")

    if response.gaps:
        console.print("\n[red]Wissenslücken:[/red]")
        for g in response.gaps:
            console.print(f"  ⚠ {g.topic}" + (f": {g.reason}" if g.reason else ""))


def _ensure_swarm(text: str, auto: bool = False) -> bool:
    """
    Prüft ob Agenten vorhanden sind.
    Wenn nicht: Bootstrap-Flow starten.
    Gibt True zurück wenn der Schwarm bereit ist.
    """
    from atlas_core.bootstrap import bootstrap_swarm

    registry = load_agent_registry()
    if registry:
        return True

    console.print(Panel.fit(
        "[bold yellow]Der ATLAS-Schwarm ist leer.[/bold yellow]\n"
        "[dim]Kein Agent ist registriert. Der Swarm-Architekt analysiert dein Thema\n"
        "und erstellt automatisch ein passendes Agenten-Team.[/dim]",
        border_style="yellow",
    ))
    console.print()

    spawned = bootstrap_swarm(text, auto=auto)
    return len(spawned) > 0


def _run_task(
    text: str,
    agent: str = "auto",
    no_learn: bool = False,
    process_queue: bool = True,
    auto_bootstrap: bool = False,
) -> AgentResponse | None:

    if process_queue:
        process_delegations()
        process_spawn_requests()

    valid, error = validate_input(text)
    if not valid:
        console.print(f"[red]Input ungültig:[/red] {error}")
        return None

    # Agenten wählen — Bootstrap wenn leer
    if agent == "auto":
        try:
            with console.status("[dim]Router wählt Agenten...[/dim]", spinner="dots"):
                selected_agent, spawn_needed = route_task(text)
        except RuntimeError as e:
            if "ATLAS_EMPTY_SWARM" in str(e):
                if not _ensure_swarm(text, auto=auto_bootstrap):
                    return None
                # Nochmal versuchen nach Bootstrap
                try:
                    selected_agent, spawn_needed = route_task(text)
                except RuntimeError:
                    console.print("[red]Routing nach Bootstrap fehlgeschlagen.[/red]")
                    return None
            else:
                console.print(f"[red]Router-Fehler:[/red] {e}")
                return None

        if spawn_needed:
            console.print("[yellow]⚡ Spawn-Anfrage eingereiht für neuen Agenten.[/yellow]")
    else:
        selected_agent = agent

    console.print(f"[dim]Agent: [cyan]{selected_agent}[/cyan][/dim]")

    # Streaming Output
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
        console.print(f"\n[red]Fehler bei '{selected_agent}':[/red] {e}")
        return None

    if streamed_text:
        console.print()
        console.rule(style="cyan dim")

    _show_response(response, selected_agent, streamed=bool(streamed_text))

    saved = save_history(selected_agent, text, response.output)
    console.print(f"[dim]  ↳ {saved.name}[/dim]")

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
    agent: str = typer.Option("auto", "--agent", "-a", help="Agent: auto oder Name"),
    no_learn: bool = typer.Option(False, "--no-learn", help="Kein automatisches Lernen"),
    no_queue: bool = typer.Option(False, "--no-queue", help="Delegations-Queue nicht verarbeiten"),
    auto: bool = typer.Option(False, "--auto", help="Bootstrap ohne Bestätigung"),
):
    """
    Führt einen Task im ATLAS-Schwarm aus.

    Wenn noch kein Agent existiert, analysiert der Swarm-Architekt
    dein Thema und erstellt automatisch ein passendes Agenten-Team.
    """
    _run_task(text, agent=agent, no_learn=no_learn, process_queue=not no_queue, auto_bootstrap=auto)


@app.command()
def init(
    topic: str = typer.Argument(..., help="Domäne oder Thema für den Schwarm"),
    auto: bool = typer.Option(False, "--auto", help="Ohne Bestätigung spawnen"),
):
    """
    Initialisiert den Schwarm für eine neue Domäne.

    Der Swarm-Architekt analysiert das Thema und erstellt ein
    optimales Agenten-Team mit passenden Persönlichkeiten.

    Beispiele:
      atlas init "Software Engineering Team"
      atlas init "E-Commerce Customer Support" --auto
      atlas init "Medizinische Forschung und Literaturrecherche"
    """
    from atlas_core.bootstrap import bootstrap_swarm

    registry = load_agent_registry()
    if registry:
        console.print(
            f"[yellow]Der Schwarm hat bereits {len(registry)} Agenten.[/yellow]\n"
            "[dim]Bestehende Agenten bleiben erhalten. Neue werden hinzugefügt.[/dim]"
        )
        console.print()

    bootstrap_swarm(topic, auto=auto)


@app.command()
def chat(
    agent: str = typer.Option("auto", "--agent", "-a", help="Agent (auto = automatisch)"),
    no_learn: bool = typer.Option(False, "--no-learn", help="Kein automatisches Lernen"),
    auto: bool = typer.Option(False, "--auto", help="Bootstrap ohne Bestätigung"),
):
    """
    Interaktiver Multi-Turn Chat mit dem ATLAS-Schwarm.

    Sonderbefehle im Chat:
      :agent <name>  — Agent wechseln
      :status        — Schwarm-Status anzeigen
      :agents        — Alle Agenten auflisten
      exit           — Chat beenden
    """
    console.print(Panel.fit(
        "[bold]ATLAS Swarm Chat[/bold]\n"
        "[dim]Ctrl+C oder 'exit' zum Beenden | ':agent <name>' | ':status' | ':agents'[/dim]",
        border_style="cyan",
    ))

    current_agent = agent
    turn = 0

    while True:
        try:
            user_input = Prompt.ask(
                f"\n[bold green]Du[/bold green] [dim]({current_agent})[/dim]"
            ).strip()
        except (KeyboardInterrupt, EOFError):
            console.print("\n[dim]Chat beendet.[/dim]")
            break

        if not user_input:
            continue
        if user_input.lower() in ("exit", "quit", ":exit", "bye"):
            console.print("[dim]Chat beendet.[/dim]")
            break
        if user_input.startswith(":agent "):
            current_agent = user_input[7:].strip()
            console.print(f"[yellow]Agent → {current_agent}[/yellow]")
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
            process_queue=(turn == 1),
            auto_bootstrap=auto,
        )


@app.command()
def status():
    """Zeigt den aktuellen Schwarm-Status."""
    _print_status()


def _print_status():
    registry = load_agent_registry()

    if not registry:
        console.print(Panel.fit(
            "[yellow]Schwarm ist leer[/yellow]\n"
            "[dim]Starte mit:[/dim]\n"
            "  [cyan]atlas init \"Deine Domäne\"[/cyan]  — Team automatisch erstellen\n"
            "  [cyan]atlas run \"Deine Frage\"[/cyan]    — Direkt starten (Bootstrap greift automatisch)",
            border_style="yellow",
            title="ATLAS Swarm",
        ))
        return

    table = Table(title="ATLAS Schwarm", show_header=True, header_style="bold cyan")
    table.add_column("Agent", style="cyan", min_width=20)
    table.add_column("Beschreibung", max_width=50)
    table.add_column("Status", justify="center")

    for name, info in registry.items():
        status_str = "[green]aktiv[/green]" if info.get("active") else "[red]inaktiv[/red]"
        desc = info.get("description", "")[:50]
        table.add_row(name, desc, status_str)

    console.print(table)

    bb = get_signal_stats()
    console.print(
        f"\n[bold]Blackboard:[/bold] {bb['active']} aktiv | {bb['consumed']} verbraucht"
    )
    console.print(f"[bold]Lernpool:[/bold] {len(read_learnings(limit=9999))} Erkenntnisse")


def _print_agents():
    registry = load_agent_registry()
    if not registry:
        console.print("[dim]Keine Agenten registriert.[/dim]")
        return
    for name, info in registry.items():
        if info.get("active"):
            console.print(f"  [cyan]{name}[/cyan]: {info.get('description', '')[:70]}")


@app.command()
def spawn(
    name: str = typer.Argument(..., help="Agent-Name (snake_case)"),
    description: str = typer.Option(..., "--desc", "-d", help="Was kann dieser Agent?"),
    skills: str = typer.Option("", "--skills", "-s", help="Komma-getrennte Skills"),
    auto: bool = typer.Option(False, "--auto", help="Ohne Bestätigung spawnen"),
):
    """
    Fügt einen einzelnen Agenten manuell zum Schwarm hinzu.

    Beispiel:
      atlas spawn "code_reviewer" --desc "Überprüft Code auf Qualität und Bugs" --skills "Python,Code Review,Testing"
    """
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
    limit: int = typer.Option(10, "--limit", "-n", help="Anzahl Einträge"),
    agent: str = typer.Option("", "--agent", "-a", help="Filter nach Agent"),
):
    """Zeigt vergangene Läufe."""
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
        console.print("[dim]Keine History-Einträge.[/dim]")
        return

    table = Table(title="ATLAS History", show_header=True, header_style="bold")
    table.add_column("Zeit", style="dim", min_width=19)
    table.add_column("Agent", style="cyan", min_width=15)
    table.add_column("Input", max_width=45)
    table.add_column("Output", max_width=55)

    for e in entries:
        table.add_row(
            e.get("timestamp", "")[:19],
            e.get("agent", "?"),
            e.get("input", "")[:45],
            e.get("output", "")[:55].replace("\n", " "),
        )

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
        table.add_row(name, info["description"], ", ".join(info.get("agents", [])))

    console.print(table)
    console.print(
        "\n[dim]Tools werden automatisch für Agenten aktiviert die dem entsprechenden Agentennamen entsprechen.[/dim]"
    )


@app.command()
def vector():
    """Zeigt Vector-Store Statistiken (ChromaDB)."""
    from atlas_core import vector_memory as vm
    stats = vm.vector_stats()

    if not stats.get("available"):
        console.print(
            f"[yellow]Vector Store nicht verfügbar:[/yellow] {stats.get('reason', 'chromadb fehlt')}\n"
            "[dim]pip install chromadb[/dim]"
        )
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

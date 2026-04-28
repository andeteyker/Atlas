"""
ATLAS CLI — Agent Command Interface
Textual TUI Launcher für AI-Agenten und Tools.

Design: Dunkel-Navy Hintergrund · Cyan/Hellblau Akzente · Unicode-Symbole
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal, Vertical
from textual.reactive import reactive
from textual.widgets import Footer, Input, Label, ListItem, ListView, RichLog, Static

BASE_DIR = Path(__file__).resolve().parent
COMMANDS_FILE = BASE_DIR / "commands.yaml"


# ── Datenmodelle ──────────────────────────────────────────────────────────────

@dataclass
class Command:
    name: str
    cmd: str
    args: list[str]
    description: str
    icon: str = "○"
    category: str = ""
    prompt: bool = False
    prompt_label: str = "Eingabe"
    env: dict = field(default_factory=dict)

    @property
    def is_available(self) -> bool:
        return shutil.which(self.cmd) is not None or self.cmd == "python"

    @property
    def full_cmd(self) -> str:
        parts = [self.cmd] + self.args
        return " ".join(parts)


@dataclass
class Category:
    name: str
    icon: str
    commands: list[Command]


def load_commands(path: Path = COMMANDS_FILE) -> list[Category]:
    if not path.exists():
        return []
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    categories = []
    for cat in raw.get("categories", []):
        cmds = []
        for c in cat.get("commands", []):
            cmds.append(Command(
                name=c.get("name", "Unnamed"),
                cmd=c.get("cmd", ""),
                args=c.get("args", []),
                description=c.get("description", ""),
                icon=c.get("icon", "○"),
                category=cat.get("name", ""),
                prompt=c.get("prompt", False),
                prompt_label=c.get("prompt_label", "Eingabe"),
                env=c.get("env", {}),
            ))
        categories.append(Category(
            name=cat.get("name", ""),
            icon=cat.get("icon", "○"),
            commands=cmds,
        ))
    return categories


# ── Textual CSS ───────────────────────────────────────────────────────────────

CSS = """
/* ── Basis ─────────────────────────────────────────────────────────────── */
Screen {
    background: #080d1a;
    layers: base overlay;
}

/* ── Header-Block ───────────────────────────────────────────────────────── */
#header {
    height: 7;
    background: #080d1a;
    border-bottom: solid #0d3060;
    padding: 0 3;
    content-align: center middle;
    layer: base;
}

#title-row {
    height: 3;
    align: center middle;
}

#title-icon {
    color: #00ccff;
    text-style: bold;
    width: auto;
    padding: 0 1;
}

#title-text {
    color: #00ddff;
    text-style: bold;
    width: auto;
    padding: 0 1;
}

#subtitle {
    color: #3a7a9c;
    text-align: center;
    height: 1;
    padding: 0 4;
}

#divider {
    color: #0d3060;
    text-align: center;
    height: 1;
}

/* ── Body ───────────────────────────────────────────────────────────────── */
#body {
    height: 1fr;
    overflow-y: auto;
    padding: 0 2;
}

/* ── Kategorie ──────────────────────────────────────────────────────────── */
.cat-header {
    color: #0099bb;
    text-style: bold;
    padding: 1 1 0 1;
    height: 2;
}

.cat-icon {
    color: #00ccff;
    width: auto;
}

/* ── Command-Liste ──────────────────────────────────────────────────────── */
ListView {
    background: #080d1a;
    border: round #0d2a4a;
    height: auto;
    margin: 0 1 1 1;
    scrollbar-size: 1 1;
    scrollbar-color: #0d3060;
    scrollbar-color-hover: #0099bb;
    scrollbar-background: #080d1a;
}

ListItem {
    background: #080d1a;
    height: 1;
    padding: 0 1;
}

ListItem:hover {
    background: #0a2240;
}

ListItem.--highlight {
    background: #0d3060;
}

.item-icon {
    color: #006688;
    width: 3;
}

.item-icon-active {
    color: #00ccff;
    width: 3;
}

.item-name {
    color: #a8d8f0;
    width: 24;
}

.item-name-selected {
    color: #00e5ff;
    text-style: bold;
    width: 24;
}

.item-name-unavail {
    color: #3a5060;
    width: 24;
}

.item-desc {
    color: #2a6080;
    width: 1fr;
}

.item-desc-selected {
    color: #3a90b0;
    width: 1fr;
}

.item-tag-avail {
    color: #006644;
    width: 8;
    text-align: right;
}

.item-tag-unavail {
    color: #442222;
    width: 8;
    text-align: right;
}

.empty-cat {
    color: #1a3a50;
    padding: 0 2;
    height: 1;
}

/* ── Chat-Leiste (integriert, immer sichtbar) ───────────────────────────── */
#chat-area {
    height: 8;
    background: #050a15;
    border-top: solid #0d3060;
}

#chat-log {
    height: 5;
    background: #050a15;
    padding: 0 3;
    border: none;
    scrollbar-color: #0d3060;
    scrollbar-background: #050a15;
    scrollbar-size: 1 1;
}

#slash-popup {
    height: auto;
    max-height: 6;
    background: #0a1a2e;
    border: round #0d3060;
    margin: 0 3;
    display: none;
    layer: overlay;
}

#slash-popup.visible {
    display: block;
}

#slash-popup ListView {
    background: #0a1a2e;
    border: none;
    margin: 0;
    height: auto;
}

#slash-popup ListItem {
    height: 1;
    padding: 0 1;
    background: #0a1a2e;
    color: #5aaad0;
}

#slash-popup ListItem.--highlight {
    background: #0d3060;
    color: #00e5ff;
}

#chat-input-row {
    height: 3;
    background: #050a15;
    border-top: solid #0a2030;
    padding: 0 2;
    align: left middle;
}

#chat-agent-badge {
    color: #00ccff;
    background: #0d2240;
    border: solid #0d3060;
    width: auto;
    padding: 0 2;
    content-align: left middle;
}

#chat-input {
    width: 1fr;
    background: #0a1a2a;
    color: #c8e8ff;
    border: solid #0d3060;
    margin: 0 1;
}

#chat-input:focus {
    border: solid #00ccff;
}

#chat-send-hint {
    color: #0d3a50;
    width: auto;
    padding: 0 1;
    content-align: right middle;
}

/* ── Footer ─────────────────────────────────────────────────────────────── */
#footer-bar {
    background: #050a15;
    color: #0d5070;
    height: 1;
    border-top: solid #0a2030;
    padding: 0 3;
    content-align: left middle;
}

#chat-log {
    height: 1fr;
    background: #080d1a;
    padding: 1 3;
    scrollbar-color: #0d3060;
    scrollbar-background: #080d1a;
    border: none;
}

#chat-input-row {
    height: 3;
    background: #050a15;
    border-top: solid #0d2a4a;
    padding: 0 2;
    align: left middle;
}

#chat-prompt-icon {
    color: #0099bb;
    width: 4;
    content-align: left middle;
}

#chat-input {
    width: 1fr;
    background: #0a1a2a;
    color: #c8e8ff;
    border: solid #0d3060;
}

#chat-input:focus {
    border: solid #00ccff;
}

#chat-status {
    color: #1a5060;
    width: 12;
    content-align: right middle;
    padding: 0 1;
}

#chat-footer-bar {
    background: #050a15;
    color: #0d5070;
    height: 1;
    border-top: solid #0a2030;
    padding: 0 3;
    content-align: left middle;
}
"""


# ── Widgets ───────────────────────────────────────────────────────────────────

class CommandItem(ListItem):
    """Ein einzelner Command-Eintrag in der Liste."""

    def __init__(self, command: Command, is_selected: bool = False) -> None:
        super().__init__()
        self.command = command
        self._is_selected = is_selected

    def compose(self) -> ComposeResult:
        avail = self.command.is_available
        selected = self._is_selected

        if not avail:
            icon_cls = "item-icon"
            name_cls = "item-name-unavail"
            desc_cls = "item-desc"
            tag = " ✗ n/a "
            tag_cls = "item-tag-unavail"
            icon = "○"
        elif selected:
            icon_cls = "item-icon-active"
            name_cls = "item-name-selected"
            desc_cls = "item-desc-selected"
            tag = "  ▶ run"
            tag_cls = "item-tag-avail"
            icon = self.command.icon or "▶"
        else:
            icon_cls = "item-icon"
            name_cls = "item-name"
            desc_cls = "item-desc"
            tag = "      "
            tag_cls = "item-tag-avail"
            icon = self.command.icon or "○"

        with Horizontal():
            yield Label(f" {icon} ", classes=icon_cls)
            yield Label(self.command.name, classes=name_cls)
            yield Label(self.command.description[:55], classes=desc_cls)
            yield Label(tag, classes=tag_cls)


# ── Haupt-App ─────────────────────────────────────────────────────────────────

class AtlasLauncher(App[Optional[tuple[Command, str]]]):
    """
    ATLAS CLI — Agent Command Interface.
    Returns (Command, extra_input) on launch, None on quit.
    """

    CSS = CSS

    BINDINGS = [
        Binding("q", "quit_app", "Quit", show=True),
        Binding("e", "edit_config", "Edit Config", show=True),
        Binding("r", "reload", "Reload", show=True),
        Binding("tab", "focus_chat", "Chat", show=True),
        Binding("escape", "focus_list", "Liste", show=False),
    ]

    _all_commands: list[Command] = []
    _selected_idx: reactive[int] = reactive(0)
    _current_agent: str = "auto"

    # Verfügbare Slash-Commands
    SLASH_COMMANDS: list[tuple[str, str]] = [
        ("/run",    "Task im Schwarm ausführen"),
        ("/init",   "Schwarm für Domäne initialisieren"),
        ("/status", "Schwarm-Status anzeigen"),
        ("/spawn",  "Neuen Agenten hinzufügen"),
        ("/learn",  "Erkenntnisse anzeigen"),
        ("/history","Letzte Läufe anzeigen"),
        ("/agent",  "Agent wechseln  z.B. /agent plm_coordinator"),
        ("/clear",  "Chat-Log leeren"),
        ("/help",   "Alle Befehle anzeigen"),
    ]

    def __init__(self):
        super().__init__()
        self._categories: list[Category] = []
        self._list_views: list[ListView] = []
        self._reload_commands()

    def _reload_commands(self):
        self._categories = load_commands()
        self._all_commands = [cmd for cat in self._categories for cmd in cat.commands]

    # ── Layout ────────────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        # Header
        with Container(id="header"):
            with Horizontal(id="title-row"):
                yield Label("◈", id="title-icon")
                yield Label("A T L A S   A I O S", id="title-text")
            yield Label("Agent Command Interface", id="subtitle")
            yield Label("─" * 52, id="divider")

        # Body — Command-Listen
        with Container(id="body"):
            for cat in self._categories:
                yield Label(f"  {cat.icon}  {cat.name}", classes="cat-header")
                lv_id = f"lv-{_safe_id(cat.name)}"
                lv = ListView(id=lv_id)
                self._list_views.append(lv)
                with lv:
                    if not cat.commands:
                        yield ListItem(Label(
                            "  (keine Commands — E drücken zum Bearbeiten)",
                            classes="empty-cat",
                        ))
                    else:
                        for cmd in cat.commands:
                            yield CommandItem(cmd)

        # Slash-Command Popup (über der Chat-Leiste, standardmäßig versteckt)
        with Container(id="slash-popup"):
            yield ListView(id="slash-list")

        # Chat-Leiste — immer unten sichtbar
        with Container(id="chat-area"):
            yield RichLog(id="chat-log", markup=True, highlight=False, auto_scroll=True)
            with Horizontal(id="chat-input-row"):
                yield Label(f" {self._current_agent} ", id="chat-agent-badge")
                yield Input(placeholder="Nachricht oder /befehl …", id="chat-input")
                yield Label("Tab=Fokus  Esc=Liste", id="chat-send-hint")

        # Footer
        yield Label(
            "  ↑↓ Navigate   Enter Launch   Tab Chat   /befehl   E Config   Q Quit",
            id="footer-bar",
        )

    def on_mount(self) -> None:
        # Slash-Popup mit allen Commands füllen
        sl = self.query_one("#slash-list", ListView)
        for cmd, desc in self.SLASH_COMMANDS:
            sl.append(ListItem(Label(f"  {cmd:<12} {desc}")))

        self._chat_sys(
            "◈ ATLAS bereit. [dim]Tippe[/dim] [cyan]/help[/cyan] [dim]für Befehle "
            "oder wähle oben ein Tool.[/dim]"
        )
        if self._list_views:
            self._list_views[0].focus()

    # ── Chat-Hilfsfunktionen ──────────────────────────────────────────────────

    def _chat_sys(self, msg: str) -> None:
        self.query_one("#chat-log", RichLog).write(msg)

    def _chat_user(self, msg: str) -> None:
        self.query_one("#chat-log", RichLog).write(
            f"[bold cyan]  Du[/bold cyan]  [dim]({self._current_agent})[/dim]  {msg}"
        )

    def _chat_agent(self, agent: str, msg: str) -> None:
        self.query_one("#chat-log", RichLog).write(
            f"[bold]  {agent}[/bold]  {msg}"
        )

    def _chat_err(self, msg: str) -> None:
        self.query_one("#chat-log", RichLog).write(f"[red]  ✗[/red]  {msg}")

    # ── Input-Events ──────────────────────────────────────────────────────────

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id != "chat-input":
            return
        text = event.value
        popup = self.query_one("#slash-popup")
        if text.startswith("/") and len(text) <= 12:
            # Passende Slash-Commands filtern
            matches = [
                (c, d) for c, d in self.SLASH_COMMANDS
                if c.startswith(text)
            ]
            sl = self.query_one("#slash-list", ListView)
            sl.clear()
            for cmd, desc in matches:
                sl.append(ListItem(Label(f"  {cmd:<12} {desc}")))
            if matches:
                popup.add_class("visible")
                return
        popup.remove_class("visible")

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "chat-input":
            return
        text = event.value.strip()
        event.input.value = ""
        self.query_one("#slash-popup").remove_class("visible")
        if not text:
            return
        if text.startswith("/"):
            self._handle_slash(text)
        else:
            self._handle_chat(text)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        # Slash-Popup Auswahl
        if event.list_view.id == "slash-list":
            lbl = event.item.query_one(Label)
            cmd = str(lbl.renderable).strip().split()[0]
            inp = self.query_one("#chat-input", Input)
            inp.value = cmd + " "
            self.query_one("#slash-popup").remove_class("visible")
            inp.focus()
            return
        # Launcher-Liste
        if event.item and isinstance(event.item, CommandItem):
            cmd = event.item.command
            if not cmd.is_available:
                self._chat_err(f"'{cmd.cmd}' nicht installiert / nicht im PATH")
                return
            if cmd.prompt:
                inp = self.query_one("#chat-input", Input)
                inp.placeholder = cmd.prompt_label + " …"
                inp.value = ""
                inp.focus()
                self._pending_launch = cmd
            else:
                self.exit((cmd, ""))

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "slash-list":
            return
        if event.item and isinstance(event.item, CommandItem):
            cmd = event.item.command
            avail = "" if cmd.is_available else "  [dim red](nicht installiert)[/dim red]"
            self._chat_sys(
                f"[dim cyan]  {cmd.icon}  {cmd.name}[/dim cyan]{avail}"
                f"  [dim]{cmd.description[:60]}[/dim]"
            )

    # ── Slash-Command Handler ─────────────────────────────────────────────────

    _pending_launch: Optional[Command] = None

    def _handle_slash(self, text: str) -> None:
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "/help":
            self._chat_sys("[bold cyan]  Verfügbare Befehle:[/bold cyan]")
            for c, d in self.SLASH_COMMANDS:
                self._chat_sys(f"  [cyan]{c:<14}[/cyan][dim]{d}[/dim]")

        elif cmd == "/clear":
            self.query_one("#chat-log", RichLog).clear()
            self._chat_sys("◈ Chat geleert.")

        elif cmd == "/agent":
            if arg:
                self._current_agent = arg
                self.query_one("#chat-agent-badge", Label).update(f" {arg} ")
                self._chat_sys(f"[cyan]  Agent → {arg}[/cyan]")
            else:
                self._chat_sys(f"  Aktueller Agent: [cyan]{self._current_agent}[/cyan]")

        elif cmd in ("/status", "/learn", "/history"):
            atlas_cmd = cmd.lstrip("/")
            self._chat_sys(f"[dim]  Starte atlas {atlas_cmd} …[/dim]")
            self.exit((Command(
                name=atlas_cmd, cmd="python",
                args=["-m", "atlas_run.atlas", atlas_cmd],
                description="",
            ), ""))

        elif cmd in ("/run", "/init", "/spawn"):
            atlas_cmd = cmd.lstrip("/")
            if arg:
                self.exit((Command(
                    name=atlas_cmd, cmd="python",
                    args=["-m", "atlas_run.atlas", atlas_cmd],
                    description="",
                ), arg))
            else:
                self._chat_sys(
                    f"[yellow]  Verwendung:[/yellow] [cyan]{cmd}[/cyan] <{atlas_cmd}-argument>"
                )

        else:
            self._chat_err(f"Unbekannter Befehl: {text}  →  /help für Übersicht")

    def _handle_chat(self, text: str) -> None:
        # Wenn ein Launcher-Prompt aktiv war → als Argument benutzen
        if self._pending_launch:
            cmd = self._pending_launch
            self._pending_launch = None
            inp = self.query_one("#chat-input", Input)
            inp.placeholder = "Nachricht oder /befehl …"
            self.exit((cmd, text))
            return
        # Normaler Chat → direkt als /run weiterleiten
        self._chat_user(text)
        self._chat_sys(
            f"[dim]  → Sende an Schwarm als[/dim] [cyan]/run {text[:40]}[/cyan][dim] …[/dim]"
        )
        self.exit((Command(
            name="run", cmd="python",
            args=["-m", "atlas_run.atlas", "run"],
            description="",
        ), text))

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_focus_chat(self) -> None:
        self.query_one("#chat-input", Input).focus()

    def action_focus_list(self) -> None:
        self.query_one("#slash-popup").remove_class("visible")
        if self._list_views:
            self._list_views[0].focus()

    def action_quit_app(self) -> None:
        self.exit(None)

    def action_edit_config(self) -> None:
        self.exit(("EDIT_CONFIG", ""))

    def action_reload(self) -> None:
        self._reload_commands()
        self.refresh(recompose=True)


def _safe_id(name: str) -> str:
    return name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")

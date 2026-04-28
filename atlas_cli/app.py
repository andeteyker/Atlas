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
from textual.widgets import Footer, Input, Label, ListItem, ListView, Static

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

/* ── Detail-Leiste ──────────────────────────────────────────────────────── */
#detail {
    height: 4;
    background: #050a15;
    border-top: solid #0d2a4a;
    padding: 0 3;
}

#detail-name {
    color: #00ccff;
    text-style: bold;
    height: 1;
    padding-top: 1;
}

#detail-cmd {
    color: #0d6080;
    height: 1;
}

#detail-desc {
    color: #3a7a9c;
    height: 1;
}

/* ── Prompt-Overlay ─────────────────────────────────────────────────────── */
#prompt-overlay {
    height: 3;
    background: #050a15;
    border-top: solid #00ccff;
    padding: 0 3;
    display: none;
    layer: overlay;
}

#prompt-overlay.visible {
    display: block;
}

#prompt-label {
    color: #0099bb;
    height: 1;
    padding-top: 1;
}

#prompt-input {
    background: #0a1a2a;
    color: #00e5ff;
    border: solid #0d3060;
    height: 1;
}

#prompt-input:focus {
    border: solid #00ccff;
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
        Binding("escape", "cancel_prompt", "Abbrechen", show=False),
    ]

    # Flache Liste aller Commands für Navigation
    _all_commands: list[Command] = []
    _selected_idx: reactive[int] = reactive(0)
    _prompt_active: reactive[bool] = reactive(False)
    _pending_command: Optional[Command] = None

    def __init__(self):
        super().__init__()
        self._categories: list[Category] = []
        self._list_views: list[ListView] = []
        self._reload_commands()

    def _reload_commands(self):
        self._categories = load_commands()
        self._all_commands = [
            cmd
            for cat in self._categories
            for cmd in cat.commands
        ]

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
                yield Label(
                    f"  {cat.icon}  {cat.name}",
                    classes="cat-header",
                )
                lv = ListView(id=f"lv-{_safe_id(cat.name)}")
                if not cat.commands:
                    lv = ListView(id=f"lv-{_safe_id(cat.name)}")
                    self._list_views.append(lv)
                    with lv:
                        yield ListItem(
                            Label("  (keine Commands — commands.yaml bearbeiten)", classes="empty-cat")
                        )
                else:
                    self._list_views.append(lv)
                    with lv:
                        for cmd in cat.commands:
                            yield CommandItem(cmd)

        # Detail-Leiste
        with Container(id="detail"):
            yield Label("", id="detail-name")
            yield Label("", id="detail-cmd")
            yield Label("", id="detail-desc")

        # Prompt-Overlay (für Commands mit prompt: true)
        with Container(id="prompt-overlay"):
            yield Label("", id="prompt-label")
            yield Input(placeholder="", id="prompt-input")

        # Footer
        yield Label(
            "  ↑↓ Navigate   Enter Launch   E Edit Config   R Reload   Q Quit",
            id="footer-bar",
        )

    def on_mount(self) -> None:
        self._update_detail()
        if self._list_views:
            self._list_views[0].focus()

    # ── Navigation & Events ───────────────────────────────────────────────────

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and isinstance(event.item, CommandItem):
            cmd = event.item.command
            idx = self._all_commands.index(cmd) if cmd in self._all_commands else -1
            if idx >= 0:
                self._selected_idx = idx
                self._update_detail()

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.item and isinstance(event.item, CommandItem):
            self._launch_or_prompt(event.item.command)

    def _launch_or_prompt(self, cmd: Command) -> None:
        if not cmd.is_available:
            self._set_detail(
                f"✗  {cmd.name}",
                f"  Nicht installiert: '{cmd.cmd}' nicht im PATH",
                "  Installiere das Tool und starte den Launcher neu.",
            )
            return

        if cmd.prompt:
            self._pending_command = cmd
            self._show_prompt(cmd)
        else:
            self.exit((cmd, ""))

    def _show_prompt(self, cmd: Command) -> None:
        overlay = self.query_one("#prompt-overlay")
        label = self.query_one("#prompt-label", Label)
        inp = self.query_one("#prompt-input", Input)
        label.update(f"  ⌨  {cmd.prompt_label}:")
        inp.value = ""
        overlay.add_class("visible")
        inp.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "prompt-input" and self._pending_command:
            extra = event.value.strip()
            cmd = self._pending_command
            self._pending_command = None
            self._hide_prompt()
            self.exit((cmd, extra))

    def action_cancel_prompt(self) -> None:
        if self._pending_command:
            self._pending_command = None
            self._hide_prompt()
            if self._list_views:
                self._list_views[0].focus()

    def _hide_prompt(self) -> None:
        self.query_one("#prompt-overlay").remove_class("visible")

    # ── Detail-Leiste ─────────────────────────────────────────────────────────

    def _update_detail(self) -> None:
        if not self._all_commands or self._selected_idx < 0:
            return
        idx = min(self._selected_idx, len(self._all_commands) - 1)
        cmd = self._all_commands[idx]
        avail_str = "" if cmd.is_available else "  [nicht installiert]"
        self._set_detail(
            f"  {cmd.icon}  {cmd.name}{avail_str}",
            f"  $ {cmd.full_cmd}",
            f"  {cmd.description}",
        )

    def _set_detail(self, name: str, cmd_str: str, desc: str) -> None:
        self.query_one("#detail-name", Label).update(name)
        self.query_one("#detail-cmd", Label).update(cmd_str)
        self.query_one("#detail-desc", Label).update(desc)

    # ── Actions ───────────────────────────────────────────────────────────────

    def action_quit_app(self) -> None:
        self.exit(None)

    def action_edit_config(self) -> None:
        self.exit(("EDIT_CONFIG", ""))

    def action_reload(self) -> None:
        self._reload_commands()
        self.refresh(recompose=True)
        self._update_detail()


def _safe_id(name: str) -> str:
    return name.lower().replace(" ", "-").replace("&", "and").replace("/", "-")

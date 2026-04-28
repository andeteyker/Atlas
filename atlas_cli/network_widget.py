"""
ATLAS Agent Network Widget — terminale Netzwerk-Visualisierung.

Zeigt alle aktiven Agenten in einem kreisförmigen Layout mit
Verbindungslinien zum CORE-Orchestrator (Blackboard-Prinzip).
Aktualisiert sich automatisch wenn neue Agenten gespawnt werden.
"""

from __future__ import annotations

import math
from rich.style import Style
from rich.text import Text
from textual.widget import Widget


# ── Zeichen-Palette ───────────────────────────────────────────────────────────
NODE_CORE   = "◈"
NODE_AGENT  = "◉"
DOT_SPOKE   = "·"    # Verbindung: Core → Agent
DOT_RING    = "·"    # Verbindung: Agent → Agent (Ring)


class AgentNetwork(Widget):
    """Kreisförmige Agenten-Netzwerk-Visualisierung im Terminal."""

    DEFAULT_CSS = """
    AgentNetwork {
        background: #050a15;
        border: round #0d3060;
        width: 38;
        min-width: 30;
        height: 1fr;
    }
    """

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._agents: list[str] = []

    def on_mount(self) -> None:
        self._refresh_agents()
        self.set_interval(3.0, self._refresh_agents)

    def _refresh_agents(self) -> None:
        try:
            from atlas_core.blackboard import load_agent_registry
            reg = load_agent_registry()
            self._agents = [n for n, i in reg.items() if i.get("active", True)]
        except Exception:
            self._agents = []
        self.refresh()

    # ── Render ────────────────────────────────────────────────────────────────

    def render(self) -> Text:
        w = max(self.size.width - 2, 24)
        h = max(self.size.height - 2, 10)

        if not self._agents:
            return _render_empty(w, h)
        return _render_network(self._agents, w, h)


# ── Rendering-Logik ───────────────────────────────────────────────────────────

def _render_empty(w: int, h: int) -> Text:
    text = Text()
    mid = h // 2
    for y in range(h):
        if y == mid - 1:
            line = Text.from_markup("  [dim cyan]◈  Kein Schwarm aktiv[/dim cyan]\n")
        elif y == mid:
            line = Text.from_markup("  [dim]atlas init \"Thema\" starten[/dim]\n")
        elif y == mid + 2:
            line = Text.from_markup("  [dim blue]· · · · · · · · · · ·[/dim blue]\n")
        else:
            line = Text("\n")
        text.append_text(line)
    return text


def _render_network(agents: list[str], w: int, h: int) -> Text:
    # Raster anlegen
    grid: list[list[str]] = [[" "] * w for _ in range(h)]
    style_map: dict[tuple[int, int], str] = {}

    cx, cy = w // 2, h // 2
    n = len(agents)

    # Radius (Terminals: Zeichen ~2× so hoch wie breit → ry ≈ rx/2)
    rx = max(7, cx - 9)
    ry = max(3, cy - 3)

    # Agenten-Positionen auf dem Kreis berechnen
    positions: list[tuple[int, int]] = []
    for i in range(n):
        angle = 2 * math.pi * i / n - math.pi / 2
        x = max(2, min(w - 3, int(round(cx + rx * math.cos(angle)))))
        y = max(0, min(h - 1, int(round(cy + ry * math.sin(angle)))))
        positions.append((x, y))

    # Speichen: Core → Agent
    for px, py in positions:
        for x, y in _bresenham(cx, cy, px, py):
            if (x, y) not in style_map:
                _set(grid, x, y, DOT_SPOKE)
                style_map[(x, y)] = "dim cyan"

    # Ring: Agent → nächster Agent
    for i in range(n):
        x1, y1 = positions[i]
        x2, y2 = positions[(i + 1) % n]
        for x, y in _bresenham(x1, y1, x2, y2):
            if (x, y) not in style_map:
                _set(grid, x, y, DOT_RING)
                style_map[(x, y)] = "dim blue"

    # Core-Knoten
    _set(grid, cx, cy, NODE_CORE)
    style_map[(cx, cy)] = "bold cyan"

    # Agenten-Knoten + Name
    for i, (px, py) in enumerate(positions):
        _set(grid, px, py, NODE_AGENT)
        style_map[(px, py)] = "bold cyan"

        # Kurzname (max 8 Zeichen, snake_case → Unterstriche entfernen)
        raw = agents[i]
        short = raw.replace("_", " ")[:9]

        # Richtung für den Namen: rechts / links / oben / unten vom Knoten
        dx = px - cx
        dy = py - cy
        if abs(dx) >= abs(dy):
            # Links oder rechts
            if dx >= 0:
                _place_right(grid, style_map, px + 2, py, short)
            else:
                _place_left(grid, style_map, px - 2, py, short)
        else:
            # Oben oder unten
            label_x = max(1, px - len(short) // 2)
            label_y = py - 1 if dy < 0 else py + 1
            _place_right(grid, style_map, label_x, label_y, short)

    # Legend unten
    _render_legend(grid, style_map, w, h, n)

    # Grid → Rich Text
    return _grid_to_text(grid, style_map, w, h)


def _render_legend(grid, style_map, w, h, n):
    """Legende ganz unten im Widget."""
    if h < 4:
        return
    legend = f" {NODE_CORE} core  {NODE_AGENT} agent  · link "
    ly = h - 1
    for x, ch in enumerate(legend[:w]):
        _set(grid, x, ly, ch)
        style_map[(x, ly)] = "dim blue"


def _place_right(grid, style_map, x, y, text):
    for j, ch in enumerate(text):
        nx = x + j
        if 0 <= nx < len(grid[0]) and 0 <= y < len(grid):
            _set(grid, nx, y, ch)
            style_map[(nx, y)] = "dim cyan"


def _place_left(grid, style_map, x, y, text):
    for j, ch in enumerate(reversed(text)):
        nx = x - j
        if 0 <= nx < len(grid[0]) and 0 <= y < len(grid):
            _set(grid, nx, y, ch)
            style_map[(nx, y)] = "dim cyan"


def _set(grid, x, y, ch):
    if 0 <= x < len(grid[0]) and 0 <= y < len(grid):
        grid[y][x] = ch


def _bresenham(x0, y0, x1, y1) -> list[tuple[int, int]]:
    """Bresenham-Linie zwischen zwei Punkten."""
    points = []
    dx, dy = abs(x1 - x0), abs(y1 - y0)
    sx = 1 if x0 < x1 else -1
    sy = 1 if y0 < y1 else -1
    err = dx - dy
    x, y = x0, y0
    while True:
        points.append((x, y))
        if x == x1 and y == y1:
            break
        e2 = 2 * err
        if e2 > -dy:
            err -= dy
            x += sx
        if e2 < dx:
            err += dx
            y += sy
    return points


def _grid_to_text(grid, style_map, w, h) -> Text:
    text = Text()
    for y in range(h):
        for x in range(w):
            ch = grid[y][x]
            skey = style_map.get((x, y), "")
            if skey:
                text.append(ch, style=Style.parse(skey))
            else:
                text.append(ch)
        text.append("\n")
    return text

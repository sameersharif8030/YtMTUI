from __future__ import annotations

import math
from enum import Enum

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static


class VisualizerMode(Enum):
    TURNTABLE = 0
    SPECTRUM = 1
    CASSETTE = 2
    SOUNDWAVE = 3


class VisualizerWidget(Static):
    """Responsive terminal visuals with smooth playback-driven animation."""

    mode = reactive(VisualizerMode.TURNTABLE, init=False)
    compact = reactive(False, init=False)
    playing = reactive(False, init=False)
    beat_phase = reactive(0.0, init=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._rotation = 0.0
        self._bpm = 112.0

    def on_mount(self) -> None:
        # A single lightweight timer drives all modes. It stops redrawing while
        # paused, so static artwork remains crisp and idle CPU stays low.
        self.set_interval(0.05, self._tick)

    def _tick(self) -> None:
        if not self.playing:
            return
        self._rotation = (self._rotation + 0.18) % (2 * math.pi)
        self.beat_phase = (self.beat_phase + (2 * math.pi * self._bpm / 60 / 20)) % (2 * math.pi)
        self.refresh()

    def cycle_mode(self) -> None:
        self.mode = VisualizerMode((self.mode.value + 1) % len(VisualizerMode))

    def set_playing(self, playing: bool) -> None:
        if self.playing != playing:
            self.playing = playing
            self.refresh()

    def set_bpm(self, bpm: float) -> None:
        self._bpm = max(60.0, min(200.0, bpm))

    def _palette(self) -> dict[str, str]:
        try:
            return self.app.get_css_variables()
        except Exception:
            return {"accent": "#89dceb", "green": "#a6e3a1", "queue": "#f5c2e7", "muted": "#a6adc8", "surface_alt": "#313244", "active_fg": "#11111b"}

    def _get_mode_color(self) -> str:
        palette = self._palette()
        return {
            VisualizerMode.TURNTABLE: palette.get("accent", "#89dceb"),
            VisualizerMode.SPECTRUM: palette.get("green", "#a6e3a1"),
            VisualizerMode.CASSETTE: palette.get("queue", "#f5c2e7"),
            VisualizerMode.SOUNDWAVE: palette.get("accent", "#89dceb"),
        }.get(self.mode, palette.get("accent", "#89dceb"))

    def render(self) -> Text:
        width = max(self.size.width, 1)
        height = max(self.size.height, 1)
        if self.compact or width < 20 or height < 4:
            return self._render_compact(width)
        if self.mode is VisualizerMode.TURNTABLE:
            return self._render_vinyl(width)
        if self.mode is VisualizerMode.SPECTRUM:
            return self._render_spectrum(width, height)
        if self.mode is VisualizerMode.CASSETTE:
            return self._render_cassette(width)
        return self._render_waveform(width, height)

    def _render_compact(self, width: int) -> Text:
        """A small, clean mode-specific animation for genuinely narrow panels."""
        palette = self._palette()
        accent = self._get_mode_color()
        width = max(min(width, 28), 8)
        if self.mode is VisualizerMode.TURNTABLE:
            frames = ("◉──·", "◉──°", "◉──•", "◉──˚")
            frame = frames[int(self._rotation / 0.18) % len(frames)] if self.playing else "◉──·"
        elif self.mode is VisualizerMode.SPECTRUM:
            glyphs = "▁▃▅▇█▇▅▃▁"
            frame = "".join(glyphs[int(abs(math.sin(self.beat_phase + i * 0.7)) * 8) % len(glyphs)] for i in range(width))
        elif self.mode is VisualizerMode.CASSETTE:
            reel = "◉" if not self.playing or int(self._rotation / 0.18) % 2 == 0 else "◎"
            frame = f"╭─ {reel} ═══ {reel} ─╮"
        else:
            frame = "".join("▁▃▅▇█▇▅▃▁"[int(abs(math.sin(self.beat_phase + i * 0.4)) * 8) % 9] for i in range(width))
        text = Text(frame, no_wrap=True)
        text.stylize(f"bold {accent}")
        return text

    def _render_vinyl(self, width: int) -> Text:
        """A centered grooved record with a smoothly rotating outer marker."""
        palette = self._palette()
        accent = self._get_mode_color()
        muted = palette.get("muted", "#a6adc8")
        radius_x, radius_y = 8.0, 3.25
        marker_angle = self._rotation if self.playing else -0.72
        edge_cells = []
        for marker_row in range(-3, 4):
            for marker_col in range(-8, 9):
                nx, ny = marker_col / radius_x, marker_row / radius_y
                radius = math.sqrt(nx * nx + ny * ny)
                if 0.82 <= radius <= 1.08:
                    angle = math.atan2(ny, nx)
                    delta = (angle - marker_angle + math.pi) % (2 * math.pi) - math.pi
                    edge_cells.append((abs(delta), marker_row, marker_col))
        _, marker_row, marker_col = min(edge_cells)
        text = Text(no_wrap=True)
        for row in range(-3, 4):
            line = Text()
            for col in range(-8, 9):
                nx, ny = col / radius_x, row / radius_y
                radius = math.sqrt(nx * nx + ny * ny)
                if radius > 1.08:
                    glyph, style = " ", ""
                elif (row, col) == (marker_row, marker_col):
                    glyph, style = "◆", f"bold {accent}"
                elif radius < 0.20:
                    glyph, style = "●", f"bold {palette.get('queue', accent)}"
                elif radius < 0.31:
                    glyph, style = "◉", f"bold {accent}"
                elif abs(radius - 0.40) < 0.035 or abs(radius - 0.63) < 0.035 or abs(radius - 0.83) < 0.035:
                    glyph, style = "·", muted
                elif radius <= 1:
                    glyph, style = "░" if int(radius * 18) % 3 else "▒", accent
                else:
                    glyph, style = "·", muted
                line.append(glyph, style=style)
            text.append(line)
            if row < 3:
                text.append("\n")
        text.justify = "center"
        return text

    def _render_spectrum(self, width: int, height: int) -> Text:
        """Balanced, independently moving columns with soft color variation."""
        palette = self._palette()
        accent = palette.get("accent", "#89dceb")
        green = palette.get("green", "#a6e3a1")
        bar_count = max(8, min(width - 2, 30))
        rows = max(3, min(height - 1, 7))
        levels = []
        for index in range(bar_count):
            phase = self.beat_phase + index * 0.47
            wave = (math.sin(phase) + 0.55 * math.sin(phase * 0.57 + index * 0.19) + 1.55) / 3.1
            levels.append(max(0.10, min(1.0, wave)))
        text = Text(no_wrap=True)
        for row in range(rows, 0, -1):
            line = Text()
            threshold = row / rows
            for index, level in enumerate(levels):
                if level >= threshold:
                    char = "█" if row >= rows - 1 else "▇"
                    line.append(char, style=f"bold {green if index % 5 == 0 else accent}")
                else:
                    line.append(" " )
            text.append(line)
            if row > 1:
                text.append("\n")
        text.justify = "center"
        return text

    def _render_cassette(self, width: int) -> Text:
        """A clean, symmetric cassette shell with subtly turning reel hubs."""
        accent = self._get_mode_color()
        palette = self._palette()
        muted = palette.get("muted", "#a6adc8")
        left_reel = "◉" if not self.playing or int(self._rotation / 0.18) % 2 == 0 else "◎"
        right_reel = "◎" if left_reel == "◉" else "◉"
        lines = [
            "╭─────────────────────╮",
            "│  ╭───────────────╮  │",
            f"│  │   {left_reel}         {right_reel}   │  │",
            "│  │     ╲  ╱      │  │",
            "│  │      ╳       │  │",
            "│  ╰──────┴────────╯  │",
            "╰───────┬───┬─────────╯",
        ]
        text = Text(no_wrap=True)
        for idx, line in enumerate(lines):
            if idx:
                text.append("\n")
            text.append(line, style=f"{accent if idx in (0, 6) else muted}")
        text.justify = "center"
        return text

    def _render_waveform(self, width: int, height: int) -> Text:
        """A centered, mirrored waveform with smooth animated amplitude."""
        palette = self._palette()
        accent = self._get_mode_color()
        green = palette.get("green", "#a6e3a1")
        columns = max(10, min(width - 2, 36))
        rows = max(3, min(height - 1, 7))
        center = (rows - 1) / 2
        points = []
        for index in range(columns):
            phase = index * 0.38 - self.beat_phase
            amplitude = abs(math.sin(phase) * 0.75 + math.sin(phase * 0.43 + 1.2) * 0.2)
            points.append(max(0.15, min(1.0, amplitude)))
        text = Text(no_wrap=True)
        for row in range(rows):
            line = Text()
            for index, amplitude in enumerate(points):
                vertical = abs(row - center) / max(center, 1)
                target = 1.0 - amplitude
                if abs(vertical - target) < (0.20 + 0.05 * amplitude):
                    line.append("●" if row == round(center) else "━", style=f"bold {green if index % 6 == 0 else accent}")
                else:
                    line.append("·", style=palette.get("surface_alt", "#313244"))
            text.append(line)
            if row < rows - 1:
                text.append("\n")
        text.justify = "center"
        return text

    def set_mode_from_track_change(self) -> None:
        self.cycle_mode()
        self._rotation = 0.0

    def on_track_change(self, bpm: float | None = None) -> None:
        if bpm:
            self.set_bpm(bpm)
        self.set_mode_from_track_change()


class VisualizerModeBadge(Static):
    """Compact badge showing the active visualizer mode."""

    mode = reactive(VisualizerMode.TURNTABLE, init=False)

    MODE_LABELS = {
        VisualizerMode.TURNTABLE: "VINYL",
        VisualizerMode.SPECTRUM: "SPECTRUM",
        VisualizerMode.CASSETTE: "CASSETTE",
        VisualizerMode.SOUNDWAVE: "WAVEFORM",
    }

    def render(self) -> Text:
        label = self.MODE_LABELS.get(self.mode, "VISUALIZER")
        try:
            palette = self.app.get_css_variables()
        except Exception:
            palette = {}
        foreground = palette.get("active_fg", "#11111b")
        accent = palette.get("accent", "#89dceb")
        return Text(f" ♫ {label} ", style=f"bold {foreground} on {accent}")

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from ..config import DEFAULT_VOLUME
from ..player import PlayerState, PlaybackMode
from ..ytmusic import Track

SPINNER_FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def _fit(text: str, width: int) -> str:
    if width <= 0:
        return ""
    if len(text) <= width:
        return text
    if width == 1:
        return "…"
    return text[: width - 1] + "…"


def _time_label(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


class NowPlaying(Static):
    """Compact now-playing widget for mini-mode or header."""

    track = reactive[Track | None](None, init=False)
    state = reactive(PlayerState.IDLE, init=False)
    time_pos = reactive(0.0, init=False)
    duration = reactive(0.0, init=False)
    volume = reactive(float(DEFAULT_VOLUME), init=False)
    compact = reactive(False, init=False)
    playback_mode = reactive(PlaybackMode.NORMAL, init=False)
    audio_bitrate = reactive[int | None](None, init=False)
    audio_codec = reactive[str | None](None, init=False)
    audio_channels = reactive[int | None](None, init=False)

    def on_mount(self) -> None:
        self._frame = 0
        self._pulse = 0
        self.set_interval(0.15, self._tick)

    def _tick(self) -> None:
        if self.state in (PlayerState.LOADING, PlayerState.BUFFERING):
            self._frame = (self._frame + 1) % len(SPINNER_FRAMES)
            self.refresh()
        elif self.state is PlayerState.PLAYING:
            self._pulse = (self._pulse + 1) % 4
            self.refresh()

    def _icon(self) -> tuple[str, str]:
        if self.state is PlayerState.PLAYING:
            return "▶", "green"
        if self.state is PlayerState.PAUSED:
            return "⏸", "yellow"
        if self.state is PlayerState.LOADING:
            return SPINNER_FRAMES[self._frame], "yellow"
        if self.state is PlayerState.BUFFERING:
            return SPINNER_FRAMES[self._frame], "cyan"
        if self.state is PlayerState.ERROR:
            return "✖", "red"
        return "■", "dim"

    def _fraction(self) -> float:
        if self.duration > 0:
            return min(max(self.time_pos / self.duration, 0.0), 1.0)
        return 0.0

    def _bar_text(self, cells: int) -> Text:
        cells = max(cells, 1)
        filled = min(int(round(self._fraction() * cells)), cells)
        bar = Text()
        if filled > 0:
            if filled > 1:
                bar.append("━" * (filled - 1), style="green")
            pulse = self._pulse % 2 == 0 and self.state is PlayerState.PLAYING
            bar.append("━", style="reverse green" if pulse else "green")
        if filled < cells:
            bar.append("─" * (cells - filled), style="dim")
        return bar

    def render(self) -> Text:
        width = max(self.size.width, 10)
        text = Text(no_wrap=True)
        icon, icon_style = self._icon()
        track = self.track
        if track is None:
            text.append(f"{icon} Nothing playing", style=icon_style)
            return text
        current = _time_label(self.time_pos)
        total = _time_label(self.duration) if self.duration > 0 else track.duration_label
        span = f"{current}/{total}"
        title = track.title or "Unknown"
        artist = track.artist or "Unknown artist"

        # Audio metadata line
        audio_parts = []
        if self.audio_codec:
            audio_parts.append(self.audio_codec.upper())
        if self.audio_bitrate:
            audio_parts.append(f"{self.audio_bitrate}kbps")
        if self.audio_channels:
            audio_parts.append(f"{self.audio_channels}ch")
        audio_str = " ".join(audio_parts)
        remaining = _time_label(max(self.duration - self.time_pos, 0))
        audio_meta = f"  {audio_str}  ·  -{remaining}" if audio_str else f"  -{remaining}"

        if self.compact:
            bar_cells = 14
            meta = f"  {span} "
            room = width - len(meta) - bar_cells
            head = _fit(f"{icon} {title} — {artist}", max(room, 6))
            text.append(head, style="bold")
            text.append(meta, style="dim")
            text.append(self._bar_text(bar_cells))
            return text

        # Shuffle indicator
        mode_str = " 🔀" if self.playback_mode is PlaybackMode.SHUFFLE else ""
        bar_cells = max(width - len(span) - len(audio_meta) - 26, 8)
        meta = f"  {span}  vol {int(self.volume)}%"
        vol_str = f"  vol {int(self.volume)}%"
        room = width - len(meta) - bar_cells - (len(icon) + 1 + len(mode_str))
        text.append(f"{icon} ", style=icon_style)
        text.append(_fit(f"{title} — {artist}{mode_str}", max(room, 4)), style="bold")
        text.append(meta, style="dim")
        text.append("\n")
        text.append(" ")
        text.append(self._bar_text(bar_cells))
        text.append(audio_meta, style="dim")
        return text


def _track_item(track: Track | None, current: bool = False):
    """Create a list item for a track."""
    from textual.widgets import ListItem, Label

    if track is None:
        return ListItem(Label("Unknown"))

    prefix = "▶ " if current else "  "
    line = track.line if hasattr(track, "line") else str(track)
    item = ListItem(Label(f"{prefix}{line}"))
    if current:
        item.add_class("current")
    return item
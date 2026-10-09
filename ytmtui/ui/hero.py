from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static, Label
from textual.containers import Vertical, Horizontal

from ..player import PlayerState
from ..ytmusic import Track
from .cover_art import CoverArtWidget
from .visualizer import VisualizerWidget, VisualizerMode, VisualizerModeBadge


def _time_label(seconds: float) -> str:
    total = max(int(seconds), 0)
    minutes, secs = divmod(total, 60)
    hours, minutes = divmod(minutes, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes}:{secs:02d}"


def buffered_until(cache_state: dict | None, position: float) -> float | None:
    """Return the contiguous cached endpoint containing the playhead, if known."""
    if not isinstance(cache_state, dict):
        return None
    ranges = cache_state.get("seekable-ranges")
    if isinstance(ranges, list):
        candidates = []
        for item in ranges:
            if not isinstance(item, dict):
                continue
            start, end = item.get("start"), item.get("end")
            if isinstance(start, (int, float)) and isinstance(end, (int, float)):
                if start <= position + 0.25 <= end or start <= position <= end + 0.25:
                    candidates.append(float(end))
        return max(candidates) if candidates else None
    cache_end = cache_state.get("cache-end")
    if isinstance(cache_end, (int, float)) and cache_end > position:
        return float(cache_end)
    return None


class TimelineBar(Static):
    """Single-line proportional playback and temporary mpv cache indicator."""

    position = reactive(0.0, init=False)
    duration = reactive(0.0, init=False)
    cache_state = reactive[dict | None](None, init=False)

    def watch_position(self, old: float, new: float) -> None:
        self.refresh()

    def watch_duration(self, old: float, new: float) -> None:
        self.refresh()

    def watch_cache_state(self, old: dict | None, new: dict | None) -> None:
        self.refresh()

    def render(self) -> Text:
        width = max(self.size.width, 1)
        text = Text(no_wrap=True)
        if self.duration <= 0:
            text.append("─" * width, style="dim")
            return text

        duration = max(float(self.duration), 0.001)
        position = min(max(float(self.position), 0.0), duration)
        played_cells = min(width, int(position / duration * width))
        buffered_end = buffered_until(self.cache_state, position)
        buffered_cells = played_cells
        if buffered_end is not None:
            buffered_end = min(max(buffered_end, position), duration)
            buffered_cells = max(played_cells, min(width, int(buffered_end / duration * width)))

        try:
            palette = self.app.get_css_variables()
        except Exception:
            palette = {}
        played_color = palette.get("accent", "#89dceb")
        buffered_color = palette.get("muted", "#a6adc8")

        if played_cells:
            text.append("━" * played_cells, style=f"bold {played_color}")
        if buffered_cells > played_cells:
            text.append("═" * (buffered_cells - played_cells), style=f"{buffered_color}")
        remaining = width - buffered_cells
        if remaining:
            text.append("─" * remaining, style="dim")
        return text


class HeroPanel(Static):
    """Now-playing panel with metadata, visualizer, and always-visible timeline."""

    track = reactive[Track | None](None, init=False)
    state = reactive(PlayerState.IDLE, init=False)
    time_pos = reactive(0.0, init=False)
    duration = reactive(0.0, init=False)
    cache_state = reactive[dict | None](None, init=False)
    volume = reactive(80.0, init=False)
    playback_mode = reactive(False, init=False)
    visualizer_mode = reactive(VisualizerMode.TURNTABLE, init=False)
    compact = reactive(False, init=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._visualizer: VisualizerWidget | None = None
        self._mode_badge: VisualizerModeBadge | None = None
        self._timeline: TimelineBar | None = None
        self._cover_art: CoverArtWidget | None = None

    def compose(self):
        with Vertical(id="hero-content"):
            with Horizontal(id="hero-main"):
                with Static(id="visualizer-container"):
                    self._visualizer = VisualizerWidget(id="visualizer")
                    yield self._visualizer
                    self._mode_badge = VisualizerModeBadge(id="mode-badge")
                    yield self._mode_badge

                with Static(id="metadata-container"):
                    yield Label("", id="track-title", classes="track-title")
                    yield Label("", id="track-artist", classes="track-artist")
                    yield Label("", id="track-album-year", classes="track-album-year")
                    with Horizontal(id="status-row"):
                        yield Label("", id="playback-status", classes="playback-status")
                        yield Label("", id="track-quality", classes="track-quality")

                with Static(id="spectrum-container"):
                    yield Label("", id="spectrum-bars", classes="spectrum-bars")

                with Static(id="cover-container"):
                    self._cover_art = CoverArtWidget(id="cover-art")
                    yield self._cover_art

            with Horizontal(id="timeline-row"):
                yield Label("0:00", id="timeline-current", classes="timeline-time")
                self._timeline = TimelineBar(id="timeline-bar")
                yield self._timeline
                yield Label("--:--", id="timeline-total", classes="timeline-time")

    def on_mount(self) -> None:
        self._update_metadata()
        self._update_playback_status()
        self.query_one("#spectrum-bars", Label).update("▃▅▇█▇▅▃")
        self._update_progress()

    def watch_track(self, old: Track | None, new: Track | None) -> None:
        self.cache_state = None
        self._update_metadata()
        self._update_progress()
        if self._cover_art is not None:
            if new is None:
                self._cover_art.load_track("", None)
            else:
                self._cover_art.load_track(new.id, new.cover_url)

    def watch_state(self, old, new) -> None:
        self._update_playback_status()
        if self._visualizer is not None:
            self._visualizer.set_playing(new == PlayerState.PLAYING)

    def watch_time_pos(self, old: float, new: float) -> None:
        self._update_progress()

    def watch_duration(self, old: float, new: float) -> None:
        self._update_progress()

    def watch_cache_state(self, old: dict | None, new: dict | None) -> None:
        if self._timeline is not None:
            self._timeline.cache_state = new

    def watch_visualizer_mode(self, old, new) -> None:
        if self._visualizer is not None:
            self._visualizer.mode = new
        if self._mode_badge is not None:
            self._mode_badge.mode = new

    def watch_compact(self, old: bool, new: bool) -> None:
        if self._visualizer is not None:
            self._visualizer.compact = new
        self._update_visibility()

    def watch_playback_mode(self, old, new) -> None:
        self._update_shuffle_indicator()

    def _update_metadata(self) -> None:
        try:
            if not self.track:
                self.query_one("#track-title", Label).update("No track playing")
                self.query_one("#track-artist", Label).update("")
                self.query_one("#track-album-year", Label).update("")
                return
            self.query_one("#track-title", Label).update(self.track.title or "Unknown")
            self.query_one("#track-artist", Label).update(self.track.artist or "Unknown Artist")
            self.query_one("#track-album-year", Label).update(self.track.album or "")
        except Exception:
            pass

    def _update_playback_status(self) -> None:
        status_icons = {
            "PLAYING": "▶", "PAUSED": "⏸", "LOADING": "⏳",
            "BUFFERING": "⏳", "ERROR": "✖", "IDLE": "■",
        }
        try:
            icon = status_icons.get(self.state.name, "■")
            self.query_one("#playback-status", Label).update(f"{icon} {self.state.name.capitalize()}")
        except Exception:
            pass

    def _update_progress(self) -> None:
        try:
            current = max(0.0, self.time_pos)
            total = self.duration if self.duration > 0 else (self.track.duration_s if self.track else 0)
            self.query_one("#timeline-current", Label).update(_time_label(current))
            self.query_one("#timeline-total", Label).update(_time_label(total) if total > 0 else "--:--")
            timeline = self.query_one("#timeline-bar", TimelineBar)
            timeline.position = current
            timeline.duration = float(total)
            timeline.cache_state = self.cache_state
        except Exception:
            pass

    def _update_shuffle_indicator(self) -> None:
        pass

    def _update_visibility(self) -> None:
        try:
            self.query_one("#spectrum-container").display = not self.compact
        except Exception:
            pass

    def cycle_visualizer(self) -> None:
        if self._visualizer is not None:
            self._visualizer.cycle_mode()
            self.visualizer_mode = self._visualizer.mode

    def on_track_change(self, bpm: float | None = None) -> None:
        if self._visualizer is not None:
            self._visualizer.on_track_change(bpm)
            self.visualizer_mode = self._visualizer.mode

    def set_playing(self, playing: bool) -> None:
        if self._visualizer is not None:
            self._visualizer.set_playing(playing)

    def set_visualizer_mode(self, mode: int) -> None:
        self.visualizer_mode = list(VisualizerMode)[mode % len(VisualizerMode)]

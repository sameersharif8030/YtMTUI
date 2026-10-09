from __future__ import annotations

from typing import Dict, List, Tuple

from textual.reactive import reactive
from textual.widgets import Static, Label, ProgressBar
from textual.containers import Horizontal
from textual.widgets import Static as StaticWidget

from ..player import PlayerState
from .keycap import KeycapWidget


class FooterWidget(Static):
    """Footer dock with progress bar, volume, and keycap hints."""

    # State
    time_pos = reactive(0.0, init=False)
    duration = reactive(0.0, init=False)
    volume = reactive(80.0, init=False)
    state = reactive(PlayerState.IDLE, init=False)
    context = reactive("queue", init=False)  # search, queue, library, hero
    compact = reactive(False, init=False)

    # Keycap bindings per context
    CONTEXT_BINDINGS: Dict[str, List[Tuple[str, str]]] = {
        "search": [
            ("/", "Search"),
            ("↑↓", "Navigate"),
            ("Enter", "Play"),
            ("Esc", "Back"),
            ("P", "Playlists"),
            ("T", "Theme"),
        ],
        "queue": [
            ("Space", "Play/Pause"),
            ("N", "Next"),
            ("T", "Theme"),
            ("Q", "Quit"),
        ],
        "library": [
            ("↑↓", "Navigate"),
            ("Enter", "Play"),
            ("Esc", "Back"),
            ("H", "History"),
            ("L", "Liked"),
            ("P", "Playlists"),
            ("T", "Theme"),
        ],
        "hero": [
            ("Space", "Play/Pause"),
            ("N", "Next"),
            ("P", "Previous"),
            ("V", "Visualizer"),
            ("T", "Theme"),
            ("M", "Mini"),
            ("S", "Shuffle"),
        ],
        "playlist": [
            ("↑↓", "Navigate"),
            ("Enter", "Play"),
            ("Esc", "Back"),
            ("T", "Theme"),
        ],
    }

    def compose(self):
        with Horizontal(id="footer-content"):
            # Progress bar section
            with Static(id="progress-container", classes="footer-section"):
                yield Label("", id="progress-time", classes="progress-time")
                yield ProgressBar(id="progress-bar", show_eta=False)
                yield Label("", id="progress-time-right", classes="progress-time-right")

            # Volume section
            with Static(id="volume-container", classes="footer-section"):
                yield Label("Vol:", id="volume-label", classes="volume-label")
                yield ProgressBar(id="volume-bar", show_eta=False, total=100)
                yield Label(f"{int(self.volume)}%", id="volume-percent", classes="volume-percent")

            # Keycap hints
            with Static(id="keycap-hints-container", classes="keycap-hints-container"):
                # Will be populated dynamically
                pass

    def on_mount(self) -> None:
        self._rebuild_keycaps()
        self._update_volume_display()

    def watch_context(self, old: str, new: str) -> None:
        self._rebuild_keycaps()

    def watch_compact(self, old: bool, new: bool) -> None:
        # The dock remains a stable three rows in every responsive mode.
        self._rebuild_keycaps()

    def watch_time_pos(self, old: float, new: float) -> None:
        self._update_progress()

    def watch_duration(self, old: float, new: float) -> None:
        self._update_progress()

    def watch_volume(self, old: float, new: float) -> None:
        self._update_volume_display()

    def _update_volume_display(self) -> None:
        """Keep both visible volume indicators synchronized with player state."""
        value = min(max(float(self.volume), 0.0), 100.0)
        try:
            vol_bar = self.query_one("#volume-bar", ProgressBar)
            vol_bar.progress = value
        except Exception:
            pass
        try:
            self.query_one("#volume-percent", Label).update(f"{int(round(value))}%")
        except Exception:
            pass

    def watch_state(self, old, new) -> None:
        # Could update play/pause icon in progress area
        pass

    def _update_progress(self) -> None:
        try:
            progress_bar = self.query_one("#progress-bar", ProgressBar)
            if self.duration > 0:
                progress_bar.progress = (self.time_pos / self.duration) * 100
            else:
                progress_bar.progress = 0

            # Update time labels
            from ..ui.widgets import _time_label
            current = _time_label(self.time_pos)
            total = _time_label(self.duration) if self.duration > 0 else "--:--"

            self.query_one("#progress-time", Label).update(f"{current} / ")
            self.query_one("#progress-time-right", Label).update(f" {total}")
        except Exception:
            pass

    def _rebuild_keycaps(self) -> None:
        try:
            container = self.query_one("#keycap-hints-container")
            container.clear()

            bindings = self.CONTEXT_BINDINGS.get(self.context, [])
            for key, label in bindings:
                if self.compact and len(bindings) > 4:
                    # In compact mode, show only first few
                    continue
                container.mount(KeycapWidget(key, label, compact=self.compact))
        except Exception:
            pass

    def set_context(self, context: str) -> None:
        """Update footer context."""
        self.context = context

    def set_compact(self, compact: bool) -> None:
        self.compact = compact

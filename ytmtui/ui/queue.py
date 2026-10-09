from __future__ import annotations

from typing import Callable, Optional
from textual.reactive import reactive
from textual.widgets import Static, Label, ListView, ListItem, Button
from textual.containers import Vertical, Horizontal

from ..ytmusic import Track
from ..player import PlayerState


class QueuePanel(Static):
    """Interactive queue panel with playing indicator."""

    queue = reactive([], init=False)
    current_index = reactive(-1, init=False)
    state = reactive(PlayerState.IDLE, init=False)

    def __init__(self, on_goto: Callable[[int], None] | None = None, on_remove: Callable[[int], None] | None = None, on_shuffle=None, on_clear=None, **kwargs):
        super().__init__(**kwargs)
        self._on_goto = on_goto
        self._on_remove = on_remove
        self._on_shuffle = on_shuffle
        self._on_clear = on_clear
        self._queue_list: ListView | None = None

    def compose(self):
        with Vertical(id="queue-content"):
            # Header with queue title and controls
            with Horizontal(id="queue-header"):
                yield Label("🎵 Queue", id="queue-title", classes="queue-title")

                with Horizontal(id="queue-controls"):
                    yield Button("🔀", id="btn-shuffle", classes="queue-btn", tooltip="Shuffle")
                    yield Button("🗑️", id="btn-clear", classes="queue-btn", tooltip="Clear queue")
                    yield Button("🔁", id="btn-repeat", classes="queue-btn", tooltip="Repeat mode")

            # Queue list
            yield ListView(id="queue-list", classes="queue-list")

            # Empty state
            yield Label("Queue is empty\nPress Enter on a track to add it", id="queue-empty", classes="queue-empty hidden")

    def on_mount(self) -> None:
        self._queue_list = self.query_one("#queue-list", ListView)
        self.query_one("#queue-empty").remove_class("hidden")
        self._render_queue()

    def watch_queue(self, old: list, new: list) -> None:
        self._render_queue()

    def watch_current_index(self, old: int, new: int) -> None:
        self._render_queue()

    def watch_state(self, old, new) -> None:
        self._update_playing_indicator()

    def _render_queue(self) -> None:
        if self._queue_list is None:
            return

        self._queue_list.clear()
        if not self.queue:
            try:
                self.query_one("#queue-empty").remove_class("hidden")
            except Exception:
                pass
            return

        try:
            self.query_one("#queue-empty").add_class("hidden")
        except Exception:
            pass

        from .widgets import _track_item
        items = []
        for i, track in enumerate(self.queue):
            is_current = i == self.current_index
            items.append(_track_item(track, current=is_current))

        self._queue_list.mount(*items)

        # Keep the playing item visible; ListView scrolls automatically when
        # its index moves beyond the viewport, while preserving access to the
        # remaining queue items with normal scrolling.
        if self.current_index >= 0 and self.current_index < len(self.queue):
            self._queue_list.index = self.current_index

    def _update_playing_indicator(self) -> None:
        # Update the visual indicator for currently playing track
        if self._queue_list is not None and 0 <= self.current_index < len(self.queue):
            self._queue_list.index = self.current_index

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        if event.list_view.id == "queue-list":
            if self._on_goto and 0 <= event.index < len(self.queue):
                self._on_goto(event.index)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "btn-shuffle":
            if self._on_shuffle is not None:
                self._on_shuffle()
        elif event.button.id == "btn-clear":
            if self._on_clear is not None:
                self._on_clear()
        elif event.button.id == "btn-repeat":
            pass

    class ShuffleRequested:
        pass

    class ClearQueueRequested:
        pass

    class RepeatModeRequested:
        pass

    def get_current_track(self) -> Track | None:
        if 0 <= self.current_index < len(self.queue):
            return self.queue[self.current_index]
        return None

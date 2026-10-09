from __future__ import annotations

from typing import Any, Callable, List

from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Label, ListView, Static
from textual.containers import Vertical, Horizontal

from ..ytmusic import Playlist


class SidebarWidget(Static):
    """Left sidebar with quick navigation links."""

    # Navigation items
    NAV_ITEMS = [
        ("search", "🔍", "Search", "Search YouTube Music"),
        ("playlists", "📁", "Playlists", "Your library playlists"),
        ("history", "📜", "History", "Recently played"),
        ("favorites", "★", "Favorites", "Liked songs"),
    ]

    active_section = reactive("search", init=False)
    collapsed = reactive(False, init=False)

    def __init__(self, on_navigate: Callable[[str], None] | None = None, **kwargs):
        super().__init__(**kwargs)
        self._on_navigate = on_navigate
        self._nav_buttons: dict[str, Button] = {}

    def compose(self) -> ComposeResult:
        with Vertical(id="sidebar-content"):
            yield Label("YTMTUI", id="sidebar-logo", classes="sidebar-logo")
            yield Label("Theme: Catppuccin Mocha", id="theme-status", classes="sidebar-stat")

            # Search input
            yield Input(placeholder="Search YouTube Music…", id="search", classes="input-search")

            for section_id, icon, label, tooltip in self.NAV_ITEMS:
                btn = Button(
                    f"{icon}  {label}",
                    id=f"nav-{section_id}",
                    classes="sidebar-nav-btn",
                    tooltip=tooltip,
                )
                self._nav_buttons[section_id] = btn
                yield btn

            yield Label("", id="sidebar-spacer")

            # Quick stats
            yield Label("📊 Quick Stats", classes="sidebar-section-title")
            yield Label("Queue: 0 tracks", id="stat-queue", classes="sidebar-stat")
            yield Label("History: 0 entries", id="stat-history", classes="sidebar-stat")
            yield Label("Playlists: 0", id="stat-playlists", classes="sidebar-stat")

    def on_mount(self) -> None:
        self._update_active_button()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("nav-"):
            section = event.button.id[4:]  # Remove "nav-"
            self.active_section = section
            if self._on_navigate:
                self._on_navigate(section)

    def watch_active_section(self, old: str, new: str) -> None:
        self._update_active_button()
        if hasattr(self, "query"):
            try:
                self.query_one(f"#nav-{old}", expect_type=Button).remove_class("current")
            except Exception:
                pass
            try:
                self.query_one(f"#nav-{new}", expect_type=Button).add_class("current")
            except Exception:
                pass

    def _update_active_button(self) -> None:
        for section_id, btn in self._nav_buttons.items():
            if section_id == self.active_section:
                btn.add_class("current")
            else:
                btn.remove_class("current")

    def update_stats(self, queue_count: int = 0, history_count: int = 0, playlist_count: int = 0) -> None:
        """Update sidebar statistics."""
        try:
            self.query_one("#stat-queue").update(f"Queue: {queue_count} tracks")
            self.query_one("#stat-history").update(f"History: {history_count} entries")
            self.query_one("#stat-playlists").update(f"Playlists: {playlist_count}")
        except Exception:
            pass

    def update_theme(self, label: str) -> None:
        try:
            self.query_one("#theme-status", Label).update(f"Theme: {label}")
        except Exception:
            pass

    def toggle_collapse(self) -> None:
        self.collapsed = not self.collapsed
        self.display = not self.collapsed


# Quick Links Section for expanded sidebar
class QuickLinksSection(Static):
    """Expandable quick links section in sidebar."""

    def __init__(self, title: str, items: List[tuple[str, str, str]], **kwargs):
        super().__init__(**kwargs)
        self.title = title
        self.items = items  # (id, icon, label)

    def compose(self) -> ComposeResult:
        yield Label(self.title, classes="sidebar-section-title")
        for item_id, icon, label in self.items:
            yield Button(
                f"{icon} {label}",
                id=f"quick-{item_id}",
                classes="sidebar-quick-btn",
            )

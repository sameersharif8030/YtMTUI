from __future__ import annotations

import asyncio
import threading
from typing import Any, Callable

from textual import on, work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.css.query import QueryError
from textual.events import Resize
from textual.widgets import Input, Label, ListItem, ListView, Static

from .config import BROWSER_AUTH, DEFAULT_VOLUME
from .history import HistoryCache
from .layout import DashboardLayoutEngine
from .mpv_ipc import MPVError
from .player import PlaybackController, PlayerEvent, PlayerState
from .theme import THEME_PALETTES, ThemeManager
from .ui import (
    VisualizerWidget,
    VisualizerMode,
    SidebarWidget,
    HeroPanel,
    LibraryPanel,
    QueuePanel,
    FooterWidget,
    KeycapWidget,
)
from .ytmusic import Playlist, Track, YTMusicService


class YtMTUI(App):
    """YouTube Music Terminal UI - Multi-panel Dashboard."""

    TITLE = "YtMTUI"
    SUB_TITLE = "YouTube Music"

    # Load external CSS files
    CSS_PATH = [
        "styles/base.tcss",
        "styles/themes.tcss",
        "styles/layout.tcss",
        "styles/widgets.tcss",
    ]

    BINDINGS = [
        # Global playback controls
        Binding("space", "toggle_pause", "Play/Pause"),
        Binding("n", "next_track", "Next"),
        Binding("p", "prev_track", "Previous"),
        Binding("[", "seek_back", "Seek -5s", show=False),
        Binding("]", "seek_forward", "Seek +5s", show=False),
        Binding("+", "volume_up", show=False),
        Binding("-", "volume_down", show=False),

        # Navigation
        Binding("/", "focus_search", "Search"),
        Binding("escape", "browser_back", "Back"),
        Binding("P", "show_playlists", "Playlists"),
        Binding("p", "show_playlists", show=False),
        Binding("H", "show_history", "History"),
        Binding("L", "load_liked", "Liked"),

        # Playback modes
        Binding("s", "toggle_shuffle", "Shuffle"),
        Binding("shift+enter", "play_shuffled", "Play Shuffled", show=True),
        Binding("c", "clear_queue", "Clear Queue"),
        Binding("d", "remove_selected", show=False),
        Binding("r", "retry_track", show=False),

        # UI Controls
        Binding("v", "cycle_visualizer", "Visualizer"),
        Binding("t", "cycle_theme", "Theme"),
        Binding("m", "toggle_mini", "Mini"),
        Binding("q", "quit", "Quit"),

        # Queue management
        Binding("ctrl+up", "move_up_queue", "Move Up", show=False),
        Binding("ctrl+down", "move_down_queue", "Move Down", show=False),
    ]

    def __init__(self, volume: int = DEFAULT_VOLUME, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._initial_volume = volume
        self._engine = DashboardLayoutEngine()
        self._last_size = (120, 40)
        self.mini = False
        self._volume = float(volume)
        self._mpv_error: str | None = None
        self._service_error: str | None = None
        self._service: YTMusicService | None = None
        self._history = None
        self.controller: PlaybackController | None = None
        self._status_seq = 0

        # Theme & Visualizer
        self._theme_manager: ThemeManager | None = None
        self._current_visualizer_mode = 0

        # Browser state
        self._browser_mode: str = "search"  # search, playlists, playlist_tracks, history, liked
        self._playlists: list[Playlist] = []
        self._current_playlist_id: str | None = None
        self._playlist_tracks: list[Track] = []
        self._playlist_start_mode: str | None = None
        self._liked_tracks: list[Track] = []
        self._history_tracks: list[Track] = []
        self._results: list[Track] = []
        self._search_input_visible: bool = True
        self._focused_panel: str = "queue"  # search, queue, library, hero, sidebar

    def get_css_variables(self) -> dict[str, str]:
        """Include the selected application palette in Textual's CSS variables."""
        variables = super().get_css_variables()
        manager = getattr(self, "_theme_manager", None)
        palette = manager.palette if manager is not None else THEME_PALETTES["catppuccin"]
        variables.update(palette)
        return variables

    def compose(self) -> ComposeResult:
        """Compose the multi-panel dashboard layout."""
        with Horizontal(id="app-grid"):
            yield SidebarWidget(id="sidebar", on_navigate=self._on_sidebar_navigate)
            with Vertical(id="workspace"):
                with Vertical(id="top-half"):
                    yield HeroPanel(id="hero")
                with Horizontal(id="bottom-half"):
                    yield LibraryPanel(
                        id="library",
                        on_play_track=self._play_track_from_library,
                        on_open_playlist=self._open_playlist,
                    )
                    yield QueuePanel(
                        id="queue",
                        on_goto=self._goto_queue_index,
                        on_remove=self._remove_from_queue,
                        on_shuffle=self.action_toggle_shuffle,
                        on_clear=self.action_clear_queue,
                    )

        yield Static(self._ready_message(), id="status")
        yield FooterWidget(id="footer")

    def on_mount(self) -> None:
        """Initialize services and start playback controller."""
        try:
            self._service = YTMusicService(BROWSER_AUTH)
        except Exception as exc:
            self._service_error = str(exc)

        self._history = HistoryCache()
        self.controller = PlaybackController(
            self._player_event,
            self._service,
            self._history,
        )
        try:
            self.controller.start(volume=self._initial_volume)
        except MPVError as exc:
            self._mpv_error = str(exc)

        # Initialize theme manager
        self._theme_manager = ThemeManager(self)
        try:
            self.query_one("#sidebar", SidebarWidget).update_theme(
                self._theme_manager.get_current_label()
            )
        except QueryError:
            pass

        # Border titles are applied at mount so every main panel is framed on
        # the first rendered frame, rather than waiting for content to arrive.
        for selector, title in (
            ("#sidebar", "Navigation"),
            ("#top-half", "Now Playing / Visualizer"),
            ("#library", "Library / Playlists"),
            ("#queue", "Interactive Queue"),
        ):
            try:
                self.query_one(selector).border_title = title
            except QueryError:
                pass

        self._status(self._ready_message())
        self._apply_layout()
        self._render_queue()
        self._refresh_now()
        self._update_search_input_visibility()

        # Focus queue list by default
        try:
            self.query_one("#queue-list", ListView).focus()
        except QueryError:
            pass

    def shutdown_player(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

    def on_resize(self, event: Resize) -> None:
        self._last_size = (event.size.width, event.size.height)
        self._apply_layout()

    def _apply_layout(self) -> None:
        width, height = self._last_size
        plan = self._engine.plan(width, height, self.mini)
        self._engine.apply_plan(self, plan)

        # Update widget visibility based on plan
        try:
            sidebar = self.query_one("#sidebar")
            sidebar.display = plan.show_sidebar
        except QueryError:
            pass

        try:
            hero = self.query_one("#hero")
            hero.display = True
            hero.compact = plan.compact or plan.mini
        except QueryError:
            pass

        try:
            library = self.query_one("#library")
            library.display = plan.show_library
        except QueryError:
            pass

        try:
            queue = self.query_one("#queue")
            queue.display = plan.show_queue
        except QueryError:
            pass

        try:
            footer = self.query_one("#footer")
            footer.display = plan.show_footer
            footer.compact = plan.mini
            footer.set_context("queue")
        except QueryError:
            pass

        # Update mini mode class on screen
        self.screen.set_class(plan.mini, "mini")
        self.screen.set_class(plan.compact, "compact")

    def _ready_message(self) -> str:
        if self._mpv_error:
            return f"mpv unavailable: {self._mpv_error}"
        if self._service_error:
            return f"auth unavailable: {self._service_error}"
        return "Ready — press / to search, P for playlists, H for history, V for visualizer, T for theme"

    def _status(self, message: str, ttl: float = 6.0) -> None:
        self._status_seq += 1
        seq = self._status_seq
        try:
            self.query_one("#status", Static).update(message)
        except QueryError:
            return
        if ttl > 0:
            self.set_timer(ttl, lambda: self._revert_status(seq))

    def _revert_status(self, seq: int) -> None:
        if seq != self._status_seq:
            return
        try:
            self.query_one("#status", Static).update(self._ready_message())
        except QueryError:
            pass

    def _player_event(self, event: PlayerEvent) -> None:
        try:
            if threading.current_thread() is threading.main_thread():
                self._handle_player_event(event)
            elif self.is_running:
                self.call_from_thread(self._handle_player_event, event)
        except Exception:
            pass

    def _handle_player_event(self, event: PlayerEvent) -> None:
        if event.kind == "status":
            self._status(str(event.data))
        elif event.kind == "volume":
            if isinstance(event.data, (int, float)):
                self._volume = float(event.data)
            self._refresh_now()
        elif event.kind == "playback_mode":
            self._refresh_now()
        elif event.kind == "audio_bitrate":
            self._refresh_now()
        elif event.kind == "audio_codec":
            self._refresh_now()
        elif event.kind == "audio_channels":
            self._refresh_now()
        elif event.kind == "cache_state":
            self._refresh_now()
        elif event.kind == "track":
            # Track changed - auto-cycle visualizer
            self._on_track_change()
            self._refresh_now()
        elif event.kind in ("state", "progress"):
            self._refresh_now()
        elif event.kind == "queue":
            self._render_queue(preserve_index=True)
            self._refresh_now()

    def _refresh_now(self) -> None:
        if self.controller is None:
            return
        try:
            now = self.query_one("#hero")
            now.track = self.controller.current
            now.state = self.controller.state
            now.time_pos = self.controller.time_pos
            now.duration = self.controller.duration
            now.cache_state = self.controller.demuxer_cache_state
            now.volume = self._volume
            now.playback_mode = self.controller.playback_mode
            now.audio_bitrate = getattr(self.controller, "audio_bitrate", None)
            now.audio_codec = getattr(self.controller, "audio_codec", None)
            now.audio_channels = getattr(self.controller, "audio_channels", None)
        except QueryError:
            pass
        try:
            footer = self.query_one("#footer", FooterWidget)
            footer.time_pos = self.controller.time_pos
            footer.duration = self.controller.duration
            footer.state = self.controller.state
            footer.volume = self._volume
        except QueryError:
            pass
        try:
            queue_panel = self.query_one("#queue", QueuePanel)
            queue_panel.current_index = self.controller.index
            queue_panel.state = self.controller.state
        except QueryError:
            pass

    def _render_queue(self, preserve_index: bool = False) -> None:
        if self.controller is None:
            return
        try:
            queue_panel = self.query_one("#queue", QueuePanel)
        except QueryError:
            return
        queue_panel.current_index = self.controller.index
        queue_panel.state = self.controller.state
        queue_panel.queue = list(self.controller.queue)

    def _require_player(self) -> bool:
        if self.controller is None or not self.controller.connected:
            self._status(self._mpv_error or "Player not ready")
            return False
        return True

    # =========================================================================
    # ACTIONS
    # =========================================================================

    def action_focus_search(self) -> None:
        try:
            self.query_one("#search", Input).focus()
            self._focused_panel = "search"
        except QueryError:
            pass

    def action_focus_queue(self) -> None:
        try:
            self.query_one("#queue-list", ListView).focus()
            self._focused_panel = "queue"
        except QueryError:
            pass

    def action_toggle_pause(self) -> None:
        # Space on a selected playlist starts the complete playlist. Space in
        # its track view starts the complete list; elsewhere it remains pause.
        if self._start_selected_playlist("normal"):
            return
        if self._browser_mode == "playlist_tracks" and self._playlist_tracks:
            if self._require_player():
                if (
                    len(self.controller.queue) == len(self._playlist_tracks)
                    and {track.id for track in self.controller.queue}
                    == {track.id for track in self._playlist_tracks}
                    and self.controller.state in (
                        PlayerState.PLAYING,
                        PlayerState.PAUSED,
                        PlayerState.LOADING,
                        PlayerState.BUFFERING,
                    )
                ):
                    self.controller.toggle_pause()
                else:
                    self.controller.play_all(self._playlist_tracks)
            return
        if self._require_player():
            self.controller.toggle_pause()

    def action_next_track(self) -> None:
        if self._require_player():
            self.controller.next()

    def action_prev_track(self) -> None:
        if self._require_player():
            self.controller.previous()

    def action_seek_back(self) -> None:
        if self._require_player():
            self.controller.seek(-5)

    def action_seek_forward(self) -> None:
        if self._require_player():
            self.controller.seek(5)

    def action_volume_up(self) -> None:
        if self._require_player():
            self.controller.adjust_volume(5)

    def action_volume_down(self) -> None:
        if self._require_player():
            self.controller.adjust_volume(-5)

    def action_remove_selected(self) -> None:
        focused = self.focused
        if (
            self.controller is not None
            and focused is not None
            and focused.id == "queue-list"
            and isinstance(focused, ListView)
            and focused.index is not None
        ):
            self.controller.remove_at(focused.index)

    def action_retry_track(self) -> None:
        if self._require_player():
            self.controller.retry()

    def action_toggle_shuffle(self) -> None:
        if self._start_selected_playlist("shuffle"):
            return
        if self._browser_mode == "playlist_tracks" and self._playlist_tracks:
            if self._require_player():
                self.controller.play_shuffled(self._playlist_tracks)
            return
        if self._require_player():
            self.controller.toggle_shuffle()

    def action_clear_queue(self) -> None:
        if self.controller is not None:
            self.controller.clear_queue()

    def action_toggle_mini(self) -> None:
        self.mini = not self.mini
        self._apply_layout()
        self._status("Mini mode on" if self.mini else "Mini mode off")

    def action_play_shuffled(self) -> None:
        if self._start_selected_playlist("shuffle"):
            return
        if self._browser_mode == "playlist_tracks" and self._playlist_tracks and self._require_player():
            self.controller.play_shuffled(self._playlist_tracks)

    def _start_selected_playlist(self, mode: str) -> bool:
        """Load and start the highlighted playlist row when that list is focused."""
        focused = self.focused
        if (
            self._browser_mode != "playlists"
            or focused is None
            or focused.id != "playlists-list"
            or not isinstance(focused, ListView)
            or focused.index is None
            or not (0 <= focused.index < len(self._playlists))
        ):
            return False
        if not self._require_player():
            return True
        playlist = self._playlists[focused.index]
        self._playlist_start_mode = mode
        self._open_playlist(playlist)
        return True

    def action_load_liked(self) -> None:
        if self._service is None:
            self._status(f"Auth unavailable: {self._service_error}")
            return
        self._do_liked()

    def action_show_history(self) -> None:
        if self._history is None:
            self._status("History not available")
            return
        self._browser_mode = "history"
        self._search_input_visible = False
        self._update_search_input_visibility()
        self._update_panel_title()
        self._show_history()

    def action_show_playlists(self) -> None:
        if self._service is None:
            self._status(f"Auth unavailable: {self._service_error}")
            return
        if self._browser_mode == "playlists":
            return
        self._browser_mode = "playlists"
        self._search_input_visible = False
        self._update_search_input_visibility()
        self._update_panel_title()
        self._do_load_playlists()

    def action_cycle_visualizer(self) -> None:
        """Cycle visualizer mode."""
        try:
            hero = self.query_one("#hero", HeroPanel)
            hero.cycle_visualizer()
            self._status(f"Visualizer: {hero.visualizer_mode.name}")
        except QueryError:
            pass

    def action_cycle_theme(self) -> None:
        """Cycle theme."""
        if self._theme_manager:
            new_theme = self._theme_manager.cycle_theme()
            try:
                self.query_one("#sidebar", SidebarWidget).update_theme(
                    self._theme_manager.get_current_label()
                )
            except QueryError:
                pass
            self._status(f"Theme: {self._theme_manager.get_current_label()}")

    def action_move_up_queue(self) -> None:
        if self.controller and self.controller.index > 0:
            # Move current track up in queue
            idx = self.controller.index
            if idx > 0:
                self.controller.queue[idx], self.controller.queue[idx - 1] = \
                    self.controller.queue[idx - 1], self.controller.queue[idx]
                self.controller.index = idx - 1
                self._emit_queue_update()

    def action_move_down_queue(self) -> None:
        if self.controller and self.controller.index >= 0 and self.controller.index + 1 < len(self.controller.queue):
            idx = self.controller.index
            self.controller.queue[idx], self.controller.queue[idx + 1] = \
                self.controller.queue[idx + 1], self.controller.queue[idx]
            self.controller.index = idx + 1
            self._emit_queue_update()

    def _emit_queue_update(self) -> None:
        if self.controller:
            self.controller._emit("queue")

    # =========================================================================
    # SIDEBAR NAVIGATION
    # =========================================================================

    def _on_sidebar_navigate(self, section: str) -> None:
        """Handle sidebar navigation."""
        if section == "search":
            self.action_focus_search()
        elif section == "playlists":
            self.action_show_playlists()
        elif section == "history":
            self.action_show_history()
        elif section == "favorites":
            self.action_load_liked()

    # =========================================================================
    # SEARCH & RESULTS
    # =========================================================================

    def _update_search_input_visibility(self) -> None:
        try:
            search_input = self.query_one("#search", Input)
            search_input.display = self._search_input_visible
            if self._search_input_visible:
                search_input.focus()
        except QueryError:
            pass

    def _update_panel_title(self) -> None:
        titles = {
            "search": "Search",
            "playlists": "Playlists",
            "playlist_tracks": self._playlist_title(),
            "history": "History",
            "liked": "Liked Songs",
        }
        try:
            self.query_one("#library-title", Label).update(titles.get(self._browser_mode, "Library"))
        except QueryError:
            pass

    def _playlist_title(self) -> str:
        for pl in self._playlists:
            if pl.id == self._current_playlist_id:
                return pl.title
        return "Playlist"

    def _show_history(self) -> None:
        if self._history is None:
            self._status("History not available")
            return
        self._browser_mode = "history"
        self._search_input_visible = False
        self._update_search_input_visibility()
        self._update_panel_title()
        self._show_history_results()

    def _show_history_results(self) -> None:
        if self._history is None:
            self._status("History not available")
            return
        try:
            history_entries = self._history.get_recent(limit=50)
        except Exception as exc:
            self._status(f"Failed to load history: {exc}")
            return
        from .ytmusic import Track

        self._history_tracks = [
            Track(
                id=e["video_id"],
                title=e["title"],
                artist=e["artist"],
                album=e["album"],
                duration_s=e["duration_s"],
            )
            for e in history_entries
        ]
        try:
            library = self.query_one("#library", LibraryPanel)
            library.active_tab = "history"
            library.set_history(self._history_tracks)
            self._focus_library_list("#history-list")
        except QueryError:
            pass
        self._status(f"History: {len(self._history_tracks)} entries")

    @on(Input.Submitted, "#search")
    def _on_search_submitted(self, event: Input.Submitted) -> None:
        query = event.value.strip()
        if not query:
            return
        if self._service is None:
            self._status(f"Auth unavailable: {self._service_error}")
            return
        self._do_search(query)

    @work(thread=True, exclusive=True, group="search")
    def _do_search(self, query: str) -> None:
        if self._service is None:
            self._ui_call(self._status, f"Auth unavailable: {self._service_error}")
            return
        try:
            tracks = self._service.search_songs(query)
        except Exception as exc:
            self._ui_call(self._status, f"Search failed: {exc}")
            return
        if tracks:
            note = f"{len(tracks)} results for '{query}'"
        else:
            note = f"No results for '{query}'"
        self._ui_call(self._show_results, tracks, note)

    def _show_results(self, tracks: list[Track], note: str) -> None:
        self._results = tracks
        try:
            library = self.query_one("#library", LibraryPanel)
            library.active_tab = "search"
            library.set_search_results(tracks)
            self._focus_library_list("#search-results-list")
        except QueryError:
            pass
        self._status(note)

    @work(thread=True, exclusive=True, group="library")
    def _do_liked(self) -> None:
        if self._service is None:
            self._ui_call(self._status, f"Auth unavailable: {self._service_error}")
            return
        try:
            tracks = self._service.liked_songs()
        except Exception as exc:
            self._ui_call(self._status, f"Library failed: {exc}")
            return
        note = f"{len(tracks)} liked songs" if tracks else "No liked songs found"
        self._ui_call(self._show_liked, tracks, note)

    def _show_liked(self, tracks: list[Track], note: str) -> None:
        self._liked_tracks = list(tracks)
        try:
            library = self.query_one("#library", LibraryPanel)
            library.active_tab = "liked"
            library.set_liked_tracks(self._liked_tracks)
            self._focus_library_list("#liked-list")
        except QueryError:
            pass
        self._status(note)

    def _ui_call(self, fn: Callable[..., Any], *args: Any) -> None:
        try:
            if threading.current_thread() is threading.main_thread():
                fn(*args)
            elif self.is_running:
                self.call_from_thread(fn, *args)
        except Exception:
            pass

    # =========================================================================
    # PLAYLIST HANDLING
    # =========================================================================

    def _play_track_from_library(self, track: Track) -> None:
        if self.controller:
            self.controller.play_now(track)

    def _goto_queue_index(self, index: int) -> None:
        if self.controller:
            self.controller.goto(index)

    def _remove_from_queue(self, index: int) -> None:
        if self.controller:
            self.controller.remove_at(index)

    @work(thread=True, exclusive=True, group="library")
    def _do_load_playlists(self) -> None:
        if self._service is None:
            self._ui_call(self._status, f"Auth unavailable: {self._service_error}")
            return
        try:
            self._playlists = self._service.get_playlists()
        except Exception as exc:
            self._ui_call(self._status, f"Failed to load playlists: {exc}")
            return
        self._ui_call(self._show_playlists, self._playlists)

    def _show_playlists(self, playlists: list[Playlist]) -> None:
        self._playlists = list(playlists)
        try:
            library = self.query_one("#library", LibraryPanel)
            library.active_tab = "playlists"
            library.set_playlists(self._playlists)
            self._focus_library_list("#playlists-list")
        except QueryError:
            pass
        self._status(f"{len(self._playlists)} playlists")

    def _set_browser_mode(self, mode: str) -> None:
        self._browser_mode = mode
        self._update_panel_title()
        try:
            library = self.query_one("#library", LibraryPanel)
            if mode in ("search", "playlists", "playlist_tracks", "liked", "history"):
                library.active_tab = mode
        except QueryError:
            pass

    def _focus_library_list(self, selector: str) -> None:
        try:
            self.query_one(selector, ListView).focus()
        except QueryError:
            pass

    def _open_playlist(self, playlist: Playlist) -> None:
        self._browser_mode = "playlist_tracks"
        self._current_playlist_id = playlist.id
        self._playlist_tracks = []
        self._search_input_visible = False
        self._update_search_input_visibility()
        self._update_panel_title()
        self._do_load_playlist_tracks(playlist.id)

    @work(thread=True, exclusive=True, group="library")
    def _do_load_playlist_tracks(self, playlist_id: str) -> None:
        if self._service is None:
            self._ui_call(self._status, f"Auth unavailable: {self._service_error}")
            return
        try:
            tracks = self._service.get_playlist_tracks(playlist_id)
        except Exception as exc:
            self._ui_call(self._status, f"Failed to load playlist: {exc}")
            return
        self._ui_call(self._show_playlist_tracks, tracks)

    def _show_playlist_tracks(self, tracks: list[Track]) -> None:
        self._playlist_tracks = list(tracks)
        try:
            library = self.query_one("#library", LibraryPanel)
            title = self._playlist_title()
            library.active_tab = "playlist_tracks"
            library.set_playlist_tracks(self._playlist_tracks, title)
            self._focus_library_list("#playlist-tracks-list")
        except QueryError:
            pass
        self._status(f"{len(self._playlist_tracks)} tracks")
        start_mode = self._playlist_start_mode
        self._playlist_start_mode = None
        if self._playlist_tracks and start_mode and self._require_player():
            if start_mode == "shuffle":
                self.controller.play_shuffled(self._playlist_tracks)
            else:
                self.controller.play_all(self._playlist_tracks)

    def action_browser_back(self) -> None:
        if self._browser_mode == "playlist_tracks":
            self._playlist_start_mode = None
            self._current_playlist_id = None
            self._playlist_tracks = []
            self._search_input_visible = False
            self._update_search_input_visibility()
            self._set_browser_mode("playlists")
            self._refresh_library_playlists()
        elif self._browser_mode in ("playlists", "history", "liked"):
            self._playlists = []
            self._search_input_visible = True
            self._update_search_input_visibility()
            self._set_browser_mode("search")
            self._status(self._ready_message())
        else:
            self.action_focus_queue()

    def _refresh_library_playlists(self) -> None:
        try:
            library = self.query_one("#library", LibraryPanel)
            library.set_playlists(self._playlists)
            self._focus_library_list("#playlists-list")
        except QueryError:
            pass
        self._status(f"{len(self._playlists)} playlists")

    def _on_track_change(self) -> None:
        """Called when track changes - auto-cycle visualizer."""
        try:
            hero = self.query_one("#hero", HeroPanel)
            hero.on_track_change()
        except QueryError:
            pass

    def shutdown_player(self) -> None:
        if self.controller is not None:
            self.controller.shutdown()

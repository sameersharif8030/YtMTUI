from __future__ import annotations

from typing import Callable, Optional

from textual.reactive import reactive
from textual.widgets import Static, Label, ListView, Button
from textual.containers import Vertical, Horizontal

from ..ytmusic import Track, Playlist


class LibraryPanel(Static):
    """Library panel showing search results, playlists, playlist tracks, liked and history."""

    active_tab = reactive("playlists", init=False)
    playlists: list = reactive([], init=False)
    playlist_tracks: list = reactive([], init=False)
    liked_tracks: list = reactive([], init=False)
    history_tracks: list = reactive([], init=False)
    search_results: list = reactive([], init=False)
    selected_playlist_id = reactive(None, init=False)

    TABS = ("search", "playlists", "playlist_tracks", "liked", "history")

    TAB_LABELS = {
        "search": "Search",
        "playlists": "Playlists",
        "playlist_tracks": "Tracks",
        "liked": "Liked",
        "history": "History",
    }

    def __init__(
        self,
        on_play_track: Callable[[Track], None] | None = None,
        on_open_playlist: Callable[[Playlist], None] | None = None,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._on_play_track = on_play_track
        self._on_open_playlist = on_open_playlist
        self._playlists_list: ListView | None = None
        self._playlist_tracks_list: ListView | None = None
        self._liked_list: ListView | None = None
        self._history_list: ListView | None = None
        self._search_results_list: ListView | None = None

    def compose(self):
        with Vertical(id="library-content"):
            with Horizontal(id="library-header"):
                yield Label("Library", id="library-title", classes="library-title")
                with Horizontal(id="library-tabs"):
                    yield Button("Search", id="tab-search", classes="library-tab")
                    yield Button("Playlists", id="tab-playlists", classes="library-tab")
                    yield Button("Tracks", id="tab-playlist_tracks", classes="library-tab")
                    yield Button("Liked", id="tab-liked", classes="library-tab")
                    yield Button("History", id="tab-history", classes="library-tab")
            with Static(id="library-panes"):
                with Static(id="pane-search", classes="library-pane hidden"):
                    yield Label("Search results", id="search-results-title", classes="library-section-title")
                    yield Label("Search for a song to see results here.", id="search-empty", classes="empty-state")
                    yield ListView(id="search-results-list", classes="library-list")
                with Static(id="pane-playlists", classes="library-pane hidden"):
                    yield Label("Playlists", id="playlists-title", classes="library-section-title")
                    yield Label("Your playlists will appear here.", id="playlists-empty", classes="empty-state")
                    yield ListView(id="playlists-list", classes="library-list")
                with Static(id="pane-playlist_tracks", classes="library-pane hidden"):
                    yield Label("Playlist tracks", id="playlist-tracks-title", classes="library-section-title")
                    yield Label("Choose a playlist to view its tracks.", id="tracks-empty", classes="empty-state")
                    yield ListView(id="playlist-tracks-list", classes="library-list")
                with Static(id="pane-liked", classes="library-pane hidden"):
                    yield Label("Liked songs", id="liked-title", classes="library-section-title")
                    yield ListView(id="liked-list", classes="library-list")
                with Static(id="pane-history", classes="library-pane hidden"):
                    yield Label("History", id="history-title", classes="library-section-title")
                    yield ListView(id="history-list", classes="library-list")

    def on_mount(self) -> None:
        self._playlists_list = self.query_one("#playlists-list", ListView)
        self._playlist_tracks_list = self.query_one("#playlist-tracks-list", ListView)
        self._liked_list = self.query_one("#liked-list", ListView)
        self._history_list = self.query_one("#history-list", ListView)
        self._search_results_list = self.query_one("#search-results-list", ListView)
        self._update_tab_visibility()

    def watch_active_tab(self, old: str, new: str) -> None:
        self._update_tab_visibility()

    def _update_tab_visibility(self) -> None:
        try:
            for tab_id in self.TABS:
                try:
                    self.query_one(f"#pane-{tab_id}").display = tab_id == self.active_tab
                except Exception:
                    pass
                try:
                    btn = self.query_one(f"#tab-{tab_id}")
                    if tab_id == self.active_tab:
                        btn.add_class("current")
                    else:
                        btn.remove_class("current")
                except Exception:
                    pass
        except Exception:
            pass

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id and event.button.id.startswith("tab-"):
            tab = event.button.id[4:]
            if tab in self.TABS:
                self.active_tab = tab

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        list_id = event.list_view.id
        index = event.index
        if list_id == "playlists-list":
            if self._on_open_playlist and 0 <= index < len(self.playlists):
                self._on_open_playlist(self.playlists[index])
            return
        mapping = {
            "search-results-list": self.search_results,
            "playlist-tracks-list": self.playlist_tracks,
            "liked-list": self.liked_tracks,
            "history-list": self.history_tracks,
        }
        tracks = mapping.get(list_id or "")
        if self._on_play_track is not None and tracks is not None and 0 <= index < len(tracks):
            self._on_play_track(tracks[index])

    def set_playlists(self, playlists: list[Playlist]) -> None:
        self.playlists = list(playlists)
        self._render_playlists()

    def _render_playlists(self) -> None:
        if self._playlists_list is None:
            return
        self._playlists_list.clear()
        self._set_empty_state("#playlists-empty", not self.playlists)
        if self.playlists:
            from .widgets import _track_item

            items = []
            for pl in self.playlists:
                fake = type("FakeTrack", (), {
                    "line": f"{pl.display_prefix} {pl.title} ({pl.count})",
                    "id": pl.id,
                })()
                items.append(fake)
            self._playlists_list.mount(*[_track_item(t, current=False) for t in items])
            self._playlists_list.index = 0

    def set_playlist_tracks(self, tracks: list[Track], title: str = "Playlist tracks") -> None:
        self.playlist_tracks = list(tracks)
        self._render_playlist_tracks(title)

    def _render_playlist_tracks(self, title: str = "Playlist tracks") -> None:
        try:
            self.query_one("#playlist-tracks-title", Label).update(title)
        except Exception:
            pass
        if self._playlist_tracks_list is None:
            return
        self._playlist_tracks_list.clear()
        self._set_empty_state("#tracks-empty", not self.playlist_tracks)
        if self.playlist_tracks:
            from .widgets import _track_item

            self._playlist_tracks_list.mount(*[_track_item(t) for t in self.playlist_tracks])
            self._playlist_tracks_list.index = 0
            self._playlist_tracks_list.focus()

    def set_liked_tracks(self, tracks: list[Track]) -> None:
        self.liked_tracks = list(tracks)
        self._render_liked()

    def _render_liked(self) -> None:
        if self._liked_list is None:
            return
        self._liked_list.clear()
        if self.liked_tracks:
            from .widgets import _track_item

            self._liked_list.mount(*[_track_item(t) for t in self.liked_tracks])
            self._liked_list.index = 0

    def set_history(self, tracks: list[Track]) -> None:
        self.history_tracks = list(tracks)
        self._render_history()

    def _render_history(self) -> None:
        if self._history_list is None:
            return
        self._history_list.clear()
        if self.history_tracks:
            from .widgets import _track_item

            self._history_list.mount(*[_track_item(t) for t in self.history_tracks])
            self._history_list.index = 0

    def set_search_results(self, tracks: list[Track]) -> None:
        self.search_results = list(tracks)
        self._render_search_results()

    def _render_search_results(self) -> None:
        if self._search_results_list is None:
            return
        self._search_results_list.clear()
        self._set_empty_state("#search-empty", not self.search_results)
        if self.search_results:
            from .widgets import _track_item

            self._search_results_list.mount(*[_track_item(t) for t in self.search_results])
            self._search_results_list.index = 0
            self._search_results_list.focus()

    def _set_empty_state(self, selector: str, visible: bool) -> None:
        try:
            self.query_one(selector).display = visible
        except Exception:
            pass

    def get_selected_playlist(self) -> Optional[Playlist]:
        if self.selected_playlist_id:
            for pl in self.playlists:
                if pl.id == self.selected_playlist_id:
                    return pl
        return None

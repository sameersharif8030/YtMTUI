from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ytmusicapi import YTMusic


@dataclass(frozen=True)
class Track:
    id: str
    title: str
    artist: str
    album: str
    duration_s: int
    source: str = "ytmusic"
    audio_bitrate: int | None = None
    audio_format: str | None = None
    audio_channels: int | None = None
    thumbnail_url: str | None = None

    @property
    def cover_url(self) -> str | None:
        """Return API artwork or YouTube's standard thumbnail URL."""
        if self.thumbnail_url:
            return self.thumbnail_url
        if len(self.id) == 11 and all(char.isalnum() or char in "_-" for char in self.id):
            return f"https://i.ytimg.com/vi/{self.id}/hqdefault.jpg"
        return None

    @property
    def watch_url(self) -> str:
        return f"https://music.youtube.com/watch?v={self.id}"

    @property
    def duration_label(self) -> str:
        minutes, seconds = divmod(max(int(self.duration_s), 0), 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def line(self) -> str:
        artist = self.artist or "Unknown artist"
        album = f" · {self.album}" if self.album else ""
        return f"{self.title} — {artist}{album} ({self.duration_label})"


@dataclass(frozen=True)
class Playlist:
    id: str
    title: str
    count: int
    description: str
    owned: bool
    author: str | None
    is_special: bool

    @property
    def display_prefix(self) -> str:
        if self.is_special:
            return "[PL]"
        return "*" if self.owned else "[PL]"

    @property
    def line(self) -> str:
        count_str = f"({self.count})" if self.count > 0 else ""
        return f"{self.display_prefix} {self.title} {count_str}".strip()


def _to_seconds(value: Any) -> int:
    if isinstance(value, (int, float)):
        return int(value)
    if not value:
        return 0
    total = 0
    found = False
    for part in str(value).split(":"):
        if part.isdigit():
            total = total * 60 + int(part)
            found = True
    return total if found else 0


def _join_names(value: Any) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        names = [item.get("name", "") for item in value if isinstance(item, dict)]
        return ", ".join(name for name in names if name)
    return ""


def _album_name(value: Any) -> str:
    if isinstance(value, dict):
        return value.get("name") or ""
    if isinstance(value, str):
        return value
    return ""


def track_from_item(item: dict[str, Any]) -> Track | None:
    video_id = item.get("videoId")
    if not video_id:
        return None
    artist = _join_names(item.get("artists")) or _join_names(item.get("artist"))
    thumbnails = item.get("thumbnails") or []
    thumbnail_url = None
    if isinstance(thumbnails, list):
        candidates = [
            thumbnail for thumbnail in thumbnails
            if isinstance(thumbnail, dict) and isinstance(thumbnail.get("url"), str)
        ]
        if candidates:
            best = max(
                candidates,
                key=lambda thumb: (thumb.get("width") or 0) * (thumb.get("height") or 0),
            )
            thumbnail_url = best["url"]
    return Track(
        id=video_id,
        title=item.get("title") or "Unknown",
        artist=artist,
        album=_album_name(item.get("album")),
        duration_s=_to_seconds(item.get("duration") or item.get("duration_seconds")),
        audio_bitrate=item.get("bitrate") or item.get("audio_bitrate"),
        audio_format=item.get("audio_format") or item.get("format"),
        audio_channels=item.get("audio_channels") or item.get("channels"),
        thumbnail_url=thumbnail_url,
    )


class YTMusicService:
    def __init__(self, auth_path: Path):
        if not auth_path.exists():
            raise FileNotFoundError(f"missing auth file: {auth_path}")
        self._yt = YTMusic(str(auth_path))

    def search_songs(self, query: str, limit: int = 20) -> list[Track]:
        results = self._yt.search(query, filter="songs", limit=limit) or []
        tracks = [track_from_item(item) for item in results]
        return [track for track in tracks if track is not None]

    def liked_songs(self, limit: int = 50) -> list[Track]:
        response = self._yt.get_liked_songs(limit=limit) or {}
        items = response.get("tracks") or []
        tracks = [track_from_item(item) for item in items]
        return [track for track in tracks if track is not None]

    def get_playlists(self, limit: int = 50) -> list[Playlist]:
        raw = self._yt.get_library_playlists(limit=limit) or []
        playlists = []
        for item in raw:
            pid = item.get("playlistId") or item.get("browseId")
            if not pid:
                continue
            title = item.get("title") or "Unknown"
            count = int(item.get("count") or 0)
            description = item.get("description") or ""
            owned = bool(item.get("owned"))
            author = None
            auth = item.get("author")
            if isinstance(auth, list) and auth:
                author = auth[0].get("name")
            elif isinstance(auth, dict):
                author = auth.get("name")
            is_special = pid in ("LM", "SE") or pid.startswith("LR") or pid.startswith("LS")
            playlists.append(Playlist(
                id=pid,
                title=title,
                count=count,
                description=description,
                owned=owned,
                author=author,
                is_special=is_special,
            ))
        return playlists

    def get_playlist_tracks(self, playlist_id: str, limit: int = 200) -> list[Track]:
        raw = self._yt.get_playlist(playlist_id, limit=limit) or {}
        tracks_raw = raw.get("tracks") or []
        tracks = [track_from_item(item) for item in tracks_raw]
        return [track for track in tracks if track is not None]

    def get_watch_playlist(self, video_id: str, limit: int = 25) -> list[Track]:
        raw = self._yt.get_watch_playlist(video_id, limit=limit) or {}
        tracks_raw = raw.get("tracks") or []
        tracks = [track_from_item(item) for item in tracks_raw]
        return [track for track in tracks if track is not None]

    def get_track_radio(self, video_id: str, limit: int = 20) -> list[Track]:
        """Generate an endless track radio based on the currently playing song."""
        return self.get_watch_playlist(video_id, limit=limit)

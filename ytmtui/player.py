from __future__ import annotations

import random
import time
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable

from .config import DEFAULT_VOLUME, MAX_STREAM_RETRIES
from .history import HistoryCache
from .mpv_ipc import MPVIPC, MPVError, MPVConnectionManager
from .ytmusic import Track

PROP_PAUSE = 1
PROP_TIME_POS = 2
PROP_DURATION = 3
PROP_CORE_IDLE = 4
PROP_VOLUME = 5
PROP_AUDIO_BITRATE = 6
PROP_AUDIO_CODEC = 7
PROP_AUDIO_CHANNELS = 8
PROP_DEMUXER_CACHE_STATE = 9


class PlayerState(Enum):
    IDLE = auto()
    LOADING = auto()
    PLAYING = auto()
    PAUSED = auto()
    BUFFERING = auto()
    ERROR = auto()


class PlaybackMode(Enum):
    NORMAL = auto()
    SHUFFLE = auto()


@dataclass(frozen=True)
class PlayerEvent:
    kind: str
    data: Any = None


class PlaybackController:
    def __init__(
        self,
        emit: Callable[[PlayerEvent], None],
        ytmusic_service=None,
        history_cache: HistoryCache | None = None,
    ):
        self._emit_raw = emit
        self._mpv = MPVConnectionManager(
            on_message=self._on_mpv_message,
            on_reconnect=self._on_mpv_reconnect,
        )
        self.queue: list[Track] = []
        self.index = -1
        self.state = PlayerState.IDLE
        self.time_pos = 0.0
        self.duration = 0.0
        self.retries = 0
        self._last_progress_emit = 0.0
        self._last_emitted_pos = 0.0

        # Playback mode
        self.playback_mode: PlaybackMode = PlaybackMode.NORMAL
        self._shuffle_order: list[int] = []
        self._shuffle_stack: list[int] = []

        # Audio metadata
        self.audio_bitrate: int | None = None
        self.audio_codec: str | None = None
        self.audio_channels: int | None = None
        self.demuxer_cache_state: dict[str, Any] | None = None

        # Auto-mix (track radio)
        self.auto_mix = True
        self._ytmusic = ytmusic_service
        self._history = history_cache or HistoryCache()

        # Volume
        self._volume = 80.0

    @property
    def connected(self) -> bool:
        return self._mpv.connected

    @property
    def current(self) -> Track | None:
        if 0 <= self.index < len(self.queue):
            return self.queue[self.index]
        return None

    def _rebuild_shuffle_order(self) -> None:
        if not self.queue:
            self._shuffle_order = []
            self._shuffle_stack = []
            return
        indices = list(range(len(self.queue)))
        if self.index >= 0:
            # Keep current track at its position in shuffle order
            current_idx = self.index
            indices.remove(current_idx)
            random.shuffle(indices)
            # Insert current index at the front of shuffled order
            self._shuffle_order = [current_idx] + indices
            self._shuffle_stack = [current_idx]
        else:
            random.shuffle(indices)
            self._shuffle_order = indices
            self._shuffle_stack = []

    def start(self, volume: int = DEFAULT_VOLUME) -> None:
        self._mpv.start(volume=volume)
        self._volume = float(volume)
        self._mpv.observe_property(PROP_VOLUME, "volume")
        self._mpv.observe_property(PROP_PAUSE, "pause")
        self._mpv.observe_property(PROP_TIME_POS, "time-pos")
        self._mpv.observe_property(PROP_DURATION, "duration")
        self._mpv.observe_property(PROP_CORE_IDLE, "core-idle")
        self._mpv.observe_property(PROP_VOLUME, "volume")
        # Audio properties may not be available in idle mode; observe lazily
        for prop_id, prop_name in (
            (PROP_AUDIO_BITRATE, "audio-bitrate"),
            (PROP_AUDIO_CODEC, "audio-codec"),
            (PROP_AUDIO_CHANNELS, "audio-params/channel-count"),
            (PROP_DEMUXER_CACHE_STATE, "demuxer-cache-state"),
        ):
            self._mpv.observe_property(prop_id, prop_name)

    def shutdown(self) -> None:
        try:
            self._mpv.stop()
        except Exception:
            pass

    def _emit(self, kind: str, data: Any = None) -> None:
        try:
            self._emit_raw(PlayerEvent(kind, data))
        except Exception:
            pass

    def _set_state(self, state: PlayerState, status: str | None = None) -> None:
        if state is not self.state:
            self.state = state
            self._emit("state", state)
        if status:
            self._emit("status", status)

    def _on_mpv_message(self, message: dict[str, Any]) -> None:
        event = message.get("event")
        if event == "property-change":
            self._on_property_change(message)
        elif event == "end-file":
            self._on_end_file(message)
        elif event == "playback-restart":
            if self.current is not None:
                self.retries = 0
                if self.state is not PlayerState.PAUSED:
                    self._set_state(PlayerState.PLAYING)
        elif event == "__ipc_closed__":
            self._set_state(PlayerState.ERROR, "Lost connection to mpv")
        elif event == "__reconnect_failed__":
            self._set_state(PlayerState.ERROR, "mpv reconnection failed")
        elif event == "__reconnected__":
            self._set_state(PlayerState.LOADING, "Reconnected, restoring playback…")
            if self.current:
                self._mpv.post("loadfile", self.current.watch_url, "replace")
                self._mpv.post("set", "pause", False)

    def _on_mpv_reconnect(self) -> None:
        self._emit("status", "mpv reconnected")
        self._emit("reconnected")

    def enqueue(self, track: Track) -> None:
        if any(queued.id == track.id for queued in self.queue):
            self._emit("status", f"Already queued: {track.title}")
            return
        self.queue.append(track)
        if self.playback_mode is PlaybackMode.SHUFFLE:
            self._rebuild_shuffle_order()
        self._emit("queue")
        self._emit("status", f"Queued: {track.title}")

    def play_now(self, track: Track) -> None:
        for position, queued in enumerate(self.queue):
            if queued.id == track.id:
                self.goto(position)
                return
        position = self.index + 1 if self.index >= 0 else 0
        self.queue.insert(position, track)
        if self.playback_mode is PlaybackMode.SHUFFLE:
            self._rebuild_shuffle_order()
        self._emit("queue")
        self.goto(position)

    def goto(self, index: int) -> None:
        if not (0 <= index < len(self.queue)):
            return
        if self.playback_mode is PlaybackMode.SHUFFLE:
            if not self._shuffle_order:
                self._rebuild_shuffle_order()
            if 0 <= index < len(self._shuffle_order):
                real_index = self._shuffle_order[index]
            else:
                return
        else:
            real_index = index
        if not (0 <= real_index < len(self.queue)):
            return
        self.index = real_index
        self.retries = 0
        self.time_pos = 0.0
        self._last_progress_emit = 0.0
        self._last_emitted_pos = 0.0
        self.demuxer_cache_state = None
        self._emit("cache_state", None)
        track = self.queue[real_index]
        self.duration = float(track.duration_s)
        self._set_state(PlayerState.LOADING, f"Loading {track.title}…")
        self._mpv.post("loadfile", track.watch_url, "replace")
        self._mpv.post("set", "pause", False)
        if self.playback_mode is PlaybackMode.SHUFFLE:
            shuffle_idx = index
            self._shuffle_stack = [shuffle_idx]
        self._emit("track")

    def next(self) -> None:
        if self.playback_mode is PlaybackMode.SHUFFLE:
            if not self._shuffle_order:
                self._rebuild_shuffle_order()
            # Find current position in shuffle order
            try:
                current_shuffle_pos = self._shuffle_order.index(self.index)
            except ValueError:
                current_shuffle_pos = -1
            next_shuffle_pos = current_shuffle_pos + 1
            if next_shuffle_pos < len(self._shuffle_order):
                self.goto(next_shuffle_pos)
            else:
                self._stop_playback("End of queue")
        else:
            if self.index + 1 < len(self.queue):
                self.goto(self.index + 1)
            else:
                self._stop_playback("End of queue")

    def previous(self) -> None:
        if self.playback_mode is PlaybackMode.SHUFFLE:
            if not self._shuffle_order:
                self._rebuild_shuffle_order()
            try:
                current_shuffle_pos = self._shuffle_order.index(self.index)
            except ValueError:
                current_shuffle_pos = -1
            if self.time_pos > 3.0 and current_shuffle_pos >= 0:
                # Restart current track
                self._mpv.post("seek", 0, "absolute")
            elif current_shuffle_pos > 0:
                # Go to previous in shuffle order
                prev_shuffle_pos = current_shuffle_pos - 1
                self.goto(prev_shuffle_pos)
            elif self.current is not None:
                self._mpv.post("seek", 0, "absolute")
        else:
            if self.time_pos > 3.0:
                self._mpv.post("seek", 0, "absolute")
            elif self.index > 0:
                self.goto(self.index - 1)
            elif self.current is not None:
                self._mpv.post("seek", 0, "absolute")

    def remove_at(self, index: int) -> None:
        if not (0 <= index < len(self.queue)):
            return
        removing_current = index == self.index
        self.queue.pop(index)
        if index < self.index:
            self.index -= 1
        if self.playback_mode is PlaybackMode.SHUFFLE:
            self._rebuild_shuffle_order()
        self._emit("queue")
        if removing_current:
            if 0 <= self.index < len(self.queue):
                self.goto(self.index)
            else:
                self._stop_playback("Stopped")

    def toggle_pause(self) -> None:
        if self.state in (PlayerState.IDLE, PlayerState.ERROR):
            return
        self._mpv.post("cycle", "pause")

    def seek(self, delta: float) -> None:
        if self.current is None:
            return
        self._mpv.post("seek", delta, "relative")

    def adjust_volume(self, delta: int) -> None:
        self._mpv.post("add", "volume", delta)

    def retry(self) -> None:
        if self.current is not None:
            self.goto(self.index)

    def toggle_shuffle(self) -> None:
        if self.playback_mode is PlaybackMode.NORMAL:
            self.playback_mode = PlaybackMode.SHUFFLE
            self._rebuild_shuffle_order()
        else:
            self.playback_mode = PlaybackMode.NORMAL
            self._shuffle_order = []
            self._shuffle_stack = []
        self._emit("playback_mode", self.playback_mode)

    def play_shuffled(self, tracks: list[Track]) -> None:
        """Shuffle a playlist into queue order and start the complete queue."""
        if not tracks:
            self._emit("status", "Nothing to shuffle")
            return
        self.queue = list(tracks)
        random.shuffle(self.queue)
        self.playback_mode = PlaybackMode.SHUFFLE
        # Materialize the shuffle in queue order so the visible queue exactly
        # matches what will play next, rather than hiding order in an index map.
        self._shuffle_order = list(range(len(self.queue)))
        self._shuffle_stack = []
        self._emit("queue")
        self.goto(0)
        self._emit("status", f"Playing {len(tracks)} tracks shuffled")

    def play_all(self, tracks: list[Track]) -> None:
        """Replace the queue with a playlist in its original order and play it."""
        if not tracks:
            self._emit("status", "Playlist has no tracks")
            return
        self.queue = list(tracks)
        self.index = -1
        self.playback_mode = PlaybackMode.NORMAL
        self._shuffle_order = []
        self._shuffle_stack = []
        self._emit("queue")
        self.goto(0)
        self._emit("status", f"Playing playlist ({len(tracks)} tracks)")

    def clear_queue(self) -> None:
        self.queue.clear()
        self.index = -1
        self.time_pos = 0.0
        self.duration = 0.0
        self.retries = 0
        self._shuffle_order = []
        self._shuffle_stack = []
        self._mpv.post("stop")
        self._set_state(PlayerState.IDLE, "Queue cleared")
        self._emit("queue")
        self._emit("track")

    def _stop_playback(self, status: str | None = None) -> None:
        self._mpv.post("stop")
        self.index = -1
        self.time_pos = 0.0
        self.duration = 0.0
        self.retries = 0
        self._set_state(PlayerState.IDLE, status)
        self._emit("track")

    def _on_mpv_message(self, message: dict[str, Any]) -> None:
        event = message.get("event")
        if event == "property-change":
            self._on_property_change(message)
        elif event == "end-file":
            self._on_end_file(message)
        elif event == "playback-restart":
            if self.current is not None:
                self.retries = 0
                if self.state is not PlayerState.PAUSED:
                    self._set_state(PlayerState.PLAYING)
        elif event == "__ipc_closed__":
            self._set_state(PlayerState.ERROR, "Lost connection to mpv")

    def _on_property_change(self, message: dict[str, Any]) -> None:
        prop_id = message.get("id")
        data = message.get("data")
        if prop_id == PROP_VOLUME:
            if isinstance(data, (int, float)):
                self._volume = float(data)
                self._emit("volume", float(data))
        elif prop_id == PROP_PAUSE:
            if data is True and self.state in (
                PlayerState.PLAYING,
                PlayerState.BUFFERING,
                PlayerState.LOADING,
            ):
                self._set_state(PlayerState.PAUSED)
            elif data is False and self.state is PlayerState.PAUSED:
                self._set_state(PlayerState.PLAYING)
        elif prop_id == PROP_TIME_POS:
            if isinstance(data, (int, float)):
                self.time_pos = float(data)
                now = time.monotonic()
                if (
                    now - self._last_progress_emit >= 0.2
                    or abs(self.time_pos - self._last_emitted_pos) >= 0.5
                ):
                    self._last_progress_emit = now
                    self._last_emitted_pos = self.time_pos
                    self._emit("progress")
        elif prop_id == PROP_DURATION:
            if isinstance(data, (int, float)) and data > 0:
                self.duration = float(data)
                self._emit("progress")
        elif prop_id == PROP_CORE_IDLE:
            if data is True and self.state is PlayerState.PLAYING:
                self._set_state(PlayerState.BUFFERING)
            elif data is False and self.state is PlayerState.BUFFERING:
                self._set_state(PlayerState.PLAYING)
        elif prop_id == PROP_VOLUME:
            if isinstance(data, (int, float)):
                self._emit("volume", float(data))
        elif prop_id == PROP_AUDIO_BITRATE:
            if isinstance(data, (int, float)):
                self._emit("audio_bitrate", int(data))
        elif prop_id == PROP_AUDIO_CODEC:
            if isinstance(data, str):
                self._emit("audio_codec", data)
        elif prop_id == PROP_AUDIO_CHANNELS:
            if isinstance(data, (int, float)):
                self._emit("audio_channels", int(data))
        elif prop_id == PROP_DEMUXER_CACHE_STATE:
            self.demuxer_cache_state = data if isinstance(data, dict) else None
            self._emit("cache_state", self.demuxer_cache_state)

    def _on_end_file(self, message: dict[str, Any]) -> None:
        reason = message.get("reason") or "error"
        if reason in ("stop", "redirect"):
            return
        if reason == "eof":
            self.retries = 0
            track = self.current
            if track:
                self._history.add(track)
            if self.playback_mode is PlaybackMode.SHUFFLE:
                if not self._shuffle_order:
                    self._rebuild_shuffle_order()
                try:
                    current_shuffle_pos = self._shuffle_order.index(self.index)
                except ValueError:
                    current_shuffle_pos = -1
                next_shuffle_pos = current_shuffle_pos + 1
                if next_shuffle_pos < len(self._shuffle_order):
                    self.goto(next_shuffle_pos)
                else:
                    self._handle_queue_end()
            else:
                if self.index + 1 < len(self.queue):
                    self.goto(self.index + 1)
                else:
                    self._handle_queue_end()
            return
        track = self.current
        if track is None:
            self._set_state(PlayerState.ERROR, "Playback failed")
            return
        if self.retries < MAX_STREAM_RETRIES:
            self.retries += 1
            self._set_state(
                PlayerState.LOADING,
                f"Stream failed, refreshing ({self.retries}/{MAX_STREAM_RETRIES})…",
            )
            self._mpv.post("loadfile", track.watch_url, "replace")
            return
        failed = track.title
        self.retries = 0
        self._emit("status", f"Failed after retries: {failed}")
        if self.playback_mode is PlaybackMode.SHUFFLE:
            if not self._shuffle_order:
                self._rebuild_shuffle_order()
            try:
                current_shuffle_pos = self._shuffle_order.index(self.index)
            except ValueError:
                current_shuffle_pos = -1
            next_shuffle_pos = current_shuffle_pos + 1
            if next_shuffle_pos < len(self._shuffle_order):
                self.goto(next_shuffle_pos)
            else:
                self._handle_queue_end()
        else:
            if self.index + 1 < len(self.queue):
                self.goto(self.index + 1)
            else:
                self._handle_queue_end()

    def _handle_queue_end(self) -> None:
        """Called when queue ends. If auto_mix is enabled, generate track radio."""
        if self.auto_mix and self.current and self._ytmusic:
            self._set_state(PlayerState.LOADING, "Queue ended — generating track radio…")
            try:
                radio_tracks = self._ytmusic.get_track_radio(self.current.id, limit=20)
                for t in radio_tracks:
                    self.enqueue(t)
                if self.queue:
                    self.goto(0)
            except Exception as exc:
                self._emit("status", f"Auto-mix failed: {exc}")
                self._stop_playback("Queue ended")
        else:
            self._stop_playback("End of queue")

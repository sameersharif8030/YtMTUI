from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from .ytmusic import Track

HISTORY_FILE = Path(__file__).resolve().parent.parent / "history.json"
HISTORY_MAX_ENTRIES = 500
HISTORY_MAX_SIZE_MB = 100


class HistoryCache:
    def __init__(self, path: Path = HISTORY_FILE):
        self._path = path
        self._lock = threading.Lock()
        self._data: dict[str, Any] = {"version": 1, "entries": []}
        self._load()

    def _load(self) -> None:
        if self._path.exists():
            try:
                with self._path.open("r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except (json.JSONDecodeError, OSError):
                self._data = {"version": 1, "entries": []}

    def _save(self) -> None:
        tmp = self._path.with_suffix(".tmp")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(self._data, f, ensure_ascii=False, separators=(",", ":"))
            tmp.replace(self._path)
        except OSError:
            if tmp.exists():
                tmp.unlink(missing_ok=True)

    def add(self, track: Track) -> None:
        with self._lock:
            now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
            vid = track.id
            for entry in self._data["entries"]:
                if entry["video_id"] == vid:
                    entry["play_count"] += 1
                    entry["last_played"] = now
                    break
            else:
                self._data["entries"].insert(0, {
                    "video_id": vid,
                    "title": track.title,
                    "artist": track.artist,
                    "album": track.album,
                    "duration_s": track.duration_s,
                    "play_count": 1,
                    "last_played": now,
                })
            # Trim to max entries
            if len(self._data["entries"]) > HISTORY_MAX_ENTRIES:
                self._data["entries"] = self._data["entries"][:HISTORY_MAX_ENTRIES]
            self._save()

    def get_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        with self._lock:
            return self._data["entries"][:limit]

    def search(self, query: str, limit: int = 20) -> list[dict[str, Any]]:
        with self._lock:
            q = query.lower()
            results = [
                e for e in self._data["entries"]
                if q in e["title"].lower() or q in e["artist"].lower()
            ]
            return results[:limit]

    def clear(self) -> None:
        with self._lock:
            self._data["entries"] = []
            self._save()
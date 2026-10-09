from __future__ import annotations

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BROWSER_AUTH = ROOT / "browser.json"
OAUTH_TOKEN = ROOT / "oauth.json"

YTDLP_FORMAT = "bestaudio/best"
DEFAULT_VOLUME = 80
MAX_STREAM_RETRIES = 2
IPC_CONNECT_TIMEOUT = 8.0
COMMAND_TIMEOUT = 5.0


def find_mpv() -> str | None:
    return shutil.which("mpv")


def spawn_env() -> dict[str, str]:
    env = os.environ.copy()
    entries: list[str] = []
    for entry in env.get("PATH", "").split(os.pathsep):
        if not entry.strip():
            continue
        expanded = os.path.expandvars(entry)
        try:
            if os.path.isdir(expanded):
                entries.append(entry)
        except OSError:
            continue
    env["PATH"] = os.pathsep.join(entries)
    return env

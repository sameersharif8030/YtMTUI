from __future__ import annotations

import ctypes
import json
import msvcrt
import os
import subprocess
import threading
import time
import uuid
from collections import deque
from typing import Any, Callable, Optional

from .config import (
    COMMAND_TIMEOUT,
    DEFAULT_VOLUME,
    IPC_CONNECT_TIMEOUT,
    YTDLP_FORMAT,
    find_mpv,
    spawn_env,
)

_KERNEL32 = ctypes.WinDLL("kernel32", use_last_error=True)
_POLL_INTERVAL = 0.01
_RECONNECT_MAX_ATTEMPTS = 3
_RECONNECT_BASE_DELAY = 1.0


def _bytes_available(handle: int) -> int | None:
    remaining = ctypes.c_ulong()
    if not _KERNEL32.PeekNamedPipe(
        handle, None, 0, None, ctypes.byref(remaining), None
    ):
        return None
    return remaining.value


class MPVError(RuntimeError):
    pass


class MPVIPC:
    def __init__(self, on_message: Callable[[dict[str, Any]], None]):
        self._on_message = on_message
        self._pipe = rf"\\.\pipe\ytmtui-{uuid.uuid4().hex}"
        self._proc: subprocess.Popen[bytes] | None = None
        self._fh: Any = None
        self._write_lock = threading.Lock()
        self._pending: dict[int, tuple[threading.Event, dict[str, Any]]] = {}
        self._pending_lock = threading.Lock()
        self._next_request_id = 1
        self._closed = threading.Event()
        self._shutdown_notified = False
        self.stderr_tail: deque[str] = deque(maxlen=40)

    @property
    def connected(self) -> bool:
        return self._fh is not None and not self._closed.is_set()

    @property
    def pipe_name(self) -> str:
        return self._pipe

    def start(self, volume: int = DEFAULT_VOLUME, extra_args: tuple[str, ...] = ()) -> None:
        mpv = find_mpv()
        if not mpv:
            raise MPVError("mpv not found on PATH")
        args = [
            mpv,
            f"--input-ipc-server={self._pipe}",
            "--idle=yes",
            "--no-video",
            "--no-terminal",
            "--msg-level=all=warn",
            f"--ytdl-format={YTDLP_FORMAT}",
            f"--volume={volume}",
            *extra_args,
        ]
        self._proc = subprocess.Popen(
            args,
            env=spawn_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        deadline = time.monotonic() + IPC_CONNECT_TIMEOUT
        last_error: OSError | None = None
        while time.monotonic() < deadline:
            if self._proc.poll() is not None:
                raise MPVError(f"mpv exited with code {self._proc.returncode}")
            try:
                self._fh = open(self._pipe, "r+b", buffering=0)
                break
            except OSError as exc:
                last_error = exc
                time.sleep(0.05)
        if self._fh is None:
            self.stop()
            raise MPVError(f"cannot connect to mpv ipc pipe: {last_error}")
        threading.Thread(target=self._read_loop, name="ytmtui-mpv-ipc", daemon=True).start()
        threading.Thread(target=self._drain_stderr, name="ytmtui-mpv-log", daemon=True).start()

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        for raw in iter(proc.stderr.readline, b""):
            self.stderr_tail.append(raw.decode("utf-8", "replace").rstrip())

    def _read_loop(self) -> None:
        buffer = b""
        try:
            fd = self._fh.fileno()
            handle = msvcrt.get_osfhandle(fd)
            while not self._closed.is_set():
                available = _bytes_available(handle)
                if available is None:
                    break
                if available == 0:
                    time.sleep(_POLL_INTERVAL)
                    continue
                chunk = os.read(fd, min(available, 65536))
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    if not line.strip():
                        continue
                    try:
                        message = json.loads(line)
                    except ValueError:
                        continue
                    self._dispatch(message)
        except (OSError, ValueError):
            pass
        finally:
            self._notify_shutdown()

    def _dispatch(self, message: dict[str, Any]) -> None:
        request_id = message.get("request_id")
        if request_id is not None and ("error" in message or "data" in message):
            with self._pending_lock:
                waiter = self._pending.pop(request_id, None)
            if waiter is not None:
                event, store = waiter
                store.update(message)
                event.set()
                return
        self._on_message(message)

    def _write(self, data: bytes) -> None:
        view = memoryview(data)
        while view:
            written = self._fh.write(view)
            if not written:
                raise OSError("short write to mpv ipc pipe")
            view = view[written:]

    def post(self, *command: Any) -> bool:
        if self._fh is None or self._closed.is_set():
            return False
        payload = json.dumps({"command": list(command)}).encode("utf-8") + b"\n"
        try:
            with self._write_lock:
                self._write(payload)
            return True
        except (OSError, ValueError):
            return False

    def command(self, *command: Any, timeout: float = COMMAND_TIMEOUT) -> Any:
        if self._fh is None or self._closed.is_set():
            raise MPVError("ipc not connected")
        with self._pending_lock:
            request_id = self._next_request_id
            self._next_request_id += 1
            event = threading.Event()
            store: dict[str, Any] = {}
            self._pending[request_id] = (event, store)
        payload = (
            json.dumps({"command": list(command), "request_id": request_id}).encode("utf-8") + b"\n"
        )
        try:
            with self._write_lock:
                self._write(payload)
        except (OSError, ValueError) as exc:
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise MPVError(f"ipc write failed: {exc}") from exc
        if not event.wait(timeout):
            with self._pending_lock:
                self._pending.pop(request_id, None)
            raise TimeoutError(f"mpv command timed out: {command[0]}")
        error = store.get("error")
        if error != "success":
            raise MPVError(f"mpv command failed ({error}): {command[0]}")
        return store.get("data")

    def _notify_shutdown(self) -> None:
        if self._shutdown_notified:
            return
        self._shutdown_notified = True
        self._closed.set()
        with self._pending_lock:
            waiters = list(self._pending.values())
            self._pending.clear()
        for event, store in waiters:
            store.setdefault("error", "connection-lost")
            event.set()
        try:
            self._on_message({"event": "__ipc_closed__"})
        except Exception:
            pass

    def stop(self) -> None:
        if self._proc is None:
            self._notify_shutdown()
            return
        self.post("quit")
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            self._proc.kill()
            try:
                self._proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                pass
        self._notify_shutdown()
        if self._fh is not None:
            try:
                self._fh.close()
            except OSError:
                pass
            self._fh = None


class MPVConnectionManager:
    """Manages mpv process with automatic reconnection."""

    def __init__(
        self,
        on_message: Callable[[dict[str, Any]], None],
        on_reconnect: Optional[Callable[[], None]] = None,
        max_attempts: int = _RECONNECT_MAX_ATTEMPTS,
    ):
        self._on_message = on_message
        self._on_reconnect = on_reconnect
        self._max_attempts = max_attempts
        self._ipc: Optional[MPVIPC] = None
        self._reconnect_attempts = 0
        self._shutdown = False
        self._volume = DEFAULT_VOLUME
        self._observed_properties: list[tuple[int, str]] = []
        self._lock = threading.Lock()

    @property
    def connected(self) -> bool:
        return self._ipc is not None and self._ipc.connected

    @property
    def ipc(self) -> Optional[MPVIPC]:
        return self._ipc

    def start(self, volume: int = DEFAULT_VOLUME) -> None:
        with self._lock:
            self._shutdown = False
            self._reconnect_attempts = 0
            self._volume = volume
            self._spawn_and_connect(volume)

    def _spawn_and_connect(self, volume: int) -> None:
        self._ipc = MPVIPC(self._on_mpv_message)
        self._ipc.start(volume=volume)
        self._reconnect_attempts = 0
        # Re-observe properties
        for prop_id, prop_name in self._observed_properties:
            try:
                self._ipc.command("observe_property", prop_id, prop_name)
            except (TimeoutError, MPVError):
                pass

    def _on_mpv_message(self, message: dict[str, Any]) -> None:
        if message.get("event") == "__ipc_closed__":
            self._handle_disconnect()
        else:
            self._on_message(message)

    def _handle_disconnect(self) -> None:
        if self._shutdown:
            return
        with self._lock:
            if self._shutdown:
                return
            self._reconnect_attempts += 1
            if self._reconnect_attempts > self._max_attempts:
                self._on_message({"event": "__reconnect_failed__"})
                return
            delay = _RECONNECT_BASE_DELAY * (2 ** (self._reconnect_attempts - 1))
            threading.Timer(delay, self._attempt_reconnect).start()

    def _attempt_reconnect(self) -> None:
        with self._lock:
            if self._shutdown:
                return
            try:
                self._spawn_and_connect(self._volume)
                if self._on_reconnect:
                    self._on_reconnect()
            except (MPVError, OSError):
                self._handle_disconnect()

    def post(self, *command: Any) -> bool:
        with self._lock:
            if self._ipc is None:
                return False
            return self._ipc.post(*command)

    def command(self, *command: Any, timeout: float = COMMAND_TIMEOUT) -> Any:
        with self._lock:
            if self._ipc is None:
                raise MPVError("ipc not connected")
            return self._ipc.command(*command, timeout=timeout)

    def observe_property(self, prop_id: int, prop_name: str) -> None:
        with self._lock:
            if (prop_id, prop_name) not in self._observed_properties:
                self._observed_properties.append((prop_id, prop_name))
            if self._ipc and self._ipc.connected:
                try:
                    self._ipc.command("observe_property", prop_id, prop_name)
                except (TimeoutError, MPVError):
                    pass

    def stop(self) -> None:
        with self._lock:
            self._shutdown = True
            if self._ipc:
                self._ipc.stop()
                self._ipc = None

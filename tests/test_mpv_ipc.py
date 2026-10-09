import asyncio
import time

from ytmtui.player import PlaybackController, PlayerState
from ytmtui.ytmusic import Track

TRACK = Track(
    id="vXZHHg823ro",
    title="Kerosene",
    artist="Crystal Castles",
    album="Crystal Castles II",
    duration_s=192,
)


async def wait_for(predicate, timeout: float, what: str) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        await asyncio.sleep(0.15)
    raise AssertionError(f"timed out waiting for: {what}")


async def main() -> None:
    events = []
    controller = PlaybackController(events.append)
    controller.start(volume=0)
    try:
        controller.play_now(TRACK)
        assert len(controller.queue) == 1
        assert controller.index == 0

        await wait_for(
            lambda: controller.state is PlayerState.PLAYING and controller.time_pos > 1,
            60,
            "playing with time_pos > 1",
        )

        controller.toggle_pause()
        await wait_for(
            lambda: controller.state is PlayerState.PAUSED,
            5,
            "paused after toggle",
        )

        controller.toggle_pause()
        await wait_for(
            lambda: controller.state is PlayerState.PLAYING,
            5,
            "playing after second toggle",
        )

        paused_at = controller.time_pos
        controller.seek(10)
        await wait_for(
            lambda: controller.time_pos >= paused_at + 8,
            5,
            "seek forward applied",
        )

        controller.adjust_volume(-5)
        await asyncio.sleep(0.5)

        controller.next()
        assert controller.index == -1
        assert controller.state is PlayerState.IDLE

        assert any(event.kind == "state" for event in events), "state events emitted"
        assert any(event.kind == "progress" for event in events), "progress events emitted"
    finally:
        controller.shutdown()

    await wait_for(lambda: not controller.connected, 5, "mpv shutdown")
    print("mpv ipc test OK")


if __name__ == "__main__":
    asyncio.run(main())

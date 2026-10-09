import asyncio

from textual.widgets import Input, ListView

from ytmtui.app import YtMTUI
from ytmtui.ytmusic import Track, YTMusicService

FAKE_TRACKS = [
    Track(id=f"fake{i}", title=f"Song {i}", artist=f"Artist {i}", album="Album", duration_s=90 + i)
    for i in range(5)
]


def patch_service() -> None:
    YTMusicService.search_songs = lambda self, query, limit=20: list(FAKE_TRACKS)  # type: ignore[method-assign]


async def wait_for_results(library, expected_count: int, timeout: float = 2.0) -> ListView:
    """Wait for search results to appear."""
    start = asyncio.get_event_loop().time()
    while asyncio.get_event_loop().time() - start < timeout:
        try:
            results = library.query_one("#search-results-list", ListView)
            if len(results.children) >= expected_count:
                return results
        except Exception:
            pass
        await asyncio.sleep(0.05)
    raise AssertionError(f"Timeout waiting for {expected_count} results")


async def main() -> None:
    patch_service()
    app = YtMTUI(volume=0)
    try:
        async with app.run_test(size=(120, 40)) as pilot:
            await pilot.pause()
            assert app.controller is not None, "controller missing"

            # All four framed dashboard panels must be laid out immediately.
            expected_panels = {
                "#sidebar": "Navigation",
                "#top-half": "Now Playing / Visualizer",
                "#library": "Library / Playlists",
                "#queue": "Interactive Queue",
            }
            for selector, title in expected_panels.items():
                panel = app.query_one(selector)
                assert panel.size.width > 0 and panel.size.height > 0, (
                    selector, panel.size
                )
                assert panel.border_title == title, (selector, panel.border_title)

            # Focus search input directly
            search_input = app.query_one("#search", Input)
            search_input.focus()
            await pilot.pause()
            assert app.focused is not None and app.focused.id == "search", (
                app.focused
            )

            for char in "test":
                await pilot.press(char)
            await pilot.press("enter")
            await asyncio.sleep(0.5)
            await pilot.pause()

            # Results are now in the library panel's search results pane
            library = app.query_one("#library")
            # Wait for search results to be mounted
            results = await wait_for_results(library, 5)
            assert app.focused is not None and app.focused.id == "search-results-list", (
                app.focused
            )

            mpv = app.controller._mpv
            original_post = mpv.post

            def fake_post(*command):
                if command and command[0] == "loadfile":
                    return True
                return original_post(*command)

            mpv.post = fake_post

            await pilot.press("enter")
            await asyncio.sleep(0.3)
            await pilot.pause()
            assert len(app.controller.queue) == 1, app.controller.queue
            assert app.controller.index == 0

            queue_items = app.query_one("#queue").children
            assert len(queue_items) == 1

            await pilot.press("m")
            await pilot.pause()
            # In mini mode, sidebar, library, and queue should be hidden
            assert not app.query_one("#sidebar").display, "sidebar should hide in mini mode"
            assert not app.query_one("#library").display, "library should hide in mini mode"
            assert not app.query_one("#queue").display, "queue should hide in mini mode"

            await pilot.press("m")
            await pilot.pause()
            assert app.query_one("#sidebar").display, "sidebar should return"
            assert app.query_one("#library").display, "library should return"
            assert app.query_one("#queue").display, "queue should return"

            await pilot.resize_terminal(70, 30)
            await pilot.pause()
            assert app.screen.has_class("compact"), "narrow should be compact"
            assert app.screen.has_class("sidebar-hidden"), "narrow should hide sidebar"

            await pilot.resize_terminal(120, 40)
            await pilot.pause()
            assert not app.screen.has_class("compact"), "wide should not be compact"
            assert app.screen.has_class("sidebar-visible"), "wide should show sidebar"

            await pilot.press("escape")
            await pilot.pause()
            assert app.focused is not None and app.focused.id == "queue-list", (
                app.focused
            )
        print("smoke test OK")
    finally:
        app.shutdown_player()


if __name__ == "__main__":
    asyncio.run(main())

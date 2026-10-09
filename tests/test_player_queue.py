from __future__ import annotations

from ytmtui.player import PlaybackController, PlaybackMode
from ytmtui.ytmusic import Track


class FakeMPV:
    def __init__(self) -> None:
        self.commands: list[tuple] = []

    def post(self, *command) -> bool:
        self.commands.append(command)
        return True


def make_tracks() -> list[Track]:
    return [
        Track(id=f"track-{i}", title=f"Track {i}", artist="Artist", album="Album", duration_s=120)
        for i in range(4)
    ]


def make_controller() -> tuple[PlaybackController, FakeMPV]:
    controller = PlaybackController(lambda _event: None)
    fake_mpv = FakeMPV()
    controller._mpv = fake_mpv  # type: ignore[assignment]
    return controller, fake_mpv


def test_play_all_queues_every_song_in_playlist_order() -> None:
    controller, fake_mpv = make_controller()
    tracks = make_tracks()

    controller.play_all(tracks)
    controller.next()

    assert controller.queue == tracks
    assert controller.index == 1
    assert controller.playback_mode is PlaybackMode.NORMAL
    loaded = [command[1] for command in fake_mpv.commands if command[0] == "loadfile"]
    assert loaded == [tracks[0].watch_url, tracks[1].watch_url]


def test_play_shuffled_displays_and_plays_the_same_order(monkeypatch) -> None:
    controller, fake_mpv = make_controller()
    tracks = make_tracks()
    monkeypatch.setattr("ytmtui.player.random.shuffle", lambda items: items.reverse())

    controller.play_shuffled(tracks)
    displayed_order = list(controller.queue)
    controller.next()

    assert displayed_order == list(reversed(tracks))
    assert controller.playback_mode is PlaybackMode.SHUFFLE
    assert controller.index == 1
    loaded = [command[1] for command in fake_mpv.commands if command[0] == "loadfile"]
    assert loaded == [displayed_order[0].watch_url, displayed_order[1].watch_url]

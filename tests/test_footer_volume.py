from types import SimpleNamespace

from ytmtui.app import YtMTUI
from ytmtui.player import PlaybackMode, PlayerState


class DummyWidget:
    pass


def test_app_refresh_syncs_player_volume_to_footer() -> None:
    hero = DummyWidget()
    footer = DummyWidget()
    queue = DummyWidget()
    controller = SimpleNamespace(
        current=None,
        state=PlayerState.IDLE,
        time_pos=0.0,
        duration=0.0,
        demuxer_cache_state=None,
        playback_mode=PlaybackMode.NORMAL,
        audio_bitrate=None,
        audio_codec=None,
        audio_channels=None,
        index=-1,
    )
    widgets = {"#hero": hero, "#footer": footer, "#queue": queue}
    app = SimpleNamespace(
        controller=controller,
        _volume=37.0,
        query_one=lambda selector, *_args: widgets[selector],
    )

    YtMTUI._refresh_now(app)

    assert footer.volume == 37.0
    assert hero.volume == 37.0

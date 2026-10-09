from ytmtui.ui.hero import buffered_until


def test_buffered_until_uses_contiguous_range_at_playhead() -> None:
    cache = {
        "seekable-ranges": [
            {"start": 0.0, "end": 42.0},
            {"start": 58.0, "end": 95.0},
        ]
    }

    assert buffered_until(cache, 30.0) == 42.0
    assert buffered_until(cache, 50.0) is None


def test_buffered_until_falls_back_to_cache_end_and_ignores_stale_data() -> None:
    assert buffered_until({"cache-end": 75.0}, 40.0) == 75.0
    assert buffered_until({"cache-end": 40.0}, 40.0) is None
    assert buffered_until(None, 10.0) is None

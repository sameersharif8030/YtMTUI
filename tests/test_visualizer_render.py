from ytmtui.ui.visualizer import VisualizerMode, VisualizerWidget


def test_full_size_modes_render_centerpiece_artwork() -> None:
    widget = VisualizerWidget()
    widget._rotation = 0.4

    renderers = {
        VisualizerMode.TURNTABLE: widget._render_vinyl(60),
        VisualizerMode.SPECTRUM: widget._render_spectrum(60, 12),
        VisualizerMode.CASSETTE: widget._render_cassette(60),
        VisualizerMode.SOUNDWAVE: widget._render_waveform(60, 12),
    }
    for mode, frame in renderers.items():
        assert len(frame.plain) > 30, mode
        assert "\n" in frame.plain, mode

    assert "●" in renderers[VisualizerMode.TURNTABLE].plain
    assert "█" in renderers[VisualizerMode.SPECTRUM].plain
    assert "╭" in renderers[VisualizerMode.CASSETTE].plain
    assert "━" in renderers[VisualizerMode.SOUNDWAVE].plain


def test_vinyl_marker_moves_when_rotation_changes() -> None:
    widget = VisualizerWidget()
    widget.playing = True
    widget._rotation = 0.0
    first = widget._render_vinyl(60).plain
    widget._rotation = 1.5
    second = widget._render_vinyl(60).plain

    assert first != second
    assert first.count("◆") == 1
    assert second.count("◆") == 1


def test_compact_visualizer_modes_stay_single_line() -> None:
    widget = VisualizerWidget()
    for mode in VisualizerMode:
        widget.mode = mode
        frame = widget._render_compact(18)
        assert "\n" not in frame.plain
        assert frame.plain

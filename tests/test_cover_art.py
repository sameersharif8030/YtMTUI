import io

import pytest

from ytmtui.ui.cover_art import image_bytes_to_pixels, render_pixels
from ytmtui.ytmusic import track_from_item


def _gradient_grid(size: int = 32):
    return tuple(
        tuple(((x * 7) % 256, (y * 8) % 256, ((x + y) * 4) % 256) for x in range(size))
        for y in range(size)
    )


def test_32_pixel_square_renders_as_32_columns_by_16_half_block_rows() -> None:
    rendered = render_pixels(_gradient_grid())
    lines = rendered.plain.splitlines()

    assert len(lines) == 16
    assert all(len(line) == 32 and set(line) == {"▀"} for line in lines)
    assert rendered.get_style_at(0).color is not None
    assert rendered.get_style_at(0).bgcolor is not None


def test_art_downscales_square_to_fit_short_panel_without_clipping() -> None:
    rendered = render_pixels(_gradient_grid(), max_columns=18, max_rows=18)
    lines = rendered.plain.splitlines()

    assert len(lines) == 9
    assert all(len(line) == 18 for line in lines)


def test_cover_image_decodes_to_32_by_32_rgb_grid() -> None:
    Image = pytest.importorskip("PIL.Image")
    image = Image.new("RGB", (8, 4))
    for x in range(8):
        for y in range(4):
            image.putpixel((x, y), (x * 30, y * 50, 120))
    stream = io.BytesIO()
    image.save(stream, format="PNG")

    pixels = image_bytes_to_pixels(stream.getvalue())
    assert len(pixels) == 32
    assert all(len(row) == 32 for row in pixels)


def test_track_selects_largest_thumbnail_and_has_youtube_fallback() -> None:
    track = track_from_item({
        "videoId": "sample-id",
        "title": "Sample",
        "artists": [{"name": "Artist"}],
        "thumbnails": [
            {"url": "https://img.example/small.jpg", "width": 60, "height": 60},
            {"url": "https://img.example/large.jpg", "width": 400, "height": 400},
        ],
    })
    assert track is not None
    assert track.cover_url == "https://img.example/large.jpg"

    fallback = track_from_item({"videoId": "fallback123", "title": "Fallback"})
    assert fallback is not None
    assert fallback.cover_url == "https://i.ytimg.com/vi/fallback123/hqdefault.jpg"

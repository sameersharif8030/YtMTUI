from __future__ import annotations

import io
import urllib.request
from collections import OrderedDict
from typing import TypeAlias

from rich.style import Style
from rich.text import Text
from textual import work
from textual.reactive import reactive
from textual.widgets import Static

RGB: TypeAlias = tuple[int, int, int]
PixelGrid: TypeAlias = tuple[tuple[RGB, ...], ...]
_ASCII_CACHE: OrderedDict[str, PixelGrid] = OrderedDict()
_CACHE_LIMIT = 64
_IMAGE_PIXELS = 32
_MAX_IMAGE_BYTES = 5 * 1024 * 1024


def image_bytes_to_pixels(image_bytes: bytes, size: int = _IMAGE_PIXELS) -> PixelGrid:
    """Decode, square-crop, and downsample a cover to a small RGB pixel grid."""
    from PIL import Image, ImageOps

    with Image.open(io.BytesIO(image_bytes)) as source:
        rgba = source.convert("RGBA")
        backdrop = Image.new("RGBA", rgba.size, (30, 30, 46, 255))
        rgb = Image.alpha_composite(backdrop, rgba).convert("RGB")
        image = ImageOps.fit(
            rgb,
            (max(1, size), max(1, size)),
            method=Image.Resampling.LANCZOS,
            centering=(0.5, 0.5),
        )
        pixels = image.load()
        return tuple(
            tuple(tuple(int(channel) for channel in pixels[x, y]) for x in range(image.width))
            for y in range(image.height)
        )


def _sample_grid(grid: PixelGrid, width: int, height: int) -> PixelGrid:
    """Nearest-sample the cached square grid to the visible pixel dimensions."""
    if not grid or not grid[0] or width <= 0 or height <= 0:
        return ()
    source_height, source_width = len(grid), len(grid[0])
    return tuple(
        tuple(
            grid[min(source_height - 1, int((y + 0.5) * source_height / height))][
                min(source_width - 1, int((x + 0.5) * source_width / width))
            ]
            for x in range(width)
        )
        for y in range(height)
    )


def render_pixels(grid: PixelGrid, max_columns: int = _IMAGE_PIXELS, max_rows: int = _IMAGE_PIXELS) -> Text:
    """Render two vertically stacked RGB pixels per terminal cell with `▀`."""
    if not grid or not grid[0]:
        return Text()
    pixel_size = min(_IMAGE_PIXELS, max_columns, max_rows)
    if pixel_size <= 0:
        return Text()
    pixels = _sample_grid(grid, pixel_size, pixel_size)
    text = Text(no_wrap=True)
    for y in range(0, pixel_size, 2):
        if y:
            text.append("\n")
        lower_y = min(y + 1, pixel_size - 1)
        for x in range(pixel_size):
            top = pixels[y][x]
            bottom = pixels[lower_y][x]
            style = Style(
                color=f"#{top[0]:02x}{top[1]:02x}{top[2]:02x}",
                bgcolor=f"#{bottom[0]:02x}{bottom[1]:02x}{bottom[2]:02x}",
            )
            text.append("▀", style=style)
    return text


def _download_and_convert(url: str) -> PixelGrid:
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "Mozilla/5.0 (compatible; YtMTUI/1.0)", "Accept": "image/*"},
    )
    with urllib.request.urlopen(request, timeout=6) as response:
        content_type = response.headers.get("Content-Type", "")
        if not content_type.lower().startswith("image/"):
            raise ValueError("Thumbnail URL did not return an image")
        data = response.read(_MAX_IMAGE_BYTES + 1)
    if len(data) > _MAX_IMAGE_BYTES:
        raise ValueError("Thumbnail exceeds size limit")
    return image_bytes_to_pixels(data)


class CoverArtWidget(Static):
    """Colored square terminal pixel-art cover with session caching."""

    track_id = reactive[str | None](None, init=False)

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._pixels: PixelGrid | None = None
        self._failed = False

    def render(self) -> Text:
        if self._pixels is not None:
            # Preserve a square image and fit whatever height the hero actually
            # has. Each half-block cell displays two vertical pixels.
            pixel_limit = min(_IMAGE_PIXELS, max(self.size.width, 1), max(self.size.height * 2, 1))
            return render_pixels(self._pixels, max_columns=pixel_limit, max_rows=pixel_limit)
        try:
            palette = self.app.get_css_variables()
        except Exception:
            palette = {}
        muted = palette.get("muted", "#a6adc8")
        accent = palette.get("accent", "#89dceb")
        if self._failed:
            return Text("ART\nUNAVAILABLE", style=muted, justify="center")
        return Text("♪\nCOVER\nART", style=f"bold {accent}", justify="center")

    def load_track(self, track_id: str, url: str | None) -> None:
        self.track_id = track_id
        self._pixels = _ASCII_CACHE.get(url or "")
        if self._pixels is not None and url:
            _ASCII_CACHE.move_to_end(url)
        self._failed = False
        self.refresh()
        if not url:
            self._failed = True
            self.refresh()
        elif self._pixels is None:
            self._load_cover(track_id, url)

    @work(thread=True, exclusive=True, group="cover-art")
    def _load_cover(self, track_id: str, url: str) -> None:
        try:
            pixels = _ASCII_CACHE.get(url)
            if pixels is None:
                pixels = _download_and_convert(url)
                _ASCII_CACHE[url] = pixels
                _ASCII_CACHE.move_to_end(url)
                while len(_ASCII_CACHE) > _CACHE_LIMIT:
                    _ASCII_CACHE.popitem(last=False)
            self.app.call_from_thread(self._set_cover, track_id, pixels)
        except Exception:
            try:
                self.app.call_from_thread(self._set_unavailable, track_id)
            except Exception:
                pass

    def _set_cover(self, track_id: str, pixels: PixelGrid) -> None:
        if self.track_id != track_id:
            return
        self._pixels = pixels
        self._failed = False
        self.refresh()

    def _set_unavailable(self, track_id: str) -> None:
        if self.track_id != track_id:
            return
        self._pixels = None
        self._failed = True
        self.refresh()

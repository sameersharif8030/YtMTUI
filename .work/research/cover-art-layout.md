# Album art rendering research and chosen implementation

## Findings

- Rich supports per-character foreground and background colors, including full RGB/truecolor; terminal support may fall back to a smaller palette. Source: https://rich.readthedocs.io/en/latest/style.html
- Textual widgets may return Rich renderables such as `rich.text.Text` from `render()`, allowing existing custom widgets to build color-styled output without a new terminal framework. Source: https://textual.textualize.io/guide/content/
- PIXterm renders image pixels with ANSI color and Unicode half-blocks; it notes that accurate color requires truecolor support and a compatible monospaced font. Source: https://github.com/eliukblau/pixterm
- Kitty graphics protocol can show raster images but requires emulator-specific protocol support; protocol codes are ignored by most terminals, so it is a less portable default for this Textual app. Source: https://sw.kovidgoyal.net/kitty/graphics-protocol/
- The current code maps pixels to luminance ASCII glyphs, reducing color detail and making album art difficult to recognize. The hero has four columns (visualizer, metadata, static spectrum, cover); the current right cover is only one fractional column. Queue CSS shows up to six rows, and the bottom workspace currently occupies half the available height.

## Selected visual logic

Use a standard colored Unicode half-block (`▀`) rather than density-mapped letters. A 32-by-32 RGB thumbnail is rendered as 32 terminal columns by 16 text rows: each cell displays the upper pixel in its foreground color and the lower pixel in its background color. This preserves a square image at typical terminal cell proportions, uses two colors per character cell, and stays within Textual/Rich instead of requiring Kitty/Sixel support.

Place the cover as a fixed approximately 34-cell right column in the full-size Now Playing hero. Remove the redundant static spectrum side-column; the animated visualizer already has a spectrum mode. Split the remaining hero width between visualizer and metadata, retaining the playback timeline beneath. Hide cover art in compact/mini layouts.

Give the upper hero about 65% of the workspace height and bottom library/queue about 35%; set the visible queue viewport to five rows (current song plus four upcoming) while retaining scroll access to the full queue. This yields room for the 16-row artwork in normal-height terminals without removing the library or queue.

## Compatibility and safety

- Keep image fetch off the UI thread and retain size limits, timeout, stale-track protection, and session cache.
- Keep Pillow as the decoder dependency already declared by the feature.
- Fit/crop the source square, downsample to 32x32 with Lanczos, and render paired RGB colors. For shorter panels, scale the square pixel grid down to the available widget cell dimensions to avoid clipping.
- Preserve text-mode fallback and hide art at compact widths.

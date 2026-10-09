from __future__ import annotations

from textual.reactive import reactive
from textual.widgets import Static
from rich.text import Text


class KeycapWidget(Static):
    """A keycap-styled button badge for footer hints."""

    key = reactive("", init=False)
    label = reactive("", init=False)
    compact = reactive(False, init=False)

    DEFAULT_CSS = """
    KeycapWidget {
        background: $accent;
        border: none;
        color: $active_fg;
        padding: 0 1;
        margin: 0 1;
        text-style: bold;
        min-width: 6;
        height: 3;
        content-align: center middle;
        layout: horizontal;
    }
    KeycapWidget:focus {
        background: $queue;
        color: $active_fg;
        border: none;
    }
    KeycapWidget.compact {
        height: 2;
        min-width: 4;
        padding: 0;
    }
    """

    def __init__(self, key: str, label: str = "", compact: bool = False, **kwargs):
        super().__init__(**kwargs)
        self.key = key
        self.label = label
        self.compact = compact

    def render(self) -> Text:
        text = Text()
        # Key text
        text.append(f" {self.key} ", style="bold")
        # Label
        if self.label and not self.compact:
            text.append(f" {self.label}", style="dim")
        return text

    def watch_compact(self, old: bool, new: bool) -> None:
        self.set_class(new, "compact")

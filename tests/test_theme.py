from ytmtui.theme import THEME_PALETTES, ThemeManager


class FakeScreen:
    def __init__(self) -> None:
        self.classes: set[str] = set()

    def set_class(self, enabled: bool, name: str) -> None:
        if enabled:
            self.classes.add(name)
        else:
            self.classes.discard(name)


class FakeApp:
    def __init__(self) -> None:
        self.screen = FakeScreen()
        self.refreshes = 0

    def refresh_css(self, animate: bool = True) -> None:
        self.refreshes += 1


def test_every_theme_has_complete_palette() -> None:
    required = {
        "bg", "surface", "surface_alt", "text", "muted", "accent",
        "green", "queue", "border", "selection", "footer_bg",
        "active_bg", "active_fg",
    }
    assert all(required <= palette.keys() for palette in THEME_PALETTES.values())


def test_cycle_applies_next_palette_and_refreshes_styles() -> None:
    app = FakeApp()
    manager = ThemeManager(app)  # type: ignore[arg-type]

    assert manager.cycle_theme() == "gruvbox"
    assert "theme-gruvbox" in app.screen.classes
    assert "theme-catppuccin" not in app.screen.classes
    assert app.refreshes == 1

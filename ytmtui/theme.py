from __future__ import annotations

from textual.app import App


THEME_PALETTES: dict[str, dict[str, str]] = {
    "catppuccin": {
        "bg": "#1e1e2e", "surface": "#181825", "surface_alt": "#313244",
        "text": "#cdd6f4", "muted": "#6c7086", "accent": "#89dceb",
        "green": "#a6e3a1", "queue": "#f5c2e7", "border": "#45475a",
        "selection": "#45475a", "footer_bg": "#11111b",
        "active_bg": "#89dceb", "active_fg": "#11111b",
    },
    "gruvbox": {
        "bg": "#282828", "surface": "#32302f", "surface_alt": "#3c3836",
        "text": "#ebdbb2", "muted": "#a89984", "accent": "#83a598",
        "green": "#b8bb26", "queue": "#d3869b", "border": "#504945",
        "selection": "#504945", "footer_bg": "#1d2021",
        "active_bg": "#83a598", "active_fg": "#1d2021",
    },
    "cyberpunk": {
        "bg": "#0b1021", "surface": "#151a30", "surface_alt": "#222944",
        "text": "#f8f8f2", "muted": "#8b90a7", "accent": "#00f5ff",
        "green": "#00ff9f", "queue": "#ff2bd6", "border": "#343a5a",
        "selection": "#343a5a", "footer_bg": "#070b18",
        "active_bg": "#00f5ff", "active_fg": "#0b1021",
    },
    "nord": {
        "bg": "#2e3440", "surface": "#3b4252", "surface_alt": "#434c5e",
        "text": "#eceff4", "muted": "#a3be8c", "accent": "#88c0d0",
        "green": "#a3be8c", "queue": "#b48ead", "border": "#4c566a",
        "selection": "#4c566a", "footer_bg": "#242933",
        "active_bg": "#88c0d0", "active_fg": "#2e3440",
    },
    "tokyonight": {
        "bg": "#1a1b26", "surface": "#16161e", "surface_alt": "#24283b",
        "text": "#c0caf5", "muted": "#565f89", "accent": "#7aa2f7",
        "green": "#9ece6a", "queue": "#bb9af7", "border": "#3b4261",
        "selection": "#3b4261", "footer_bg": "#13131a",
        "active_bg": "#7aa2f7", "active_fg": "#1a1b26",
    },
    "solarized": {
        "bg": "#002b36", "surface": "#073642", "surface_alt": "#094451",
        "text": "#839496", "muted": "#586e75", "accent": "#2aa198",
        "green": "#859900", "queue": "#d33682", "border": "#31545c",
        "selection": "#31545c", "footer_bg": "#00212b",
        "active_bg": "#2aa198", "active_fg": "#002b36",
    },
    "monokai": {
        "bg": "#272822", "surface": "#1e1f1c", "surface_alt": "#3e3d32",
        "text": "#f8f8f2", "muted": "#75715e", "accent": "#66d9ef",
        "green": "#a6e22e", "queue": "#f92672", "border": "#49483e",
        "selection": "#49483e", "footer_bg": "#191a16",
        "active_bg": "#66d9ef", "active_fg": "#272822",
    },
    "everforest": {
        "bg": "#2d353b", "surface": "#343f44", "surface_alt": "#3d484d",
        "text": "#d3c6aa", "muted": "#859289", "accent": "#7fbbb3",
        "green": "#a7c080", "queue": "#d699b6", "border": "#4a555b",
        "selection": "#4a555b", "footer_bg": "#272f34",
        "active_bg": "#7fbbb3", "active_fg": "#2d353b",
    },
    "rosepine": {
        "bg": "#191724", "surface": "#1f1d2e", "surface_alt": "#26233a",
        "text": "#e0def4", "muted": "#6e6a86", "accent": "#9ccfd8",
        "green": "#31748f", "queue": "#ebbcba", "border": "#403d52",
        "selection": "#403d52", "footer_bg": "#14121f",
        "active_bg": "#9ccfd8", "active_fg": "#191724",
    },
}


class ThemeManager:
    """Manages live theme palettes applied to Textual CSS variables."""

    THEMES = list(THEME_PALETTES)

    THEME_LABELS = {
        "catppuccin": "🌸 Catppuccin Mocha",
        "gruvbox": "🟤 Gruvbox Dark",
        "cyberpunk": "🌈 Cyberpunk",
        "nord": "❄️ Nord",
        "tokyonight": "🌃 Tokyo Night",
        "solarized": "☀️ Solarized",
        "monokai": "🌈 Monokai",
        "everforest": "🌲 Everforest",
        "rosepine": "🌹 Rose Pine",
    }

    def __init__(self, app: App):
        self.app = app
        self.current_theme = "catppuccin"

    @property
    def palette(self) -> dict[str, str]:
        return THEME_PALETTES[self.current_theme]

    def set_theme(self, theme: str) -> bool:
        """Set the active palette and immediately refresh the running app."""
        if theme not in self.THEMES:
            return False
        previous_theme = self.current_theme
        self.current_theme = theme
        self.app.screen.set_class(False, f"theme-{previous_theme}")
        self.app.screen.set_class(True, f"theme-{theme}")
        self.app.refresh_css(animate=False)
        return True

    def cycle_theme(self) -> str:
        """Cycle to the next palette."""
        idx = self.THEMES.index(self.current_theme)
        self.set_theme(self.THEMES[(idx + 1) % len(self.THEMES)])
        return self.current_theme

    def get_current_label(self) -> str:
        return self.THEME_LABELS.get(self.current_theme, self.current_theme)

    class ThemeChanged:
        """Message sent when a theme changes."""

        def __init__(self, theme: str):
            self.theme = theme

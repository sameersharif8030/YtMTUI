from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LayoutPlan:
    """Computed layout plan for responsive breakpoints."""
    grid_template: str
    columns: str
    rows: str
    show_sidebar: bool
    show_hero: bool
    show_library: bool
    show_queue: bool
    show_footer: bool
    show_header: bool
    compact: bool
    mini: bool


class LayoutEngine:
    """Responsive layout engine for multi-panel dashboard."""

    # Breakpoints
    DESKTOP_MIN_WIDTH = 120
    TABLET_MIN_WIDTH = 96
    MOBILE_MIN_WIDTH = 60
    MINI_MIN_HEIGHT = 20

    def plan(self, width: int, height: int, mini: bool = False) -> LayoutPlan:
        """Compute layout plan based on terminal size and mode."""
        if mini or height < self.MINI_MIN_HEIGHT:
            return self._mini_plan(width, height)
        elif width >= self.DESKTOP_MIN_WIDTH:
            return self._desktop_plan(width, height)
        elif width >= self.TABLET_MIN_WIDTH:
            return self._tablet_plan(width, height)
        else:
            return self._mobile_plan(width, height)

    def _desktop_plan(self, width: int, height: int) -> LayoutPlan:
        """Full desktop layout with all panels."""
        return LayoutPlan(
            grid_template=(
                '"header header header header" auto\n'
                '"sidebar hero hero hero" 1fr\n'
                '"sidebar library queue queue" 1fr\n'
                '"footer footer footer footer" 4'
            ),
            columns="25 1fr 1fr auto",
            rows="auto 1fr 1fr 4",
            show_sidebar=True,
            show_hero=True,
            show_library=True,
            show_queue=True,
            show_footer=True,
            show_header=True,
            compact=False,
            mini=False,
        )

    def _tablet_plan(self, width: int, height: int) -> LayoutPlan:
        """Tablet layout - sidebar collapsed."""
        return LayoutPlan(
            grid_template=(
                '"header header header" auto\n'
                '"hero hero hero" 1fr\n'
                '"footer footer footer" 4'
            ),
            columns="1fr 1fr auto",
            rows="auto 1fr 4",
            show_sidebar=False,
            show_hero=True,
            show_library=True,
            show_queue=True,
            show_footer=True,
            show_header=True,
            compact=True,
            mini=False,
        )

    def _mobile_plan(self, width: int, height: int) -> LayoutPlan:
        """Mobile layout - stacked single column."""
        return LayoutPlan(
            grid_template=(
                '"header" auto\n'
                '"hero" auto\n'
                '"library" 1fr\n'
                '"queue" 1fr\n'
                '"footer" 4'
            ),
            columns="1fr",
            rows="auto auto 1fr 1fr 4",
            show_sidebar=False,
            show_hero=True,
            show_library=True,
            show_queue=True,
            show_footer=True,
            show_header=True,
            compact=True,
            mini=False,
        )

    def _mini_plan(self, width: int, height: int) -> LayoutPlan:
        """Mini mode - ultra compact."""
        return LayoutPlan(
            grid_template=(
                '"hero" 1fr\n'
                '"footer" 3'
            ),
            columns="1fr",
            rows="1fr 3",
            show_sidebar=False,
            show_hero=True,
            show_library=False,
            show_queue=False,
            show_footer=True,
            show_header=False,
            compact=True,
            mini=True,
        )


class DashboardLayoutEngine(LayoutEngine):
    """Extended layout engine with dashboard-specific logic."""

    def apply_plan(self, app, plan: LayoutPlan) -> None:
        """Set responsive state classes; sizing is defined in valid Textual CSS."""
        screen = app.screen
        screen.set_class(plan.compact, "compact")
        screen.set_class(plan.mini, "mini")
        screen.set_class(plan.show_sidebar, "sidebar-visible")
        screen.set_class(not plan.show_sidebar, "sidebar-hidden")

        breakpoint = self.get_breakpoint_name(
            app._last_size[0], app._last_size[1], plan.mini
        )
        for name in ("desktop", "tablet", "mobile"):
            screen.set_class(name == breakpoint, name)

    def get_breakpoint_name(self, width: int, height: int, mini: bool) -> str:
        """Get human-readable breakpoint name."""
        if mini or height < self.MINI_MIN_HEIGHT:
            return "mini"
        elif width >= self.DESKTOP_MIN_WIDTH:
            return "desktop"
        elif width >= self.TABLET_MIN_WIDTH:
            return "tablet"
        else:
            return "mobile"

# SPDX-License-Identifier: GPL-3.0-or-later
"""Choose and place the main window on the primary screen (D-42).

Sizes are logical pixels; pywebview applies scaling.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

MIN_SIZE: Final = (1120, 640)
PREFERRED_SIZE: Final = (1440, 900)
# Room left for the window's title bar and the Windows taskbar.
_VERTICAL_ALLOWANCE: Final = 80


@dataclass(frozen=True, slots=True)
class Geometry:
    """The window's initial size, and whether it opens maximized."""

    width: int
    height: int
    maximized: bool


def window_geometry(screen_width: int, screen_height: int) -> Geometry:
    """Open at the preferred size when the screen has room for it, maximized otherwise."""
    width, height = PREFERRED_SIZE
    fits = screen_width >= width and screen_height >= height + _VERTICAL_ALLOWANCE
    return Geometry(width, height, maximized=not fits)


class Screen(Protocol):
    """A screen's origin and size, in logical pixels (structurally, `webview.screen.Screen`).

    Read-only properties, so a frozen dataclass can stand in for `webview.screen.Screen` in
    tests: mypy treats a plain attribute as a Protocol member with a matching read-only
    property, but not the reverse.
    """

    @property
    def x(self) -> int: ...
    @property
    def y(self) -> int: ...
    @property
    def width(self) -> int: ...
    @property
    def height(self) -> int: ...


def primary_screen[ScreenT: Screen](screens: Sequence[ScreenT]) -> ScreenT | None:
    """Return the screen at (0, 0), the first screen, or None when the list is empty.

    `webview.screens`' order isn't guaranteed to put the primary screen first, so it's found
    by position instead.
    """
    for screen in screens:
        if screen.x == 0 and screen.y == 0:
            return screen
    return screens[0] if screens else None

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


def window_geometry(screen: Screen | None) -> Geometry:
    """Open at the preferred size when the screen has room for it, maximized otherwise.

    With no screen information (`screen` is None), open maximized at the preferred size.
    """
    width, height = PREFERRED_SIZE
    if screen is None:
        return Geometry(width, height, maximized=True)
    fits = screen.width >= width and screen.height >= height + _VERTICAL_ALLOWANCE
    return Geometry(width, height, maximized=not fits)


def primary_screen[ScreenT: Screen](screens: Sequence[ScreenT]) -> ScreenT | None:
    """Return the screen at (0, 0), the first screen, or None when the list is empty.

    `webview.screens`' order isn't guaranteed to put the primary screen first, so it's found
    by position instead.
    """
    for screen in screens:
        if screen.x == 0 and screen.y == 0:
            return screen
    return screens[0] if screens else None

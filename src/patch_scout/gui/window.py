# SPDX-License-Identifier: GPL-3.0-or-later
"""Choose the main window's size (D-42). Sizes are logical pixels; pywebview applies scaling."""

from dataclasses import dataclass
from typing import Final

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

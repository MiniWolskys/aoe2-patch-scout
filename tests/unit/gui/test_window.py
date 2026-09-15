# SPDX-License-Identifier: GPL-3.0-or-later
from dataclasses import dataclass

import pytest

from patch_scout.gui.window import (
    MIN_SIZE,
    PREFERRED_SIZE,
    Geometry,
    primary_screen,
    window_geometry,
)


@dataclass(frozen=True, slots=True)
class FakeScreen:
    """A screen in logical pixels, standing in for `webview.screen.Screen` in tests."""

    x: int
    y: int
    width: int
    height: int


def test_sizes_follow_d42() -> None:
    assert (MIN_SIZE, PREFERRED_SIZE) == ((1120, 640), (1440, 900))


@pytest.mark.parametrize("screen", [(1920, 1080), (1440, 980), (2560, 1440)])
def test_window_opens_at_the_preferred_size_when_the_screen_has_room(
    screen: tuple[int, int],
) -> None:
    assert window_geometry(*screen) == Geometry(1440, 900, maximized=False)


@pytest.mark.parametrize("screen", [(1439, 1080), (1440, 979), (1366, 768), (1280, 720)])
def test_window_opens_maximized_on_a_smaller_screen(screen: tuple[int, int]) -> None:
    assert window_geometry(*screen) == Geometry(1440, 900, maximized=True)


def test_primary_screen_is_the_one_at_the_origin_even_when_listed_second() -> None:
    other = FakeScreen(x=-1920, y=1065, width=1920, height=1080)
    origin = FakeScreen(x=0, y=0, width=2560, height=1440)

    assert primary_screen([other, origin]) is origin


def test_primary_screen_falls_back_to_the_first_entry_when_none_is_at_the_origin() -> None:
    first = FakeScreen(x=-1920, y=1065, width=1920, height=1080)
    second = FakeScreen(x=1920, y=0, width=1920, height=1080)

    assert primary_screen([first, second]) is first


def test_primary_screen_is_none_for_an_empty_list() -> None:
    assert primary_screen([]) is None

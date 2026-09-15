# SPDX-License-Identifier: GPL-3.0-or-later
import pytest

from patch_scout.gui.window import MIN_SIZE, PREFERRED_SIZE, Geometry, window_geometry


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

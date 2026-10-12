# SPDX-License-Identifier: GPL-3.0-or-later
"""The patch notes read a change's values as players do (diff-rules.md, Patch notes)."""

import pytest

from patch_scout.report.notes.values import direction, shown


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("5", "5"),
        ("1.35", "1.35"),
        ("-3", "-3"),
        ("=15", "15"),  # a value the effect sets: the "=" says nothing to a reader
        ("+1", "+1"),
        ("-50", "-50"),
        ("\N{MULTIPLICATION SIGN}1.2", "+20%"),
        ("\N{MULTIPLICATION SIGN}0.6", "-40%"),
        ("\N{MULTIPLICATION SIGN}1.0835", "+8.35%"),
        ("\N{MULTIPLICATION SIGN}1", "+0%"),
        ("\N{MULTIPLICATION SIGN}0.34", "-66%"),
        ("Castle Age; Chemistry", "Castle Age; Chemistry"),
        ("", ""),
    ],
)
def test_a_value_reads_as_players_write_it(value: str, expected: str) -> None:
    assert shown(value) == expected


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        ("3", "5", "up"),
        ("2.0", "1.9", "down"),
        ("-3", "2", "up"),
        ("=6", "=15", "up"),
        ("+1", "+2", "up"),
        ("+2", "-1", "down"),
        ("\N{MULTIPLICATION SIGN}1.20", "\N{MULTIPLICATION SIGN}1.15", "down"),
        # Different forms are not compared: "=5" and "+5" mean different things.
        ("=5", "+6", None),
        ("5", "=6", None),
        ("Feudal Age", "Castle Age", None),
        ("5", "5", None),
        ("", "5", None),
    ],
)
def test_the_direction_compares_numbers_of_the_same_form(
    old: str, new: str, expected: str | None
) -> None:
    assert direction(old, new) == expected

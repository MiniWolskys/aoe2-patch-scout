# SPDX-License-Identifier: GPL-3.0-or-later
"""Techs known only by their developers' name are flagged internal (diff-rules.md, Patch notes).

"Disable Regionals" and "Genitour (make avail)" on 101.103.54800.0 are plumbing players never
see. A civ or team bonus's internal name says what it does, so it is not flagged.
"""

import pytest
from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import Entity
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot


def _tech(name: str, string_id: int, cost: int) -> JsonObject:
    return {
        "name": name,
        "civ": -1,
        "language_dll_name": string_id,
        "effect_id": -1,
        "required_tech_count": 0,
        "required_techs": [],
        "research_locations": [{"location_id": 82, "research_time": 40}],
        "resource_costs": [{"type": 0, "amount": cost, "flag": 1}],
        "repeatable": 0,
        "type": 0,
    }


def _build(cost: int, names: dict[str, str]) -> Snapshot:
    techs: dict[str, JsonValue] = {
        "1": _tech("Disable Regionals", 9001, cost),
        "2": _tech("C-Bonus, Archers +20% HP", 9002, cost),
        "3": _tech("Bodkin Arrow", 9003, cost),
    }
    return make_snapshot(
        civs=[],
        tech_trees={},
        strings={"tables": {"en": names}},
        flags={"stats_available": True},
        stats={"units": {}, "techs": techs, "effects": {}, "civ_dat": []},
    )


def _entity(name: str, old: Snapshot, new: Snapshot) -> Entity:
    found = {change.entity.name: change.entity for change in compare(old, new).changes}
    return found[name]


@pytest.mark.parametrize(
    ("name", "internal"),
    [
        ("Disable Regionals", True),
        ("Civ bonus: Archers +20% HP", False),
        ("Bodkin Arrow", False),
    ],
)
def test_only_plumbing_techs_are_internal(name: str, internal: bool) -> None:
    names = {"9003": "Bodkin Arrow"}
    entity = _entity(name, _build(100, names), _build(120, names))

    assert entity.internal is internal


def test_a_tech_that_had_a_display_name_in_either_build_is_not_internal() -> None:
    entity = _entity(
        "Disable Regionals", _build(100, {"9001": "Disable Regionals"}), _build(120, {})
    )

    assert entity.internal is False

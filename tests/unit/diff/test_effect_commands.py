# SPDX-License-Identifier: GPL-3.0-or-later
"""Effect commands are compared as a sequence: an inserted command is one change (diff-rules.md)."""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import Change
from patch_scout.snapshot import JsonValue, Snapshot


def _command(type_: int, a: int, d: float = 0.85) -> JsonValue:
    return {"type": type_, "a": a, "b": -1, "c": 0, "d": d}


def _build(commands: list[JsonValue]) -> Snapshot:
    tech: JsonValue = {
        "name": "Butalmapu",
        "civ": -1,
        "language_dll_name": 7000,
        "effect_id": 5,
        "required_tech_count": 1,
        "required_techs": [],
        "research_locations": [],
        "resource_costs": [],
        "repeatable": 0,
        "type": 0,
    }
    return make_snapshot(
        civs=[],
        tech_trees={},
        strings={"tables": {"en": {}}},
        flags={"stats_available": True},
        stats={
            "units": {},
            "techs": {"1380": tech},
            "effects": {"5": {"name": "Butalmapu", "commands": commands}},
            "civ_dat": [],
        },
    )


def _effect_changes(old: list[JsonValue], new: list[JsonValue]) -> list[Change]:
    return [
        change
        for change in compare(_build(old), _build(new)).changes
        if change.field is not None and change.field.key == "field.tech_effect"
    ]


def test_a_command_inserted_first_is_one_added_command() -> None:
    kept = [_command(5, unit) for unit in (10, 11, 12, 13)]
    changes = _effect_changes(kept, [_command(0, 99), *kept])

    assert len(changes) == 1
    assert changes[0].old == ""
    assert changes[0].new is not None and changes[0].new.startswith("type 0 a=99")


def test_commands_removed_from_the_middle_are_reported_as_removed() -> None:
    old = [_command(5, unit) for unit in (10, 11, 12, 13)]
    new = [old[0], old[3]]

    changes = _effect_changes(old, new)

    assert [(change.old != "", change.new) for change in changes] == [(True, ""), (True, "")]


def test_a_changed_command_in_place_still_shows_old_and_new() -> None:
    old = [_command(5, 10), _command(5, 11)]
    new = [_command(5, 10), _command(5, 11, d=0.9)]

    changes = _effect_changes(old, new)

    assert len(changes) == 1
    assert changes[0].old is not None and changes[0].old.endswith("d=0.85")
    assert changes[0].new is not None and changes[0].new.endswith("d=0.90")

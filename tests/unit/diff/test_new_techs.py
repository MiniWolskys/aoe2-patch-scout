# SPDX-License-Identifier: GPL-3.0-or-later
"""A new tech reads as Added, with what it costs and does (diff-rules.md, One entry per entity).

Ordonnance Companies on 101.103.54800.0 was a placeholder record in 101.103.48987.0: it gained a
cost, a research location and an effect, and read as a list of "added" values.
"""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import ChangeSet, Entry
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

TECH_ID = "1700"


def _tech(**overrides: JsonValue) -> JsonObject:
    record: JsonObject = {
        "name": "Ordonnance Companies",
        "civ": -1,
        "language_dll_name": 7000,
        "effect_id": -1,
        "required_tech_count": 0,
        "required_techs": [],
        "research_locations": [],
        "resource_costs": [],
        "repeatable": 0,
        "type": 0,
    }
    return record | overrides


def _researchable() -> JsonObject:
    return _tech(
        effect_id=5,
        required_tech_count=1,
        required_techs=[102],
        research_locations=[{"location_id": 82, "research_time": 40}],
        resource_costs=[
            {"type": 0, "amount": 400, "flag": 1},
            {"type": 3, "amount": 250, "flag": 1},
        ],
    )


def _build(tech: JsonObject | None) -> Snapshot:
    techs: dict[str, JsonValue] = {
        "102": _tech(name="Castle Age", language_dll_name=7001),
    }
    if tech is not None:
        techs[TECH_ID] = tech
    effect: JsonValue = {
        "name": "Ordonnance Companies",
        "commands": [{"type": 0, "a": 4, "b": -1, "c": 0, "d": 100.0}],
    }
    return make_snapshot(
        civs=[],
        tech_trees={},
        strings={"tables": {"en": {"7000": "Ordonnance Companies", "7001": "Castle Age"}}},
        flags={"stats_available": True},
        stats={
            "units": {},
            "techs": techs,
            "effects": {"5": effect},
            "civ_dat": [],
        },
    )


def _entries(change_set: ChangeSet) -> list[Entry]:
    return [
        entry
        for entry in change_set.entries
        if entry.category == "techs" and entry.entity.id == TECH_ID
    ]


def _fields(entry: Entry) -> set[str]:
    return {change.field.key for change in entry.changes if change.field is not None}


def test_a_tech_record_new_in_the_new_build_lists_what_it_costs_and_does() -> None:
    [entry] = _entries(compare(_build(None), _build(_researchable())))

    assert entry.kind == "added"
    assert {"field.cost", "field.research_locations", "field.required_techs"} <= _fields(entry)
    # Its effect's commands come with it, as for a tech that gains an effect.
    assert "field.tech_effect" in _fields(entry)
    costs = {
        change.new for change in entry.changes if change.field and change.field.key == "field.cost"
    }
    assert costs == {"400", "250"}


def test_a_placeholder_tech_that_becomes_researchable_reads_as_added() -> None:
    # As on 101.103.48987.0: a research time of 0 somewhere else, which the patch moves.
    placeholder = _tech(research_locations=[{"location_id": -1, "research_time": 0}])
    [entry] = _entries(compare(_build(placeholder), _build(_researchable())))

    assert entry.kind == "added"
    assert "field.research_locations" in _fields(entry)


def test_an_existing_tech_that_only_gains_an_effect_is_not_added() -> None:
    before = _researchable() | {"effect_id": -1}
    [entry] = _entries(compare(_build(before), _build(_researchable())))

    assert entry.kind == "modified"


def test_a_removed_tech_is_still_one_line() -> None:
    entries = _entries(compare(_build(_researchable()), _build(None)))

    assert [(entry.kind, entry.changes[0].field) for entry in entries] == [("removed", None)]

# SPDX-License-Identifier: GPL-3.0-or-later
"""One entry per entity: a unit's or tech's field changes read as one item (diff-rules.md)."""

from patch_scout.diff.entries import group
from patch_scout.diff.model import Change, Entity, Message, Scope

KNIGHT = Entity("unit", "38", "Knight")
JARL = Entity("unit", "2716", "Jarl")
ALL = Scope("all")
FRANKS = Scope("some", ("Franks",))


def _stat(entity: Entity, field: str, old: str | None, new: str, scope: Scope = ALL) -> Change:
    return Change(
        "unit_stats",
        "modified",
        entity,
        scope,
        field=Message(f"field.{field}"),
        old=old,
        new=new,
        civ=scope.civs[0] if scope.kind == "some" else None,
    )


def test_the_fields_of_one_unit_with_one_scope_make_one_entry() -> None:
    entries = group(
        [_stat(KNIGHT, "hit_points", "100", "110"), _stat(KNIGHT, "speed", "1.35", "1.4")]
    )

    assert len(entries) == 1
    assert entries[0].kind == "modified"
    assert [change.field.key for change in entries[0].changes if change.field] == [
        "field.hit_points",
        "field.speed",
    ]


def test_a_different_scope_makes_a_separate_entry() -> None:
    entries = group(
        [_stat(KNIGHT, "hit_points", "100", "110"), _stat(KNIGHT, "speed", "1.35", "1.4", FRANKS)]
    )

    assert [(entry.scope.kind, entry.civ) for entry in entries] == [
        ("all", None),
        ("some", "Franks"),
    ]


def test_entries_keep_the_order_of_their_first_change() -> None:
    entries = group(
        [
            _stat(JARL, "hit_points", "60", "65"),
            _stat(KNIGHT, "hit_points", "100", "110"),
            _stat(JARL, "speed", "1", "1.1"),
        ]
    )

    assert [entry.entity.name for entry in entries] == ["Jarl", "Knight"]


def test_a_new_unit_shows_its_main_stats_and_counts_the_rest() -> None:
    danes = Scope("some", ("Danes",))
    entries = group(
        [
            _stat(JARL, "hit_points", None, "65", danes),
            _stat(JARL, "speed", None, "1.1", danes),
            _stat(JARL, "garrison_capacity", None, "0", danes),  # a default value
            _stat(JARL, "search_radius", None, "4", danes),  # not a main stat
        ]
    )

    assert len(entries) == 1
    entry = entries[0]
    assert entry.kind == "added"
    assert [change.field.key for change in entry.changes if change.field] == [
        "field.hit_points",
        "field.speed",
    ]
    assert entry.hidden == 2


def test_a_field_that_only_appears_with_a_default_value_is_not_listed() -> None:
    """A placeholder unit filled in (the Mounted Crossbowman) gains dozens of "added 0" fields."""
    entries = group(
        [
            _stat(KNIGHT, "line_of_sight", "2", "6"),
            _stat(KNIGHT, "max_charge", None, "0"),
            _stat(KNIGHT, "garrison_capacity", "0", ""),
        ]
    )

    assert [change.field.key for change in entries[0].changes if change.field] == [
        "field.line_of_sight"
    ]
    assert entries[0].hidden == 2


def test_a_change_without_a_field_is_an_entry_of_its_own() -> None:
    added = Change("civ_availability", "added", Entity("unit", "2716", "Jarl", where="Castle"))
    entries = group([added, _stat(JARL, "hit_points", "60", "65")])

    assert [(entry.category, entry.kind) for entry in entries] == [
        ("civ_availability", "added"),
        ("unit_stats", "modified"),
    ]


def test_an_entry_with_one_change_keeps_that_changes_kind() -> None:
    text = Change("text", "text_changed", KNIGHT, ALL, field=Message("field.help_text"), words=())
    assert [entry.kind for entry in group([text])] == ["text_changed"]

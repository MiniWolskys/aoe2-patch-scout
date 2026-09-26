# SPDX-License-Identifier: GPL-3.0-or-later
"""Projectiles on the units that fire them, tech names, and objects with no name (D-37)."""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import Change, ChangeSet
from patch_scout.i18n.catalog import load_catalog
from patch_scout.report import Filters, render_text
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

ARCHER = 4
ARROW = 363


def _civ(name: str, index: int) -> JsonValue:
    return {
        "internal_name": name,
        "index": index,
        "name_string_id": None,
        "era": "base",
        "emblem_icon": None,
        "bonus_string_id": None,
        "unique_unit_string_ids": [],
    }


CIVS = [_civ("Gaia", 0), _civ("Alpha", 1), _civ("Beta", 2)]


def _unit(base: JsonObject) -> JsonValue:
    return {"base": base, "base_civs": [0, 1, 2], "overrides": {}, "absent_civs": []}


def _tech(name: str, civ: int, required_count: int, dll: int = 7000) -> JsonValue:
    return {
        "name": name,
        "civ": civ,
        "language_dll_name": dll,
        "effect_id": -1,
        "required_tech_count": required_count,
        "required_techs": [],
        "research_locations": [],
        "resource_costs": [],
        "repeatable": 0,
        "type": 0,
    }


def _build(arrow_attack: int, techs: dict[str, JsonValue]) -> Snapshot:
    archer: JsonObject = {
        "hit_points": 30,
        "language_dll_name": 5004,
        "type_50": {"projectile_unit_id": ARROW, "attacks": [{"class_": 3, "amount": 4}]},
    }
    arrow: JsonObject = {
        "hit_points": 1,
        "language_dll_name": 0,
        "type_50": {"projectile_unit_id": -1, "attacks": [{"class_": 3, "amount": arrow_attack}]},
    }
    tree = [{"use_type": "Unit", "node_id": ARCHER, "node_status": "ResearchedCompleted"}]
    return make_snapshot(
        civs=CIVS,
        tech_trees={"Alpha": tree, "Beta": tree},
        strings={"tables": {"en": {"5004": "Archer", "7022": "Loom"}}},
        flags={"stats_available": True},
        stats={
            "units": {str(ARCHER): _unit(archer), str(ARROW): _unit(arrow)},
            "techs": techs,
            "effects": {},
            "civ_dat": [],
        },
    )


def _compare(old_techs: dict[str, JsonValue], new_techs: dict[str, JsonValue]) -> ChangeSet:
    return compare(_build(6, old_techs), _build(7, new_techs))


def _stats(change_set: ChangeSet) -> list[Change]:
    return [change for change in change_set.changes if change.category == "unit_stats"]


def test_a_projectile_change_is_reported_on_the_unit_that_fires_it() -> None:
    changes = _stats(_compare({}, {}))

    assert [(change.entity.id, change.entity.name) for change in changes] == [("4", "Archer")]
    field = changes[0].field
    assert field is not None
    assert field.key == "field.projectile"
    assert field.args["field"] == {"key": "field.attacks", "args": {"class": "#3"}}
    assert (changes[0].old, changes[0].new) == ("6", "7")


def test_a_projectile_field_reads_as_part_of_its_shooter() -> None:
    text = render_text(_compare({}, {}), load_catalog("en"))
    assert "Archer · Projectile: Attack vs #3 · 6 → 7" in text


def test_a_tech_without_a_display_name_uses_its_internal_name() -> None:
    old = {"153": _tech("C-Bonus, Military cost -20%", -1, 1)}
    new = {"153": _tech("C-Bonus, Military cost -20%", -1, 2)}

    changes = [change for change in _compare(old, new).changes if change.category == "techs"]

    assert {change.entity.name for change in changes} == {"C-Bonus, Military cost -20%"}
    assert all(change.entity.named for change in changes)


def test_a_tech_tied_to_a_civ_shows_on_that_civs_page() -> None:
    old = {"153": _tech("C-Bonus, Military cost -20%", 2, 1)}
    new = {"153": _tech("C-Bonus, Military cost -20%", 2, 2)}

    changes = [change for change in _compare(old, new).changes if change.category == "techs"]

    assert [(change.civ, change.scope.kind, change.scope.civs) for change in changes] == [
        ("Beta", "some", ("Beta",))
    ]


def test_a_tech_whose_effect_changed_reports_it_once() -> None:
    before = _tech("C-Bonus, Docks garrison", 2, 1)
    after = _tech("C-Bonus, Docks garrison", 2, 1)
    assert isinstance(before, dict) and isinstance(after, dict)
    before["effect_id"] = 870

    changes = [
        change
        for change in _compare({"855": before}, {"855": after}).changes
        if change.category == "techs"
    ]

    assert [(change.old, change.new) for change in changes] == [("870", "-1")]


def test_a_tech_with_no_usable_name_is_marked_unnamed_and_counted() -> None:
    old = {"172": _tech("New Research", -1, 1, dll=0)}
    new = {"172": _tech("New Research", -1, 2, dll=0)}

    change_set = _compare(old, new)

    unnamed = [change for change in change_set.changes if not change.entity.named]
    assert [change.entity.name for change in unnamed] == ["#172"]
    notices = [notice for notice in change_set.notices if notice.kind == "unnamed_hidden"]
    assert [notice.message.args for notice in notices] == [{"count": 1}]


def test_unnamed_objects_are_left_out_of_exports_unless_asked_for() -> None:
    old = {"172": _tech("New Research", -1, 1, dll=0)}
    new = {"172": _tech("New Research", -1, 2, dll=0)}
    change_set = _compare(old, new)
    catalog = load_catalog("en")

    assert "#172" not in render_text(change_set, catalog)
    assert "#172" in render_text(change_set, catalog, Filters(unnamed=True))

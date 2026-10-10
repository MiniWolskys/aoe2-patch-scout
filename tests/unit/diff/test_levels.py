# SPDX-License-Identifier: GPL-3.0-or-later
"""Change levels (diff-rules.md, Levels): what a player sees first, and what waits a click.

The rules come from the noise measured on two public builds (101.103.48987.0 → 101.103.54800.0).
"""

from typing import Any

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import ChangeSet
from patch_scout.i18n.catalog import load_catalog
from patch_scout.report import Filters, render_text
from patch_scout.snapshot import JsonValue, Snapshot

KNIGHT, RAM, SCORPION, CROSSBOW = 38, 35, 279, 2700
CATALOG = load_catalog("en")
CONSTANTS: JsonValue = {
    "Effect Constants": [["cSetAttribute", 0], ["cAddAttribute", 4], ["cModResource", 1]],
    "Tech Effect Constants": [["cHitpoints", 0], ["cBlastWidth", 22]],
    "Damage Classes": [["cDamageClassPierce", 3], ["cDamageClassMelee", 4]],
    "Attributes": [["cAttributeFood", 0], ["cAttributeVarangianGold", 297]],
}


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


def _unit(base: dict[str, Any]) -> JsonValue:
    return {"base": base, "base_civs": [0, 1, 2], "overrides": {}, "absent_civs": []}


def _build(**values: Any) -> Snapshot:
    """One build; keyword values tweak the defaults below."""
    v: dict[str, Any] = {
        "knight_blast": 0,
        "knight_width": 0.0,
        "ram_los": 3,
        "ram_search": 3,
        "melee": 4,
        "shown_melee": 4,
        "extra_armour": [],
        "gold": [0, 0, 0],
        "food": [200, 200, 200],
        "status": "ResearchRequired",
        "commands": [],
        "tree_commands": [],
        "crossbow_hp": 1,
        "crossbow_in_tree": False,
    } | values
    knight = {
        "hit_points": 100,
        "language_dll_name": 5038,
        "blast_defense_level": 0,
        "type_50": {
            "blast_attack_level": v["knight_blast"],
            "blast_width": v["knight_width"],
            "armours": [{"class_": 4, "amount": 2}, *v["extra_armour"]],
            "displayed_melee_armour": 2,
        },
    }
    ram = {
        "hit_points": 175,
        "language_dll_name": 5035,
        "line_of_sight": v["ram_los"],
        "bird": {"search_radius": v["ram_search"]},
    }
    scorpion = {
        "hit_points": 40,
        "language_dll_name": 5279,
        "type_50": {
            "armours": [{"class_": 4, "amount": v["melee"]}],
            "displayed_melee_armour": v["shown_melee"],
        },
    }
    crossbow = {"hit_points": v["crossbow_hp"], "language_dll_name": 5999}
    shown = (KNIGHT, RAM, SCORPION, CROSSBOW) if v["crossbow_in_tree"] else (KNIGHT, RAM, SCORPION)
    tree = [
        {"use_type": "Unit", "node_id": unit, "node_status": "ResearchedCompleted"}
        for unit in shown
    ] + [
        {
            "use_type": "Building",
            "node_id": 87,
            "node_status": v["status"],
            "name_string_id": 5087,
        }
    ]
    civ_dat = [
        {"resources": [food, *([0] * 296), gold], "tech_tree_effect_id": 9 if index else -1}
        for index, (food, gold) in enumerate(zip(v["food"], v["gold"], strict=True))
    ]
    return make_snapshot(
        civs=CIVS,
        tech_trees={"Alpha": tree, "Beta": tree},
        strings={
            "tables": {
                "en": {
                    "5038": "Knight",
                    "5035": "Battering Ram",
                    "5279": "Scorpion",
                    "5999": "Mounted Crossbowman",
                    "5087": "Archery Range",
                    "7100": "Vendel Legacy",
                }
            }
        },
        flags={"stats_available": True},
        scripts={"constants": CONSTANTS},
        stats={
            "units": {
                str(KNIGHT): _unit(knight),
                str(RAM): _unit(ram),
                str(SCORPION): _unit(scorpion),
                str(CROSSBOW): _unit(crossbow),
            },
            "techs": {
                "100": {
                    "name": "Vendel Legacy",
                    "civ": -1,
                    "language_dll_name": 7100,
                    "effect_id": 5,
                    "required_tech_count": 1,
                    "required_techs": [],
                    "research_locations": [],
                    "resource_costs": [],
                    "repeatable": 0,
                    "type": 0,
                }
            },
            "effects": {
                "5": {"name": "Vendel Legacy", "commands": v["commands"]},
                "9": {"name": "Tech tree", "commands": v["tree_commands"]},
            },
            "civ_dat": civ_dat,
        },
    )


def _compare(old: dict[str, Any] | None = None, new: dict[str, Any] | None = None) -> ChangeSet:
    return compare(_build(**(old or {})), _build(**(new or {})))


def _levels(change_set: ChangeSet, entity: str) -> dict[str, str]:
    return {
        CATALOG.message(c.field.key, c.field.args): c.level
        for c in change_set.changes
        if c.entity.name == entity and c.field is not None
    }


def _command(type_: int, a: int = -1, b: int = -1, c: int = -1, d: float = 0.0) -> JsonValue:
    return {"type": type_, "a": a, "b": b, "c": c, "d": d}


# --- starting resources -------------------------------------------------------------------------


def test_a_resource_changed_for_every_civ_is_one_overall_line() -> None:
    change_set = _compare(new={"gold": [50, 50, 50]})
    [change] = [c for c in change_set.changes if c.category == "bonuses"]
    assert (change.entity.name, change.civ, change.scope.kind) == ("Varangian Gold", None, "all")
    assert (change.old, change.new) == ("0", "50")


def test_a_resource_changed_for_one_civ_stays_on_its_page() -> None:
    change_set = _compare(new={"food": [200, 300, 200]})
    [change] = [c for c in change_set.changes if c.category == "bonuses"]
    assert (change.entity.name, change.civ) == ("Food", "Alpha")


# --- unit stats ---------------------------------------------------------------------------------


def test_search_radius_is_a_detail() -> None:
    levels = _levels(_compare(new={"ram_los": 5, "ram_search": 5}), "Battering Ram")
    assert levels == {"Line of sight": "headline", "Search radius": "detail"}


def test_a_displayed_stat_repeating_its_armour_class_is_a_detail() -> None:
    levels = _levels(_compare(new={"melee": 3, "shown_melee": 3}), "Scorpion")
    assert levels == {"Armour vs Melee": "headline", "Displayed melee armour": "detail"}


def test_a_displayed_stat_that_disagrees_stays_a_headline() -> None:
    levels = _levels(_compare(new={"shown_melee": 3}), "Scorpion")
    assert levels == {"Displayed melee armour": "headline"}


def test_a_blast_level_without_any_blast_width_is_technical() -> None:
    levels = _levels(_compare(new={"knight_blast": 2}), "Knight")
    assert levels == {"Blast attack level": "technical"}


def test_a_blast_level_with_a_blast_width_is_a_headline() -> None:
    levels = _levels(_compare(new={"knight_blast": 2, "knight_width": 0.5}), "Knight")
    assert levels["Blast attack level"] == "headline"


def test_a_blast_level_only_a_tech_gives_width_to_is_a_detail() -> None:
    """The tech's own line says what changes; the level alone reads as if every civ gained it."""
    grant = _command(4, a=KNIGHT, c=22, d=0.5)
    levels = _levels(_compare(new={"knight_blast": 2, "commands": [grant]}), "Knight")
    assert levels["Blast attack level"] == "detail"


# --- placeholders -------------------------------------------------------------------------------


def test_a_unit_no_civ_could_get_before_reads_as_added() -> None:
    change_set = _compare(new={"crossbow_hp": 45, "crossbow_in_tree": True})
    [entry] = [
        e
        for e in change_set.entries
        if e.entity.name == "Mounted Crossbowman" and e.category == "unit_stats"
    ]
    assert entry.kind == "added"
    assert [(c.old, c.new) for c in entry.changes] == [("", "45")]


def test_a_zero_armour_class_coming_or_going_is_technical() -> None:
    levels = _levels(_compare(old={"extra_armour": [{"class_": 3, "amount": 0}]}), "Knight")
    assert levels == {"Armour vs Pierce": "technical"}


# --- availability and effects -------------------------------------------------------------------


def test_a_building_switching_between_two_available_states_is_a_detail() -> None:
    levels = _levels(_compare(new={"status": "ResearchedCompleted"}), "Archery Range")
    assert set(levels.values()) == {"detail"}


def test_a_raw_tech_tree_command_is_technical() -> None:
    change_set = _compare(new={"tree_commands": [_command(255)]})
    tree = [c for c in change_set.changes if c.category == "bonuses"]
    assert tree and {c.level for c in tree} == {"technical"}


def test_a_value_that_only_lost_a_rounding_error_is_technical() -> None:
    old = {"commands": [_command(1, a=0, b=0, d=0.99999)]}
    new = {"commands": [_command(1, a=0, b=0, d=1.0)]}
    [change] = [c for c in _compare(old, new).changes if c.category == "techs"]
    assert change.level == "technical"


# --- filters and exports ------------------------------------------------------------------------


def test_the_default_export_hides_details_and_says_how_many() -> None:
    change_set = _compare(new={"ram_los": 5, "ram_search": 5, "knight_blast": 2})
    text = render_text(change_set, CATALOG)
    assert "Line of sight" in text
    assert "Search radius" not in text
    assert "Blast attack level" not in text
    assert "2 minor or technical changes are hidden" in text


def test_the_filters_bring_details_and_technical_changes_back() -> None:
    change_set = _compare(new={"ram_los": 5, "ram_search": 5, "knight_blast": 2})
    text = render_text(change_set, CATALOG, Filters(details=True, technical=True))
    assert "Search radius" in text
    assert "Blast attack level" in text


def test_levels_are_in_the_change_set_json() -> None:
    change_set = _compare(new={"ram_los": 5, "ram_search": 5})
    changes = change_set.to_json()["changes"]
    assert isinstance(changes, list)
    assert {change["level"] for change in changes if isinstance(change, dict)} == {
        "headline",
        "detail",
    }


def test_an_unchanged_unit_no_civ_could_get_before_still_reads_as_added() -> None:
    change_set = _compare(new={"crossbow_in_tree": True})
    [entry] = [
        e
        for e in change_set.entries
        if e.entity.name == "Mounted Crossbowman" and e.category == "unit_stats"
    ]
    assert entry.kind == "added"

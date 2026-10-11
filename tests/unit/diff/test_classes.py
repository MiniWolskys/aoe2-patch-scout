# SPDX-License-Identifier: GPL-3.0-or-later
"""Attack and armour classes as players name them, and the classes nothing attacks (D-50)."""

from typing import Any

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.classes import ClassKind, attacked_classes, class_field
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.i18n.catalog import load_catalog
from patch_scout.snapshot import JsonValue, Snapshot

CATALOG = load_catalog("en")
RAM, ARCHER = 35, 4
UNUSED, ARCHERS = 31, 15
CONSTANTS: JsonValue = {
    "Effect Constants": [["cSetAttribute", 0], ["cAddAttribute", 4], ["cMulAttribute", 5]],
    "Tech Effect Constants": [["cHitpoints", 0], ["cArmor", 8], ["cAttack", 9]],
    "Damage Classes": [
        ["cDamageClassPierce", 3],
        ["cDamageClassMelee", 4],
        ["cDamageClassArchers", 15],
        ["cDamageClassShockInfantry", 29],
    ],
}


def _label(kind: ClassKind, armour_class: int) -> str:
    field = class_field(kind, armour_class, _vocabulary())
    return CATALOG.message(field.key, field.args)


# --- wording ------------------------------------------------------------------------------------


def test_melee_and_pierce_read_as_the_units_own_armour_and_attack() -> None:
    assert _label("armours", 4) == "Melee armour"
    assert _label("armours", 3) == "Pierce armour"
    assert _label("attacks", 4) == "Melee attack"
    assert _label("attacks", 3) == "Pierce attack"


def test_other_classes_read_as_an_armour_class_and_a_bonus_against_it() -> None:
    assert _label("armours", 15) == "Archers armour class"
    assert _label("attacks", 29) == "Bonus vs Shock Infantry"


def test_an_unnamed_class_keeps_its_number() -> None:
    assert _label("armours", 31) == "#31 armour class"
    assert _label("attacks", 31) == "Bonus vs #31"


# --- classes nothing attacks --------------------------------------------------------------------


def _unit(base: dict[str, Any], overrides: dict[str, Any] | None = None) -> JsonValue:
    return {"base": base, "base_civs": [0, 1], "overrides": overrides or {}, "absent_civs": []}


def _build(
    *,
    ram_armours: list[JsonValue],
    archer_attacks: list[JsonValue] | None = None,
    overrides: dict[str, Any] | None = None,
    commands: list[JsonValue] | None = None,
) -> Snapshot:
    ram = {"hit_points": 175, "language_dll_name": 5035, "type_50": {"armours": ram_armours}}
    archer = {
        "hit_points": 30,
        "language_dll_name": 5004,
        "type_50": {
            "attacks": [{"class_": 3, "amount": 4}] if archer_attacks is None else archer_attacks
        },
    }
    tree = [
        {"use_type": "Unit", "node_id": unit, "node_status": "ResearchedCompleted"}
        for unit in (RAM, ARCHER)
    ]
    civs = [
        {"internal_name": name, "index": index, "name_string_id": None, "era": "base"}
        for index, name in enumerate(("Gaia", "Alpha"))
    ]
    return make_snapshot(
        civs=civs,
        tech_trees={"Alpha": tree},
        strings={"tables": {"en": {"5035": "Battering Ram", "5004": "Archer"}}},
        flags={"stats_available": True},
        scripts={"constants": CONSTANTS},
        stats={
            "units": {str(RAM): _unit(ram), str(ARCHER): _unit(archer, overrides)},
            "techs": {},
            "effects": {"5": {"name": "Effect", "commands": commands or []}},
            "civ_dat": [{"resources": []}, {"resources": []}],
        },
    )


def _vocabulary() -> Vocabulary:
    return Vocabulary(make_snapshot(scripts={"constants": CONSTANTS}))


def test_a_class_counts_as_attacked_only_with_a_non_zero_amount() -> None:
    snapshot = _build(
        ram_armours=[],
        archer_attacks=[{"class_": 3, "amount": 4}, {"class_": UNUSED, "amount": 0}],
    )
    assert attacked_classes([snapshot]) == frozenset({3})


def test_a_civ_override_or_an_effect_can_attack_a_class() -> None:
    override = {"type_50.attacks": [{"class_": ARCHERS, "amount": 2}]}
    bonus: JsonValue = {"type": 4, "a": ARCHER, "b": -1, "c": 9, "d": float(29 * 256 + 3)}
    multiplied: JsonValue = {"type": 5, "a": ARCHER, "b": -1, "c": 9, "d": float(UNUSED * 256 + 2)}
    snapshot = _build(ram_armours=[], overrides={"1": override}, commands=[bonus, multiplied])
    assert attacked_classes([snapshot]) == frozenset({3, ARCHERS, 29})


def _armour_lines(old: Snapshot, new: Snapshot) -> set[str]:
    return {
        CATALOG.message(c.field.key, c.field.args)
        for c in compare(old, new).changes
        if c.entity.name == "Battering Ram" and c.field is not None
    }


def test_an_armour_class_nothing_attacks_is_not_compared() -> None:
    old = _build(ram_armours=[{"class_": 4, "amount": 0}, {"class_": UNUSED, "amount": 0}])
    new = _build(ram_armours=[{"class_": 4, "amount": -2}, {"class_": UNUSED, "amount": 6}])
    assert _armour_lines(old, new) == {"Melee armour"}


def test_an_armour_class_comes_back_once_something_attacks_it() -> None:
    old = _build(ram_armours=[{"class_": UNUSED, "amount": 0}])
    new = _build(
        ram_armours=[{"class_": UNUSED, "amount": 6}],
        archer_attacks=[{"class_": 3, "amount": 4}, {"class_": UNUSED, "amount": 2}],
    )
    assert _armour_lines(old, new) == {"#31 armour class"}


def test_melee_and_pierce_armour_are_compared_even_when_nothing_attacks_them() -> None:
    old = _build(ram_armours=[{"class_": 3, "amount": 180}], archer_attacks=[])
    new = _build(ram_armours=[{"class_": 3, "amount": 190}], archer_attacks=[])
    assert _armour_lines(old, new) == {"Pierce armour"}

# SPDX-License-Identifier: GPL-3.0-or-later
"""Names for the game's numeric IDs, read from the snapshot's XS constants (game-files.md §11)."""

from support.snapshots import make_snapshot

from patch_scout.diff.vocabulary import Vocabulary, label
from patch_scout.snapshot import JsonValue, Snapshot


def _with_constants(constants: dict[str, JsonValue]) -> Snapshot:
    return make_snapshot(scripts={"constants": constants})


NEW = _with_constants(
    {
        "Damage Classes": [["cDamageClassPierce", 3], ["cDamageClassShockInfantry", 29]],
        "Tech Effect Constants": [["cHitpoints", 0], ["cBlastAttackLevel", 44]],
        "Object Classes": [["cArcherClass", 900], ["cCavalryArcherClass", 936]],
        "Attributes": [["cAttributeFood", 0], ["cAttributeTrageBonus", 8]],
        "Effect Constants": [["cSetAttribute", 0], ["cAddAttribute", 4]],
    }
)


def test_identifiers_become_readable_labels() -> None:
    assert label("ShockInfantry") == "Shock Infantry"
    assert label("BlastAttackLevel") == "Blast Attack Level"
    assert label("Hitpoints") == "Hitpoints"


def test_armour_classes_attributes_and_resources_are_named() -> None:
    names = Vocabulary(NEW)
    assert names.armour_class(29) == "Shock Infantry"
    assert names.attribute(44) == "Blast Attack Level"
    assert names.resource(0) == "Food"


def test_unit_classes_drop_the_900_offset() -> None:
    names = Vocabulary(NEW)
    assert names.unit_class(0) == "Archer"
    assert names.unit_class(36) == "Cavalry Archer"


def test_command_types_give_the_identifier() -> None:
    assert Vocabulary(NEW).command_type(4) == "AddAttribute"


def test_an_unnamed_or_non_numeric_id_has_no_name() -> None:
    names = Vocabulary(NEW)
    assert names.armour_class(31) is None
    assert names.armour_class("3") is None
    assert names.attribute(None) is None


def test_the_first_snapshot_wins_and_the_next_fills_gaps() -> None:
    old = _with_constants(
        {"Damage Classes": [["cDamageClassPierceOld", 3], ["cDamageClassCavalry", 8]]}
    )
    names = Vocabulary(NEW, old)
    assert names.armour_class(3) == "Pierce"
    assert names.armour_class(8) == "Cavalry"


def test_a_snapshot_without_scripts_names_nothing() -> None:
    assert Vocabulary(make_snapshot()).armour_class(3) is None

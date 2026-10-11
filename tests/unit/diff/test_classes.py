# SPDX-License-Identifier: GPL-3.0-or-later
"""Attack and armour classes as players name them (D-50)."""

from support.snapshots import make_snapshot

from patch_scout.diff.classes import ClassKind, class_field
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.i18n.catalog import load_catalog
from patch_scout.snapshot import JsonValue

CATALOG = load_catalog("en")
CONSTANTS: JsonValue = {
    "Damage Classes": [
        ["cDamageClassPierce", 3],
        ["cDamageClassMelee", 4],
        ["cDamageClassArchers", 15],
        ["cDamageClassShockInfantry", 29],
    ],
}


def _label(kind: ClassKind, armour_class: int) -> str:
    vocabulary = Vocabulary(make_snapshot(scripts={"constants": CONSTANTS}))
    field = class_field(kind, armour_class, vocabulary)
    return CATALOG.message(field.key, field.args)


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

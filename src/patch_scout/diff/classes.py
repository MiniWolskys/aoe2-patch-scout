# SPDX-License-Identifier: GPL-3.0-or-later
"""Attack and armour classes as players name them (D-50).

A unit's armour is a list of classes, each with an amount; an attack's bonus applies to a target
that has its class. Players call the two basic classes the unit's own armour and attack, "Melee
armour: -2", and the others an armour class and a bonus against it: "Archers armour class: 0",
"Bonus vs Archers: 3". The basic classes are recognised by their `Constants.xs` names.
"""

from typing import Final, Literal

from patch_scout.diff.model import Message
from patch_scout.diff.values import unknown_id
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.snapshot import JsonValue

type ClassKind = Literal["attacks", "armours"]
type Basic = Literal["Melee", "Pierce"]

# The classes players read as a unit's own armour and attack, by their `Constants.xs` names.
BASIC: Final[tuple[Basic, ...]] = ("Melee", "Pierce")


def class_field(kind: ClassKind, armour_class: JsonValue, vocabulary: Vocabulary) -> Message:
    """The label of one attack or armour class, e.g. "Melee armour" or "Bonus vs Archers"."""
    name = vocabulary.armour_class(armour_class) or unknown_id(armour_class)
    basic = basic_name(armour_class, vocabulary) is not None
    return Message(f"field.{kind}_basic" if basic else f"field.{kind}", {"class": name})


def basic_name(armour_class: JsonValue, vocabulary: Vocabulary) -> Basic | None:
    """The basic class's name, "Melee" or "Pierce"; None for any other class."""
    identifier = vocabulary.armour_class_identifier(armour_class)
    return next((basic for basic in BASIC if basic == identifier), None)

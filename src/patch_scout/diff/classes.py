# SPDX-License-Identifier: GPL-3.0-or-later
"""Attack and armour classes as players name them, and the classes nothing attacks (D-50).

A unit's armour is a list of classes, each with an amount; an attack's bonus applies to a target
that has its class. Players call the two basic classes the unit's own armour and attack, "Melee
armour: -2", and the others an armour class and a bonus against it: "Archers armour class: 0",
"Bonus vs Archers: 3".

An armour class that no attack targets changes no damage, so its armour values are noise: they
are left out until a build gives some attack a bonus against it. On 101.103.54800.0 that hides
classes 0, 34 and 40. Class 31, on most units, stays: only the Achaemenids' Sagaris attacks it.
Melee and Pierce are always kept.
"""

from collections.abc import Iterable
from typing import Final, Literal

from patch_scout.diff.model import Message
from patch_scout.diff.values import at_path, unknown_id
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.snapshot import JsonValue, Snapshot

type ClassKind = Literal["attacks", "armours"]

# The classes players read as a unit's own armour and attack, by their `Constants.xs` names.
_BASIC: Final = frozenset({"Melee", "Pierce"})
# The commands whose amount packs a class and a value; a multiplier doesn't (diff-rules.md).
_PACKING_COMMANDS: Final = frozenset({"AddAttribute", "SetAttribute"})


def class_field(kind: ClassKind, armour_class: JsonValue, vocabulary: Vocabulary) -> Message:
    """The label of one attack or armour class, e.g. "Melee armour" or "Bonus vs Archers"."""
    name = vocabulary.armour_class(armour_class) or unknown_id(armour_class)
    basic = vocabulary.armour_class_identifier(armour_class) in _BASIC
    return Message(f"field.{kind}_basic" if basic else f"field.{kind}", {"class": name})


def is_basic(armour_class: JsonValue, vocabulary: Vocabulary) -> bool:
    """Melee or Pierce: a unit's own armour, shown whether or not anything attacks it."""
    return vocabulary.armour_class_identifier(armour_class) in _BASIC


def attacked_classes(snapshots: Iterable[Snapshot]) -> frozenset[int]:
    """The classes some attack targets with a non-zero amount: a unit's, or an effect's.

    Each snapshot's effects are read with its own `Constants.xs`.
    """
    found: set[int] = set()
    for snapshot in snapshots:
        found |= _attacked(snapshot)
    return frozenset(found)


def shown(armour_class: JsonValue, attacked: frozenset[int], vocabulary: Vocabulary) -> bool:
    """Whether an armour class is worth showing: a basic one, or one something attacks."""
    return armour_class in attacked or is_basic(armour_class, vocabulary)


def _attacked(snapshot: Snapshot) -> frozenset[int]:
    """One snapshot's attacked classes; kept, since a snapshot never changes (rule 5)."""
    cached = _CACHE.get(id(snapshot))
    if cached is not None and cached[0] is snapshot:
        return cached[1]
    found: set[int] = set()
    vocabulary = Vocabulary(snapshot)
    stats = snapshot.stats if isinstance(snapshot.stats, dict) else {}
    units = stats.get("units")
    for entry in units.values() if isinstance(units, dict) else []:
        if not isinstance(entry, dict):
            continue
        _add_attacks(at_path(entry.get("base"), "type_50.attacks"), found)
        overrides = entry.get("overrides")
        for values in overrides.values() if isinstance(overrides, dict) else []:
            if isinstance(values, dict):
                _add_attacks(values.get("type_50.attacks"), found)
    effects = stats.get("effects")
    for effect in effects.values() if isinstance(effects, dict) else []:
        commands = effect.get("commands") if isinstance(effect, dict) else None
        for command in commands if isinstance(commands, list) else []:
            armour_class = _effect_attack(command, vocabulary)
            if armour_class is not None:
                found.add(armour_class)
    if len(_CACHE) >= 8:
        _CACHE.clear()
    result = frozenset(found)
    _CACHE[id(snapshot)] = (snapshot, result)
    return result


# Snapshot id() -> the snapshot and its attacked classes; the snapshot is kept so a reused id()
# can't match.
_CACHE: dict[int, tuple[Snapshot, frozenset[int]]] = {}


def _add_attacks(attacks: JsonValue, found: set[int]) -> None:
    for attack in attacks if isinstance(attacks, list) else []:
        if not isinstance(attack, dict):
            continue
        armour_class, amount = attack.get("class_"), attack.get("amount")
        if _integer(armour_class) and _nonzero(amount):
            found.add(armour_class)  # type: ignore[arg-type]  # checked just above


def _effect_attack(command: JsonValue, vocabulary: Vocabulary) -> int | None:
    """The class an effect command gives a non-zero attack against, if it does."""
    if not isinstance(command, dict):
        return None
    if vocabulary.command_type(command.get("type")) not in _PACKING_COMMANDS:
        return None
    if vocabulary.attribute_identifier(command.get("c")) != "Attack":
        return None
    d = command.get("d")
    if isinstance(d, bool) or not isinstance(d, (int, float)) or d < 0 or not float(d).is_integer():
        return None
    packed = int(d)
    return packed >> 8 if packed & 0xFF else None


def _integer(value: JsonValue) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonzero(value: JsonValue) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value != 0

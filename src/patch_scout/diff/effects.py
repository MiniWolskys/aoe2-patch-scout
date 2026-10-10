# SPDX-License-Identifier: GPL-3.0-or-later
"""Effect commands as sentences (diff-rules.md, Effects; O-5 layer 2).

A template applies only when the snapshot's own `Constants.xs` names the command type, and it is
looked up by that name, not by number (game-files.md §11). The slots are those `Effects.xs`
passes to `xsEffectAmount`: `a` a unit, `b` a unit class, `c` an attribute, `d` the value. A
command that doesn't fit a template returns None, and the caller keeps the raw command: a wrong
sentence is worse than a raw one (D-04).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from patch_scout.diff.model import Message
from patch_scout.diff.values import display, unknown_id
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.snapshot import JsonObject, JsonValue

# Attributes whose value packs a class and an amount: d = class * 256 + amount (game-files.md §11).
_PACKED: Final = {8: "field.armours", 9: "field.attacks"}
# Modes from Constants.xs "Effect Type Constants": cAttributeSet/cAttributeDisable = 0,
# cAttributeAdd/cAttributeEnable = 1.
_SET, _ADD = 0, 1
_DISABLE, _ENABLE = 0, 1
TIMES: Final = "\N{MULTIPLICATION SIGN}"


@dataclass(frozen=True, slots=True)
class Lookup:
    """How a sentence names the units, techs and IDs it mentions."""

    unit: Callable[[int], str]
    tech: Callable[[int], str]
    vocabulary: Vocabulary


@dataclass(frozen=True, slots=True)
class Sentence:
    """A command as words: a label, and the value it sets, adds or multiplies by, if any."""

    label: Message
    value: str | None = None


def describe(command: JsonValue, lookup: Lookup) -> Sentence | None:
    """The command as a sentence, or None when no template fits it."""
    if not isinstance(command, dict):
        return None
    kind = lookup.vocabulary.command_type(command.get("type"))
    a, b, c = _int(command.get("a")), _int(command.get("b")), _int(command.get("c"))
    d = command.get("d")
    if not isinstance(d, (int, float)) or isinstance(d, bool) or a is None or b is None:
        return None
    if kind in ("SetAttribute", "AddAttribute", "MulAttribute"):
        return _attribute(kind, a, b, c, float(d), lookup)
    if kind == "ModResource" and b in (_SET, _ADD):
        value = f"={display(d)}" if b == _SET else _signed(d)
        return Sentence(Message("effect.resource", {"resource": _resource(a, lookup)}), value)
    if kind == "MulResource":
        return Sentence(Message("effect.resource", {"resource": _resource(a, lookup)}), _times(d))
    if kind == "EnableObject" and b in (_DISABLE, _ENABLE) and a >= 0:
        key = "effect.enable" if b == _ENABLE else "effect.disable"
        return Sentence(Message(key, {"unit": lookup.unit(a)}))
    if kind == "UpgradeUnit" and a >= 0 and b >= 0:
        return Sentence(Message("effect.upgrade", {"unit": lookup.unit(a), "to": lookup.unit(b)}))
    if kind == "DisableTech" and float(d).is_integer() and d >= 0:
        return Sentence(Message("effect.disable_tech", {"tech": lookup.tech(int(d))}))
    return None


def _attribute(
    kind: str, a: int, b: int, c: int | None, d: float, lookup: Lookup
) -> Sentence | None:
    target = _target(a, b, lookup)
    if target is None or c is None:
        return None
    if c in _PACKED:
        if kind == "MulAttribute" or d < 0 or not d.is_integer():
            return None
        armour_class, amount = int(d) >> 8, int(d) & 0xFF
        name = lookup.vocabulary.armour_class(armour_class) or unknown_id(armour_class)
        attribute: JsonValue = Message(_PACKED[c], {"class": name}).to_json()
        value = f"={amount}" if kind == "SetAttribute" else _signed(amount)
    else:
        named = lookup.vocabulary.attribute(c)
        if named is None:
            return None
        attribute = named
        if kind == "SetAttribute":
            value = f"={display(d)}"
        elif kind == "AddAttribute":
            value = _signed(d)
        else:
            value = _times(d)
    return Sentence(Message("effect.attribute", {"target": target, "attribute": attribute}), value)


def _target(a: int, b: int, lookup: Lookup) -> JsonValue:
    """A unit, or a whole unit class when the command names no unit."""
    if a >= 0:
        return lookup.unit(a)
    if b >= 0:
        name = lookup.vocabulary.unit_class(b) or unknown_id(b)
        message: JsonObject = Message("effect.class_target", {"class": name}).to_json()
        return message
    return None


def _resource(resource: int, lookup: Lookup) -> str:
    return lookup.vocabulary.resource(resource) or unknown_id(resource)


def _signed(value: float) -> str:
    text = display(float(value) if not isinstance(value, int) else value)
    return text if text.startswith("-") else f"+{text}"


def _times(value: float) -> str:
    return f"{TIMES}{display(float(value))}"


def _int(value: JsonValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None

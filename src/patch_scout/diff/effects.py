# SPDX-License-Identifier: GPL-3.0-or-later
"""Effect commands as sentences (diff-rules.md, Effects; O-5 layer 2).

A template applies only when the snapshot's own `Constants.xs` names the command type, and it is
looked up by that name, not by number (game-files.md §11). The slots are those `Effects.xs`
passes to `xsEffectAmount`: `a` a unit, `b` a unit class, `c` an attribute, `d` the value. A
command that doesn't fit a template returns None, and the caller keeps the raw command: a wrong
sentence is worse than a raw one (D-04).
"""

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

from patch_scout.diff.model import Message
from patch_scout.diff.values import display, pair, unknown_id
from patch_scout.diff.vocabulary import Vocabulary, label
from patch_scout.snapshot import JsonObject, JsonValue

# Attributes, by XS name, whose value packs a class and an amount: d = class * 256 + amount
# (game-files.md §11).
_PACKED: Final = {"Armor": "field.armours", "Attack": "field.attacks"}
# Attributes whose value probably packs too, in a way not verified yet: they stay raw.
_UNVERIFIED: Final = frozenset(
    {"ResourceCost", "AddArmorType", "AddAttackType", "RemoveArmorType", "RemoveAttackType"}
)
# Modes from Constants.xs "Effect Type Constants": cAttributeSet/cAttributeDisable = 0,
# cAttributeAdd/cAttributeEnable = 1.
_SET, _ADD = 0, 1
_DISABLE, _ENABLE = 0, 1
TIMES: Final = "\N{MULTIPLICATION SIGN}"
# AddTechCost and ModTechTime: `a` a tech, `b` a resource (-1 every one), `c` the mode. Only the
# modes that bonuses named after them confirm (101.103.54800.0) get a sentence: 0 sets ("free
# Careening, Dry Dock" sets food and gold to 0) and 2 multiplies (Italians, "Age up 15% cheaper":
# x0.85). The others, 1 and -1, stay raw.
_TECH_SET, _TECH_MUL = 0, 2
_ALL_RESOURCES: Final = -1
_COST_RESOURCES: Final = frozenset({0, 1, 2, 3})  # food, wood, stone, gold
# The player resource that, when set, runs a function of Effects.xs (its Constants.xs name).
_SCRIPT_RESOURCE: Final = "EffectFunctionNumber"
# A numbered function's title comment in Effects.xs, e.g. "// 52 - Effect of Kasbah for Berbers".
_SCRIPT_TITLE: Final = re.compile(r"^//\s*(\d+)\s*-\s*(.+?)\s*$", re.MULTILINE)


@dataclass(frozen=True, slots=True)
class Lookup:
    """How a sentence names the units, techs and IDs it mentions."""

    unit: Callable[[int], str]
    tech: Callable[[int], str]
    vocabulary: Vocabulary
    # A scripted effect's title in Effects.xs, by function number; None when it has none.
    script: Callable[[int], str | None]


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
    if (
        kind == "ModResource"
        and b == _SET
        and lookup.vocabulary.resource_identifier(a) == _SCRIPT_RESOURCE
        and float(d).is_integer()
        and d >= 0
    ):
        # Setting this resource runs that function of Effects.xs: the Kasbah tech sets it to 52,
        # "Effect of Kasbah for Berbers" (game-files.md §11).
        title = lookup.script(int(d)) or unknown_id(int(d))
        return Sentence(Message("effect.script", {"title": title}))
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
    if kind in ("AddTechCost", "ModTechTime") and a >= 0 and c in (_TECH_SET, _TECH_MUL):
        return _tech_cost_or_time(kind, a, b, c, float(d), lookup)
    if kind == "DisableTech" and float(d).is_integer() and d >= 0:
        return Sentence(Message("effect.disable_tech", {"tech": lookup.tech(int(d))}))
    return None


def _attribute(
    kind: str, a: int, b: int, c: int | None, d: float, lookup: Lookup
) -> Sentence | None:
    target = _target(a, b, lookup)
    if target is None or c is None:
        return None
    identifier = lookup.vocabulary.attribute_identifier(c)
    if identifier is None or identifier in _UNVERIFIED:
        return None
    if identifier in _PACKED:
        if kind == "MulAttribute" or d < 0 or not d.is_integer():
            return None
        armour_class, amount = int(d) >> 8, int(d) & 0xFF
        name = lookup.vocabulary.armour_class(armour_class) or unknown_id(armour_class)
        attribute: JsonValue = Message(_PACKED[identifier], {"class": name}).to_json()
        value = f"={amount}" if kind == "SetAttribute" else _signed(amount)
    else:
        attribute = label(identifier)
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


def _tech_cost_or_time(
    kind: str, tech: int, resource: int, mode: int, value: float, lookup: Lookup
) -> Sentence | None:
    shown = f"={display(value)}" if mode == _TECH_SET else _times(value)
    name = lookup.tech(tech)
    if kind == "ModTechTime":
        if resource != _ALL_RESOURCES:
            return None  # a resource slot on a time: not explained yet
        return Sentence(Message("effect.tech_time", {"tech": name}), shown)
    if resource == _ALL_RESOURCES:
        return Sentence(Message("effect.tech_cost", {"tech": name}), shown)
    if resource not in _COST_RESOURCES:
        return None
    resource_name = _resource(resource, lookup)
    message = Message("effect.tech_resource_cost", {"tech": name, "resource": resource_name})
    return Sentence(message, shown)


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


def raw_pair(old: JsonValue, new: JsonValue) -> tuple[str, str]:
    """Both sides of a raw command, formatted together so their numbers line up (O-5, layer 3)."""
    old_fields = old if isinstance(old, dict) else {}
    new_fields = new if isinstance(new, dict) else {}
    old_parts: list[str] = []
    new_parts: list[str] = []
    for key in ("type", "a", "b", "c", "d"):
        prefix = "type " if key == "type" else f"{key}="
        old_value, new_value = pair(old_fields.get(key), new_fields.get(key))
        old_parts.append(f"{prefix}{old_value}")
        new_parts.append(f"{prefix}{new_value}")
    return (
        " ".join(old_parts) if old_fields else "",
        " ".join(new_parts) if new_fields else "",
    )


def script_titles(text: str) -> dict[int, str]:
    """Each numbered function's title in Effects.xs; the first title of a number wins."""
    titles: dict[int, str] = {}
    for number, title in _SCRIPT_TITLE.findall(text):
        titles.setdefault(int(number), title)
    return titles


def script_functions(text: str) -> dict[int, tuple[str, str]]:
    """Each numbered function of Effects.xs as (title, code up to the next title), by number.

    A number used twice (the file has two `// 9 -` sections) keeps both parts, joined.
    """
    found: dict[int, tuple[str, str]] = {}
    matches = list(_SCRIPT_TITLE.finditer(text))
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        number, title = int(match.group(1)), match.group(2)
        code = text[match.end() : end].strip()
        if number in found:
            first_title, first_code = found[number]
            found[number] = (first_title, f"{first_code}\n{code}")
        else:
            found[number] = (title, code)
    return found

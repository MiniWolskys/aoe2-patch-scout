# SPDX-License-Identifier: GPL-3.0-or-later
"""Which effect commands affect a unit, a building or a tech (diff-rules.md, "What affects").

A command is matched by what its type says its slots mean, never by "slot `a` holds the ID":
the slots of `AddTechCost` name a tech, those of `AddAttribute` a unit, and the IDs of units and
techs overlap. On 101.103.54800.0 the Bulgarians' tech tree effect halves the cost of tech 74,
Scale Mail Armor, which is not the Militia, unit 74. Command types are looked up by their name
in the snapshot's `Constants.xs`, as `effects.describe` does (game-files.md §11).
"""

from dataclasses import dataclass
from typing import Final, Literal

from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.snapshot import JsonValue

type Kind = Literal["unit", "building", "tech"]

_ATTRIBUTES: Final = frozenset({"SetAttribute", "AddAttribute", "MulAttribute"})
_TECH_COSTS: Final = frozenset({"AddTechCost", "ModTechTime"})
# `a` is -1 when a command names a class (`b`) instead of a unit (effects.py, `_target`).
_NO_UNIT: Final = -1
# The player resource that, when set, runs a function of Effects.xs (effects.py).
_SCRIPT_RESOURCE: Final = "EffectFunctionNumber"
_SET: Final = 0


@dataclass(frozen=True, slots=True)
class Target:
    """What a command may affect: a unit or building (with its class, when known), or a tech."""

    kind: Kind
    id: int
    unit_class: int | None = None


def affects(command: JsonValue, target: Target, vocabulary: Vocabulary) -> bool:
    """Whether the command changes the target itself.

    `DisableTech` is left out: it makes a tech unavailable, which the tech tree already says.
    """
    if not isinstance(command, dict):
        return False
    kind = vocabulary.command_type(command.get("type"))
    a, b = _int(command.get("a")), _int(command.get("b"))
    if kind is None or a is None:
        return False
    if target.kind == "tech":
        return kind in _TECH_COSTS and a == target.id
    if kind in _ATTRIBUTES:
        if a == target.id:
            return True
        return a == _NO_UNIT and target.unit_class is not None and b == target.unit_class
    if kind == "EnableObject":
        return a == target.id
    if kind == "UpgradeUnit":
        # An upgrade to the same unit only swaps its graphics: each age-up "upgrades" the Town
        # Center to the Town Center (101.103.54800.0).
        return a != b and target.id in (a, b)
    return False


def script_number(command: JsonValue, vocabulary: Vocabulary) -> int | None:
    """The Effects.xs function a command runs, or None when it runs none (game-files.md §11)."""
    if not isinstance(command, dict):
        return None
    if vocabulary.command_type(command.get("type")) != "ModResource":
        return None
    if vocabulary.resource_identifier(command.get("a")) != _SCRIPT_RESOURCE:
        return None
    if _int(command.get("b")) != _SET:
        return None
    number = _int(command.get("d"))
    return number if number is not None and number >= 0 else None


def _int(value: JsonValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None

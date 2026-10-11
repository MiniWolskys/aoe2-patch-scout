# SPDX-License-Identifier: GPL-3.0-or-later
"""Give each change a level: headline, detail or technical (diff-rules.md, Levels).

The rules come from measuring a real patch against its official notes (101.103.48987.0 →
101.103.54800.0): about half of what the comparison reported mattered to no player. A level only
decides what is shown by default; every change stays in the change set, and the filters bring
details and technical changes back. A rule that could hide a real change is not a rule here.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import Final, Literal

from patch_scout.diff.model import Change, Level
from patch_scout.diff.values import unknown_id
from patch_scout.diff.vocabulary import Vocabulary

# Unit fields that tune behaviour rather than what a player compares: AI search range, carried
# resources, interface and projectile plumbing.
_DETAIL_UNIT_FIELDS: Final = frozenset(
    {
        "field.search_radius",
        "field.resource_capacity",
        "field.resource_decay",
        "field.button_icon_id",
        "field.accuracy_dispersion",
        "field.base_armor",
        "field.charge_event",
        "field.charge_type",
        "field.charge_target",
        "field.projectile_unit_id",
        "field.secondary_projectile_unit",
        "field.charge_projectile_unit",
        "field.special_ability",
        "field.invulnerability_level",
        "field.friendly_fire_damage",
    }
)
_BLAST_LEVELS: Final = frozenset({"field.blast_attack_level", "field.blast_defense_level"})
_BY_CLASS: Final = frozenset(
    {"field.armours", "field.attacks", "field.armours_basic", "field.attacks_basic"}
)
# Bookkeeping on techs: the effect itself, when it changed, is reported with its commands.
_DETAIL_TECH_FIELDS: Final = frozenset(
    {"field.repeatable", "field.required_tech_count", "field.tech_type"}
)
# A civ's tech tree effect: the availability category already says what it does.
_TREE_EFFECT: Final = "field.tech_tree_effect"
# What a tech tree sentence says that the Availability category already shows.
_AVAILABILITY_SENTENCES: Final = frozenset(
    {"effect.disable_tech", "effect.enable", "effect.disable"}
)
_EFFECT_IDS: Final = frozenset(
    {"field.tech_effect", "field.effect_id", "field.tech_tree_effect", "field.team_bonus_effect"}
)
_AVAILABLE: Final = frozenset({"ResearchRequired", "ResearchedCompleted"})
# Differences smaller than this share of the value are rounding, e.g. 0.99999 → 1.
_ROUNDING: Final = 1e-3


# Where a unit's blast width comes from, in either build: its own record, an effect, or nowhere.
type BlastWidth = Literal["own", "granted", "none"]


@dataclass(frozen=True, slots=True)
class Context:
    """What the rules need beyond the changes themselves."""

    vocabulary: Vocabulary
    blast_width: Callable[[str], BlastWidth]


def assign(changes: Sequence[Change], context: Context) -> list[Change]:
    """The changes with their levels set; the order is kept."""
    leveled = [replace(change, level=_level(change, context)) for change in changes]
    return _repeated_displayed_stats(leveled, context)


def _level(change: Change, context: Context) -> Level:
    key = _field_key(change)
    if change.category == "unit_stats":
        if key in _DETAIL_UNIT_FIELDS:
            return "detail"
        if key in _BLAST_LEVELS:
            # Without a width the level does nothing. With one only a tech gives, the tech's own
            # line says what changes, and the level alone reads as if every civ gained trample.
            width = context.blast_width(change.entity.id)
            if width != "own":
                return "technical" if width == "none" else "detail"
        if key in _BY_CLASS and {change.old or "", change.new or ""} <= {"", "0"}:
            return "technical"
    elif change.category == "civ_availability":
        if key in ("field.offered_units", "field.offered_techs"):
            return "detail"
        if (
            key == "field.node_status"
            and change.entity.kind == "building"
            and {change.old, change.new} == _AVAILABLE
        ):
            return "detail"
    elif change.category in ("techs", "bonuses", "other_effects"):
        return _effect_level(change, key)
    elif (
        change.category == "text"
        and change.detail
        and change.detail.key == "detail.whitespace_only"
    ):
        return "technical"
    return "headline"


def _effect_level(change: Change, key: str | None) -> Level:
    if key in _DETAIL_TECH_FIELDS:
        return "detail"
    raw = change.detail is not None and change.detail.key == "detail.effect_command"
    if raw:
        # A command with no sentence may still be a real change (the Huns' Atheism on
        # 101.103.54800.0 uses unnamed types), so only tech tree commands step back.
        return "technical" if key == _TREE_EFFECT else "headline"
    if _availability_sentence(change):
        return "detail"
    if change.detail is None and key in _EFFECT_IDS:
        return "detail"  # an effect ID; its commands are reported on their own lines
    if _rounding(change.old, change.new):
        return "technical"
    return "headline"


def _availability_sentence(change: Change) -> bool:
    """A civ's tech tree enabling or disabling something: Availability says it already.

    Treadmill Crane on 101.103.54800.0 read twice: "Available → Not available (Bengalis, …)" and
    "Bengalis · New: Disables Treadmill Crane".
    """
    detail = change.detail
    if detail is None or detail.key != "detail.effect_command_raw" or change.field is None:
        return False
    if detail.args.get("source") != _TREE_EFFECT:
        return False
    sentence = change.field.args.get("effect")
    key = sentence.get("key") if isinstance(sentence, dict) else change.field.key
    return key in _AVAILABILITY_SENTENCES


def _rounding(old: str | None, new: str | None) -> bool:
    before, after = _number(old), _number(new)
    if before is None or after is None or before == after:
        return False
    scale = max(abs(before), abs(after))
    return abs(after - before) <= _ROUNDING * scale


def _number(text: str | None) -> float | None:
    if not text:
        return None
    try:
        return float(text.lstrip("=+\N{MULTIPLICATION SIGN}"))
    except ValueError:
        return None


# --- displayed stats -----------------------------------------------------------------------------

# A displayed stat and the stats it repeats; None means any attack class.
_ATTACKS: Final = frozenset({"field.attacks", "field.attacks_basic"})
_DISPLAYED: Final[dict[str, tuple[frozenset[str], int | None]]] = {
    "field.displayed_melee_armour": (frozenset({"field.armours_basic"}), 4),
    "field.displayed_pierce_armour": (frozenset({"field.armours_basic"}), 3),
    "field.displayed_attack": (_ATTACKS, None),
    "field.displayed_range": (frozenset({"field.max_range"}), None),
    "field.displayed_reload_time": (frozenset({"field.reload_time"}), None),
}


def _repeated_displayed_stats(changes: list[Change], context: Context) -> list[Change]:
    """A displayed stat that moved exactly like the stat it shows is a detail.

    The Hulk's melee armour went 4 → 3 twice on 101.103.54800.0: as a class and as displayed.
    """
    groups: dict[tuple[object, ...], list[int]] = {}
    for index, change in enumerate(changes):
        if change.category == "unit_stats":
            groups.setdefault(_unit_group(change), []).append(index)
    result = list(changes)
    for indexes in groups.values():
        for index in indexes:
            change = result[index]
            partner = _DISPLAYED.get(_field_key(change) or "")
            if partner is None or change.level != "headline":
                continue
            if any(
                _repeats(change, result[other], partner, context)
                for other in indexes
                if other != index
            ):
                result[index] = replace(change, level="detail")
    return result


def _repeats(
    shown: Change, other: Change, partner: tuple[frozenset[str], int | None], context: Context
) -> bool:
    keys, armour_class = partner
    if _field_key(other) not in keys or (shown.old, shown.new) != (other.old, other.new):
        return False
    if armour_class is None:
        return True
    name = context.vocabulary.armour_class(armour_class) or unknown_id(armour_class)
    return _field_args(other).get("class") == name


def _unit_group(change: Change) -> tuple[object, ...]:
    projectile = change.field is not None and change.field.key == "field.projectile"
    return (change.entity.kind, change.entity.id, change.civ, change.scope, projectile)


def _field_key(change: Change) -> str | None:
    """The field's key, looking inside "Projectile: {field}"."""
    if change.field is None:
        return None
    nested = change.field.args.get("field")
    if change.field.key == "field.projectile" and isinstance(nested, dict):
        key = nested.get("key")
        return key if isinstance(key, str) else None
    return change.field.key


def _field_args(change: Change) -> dict[str, object]:
    if change.field is None:
        return {}
    nested = change.field.args.get("field")
    if change.field.key == "field.projectile" and isinstance(nested, dict):
        args = nested.get("args")
        return dict(args) if isinstance(args, dict) else {}
    return dict(change.field.args)

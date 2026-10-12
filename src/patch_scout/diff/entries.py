# SPDX-License-Identifier: GPL-3.0-or-later
"""Group field-level changes into one entry per entity (diff-rules.md, One entry per entity).

The change set is field-level: one `Change` per field, per value group. A reader wants one item
per unit or tech, with all its changed fields, so this pass groups the changes that share an
entity, a page and a scope. A scope stays part of the key, so civ information is never merged.
"""

from collections.abc import Iterable
from typing import Final

from patch_scout.diff.model import Change, Entry, Kind

# The stats a brand-new entity's entry shows; the rest are counted in `Entry.hidden`.
MAIN_FIELDS: Final = frozenset(
    {
        "field.hit_points",
        "field.line_of_sight",
        "field.speed",
        "field.attacks",
        "field.attacks_basic",
        "field.armours",
        "field.armours_basic",
        "field.displayed_attack",
        "field.displayed_melee_armour",
        "field.displayed_pierce_armour",
        "field.max_range",
        "field.reload_time",
        "field.cost",
        "field.train_locations",
        "field.build_time",
    }
)
# Values that say "nothing here" for a new entity, e.g. a garrison capacity of 0.
DEFAULT_VALUES: Final = frozenset({"", "0", "-1"})
# Tech fields that are bookkeeping, not something players compare (diff-rules.md, Levels).
TECH_BOOKKEEPING: Final = frozenset(
    {"field.required_tech_count", "field.repeatable", "field.tech_type"}
)

type _Key = tuple[object, ...]


def group(changes: Iterable[Change]) -> tuple[Entry, ...]:
    """One entry per (category, page, entity, scope), in the order of each entry's first change."""
    buckets: dict[_Key, list[Change]] = {}
    for position, change in enumerate(changes):
        buckets.setdefault(_key(change, position), []).append(change)
    return tuple(_entry(members) for members in buckets.values())


def _key(change: Change, position: int) -> _Key:
    if change.field is None:
        # "Added: Jarl (Castle)" and the like carry no field: each is an entry of its own.
        return ("alone", position)
    entity = change.entity
    scope = change.scope
    return (
        change.category,
        change.civ,
        entity.kind,
        entity.id,
        entity.where,
        scope.kind,
        scope.civs,
        scope.count,
    )


def _entry(members: list[Change]) -> Entry:
    members = _distinct(members)
    first = members[0]
    kind: Kind = first.kind if len(members) == 1 else "modified"
    # A field that only appears or disappears with a default value says nothing to a reader.
    shown = [change for change in members if not _trivial(change)] or members[:1]
    # Only a unit's stats read as "a new unit": other categories keep every change they have.
    stats = first.category == "unit_stats"
    if stats and all(_is_new(change) for change in members) and _gains_hit_points(members):
        kind = "added"
        shown = [change for change in members if _worth_showing(change)]
    elif stats and len(members) > 1 and all(_is_gone(change) for change in members):
        kind = "removed"
        shown = []
    elif first.category == "techs" and _is_new_tech(members):
        kind = "added"
    return Entry(
        category=first.category,
        kind=kind,
        entity=first.entity,
        scope=first.scope,
        civ=first.civ,
        changes=tuple(shown),
        hidden=len(members) - len(shown),
    )


def _distinct(members: list[Change]) -> list[Change]:
    """The changes without lines that read exactly like an earlier one.

    The game has several records for some buildings, one per look, all named alike: an effect on
    each read "Dock: Garrison Capacity · removed +5" four times (Gurjaras on 101.103.54800.0).
    The change set keeps them all; only the entry lists the line once.
    """
    seen: set[tuple[object, ...]] = set()
    distinct: list[Change] = []
    for change in members:
        field = change.field.to_json() if change.field is not None else None
        key = (repr(field), change.kind, change.old, change.new, change.level, tuple(change.words))
        if key not in seen:
            seen.add(key)
            distinct.append(change)
    return distinct


def _is_new(change: Change) -> bool:
    return change.kind == "modified" and not change.old and bool(change.new)


def _gains_hit_points(members: list[Change]) -> bool:
    """Whether a unit gains its hit points: every unit has them, so a new one always does.

    A unit that only gains a value in a new slot is not new: the Missionary gained a food cost
    (Spanish, 101.103.54800.0).
    """
    return any(
        change.field is not None and change.field.key == "field.hit_points" for change in members
    )


def _trivial(change: Change) -> bool:
    if change.kind != "modified" or change.field is None:
        return False
    old, new = change.old or "", change.new or ""
    if not old and not new:
        # A sentence that says it all in its label, e.g. "New: Enables Champi Runner" (101.103.
        # 54800.0): it has no value because it needs none, and it is never trivial.
        return False
    return (not old and new in DEFAULT_VALUES) or (not new and old in DEFAULT_VALUES)


def _is_new_tech(members: list[Change]) -> bool:
    """A tech that only gains values, a place to research it among them, is new to players.

    A tech players could research always has a research location, so gaining one means it wasn't
    researchable before: either a new record, or a placeholder the patch fills in (Ordonnance
    Companies and Cranequins on 101.103.54800.0). A tech that only gains an effect is not new.
    An effect sentence without a value ("New: Enables X") is new too. Bookkeeping fields, such as
    a placeholder's effect ID of -1, and default values, such as its research time of 0, say
    nothing either way (diff-rules.md, Levels).
    """
    located = any(
        change.field is not None
        and change.field.key == "field.research_locations"
        and _is_new(change)
        and not _trivial(change)
        for change in members
    )
    return located and all(
        _is_new(change)
        or _bookkeeping(change)
        or _trivial(change)
        or (change.kind == "modified" and not change.old and not change.new)
        for change in members
    )


def _bookkeeping(change: Change) -> bool:
    """A tech field players never see: its flags, required count, or which effect it points at."""
    if change.field is None:
        return False
    if change.field.key == "field.tech_effect":
        # The effect ID itself; its commands carry a detail naming the command.
        return change.detail is None
    return change.field.key in TECH_BOOKKEEPING


def _is_gone(change: Change) -> bool:
    return change.kind == "modified" and bool(change.old) and not change.new


def _worth_showing(change: Change) -> bool:
    field = change.field
    return (
        field is not None and field.key in MAIN_FIELDS and (change.new or "") not in DEFAULT_VALUES
    )

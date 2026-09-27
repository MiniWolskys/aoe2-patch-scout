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
        "field.armours",
        "field.displayed_attack",
        "field.displayed_melee_armour",
        "field.displayed_pierce_armour",
        "field.max_range",
        "field.reload_time",
        "field.cost",
        "field.train_locations",
    }
)
# Values that say "nothing here" for a new entity, e.g. a garrison capacity of 0.
DEFAULT_VALUES: Final = frozenset({"", "0", "-1"})

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
    first = members[0]
    kind: Kind = first.kind if len(members) == 1 else "modified"
    # A field that only appears or disappears with a default value says nothing to a reader.
    shown = [change for change in members if not _trivial(change)] or members[:1]
    # Only a unit's stats read as "a new unit": other categories keep every change they have.
    stats = first.category == "unit_stats"
    if stats and all(_is_new(change) for change in members):
        kind = "added"
        shown = [change for change in members if _worth_showing(change)]
    elif stats and len(members) > 1 and all(_is_gone(change) for change in members):
        kind = "removed"
        shown = []
    return Entry(
        category=first.category,
        kind=kind,
        entity=first.entity,
        scope=first.scope,
        civ=first.civ,
        changes=tuple(shown),
        hidden=len(members) - len(shown),
    )


def _is_new(change: Change) -> bool:
    return change.kind == "modified" and not change.old and bool(change.new)


def _trivial(change: Change) -> bool:
    if change.kind != "modified" or change.field is None:
        return False
    old, new = change.old or "", change.new or ""
    return (not old and new in DEFAULT_VALUES) or (not new and old in DEFAULT_VALUES)


def _is_gone(change: Change) -> bool:
    return change.kind == "modified" and bool(change.old) and not change.new


def _worth_showing(change: Change) -> bool:
    field = change.field
    return (
        field is not None and field.key in MAIN_FIELDS and (change.new or "") not in DEFAULT_VALUES
    )

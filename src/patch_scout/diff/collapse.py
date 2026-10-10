# SPDX-License-Identifier: GPL-3.0-or-later
"""Group a per-civ change by the value pair it produced (D-07, diff-rules.md).

A stat that changed the same way everywhere reads as one line, "(all civs)"; one that changed
for a few civs names them, which is usually where a civ bonus changed.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from patch_scout.diff.model import Scope
from patch_scout.snapshot import JsonValue

# Lists longer than this are truncated by the renderer, never by the change set (diff-rules.md).
MAX_NAMED_CIVS = 8


@dataclass(frozen=True, slots=True)
class Group:
    """One value pair and the civs it applies to."""

    old: JsonValue
    new: JsonValue
    scope: Scope
    size: int


def collapse(
    in_scope: Sequence[str],
    changed: Mapping[str, tuple[JsonValue, JsonValue]],
    *,
    every: Sequence[str],
) -> list[Group]:
    """Group the civs that changed by their (old, new) pair, largest group first.

    `in_scope` is every civ the entity exists in and is reachable for; `changed` holds only the
    civs whose value actually differs; `every` is every civ in the comparison, which decides
    whether "all civilizations" is true.
    """
    if not changed:
        return []
    buckets: dict[str, list[str]] = {}
    values: dict[str, tuple[JsonValue, JsonValue]] = {}
    order = {name: index for index, name in enumerate(in_scope)}
    for civ in sorted(changed, key=lambda name: order.get(name, len(order))):
        pair = changed[civ]
        key = repr(pair)
        buckets.setdefault(key, []).append(civ)
        values[key] = pair
    groups = [
        Group(
            old=values[key][0],
            new=values[key][1],
            scope=_scope(in_scope, civs, every, single=len(buckets) == 1),
            size=len(civs),
        )
        for key, civs in buckets.items()
    ]
    groups.sort(key=lambda group: (-group.size, group.scope.civs))
    return groups


def _scope(
    in_scope: Sequence[str], civs: Sequence[str], every: Sequence[str], *, single: bool
) -> Scope:
    """Choose between "all civs", "all civs that have it", their "except" forms, and naming."""
    everywhere = set(in_scope) >= set(every)
    if single and len(civs) == len(in_scope) and in_scope:
        if everywhere:
            return Scope("all")
        # An entity only a few civs have: naming them says more than "all" (diff-rules.md).
        if len(in_scope) > MAX_NAMED_CIVS:
            return Scope("having", count=len(in_scope))
        return Scope("some", tuple(civs))
    missing = [name for name in in_scope if name not in set(civs)]
    # The "except" forms only when they really are shorter to read (diff-rules.md, Thresholds).
    if single and missing and len(missing) < len(civs):
        if everywhere:
            return Scope("all_except", tuple(missing))
        if len(in_scope) > MAX_NAMED_CIVS:
            return Scope("having_except", tuple(missing), count=len(in_scope))
    return Scope("some", tuple(civs))

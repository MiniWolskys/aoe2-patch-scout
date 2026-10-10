# SPDX-License-Identifier: GPL-3.0-or-later
"""One civ's tech tree as the page draws it, with a comparison's changes marked (D-39).

The newer version's tree is drawn. A node the newer tree dropped is drawn from the older one.
Marks compare the two trees (gained, lost) and read the change set (changed, renamed). The
hover panel uses the game's own tooltip template, filled with the civ's own values: values
before civ bonuses and techs, as the game's tech tree shows them (D-20).
"""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from typing import Final

from patch_scout.diff.model import Change, ChangeSet
from patch_scout.diff.names import Names
from patch_scout.diff.reachability import UnitLookup
from patch_scout.diff.values import at_path, display, pair, words
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot
from patch_scout.tree.layout import NodeIn, layout
from patch_scout.tree.tooltip import STATS, Run, parse

_UNAVAILABLE: Final = "NotAvailable"
# Where the template's stats live in a unit or building record (verified on 101.103.54800.0).
_STAT_PATHS: Final = {
    "hp": "hit_points",
    "attack": "type_50.displayed_attack",
    "armor": "type_50.displayed_melee_armour",
    "piercearmor": "creatable.displayed_pierce_armour",
    "range": "type_50.displayed_range",
    "garrison": "garrison_capacity",
}
_RESOURCES: Final = {0: "food", 1: "wood", 2: "stone", 3: "gold"}


@dataclass(frozen=True, slots=True)
class _Side:
    """One snapshot, read for one civ."""

    snapshot: Snapshot
    names: Names
    units: UnitLookup
    index: int | None
    nodes: dict[str, JsonObject]

    @classmethod
    def of(cls, snapshot: Snapshot, civ: str, language: str) -> "_Side":
        tree = snapshot.tech_trees.get(civ)
        nodes: dict[str, JsonObject] = {}
        for node in tree if isinstance(tree, list) else []:
            key = _key(node)
            if key is not None and isinstance(node, dict):
                nodes.setdefault(key, node)
        names, units = Names(snapshot, language), UnitLookup(snapshot)
        return cls(snapshot, names, units, _index(snapshot, civ), nodes)

    @property
    def has_civ(self) -> bool:
        return bool(self.nodes)


def build(
    old: Snapshot,
    new: Snapshot,
    change_set: ChangeSet,
    civ: str,
    *,
    details: bool = False,
    technical: bool = False,
    low_priority: bool = False,
    language: str = "en",
) -> JsonObject | None:
    """The civ's tree; None when neither version has a tech tree for it.

    A node is marked changed only by changes the comparison shows with the same filters: the
    levels chosen, and the low-priority categories (texts, icons) when those are on.
    """
    before, after = _Side.of(old, civ, language), _Side.of(new, civ, language)
    if not before.has_civ and not after.has_civ:
        return None
    drawn: dict[str, tuple[JsonObject, _Side]] = {key: (n, after) for key, n in after.nodes.items()}
    for key, node in before.nodes.items():
        if key not in drawn and _available(node):
            drawn[key] = (node, before)  # dropped by the newer tree: drawn as it was
    placed = layout([_layout_node(key, node) for key, (node, _) in drawn.items()])
    # The same filters as the change list: each level has its own switch.
    levels = (
        {"headline"} | ({"detail"} if details else set()) | ({"technical"} if technical else set())
    )
    changes = [
        c for c in change_set.changes if c.level in levels and (low_priority or not c.low_priority)
    ]
    nodes: list[JsonValue] = []
    for key, (node, side) in drawn.items():
        place = placed.places[key]
        node_changes = [c for c in changes if _concerns(c, node, civ)]
        mark = _mark(key, node, node_changes, before, after)
        if mark is None and not _available(node):
            node_changes = []  # changes for the civs that have it; this civ doesn't
        nodes.append(
            {
                "key": key,
                "kind": str(node.get("use_type", "")).lower(),
                "node_type": node.get("node_type"),
                "name": _name(side, civ, node),
                "old_name": _old_name(node_changes),
                # As drawn: a node from the older tree is shown as it was, marked lost.
                "available": _available(node),
                "mark": mark,
                "icon": node.get("icon") if isinstance(node.get("icon"), dict) else None,
                "group": place.group,
                "column": place.column,
                "row": place.row,
                "tooltip": _tooltip(key, node, side, before, after, civ),
                "changes": [change.to_json() for change in node_changes],
            }
        )
    return {
        "civ": civ,
        "new_civ": not before.has_civ,
        "removed_civ": not after.has_civ,
        "columns": placed.columns,
        "groups": placed.groups,
        "rows": placed.rows,
        "age_rows": list(placed.age_rows),
        "nodes": nodes,
        "links": [[child, parent] for child, parent in placed.links],
        "bonus": [run.to_json() for run in words(_bonus(before, civ), _bonus(after, civ))],
    }


# --- marks ----------------------------------------------------------------------------------


def _mark(
    key: str, node: JsonObject, changes: list[Change], before: _Side, after: _Side
) -> str | None:
    if before.has_civ and after.has_civ:
        was = before.nodes.get(key)
        now = after.nodes.get(key)
        was_available = was is not None and _available(was)
        now_available = now is not None and _available(now)
        if now_available and not was_available:
            return "gained"
        if was_available and not now_available:
            return "lost"
    elif not after.has_civ:
        return "lost" if _available(before.nodes[key]) else None
    if not _available(node):
        return None  # "all civilizations that have it" says nothing about a civ without it
    if any(change.kind == "renamed" for change in changes):
        return "renamed"
    return "changed" if changes else None


def _concerns(change: Change, node: JsonObject, civ: str) -> bool:
    """Whether a change is about this node, for this civ."""
    entity = change.entity
    kind, node_id = str(node.get("use_type", "")).lower(), str(node.get("node_id"))
    if entity.kind != kind or entity.id != node_id:
        return False
    if change.civ is not None:
        return change.civ == civ
    scope = change.scope
    # Global: a generic tech such as Loom, which no civ owns, read under Overall.
    if scope.kind in ("all", "having", "global"):
        return True
    if scope.kind in ("all_except", "having_except"):
        return civ not in scope.civs
    return scope.kind == "some" and civ in scope.civs


def _old_name(changes: Iterable[Change]) -> str | None:
    for change in changes:
        if change.kind == "renamed" and change.old:
            return change.old
    return None


# --- tooltip ----------------------------------------------------------------------------------


def _tooltip(
    key: str, node: JsonObject, side: _Side, before: _Side, after: _Side, civ: str
) -> JsonObject:
    template = side.names.help_text(node.get("help_string_id")) or ""
    if not template and side is after and key in before.nodes:
        template = before.names.help_text(before.nodes[key].get("help_string_id")) or ""
    lines = parse(template) or [(Run("text", _name(side, civ, node), bold=True),)]
    old_record = _record(before, node)
    new_record = _record(after, node)
    return {
        "lines": [_line(line) for line in lines],
        "stats": _stats(node, old_record, new_record),
        "cost": {"old": _cost(node, old_record), "new": _cost(node, new_record)},
    }


def _line(line: tuple[Run, ...]) -> JsonValue:
    return [run.to_json() for run in line]


def _record(side: _Side, node: JsonObject) -> JsonObject | None:
    node_id = node.get("node_id")
    if not isinstance(node_id, int) or not side.has_civ:
        return None
    if node.get("use_type") == "Tech":
        techs = (side.snapshot.stats or {}).get("techs")
        tech = techs.get(str(node_id)) if isinstance(techs, dict) else None
        return tech if isinstance(tech, dict) else None
    if side.index is None:
        return None
    return side.units.record(node_id, side.index)


def _stats(
    node: JsonObject, old: JsonObject | None, new: JsonObject | None
) -> dict[str, JsonValue]:
    if node.get("use_type") == "Tech":
        return {}
    stats: dict[str, JsonValue] = {}
    for stat in STATS:
        before = _number(old, _STAT_PATHS[stat])
        after = _number(new, _STAT_PATHS[stat])
        old_text: str | None = display(before) if before is not None else None
        new_text: str | None = display(after) if after is not None else None
        if before is not None and after is not None:
            old_text, new_text = pair(before, after)
        stats[stat] = {"old": old_text, "new": new_text}
    return stats


def _number(record: JsonObject | None, path: str) -> int | float | None:
    if record is None:
        return None
    value = at_path(record, path)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _cost(node: JsonObject, record: JsonObject | None) -> list[JsonValue] | None:
    if record is None:
        return None
    path = "resource_costs" if node.get("use_type") == "Tech" else "creatable.resource_costs"
    entries = at_path(record, path)
    cost: list[JsonValue] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict) or entry.get("flag") != 1:
            continue
        resource, amount = entry.get("type"), entry.get("amount")
        if isinstance(resource, int) and resource in _RESOURCES and isinstance(amount, int):
            cost.append({"resource": _RESOURCES[resource], "amount": amount})
    return cost


# --- nodes ------------------------------------------------------------------------------------


def _layout_node(key: str, node: JsonObject) -> NodeIn:
    node_id = node.get("node_id")
    building, age, link = node.get("building_id"), node.get("age_id"), node.get("link_id")
    link_type, node_type = node.get("link_node_type"), node.get("node_type")
    return NodeIn(
        key=key,
        use_type=str(node.get("use_type", "")),
        node_id=node_id if isinstance(node_id, int) else -1,  # _key checked it already
        building_id=building if isinstance(building, int) else None,
        age=age if isinstance(age, int) else 1,
        link_id=link if isinstance(link, int) else None,
        link_type=link_type if isinstance(link_type, str) else None,
        node_type=node_type if isinstance(node_type, str) else None,
    )


def _key(node: JsonValue) -> str | None:
    if not isinstance(node, dict):
        return None
    use_type, node_id = node.get("use_type"), node.get("node_id")
    if not isinstance(use_type, str) or not isinstance(node_id, int):
        return None
    return f"{use_type}:{node_id}"


def _name(side: _Side, civ: str, node: JsonObject) -> str:
    use_type, node_id = node.get("use_type"), node.get("node_id")
    if isinstance(use_type, str) and isinstance(node_id, int):
        label = side.names.node_name(civ, use_type, node_id)
        if label:
            return label
    internal = node.get("name")
    return internal if isinstance(internal, str) and internal else f"#{node_id}"


def _available(node: JsonObject) -> bool:
    return node.get("node_status") not in (None, _UNAVAILABLE)


def _bonus(side: _Side, civ: str) -> str:
    """The civ's bonus text in one version, the game's own wording; empty when it has none."""
    for entry in side.snapshot.civs:
        if isinstance(entry, Mapping) and entry.get("internal_name") == civ:
            return side.names.text(entry.get("bonus_string_id")) or ""
    return ""


def _index(snapshot: Snapshot, civ: str) -> int | None:
    for entry in snapshot.civs:
        if isinstance(entry, Mapping) and entry.get("internal_name") == civ:
            index = entry.get("index")
            return index if isinstance(index, int) else None
    return None

# SPDX-License-Identifier: GPL-3.0-or-later
"""Where each node of a civ's tech tree goes.

The game's tech tree data gives an order, ages and links, but no positions: the game computes
them. Here each age is two rows (its buildings, then its units and techs), buildings head groups
of lanes in file order, and a line of upgrades stays in one lane when the rows below are free.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Final

ROWS: Final = 8
_UNIT_TYPES: Final = frozenset({"Unit", "UnitUpgrade", "UniqueUnit", "RegionalUnit"})
_TECH_TYPES: Final = frozenset({"Research", "UniqueTech"})
_BUILDING_TYPES: Final = frozenset({"BuildingTech", "BuildingNonTech", "RegionalBuilding"})


@dataclass(frozen=True, slots=True)
class NodeIn:
    """What the layout needs from one tech tree node."""

    key: str
    use_type: str
    node_id: int
    building_id: int | None
    age: int
    link_id: int | None
    link_type: str | None
    node_type: str | None


@dataclass(frozen=True, slots=True)
class Place:
    """A node's group, its column across the whole tree, and its row."""

    group: int
    column: int
    row: int


@dataclass(slots=True)
class Layout:
    """Every node's place, the lines from a node to the one it comes from, and the size."""

    places: dict[str, Place] = field(default_factory=dict)
    links: list[tuple[str, str]] = field(default_factory=list)
    columns: int = 0
    groups: int = 0


@dataclass(slots=True)
class _Group:
    members: list[NodeIn] = field(default_factory=list)
    taken: set[tuple[int, int]] = field(default_factory=set)
    lanes: dict[str, tuple[int, int]] = field(default_factory=dict)  # key -> (lane, row)

    def first_free(self, rows: range) -> int:
        lane = 0
        while any((lane, row) in self.taken for row in rows):
            lane += 1
        return lane

    def put(self, key: str, lane: int, row: int) -> None:
        self.taken.add((lane, row))
        self.lanes[key] = (lane, row)

    @property
    def width(self) -> int:
        return 1 + max((lane for lane, _ in self.taken), default=0)


def layout(nodes: Sequence[NodeIn]) -> Layout:
    """Each node's place, and the lines between nodes."""
    unique: dict[str, NodeIn] = {}
    for node in nodes:
        unique.setdefault(node.key, node)  # a node listed twice is drawn once
    by_id = {(node.use_type, node.node_id): node for node in unique.values()}
    groups = _groups(list(unique.values()), by_id)

    result = Layout()
    column = 0
    for index, group in enumerate(groups):
        for member in group.members:
            _place(group, member, by_id)
        for key, (lane, row) in group.lanes.items():
            result.places[key] = Place(index, column + lane, row)
        column += group.width
    result.columns = column
    result.groups = len(groups)
    for node in unique.values():
        parent = _parent(node, by_id)
        if parent is not None:
            result.links.append((node.key, parent.key))
    return result


def _groups(nodes: list[NodeIn], by_id: dict[tuple[str, int], NodeIn]) -> list[_Group]:
    """One group per root building, then one for nodes whose building isn't drawn.

    A root building follows the building it needs, as in the game: the file lists the Archery
    Range before the Barracks, the game draws Barracks, Archery Range, Stable.
    """
    buildings = [node for node in nodes if node.use_type == "Building"]
    # Towers, walls, the Mill's Farm and Market, and the Fish Trap (from the Fishing Ship) grow
    # from another node in place: they join that node's group.
    stacked = [n for n in buildings if n.node_type == "BuildingNonTech" and _parent(n, by_id)]
    stacked_keys = {node.key for node in stacked}
    roots = [node for node in buildings if node.key not in stacked_keys]
    group_of: dict[int, int] = {}  # building node ID -> group index
    groups: list[_Group] = []
    for root in _root_order(roots, by_id):
        group_of[root.node_id] = len(groups)
        groups.append(_Group(members=[root]))
    pending = stacked
    while pending:
        waiting = []
        for node in pending:
            index = _group_of_parent(node, by_id, group_of)
            if index is None:
                waiting.append(node)
                continue
            group_of[node.node_id] = index
            groups[index].members.append(node)
        if len(waiting) == len(pending):  # their parents aren't drawn: groups of their own
            for node in waiting:
                group_of[node.node_id] = len(groups)
                groups.append(_Group(members=[node]))
            break
        pending = waiting
    other = _Group()
    for node in nodes:
        if node.use_type == "Building":
            continue
        index = group_of.get(node.building_id) if node.building_id is not None else None
        (groups[index] if index is not None else other).members.append(node)
    if other.members:
        groups.append(other)
    return groups


def _root_order(roots: list[NodeIn], by_id: dict[tuple[str, int], NodeIn]) -> list[NodeIn]:
    """File order, with each building right after the building it needs."""
    keys = {root.key for root in roots}
    needs: dict[str, list[NodeIn]] = {}
    top: list[NodeIn] = []
    for root in roots:
        parent = _parent(root, by_id)
        if parent is not None and parent.key in keys:
            needs.setdefault(parent.key, []).append(root)
        else:
            top.append(root)
    ordered: list[NodeIn] = []
    seen: set[str] = set()

    def visit(node: NodeIn) -> None:
        if node.key in seen:
            return
        seen.add(node.key)
        ordered.append(node)
        for child in needs.get(node.key, []):
            visit(child)

    for root in top:
        visit(root)
    for root in roots:  # a loop of buildings needing each other: file order
        visit(root)
    return ordered


def _group_of_parent(
    node: NodeIn, by_id: dict[tuple[str, int], NodeIn], group_of: dict[int, int]
) -> int | None:
    parent = _parent(node, by_id)
    if parent is None:
        return None
    if parent.use_type == "Building":
        return group_of.get(parent.node_id)
    return group_of.get(parent.building_id) if parent.building_id is not None else None


def _place(group: _Group, node: NodeIn, by_id: dict[tuple[str, int], NodeIn]) -> None:
    row = _row(node)
    parent = _parent(node, by_id)
    placed = group.lanes.get(parent.key) if parent is not None else None
    if placed is not None and placed[1] < row:
        # Under its parent when the line down to it crosses no other node.
        below = range(placed[1] + 1, row + 1)
        blocked = any((placed[0], between) in group.taken for between in below)
        lane = group.first_free(below) if blocked else placed[0]
    else:
        lane = group.first_free(range(row, row + 1))
    group.put(node.key, lane, row)


def _row(node: NodeIn) -> int:
    age = node.age if 1 <= node.age <= 4 else 1
    return (age - 1) * 2 + (0 if node.use_type == "Building" else 1)


def _parent(node: NodeIn, by_id: dict[tuple[str, int], NodeIn]) -> NodeIn | None:
    if node.link_id is None or node.link_id < 0:
        return None
    for use_type in _use_types(node.link_type):
        found = by_id.get((use_type, node.link_id))
        if found is not None and found.key != node.key:
            return found
    return None


def _use_types(link_type: str | None) -> tuple[str, ...]:
    if link_type in _UNIT_TYPES:
        return ("Unit",)
    if link_type in _TECH_TYPES:
        return ("Tech",)
    if link_type in _BUILDING_TYPES:
        return ("Building",)
    return ("Unit", "Tech", "Building")

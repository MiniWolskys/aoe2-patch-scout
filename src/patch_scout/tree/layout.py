# SPDX-License-Identifier: GPL-3.0-or-later
"""Where each node of a civ's tech tree goes.

The game's tech tree data gives an order, ages and links, but no positions: the game computes
them. Here each age is a band of rows: its buildings, then its units and techs, then more rows
when a line goes on within the age (the Champion under the Two-Handed Swordsman, both Imperial),
as the game draws it. Buildings head groups of lanes, and a line stays in one lane when it can.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from itertools import chain, count
from typing import Final

AGES: Final = 4
_FIRST_ROWS: Final = 2  # every age has a building row and a row below
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
    """A node's group, its column across the whole tree, and its row.

    A building centred over its group sits between two columns, e.g. 1.5.
    """

    group: int
    column: float
    row: int


@dataclass(slots=True)
class Layout:
    """Every node's place, the lines from a node to the one it comes from, and the size."""

    places: dict[str, Place] = field(default_factory=dict)
    links: list[tuple[str, str]] = field(default_factory=list)
    columns: int = 0
    groups: int = 0
    age_rows: list[int] = field(default_factory=lambda: [_FIRST_ROWS] * AGES)

    @property
    def rows(self) -> int:
        """Rows in the whole tree."""
        return sum(self.age_rows)


# A cell inside a group: lane, age (1 to 4), depth in the age (0 is the building row).
type _Cell = tuple[int, int, int]


@dataclass(slots=True)
class _Group:
    members: list[NodeIn] = field(default_factory=list)
    taken: set[_Cell] = field(default_factory=set)
    cells: dict[str, _Cell] = field(default_factory=dict)

    def first_free(self, age: int, depth: int) -> int:
        lane = 0
        while (lane, age, depth) in self.taken:
            lane += 1
        return lane

    def clear_between(self, lane: int, start: tuple[int, int], end: tuple[int, int]) -> bool:
        """Whether a line down the lane, from just after `start` to `end`, crosses no node."""
        return not any(cell[0] == lane and start < (cell[1], cell[2]) <= end for cell in self.taken)

    def put(self, key: str, cell: _Cell) -> None:
        self.taken.add(cell)
        self.cells[key] = cell

    @property
    def width(self) -> int:
        return 1 + max((cell[0] for cell in self.taken), default=0)


def layout(nodes: Sequence[NodeIn]) -> Layout:
    """Each node's place, and the lines between nodes."""
    unique: dict[str, NodeIn] = {}
    for node in nodes:
        unique.setdefault(node.key, node)  # a node listed twice is drawn once
    by_id = {(node.use_type, node.node_id): node for node in unique.values()}
    groups = _groups(list(unique.values()), by_id)

    result = Layout()
    for group in groups:
        for member in group.members:
            _place(group, member, by_id)
    for group in groups:
        for _, age, depth in group.cells.values():
            result.age_rows[age - 1] = max(result.age_rows[age - 1], depth + 1)
    starts = [sum(result.age_rows[:age]) for age in range(AGES)]
    column = 0
    for index, group in enumerate(groups):
        centre = _centre(group)
        for key, (lane, age, depth) in group.cells.items():
            at = centre if key == group.members[0].key and centre is not None else lane
            result.places[key] = Place(index, column + at, starts[age - 1] + depth)
        column += group.width
    result.columns = column
    result.groups = len(groups)
    for node in unique.values():
        parent = _parent(node, by_id)
        if parent is not None:
            result.links.append((node.key, parent.key))
    for group in groups:
        result.links.extend(_from_building(group, unique, by_id))
    return result


def _centre(group: _Group) -> float | None:
    """Where the group's building goes: centred over its lanes, as in the game.

    Not when another building shares its row (the Mill and its Farm): it keeps its lane.
    """
    root = group.members[0] if group.members else None
    if root is None or root.use_type != "Building" or root.key not in group.cells:
        return None
    _, age, depth = group.cells[root.key]
    if any((a, d) == (age, depth) for k, (_, a, d) in group.cells.items() if k != root.key):
        return None
    return (group.width - 1) / 2


def _from_building(
    group: _Group, nodes: dict[str, NodeIn], by_id: dict[tuple[str, int], NodeIn]
) -> list[tuple[str, str]]:
    """The building's own lines: to the top of each lane, when that node starts a line.

    As in the game: Barracks to Militia, Spearman and Arson; not to a node below another one,
    such as the Hand Cannoneer under the Elite Skirmisher.
    """
    root = group.members[0] if group.members else None
    if root is None or root.use_type != "Building" or root.key not in group.cells:
        return []
    start = group.cells[root.key][1:]
    tops: dict[int, tuple[tuple[int, int], str]] = {}
    for key, (lane, age, depth) in group.cells.items():
        below = key != root.key and (age, depth) > start
        if below and (lane not in tops or (age, depth) < tops[lane][0]):
            tops[lane] = ((age, depth), key)
    links: list[tuple[str, str]] = []
    for _, key in sorted(tops.values()):
        node = nodes[key]
        if node.use_type != "Building" and _placement_parent(node, by_id) is None:
            links.append((key, root.key))
    return links


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
    age = node.age if 1 <= node.age <= AGES else 1
    depth = 0 if node.use_type == "Building" else 1
    parent = _placement_parent(node, by_id)
    placed = group.cells.get(parent.key) if parent is not None else None
    if placed is not None:
        lane, parent_age, parent_depth = placed
        if (parent_age, parent_depth) >= (age, depth):
            # A line that goes on within the age: below its parent, in the same lane.
            age, depth = parent_age, parent_depth + 1
            while (lane, age, depth) in group.taken:
                depth += 1
            group.put(node.key, (lane, age, depth))
            return
        # Down its parent's lane, else the first lane clear all the way: the line leaves the
        # parent just below it and comes down that lane, so it crosses no other node.
        start = (parent_age, parent_depth)
        lanes = chain([lane], (other for other in count() if other != lane))
        clear = next(other for other in lanes if group.clear_between(other, start, (age, depth)))
        group.put(node.key, (clear, age, depth))
        return
    group.put(node.key, (group.first_free(age, depth), age, depth))


def _parent(node: NodeIn, by_id: dict[tuple[str, int], NodeIn]) -> NodeIn | None:
    if node.link_id is None or node.link_id < 0:
        return None
    for use_type in _use_types(node.link_type):
        found = by_id.get((use_type, node.link_id))
        if found is not None and found.key != node.key:
            return found
    return None


def _placement_parent(node: NodeIn, by_id: dict[tuple[str, int], NodeIn]) -> NodeIn | None:
    """The node this one goes under. A link whose type names no such node is tried with any
    type: Squires links to Gambesons (875) but says BuildingTech, and the game still draws it
    under Gambesons. No line is drawn for such a link."""
    found = _parent(node, by_id)
    if found is not None or node.link_id is None or node.link_id < 0:
        return found
    for use_type in ("Unit", "Tech", "Building"):
        other = by_id.get((use_type, node.link_id))
        if other is not None and other.key != node.key:
            return other
    return None


def _use_types(link_type: str | None) -> tuple[str, ...]:
    if link_type in _UNIT_TYPES:
        return ("Unit",)
    if link_type in _TECH_TYPES:
        return ("Tech",)
    if link_type in _BUILDING_TYPES:
        return ("Building",)
    return ("Unit", "Tech", "Building")

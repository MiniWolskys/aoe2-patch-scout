# SPDX-License-Identifier: GPL-3.0-or-later
"""Where each node of a civ's tech tree goes, following the game's own tech tree screen.

The game's data gives an order, ages and links, but no positions: the game computes them. The
rules below were read off the game's screen (Bulgarians, 101.103.54800.0) and hold for any civ,
because they only use the data:

- **Ages** are bands of rows: a building row, a row for units and techs, and more rows when a
  line goes on within the age (the Champion under the Two-Handed Swordsman, both Imperial).
- **Top-level buildings** come in the data's order, each heading a block of columns.
- **A building that needs another and has units or techs of its own** is a block beside it: on
  its left when the data lists it before, on its right when after (Archery Range | Barracks |
  Stable, Siege Workshop | Blacksmith, Market | Mill | Farm).
- **A building with no units or techs** stays in the column of what it comes from: the towers
  from the Outpost, the Stone and Fortified Walls from the Gate, the Fish Trap under the Fishing
  Ship. Plain top-level buildings that follow each other share one column (the Palisade Wall,
  Palisade Gate and Gate; the House, a second Town Center and the Wonder).
- **Units and techs** go in the data's order: a line stays in its column, an upgrade within the
  same age goes below, and anything else takes the first free column of its building's block.
- **A building** is centred over its own columns, and its bar reaches the top of each column
  that starts a line (Barracks to Militia, Spearman and Arson).

A link names a node ID, and the same ID is often used by a unit, a tech and a building (Fletching
and the Fish Trap are both 199). The link's type in the data is unreliable, so a link resolves to
the node in the same building first: Fishing Lines links to 199 "Research" but means the Fish
Trap under the Fishing Ship, not the Blacksmith's Fletching.
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
_OTHER: Final = "#other"  # the block of nodes whose building isn't drawn


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
    """A node's top-level block, its column across the whole tree, and its row.

    A building centred over its columns sits between two of them, e.g. 1.5.
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


# A cell inside a block: lane, age (1 to 4), depth in the age (0 is the building row).
type _Cell = tuple[int, int, int]


@dataclass(slots=True)
class _Lanes:
    """The cells a block's own nodes take."""

    taken: set[_Cell] = field(default_factory=set)
    cells: dict[str, _Cell] = field(default_factory=dict)

    def first_free(self, age: int, depth: int) -> int:
        """The first lane free at that row with nothing below it: a node never goes above
        another one, whose line comes down that lane (Bloodlines over the Knight)."""
        lane = 0
        while any(c[0] == lane and (c[1], c[2]) >= (age, depth) for c in self.taken):
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


@dataclass(slots=True)
class _Block:
    """A building with its own columns, and the blocks of the buildings beside it."""

    head: str
    members: list[str] = field(default_factory=list)  # in the data's order, head first
    roots: list[str] = field(default_factory=list)  # plain buildings sharing the head's column
    left: list["_Block"] = field(default_factory=list)
    right: list["_Block"] = field(default_factory=list)
    lanes: _Lanes = field(default_factory=_Lanes)


class _Tree:
    """The nodes, how they link, and which block each belongs to."""

    def __init__(self, nodes: Sequence[NodeIn]) -> None:
        self.nodes: dict[str, NodeIn] = {}
        for node in nodes:
            self.nodes.setdefault(node.key, node)  # a node listed twice is drawn once
        self.order = {key: index for index, key in enumerate(self.nodes)}
        self.by_id: dict[int, list[NodeIn]] = {}
        for node in self.nodes.values():
            self.by_id.setdefault(node.node_id, []).append(node)
        # Buildings first: a unit's link may name a building whose own place depends on a unit.
        self.parent: dict[str, NodeIn | None] = {}
        for node in self.nodes.values():
            if node.use_type == "Building":
                self.parent[node.key] = self._resolve(node)
        for node in self.nodes.values():
            if node.use_type != "Building":
                self.parent[node.key] = self._resolve(node)
        self.children: dict[str, list[NodeIn]] = {}
        for node in self.nodes.values():
            found = self.parent[node.key]
            if found is not None:
                self.children.setdefault(found.key, []).append(node)
        self._blocks: dict[str, str] = {}

    def context(self, node: NodeIn) -> int | None:
        """The building a node is drawn with: its own, or for a building under a unit (the
        Fish Trap under the Fishing Ship), that unit's building."""
        if node.use_type != "Building":
            return node.building_id
        found = self.parent.get(node.key)
        if found is not None and found.use_type != "Building":
            return found.building_id
        return node.node_id

    def _resolve(self, node: NodeIn) -> NodeIn | None:
        if node.link_id is None or node.link_id < 0:
            return None
        candidates = [other for other in self.by_id.get(node.link_id, []) if other.key != node.key]
        if not candidates:
            return None
        typed = _use_types(node.link_type)
        own = node.building_id if node.use_type != "Building" else None

        def score(other: NodeIn) -> tuple[bool, bool]:
            same = own is not None and self.context(other) == own
            return same, other.use_type in typed

        return max(candidates, key=score)

    def has_content(self, building: NodeIn) -> bool:
        """Whether a building has units or techs of its own (then it gets its own columns)."""
        for node in self.nodes.values():
            if node.use_type == "Building":
                continue
            found = self.parent[node.key]
            if (found is not None and found.key == building.key) or (
                found is None and node.building_id == building.node_id
            ):
                return True
        return False

    def stays_in_column(self, building: NodeIn) -> bool:
        """A building that goes in the column of what it comes from, not a block of its own."""
        found = self.parent[building.key]
        if found is None:
            return False
        return found.use_type != "Building" or not self.has_content(building)

    def block_of(self, key: str) -> str:
        """The head of the block a node is drawn in."""
        if key in self._blocks:
            return self._blocks[key]
        self._blocks[key] = _OTHER  # a loop of links: drawn apart rather than forever
        node = self.nodes[key]
        found = self.parent[key]
        if node.use_type == "Building":
            block = self.block_of(found.key) if self.stays_in_column(node) and found else key
        elif found is not None:
            block = self.block_of(found.key)
        else:
            building = f"Building:{node.building_id}"
            block = self.block_of(building) if building in self.nodes else _OTHER
        self._blocks[key] = block
        return block


def layout(nodes: Sequence[NodeIn]) -> Layout:
    """Each node's place, and the lines between nodes."""
    tree = _Tree(nodes)
    tops = _blocks(tree)
    result = Layout()
    for top in tops:
        _place_block(tree, top)
    for top in tops:
        for block in _all(top):
            for _, age, depth in block.lanes.cells.values():
                result.age_rows[age - 1] = max(result.age_rows[age - 1], depth + 1)
    starts = [sum(result.age_rows[:age]) for age in range(AGES)]
    column = 0
    for index, top in enumerate(tops):
        width, positions = _compose(tree, top)
        for key, (x, age, depth) in positions.items():
            result.places[key] = Place(index, column + x, starts[age - 1] + depth)
        column += width
    result.columns = column
    result.groups = len(tops)
    for node in tree.nodes.values():
        found = tree.parent[node.key]
        if found is not None and found.key in result.places:
            result.links.append((node.key, found.key))
    for top in tops:
        for block in _all(top):
            result.links.extend(_from_building(tree, block))
    return result


def _blocks(tree: _Tree) -> list[_Block]:
    """The top-level blocks, in the data's order, with the blocks beside them filled in."""
    blocks: dict[str, _Block] = {}
    for key in tree.nodes:
        head = tree.block_of(key)
        if head not in blocks:
            blocks[head] = _Block(head=head)
        blocks[head].members.append(key)
    # In the buildings' order: the units come first in the data, and would put the blocks in the
    # order of each building's first unit.
    heads = sorted((head for head in blocks if head != _OTHER), key=lambda head: tree.order[head])
    beside_of: dict[str, _Block] = {}
    for head in heads:
        found = tree.parent[head]
        if (
            found is not None
            and found.use_type == "Building"
            and tree.block_of(found.key) in blocks
        ):
            beside = blocks[tree.block_of(found.key)]
            before = tree.order[head] < tree.order[beside.head]
            (beside.left if before else beside.right).append(blocks[head])
            beside_of[head] = beside
    tops: list[_Block] = []
    for head in heads:
        if head in beside_of:
            continue
        block = blocks[head]
        previous = tops[-1] if tops else None
        receives = (
            previous is not None
            and _plain_column(tree, previous)
            and all(key in (previous.head, *previous.roots) for key in previous.members)
        )
        if previous is not None and receives and _plain_column(tree, block):
            # Plain buildings that follow each other share one column, as in the game.
            previous.roots.append(head)
            previous.members.extend(block.members)
        else:
            tops.append(block)
    if _OTHER in blocks:
        tops.append(blocks[_OTHER])
    return tops


def _plain_column(tree: _Tree, block: _Block) -> bool:
    """A column of plain buildings only: no units, no techs, no buildings beside it.

    The block being merged may bring buildings under it (the Gate's Stone Wall); the one it
    joins may not have any (the Outpost's towers keep their own column)."""
    if block.head == _OTHER or block.left or block.right:
        return False
    if any(tree.nodes[key].use_type != "Building" for key in block.members):
        return False
    return not tree.has_content(tree.nodes[block.head])


def _all(block: _Block) -> list[_Block]:
    return [
        *(b for side in block.left for b in _all(side)),
        block,
        *(b for side in block.right for b in _all(side)),
    ]


def _place_block(tree: _Tree, block: _Block) -> None:
    for side in [*block.left, *block.right]:
        _place_block(tree, side)
    pending = sorted(block.members, key=lambda key: tree.order[key])
    # A node goes in after what it comes from, whatever the data's order.
    while pending:
        waiting: list[str] = []
        for key in pending:
            found = tree.parent[key]
            if (
                found is not None
                and tree.block_of(found.key) == block.head
                and found.key not in block.lanes.cells
                and found.key in pending
            ):
                waiting.append(key)
                continue
            _place(tree, block, tree.nodes[key])
        if len(waiting) == len(pending):  # a loop: place them anyway
            for key in waiting:
                _place(tree, block, tree.nodes[key])
            break
        pending = waiting


def _place(tree: _Tree, block: _Block, node: NodeIn) -> None:
    lanes = block.lanes
    age = node.age if 1 <= node.age <= AGES else 1
    found = tree.parent[node.key]
    if node.key == block.head or node.key in block.roots:
        depth = 0
        while (0, age, depth) in lanes.taken:  # plain buildings sharing one column
            depth += 1
        lanes.put(node.key, (0, age, depth))
        return
    under_unit = node.use_type == "Building" and found is not None and found.use_type != "Building"
    depth = 0 if node.use_type == "Building" and not under_unit else 1
    placed = lanes.cells.get(found.key) if found is not None else None
    if placed is not None:
        lane, parent_age, parent_depth = placed
        if (parent_age, parent_depth) >= (age, depth):
            # A line that goes on within the age: below what it comes from, in the same lane.
            age, depth = parent_age, parent_depth + 1
            while (lane, age, depth) in lanes.taken:
                depth += 1
            lanes.put(node.key, (lane, age, depth))
            return
        # Down its parent's lane, else the first lane clear all the way: the line leaves the
        # parent just below it and comes down that lane, so it crosses no other node.
        start = (parent_age, parent_depth)
        candidates = chain([lane], (other for other in count() if other != lane))
        clear = next(
            other for other in candidates if lanes.clear_between(other, start, (age, depth))
        )
        lanes.put(node.key, (clear, age, depth))
        return
    lanes.put(node.key, (lanes.first_free(age, depth), age, depth))


def _compose(tree: _Tree, block: _Block) -> tuple[int, dict[str, tuple[float, int, int]]]:
    """The block's width and each node's column in it: the blocks on the left, the building's
    own columns, then the blocks on the right."""
    positions: dict[str, tuple[float, int, int]] = {}
    x = 0
    for side in block.left:
        width, inner = _compose(tree, side)
        positions.update({key: (x + at, age, depth) for key, (at, age, depth) in inner.items()})
        x += width
    own = block.lanes
    for key, (lane, age, depth) in own.cells.items():
        positions[key] = (x + lane, age, depth)
    centre = _centre(block)
    if centre is not None:
        _, age, depth = own.cells[block.head]
        positions[block.head] = (x + centre, age, depth)
    x += own.width
    for side in block.right:
        width, inner = _compose(tree, side)
        positions.update({key: (x + at, age, depth) for key, (at, age, depth) in inner.items()})
        x += width
    return x, positions


def _centre(block: _Block) -> float | None:
    """Where the block's building goes: centred over its own columns, as in the game. Not in a
    column of plain buildings, and not when another node shares its row."""
    if block.head == _OTHER or block.roots or block.head not in block.lanes.cells:
        return None
    _, age, depth = block.lanes.cells[block.head]
    others = (cell for key, cell in block.lanes.cells.items() if key != block.head)
    if any((a, d) == (age, depth) for _, a, d in others):
        return None
    return (block.lanes.width - 1) / 2


def _from_building(tree: _Tree, block: _Block) -> list[tuple[str, str]]:
    """The building's own lines: to the top of each of its columns, when that node starts a line.

    As in the game: Barracks to Militia, Spearman and Arson; not to a node below another one,
    such as the Hand Cannoneer under the Elite Skirmisher.
    """
    if block.head == _OTHER or block.roots or block.head not in block.lanes.cells:
        return []
    start = block.lanes.cells[block.head][1:]
    tops: dict[int, tuple[tuple[int, int], str]] = {}
    for key, (lane, age, depth) in block.lanes.cells.items():
        below = key != block.head and (age, depth) > start
        if below and (lane not in tops or (age, depth) < tops[lane][0]):
            tops[lane] = ((age, depth), key)
    links: list[tuple[str, str]] = []
    for _, key in sorted(tops.values()):
        node = tree.nodes[key]
        if node.use_type != "Building" and tree.parent[key] is None:
            links.append((key, block.head))
    return links


def _use_types(link_type: str | None) -> tuple[str, ...]:
    if link_type in _UNIT_TYPES:
        return ("Unit",)
    if link_type in _TECH_TYPES:
        return ("Tech",)
    if link_type in _BUILDING_TYPES:
        return ("Building",)
    return ("Unit", "Tech", "Building")

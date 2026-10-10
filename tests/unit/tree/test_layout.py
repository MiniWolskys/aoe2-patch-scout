# SPDX-License-Identifier: GPL-3.0-or-later
"""The tech tree layout: age rows, building groups, lanes (spec: Layout)."""

from patch_scout.tree.layout import NodeIn, layout


def building(node_id: int, age: int, link: int | None = None, kind: str = "BuildingTech") -> NodeIn:
    link_type = "BuildingTech" if link is not None else None
    return NodeIn(f"Building:{node_id}", "Building", node_id, None, age, link, link_type, kind)


def node(
    node_id: int, at: int, age: int, link: int | None = None, use_type: str = "Unit"
) -> NodeIn:
    link_type = ("Unit" if use_type == "Unit" else "Research") if link is not None else None
    return NodeIn(f"{use_type}:{node_id}", use_type, node_id, at, age, link, link_type, "Unit")


def cells(tree_nodes: list[NodeIn]) -> dict[str, tuple[float, int]]:
    tree = layout(tree_nodes)
    return {key: (place.column, place.row) for key, place in tree.places.items()}


def test_a_line_of_upgrades_stays_in_its_lane_under_its_building() -> None:
    tree = layout(
        [building(87, 2), node(4, 87, 2), node(24, 87, 3, link=4), node(492, 87, 4, link=24)]
    )
    places = {key: (place.column, place.row) for key, place in tree.places.items()}
    assert places == {
        "Building:87": (0, 2),
        "Unit:4": (0, 3),
        "Unit:24": (0, 5),
        "Unit:492": (0, 7),
    }
    assert ("Unit:24", "Unit:4") in tree.links
    assert ("Unit:492", "Unit:24") in tree.links


def test_a_second_root_in_the_same_age_takes_the_next_lane() -> None:
    assert cells([building(87, 2), node(4, 87, 2), node(7, 87, 2)])["Unit:7"] == (1, 3)


def test_a_non_tech_building_linked_to_another_stacks_in_its_group() -> None:
    tree = layout([building(598, 1), building(79, 2, link=598, kind="BuildingNonTech")])
    assert tree.places["Building:79"].group == tree.places["Building:598"].group == 0
    assert tree.groups == 1
    assert ("Building:79", "Building:598") in tree.links


def test_a_building_that_needs_another_sits_beside_it_with_a_line() -> None:
    """The Stable needs the Barracks and has units: its own columns, right of the Barracks."""
    tree = layout([building(12, 1), node(74, 12, 1), building(101, 2, link=12), node(448, 101, 2)])
    assert ("Building:101", "Building:12") in tree.links
    assert tree.places["Building:101"].column > tree.places["Building:12"].column
    assert tree.groups == 1


def test_groups_follow_the_file_order_without_overlapping() -> None:
    tree = layout(
        [building(12, 1), node(74, 12, 1), node(75, 12, 1), building(87, 2), node(4, 87, 2)]
    )
    assert tree.places["Building:87"].column == 2
    assert tree.columns == 3
    taken = [(place.column, place.row) for place in tree.places.values()]
    assert len(taken) == len(set(taken))


def test_a_node_whose_building_is_missing_goes_to_a_last_group() -> None:
    tree = layout([building(12, 1), node(999, 4040, 3)])
    assert tree.places["Unit:999"].group == 1
    assert tree.groups == 2


def test_a_parent_placed_later_or_elsewhere_still_gets_a_line() -> None:
    tree = layout([building(12, 1), node(24, 12, 3, link=4), building(87, 2), node(4, 87, 2)])
    assert ("Unit:24", "Unit:4") in tree.links
    assert tree.places["Unit:24"].row == 5


def test_a_repeated_node_is_drawn_once() -> None:
    tree = layout([building(87, 2), node(4, 87, 2), node(4, 87, 2)])
    assert list(tree.places) == ["Building:87", "Unit:4"]


def test_an_age_outside_the_four_counts_as_the_dark_age() -> None:
    placed = cells([building(12, 0), node(74, 12, 9)])
    assert placed == {"Building:12": (0, 0), "Unit:74": (0, 1)}


def test_a_chain_moves_to_a_free_lane_when_its_own_is_blocked() -> None:
    # The Feudal unit takes lane 0, so the Dark Age tech's Castle Age upgrade can't run its line
    # straight down through it.
    tree = layout(
        [
            building(68, 1),
            node(500, 68, 1, use_type="Tech"),
            node(600, 68, 2),
            node(501, 68, 3, link=500, use_type="Tech"),
        ]
    )
    placed = {key: (place.column, place.row) for key, place in tree.places.items()}
    assert placed["Tech:500"][0] == placed["Unit:600"][0] == 0
    assert placed["Tech:501"][0] == 1
    assert len(set(placed.values())) == len(placed)


def test_an_upgrade_in_the_same_age_goes_below_in_the_same_column() -> None:
    """As the game draws the Champion under the Two-Handed Swordsman, both Imperial Age."""
    tree = layout([building(87, 2), node(4, 87, 2), node(5, 87, 2, link=4), node(6, 87, 3)])
    placed = {key: (place.column, place.row) for key, place in tree.places.items()}
    assert placed["Unit:5"] == (0, 4)
    assert tree.age_rows == [2, 3, 2, 2]
    assert placed["Unit:6"] == (0, 6)  # the Castle Age starts a row lower


def test_every_age_has_a_building_row_and_a_row_below() -> None:
    assert layout([building(12, 1)]).age_rows == [2, 2, 2, 2]
    assert layout([]).age_rows == [2, 2, 2, 2]


def test_an_empty_tree_lays_out_nothing() -> None:
    tree = layout([])
    assert (tree.places, tree.links, tree.columns, tree.groups) == ({}, [], 0, 0)


def test_a_plain_building_linked_to_a_unit_joins_that_units_group() -> None:
    """The Fish Trap comes from the Fishing Ship, so it sits with the Dock."""
    fish_trap = NodeIn("Building:199", "Building", 199, None, 2, 13, "Unit", "BuildingNonTech")
    tree = layout([fish_trap, building(12, 1), building(45, 1), node(13, 45, 1)])
    assert tree.places["Building:199"].group == tree.places["Building:45"].group
    assert tree.groups == 2


def test_a_building_is_centred_over_its_columns() -> None:
    tree = layout([building(87, 2), node(4, 87, 2), node(7, 87, 2), node(39, 87, 2)])
    assert tree.places["Building:87"].column == 1.0  # over lanes 0, 1 and 2


def test_a_building_sharing_its_row_stays_in_its_lane() -> None:
    """The Mill and its Farm are both in the Dark Age building row: no room to centre."""
    tree = layout(
        [building(68, 1), building(50, 1, link=68, kind="BuildingNonTech"), node(500, 68, 2)]
    )
    assert tree.places["Building:68"].column == 0


def test_the_building_links_to_the_top_of_each_column_that_starts_a_line() -> None:
    """As in the game: Archer, Skirmisher and Thumb Ring, not the Hand Cannoneer below."""
    tree = layout(
        [
            building(87, 2),
            node(4, 87, 2),
            node(24, 87, 3, link=4),
            node(7, 87, 2),
            node(6, 87, 3, link=7),
            node(5, 87, 4),  # Hand Cannoneer: under the Crossbowman, no line of its own
            node(437, 87, 3, use_type="Tech"),
        ]
    )
    to_building = {child for child, parent in tree.links if parent == "Building:87"}
    assert to_building == {"Unit:4", "Unit:7", "Tech:437"}


def test_a_link_with_the_wrong_type_still_places_under_its_parent() -> None:
    """Squires links to Gambesons (875) but says BuildingTech: the game stacks it below."""
    gambesons = NodeIn("Tech:875", "Tech", 875, 12, 3, None, "Research", "Research")
    squires = NodeIn("Tech:874", "Tech", 874, 12, 3, 875, "BuildingTech", "Research")
    tree = layout([building(12, 1), node(74, 12, 1), node(93, 12, 2), gambesons, squires])
    assert tree.places["Tech:874"].column == tree.places["Tech:875"].column
    assert tree.places["Tech:874"].row == tree.places["Tech:875"].row + 1


def _x(tree_nodes: list[NodeIn]) -> dict[str, float]:
    return {key: place.column for key, place in layout(tree_nodes).places.items()}


def test_a_building_listed_before_the_one_it_needs_sits_on_its_left() -> None:
    """The data lists the Archery Range, then the Barracks, then the Stable: the game draws
    Archery Range | Barracks | Stable."""
    x = _x(
        [
            building(87, 2, link=12),
            node(4, 87, 2),
            building(12, 1),
            node(74, 12, 1),
            building(101, 2, link=12),
            node(448, 101, 2),
        ]
    )
    assert x["Building:87"] < x["Building:12"] < x["Building:101"]


def test_a_link_means_the_node_drawn_with_the_same_building_first() -> None:
    """Fishing Lines links to 199 as Research, the Blacksmith's Fletching; the game means the
    Fish Trap, also 199, under the Fishing Ship in the Dock."""
    fish_trap = NodeIn("Building:199", "Building", 199, None, 2, 13, "Unit", "BuildingNonTech")
    fletching = NodeIn("Tech:199", "Tech", 199, 103, 2, None, None, "Research")
    lines = NodeIn("Tech:906", "Tech", 906, 45, 2, 199, "Research", "Research")
    tree = layout([fish_trap, building(103, 2), fletching, building(45, 1), node(13, 45, 1), lines])
    assert ("Tech:906", "Building:199") in tree.links
    assert ("Tech:906", "Tech:199") not in tree.links
    places = tree.places
    # The Fish Trap sits under the Fishing Ship, in the units row; Fishing Lines below it.
    assert places["Building:199"].column == places["Unit:13"].column
    assert places["Tech:906"].column == places["Unit:13"].column
    assert places["Unit:13"].row < places["Building:199"].row < places["Tech:906"].row


def test_plain_top_level_buildings_that_follow_each_other_share_a_column() -> None:
    plain = "BuildingNonTech"
    x = _x(
        [
            building(598, 1),
            building(79, 2, link=598, kind=plain),  # Watch Tower under the Outpost
            building(72, 1),  # Palisade Wall
            building(792, 1),  # Palisade Gate
            building(487, 2),  # Gate
            building(117, 2, link=487, kind=plain),  # Stone Wall
        ]
    )
    assert x["Building:598"] == x["Building:79"]
    assert x["Building:72"] == x["Building:792"] == x["Building:487"] == x["Building:117"]
    assert x["Building:72"] != x["Building:598"]


def test_the_mill_sits_between_the_market_and_the_farm() -> None:
    """The Market (listed before the Mill) on the left, the Farm (after) on the right, each with
    the techs that come from it: Horse Collar links to the Farm."""
    x = _x(
        [
            building(84, 2, link=68, kind="BuildingNonTech"),
            node(128, 84, 2),
            building(68, 1),
            building(50, 1, link=68, kind="BuildingNonTech"),
            NodeIn("Tech:14", "Tech", 14, 68, 2, 50, "BuildingTech", "Research"),
        ]
    )
    assert x["Building:84"] < x["Building:68"] < x["Building:50"]
    assert x["Tech:14"] == x["Building:50"]


def test_top_level_blocks_follow_the_buildings_order_not_the_units() -> None:
    """The units come first in the data; the blocks still follow the buildings' order."""
    x = _x([node(74, 12, 1), building(598, 1), building(12, 1), building(72, 1)])
    assert x["Building:598"] < x["Building:12"] < x["Building:72"]


def test_a_building_with_buildings_beside_it_keeps_its_own_column() -> None:
    """The Mill has no units, but the Market and Farm sit beside it: it isn't plain."""
    places = layout(
        [
            building(70, 1),  # House, plain
            building(84, 2, link=68, kind="BuildingNonTech"),
            node(128, 84, 2),
            building(68, 1),
            building(50, 1, link=68, kind="BuildingNonTech"),
            NodeIn("Tech:14", "Tech", 14, 68, 2, 50, "BuildingTech", "Research"),
        ]
    ).places
    assert places["Building:68"].group != places["Building:70"].group
    assert places["Building:84"].column < places["Building:68"].column


def test_a_node_never_goes_above_another_one_in_a_column() -> None:
    """Bloodlines (Feudal) can't sit over the Knight (Castle): the Stable's line comes down
    that column to the Knight."""
    places = layout(
        [
            building(101, 2),
            node(448, 101, 2),  # Scout Cavalry
            node(546, 101, 3, link=448),  # Light Cavalry
            node(38, 101, 3),  # Knight
            node(435, 101, 2, use_type="Tech"),  # Bloodlines
        ]
    ).places
    assert places["Tech:435"].column not in (places["Unit:38"].column, places["Unit:448"].column)

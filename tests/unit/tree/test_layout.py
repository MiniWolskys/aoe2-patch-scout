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


def cells(tree_nodes: list[NodeIn]) -> dict[str, tuple[int, int]]:
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


def test_a_building_that_needs_another_is_a_group_of_its_own_with_a_line() -> None:
    tree = layout([building(12, 1), building(87, 2, link=12)])
    assert tree.places["Building:87"].group == 1
    assert tree.groups == 2
    assert ("Building:87", "Building:12") in tree.links


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
    # The Market stacks under the Mill at lane 0 in the Feudal building row, so the Mill's
    # Dark Age tech can't run its upgrade line through it.
    tree = layout(
        [
            building(68, 1),
            node(500, 68, 1, use_type="Tech"),
            building(84, 2, link=68, kind="BuildingNonTech"),
            node(501, 68, 3, link=500, use_type="Tech"),
        ]
    )
    placed = {key: (place.column, place.row) for key, place in tree.places.items()}
    assert placed["Building:84"] == (0, 2)
    assert placed["Tech:500"] == (0, 1)
    assert placed["Tech:501"][1] == 5
    assert placed["Tech:501"][0] != 0
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


def test_a_building_follows_the_building_it_needs() -> None:
    """The file lists the Archery Range before the Barracks; the game draws it after."""
    tree = layout([building(87, 2, link=12), building(12, 1), building(103, 2)])
    order = sorted(tree.places, key=lambda key: tree.places[key].group)
    assert order == ["Building:12", "Building:87", "Building:103"]


def test_a_plain_building_linked_to_a_unit_joins_that_units_group() -> None:
    """The Fish Trap comes from the Fishing Ship, so it sits with the Dock."""
    fish_trap = NodeIn("Building:199", "Building", 199, None, 2, 13, "Unit", "BuildingNonTech")
    tree = layout([fish_trap, building(12, 1), building(45, 1), node(13, 45, 1)])
    assert tree.places["Building:199"].group == tree.places["Building:45"].group
    assert tree.groups == 2

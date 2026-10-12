# SPDX-License-Identifier: GPL-3.0-or-later
"""A civ added in the new build reads as a summary, not as every node "Added" (diff-rules.md)."""

from dataclasses import replace

import pytest
from support import pairs

from patch_scout.diff import compare
from patch_scout.diff.model import ChangeSet
from patch_scout.snapshot import JsonValue


@pytest.fixture(scope="module")
def change_set(tmp_path_factory: pytest.TempPathFactory) -> ChangeSet:
    pair = pairs.make(tmp_path_factory.mktemp("new-civ"))
    kept = [civ for civ in pair.old.civs if _name(civ) != "Ancients"]
    trees = {name: nodes for name, nodes in pair.old.tech_trees.items() if name != "Ancients"}
    offers = {name: data for name, data in pair.old.building_offers.items() if name != "Ancients"}
    old = replace(pair.old, civs=kept, tech_trees=trees, building_offers=offers)
    return compare(old, pair.new)


def _name(civ: JsonValue) -> JsonValue:
    return civ.get("internal_name") if isinstance(civ, dict) else None


def test_a_new_civ_gets_its_tech_tree_as_one_entry(change_set: ChangeSet) -> None:
    trees = [
        entry
        for entry in change_set.entries_for("Ancients")
        if entry.entity.kind == "civ" and entry.category == "civ_availability"
    ]

    assert len(trees) == 1
    fields = [change.field.key for change in trees[0].changes if change.field]
    assert set(fields) <= {"field.tech_tree_at", "field.tech_tree_buildings"}
    assert "Archer" in " ".join(change.new or "" for change in trees[0].changes)


def test_a_new_civ_does_not_list_each_building_offer(change_set: ChangeSet) -> None:
    offers = [
        change
        for change in change_set.for_civ("Ancients")
        if change.field is not None and change.field.key == "field.building_offer"
    ]
    assert offers == []


def test_a_new_civ_shows_its_bonus_text(change_set: ChangeSet) -> None:
    texts = [
        change
        for change in change_set.for_civ("Ancients")
        if change.field is not None and change.field.key == "field.civ_bonus_text"
    ]
    assert len(texts) == 1
    assert {word.kind for word in texts[0].words} == {"added"}


def _node(
    node_id: int, use_type: str, node_type: str, string_id: int, **extra: JsonValue
) -> JsonValue:
    node: dict[str, JsonValue] = {
        "node_id": node_id,
        "use_type": use_type,
        "node_type": node_type,
        "node_status": "ResearchedCompleted",
        "name_string_id": string_id,
        "building_id": 82,
    }
    return node | extra


def test_a_new_civ_lists_its_unique_and_regional_units_and_techs() -> None:
    # As the Danes on 101.103.54800.0: what the tree marks unique or regional, in tree order.
    from support.snapshots import make_snapshot

    danes: JsonValue = {"internal_name": "Danes", "name_string_id": 1, "bonus_string_id": 2}
    nodes = [
        _node(2711, "Unit", "UniqueUnit", 11),
        _node(2712, "Unit", "UniqueUnit", 12),
        _node(1484, "Tech", "UniqueTech", 13),
        _node(2703, "Unit", "RegionalUnit", 14),
        _node(1452, "Tech", "RegionalTech", 15),
        _node(4, "Unit", "Unit", 16),
        _node(2633, "Unit", "RegionalUnit", 17, node_status="NotAvailable"),
    ]
    names = {
        "1": "Danes",
        "2": "Infantry and Siege civilization",
        "11": "Jomsviking",
        "12": "Elite Jomsviking",
        "13": "Hamask",
        "14": "Varangian Guard",
        "15": "Cranequins",
        "16": "Archer",
        "17": "Catapult Galleon",
    }
    strings = {"tables": {"en": names}}
    old = make_snapshot(civs=[], tech_trees={}, strings=strings)
    new = make_snapshot(civs=[danes], tech_trees={"Danes": nodes}, strings=strings)

    found = {
        change.field.key: change.new
        for change in compare(old, new).for_civ("Danes")
        if change.category == "civilizations" and change.field is not None
    }

    assert found == {
        "field.unique_units": "Jomsviking, Elite Jomsviking",
        "field.unique_techs": "Hamask",
        "field.regional_units": "Varangian Guard",
        "field.regional_techs": "Cranequins",
    }

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

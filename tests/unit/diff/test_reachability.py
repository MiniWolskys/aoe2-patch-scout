# SPDX-License-Identifier: GPL-3.0-or-later
"""Which units a civ can reach (D-37, diff-rules.md)."""

from dataclasses import replace

import pytest
from support.snapshots import make_snapshot

from patch_scout.diff.reachability import UnitLookup, for_civ, seeds
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot


def unit(**fields: JsonValue) -> JsonObject:
    record: JsonObject = {"language_dll_name": 0}
    record.update(fields)
    return record


def stats(units: dict[str, JsonObject]) -> JsonObject:
    return {
        "units": {
            key: {"base": record, "base_civs": [0, 1], "overrides": {}, "absent_civs": []}
            for key, record in units.items()
        }
    }


@pytest.fixture
def snapshot() -> Snapshot:
    return make_snapshot(
        tech_trees={
            "Franks": [
                {"use_type": "Unit", "node_id": 38},
                {"use_type": "Tech", "node_id": 199},
                {"use_type": "Building", "node_id": 101},
            ]
        },
        building_offers={"Franks": {"buildings": [{"id": 12, "units": [74], "techs": [22]}]}},
        stats=stats(
            {
                "38": unit(building={"transform_unit": 39}),
                "39": unit(language_dll_name=5039),
                "74": unit(blood_unit_id=75),
                "75": unit(language_dll_name=5075),
                "101": unit(blood_unit_id=102),
                "102": unit(language_dll_name=0),  # a corpse: no name, so not a form
                "12": unit(type_50={"projectile_unit_id": 900}),
                "900": unit(language_dll_name=5900),
            }
        ),
        flags={"stats_available": True},
    )


def test_the_seeds_are_the_tech_tree_and_the_building_offers(snapshot: Snapshot) -> None:
    assert seeds(snapshot, "Franks") == {38, 101, 12, 74}


def test_a_tech_node_is_not_a_unit_seed(snapshot: Snapshot) -> None:
    assert 199 not in seeds(snapshot, "Franks")


def test_a_civ_with_no_tech_tree_reaches_nothing(snapshot: Snapshot) -> None:
    assert seeds(snapshot, "Gaia") == set()


def test_a_transform_form_is_reachable(snapshot: Snapshot) -> None:
    lookup = UnitLookup(snapshot)
    reach = for_civ(snapshot, snapshot, "Franks", (0, 0), (lookup, lookup))
    assert reach.includes(39)


def test_a_named_dismount_form_is_reachable(snapshot: Snapshot) -> None:
    lookup = UnitLookup(snapshot)
    reach = for_civ(snapshot, snapshot, "Franks", (0, 0), (lookup, lookup))
    assert reach.includes(75)


def test_a_corpse_is_not_reachable(snapshot: Snapshot) -> None:
    lookup = UnitLookup(snapshot)
    reach = for_civ(snapshot, snapshot, "Franks", (0, 0), (lookup, lookup))
    assert not reach.includes(102)


def test_a_projectile_is_not_a_unit_but_is_linked_to_its_shooter(snapshot: Snapshot) -> None:
    lookup = UnitLookup(snapshot)
    reach = for_civ(snapshot, snapshot, "Franks", (0, 0), (lookup, lookup))
    assert not reach.includes(900)
    assert reach.projectiles == frozenset({900})
    assert reach.fired_by[900] == (12,)


def test_reachability_uses_both_snapshots(snapshot: Snapshot) -> None:
    older = replace(snapshot, tech_trees={"Franks": []}, building_offers={})
    lookup = UnitLookup(snapshot)
    reach = for_civ(older, snapshot, "Franks", (0, 0), (UnitLookup(older), lookup))
    assert reach.includes(38)


def test_a_snapshot_without_stats_still_gives_its_seeds(snapshot: Snapshot) -> None:
    without = replace(snapshot, stats=None)
    lookup = UnitLookup(without)
    reach = for_civ(without, without, "Franks", (0, 0), (lookup, lookup))
    assert reach.units == frozenset({12, 38, 74, 101})


def test_the_unit_lookup_lists_what_the_snapshot_stores(snapshot: Snapshot) -> None:
    lookup = UnitLookup(snapshot)
    assert lookup.unit_ids == [12, 38, 39, 74, 75, 101, 102, 900]
    assert lookup.record(38, 0) is not None
    assert lookup.record(4242, 0) is None
    assert lookup.any_record(38) is not None


def test_a_civ_missing_from_one_build_is_read_from_the_other(snapshot: Snapshot) -> None:
    """A civ added in the new build has no slot in the old one, so that side is skipped."""
    lookup = UnitLookup(snapshot)
    reach = for_civ(snapshot, snapshot, "Franks", (None, 0), (lookup, lookup))
    assert reach.includes(39)

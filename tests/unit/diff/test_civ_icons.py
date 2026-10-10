# SPDX-License-Identifier: GPL-3.0-or-later
"""Icons the comparison hands the page: civ crests and stat icons (ui.md)."""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

CREST: JsonObject = {"hash": "c" * 64, "category": "emblems"}
EMBLEM: JsonObject = {"hash": "e" * 64, "category": "emblems"}
HP_ICON: JsonObject = {"hash": "a" * 64, "category": "stat_icons"}


def _civ(name: str, index: int, **icons: JsonValue) -> JsonValue:
    return {
        "internal_name": name,
        "index": index,
        "name_string_id": None,
        "era": "base",
        "bonus_string_id": None,
        "unique_unit_string_ids": [],
        **icons,
    }


def _build(hit_points: int, **icons: JsonValue) -> Snapshot:
    tree = [{"use_type": "Unit", "node_id": 4, "node_status": "ResearchedCompleted"}]
    unit = {
        "base": {"hit_points": 30, "language_dll_name": 5004},
        "base_civs": [0, 1, 2],
        "overrides": {"1": {"hit_points": hit_points}},
        "absent_civs": [],
    }
    return make_snapshot(
        civs=[_civ("Gaia", 0), _civ("Alpha", 1, **icons), _civ("Beta", 2)],
        tech_trees={"Alpha": tree, "Beta": tree},
        strings={"tables": {"en": {"5004": "Archer"}}},
        flags={"stats_available": True},
        stat_icons={"hp": HP_ICON},
        stats={"units": {"4": unit}, "techs": {}, "effects": {}, "civ_dat": []},
    )


def _alpha_icon(**icons: JsonValue) -> JsonValue:
    change_set = compare(_build(30, **icons), _build(35, **icons))
    [alpha] = [civ for civ in change_set.civs if civ.internal_name == "Alpha"]
    return alpha.icon


def test_the_civ_list_prefers_the_crest() -> None:
    assert _alpha_icon(crest_icon=CREST, emblem_icon=EMBLEM) == CREST


def test_an_emblem_is_marked_as_a_silhouette_when_there_is_no_crest() -> None:
    assert _alpha_icon(emblem_icon=EMBLEM) == EMBLEM | {"kind": "silhouette"}


def test_the_change_set_carries_the_stat_icons() -> None:
    change_set = compare(_build(30), _build(35))
    assert change_set.stat_icons == {"hp": HP_ICON}
    assert change_set.to_json()["stat_icons"] == {"hp": HP_ICON}

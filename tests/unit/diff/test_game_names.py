# SPDX-License-Identifier: GPL-3.0-or-later
"""Classes, buildings and techs named in unit and tech changes (game-files.md §11)."""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.model import Change, ChangeSet
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

SWORDSMAN = 77
RANGE = 87
FEUDAL, CASTLE = 101, 102

CONSTANTS: JsonValue = {
    "Damage Classes": [["cDamageClassPierce", 3], ["cDamageClassShockInfantry", 29]],
}


def _civ(name: str, index: int) -> JsonValue:
    return {
        "internal_name": name,
        "index": index,
        "name_string_id": None,
        "era": "base",
        "emblem_icon": None,
        "bonus_string_id": None,
        "unique_unit_string_ids": [],
    }


def _unit(base: JsonObject) -> JsonValue:
    return {"base": base, "base_civs": [0, 1], "overrides": {}, "absent_civs": []}


def _tech(dll: int, required: list[JsonValue]) -> JsonValue:
    return {
        "name": "internal",
        "civ": -1,
        "language_dll_name": dll,
        "effect_id": -1,
        "required_tech_count": 1,
        "required_techs": required,
        "research_locations": [],
        "resource_costs": [],
        "repeatable": 0,
        "type": 0,
    }


def _build(
    *, shock: int, pierce: int, train_time: int, required: list[JsonValue], scripts: bool = True
) -> Snapshot:
    swordsman: JsonObject = {
        "hit_points": 60,
        "language_dll_name": 5077,
        "type_50": {"attacks": [{"class_": 29, "amount": shock}, {"class_": 4, "amount": 9}]},
        "creatable": {
            "train_locations": [{"unit_id": RANGE, "train_time": train_time, "button_id": 1}],
            "resource_costs": [],
        },
    }
    building: JsonObject = {"hit_points": 1500, "language_dll_name": 5087}
    shooter: JsonObject = {"hit_points": 30, "language_dll_name": 5004}
    shooter["type_50"] = {"armours": [{"class_": 3, "amount": pierce}]}
    tree = [
        {"use_type": "Unit", "node_id": SWORDSMAN, "node_status": "ResearchedCompleted"},
        {"use_type": "Unit", "node_id": 4, "node_status": "ResearchedCompleted"},
        {"use_type": "Building", "node_id": RANGE, "node_status": "ResearchedCompleted"},
    ]
    return make_snapshot(
        civs=[_civ("Gaia", 0), _civ("Alpha", 1)],
        tech_trees={"Alpha": tree},
        strings={
            "tables": {
                "en": {
                    "5077": "Long Swordsman",
                    "5087": "Archery Range",
                    "5004": "Archer",
                    "7101": "Feudal Age",
                    "7102": "Castle Age",
                    "7200": "Crossbowman",
                }
            }
        },
        flags={"stats_available": True},
        scripts={"constants": CONSTANTS} if scripts else {},
        stats={
            "units": {
                str(SWORDSMAN): _unit(swordsman),
                str(RANGE): _unit(building),
                "4": _unit(shooter),
            },
            "techs": {
                str(FEUDAL): _tech(7101, []),
                str(CASTLE): _tech(7102, []),
                "200": _tech(7200, required),
            },
            "effects": {},
            "civ_dat": [],
        },
    )


def _compare(**changes: object) -> ChangeSet:
    old: dict[str, object] = {"shock": 6, "pierce": 0, "train_time": 21, "required": [FEUDAL, -1]}
    new = old | changes
    return compare(_build(**old), _build(**new))  # type: ignore[arg-type]  # test values


def _field_args(change: Change) -> dict[str, JsonValue]:
    assert change.field is not None
    return dict(change.field.args)


def test_an_attack_class_is_named_from_the_xs_constants() -> None:
    [change] = [c for c in _compare(shock=8).changes if c.entity.name == "Long Swordsman"]
    assert _field_args(change) == {"class": "Shock Infantry"}
    assert (change.old, change.new) == ("6", "8")


def test_an_armour_class_is_named_too() -> None:
    [change] = [c for c in _compare(pierce=1).changes if c.entity.name == "Archer"]
    assert _field_args(change) == {"class": "Pierce"}


def test_a_class_the_constants_dont_name_stays_an_id() -> None:
    old = _build(shock=6, pierce=0, train_time=21, required=[FEUDAL], scripts=False)
    new = _build(shock=8, pierce=0, train_time=21, required=[FEUDAL], scripts=False)
    [change] = [c for c in compare(old, new).changes if c.entity.name == "Long Swordsman"]
    assert _field_args(change) == {"class": "#29"}


def test_a_train_location_is_named_after_its_building() -> None:
    [change] = [c for c in _compare(train_time=18).changes if c.entity.name == "Long Swordsman"]
    assert _field_args(change) == {"location": "Archery Range"}


def test_required_techs_are_named_and_empty_slots_left_out() -> None:
    changes = _compare(required=[CASTLE, -1]).changes
    [change] = [c for c in changes if c.entity.name == "Crossbowman"]
    assert (change.old, change.new) == ("Feudal Age", "Castle Age")


def test_a_tech_that_requires_nothing_lists_no_techs() -> None:
    old = _build(shock=6, pierce=0, train_time=21, required=[FEUDAL, -1])
    new = _build(shock=6, pierce=0, train_time=21, required=[0, 0])
    assert new.stats is not None
    techs = new.stats["techs"]
    assert isinstance(techs, dict) and isinstance(techs["200"], dict)
    techs["200"]["required_tech_count"] = 0
    changes = [c for c in compare(old, new).changes if c.entity.name == "Crossbowman"]
    required = [c for c in changes if c.field is not None and c.field.key == "field.required_techs"]
    assert [(c.old, c.new) for c in required] == [("Feudal Age", "")]


def test_a_unit_without_a_name_is_still_marked_unnamed() -> None:
    old = _build(shock=6, pierce=0, train_time=21, required=[FEUDAL])
    new = _build(shock=6, pierce=0, train_time=21, required=[FEUDAL])
    for snapshot, hit_points in ((old, 30), (new, 35)):
        assert snapshot.stats is not None
        units = snapshot.stats["units"]
        assert isinstance(units, dict) and isinstance(units["4"], dict)
        base = units["4"]["base"]
        assert isinstance(base, dict)
        base["language_dll_name"] = 0
        base["hit_points"] = hit_points
    [change] = [c for c in compare(old, new).changes if c.entity.id == "4"]
    assert (change.entity.name, change.entity.named) == ("#4", False)


def test_a_change_only_in_placeholder_slots_is_not_reported() -> None:
    old = _build(shock=6, pierce=0, train_time=21, required=[-1, -1])
    new = _build(shock=6, pierce=0, train_time=21, required=[0, -1])
    for snapshot in (old, new):
        assert snapshot.stats is not None
        techs = snapshot.stats["techs"]
        assert isinstance(techs, dict) and isinstance(techs["200"], dict)
        techs["200"]["required_tech_count"] = 0
    assert [c for c in compare(old, new).changes if c.entity.name == "Crossbowman"] == []

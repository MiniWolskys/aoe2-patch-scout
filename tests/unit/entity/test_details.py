# SPDX-License-Identifier: GPL-3.0-or-later
"""A unit, building or tech in detail, with what affects it for one civ (D-49)."""

import copy
from dataclasses import replace
from typing import Any

from support.snapshots import make_snapshot

from patch_scout.diff.effects import TIMES
from patch_scout.entity.details import build
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

BREAK = r"\n"  # the game's line break in string files
# IDs as on the live build: unit 74 is the Militia and tech 74 Scale Mail Armor.
MILITIA, MAN_AT_ARMS, TOWN_CENTER, BARRACKS = 74, 75, 109, 12
SCALE_MAIL, FORGING, CHAIN_MAIL, MAA_UPGRADE = 74, 67, 76, 222
FREE_UPGRADES, BAGAINS, HIDDEN, SCRIPTED, FEUDAL = 693, 686, 861, 699, 101
TREE_EFFECT, TEAM_EFFECT = 900, 901
INFANTRY = 6

CONSTANTS: JsonValue = {
    "Effect Constants": [
        ["cSetAttribute", 0],
        ["cModResource", 1],
        ["cEnableObject", 2],
        ["cUpgradeUnit", 3],
        ["cAddAttribute", 4],
        ["cMulAttribute", 5],
        ["cAddTechCost", 101],
        ["cDisableTech", 102],
        ["cModTechTime", 103],
        ["cSpawnUnit", 7],
    ],
    "Tech Effect Constants": [
        ["cHitpoints", 0],
        ["cLineOfSight", 1],
        ["cArmor", 8],
        ["cAttack", 9],
        ["cFoodCost", 103],
    ],
    "Damage Classes": [["cDamageClassPierce", 3], ["cDamageClassMelee", 4]],
    "Object Classes": [["cInfantryClass", 906], ["cBuildingClass", 903]],
    "Attributes": [
        ["cAttributeFood", 0],
        ["cAttributeWood", 1],
        ["cAttributeStone", 2],
        ["cAttributeGold", 3],
        ["cAttributeEffectFunctionNumber", 33],
    ],
}


def _command(type_: int, a: int = -1, b: int = -1, c: int = -1, d: float = 0.0) -> JsonObject:
    return {"type": type_, "a": a, "b": b, "c": c, "d": d}


def _civ(name: str, index: int) -> JsonObject:
    return {"internal_name": name, "index": index, "name_string_id": None, "era": "base"}


def _node(use_type: str, node_id: int, age: int, **extra: Any) -> JsonObject:
    node: JsonObject = {
        "use_type": use_type,
        "node_id": node_id,
        "age_id": age,
        "node_status": "ResearchedCompleted",
        "building_id": BARRACKS,
        "node_type": {"Unit": "Unit", "Tech": "Research", "Building": "BuildingTech"}[use_type],
        "name_string_id": None,
        "help_string_id": None,
        "trigger_tech_id": None,
        "icon": {"hash": f"{use_type}{node_id}".ljust(64, "0")},
    }
    node.update(extra)
    return node


def _tech(name: str, effect: int, *, civ: int = -1, cost: int = 100, **extra: Any) -> JsonObject:
    tech: JsonObject = {
        "name": name,
        "civ": civ,
        "effect_id": effect,
        "language_dll_name": None,
        "required_techs": [-1] * 6,
        "required_tech_count": 0,
        "resource_costs": [
            {"amount": cost, "flag": 1, "type": 0},
            {"amount": 0, "flag": 0, "type": -1},
        ],
        "research_locations": [{"location_id": BARRACKS, "research_time": 40}],
    }
    tech.update(extra)
    return tech


def _militia(hit_points: int) -> JsonObject:
    return {
        "class_": INFANTRY,
        "hit_points": hit_points,
        "line_of_sight": 4,
        "speed": 0.9,
        "garrison_capacity": 0,
        "language_dll_name": 5074,
        "type_50": {
            "attacks": [{"amount": 4, "class_": 4}, {"amount": 0, "class_": 29}],
            "armours": [
                {"amount": 0, "class_": 4},
                {"amount": 1, "class_": 3},
                {"amount": 2, "class_": 31},
            ],
            "displayed_attack": 4,
            "displayed_melee_armour": 0,
            "max_range": 0.0,
            "min_range": 0.0,
            "reload_time": 2.0,
            "accuracy_percent": 100,
            "blast_width": 0.0,
        },
        "creatable": {
            "displayed_pierce_armour": 1,
            "resource_costs": [
                {"amount": 50, "flag": 1, "type": 0},
                {"amount": 20, "flag": 1, "type": 3},
                {"amount": 1, "flag": 0, "type": 4},
            ],
            "train_locations": [{"unit_id": BARRACKS, "train_time": 21}],
            "conversion_chance_mod": 0.0,
            "max_charge": 0.0,
        },
    }


def _unit(base: JsonObject, *, overrides: JsonObject | None = None) -> JsonValue:
    return {"base": base, "base_civs": [0], "overrides": overrides or {}, "absent_civs": []}


def _snapshot(
    *,
    new: bool,
    civs: tuple[str, ...] = ("Alpha", "Beta"),
    stats: bool = True,
    with_man_at_arms: bool = True,
) -> Snapshot:
    """Alpha has the bonuses; Beta has none and can't research Chain Mail."""
    alpha_tree = [
        _node("Building", BARRACKS, 1, node_type="BuildingTech", building_id=None),
        _node("Unit", MILITIA, 1, name_string_id=5074, help_string_id=105074),
        _node("Tech", SCALE_MAIL, 2, name_string_id=7074),
        _node("Tech", FORGING, 2, name_string_id=7067),
        _node("Tech", CHAIN_MAIL, 3, name_string_id=7076),
        _node("Tech", BAGAINS, 4, node_type="UniqueTech", name_string_id=7686),
    ]
    if with_man_at_arms:
        alpha_tree.append(
            _node(
                "Unit",
                MAN_AT_ARMS,
                2,
                node_type="UnitUpgrade",
                trigger_tech_id=MAA_UPGRADE,
                link_id=MILITIA,
                name_string_id=5075,
            )
        )
    beta_tree = [
        dict(node, node_status="NotAvailable") if node["node_id"] == CHAIN_MAIL else node
        for node in alpha_tree
        if node["node_id"] != BAGAINS or node["use_type"] != "Tech"
    ]
    trees = {"Alpha": alpha_tree, "Beta": beta_tree}
    indices = {name: index + 1 for index, name in enumerate(civs)}
    alpha = indices["Alpha"]
    militia = _militia(45 if new else 40)
    techs: JsonObject = {
        str(SCALE_MAIL): _tech("Scale Mail Armor", SCALE_MAIL, language_dll_name=7074),
        str(FORGING): _tech("Forging", FORGING, language_dll_name=7067),
        str(CHAIN_MAIL): _tech("Chain Mail Armor", CHAIN_MAIL, language_dll_name=7076),
        str(MAA_UPGRADE): _tech("Man-at-Arms", MAA_UPGRADE, language_dll_name=7222),
        str(FREE_UPGRADES): _tech(
            "C-Bonus, Free Militia upgrades",
            FREE_UPGRADES,
            civ=alpha,
            required_techs=[FEUDAL, -1, -1, -1, -1, -1],
            required_tech_count=1,
        ),
        str(BAGAINS): _tech("Khmer UT", BAGAINS, civ=alpha, language_dll_name=7686),
        str(HIDDEN): _tech("Kshatriyas + Supplies", HIDDEN),
        str(SCRIPTED): _tech("C-Bonus, Kasbah", SCRIPTED, civ=alpha),
        str(FEUDAL): _tech("Feudal Age", FEUDAL, language_dll_name=7101),
    }
    effects: JsonObject = {
        str(TREE_EFFECT): {
            "name": "Alpha Tech Tree",
            # Halves Scale Mail's food cost: tech 74, not the Militia (unit 74). Then infantry
            # +10% hit points, and a tech disabled.
            "commands": [
                _command(101, a=SCALE_MAIL, b=0, c=2, d=0.5),
                _command(5, a=-1, b=INFANTRY, c=0, d=1.1),
                _command(102, d=99.0),
            ],
        },
        str(TEAM_EFFECT): {
            "name": "Alpha Team Bonus",
            "commands": [_command(4, a=-1, b=INFANTRY, c=1, d=1.0)],
        },
        str(SCALE_MAIL): {
            "name": "Scale Mail Armor",
            "commands": [
                _command(4, a=-1, b=INFANTRY, c=8, d=4 * 256 + 1),
                _command(4, a=-1, b=INFANTRY, c=8, d=3 * 256 + 1),
            ],
        },
        str(FORGING): {
            "name": "Forging",
            "commands": [
                _command(4, a=-1, b=INFANTRY, c=9, d=(4 * 256 + 2) if new else 4 * 256 + 1)
            ],
        },
        str(CHAIN_MAIL): {
            "name": "Chain Mail Armor",
            "commands": [_command(4, a=-1, b=INFANTRY, c=8, d=4 * 256 + 1)],
        },
        str(MAA_UPGRADE): {
            "name": "Man-at-Arms",
            "commands": [_command(3, a=MILITIA, b=MAN_AT_ARMS)],
        },
        str(FREE_UPGRADES): {
            "name": "C-Bonus, Free Militia upgrades",
            "commands": [
                _command(101, a=MAA_UPGRADE, b=0, c=0, d=0.0),
                _command(103, a=MAA_UPGRADE, b=-1, c=0, d=0.0),
            ],
        },
        str(BAGAINS): {
            "name": "Bagains",
            # Attribute 77 has no name in the constants: no sentence fits it.
            "commands": [
                _command(4, a=MILITIA, c=8, d=4 * 256 + 5),
                _command(4, a=MILITIA, c=77, d=1.0),
            ],
        },
        str(HIDDEN): {"name": "Supplies", "commands": [_command(0, a=MILITIA, c=103, d=30.0)]},
        str(SCRIPTED): {"name": "Kasbah", "commands": [_command(1, a=33, b=0, d=52.0)]},
        str(FEUDAL): {"name": "Feudal Age", "commands": []},
    }
    civ_dat: list[JsonValue] = [{"tech_tree_effect_id": -1, "team_bonus_effect_id": -1}] * (
        len(civs) + 1
    )
    civ_dat = list(civ_dat)
    civ_dat[alpha] = {"tech_tree_effect_id": TREE_EFFECT, "team_bonus_effect_id": TEAM_EFFECT}
    town_center: JsonObject = {
        "type": 80,
        "class_": 3,
        "hit_points": 2400,
        "line_of_sight": 8,
        "garrison_capacity": 15,
        "language_dll_name": 5109,
        "building": {"garrison_heal_rate": 0.0},
        "creatable": {
            "resource_costs": [{"amount": 100, "flag": 1, "type": 2}],
            "train_locations": [{"unit_id": MILITIA, "train_time": 150}],
        },
    }
    units: JsonObject = {str(MILITIA): _unit(militia), str(TOWN_CENTER): _unit(town_center)}
    if with_man_at_arms:
        units[str(MAN_AT_ARMS)] = _unit(dict(_militia(45), language_dll_name=5075))
    return make_snapshot(
        meta={
            "capture_id": "new" if new else "old",
            "captured_at": "2026-09-16T10:00:00Z",
            "game_build": "2.0" if new else "1.0",
        },
        civs=[_civ("Gaia", 0)] + [_civ(name, indices[name]) for name in civs],
        tech_trees={name: trees[name] for name in civs if name in trees},
        strings={
            "tables": {
                "en": {
                    "5074": "Militia",
                    "5075": "Man-at-Arms",
                    "5109": "Town Center",
                    "7074": "Scale Mail Armor",
                    "7067": "Forging",
                    "7076": "Chain Mail Armor",
                    "7222": "Man-at-Arms",
                    "7686": "Bagains",
                    "7101": "Feudal Age",
                    "26074": "Create <b>Militia<b> (<cost>)"
                    + BREAK
                    + "All-purpose Infantry."
                    + BREAK
                    + "<GREY><i>Upgrades: attack (Blacksmith).<i><DEFAULT>"
                    + BREAK
                    + "<hp> <attack> <armor>",
                }
            }
        },
        scripts={"constants": CONSTANTS, "effects": "// 52 - Effect of Kasbah for Alpha\n"},
        flags={"stats_available": stats},
        stats=(
            {"units": units, "techs": techs, "effects": effects, "civ_dat": civ_dat}
            if stats
            else None
        ),
    )


OLD = _snapshot(new=False)
NEW = _snapshot(new=True)


def _details(
    kind: str = "unit",
    entity_id: int = MILITIA,
    civ: str | None = "Alpha",
    old: Snapshot = OLD,
    new: Snapshot = NEW,
) -> dict[str, Any]:
    view: Any = build(old, new, kind, entity_id, civ)
    assert view is not None
    return dict(view)


def _section(view: dict[str, Any], key: str) -> list[dict[str, Any]]:
    for section in view["sections"]:
        if section["key"] == key:
            return list(section["rows"])
    raise AssertionError(f"no section {key}: {[s['key'] for s in view['sections']]}")


def _row(rows: list[dict[str, Any]], key: str, **args: Any) -> dict[str, Any]:
    for row in rows:
        field = row["field"]
        if field["key"] == key and all(field["args"].get(k) == v for k, v in args.items()):
            return row
    raise AssertionError(f"no row {key} {args}: {[r['field'] for r in rows]}")


def _group(view: dict[str, Any], key: str) -> list[dict[str, Any]]:
    for group in view["groups"]:
        if group["key"] == key:
            return list(group["sources"])
    return []


def _source_names(view: dict[str, Any], key: str) -> list[Any]:
    return [source["name"] for source in _group(view, key)]


def _sentences(source: dict[str, Any]) -> list[tuple[Any, Any, Any, Any]]:
    return [(r["field"]["key"], r["old"], r["new"], r["state"]) for r in source["rows"]]


# --- identity -------------------------------------------------------------------------------


def test_the_header_names_the_unit_with_its_icon_age_and_availability() -> None:
    view = _details()
    assert (view["kind"], view["id"], view["name"]) == ("unit", MILITIA, "Militia")
    assert view["icon"]["hash"].startswith("Unit74")
    assert view["age"] == 1
    assert view["civ"] == "Alpha"
    assert view["presence"] == "both"
    assert view["available"] == {"old": True, "new": True}
    assert view["stats_missing"] == {"old": False, "new": False}


def test_the_description_is_the_help_text_without_its_title_and_stat_lines() -> None:
    lines = _details()["description"]
    texts = ["".join(run["text"] for run in line) for line in lines]
    assert texts == ["All-purpose Infantry.", "Upgrades: attack (Blacksmith)."]
    assert lines[1][0]["grey"] is True


def test_an_unknown_entity_has_no_details() -> None:
    assert build(OLD, NEW, "unit", 4321, "Alpha") is None
    assert build(OLD, NEW, "tech", 4321, None) is None
    assert build(OLD, NEW, "effect", MILITIA, None) is None


def test_a_unit_and_a_tech_with_the_same_number_are_told_apart() -> None:
    assert _details("unit", 74)["name"] == "Militia"
    assert _details("tech", 74)["name"] == "Scale Mail Armor"


# --- stats ----------------------------------------------------------------------------------


def test_a_changed_stat_reads_old_and_new_and_the_others_one_value() -> None:
    stats = _section(_details(), "stats")
    assert _row(stats, "field.hit_points") | {} == {
        "field": {"key": "field.hit_points", "args": {}},
        "stat_icon": "hp",
        "old": "40",
        "new": "45",
        "state": "changed",
    }
    sight = _row(stats, "field.line_of_sight")
    assert (sight["old"], sight["new"], sight["state"]) == ("4", "4", "same")


def _classes_and_icons(stats: list[dict[str, Any]]) -> list[tuple[str, Any, Any]]:
    return [
        (r["field"]["key"], r["field"]["args"].get("class"), r["stat_icon"])
        for r in stats
        if r["field"]["key"].startswith(("field.attacks", "field.armours", "field.displayed"))
    ]


def test_attack_and_armour_classes_show_once_with_melee_and_pierce_first() -> None:
    """An attack class with no amount is left out; every armour class is shown, even at 0."""
    stats = _section(_details(), "stats")
    assert _classes_and_icons(stats) == [
        ("field.attacks_basic", "Melee", "melee_attack"),
        ("field.armours_basic", "Melee", "melee_armor"),
        ("field.armours_basic", "Pierce", "pierce_armor"),
        ("field.armours", "#31", None),
    ]
    assert _row(stats, "field.armours_basic", **{"class": "Melee"})["new"] == "0"


def test_a_displayed_value_that_differs_from_its_class_is_shown() -> None:
    new = copy.deepcopy(NEW)
    units: Any = (new.stats or {})["units"]
    units[str(MILITIA)]["base"]["type_50"]["displayed_melee_armour"] = 3
    row = _row(_section(_details(new=new), "stats"), "field.displayed_melee_armour")
    assert (row["old"], row["new"], row["state"]) == ("0", "3", "changed")


def test_stats_a_melee_unit_does_not_have_are_left_out() -> None:
    keys = {row["field"]["key"] for row in _section(_details(), "stats")}
    assert "field.min_range" not in keys
    assert "entity.range" not in keys
    assert "field.accuracy_percent" not in keys
    assert "field.blast_width" not in keys
    assert "field.garrison_capacity" not in keys
    assert _row(_section(_details(), "stats"), "field.unit_class")["new"] == "Infantry"


def test_the_cost_and_train_time_are_listed() -> None:
    cost = _section(_details(), "cost")
    assert _row(cost, "field.cost", resource="food")["new"] == "50"
    assert _row(cost, "field.cost", resource="gold")["new"] == "20"
    assert _row(cost, "field.train_locations", location="#12")["new"] == "21"
    assert all(row["field"]["args"].get("resource") != "#4" for row in cost)


def test_a_building_shows_its_hit_points_garrison_and_cost() -> None:
    view = _details("building", TOWN_CENTER, civ="Alpha")
    stats = _section(view, "stats")
    assert _row(stats, "field.hit_points")["new"] == "2400"
    assert _row(stats, "field.garrison_capacity")["new"] == "15"
    assert _row(_section(view, "cost"), "field.cost", resource="stone")["new"] == "100"
    # Its train time at its builder is the time it takes to build.
    assert _row(_section(view, "cost"), "field.build_time", location="Militia")["new"] == "150"


# --- what affects it -----------------------------------------------------------------------


def test_the_civ_bonuses_team_bonus_unique_techs_and_techs_are_grouped() -> None:
    view = _details()
    assert [group["key"] for group in view["groups"]] == ["civ", "team", "unique", "techs"]
    assert _source_names(view, "team") == [{"key": "field.team_bonus_effect", "args": {}}]
    assert _source_names(view, "unique") == [{"key": "entity.source", "args": {"name": "Bagains"}}]
    names = [name["args"]["name"] for name in _source_names(view, "techs")]
    assert names == ["Scale Mail Armor", "Forging", "Chain Mail Armor", "Man-at-Arms"]


def test_the_tech_cost_trap_is_not_a_bonus_to_the_unit_with_the_same_number() -> None:
    # The tech tree effect halves Scale Mail's cost (tech 74), gives infantry +10% hit points
    # and disables tech 99: only the hit points are about the Militia.
    tree_effect = _group(_details(), "civ")[0]
    assert tree_effect["name"] == {"key": "field.tech_tree_effect", "args": {}}
    assert _sentences(tree_effect) == [("effect.attribute", f"{TIMES}1.1", f"{TIMES}1.1", "same")]


def test_a_tech_that_changed_shows_its_value_old_and_new() -> None:
    forging = next(s for s in _group(_details(), "techs") if s["name"]["args"]["name"] == "Forging")
    assert _sentences(forging) == [("effect.attribute", "+1", "+2", "changed")]
    assert forging["rows"][0]["field"]["args"]["target"] == {
        "key": "effect.class_target",
        "args": {"class": "Infantry"},
    }


def test_a_command_with_no_sentence_stays_raw() -> None:
    bagains = _group(_details(), "unique")[0]
    assert [row["field"]["key"] for row in bagains["rows"]] == [
        "effect.attribute",
        "field.effect_command",
    ]
    assert bagains["rows"][1]["new"] == "type 4 a=74 b=-1 c=77 d=1"


def test_techs_the_civ_cannot_get_and_techs_in_no_tree_are_left_out() -> None:
    view = _details(civ="Beta")
    names = [name["args"]["name"] for name in _source_names(view, "techs")]
    assert "Chain Mail Armor" not in names  # NotAvailable for Beta
    assert "Supplies" not in names and "Kshatriyas + Supplies" not in names  # in no tree
    assert _group(view, "civ") == [] and _group(view, "team") == [] and _group(view, "unique") == []


def test_an_upgrade_shows_its_research_and_the_bonus_that_makes_it_free() -> None:
    view = _details("unit", MAN_AT_ARMS)
    title = next(s["title"] for s in view["sections"] if s["key"] == "upgrade")
    assert title == {"key": "entity.section.upgrade", "args": {"tech": "Man-at-Arms"}}
    upgrade = _section(view, "upgrade")
    assert _row(upgrade, "field.cost", resource="food")["new"] == "100"
    assert _row(upgrade, "field.research_locations", location="#12")["new"] == "40"
    bonus = _group(view, "civ")
    assert [source["name"]["args"].get("name") for source in bonus] == [
        None,  # the tech tree effect: infantry hit points
        "Civ bonus: Free Militia upgrades",
    ]
    assert bonus[1]["requires"] == "Feudal Age"
    assert [row["new"] for row in bonus[1]["rows"]] == ["=0", "=0"]
    # Its research's own upgrade command is listed with the techs.
    names = [name["args"]["name"] for name in _source_names(view, "techs")]
    assert names[-1] == "Man-at-Arms"


def test_a_scripted_bonus_is_named_since_what_it_affects_is_unknown() -> None:
    assert _details()["scripts"] == ["Effect of Kasbah for Alpha"]
    assert _details(civ="Beta")["scripts"] == []
    assert _details("tech", FORGING)["scripts"] == []


# --- techs ----------------------------------------------------------------------------------


def test_a_tech_shows_its_cost_time_requirements_and_what_it_does() -> None:
    view = _details("tech", SCALE_MAIL)
    research = _section(view, "research")
    assert _row(research, "field.cost", resource="food")["new"] == "100"
    assert _row(research, "field.research_locations", location="#12")["new"] == "40"
    effects = _section(view, "effects")
    assert [row["new"] for row in effects] == ["+1", "+1"]
    assert "stats" not in [section["key"] for section in view["sections"]]


def test_a_tech_lists_the_bonuses_to_its_cost() -> None:
    civ = _group(_details("tech", SCALE_MAIL), "civ")
    assert [source["name"] for source in civ] == [{"key": "field.tech_tree_effect", "args": {}}]
    assert _sentences(civ[0]) == [
        ("effect.tech_resource_cost", f"{TIMES}0.5", f"{TIMES}0.5", "same")
    ]


def test_required_techs_are_named() -> None:
    view = _details("tech", FREE_UPGRADES)
    assert _row(_section(view, "research"), "field.required_techs")["new"] == "Feudal Age"


# --- no civ, one side, other indices ----------------------------------------------------------


def test_with_no_civ_the_shared_record_and_the_techs_any_civ_gets_are_shown() -> None:
    view = _details(civ=None)
    assert view["civ"] is None
    assert view["available"] == {"old": None, "new": None}
    assert [group["key"] for group in view["groups"]] == ["techs"]
    names = [name["args"]["name"] for name in _source_names(view, "techs")]
    assert names == ["Scale Mail Armor", "Forging", "Chain Mail Armor", "Man-at-Arms"]
    assert view["note"]["key"] == "entity.note_no_civ"
    assert view["scripts"] == []


def test_each_version_is_read_with_its_own_civ_index() -> None:
    # A civ added before Alpha in the newer version moves Alpha from slot 1 to slot 2.
    new = _snapshot(new=True, civs=("Zeta", "Alpha", "Beta"))
    view = _details(new=new)
    assert _source_names(view, "team") == [{"key": "field.team_bonus_effect", "args": {}}]
    team = _group(view, "team")[0]
    assert _sentences(team) == [("effect.attribute", "+1", "+1", "same")]


def test_a_unit_only_in_the_newer_version_reads_as_new() -> None:
    old = _snapshot(new=False, with_man_at_arms=False)
    view = _details("unit", MAN_AT_ARMS, old=old)
    assert view["presence"] == "new"
    hit_points = _row(_section(view, "stats"), "field.hit_points")
    assert (hit_points["old"], hit_points["new"], hit_points["state"]) == ("45", "45", "same")


def test_a_version_without_stats_still_has_a_name_and_says_so() -> None:
    old = _snapshot(new=False, stats=False)
    view = _details(old=old)
    assert view["stats_missing"] == {"old": True, "new": False}
    assert view["name"] == "Militia"
    hit_points = _row(_section(view, "stats"), "field.hit_points")
    assert (hit_points["new"], hit_points["state"]) == ("45", "same")


def test_neither_version_with_stats_still_describes_the_tree_node() -> None:
    old = _snapshot(new=False, stats=False)
    new = _snapshot(new=True, stats=False)
    view = _details(old=old, new=new)
    assert view["name"] == "Militia"
    assert view["sections"] == [] and view["groups"] == []
    assert view["stats_missing"] == {"old": True, "new": True}


def test_with_no_civ_the_chronicles_trees_do_not_name_the_unit() -> None:
    # The Chronicles civs give units other names, e.g. the Archer reads "Bowman" (D-38).
    chronicles = dict(_node("Unit", MILITIA, 1, name_string_id=9999), name="Hoplite")
    english: Any = NEW.strings["tables"]
    new = replace(
        NEW,
        civs=[{**_civ("Achaeans", 9), "era": "antiquity"}, *NEW.civs],
        tech_trees={"Achaeans": [chronicles], **NEW.tech_trees},
        strings={"tables": {"en": {**english["en"], "9999": "Hoplite"}}},
    )
    assert _details(civ=None, new=new)["name"] == "Militia"
    assert _details(civ="Achaeans", new=new)["name"] == "Hoplite"


def test_a_bonus_requirement_names_only_techs_players_see() -> None:
    stats: Any = NEW.stats
    techs = {**stats["techs"], "500": _tech("Shadow Node+ for Age Two", -1)}  # no display name
    techs[str(FREE_UPGRADES)] = dict(
        techs[str(FREE_UPGRADES)], required_techs=[FEUDAL, 500, -1, -1, -1, -1]
    )
    new = replace(NEW, stats={**stats, "techs": techs})
    source = _group(_details("unit", MAN_AT_ARMS, new=new), "civ")[1]
    assert source["requires"] == "Feudal Age"
    # The tech's own panel lists every requirement, as the comparison does.
    research = _section(_details("tech", FREE_UPGRADES, new=new), "research")
    assert _row(research, "field.required_techs")["new"] == "Feudal Age; Shadow Node+ for Age Two"


def test_a_civ_whose_tree_does_not_list_it_makes_no_claim_about_availability() -> None:
    # Beta's tree doesn't list Bagains at all: absent from a tree isn't "not available", since a
    # civ also owns forms outside its tree, such as a packed Trebuchet (D-37).
    assert _details("tech", BAGAINS, civ="Beta")["available"] == {"old": None, "new": None}
    assert _details("tech", CHAIN_MAIL, civ="Beta")["available"] == {"old": False, "new": False}


def test_a_raw_command_added_before_another_does_not_shift_the_pairing() -> None:
    stats: Any = NEW.stats
    effects = dict(stats["effects"])
    bagains = dict(effects[str(BAGAINS)])
    bagains["commands"] = [_command(4, a=MILITIA, c=78, d=2.0), *bagains["commands"]]
    effects[str(BAGAINS)] = bagains
    new = replace(NEW, stats={**stats, "effects": effects})
    rows = _group(_details(new=new), "unique")[0]["rows"]
    raw = [
        (row["old"], row["new"], row["state"])
        for row in rows
        if row["field"]["key"] == "field.effect_command"
    ]
    assert raw == [
        (None, "type 4 a=74 b=-1 c=78 d=2", "added"),
        ("type 4 a=74 b=-1 c=77 d=1", "type 4 a=74 b=-1 c=77 d=1", "same"),
    ]

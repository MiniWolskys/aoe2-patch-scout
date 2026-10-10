# SPDX-License-Identifier: GPL-3.0-or-later
"""One civ's tech tree view, with a comparison's changes marked on it (spec: Marks, Backend)."""

from typing import Any

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.entries import group
from patch_scout.diff.model import Change, ChangeSet, Entity, Message, Scope, Side
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot
from patch_scout.tree.build import build

BREAK = r"\n"  # the game's line break in string files
ARCHER, CROSSBOW, RANGE, THUMB_RING = 4, 24, 87, 437


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


def _node(use_type: str, node_id: int, age: int, status: str, **extra: Any) -> JsonObject:
    node: JsonObject = {
        "use_type": use_type,
        "node_id": node_id,
        "age_id": age,
        "node_status": status,
        "building_id": RANGE if use_type != "Building" else None,
        "link_id": None,
        "link_node_type": None,
        "node_type": "Unit" if use_type == "Unit" else use_type,
        "name_string_id": None,
        "help_string_id": None,
        "icon": None,
    }
    node.update(extra)
    return node


def _unit(base: JsonObject) -> JsonValue:
    return {"base": base, "base_civs": [0, 1, 2], "overrides": {}, "absent_civs": []}


def _build_snapshot(*, new: bool, civs: tuple[str, ...] = ("Alpha", "Beta")) -> Snapshot:
    """The old build has Thumb Ring and no Crossbowman; the new one the reverse."""
    tree = [
        _node("Building", RANGE, 2, "ResearchedCompleted", name_string_id=5087),
        _node("Unit", ARCHER, 2, "ResearchedCompleted", name_string_id=5083, help_string_id=105083),
        _node(
            "Unit",
            CROSSBOW,
            3,
            "ResearchedCompleted" if new else "NotAvailable",
            link_id=ARCHER,
            link_node_type="Unit",
            name_string_id=5084,
        ),
    ]
    if not new:
        tree.append(_node("Tech", THUMB_RING, 3, "ResearchRequired", name_string_id=7437))
    archer: JsonObject = {
        "hit_points": 35 if new else 30,
        "language_dll_name": 5083,
        "garrison_capacity": 0,
        "type_50": {"displayed_attack": 4, "displayed_melee_armour": 0, "displayed_range": 4.0},
        "creatable": {
            "displayed_pierce_armour": 0,
            "resource_costs": [
                {"amount": 25, "flag": 1, "type": 1},
                {"amount": 1, "flag": 0, "type": 4},
            ],
        },
    }
    archery_range: JsonObject = {"hit_points": 1500, "language_dll_name": 5087}
    all_civs = [_civ("Gaia", 0)] + [_civ(name, i + 1) for i, name in enumerate(civs)]
    return make_snapshot(
        meta={
            "capture_id": "new" if new else "old",
            "captured_at": "2026-09-16T10:00:00Z",
            "game_build": "2.0" if new else "1.0",
        },
        civs=all_civs,
        tech_trees={name: tree for name in civs},
        strings={
            "tables": {
                "en": {
                    "5083": "Archer",
                    "5084": "Crossbowman",
                    "5087": "Archery Range",
                    "7437": "Thumb Ring",
                    "26083": "Create <b>Archer<b> (<cost>)" + BREAK + "<hp> <attack>",
                }
            }
        },
        flags={"stats_available": True},
        stats={
            "units": {str(ARCHER): _unit(archer), str(RANGE): _unit(archery_range)},
            "techs": {},
            "effects": {},
            "civ_dat": [],
        },
    )


OLD = _build_snapshot(new=False)
NEW = _build_snapshot(new=True)


def _nodes(view: JsonObject | None) -> dict[str, Any]:
    """The view's nodes by key, read as plain values: the tests index deep into them."""
    assert view is not None
    nodes: Any = view["nodes"]
    return {str(node["key"]): node for node in nodes}


def _view(change_set: ChangeSet | None = None, civ: str = "Alpha", **kwargs: Any) -> dict[str, Any]:
    changes = change_set if change_set is not None else compare(OLD, NEW)
    return _nodes(build(OLD, NEW, changes, civ, **kwargs))


def _hand_set(*changes: Change) -> ChangeSet:
    side = Side("a", "A", "1.0", "2026-09-16T00:00:00Z", prerelease=False, stats_available=True)
    return ChangeSet(old=side, new=side, changes=changes, entries=group(changes))


def _archer_change(scope: Scope, level: str = "headline", civ: str | None = None) -> Change:
    return Change(
        "unit_stats",
        "modified",
        Entity("unit", str(ARCHER), "Archer"),
        scope,
        Message("field.hit_points"),
        old="30",
        new="35",
        civ=civ,
        level=level,  # type: ignore[arg-type]  # one of the three levels
    )


def test_a_node_available_only_in_the_new_tree_is_gained() -> None:
    assert _view()["Unit:24"]["mark"] == "gained"


def test_a_node_the_new_tree_dropped_is_drawn_from_the_old_one_and_lost() -> None:
    nodes = _view()
    assert nodes["Tech:437"]["mark"] == "lost"
    assert nodes["Tech:437"]["name"] == "Thumb Ring"


def test_a_node_with_a_change_for_the_civ_is_changed() -> None:
    archer = _view()["Unit:4"]
    assert archer["mark"] == "changed"
    changes = archer["changes"]
    assert isinstance(changes, list) and changes
    assert {change["new"] for change in changes if isinstance(change, dict)} == {"35"}


def test_the_tooltip_holds_the_template_and_old_and_new_values() -> None:
    tooltip = _view()["Unit:4"]["tooltip"]
    assert isinstance(tooltip, dict)
    assert tooltip["stats"]["hp"] == {"old": "30", "new": "35"}
    assert tooltip["stats"]["attack"] == {"old": "4", "new": "4"}
    assert tooltip["cost"]["new"] == [{"resource": "wood", "amount": 25}]
    first_line = tooltip["lines"][0]
    assert any(run["kind"] == "cost" for run in first_line)


def test_a_missing_value_is_none_not_a_guess() -> None:
    tooltip = _view()["Building:87"]["tooltip"]
    assert tooltip["stats"]["attack"] == {"old": None, "new": None}


def test_a_node_without_a_template_shows_its_name() -> None:
    tooltip = _view()["Tech:437"]["tooltip"]
    lines = tooltip["lines"]
    assert [[(run["text"], run["bold"]) for run in line] for line in lines] == [
        [("Thumb Ring", True)]
    ]


def test_every_node_has_a_place_and_the_upgrade_line_is_linked() -> None:
    view: Any = build(OLD, NEW, compare(OLD, NEW), "Alpha")
    assert ["Unit:24", "Unit:4"] in view["links"]
    for node in _nodes(view).values():
        assert isinstance(node["column"], (int, float)) and isinstance(node["row"], int)


def test_a_new_civ_has_no_gained_or_lost_marks() -> None:
    new = _build_snapshot(new=True, civs=("Alpha", "Beta", "Gamma"))
    view = build(OLD, new, compare(OLD, new), "Gamma")
    assert view is not None and view["new_civ"] is True
    assert {node["mark"] for node in _nodes(view).values()} <= {None, "changed", "renamed"}


def test_a_removed_civ_draws_its_old_tree_lost() -> None:
    new = _build_snapshot(new=True, civs=("Beta",))
    view = build(OLD, new, compare(OLD, new), "Alpha")
    assert view is not None and view["removed_civ"] is True
    marks = {node["mark"] for node in _nodes(view).values() if node["available"]}
    assert marks == {"lost"}


def test_a_civ_in_neither_build_has_no_tree() -> None:
    assert build(OLD, NEW, compare(OLD, NEW), "Nowhere") is None


def test_a_minor_change_marks_only_when_minor_changes_are_shown() -> None:
    change_set = _hand_set(_archer_change(Scope("all"), level="detail"))
    assert _view(change_set)["Unit:4"]["mark"] is None
    assert _view(change_set, details=True)["Unit:4"]["mark"] == "changed"


def test_a_scope_that_leaves_this_civ_out_does_not_mark_it() -> None:
    assert (
        _view(_hand_set(_archer_change(Scope("all_except", ("Alpha",)))))["Unit:4"]["mark"] is None
    )
    assert (
        _view(_hand_set(_archer_change(Scope("all_except", ("Beta",)))))["Unit:4"]["mark"]
        == "changed"
    )


def test_a_change_spread_to_another_civ_does_not_mark_this_one() -> None:
    change = _archer_change(Scope("some", ("Beta",)), civ="Beta")
    assert _view(_hand_set(change))["Unit:4"]["mark"] is None


def test_a_low_priority_change_marks_only_when_those_are_shown() -> None:
    """A help text change is in the low-priority Text category, hidden by default."""
    text = Change(
        "text",
        "text_changed",
        Entity("unit", str(ARCHER), "Archer"),
        Scope("all"),
        Message("field.help_text"),
    )
    assert _view(_hand_set(text))["Unit:4"]["mark"] is None
    assert _view(_hand_set(text), low_priority=True)["Unit:4"]["mark"] == "changed"


def test_a_node_the_civ_cannot_get_is_never_marked_changed() -> None:
    """A change for "all civilizations that have it" says nothing about a civ without it."""
    change = Change(
        "unit_stats",
        "modified",
        Entity("unit", "74", "Militia"),
        Scope("having", count=40),
        Message("field.hit_points"),
        old="40",
        new="45",
    )
    old_tree = _build_snapshot(new=False)
    new_tree = _build_snapshot(new=True)
    for snapshot in (old_tree, new_tree):
        tree = snapshot.tech_trees["Alpha"]
        assert isinstance(tree, list)
        tree.append(_node("Unit", 74, 1, "NotAvailable", name_string_id=5083))
    view: Any = build(old_tree, new_tree, _hand_set(change), "Alpha")
    assert _nodes(view)["Unit:74"]["mark"] is None
    assert _nodes(view)["Unit:74"]["changes"] == []


def test_technical_changes_alone_do_not_bring_minor_ones() -> None:
    """The two filters are independent, as in the change list."""
    change_set = _hand_set(_archer_change(Scope("all"), level="detail"))
    assert _view(change_set, technical=True)["Unit:4"]["mark"] is None


def test_a_change_with_no_civ_scope_marks_every_civ_that_has_the_node() -> None:
    """A generic tech such as Loom has no civ: its changes read under Overall, scope global."""
    assert _view(_hand_set(_archer_change(Scope())))["Unit:4"]["mark"] == "changed"


def test_the_civ_bonus_text_comes_as_a_diff_of_its_lines() -> None:
    def with_bonus(snapshot: Snapshot, text: str) -> Snapshot:
        civs: Any = snapshot.civs
        civs[1] = dict(civs[1]) | {"bonus_string_id": 120151}
        tables: Any = snapshot.strings["tables"]
        tables["en"] = dict(tables["en"]) | {"120151": text}
        return snapshot

    old = with_bonus(
        _build_snapshot(new=False), "Archer civilization" + BREAK + "• Foot archers +1"
    )
    new = with_bonus(_build_snapshot(new=True), "Archer civilization" + BREAK + "• Foot archers +2")

    view: Any = build(old, new, compare(old, new), "Alpha")

    runs = [(run["kind"], run["text"]) for run in view["bonus"]]
    assert ("removed", "+1") in runs and ("added", "+2") in runs
    assert runs[0] == ("same", "Archer civilization\n• Foot archers ")

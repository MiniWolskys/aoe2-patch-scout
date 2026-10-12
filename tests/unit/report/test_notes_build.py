# SPDX-License-Identifier: GPL-3.0-or-later
"""The patch notes: a comparison written the way the official notes are (D-51, diff-rules.md).

Change sets are built by hand here, with the engine's own entry grouping, so each rule is shown
on the smallest input that needs it. The real 101.103.48987.0 → 101.103.54800.0 comparison is
where the examples come from.
"""

from typing import Any

import pytest

from patch_scout.diff.effects import TIMES
from patch_scout.diff.entries import group
from patch_scout.diff.model import (
    Change,
    ChangeSet,
    CivRef,
    Entity,
    Message,
    Notice,
    Scope,
    Side,
    WordDiff,
)
from patch_scout.i18n.catalog import Catalog, load_catalog
from patch_scout.report.notes import Notes, build, render

OLD = Side("old", "Live", "101.103.48987.0", "2026-09-16T00:00:00Z", False, True)
NEW = Side("new", "PUP", "101.103.54800.0", "2026-10-10T00:00:00Z", True, True)
ALL = Scope("all")
CIVS = (
    CivRef("Franks", "Franks", "base", {"hash": "crest"}, added=False, count=1),
    CivRef("Persians", "Persians", "base", None, added=False, count=1),
    CivRef("Spartans", "Spartans", "antiquity", None, added=False, count=1),
    CivRef("Danes", "Danes", "base", None, added=True, count=1),
)


@pytest.fixture(scope="module")
def catalog() -> Catalog:
    return load_catalog("en")


def unit(name: str, unit_id: str = "1", **overrides: Any) -> Entity:
    return Entity("unit", unit_id, name, **overrides)


def tech(name: str, tech_id: str = "100", **overrides: Any) -> Entity:
    return Entity("tech", tech_id, name, **overrides)


def stat(entity: Entity, key: str, old: str, new: str, **overrides: Any) -> Change:
    values: dict[str, Any] = {
        "category": "unit_stats",
        "kind": "modified",
        "entity": entity,
        "scope": ALL,
        "field": Message(key),
        "old": old,
        "new": new,
    }
    return Change(**(values | overrides))


def cost(entity: Entity, resource: str, old: str, new: str, **overrides: Any) -> Change:
    field = Message("field.cost", {"resource": resource})
    return stat(entity, "field.cost", old, new, **({"field": field} | overrides))


def effect(
    owner: Entity, target: str, attribute: str, old: str, new: str, **overrides: Any
) -> Change:
    """An effect command written as a sentence, as `diff.engine` makes them (O-5, layer 2)."""
    values: dict[str, Any] = {
        "category": "techs",
        "kind": "modified",
        "entity": owner,
        "scope": Scope(),
        "field": Message("effect.attribute", {"target": target, "attribute": attribute}),
        "old": old,
        "new": new,
        "detail": Message("detail.effect_command_raw", {"effect": "x", "command": 1, "raw": "r"}),
    }
    return Change(**(values | overrides))


def node(entity: Entity, civ: str, old: str, new: str) -> Change:
    return Change(
        "civ_availability",
        "availability",
        entity,
        Scope("some", (civ,)),
        field=Message("field.node_status"),
        old=old,
        new=new,
        civ=civ,
    )


def notes(catalog: Catalog, *changes: Change, **overrides: Any) -> Notes:
    values: dict[str, Any] = {
        "old": OLD,
        "new": NEW,
        "changes": changes,
        "entries": group(changes),
        "civs": CIVS,
    }
    return build(ChangeSet(**(values | overrides)), catalog)


def lines(result: Notes) -> list[str]:
    """Every bullet, children indented by two spaces per level."""
    found: list[str] = []

    def walk(items: Any, depth: int) -> None:
        for item in items:
            found.append("  " * depth + item.text)
            walk(item.children, depth + 1)

    for section in result.sections:
        for group_ in section.groups:
            walk(group_.items, 0)
    return found


def groups(result: Notes) -> dict[str, list[str]]:
    """Each group's top-level bullets, by "section/group" title."""
    return {
        f"{section.title}/{group_.title}": [item.text for item in group_.items]
        for section in result.sections
        for group_ in section.groups
    }


# --- sentences ----------------------------------------------------------------------------------


def test_a_units_fields_read_as_one_sentence(catalog: Catalog) -> None:
    onager = unit("Onager")
    result = notes(
        catalog,
        stat(onager, "field.hit_points", "60", "65"),
        stat(onager, "field.line_of_sight", "10", "8"),
    )

    assert groups(result) == {
        "General/Unit stats": [
            "Onager hit points increased from 60 → 65, line of sight decreased from 10 → 8."
        ]
    }


def test_values_that_are_not_numbers_of_one_form_read_changed(catalog: Catalog) -> None:
    result = notes(
        catalog,
        stat(
            tech("Bombard Tower"),
            "field.required_techs",
            "Chemistry",
            "Imperial Age",
            category="techs",
        ),
    )

    assert lines(result) == ["Bombard Tower required techs changed from Chemistry → Imperial Age."]


def test_a_value_that_appears_or_goes_says_so(catalog: Catalog) -> None:
    knight = unit("Knight")
    result = notes(
        catalog,
        stat(knight, "field.attacks", "", "3", field=Message("field.attacks", {"class": "Camels"})),
        stat(knight, "field.armours", "2", "", field=Message("field.armours", {"class": "Ships"})),
    )

    assert lines(result) == ["Knight bonus vs Camels added: 3, ships armour class removed (was 2)."]


def test_the_same_change_to_several_units_is_one_sentence(catalog: Catalog) -> None:
    result = notes(
        catalog,
        *(
            stat(unit(name, str(number)), "field.line_of_sight", "3", "5")
            for number, name in enumerate(("Battering Ram", "Capped Ram", "Siege Ram"))
        ),
    )

    assert lines(result) == [
        "Battering Ram, Capped Ram and Siege Ram line of sight increased from 3 → 5."
    ]


def test_an_elite_unit_pairs_with_its_base_as_the_official_notes_write_it(
    catalog: Catalog,
) -> None:
    result = notes(
        catalog,
        stat(unit("Throwing Axeman", "1"), "field.max_range", "3", "5"),
        stat(unit("Elite Throwing Axeman", "2"), "field.max_range", "4", "6"),
        cost(unit("Hussite Wagon", "3"), "gold", "70", "80"),
        cost(unit("Elite Hussite Wagon", "4"), "gold", "70", "80"),
    )

    assert lines(result) == [
        "(Elite) Throwing Axeman maximum range increased from 3 → 5, Elite 4 → 6.",
        # The same values for both: said once.
        "(Elite) Hussite Wagon cost in gold increased from 70 → 80.",
    ]


def test_a_pair_that_moved_in_opposite_directions_reads_changed(catalog: Catalog) -> None:
    result = notes(
        catalog,
        stat(unit("Hulk", "1"), "field.hit_points", "90", "85"),
        stat(unit("War Hulk", "2"), "field.hit_points", "110", "115"),
    )

    assert lines(result) == ["(War) Hulk hit points changed from 90 → 85, War 110 → 115."]


def test_units_with_different_fields_are_not_paired(catalog: Catalog) -> None:
    result = notes(
        catalog,
        stat(unit("Hulk", "1"), "field.hit_points", "90", "85"),
        stat(unit("War Hulk", "2"), "field.line_of_sight", "7", "8"),
    )

    assert lines(result) == [
        "Hulk hit points decreased from 90 → 85.",
        "War Hulk line of sight increased from 7 → 8.",
    ]


def test_the_civs_that_dont_share_a_change_are_named(catalog: Catalog) -> None:
    result = notes(
        catalog,
        stat(
            unit("Champion"),
            "field.hit_points",
            "60",
            "70",
            scope=Scope("having_except", ("Franks", "Persians"), count=40),
        ),
    )

    assert lines(result) == [
        "Champion hit points increased from 60 → 70 (except Franks and Persians)."
    ]


def test_a_projectile_field_says_so(catalog: Catalog) -> None:
    inner = Message("field.attacks_basic", {"class": "Pierce"}).to_json()
    change = stat(unit("Archer"), "field.projectile", "4", "5")
    change = Change(**{**_fields(change), "field": Message("field.projectile", {"field": inner})})

    assert lines(notes(catalog, change)) == [
        "Archer pierce attack (projectile) increased from 4 → 5."
    ]


def _fields(change: Change) -> dict[str, Any]:
    return {name: getattr(change, name) for name in Change.__slots__}


# --- availability -------------------------------------------------------------------------------


def test_gaining_and_losing_access_read_as_the_official_notes(catalog: Catalog) -> None:
    crane = tech("Treadmill Crane", "1")
    archer = unit("Cavalry Archer", "39")
    result = notes(
        catalog,
        node(crane, "Franks", "NotAvailable", "ResearchedCompleted"),
        node(archer, "Franks", "ResearchedCompleted", "NotAvailable"),
    )

    # Gains first, then losses, whatever the order of the changes.
    assert groups(result) == {
        "Civilizations/Franks": [
            "Gain access to Treadmill Crane.",
            "Lose access to Cavalry Archer.",
        ]
    }


def test_a_tech_tree_label_uses_the_units_own_name_to_pair(catalog: Catalog) -> None:
    gained = [
        Change(
            "civ_availability",
            "added",
            Entity("unit", unit_id, label, where="Archery Range"),
            Scope("some", ("Franks",)),
            civ="Franks",
        )
        for unit_id, label in (("1", "Mounted Crossbowman"), ("2", "H. Mounted Crossbowman"))
    ]
    stats = stat(unit("Heavy Mounted Crossbowman", "2"), "field.hit_points", "1", "55")

    assert groups(notes(catalog, *gained, stats))["Civilizations/Franks"] == [
        "Gain access to (Heavy) Mounted Crossbowman."
    ]


def test_a_node_moving_between_available_states_is_not_access(catalog: Catalog) -> None:
    change = node(unit("Bombard Cannon"), "Franks", "ResearchedCompleted", "ResearchRequired")

    assert lines(notes(catalog, change)) == [
        "Bombard Cannon availability changed from Available → Needs a prerequisite."
    ]


def test_a_renamed_node_says_both_names(catalog: Catalog) -> None:
    change = Change(
        "civ_availability",
        "renamed",
        unit("Longship"),
        Scope("some", ("Franks",)),
        field=Message("field.name"),
        old="Longboat",
        new="Longship",
        civ="Franks",
    )

    assert lines(notes(catalog, change)) == ["Longboat renamed to Longship."]


# --- new units and techs ------------------------------------------------------------------------


def test_a_new_unit_lists_its_stats_with_its_costs_together(catalog: Catalog) -> None:
    rider = unit("Mounted Crossbowman", "1")
    heavy = unit("Heavy Mounted Crossbowman", "2")
    changes = [
        change
        for entity, hp in ((rider, "45"), (heavy, "55"))
        for change in (
            stat(entity, "field.hit_points", "", hp),
            cost(entity, "wood", "", "40"),
            cost(entity, "gold", "", "65"),
        )
    ]

    assert lines(notes(catalog, *changes)) == [
        "NEW: (Heavy) Mounted Crossbowman:",
        "  Hit points: 45; Heavy: 55",
        "  Cost: 40 wood, 65 gold",
    ]


def test_a_new_tech_says_what_it_does_and_its_gain_is_not_repeated(catalog: Catalog) -> None:
    companies = tech("Ordonnance Companies", "700")
    franks = Scope("some", ("Franks",))
    owned: dict[str, Any] = {"scope": franks, "civ": "Franks", "category": "techs"}
    changes = [
        effect(companies, "Mounted Crossbowman", "Gold Cost", "", f"{TIMES}0.6", **owned),
        effect(companies, "Heavy Mounted Crossbowman", "Gold Cost", "", f"{TIMES}0.6", **owned),
        cost(companies, "food", "", "400", **owned),
        cost(companies, "gold", "", "250", **owned),
        stat(
            companies,
            "field.research_locations",
            "",
            "40",
            field=Message("field.research_locations", {"location": "Castle"}),
            **owned,
        ),
        Change(
            "civ_availability",
            "added",
            Entity("tech", "700", "Ordonnance Companies", where="Castle"),
            franks,
            civ="Franks",
        ),
    ]

    assert lines(notes(catalog, *changes)) == [
        "NEW: Ordonnance Companies:",
        "  (Heavy) Mounted Crossbowman: -40% gold cost",
        "  Cost: 400 food, 250 gold",
        "  Research time at Castle: 40",
    ]


def test_a_removed_unit_is_one_line(catalog: Catalog) -> None:
    gone = Change("techs", "removed", tech("Bearded Axe"), Scope("some", ("Franks",)), civ="Franks")

    assert lines(notes(catalog, gone)) == ["Bearded Axe removed."]


# --- effects ------------------------------------------------------------------------------------


def test_techs_that_give_the_same_to_new_units_are_one_sentence(catalog: Catalog) -> None:
    changes = [
        effect(tech(name, str(number)), target, "Pierce attack", "", "+1")
        for number, name in enumerate(("Bodkin Arrow", "Bracer"))
        for target in ("Leif Erikson", "Dreki")
    ]

    assert lines(notes(catalog, *changes)) == [
        "Bodkin Arrow and Bracer now affect Leif Erikson and Dreki: +1 pierce attack."
    ]


def test_targets_given_different_things_get_a_bullet_each(catalog: Catalog) -> None:
    bodkin = tech("Bodkin Arrow")
    changes = [
        effect(bodkin, "Hearth Troop", "Line Of Sight", "", "+1"),
        effect(bodkin, "Elite Hearth Troop", "Line Of Sight", "", "+1"),
        effect(bodkin, "Dreki", "Line Of Sight", "", "+1"),
        effect(bodkin, "Dreki", "Max Range", "", "+1"),
    ]

    assert lines(notes(catalog, *changes)) == [
        "Bodkin Arrow now affects (Elite) Hearth Troop and Dreki:",
        "  (Elite) Hearth Troop: +1 line of sight",
        "  Dreki: +1 line of sight, +1 max range",
    ]


def test_what_an_effect_gives_no_longer_says_so(catalog: Catalog) -> None:
    change = effect(tech("Logistica"), "Cataphract", "Attack", "+6", "")

    assert lines(notes(catalog, change)) == ["Logistica no longer affects Cataphract: +6 attack."]


def test_a_command_that_only_moved_says_nothing(catalog: Catalog) -> None:
    shields = tech("Fabric Shields")
    moved = [
        effect(shields, "Kamayuk", "Pierce armour", "+1", ""),
        effect(shields, "Kamayuk", "Pierce armour", "", "+1"),
    ]

    result = notes(catalog, *moved)

    assert lines(result) == []
    assert result.closing is None  # both are said: nothing changed for players


def test_a_value_changed_for_several_targets_is_one_clause(catalog: Catalog) -> None:
    tactics = tech("Wagenburg Tactics")
    changes = [
        effect(tactics, target, "Movement Speed", f"{TIMES}1.15", f"{TIMES}1.1")
        for target in ("Hand Cannoneer", "Bombard Cannon", "Organ Gun", "Elite Organ Gun")
    ]

    assert lines(notes(catalog, *changes)) == [
        "Wagenburg Tactics: Hand Cannoneer, Bombard Cannon and (Elite) Organ Gun movement speed"
        " decreased from +15% → +10%."
    ]


def test_sentences_without_a_value_are_listed_under_their_tech(catalog: Catalog) -> None:
    regionals = tech("Disable Regionals")

    def disables(name: str) -> Change:
        sentence = Message("effect.disable", {"unit": name}).to_json()
        return effect(
            regionals, "", "", "", "", field=Message("effect.added", {"effect": sentence})
        )

    assert lines(notes(catalog, disables("Cranequins"), disables("Longship"))) == [
        "Disable Regionals: new effects:",
        "  Disables Cranequins",
        "  Disables Longship",
    ]


# --- civs ---------------------------------------------------------------------------------------


def _description(old: str, new: str, civ: str = "Franks") -> Change:
    runs: list[WordDiff] = []
    old_lines, new_lines = old.split("\n"), new.split("\n")
    from difflib import SequenceMatcher

    for tag, i1, i2, j1, j2 in SequenceMatcher(a=old_lines, b=new_lines).get_opcodes():
        if tag == "equal":
            runs += [WordDiff("same", line + "\n") for line in old_lines[i1:i2]]
            continue
        runs += [WordDiff("removed", line + "\n") for line in old_lines[i1:i2]]
        runs += [WordDiff("added", line + "\n") for line in new_lines[j1:j2]]
    return Change(
        "bonuses",
        "text_changed",
        Entity("civ", civ, civ),
        Scope("some", (civ,)),
        field=Message("field.civ_bonus_text"),
        words=tuple(runs),
        civ=civ,
    )


def test_the_civ_description_lists_its_lines_that_changed(catalog: Catalog) -> None:
    old = "Cavalry civilization\n• Foragers +15%\nUnique Techs:\n• Bearded Axe (+2 range)"
    new = "Cavalry civilization\n• Foragers +20%\nUnique Techs:\n• Chivalry (Stables faster)"

    assert lines(notes(catalog, _description(old, new))) == [
        "Civilization description:",
        "  Foragers +15% → Foragers +20%",
        "  Bearded Axe (+2 range) → Chivalry (Stables faster)",
    ]


def test_a_description_that_only_wraps_differently_says_nothing(catalog: Catalog) -> None:
    old = "• Buildings +10% HP in Dark/Feudal/Castle Age"
    new = "• Buildings +10% HP in Dark/Feudal/\nCastle Age"

    result = notes(catalog, _description(old, new))

    assert lines(result) == []
    assert result.closing is None


def test_a_civ_block_reads_in_the_official_order(catalog: Catalog) -> None:
    franks = {"scope": Scope("some", ("Franks",)), "civ": "Franks"}
    changes = [
        node(tech("Treadmill Crane", "5"), "Franks", "NotAvailable", "ResearchedCompleted"),
        stat(unit("Throwing Axeman", "1"), "field.max_range", "3", "5", **franks),
        _description("• Foragers +15%", "• Foragers +20%"),
    ]

    assert groups(notes(catalog, *changes))["Civilizations/Franks"] == [
        "Civilization description:",
        "Throwing Axeman maximum range increased from 3 → 5.",
        "Gain access to Treadmill Crane.",
    ]


def test_a_new_civ_says_so_and_lists_its_tech_tree(catalog: Catalog) -> None:
    danes = Entity("civ", "Danes", "Danes")
    scope = Scope("some", ("Danes",))
    changes = [
        Change("civilizations", "added", danes, scope, civ="Danes"),
        Change(
            "civ_availability",
            "added",
            danes,
            scope,
            field=Message("field.tech_tree_at", {"building": "Barracks"}),
            new="Militia, Spearman",
            civ="Danes",
        ),
        Change(
            "civ_availability",
            "added",
            danes,
            scope,
            field=Message("field.tech_tree_buildings"),
            new="Barracks, Castle",
            civ="Danes",
        ),
    ]

    assert lines(notes(catalog, *changes)) == [
        "New civilization.",
        "Tech tree:",
        "  Barracks: Militia, Spearman",
        "  Buildings: Barracks, Castle",
    ]


def test_the_chronicles_civs_have_their_own_section(catalog: Catalog) -> None:
    change = stat(
        unit("Hoplite"),
        "field.hit_points",
        "60",
        "65",
        scope=Scope("some", ("Spartans",)),
        civ="Spartans",
    )

    result = notes(catalog, change)

    assert [(section.kind, section.title) for section in result.sections] == [
        ("chronicles", "Chronicles")
    ]


def test_a_civ_group_carries_its_crest(catalog: Catalog) -> None:
    result = notes(
        catalog, node(tech("Treadmill Crane"), "Franks", "NotAvailable", "ResearchedCompleted")
    )

    [section] = result.sections
    [civ] = section.groups
    assert (civ.civ, civ.icon) == ("Franks", {"hash": "crest"})


# --- curation -----------------------------------------------------------------------------------


def test_what_the_notes_cant_say_is_counted_at_the_end(catalog: Catalog) -> None:
    onager = unit("Onager")
    raw = Change(
        "techs",
        "modified",
        tech("Butalmapu"),
        field=Message("field.tech_effect"),
        old="type 15 a=1",
        new="type 1 a=2",
        detail=Message("detail.effect_command", {"effect": "x", "command": 1}),
    )
    kept = stat(onager, "field.hit_points", "60", "65")
    changes = [
        kept,
        stat(onager, "field.search_radius", "8", "9", level="detail"),
        stat(unit("#123", "123", named=False), "field.hit_points", "1", "2"),
        stat(unit("Knight"), "field.hit_points", "1", "2", category="icons"),  # low priority
        raw,
        stat(
            onager,
            "field.train_locations",
            "1",
            "2",
            field=Message("field.train_locations", {"location": "#-1"}),
        ),
    ]

    result = notes(catalog, *changes)

    assert lines(result) == ["Onager hit points increased from 60 → 65."]
    assert result.closing is not None and result.closing.startswith("5 more changes")


def test_one_change_left_out_reads_in_the_singular(catalog: Catalog) -> None:
    onager = unit("Onager")
    result = notes(
        catalog,
        stat(onager, "field.hit_points", "60", "65"),
        stat(onager, "field.search_radius", "8", "9", level="detail"),
    )

    assert result.closing is not None and result.closing.startswith("1 more change isn't")


def test_techs_known_only_by_their_internal_name_are_grouped_apart(catalog: Catalog) -> None:
    change = cost(tech("Disable Regionals", internal=True), "food", "1", "", category="techs")

    assert list(groups(notes(catalog, change))) == ["General/Techs with no name in the game"]


# --- header -------------------------------------------------------------------------------------


def test_the_title_names_both_versions(catalog: Catalog) -> None:
    result = notes(catalog, stat(unit("Onager"), "field.hit_points", "60", "65"))

    assert result.title == ("Patch notes: Live 101.103.48987.0 → PUP 101.103.54800.0 (pre-release)")
    assert result.disclaimer.startswith("Written by Patch Scout")


def test_only_the_notices_readers_need_are_kept(catalog: Catalog) -> None:
    notices = (
        Notice("levels_hidden", Message("notice.levels_hidden", {"count": 3})),
        Notice(
            "unusually_many_changes",
            Message("notice.unusually_many_changes", {"percent": 30, "compared": 100}),
        ),
    )
    result = notes(catalog, stat(unit("Onager"), "field.hit_points", "60", "65"), notices=notices)

    assert len(result.notices) == 1
    assert result.notices[0].startswith("30% of the 100 compared unit values changed")


def test_identical_versions_have_nothing_to_say(catalog: Catalog) -> None:
    result = notes(catalog, identical=True)

    assert result.sections == ()
    assert result.empty is not None


# --- text and JSON ------------------------------------------------------------------------------


def test_the_text_is_light_markdown(catalog: Catalog) -> None:
    rider = unit("Mounted Crossbowman")
    result = notes(
        catalog,
        stat(rider, "field.hit_points", "", "45"),
        cost(rider, "wood", "", "40"),
        stat(
            unit("Onager", "2"),
            "field.hit_points",
            "60",
            "65",
            civ="Franks",
            scope=Scope("some", ("Franks",)),
        ),
        stat(unit("Onager", "2"), "field.search_radius", "8", "9", level="detail"),
    )

    assert render(result) == (
        "Patch notes: Live 101.103.48987.0 → PUP 101.103.54800.0 (pre-release)\n"
        "Written by Patch Scout from the game's data. These are not the official patch notes.\n"
        "\n"
        "GENERAL\n"
        "\n"
        "Unit stats\n"
        "\n"
        "- NEW: Mounted Crossbowman:\n"
        "    - Hit points: 45\n"
        "    - Cost: 40 wood\n"
        "\n"
        "CIVILIZATIONS\n"
        "\n"
        "Franks\n"
        "\n"
        "- Onager hit points increased from 60 → 65.\n"
        "\n"
        "1 more change isn't in these notes: a minor or technical one, or one that can't be"
        " written as a sentence. The comparison in Patch Scout lists it.\n"
    )


def test_the_page_gets_the_same_document(catalog: Catalog) -> None:
    result = notes(
        catalog, node(tech("Treadmill Crane"), "Franks", "NotAvailable", "ResearchedCompleted")
    )

    data: Any = result.to_json()

    assert data["sections"][0]["groups"][0] == {
        "title": "Franks",
        "civ": "Franks",
        "icon": {"hash": "crest"},
        "items": [{"text": "Gain access to Treadmill Crane.", "children": []}],
    }

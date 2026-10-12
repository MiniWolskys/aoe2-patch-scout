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
        stat(unit("Hulk"), "field.unit_class", "Warship", "Siege Weapon"),
    )

    assert lines(result) == ["Hulk unit class changed from Warship → Siege Weapon."]


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


def test_a_new_unit_is_one_line_with_where_it_is_trained(catalog: Catalog) -> None:
    rider = unit("Mounted Crossbowman", "1")
    heavy = unit("Heavy Mounted Crossbowman", "2")
    trained = Message("field.train_locations", {"location": "Archery Range"})
    changes = [
        change
        for entity, hp in ((rider, "45"), (heavy, "55"))
        for change in (
            stat(entity, "field.hit_points", "", hp),
            cost(entity, "wood", "", "40"),
            stat(entity, "field.train_locations", "", "40", field=trained),
        )
    ]

    result = notes(catalog, *changes)

    # Its stats are in the detailed changes and the tech tree; the line says it is new.
    assert lines(result) == ["NEW: (Heavy) Mounted Crossbowman (Archery Range)."]
    assert result.closing is None


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

    result = notes(catalog, *changes)

    # What it does, in one line; its cost and research are in the detailed changes and the tree.
    assert lines(result) == [
        "NEW: Ordonnance Companies: (Heavy) Mounted Crossbowman -40% gold cost."
    ]
    assert result.closing is None


def test_a_new_upgrade_reads_as_an_upgrade(catalog: Catalog) -> None:
    """ "NEW: Heavy Mounted Crossbowman: Upgrades Mounted Crossbowman to Heavy Mounted
    Crossbowman" said the name twice (101.103.54800.0)."""
    heavy = tech("Heavy Mounted Crossbowman", "701")
    sentence = Message(
        "effect.upgrade", {"unit": "Mounted Crossbowman", "to": "Heavy Mounted Crossbowman"}
    ).to_json()
    changes = [
        effect(heavy, "", "", "", "", field=Message("effect.added", {"effect": sentence})),
        cost(heavy, "food", "", "900", category="techs", scope=Scope()),
        stat(
            heavy,
            "field.research_locations",
            "",
            "45",
            field=Message("field.research_locations", {"location": "Archery Range"}),
            category="techs",
            scope=Scope(),
        ),
    ]

    assert lines(notes(catalog, *changes)) == ["NEW: Heavy Mounted Crossbowman upgrade."]


def test_a_techs_cost_reads_as_its_research_cost(catalog: Catalog) -> None:
    """ "Elite Rattan Archer cost in food decreased" read as the unit's cost (54800)."""
    upgrade = tech("Elite Rattan Archer", "702")
    change = cost(upgrade, "food", "1000", "800", category="techs")

    assert lines(notes(catalog, change)) == [
        "Elite Rattan Archer research cost in food decreased from 1000 → 800."
    ]


def test_required_techs_are_left_to_the_detailed_changes(catalog: Catalog) -> None:
    """On 54800 every change to them was plumbing ("Dupl. Imperial Age"); players read
    requirements as ages and availability, which the notes say from the tech tree."""
    change = stat(
        tech("Bombard Cannon"),
        "field.required_techs",
        "Imperial Age; Chemistry; Civ bonus: Free Chemistry",
        "Dupl. Imperial Age; Chemistry",
        category="techs",
    )

    result = notes(catalog, change)

    assert lines(result) == []
    assert result.closing is not None


def test_a_tech_whose_effect_moved_into_a_script_leaves_its_effects_out(catalog: Catalog) -> None:
    """On 101.103.54800.0 Kasbah and four other techs gained a script that only shows a message,
    and the Malians' gold bonus moved into a script: "Gold Bonus removed" read as a nerf. The
    script says nothing a player can read; the detailed changes keep it all."""
    owned: dict[str, Any] = {"scope": Scope("some", ("Franks",)), "civ": "Franks"}
    bonus = tech("Civ bonus: Gold productivity", "800")
    script = Message("effect.script", {"title": "Effect of Gold Miner bonus"}).to_json()
    changes = [
        effect(bonus, "", "", "", "", field=Message("effect.added", {"effect": script}), **owned),
        effect(
            bonus,
            "",
            "",
            f"{TIMES}1.1",
            "",
            field=Message("effect.resource", {"resource": "Gold Bonus"}),
            **owned,
        ),
        cost(bonus, "gold", "100", "120", category="techs", **owned),
    ]

    result = notes(catalog, *changes)

    assert lines(result) == [
        "Civ bonus: Gold productivity research cost in gold increased from 100 → 120."
    ]
    assert result.closing is not None  # the script and the effect it took over are counted


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
        "Bodkin Arrow and Bracer now affect Leif Erikson and Dreki."
    ]


def test_what_a_tech_gives_each_target_is_left_to_the_details(catalog: Catalog) -> None:
    bodkin = tech("Bodkin Arrow")
    changes = [
        effect(bodkin, "Hearth Troop", "Line Of Sight", "", "+1"),
        effect(bodkin, "Elite Hearth Troop", "Line Of Sight", "", "+1"),
        effect(bodkin, "Dreki", "Line Of Sight", "", "+1"),
        effect(bodkin, "Dreki", "Max Range", "", "+1"),
    ]

    # Players know what Bodkin Arrow does: the notes say whom it now affects.
    assert lines(notes(catalog, *changes)) == [
        "Bodkin Arrow now affects (Elite) Hearth Troop and Dreki."
    ]


def test_what_an_effect_gives_no_longer_says_so(catalog: Catalog) -> None:
    change = effect(tech("Logistica"), "Cataphract", "Attack", "+6", "")

    assert lines(notes(catalog, change)) == ["Logistica no longer affects Cataphract."]


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

    # One bullet per line, only the part that changed, under the game's own heading.
    assert lines(notes(catalog, _description(old, new))) == [
        "Foragers +15% → +20%",
        "Unique Techs: Bearded Axe (+2 range) → Chivalry (Stables faster)",
    ]


def test_a_description_line_added_or_removed_says_where(catalog: Catalog) -> None:
    old = "Cavalry civilization\n• Mill technologies free\nTeam Bonus:\n• Knights +2 line of sight"
    new = "Cavalry civilization\nTeam Bonus:\n• Knights +2 line of sight\n• Scouts +1 speed"

    assert lines(notes(catalog, _description(old, new))) == [
        "Removed: Mill technologies free",
        "New in Team Bonus: Scouts +1 speed",
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
        "Foragers +15% → +20%",
        "Throwing Axeman maximum range increased from 3 → 5.",
        "Gain access to Treadmill Crane.",
    ]


def test_a_new_civ_reads_in_a_few_lines(catalog: Catalog) -> None:
    danes = Entity("civ", "Danes", "Danes")
    scope = Scope("some", ("Danes",))
    owned: dict[str, Any] = {"scope": scope, "civ": "Danes"}

    def summary(key: str, names: str) -> Change:
        return Change("civilizations", "added", danes, field=Message(key), new=names, **owned)

    description = WordDiff("added", "Infantry and Siege civilization\n• Loot 25% of buildings")
    changes = [
        Change("civilizations", "added", danes, **owned),
        Change(
            "bonuses",
            "text_changed",
            danes,
            field=Message("field.civ_bonus_text"),
            words=(description,),
            **owned,
        ),
        summary("field.unique_units", "Jomsviking, Elite Jomsviking"),
        summary("field.regional_units", "Varangian Guard, E. Varangian Guard, Longship"),
        Change(
            "civ_availability",
            "added",
            danes,
            field=Message("field.tech_tree_at", {"building": "Barracks"}),
            new="Militia, Spearman",
            **owned,
        ),
        stat(unit("Jomsviking", "9"), "field.hit_points", "", "70", **owned),
    ]

    result = notes(catalog, *changes)

    assert lines(result) == [
        "New civilization: Infantry and Siege civilization.",
        "Unique units: Jomsviking.",
        "Regional units: Varangian Guard and Longship.",
    ]
    # Its tree and its units' stats are in the detailed changes: counted, not lost.
    assert result.closing is not None and result.closing.startswith("2 more changes")


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


def test_a_change_every_civ_that_has_it_shares_is_said_once_in_general(
    catalog: Catalog,
) -> None:
    """Lou Chuan on 101.103.54800.0 was repeated under its five civs; the official notes put it
    in General. Gaining access stays with each civ, and a civ's own unit stays in its block."""
    holders = Scope("some", ("Franks", "Persians"), count=2)
    lou_chuan = unit("Lou Chuan", "1948")
    attack = Message("field.attacks", {"class": "All Buildings"})
    shared = [
        stat(lou_chuan, "field.attacks", "230", "180", field=attack, scope=holders, civ=civ)
        for civ in holders.civs
    ]
    gains = [
        Change("civ_availability", "added", lou_chuan, holders, civ=civ) for civ in holders.civs
    ]
    franks_only = Scope("some", ("Franks",), count=1)
    axeman = stat(
        unit("Throwing Axeman", "281"), "field.max_range", "3", "5", scope=franks_only, civ="Franks"
    )

    ram = stat(unit("Battering Ram", "35"), "field.line_of_sight", "3", "5")

    # The engine puts civ-specific changes first; in General they read in name order.
    result = notes(catalog, *shared, *gains, axeman, ram)

    assert groups(result) == {
        "General/Unit stats": [
            "Battering Ram line of sight increased from 3 → 5.",
            "Lou Chuan bonus vs All Buildings decreased from 230 → 180.",
        ],
        "Civilizations/Franks": [
            "Throwing Axeman maximum range increased from 3 → 5.",
            "Gain access to Lou Chuan.",
        ],
        "Civilizations/Persians": ["Gain access to Lou Chuan."],
    }
    assert result.closing is None  # every copy counts as said


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


def test_techs_known_only_by_their_internal_name_are_left_out(catalog: Catalog) -> None:
    # Plumbing players never see (maintainer, 2026-10-12): counted, never written.
    change = cost(tech("Disable Regionals", internal=True), "food", "1", "", category="techs")

    result = notes(catalog, change)

    assert result.sections == ()
    assert result.closing is not None and result.closing.startswith("1 more change")


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
    crane = tech("Treadmill Crane")
    where = Message("field.research_locations", {"location": "University"})
    result = notes(
        catalog,
        stat(crane, "field.research_locations", "", "40", category="techs", field=where),
        cost(crane, "wood", "", "200", category="techs"),
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
        "Technologies\n"
        "\n"
        "- NEW: Treadmill Crane.\n"
        "\n"
        "CIVILIZATIONS\n"
        "\n"
        "Franks\n"
        "\n"
        "- Onager hit points increased from 60 → 65.\n"
        "\n"
        "1 more change isn't in these notes: a minor or technical one, a detail of a new"
        " civilization, or one that can't be written as a sentence. The detailed changes list"
        " it.\n"
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


# --- review fixes -------------------------------------------------------------------------------


def test_every_kind_of_sentence_names_the_civs_that_dont_share_it(catalog: Catalog) -> None:
    others = Scope("having_except", ("Franks",), count=40)
    crane = tech("Treadmill Crane", "1")
    gained = Change("civ_availability", "added", crane, others)
    gone = Change("techs", "removed", tech("Bearded Axe", "2"), others)
    given = effect(tech("Gambesons", "3"), "Dreki", "Pierce armour", "", "+1", scope=others)

    # General's groups follow the categories' order: availability, then techs.
    assert lines(notes(catalog, gained, gone, given)) == [
        "Gain access to Treadmill Crane (except Franks).",
        "Bearded Axe removed (except Franks).",
        "Gambesons now affects Dreki (except Franks).",
    ]


def test_a_change_with_no_values_says_whether_it_came_or_went(catalog: Catalog) -> None:
    stable = Entity("building", "101", "Stable")
    franks = Scope("some", ("Franks",))
    offer = Message("field.building_offer")
    came = Change("civ_availability", "added", stable, franks, field=offer, civ="Franks")
    script = Change(
        "other_effects", "removed", Entity("script", "52", "Effect of Kasbah"), franks, civ="Franks"
    )

    assert lines(notes(catalog, came, script)) == [
        "Stable building offer added.",
        "Effect of Kasbah removed.",
    ]


def test_subjects_whose_field_changed_differently_are_not_paired(catalog: Catalog) -> None:
    result = notes(
        catalog,
        stat(unit("Pikeman", "1"), "field.hit_points", "22", "25"),
        stat(unit("Elite Pikeman", "2"), "field.hit_points", "30", ""),
    )

    assert lines(result) == [
        "Pikeman hit points increased from 22 → 25.",
        "Elite Pikeman hit points removed (was 30).",
    ]


def test_what_a_new_tech_doesnt_say_is_counted(catalog: Catalog) -> None:
    placeholder = tech("Hamask", "9")
    sentence = Message("effect.disable", {"unit": "Militia"}).to_json()
    changes = [
        stat(
            placeholder,
            "field.research_locations",
            "",
            "35",
            category="techs",
            field=Message("field.research_locations", {"location": "Castle"}),
        ),
        effect(
            placeholder,
            "",
            "",
            "",
            "",
            scope=ALL,
            field=Message("effect.removed", {"effect": sentence}),
        ),
    ]

    result = notes(catalog, *changes)

    assert lines(result) == ["NEW: Hamask."]
    assert result.closing is not None and result.closing.startswith("1 more change")


def test_a_description_line_that_only_changed_punctuation_says_nothing(catalog: Catalog) -> None:
    # Mapuche on 101.103.54800.0: "Slingers and" became "Slingers, and".
    old = "• Malon (Bolas Riders, Slingers and Skirmishers deal pass through damage)"
    new = "• Malon (Bolas Riders, Slingers, and Skirmishers deal pass through damage)"

    result = notes(catalog, _description(old, new))

    assert lines(result) == []
    assert result.closing is None


def test_a_changed_description_isnt_repeated_by_its_bonus_effects(catalog: Catalog) -> None:
    # Teutons on 101.103.54800.0: the description says it; its bonuses' effects said it again.
    teutons = {"scope": Scope("some", ("Franks",)), "civ": "Franks"}
    bonus = tech("Civ bonus: Inf Cav +1 armor Castle Age", "1")
    tactics = tech("Wagenburg Tactics", "2")
    shields = tech("Fabric Shields", "3")
    changes = [
        _description(
            "• Barracks units +1 armor", "• Infantry +1 armor\n• Wagenburg Tactics (+10%)"
        ),
        effect(bonus, "Infantry class", "Melee armour", "", "+1", **teutons),
        effect(
            tactics, "Hand Cannoneer", "Movement Speed", f"{TIMES}1.15", f"{TIMES}1.1", **teutons
        ),
        effect(shields, "Kamayuk", "Pierce armour", "", "+1", **teutons),
    ]

    result = notes(catalog, *changes)

    # Fabric Shields isn't in the description: it stays.
    assert lines(result) == [
        "Barracks units → Infantry +1 armor",
        "New: Wagenburg Tactics (+10%)",
        "Fabric Shields now affects Kamayuk.",
    ]
    assert result.closing is not None and result.closing.startswith("2 more changes")


def _tech_cost_effect(owner: Entity, target: str, old: str, new: str, **overrides: Any) -> Change:
    """A bonus setting a tech's food cost, as `diff.effects` writes it."""
    sentence = Message("effect.tech_resource_cost", {"tech": target, "resource": "Food"})
    return effect(owner, "", "", old, new, field=sentence, **overrides)


def test_an_effect_on_a_techs_cost_keeps_its_numbers(catalog: Catalog) -> None:
    # "Incas no longer affects Team bonus: …" read as if the Incas lost their team bonus.
    incas = Entity("civ", "Inca", "Incas")
    owned: dict[str, Any] = {"scope": Scope("some", ("Franks",)), "civ": "Franks"}
    change = _tech_cost_effect(incas, "Team bonus: Start w/ Llama", "=0", "", **owned)

    assert lines(notes(catalog, change)) == [
        "Incas: Team bonus: Start w/ Llama food cost removed (was 0)."
    ]


def test_a_free_tech_effect_gone_with_the_techs_cost_says_nothing(catalog: Catalog) -> None:
    # Incas, Berbers and Italians on 101.103.54800.0: a tech cost 1 food and a civ's effect made
    # it free; the patch dropped both, so the civ still gets it for nothing.
    llama = tech("Team bonus: Start w/ Llama", "730")
    incas = Entity("civ", "Inca", "Incas")
    owned: dict[str, Any] = {"scope": Scope("some", ("Franks",)), "civ": "Franks"}
    changes = [
        cost(llama, "food", "1", "", category="techs"),
        _tech_cost_effect(incas, "Team bonus: Start w/ Llama", "=0", "", **owned),
    ]

    result = notes(catalog, *changes)

    assert lines(result) == []
    # The tech's own cost is left to the detailed changes: no other civ is known not to pay it.
    assert result.closing is not None and result.closing.startswith("1 more change")


def test_a_tech_cost_effect_with_no_matching_cost_change_stays(catalog: Catalog) -> None:
    llama = tech("Team bonus: Start w/ Llama", "730")
    incas = Entity("civ", "Inca", "Incas")
    owned: dict[str, Any] = {"scope": Scope("some", ("Franks",)), "civ": "Franks"}
    changes = [
        cost(llama, "gold", "1", "", category="techs"),  # another resource
        _tech_cost_effect(incas, "Team bonus: Start w/ Llama", "=0", "", **owned),
    ]

    assert lines(notes(catalog, *changes)) == [
        "Team bonus: Start w/ Llama research cost in gold removed (was 1).",
        "Incas: Team bonus: Start w/ Llama food cost removed (was 0).",
    ]

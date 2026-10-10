# SPDX-License-Identifier: GPL-3.0-or-later
"""Effect commands as sentences (diff-rules.md, Effects; O-5 layer 2)."""

from support.snapshots import make_snapshot

from patch_scout.diff import compare
from patch_scout.diff.effects import TIMES, Lookup, Sentence, describe
from patch_scout.diff.model import Change, Message
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.i18n.catalog import load_catalog
from patch_scout.snapshot import JsonValue, Snapshot

CONSTANTS: JsonValue = {
    "Effect Constants": [
        ["cSetAttribute", 0],
        ["cModResource", 1],
        ["cEnableObject", 2],
        ["cUpgradeUnit", 3],
        ["cAddAttribute", 4],
        ["cMulAttribute", 5],
        ["cMulResource", 6],
        ["cSpawnUnit", 7],
        ["cAddTechCost", 101],
        ["cDisableTech", 102],
        ["cModTechTime", 103],
    ],
    "Tech Effect Constants": [
        ["cHitpoints", 0],
        ["cLineOfSight", 1],
        ["cArmor", 8],
        ["cAttack", 9],
        ["cTrainTime", 101],
    ],
    "Damage Classes": [["cDamageClassPierce", 3], ["cDamageClassMelee", 4]],
    "Object Classes": [["cCavalryClass", 912]],
    "Attributes": [
        ["cAttributeFood", 0],
        ["cAttributeGold", 3],
        ["cAttributeEffectFunctionNumber", 33],
    ],
}
UNITS = {4: "Archer", 24: "Crossbowman", 38: "Knight"}
TECHS = {199: "Fletching"}
SCRIPTS = {56: "Effect of Atheism for Huns"}
LOOKUP = Lookup(
    unit=lambda unit_id: UNITS.get(unit_id, f"#{unit_id}"),
    tech=lambda tech_id: TECHS.get(tech_id, f"#{tech_id}"),
    vocabulary=Vocabulary(make_snapshot(scripts={"constants": CONSTANTS})),
    script=SCRIPTS.get,
)
CATALOG = load_catalog("en")


def _command(type_: int, a: int = -1, b: int = -1, c: int = -1, d: float = 0.0) -> JsonValue:
    return {"type": type_, "a": a, "b": b, "c": c, "d": d}


def _read(sentence: Sentence | None) -> tuple[str, str | None]:
    assert sentence is not None
    return CATALOG.message(sentence.label.key, sentence.label.args), sentence.value


def test_adding_to_an_attribute_names_the_unit_and_the_attribute() -> None:
    assert _read(describe(_command(4, a=4, c=1, d=1.0), LOOKUP)) == (
        "Archer: Line Of Sight",
        "+1",
    )


def test_attack_and_armour_unpack_the_class_from_the_value() -> None:
    assert _read(describe(_command(4, a=4, c=9, d=3 * 256 + 1), LOOKUP)) == (
        "Archer: Attack vs Pierce",
        "+1",
    )
    assert _read(describe(_command(0, a=38, c=8, d=4 * 256 + 2), LOOKUP)) == (
        "Knight: Armour vs Melee",
        "=2",
    )


def test_a_negative_packed_value_stays_raw() -> None:
    assert describe(_command(4, a=4, c=8, d=-1025.0), LOOKUP) is None


def test_multiplying_targets_a_class_when_no_unit_is_given() -> None:
    assert _read(describe(_command(5, b=12, c=0, d=1.2), LOOKUP)) == (
        "Cavalry class: Hitpoints",
        "\N{MULTIPLICATION SIGN}1.2",
    )


def test_resources_are_set_added_or_multiplied() -> None:
    assert _read(describe(_command(1, a=0, b=1, d=-50.0), LOOKUP)) == ("Food", "-50")
    assert _read(describe(_command(1, a=3, b=0, d=100.0), LOOKUP)) == ("Gold", "=100")
    assert _read(describe(_command(6, a=0, d=1.1), LOOKUP)) == (
        "Food",
        "\N{MULTIPLICATION SIGN}1.1",
    )


def test_enabling_upgrading_and_disabling_say_it_all_in_words() -> None:
    assert _read(describe(_command(2, a=24, b=1), LOOKUP)) == ("Enables Crossbowman", None)
    assert _read(describe(_command(2, a=24, b=0), LOOKUP)) == ("Disables Crossbowman", None)
    assert _read(describe(_command(3, a=4, b=24), LOOKUP)) == (
        "Upgrades Archer to Crossbowman",
        None,
    )
    assert _read(describe(_command(102, d=199.0), LOOKUP)) == ("Disables Fletching", None)


def test_setting_the_effect_function_number_runs_a_scripted_effect() -> None:
    assert _read(describe(_command(1, a=33, b=0, d=56.0), LOOKUP)) == (
        "Runs the scripted effect: Effect of Atheism for Huns",
        None,
    )
    assert _read(describe(_command(1, a=33, b=0, d=99.0), LOOKUP)) == (
        "Runs the scripted effect: #99",
        None,
    )


def test_script_titles_come_from_the_effects_file() -> None:
    from patch_scout.diff.effects import script_titles

    text = "// 55 - Effect of Flemish Revolution\nvoid x() {}\n// 56 - Atheism\n// 56 - Again\n"
    assert script_titles(text) == {55: "Effect of Flemish Revolution", 56: "Atheism"}


def test_types_without_a_template_or_a_name_stay_raw() -> None:
    assert describe(_command(7, a=4, b=1), LOOKUP) is None  # named, but no template yet
    assert describe(_command(255), LOOKUP) is None  # not named in Constants.xs
    assert describe(_command(4, a=4, c=44, d=1.0), LOOKUP) is None  # attribute not named
    assert describe(_command(4, c=0, d=1.0), LOOKUP) is None  # no unit and no class


def test_a_tech_cost_is_set_or_multiplied() -> None:
    """The modes come from bonuses whose names say what they do (101.103.54800.0).

    Italians: "Age up 15% cheaper" multiplies every resource (b = -1) by 0.85 (c = 2). "Free
    Careening, Dry Dock" sets food and gold (b = 0, 3) to 0 (c = 0).
    """
    assert _read(describe(_command(101, a=199, b=-1, c=2, d=0.85), LOOKUP)) == (
        "Fletching: Cost",
        f"{TIMES}0.85",
    )
    assert _read(describe(_command(101, a=199, b=3, c=0, d=0.0), LOOKUP)) == (
        "Fletching: Gold cost",
        "=0",
    )


def test_a_research_time_is_set_or_multiplied() -> None:
    assert _read(describe(_command(103, a=199, b=-1, c=2, d=0.75), LOOKUP)) == (
        "Fletching: Research time",
        f"{TIMES}0.75",
    )


def test_tech_cost_and_time_modes_not_verified_stay_raw() -> None:
    assert describe(_command(101, a=199, b=0, c=1, d=10.0), LOOKUP) is None  # add: unverified
    assert describe(_command(101, a=199, b=0, c=-1, d=750.0), LOOKUP) is None
    assert describe(_command(101, a=199, b=507, c=0, d=17.0), LOOKUP) is None  # not a cost
    assert describe(_command(103, a=199, b=3, c=0, d=15.0), LOOKUP) is None  # b unexplained


def test_a_type_is_only_trusted_when_the_snapshot_names_it() -> None:
    unnamed = Lookup(
        unit=LOOKUP.unit,
        tech=LOOKUP.tech,
        vocabulary=Vocabulary(make_snapshot()),
        script=SCRIPTS.get,
    )
    assert describe(_command(4, a=4, c=1, d=1.0), unnamed) is None


def test_sentences_carry_their_parts_as_messages() -> None:
    sentence = describe(_command(4, a=4, c=9, d=3 * 256 + 1), LOOKUP)
    assert sentence is not None
    assert sentence.label == Message(
        "effect.attribute",
        {"target": "Archer", "attribute": {"key": "field.attacks", "args": {"class": "Pierce"}}},
    )


# --- in the comparison ------------------------------------------------------------------------


def _snapshot(commands: list[JsonValue]) -> Snapshot:
    tech: JsonValue = {
        "name": "Bodkin Arrow",
        "civ": -1,
        "language_dll_name": 7200,
        "effect_id": 5,
        "required_tech_count": 1,
        "required_techs": [],
        "research_locations": [],
        "resource_costs": [],
        "repeatable": 0,
        "type": 0,
    }
    archer: JsonValue = {"base": {"language_dll_name": 5004}, "overrides": {}}
    return make_snapshot(
        civs=[],
        tech_trees={},
        strings={"tables": {"en": {"5004": "Archer", "7200": "Bodkin Arrow"}}},
        flags={"stats_available": True},
        scripts={"constants": CONSTANTS},
        stats={
            "units": {"4": archer},
            "techs": {"200": tech},
            "effects": {"5": {"name": "Bodkin Arrow", "commands": commands}},
            "civ_dat": [],
        },
    )


def _changes(old: list[JsonValue], new: list[JsonValue]) -> list[Change]:
    return [
        change
        for change in compare(_snapshot(old), _snapshot(new)).changes
        if change.category == "techs"
    ]


def _line(change: Change) -> tuple[str, str | None, str | None]:
    assert change.field is not None
    return CATALOG.message(change.field.key, change.field.args), change.old, change.new


def test_a_changed_amount_reads_as_one_sentence_with_old_and_new_values() -> None:
    [change] = _changes([_command(4, a=4, c=9, d=769.0)], [_command(4, a=4, c=9, d=770.0)])
    assert _line(change) == ("Archer: Attack vs Pierce", "+1", "+2")


def test_an_added_command_has_only_a_new_value() -> None:
    [change] = _changes([], [_command(4, a=4, c=1, d=1.0)])
    assert _line(change) == ("Archer: Line Of Sight", "", "+1")


def test_a_command_without_a_value_says_whether_it_is_new_or_gone() -> None:
    [added] = _changes([], [_command(2, a=4, b=1)])
    [removed] = _changes([_command(2, a=4, b=1)], [])
    assert _line(added) == ("New: Enables Archer", "", "")
    assert _line(removed) == ("No longer: Enables Archer", "", "")


def test_a_command_that_changes_target_is_one_removed_and_one_added_sentence() -> None:
    changes = _changes([_command(4, a=4, c=1, d=1.0)], [_command(4, a=4, c=0, d=1.0)])
    assert [_line(change) for change in changes] == [
        ("Archer: Line Of Sight", "+1", ""),
        ("Archer: Hitpoints", "", "+1"),
    ]


def test_the_raw_command_stays_in_the_detail() -> None:
    [change] = _changes([], [_command(4, a=4, c=1, d=1.0)])
    assert change.detail is not None
    detail = CATALOG.message(change.detail.key, change.detail.args)
    assert detail == "Bodkin Arrow, command 0: type 4 a=4 b=-1 c=1 d=1"


def test_a_command_with_no_template_stays_raw() -> None:
    [change] = _changes([], [_command(255)])
    assert _line(change) == ("Effect", "", "type 255 a=-1 b=-1 c=-1 d=0")


def test_a_change_in_a_slot_the_sentence_ignores_stays_raw() -> None:
    [change] = _changes([_command(6, a=0, b=-1, d=1.5)], [_command(6, a=0, b=0, d=1.5)])
    assert change.field == Message("field.tech_effect")


def test_attributes_whose_value_packing_is_unverified_stay_raw() -> None:
    lookup = Lookup(
        unit=LOOKUP.unit,
        tech=LOOKUP.tech,
        script=SCRIPTS.get,
        vocabulary=Vocabulary(
            make_snapshot(
                scripts={
                    "constants": {
                        "Effect Constants": [["cAddAttribute", 4]],
                        "Tech Effect Constants": [["cResourceCost", 100], ["cAddArmorType", 160]],
                    }
                }
            )
        ),
    )
    assert describe(_command(4, a=4, c=100, d=769.0), lookup) is None
    assert describe(_command(4, a=4, c=160, d=769.0), lookup) is None


def test_attack_is_unpacked_by_its_xs_name_not_its_number() -> None:
    moved = Lookup(
        unit=LOOKUP.unit,
        tech=LOOKUP.tech,
        script=SCRIPTS.get,
        vocabulary=Vocabulary(
            make_snapshot(
                scripts={
                    "constants": {
                        "Effect Constants": [["cAddAttribute", 4]],
                        "Tech Effect Constants": [["cSomethingElse", 9]],
                    }
                }
            )
        ),
    )
    assert _read(describe(_command(4, a=4, c=9, d=769.0), moved)) == (
        "Archer: Something Else",
        "+769",
    )

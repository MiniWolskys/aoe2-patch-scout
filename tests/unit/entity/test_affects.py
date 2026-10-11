# SPDX-License-Identifier: GPL-3.0-or-later
"""Which effect commands affect a unit, a building or a tech (diff-rules.md, "What affects")."""

from support.snapshots import make_snapshot

from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.entity.affects import Target, affects, script_number
from patch_scout.snapshot import JsonValue

CONSTANTS: JsonValue = {
    "Effect Constants": [
        ["cSetAttribute", 0],
        ["cModResource", 1],
        ["cEnableObject", 2],
        ["cUpgradeUnit", 3],
        ["cAddAttribute", 4],
        ["cMulAttribute", 5],
        ["cMulResource", 6],
        ["cAddTechCost", 101],
        ["cDisableTech", 102],
        ["cModTechTime", 103],
    ],
    "Attributes": [["cAttributeFood", 0], ["cAttributeEffectFunctionNumber", 33]],
}
VOCABULARY = Vocabulary(make_snapshot(scripts={"constants": CONSTANTS}))
MILITIA = Target("unit", 74, unit_class=6)
SCALE_MAIL = Target("tech", 74)


def _command(type_: int, a: int = -1, b: int = -1, c: int = -1, d: float = 0.0) -> JsonValue:
    return {"type": type_, "a": a, "b": b, "c": c, "d": d}


def test_an_attribute_command_on_the_unit_affects_it() -> None:
    for kind in (0, 4, 5):
        assert affects(_command(kind, a=74, c=0, d=1.0), MILITIA, VOCABULARY)
    assert not affects(_command(4, a=75, c=0, d=1.0), MILITIA, VOCABULARY)


def test_an_attribute_command_on_the_units_class_affects_it() -> None:
    assert affects(_command(4, a=-1, b=6, c=9, d=1025.0), MILITIA, VOCABULARY)
    assert not affects(_command(4, a=-1, b=12, c=9, d=1025.0), MILITIA, VOCABULARY)
    # A command naming a unit is about that unit only, whatever its class slot says.
    assert not affects(_command(4, a=75, b=6, c=9, d=1025.0), MILITIA, VOCABULARY)


def test_enabling_or_upgrading_the_unit_affects_it() -> None:
    assert affects(_command(2, a=74, b=1), MILITIA, VOCABULARY)
    assert affects(_command(3, a=74, b=75), MILITIA, VOCABULARY)
    assert affects(_command(3, a=4, b=74), MILITIA, VOCABULARY)
    assert not affects(_command(3, a=4, b=24), MILITIA, VOCABULARY)
    # An age-up "upgrades" the Town Center to itself, which only changes its look.
    assert not affects(_command(3, a=74, b=74), MILITIA, VOCABULARY)


def test_a_tech_cost_command_is_about_a_tech_even_when_a_unit_has_its_number() -> None:
    # The Bulgarians' tech tree effect halves the cost of tech 74, Scale Mail Armor, not the
    # Militia, unit 74 (101.103.54800.0).
    command = _command(101, a=74, b=0, c=2, d=0.5)
    assert not affects(command, MILITIA, VOCABULARY)
    assert affects(command, SCALE_MAIL, VOCABULARY)
    assert affects(_command(103, a=74, b=-1, c=0, d=0.0), SCALE_MAIL, VOCABULARY)


def test_an_attribute_command_is_never_about_a_tech() -> None:
    assert not affects(_command(4, a=74, c=0, d=1.0), SCALE_MAIL, VOCABULARY)


def test_disabling_a_tech_is_availability_not_an_effect_on_it() -> None:
    assert not affects(_command(102, d=74.0), SCALE_MAIL, VOCABULARY)


def test_a_command_type_the_constants_do_not_name_affects_nothing() -> None:
    assert not affects(_command(250, a=74), MILITIA, VOCABULARY)
    assert not affects("not a command", MILITIA, VOCABULARY)


def test_a_unit_whose_class_is_unknown_is_matched_by_its_number_only() -> None:
    unknown = Target("unit", 74)
    assert affects(_command(4, a=74, c=0, d=1.0), unknown, VOCABULARY)
    assert not affects(_command(4, a=-1, b=6, c=0, d=1.0), unknown, VOCABULARY)


def test_a_buildings_commands_are_matched_like_a_units() -> None:
    town_center = Target("building", 109, unit_class=3)
    assert affects(_command(5, a=109, c=106, d=0.5), town_center, VOCABULARY)


def test_a_command_that_runs_a_script_gives_the_function_number() -> None:
    assert script_number(_command(1, a=33, b=0, d=52.0), VOCABULARY) == 52
    assert script_number(_command(1, a=0, b=0, d=52.0), VOCABULARY) is None
    assert script_number(_command(1, a=33, b=1, d=52.0), VOCABULARY) is None
    assert script_number(_command(4, a=33, b=0, d=52.0), VOCABULARY) is None

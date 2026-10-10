# SPDX-License-Identifier: GPL-3.0-or-later
"""The game's tooltip template, parsed into styled lines (spec: Tooltip template)."""

from patch_scout.tree.tooltip import Run, parse

BREAK = r"\n"  # the game's line break in string files

ARCHER = (
    "Create <b>Archer<b> (<cost>)"
    + BREAK
    + "All-purpose Foot Archer."
    + BREAK
    + "<GREY><i>Upgrades: attack (Blacksmith).<i><DEFAULT>"
    + BREAK
    + "<hp> <attack> <armor> <piercearmor> <range>"
)


def test_the_archer_template_reads_as_four_lines() -> None:
    lines = parse(ARCHER)
    assert len(lines) == 4
    assert lines[0] == (
        Run("text", "Create "),
        Run("text", "Archer", bold=True),
        Run("text", " ("),
        Run("cost"),
        Run("text", ")"),
    )
    assert lines[1] == (Run("text", "All-purpose Foot Archer."),)
    assert lines[2] == (Run("text", "Upgrades: attack (Blacksmith).", italic=True, grey=True),)
    stats = [run.stat for run in lines[3] if run.kind == "stat"]
    assert stats == ["hp", "attack", "armor", "piercearmor", "range"]


def test_garrison_and_a_fixed_cost_are_read() -> None:
    [line] = parse("<garrison> <static_cost=Gold,200>")
    assert line[0] == Run("stat", stat="garrison")
    assert line[2] == Run("static_cost", resource="gold", amount=200)


def test_a_closing_bold_tag_also_ends_bold() -> None:
    [line] = parse("<b>Keep</b> rest")
    assert line == (Run("text", "Keep", bold=True), Run("text", " rest"))


def test_an_unknown_tag_stays_as_text() -> None:
    [line] = parse("Cost <spark> here")
    assert line == (Run("text", "Cost <spark> here"),)


def test_an_empty_template_has_no_lines() -> None:
    assert parse("") == []


def test_runs_serialise_for_the_page() -> None:
    assert Run("stat", stat="hp").to_json() == {
        "kind": "stat",
        "text": "",
        "bold": False,
        "italic": False,
        "grey": False,
        "stat": "hp",
        "resource": None,
        "amount": None,
    }

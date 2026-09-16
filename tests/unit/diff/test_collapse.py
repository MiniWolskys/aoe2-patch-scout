# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-civ collapsing (D-07, diff-rules.md)."""

from patch_scout.diff.collapse import collapse

CIVS = ("Aztecs", "Britons", "Franks", "Goths", "Persians")


def test_nothing_changed_gives_no_groups() -> None:
    assert collapse(CIVS, {}) == []


def test_the_same_change_everywhere_reads_as_all_civs() -> None:
    changed = dict.fromkeys(CIVS, (100, 110))
    groups = collapse(CIVS, changed)
    assert len(groups) == 1
    assert groups[0].scope.kind == "all"
    assert (groups[0].old, groups[0].new) == (100, 110)


def test_most_civs_but_not_all_reads_as_all_except() -> None:
    changed = {civ: (100, 110) for civ in CIVS if civ not in ("Franks", "Persians")}
    groups = collapse(CIVS, changed)
    assert groups[0].scope.kind == "all_except"
    assert groups[0].scope.civs == ("Franks", "Persians")


def test_a_few_civs_are_named() -> None:
    groups = collapse(CIVS, {"Franks": (120, 130)})
    assert groups[0].scope.kind == "some"
    assert groups[0].scope.civs == ("Franks",)


def test_the_except_form_is_used_only_when_it_is_shorter() -> None:
    """Two of five changed: naming the two beats naming the three exceptions."""
    changed = dict.fromkeys(("Aztecs", "Britons"), (1, 2))
    assert collapse(CIVS, changed)[0].scope.kind == "some"


def test_the_except_form_wins_when_there_are_fewer_exceptions() -> None:
    changed = dict.fromkeys(("Aztecs", "Britons", "Franks"), (1, 2))
    group = collapse(CIVS, changed)[0]
    assert group.scope.kind == "all_except"
    assert group.scope.civs == ("Goths", "Persians")


def test_several_value_pairs_give_one_group_each_largest_first() -> None:
    changed = {
        "Aztecs": (100, 110),
        "Britons": (100, 110),
        "Franks": (100, 120),
    }
    groups = collapse(CIVS, changed)
    assert [group.size for group in groups] == [2, 1]
    assert groups[0].scope.civs == ("Aztecs", "Britons")
    assert groups[1].scope.civs == ("Franks",)


def test_several_pairs_never_collapse_to_all_civs() -> None:
    changed = {civ: (100, 110 + index) for index, civ in enumerate(CIVS)}
    assert all(group.scope.kind == "some" for group in collapse(CIVS, changed))


def test_civs_are_listed_in_the_order_they_were_given() -> None:
    groups = collapse(("Zulu", "Aztecs"), {"Aztecs": (1, 2), "Zulu": (1, 2)})
    assert groups[0].scope.kind == "all"


def test_one_civ_in_scope_changing_reads_as_all_civs() -> None:
    groups = collapse(("Aztecs",), {"Aztecs": (1, 2)})
    assert groups[0].scope.kind == "all"

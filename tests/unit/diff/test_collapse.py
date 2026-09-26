# SPDX-License-Identifier: GPL-3.0-or-later
"""Per-civ collapsing (D-07, diff-rules.md)."""

from patch_scout.diff.collapse import collapse

CIVS = ("Aztecs", "Britons", "Franks", "Goths", "Persians")
# Twelve civs in the comparison, for the cases where an entity exists in only some of them.
EVERY = (*CIVS, "Celts", "Huns", "Incas", "Magyars", "Mayans", "Slavs", "Turks")


def test_nothing_changed_gives_no_groups() -> None:
    assert collapse(CIVS, {}, every=CIVS) == []


def test_the_same_change_everywhere_reads_as_all_civs() -> None:
    changed = dict.fromkeys(CIVS, (100, 110))
    groups = collapse(CIVS, changed, every=CIVS)
    assert len(groups) == 1
    assert groups[0].scope.kind == "all"
    assert (groups[0].old, groups[0].new) == (100, 110)


def test_most_civs_but_not_all_reads_as_all_except() -> None:
    changed = {civ: (100, 110) for civ in CIVS if civ not in ("Franks", "Persians")}
    groups = collapse(CIVS, changed, every=CIVS)
    assert groups[0].scope.kind == "all_except"
    assert groups[0].scope.civs == ("Franks", "Persians")


def test_a_few_civs_are_named() -> None:
    groups = collapse(CIVS, {"Franks": (120, 130)}, every=CIVS)
    assert groups[0].scope.kind == "some"
    assert groups[0].scope.civs == ("Franks",)


def test_the_except_form_is_used_only_when_it_is_shorter() -> None:
    """Two of five changed: naming the two beats naming the three exceptions."""
    changed = dict.fromkeys(("Aztecs", "Britons"), (1, 2))
    assert collapse(CIVS, changed, every=CIVS)[0].scope.kind == "some"


def test_the_except_form_wins_when_there_are_fewer_exceptions() -> None:
    changed = dict.fromkeys(("Aztecs", "Britons", "Franks"), (1, 2))
    group = collapse(CIVS, changed, every=CIVS)[0]
    assert group.scope.kind == "all_except"
    assert group.scope.civs == ("Goths", "Persians")


def test_several_value_pairs_give_one_group_each_largest_first() -> None:
    changed = {
        "Aztecs": (100, 110),
        "Britons": (100, 110),
        "Franks": (100, 120),
    }
    groups = collapse(CIVS, changed, every=CIVS)
    assert [group.size for group in groups] == [2, 1]
    assert groups[0].scope.civs == ("Aztecs", "Britons")
    assert groups[1].scope.civs == ("Franks",)


def test_several_pairs_never_collapse_to_all_civs() -> None:
    changed = {civ: (100, 110 + index) for index, civ in enumerate(CIVS)}
    assert all(group.scope.kind == "some" for group in collapse(CIVS, changed, every=CIVS))


def test_civs_are_listed_in_the_order_they_were_given() -> None:
    groups = collapse(
        ("Zulu", "Aztecs"), {"Aztecs": (1, 2), "Zulu": (1, 2)}, every=("Zulu", "Aztecs")
    )
    assert groups[0].scope.kind == "all"


# --- entities that only some civs have ---------------------------------------------------------


def test_one_civ_owning_the_entity_is_named_not_called_all_civs() -> None:
    """Regression: a Franks-only node removed read "(all civilizations)" on the first real patch."""
    groups = collapse(("Franks",), {"Franks": (1, 2)}, every=EVERY)
    assert groups[0].scope.kind == "some"
    assert groups[0].scope.civs == ("Franks",)


def test_up_to_eight_owners_changing_are_named() -> None:
    owners = EVERY[:8]
    groups = collapse(owners, dict.fromkeys(owners, (1, 2)), every=EVERY)
    assert groups[0].scope.kind == "some"
    assert groups[0].scope.civs == owners


def test_more_than_eight_owners_changing_read_as_all_that_have_it() -> None:
    owners = EVERY[:10]
    groups = collapse(owners, dict.fromkeys(owners, (1, 2)), every=EVERY)
    assert groups[0].scope.kind == "having"
    assert groups[0].scope.count == 10
    assert groups[0].scope.civs == ()


def test_most_owners_changing_read_as_all_that_have_it_except() -> None:
    owners = EVERY[:10]
    changed = {civ: (1, 2) for civ in owners if civ != "Goths"}
    groups = collapse(owners, changed, every=EVERY)
    assert groups[0].scope.kind == "having_except"
    assert groups[0].scope.count == 10
    assert groups[0].scope.civs == ("Goths",)


def test_a_few_owners_changing_among_many_are_named() -> None:
    owners = EVERY[:10]
    groups = collapse(owners, {"Huns": (1, 2)}, every=EVERY)
    assert groups[0].scope.kind == "some"
    assert groups[0].scope.civs == ("Huns",)

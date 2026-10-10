# SPDX-License-Identifier: GPL-3.0-or-later
"""Formatting and word diffs (diff-rules.md, "Values and formatting")."""

from patch_scout.diff.model import WordDiff
from patch_scout.diff.values import (
    at_path,
    display,
    pair,
    unknown_id,
    walk,
    whitespace_only,
    words,
)


def test_a_whole_number_float_loses_its_decimal_point() -> None:
    assert display(100.0) == "100"


def test_a_float_keeps_the_decimals_it_needs() -> None:
    assert display(1.2) == "1.2"
    assert display(0.9599999785423279) == "0.96"


def test_both_sides_get_enough_decimals_to_differ() -> None:
    assert pair(1.2, 1.15) == ("1.20", "1.15")


def test_a_pair_that_rounds_the_same_still_reads_apart() -> None:
    old, new = pair(2.04, 1.96)
    assert old != new


def test_integers_and_strings_are_shown_as_they_are() -> None:
    assert pair(100, 110) == ("100", "110")
    assert display("NotAvailable") == "NotAvailable"


def test_nothing_shows_as_an_empty_string() -> None:
    assert display(None) == ""


def test_booleans_read_as_words() -> None:
    assert (display(True), display(False)) == ("true", "false")


def test_a_list_is_joined() -> None:
    assert display([1, 2, 3]) == "1, 2, 3"


def test_values_that_are_not_numbers_are_named() -> None:
    assert display(float("nan")) == "NaN"
    assert display(float("inf")) == "infinity"
    assert display(float("-inf")) == "-infinity"


def test_an_id_without_a_name_is_shown_with_a_hash() -> None:
    assert unknown_id(42) == "#42"


def test_a_word_diff_marks_what_changed() -> None:
    runs = words("Villagers work faster", "Villagers work much faster")
    assert [(run.kind, run.text) for run in runs if run.kind != "same"] == [("added", "much ")]


def test_a_word_diff_keeps_the_text_that_stayed() -> None:
    runs = words("a b c", "a x c")
    assert "".join(run.text for run in runs if run.kind in ("same", "removed")) == "a b c"
    assert "".join(run.text for run in runs if run.kind in ("same", "added")) == "a x c"


def test_a_spacing_change_is_recognised() -> None:
    assert whitespace_only("a  b", "a b") is True
    assert whitespace_only("a b", "a c") is False
    assert whitespace_only("a b", "a b") is False


def test_a_dotted_path_reaches_a_nested_value() -> None:
    assert at_path({"type_50": {"max_range": 4.0}}, "type_50.max_range") == 4.0


def test_a_dotted_path_that_leads_nowhere_gives_nothing() -> None:
    assert at_path({"a": 1}, "a.b") is None
    assert at_path(None, "a") is None


def test_walking_a_record_lists_its_leaves() -> None:
    leaves = dict(walk({"b": 1, "a": {"c": [2]}}))
    assert leaves == {"a.c": [2], "b": 1}


def _sides(runs: tuple[WordDiff, ...]) -> tuple[str, str]:
    old = "".join(run.text for run in runs if run.kind in ("same", "removed"))
    new = "".join(run.text for run in runs if run.kind in ("same", "added"))
    return old, new


def test_the_game_line_breaks_become_lines() -> None:
    r"""Civ bonus texts are one string with `\n` markers; they read as a list (Vietnamese)."""
    runs = words(r"Archer civilization\n• Conscription free", r"Archer civilization\n• Free")
    assert _sides(runs) == (
        "Archer civilization\n• Conscription free",
        "Archer civilization\n• Free",
    )


def test_the_game_bold_markers_are_dropped() -> None:
    runs = words(r"<b>Unique Units:<b>\nRattan Archer", r"<b>Unique Units:</b>\nKonnik")
    assert _sides(runs) == ("Unique Units:\nRattan Archer", "Unique Units:\nKonnik")


def test_a_line_added_between_two_others_is_one_added_line() -> None:
    runs = words(r"• a\n• c", r"• a\n• b\n• c")
    assert _sides(runs) == ("• a\n• c", "• a\n• b\n• c")
    assert [run.text.strip() for run in runs if run.kind != "same"] == ["• b"]
    assert [run.kind for run in runs if run.kind != "same"] == ["added"]


def test_a_line_that_changed_a_little_marks_only_the_words() -> None:
    runs = words(r"• Archers +20% HP\n• x", r"• Archers +30% HP\n• x")
    assert [(run.kind, run.text) for run in runs if run.kind != "same"] == [
        ("removed", "+20%"),
        ("added", "+30%"),
    ]


def test_a_line_replaced_by_a_different_one_reads_as_removed_then_added() -> None:
    runs = words(r"• Cavalry +20% HP\n• x", r"• Monks heal faster\n• x")
    assert [(run.kind, run.text) for run in runs if run.kind != "same"] == [
        ("removed", "• Cavalry +20% HP"),
        ("added", "• Monks heal faster"),
    ]

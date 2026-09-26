# SPDX-License-Identifier: GPL-3.0-or-later
"""Formatting and word diffs (diff-rules.md, "Values and formatting")."""

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

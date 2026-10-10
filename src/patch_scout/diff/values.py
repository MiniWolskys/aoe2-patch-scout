# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare and display raw values the way diff-rules.md asks for.

Comparison is exact on what the snapshot stores. Display uses the shortest decimal form that
keeps the value faithful and still tells old and new apart, so a change never reads `2 -> 2`.
"""

import difflib
import re
from collections.abc import Iterator, Sequence
from typing import Final

from patch_scout.diff.model import WordDiff
from patch_scout.snapshot import JsonValue

# The game's floats come from 32-bit values, so six decimals is always enough to be faithful.
MAX_DECIMALS: Final = 6
_WORDS: Final = re.compile(r"\s+|[^\s]+")
# The game's markup in string files (game-files.md §5): a two-character line break, and bold.
_LINE_BREAK: Final = r"\n"
_BOLD: Final = re.compile(r"</?b>", re.IGNORECASE)


def display(value: JsonValue) -> str:
    """Format one value on its own."""
    if isinstance(value, float):
        return _format(value, _decimals(value))
    return _plain(value)


def pair(old: JsonValue, new: JsonValue) -> tuple[str, str]:
    """Format both sides of a change, with enough decimals to tell them apart."""
    if isinstance(old, float) and isinstance(new, float):
        decimals = max(_decimals(old), _decimals(new), _distinguishing(old, new))
        return _format(old, decimals), _format(new, decimals)
    return display(old), display(new)


def _plain(value: JsonValue) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, list):
        return ", ".join(display(item) for item in value)
    return str(value)


def _decimals(value: float) -> int:
    """The fewest decimals that still show the value faithfully."""
    if not _finite(value):
        return 0
    faithful = round(value, MAX_DECIMALS)
    for decimals in range(MAX_DECIMALS):
        if round(value, decimals) == faithful:
            return decimals
    return MAX_DECIMALS


def _distinguishing(old: float, new: float) -> int:
    """The fewest decimals at which two different values stop looking the same."""
    if old == new or not _finite(old) or not _finite(new):
        return 0
    for decimals in range(MAX_DECIMALS):
        if f"{old:.{decimals}f}" != f"{new:.{decimals}f}":
            return decimals
    return MAX_DECIMALS


def _format(value: float, decimals: int) -> str:
    if value != value:  # not a number
        return "NaN"
    if value in (float("inf"), float("-inf")):
        return "infinity" if value > 0 else "-infinity"
    return f"{value:.{decimals}f}"


def _finite(value: float) -> bool:
    return value == value and value not in (float("inf"), float("-inf"))


def unknown_id(identifier: JsonValue) -> str:
    """How an ID with no name is shown (diff-rules.md, "Values and formatting")."""
    return f"#{identifier}"


def readable(text: str) -> str:
    r"""A game text as players read it: `\n` markers as line breaks, without `<b>` markers."""
    return _BOLD.sub("", text.replace(_LINE_BREAK, "\n"))


def words(old: str, new: str) -> tuple[WordDiff, ...]:
    """A diff of two game texts, line by line, then word by word inside a line that changed.

    Civ bonus texts are lists, one bonus per line: a bonus added between two others is one added
    line, not words scattered across the text (Saxons and Vietnamese on 101.103.54800.0).
    """
    old, new = readable(old), readable(new)
    if "\n" not in old and "\n" not in new:
        return _word_runs(old, new)
    old_lines, new_lines = old.split("\n"), new.split("\n")
    matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
    lines: list[tuple[WordDiff, ...]] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            lines += [(WordDiff("same", text),) for text in old_lines[i1:i2]]
            continue
        before, after = old_lines[i1:i2], new_lines[j1:j2]
        paired = min(len(before), len(after)) if tag == "replace" else 0
        for old_line, new_line in zip(before[:paired], after[:paired], strict=True):
            if _similar(old_line, new_line):
                lines.append(_word_runs(old_line, new_line))
            else:
                lines += [(WordDiff("removed", old_line),), (WordDiff("added", new_line),)]
        lines += [(WordDiff("removed", text),) for text in before[paired:]]
        lines += [(WordDiff("added", text),) for text in after[paired:]]
    # A line break belongs to the sides that have a line before and after it, so each side reads
    # back exactly as its own text.
    runs: list[WordDiff] = []
    started = {"old": False, "new": False}
    for line in lines:
        sides = {
            "old": any(run.kind != "added" for run in line),
            "new": any(run.kind != "removed" for run in line),
        }
        needs = {side for side, present in sides.items() if present and started[side]}
        if needs:
            _append(runs, _BREAK_KIND[frozenset(needs)], ["\n"])
        for side, present in sides.items():
            started[side] = started[side] or present
        for run in line:
            _append(runs, run.kind, [run.text])
    return tuple(runs)


_BREAK_KIND: Final = {
    frozenset({"old", "new"}): "same",
    frozenset({"old"}): "removed",
    frozenset({"new"}): "added",
}


def _similar(old: str, new: str) -> bool:
    """Whether two lines are the same line edited, rather than one replaced by another."""
    before, after = old.split(), new.split()
    return difflib.SequenceMatcher(a=before, b=after, autojunk=False).ratio() >= 0.5


def _word_runs(old: str, new: str) -> tuple[WordDiff, ...]:
    """A word-level diff of two texts, keeping the whitespace between words."""
    old_tokens = _tokens(old)
    new_tokens = _tokens(new)
    matcher = difflib.SequenceMatcher(a=old_tokens, b=new_tokens, autojunk=False)
    runs: list[WordDiff] = []
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag in ("equal", "delete", "replace"):
            _append(runs, "same" if tag == "equal" else "removed", old_tokens[i1:i2])
        if tag in ("insert", "replace"):
            _append(runs, "added", new_tokens[j1:j2])
    return tuple(runs)


def whitespace_only(old: str, new: str) -> bool:
    """Whether two texts differ only in their spacing (diff-rules.md, "Strings")."""
    return old != new and "".join(old.split()) == "".join(new.split())


def _tokens(text: str) -> list[str]:
    return _WORDS.findall(text)


def _append(runs: list[WordDiff], kind: str, tokens: Sequence[str]) -> None:
    text = "".join(tokens)
    if not text:
        return
    if runs and runs[-1].kind == kind:
        runs[-1] = WordDiff(runs[-1].kind, runs[-1].text + text)
        return
    runs.append(WordDiff(kind, text))  # type: ignore[arg-type]  # kind is one of the three


def walk(value: JsonValue, prefix: str = "") -> Iterator[tuple[str, JsonValue]]:
    """Every leaf of a nested record, as a dotted path and its value; lists are leaves."""
    if isinstance(value, dict):
        for key in sorted(value):
            yield from walk(value[key], f"{prefix}{key}.")
        return
    yield prefix.rstrip("."), value


def at_path(record: JsonValue, path: str) -> JsonValue:
    """Follow a dotted path into a record; None when any step is missing."""
    current = record
    for key in path.split("."):
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current

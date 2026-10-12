# SPDX-License-Identifier: GPL-3.0-or-later
"""Sentences before they are written: paired, merged, then turned into bullets (D-51).

A draft is one sentence about one subject, with the changes it says. Two passes make the notes
read like the official ones:

- **Pairing:** "Throwing Axeman" and "Elite Throwing Axeman" with the same fields become one
  sentence about "(Elite) Throwing Axeman". It is a contraction of the two names, so it holds
  whatever the upgrade line; it never guesses one.
- **Merging:** sentences that say the same thing about different subjects become one sentence
  naming them all: "Battering Ram, Capped Ram and Siege Ram line of sight increased from 3 → 5".
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from typing import Final, Literal

from patch_scout.diff.model import Change
from patch_scout.report.notes.model import Item
from patch_scout.report.notes.phrases import Also, Words

# "silent" says nothing: it holds changes that cancel out, such as an effect command removed and
# added back unchanged, so they count as said.
type Form = Literal[
    "stats", "effect", "gain", "lose", "new", "affects", "no_longer", "line", "silent"
]

# Forms whose subjects pair as "(Elite) X", and forms whose sentences merge across subjects.
# Gaining or losing access is one line per item in the official notes: paired, never merged.
PAIRED: Final = frozenset({"stats", "gain", "lose", "new"})
MERGED: Final = frozenset({"stats", "effect", "affects", "no_longer"})


@dataclass(frozen=True, slots=True)
class Field:
    """One field's change in a sentence, with a pair's second values when they differ."""

    label: str
    old: str
    new: str
    also: Also | None = None


@dataclass(frozen=True, slots=True)
class Child:
    """A bullet under a sentence: "Hit points: 45", or a ready line."""

    label: str
    value: str = ""
    # A pair's second value when it differs: "Hit points: 45; Heavy: 55".
    other: tuple[str, str] | None = None


@dataclass(slots=True)
class Draft:
    """One sentence to be: its form, its subjects and what it says about them."""

    form: Form
    # Where it goes in a civ's block (civ_rank), and the subject's own name.
    rank: int
    subjects: list[str]
    used: list[Change]
    # The entity the sentence is about, to match a NEW item with its "Gain access".
    entity: tuple[str, str] | None = None
    scope: str = ""
    fields: list[Field] = field(default_factory=list)
    children: list[Child] = field(default_factory=list)
    # A "line" draft's sentence, written already; for "affects" and "no_longer", what every target
    # gets when they all get the same.
    text: str = ""
    # An "affects" draft's targets, after pairing: what the sentence names.
    targets: list[str] = field(default_factory=list)


def pair(drafts: list[Draft], words: Words) -> list[Draft]:
    """Join "X" and "P X" drafts that say the same fields into one about "(P) X"."""
    by_name: dict[tuple[Form, int, str], int] = {}
    for position, draft in enumerate(drafts):
        if draft.form in PAIRED and len(draft.subjects) == 1:
            by_name.setdefault((draft.form, draft.rank, draft.subjects[0]), position)
    gone: set[int] = set()
    joined: dict[int, Draft] = {}
    for position, draft in enumerate(drafts):
        if (
            draft.form not in PAIRED
            or len(draft.subjects) != 1
            or position in gone
            or position in joined
        ):
            continue
        prefix, _, base = draft.subjects[0].partition(" ")
        if not base or not prefix:
            continue
        found = by_name.get((draft.form, draft.rank, base))
        if found is None or found in gone or found in joined or found == position:
            continue
        first = drafts[found]
        if not _compatible(first, draft):
            continue
        joined[found] = _joined(first, draft, prefix, words)
        gone.add(position)
    return [
        joined.get(position, draft) for position, draft in enumerate(drafts) if position not in gone
    ]


def _compatible(first: Draft, second: Draft) -> bool:
    if first.scope != second.scope:
        return False
    if first.form == "stats":
        # The same fields, each changed the same way: a value added to one and removed from
        # the other can't share a clause.
        return [_shape(item) for item in first.fields] == [_shape(item) for item in second.fields]
    if first.form == "new":
        return [item.label for item in first.children] == [item.label for item in second.children]
    return True


def _shape(item: Field) -> tuple[str, bool, bool]:
    return item.label, bool(item.old), bool(item.new)


def _joined(first: Draft, second: Draft, prefix: str, words: Words) -> Draft:
    fields = [
        item
        if (item.old, item.new) == (other.old, other.new)
        else replace(item, also=Also(prefix, other.old, other.new))
        for item, other in zip(first.fields, second.fields, strict=True)
    ]
    children = [
        item if item.value == other.value else replace(item, other=(prefix, other.value))
        for item, other in zip(first.children, second.children, strict=False)
    ]
    return replace(
        first,
        subjects=[words.paired(prefix, first.subjects[0])],
        used=first.used + second.used,
        fields=fields,
        children=children if first.form == "new" else first.children,
    )


def merge(drafts: list[Draft], words: Words) -> list[Draft]:
    """One sentence for drafts that say the same about different subjects, at the first's place."""
    first_of: dict[tuple[object, ...], Draft] = {}
    kept: list[Draft] = []
    for draft in drafts:
        if draft.form not in MERGED:
            kept.append(draft)
            continue
        key = (draft.form, draft.rank, draft.scope, _body(draft, words))
        earlier = first_of.get(key)
        if earlier is None:
            first_of[key] = draft
            kept.append(draft)
            continue
        earlier.subjects.extend(name for name in draft.subjects if name not in earlier.subjects)
        earlier.used.extend(draft.used)
    return kept


def _body(draft: Draft, words: Words) -> tuple[object, ...]:
    """What a sentence says, without its subjects."""
    return (
        tuple(words.clause(item.label, item.old, item.new, item.also) for item in draft.fields),
        tuple(draft.targets),
        tuple(child_text(child, words) for child in draft.children),
        draft.text,
    )


def child_text(child: Child, words: Words) -> str:
    """A bullet under a sentence."""
    if not child.value:
        return child.label
    if child.other is None:
        return words.text("notes.child", field=child.label, value=child.value)
    prefix, other = child.other
    return words.text(
        "notes.child_also", field=child.label, value=child.value, prefix=prefix, other=other
    )


def render(draft: Draft, words: Words) -> Item:
    """The draft as a bullet, in the reader's language."""
    subjects = words.listed(draft.subjects)
    children = tuple(Item(child_text(child, words)) for child in draft.children)
    if draft.form in ("stats", "effect"):
        clauses = words.text("notes.list_separator").join(
            words.clause(item.label, item.old, item.new, item.also) for item in draft.fields
        )
        key = "notes.stats" if draft.form == "stats" else "notes.effect_change"
        return Item(words.text(key, subjects=subjects, clauses=clauses, scope=draft.scope))
    if draft.form == "gain":
        return Item(words.text("notes.gain", subject=subjects, scope=draft.scope))
    if draft.form == "lose":
        return Item(words.text("notes.lose", subject=subjects, scope=draft.scope))
    if draft.form == "new":
        key = "notes.new" if children else "notes.new_bare"
        return Item(words.text(key, subject=subjects, scope=draft.scope), children)
    if draft.form in ("affects", "no_longer"):
        key = "notes.affects" if draft.form == "affects" else "notes.no_longer_affects"
        # Every target given the same: one line, with what they get ("…: +1 armour.").
        key += "_all" if draft.text else ""
        key += "_many" if len(draft.subjects) > 1 else ""
        targets = words.listed(draft.targets)
        text = words.text(
            key, subjects=subjects, targets=targets, parts=draft.text, scope=draft.scope
        )
        return Item(text, children)
    return Item(draft.text, children)


def ordered(drafts: Sequence[Draft]) -> list[Draft]:
    """A civ's sentences in the order of the official notes, each kind in its own order."""
    return sorted(drafts, key=lambda draft: draft.rank)

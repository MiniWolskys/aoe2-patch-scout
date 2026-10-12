# SPDX-License-Identifier: GPL-3.0-or-later
"""Sentences before they are written: paired, merged, then turned into bullets (D-51).

A draft is one sentence about one subject, with the changes it says. Two passes make the notes
read like the official ones:

- **Pairing:** "Throwing Axeman" and "Elite Throwing Axeman" with the same fields become one
  sentence about "(Elite) Throwing Axeman". It is a contraction of the two names, so it holds
  whatever the upgrade line; it never guesses one.
- **Merging:** sentences that say the same thing about different subjects become one sentence
  naming them all: "Battering Ram, Capped Ram and Siege Ram line of sight increased from 3 → 5".

Before both, **lines**: one field that changed differently for several units of a game unit line
becomes one sentence listing them, as the official notes do: "Militia line bonus vs Shock
Infantry increased: Man-at-Arms 2 → 3, Long Swordsman 6 → 8, …".
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import Final, Literal

from patch_scout.diff.model import Change
from patch_scout.report.notes.model import Item
from patch_scout.report.notes.phrases import Also, Words
from patch_scout.report.notes.values import direction, shown

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
    # A "line" draft's sentence, written already; for a new unit, where it is trained; for a new
    # tech, what it does.
    text: str = ""
    # An "affects" draft's targets, after pairing: what the sentence names.
    targets: list[str] = field(default_factory=list)
    # Said by an effect (a tech's or bonus's): a changed civ description may say it already.
    effect: bool = False


@dataclass(frozen=True, slots=True)
class LineSlot:
    """Where a unit sits in a game unit line: the line's name, and the unit's place in it."""

    line: str
    position: int


def by_line(drafts: list[Draft], lines: Mapping[str, LineSlot], words: Words) -> list[Draft]:
    """One sentence for a field that changed differently for several units of one line.

    The units' other fields stay in their own sentences. A field that changed alike for all of
    them is left to merging ("Battering Ram and Capped Ram line of sight …"), and two units that
    pair ("Hulk", "War Hulk") to pairing ("(War) Hulk … War 115 → 110").
    """
    groups: dict[tuple[str, int, str], list[tuple[int, int, int]]] = {}
    for at, draft in enumerate(drafts):
        if draft.form != "stats" or len(draft.subjects) != 1 or draft.entity is None:
            continue
        slot = lines.get(draft.entity[1]) if draft.entity[0] == "unit" else None
        if slot is None:
            continue
        for index, item in enumerate(draft.fields):
            if item.old and item.new:
                key = (slot.line, draft.rank, item.label)
                groups.setdefault(key, []).append((slot.position, at, index))
    taken: dict[int, set[int]] = {}
    sentences: list[Draft] = []
    for (line, rank, label), members in groups.items():
        members.sort()
        if not _worth_a_line([(drafts[at], index) for _, at, index in members]):
            continue
        parts: list[str] = []
        ways: set[str | None] = set()
        used: list[Change] = []
        for _, at, index in members:
            draft, item = drafts[at], drafts[at].fields[index]
            parts.append(
                words.text(
                    "notes.by_line.member",
                    unit=draft.subjects[0],
                    old=shown(item.old),
                    new=shown(item.new),
                    scope=draft.scope,
                )
            )
            ways.add(direction(item.old, item.new))
            used.append(draft.used[index])
            taken.setdefault(at, set()).add(index)
        way = next(iter(ways)) if len(ways) == 1 else None
        sentence = {"up": "notes.by_line.up", "down": "notes.by_line.down"}.get(
            way or "", "notes.by_line.changed"
        )
        name = words.text("notes.unit_line", unit=line)
        text = words.text(sentence, line=name, field=label, members=words.listed(parts))
        sentences.append(Draft("line", rank, [name], used, text=text))
    kept: list[Draft] = []
    for at, draft in enumerate(drafts):
        gone = taken.get(at)
        if not gone:
            kept.append(draft)
            continue
        fields = [item for index, item in enumerate(draft.fields) if index not in gone]
        if fields:
            used = [change for index, change in enumerate(draft.used) if index not in gone]
            kept.append(replace(draft, fields=fields, used=used))
    for line_sentence in sentences:
        _insert_by_name(kept, line_sentence)
    return kept


def _insert_by_name(drafts: list[Draft], sentence: Draft) -> None:
    """Put a line's sentence where its name puts it among the sentences of its rank, which are
    in name order: "Militia line" between "Long Swordsman" and "Onager"."""
    name = sentence.subjects[0].casefold()
    for position, draft in enumerate(drafts):
        if draft.rank == sentence.rank and draft.subjects[0].casefold() > name:
            drafts.insert(position, sentence)
            return
    after = [position for position, draft in enumerate(drafts) if draft.rank <= sentence.rank]
    drafts.insert(after[-1] + 1 if after else len(drafts), sentence)


def _worth_a_line(members: Sequence[tuple[Draft, int]]) -> bool:
    """Several units, not all changed alike, and not just a unit and its upgrade that pair."""
    subjects = [draft.subjects[0] for draft, _ in members]
    if len(set(subjects)) < 2 or len(subjects) != len(set(subjects)):
        return False
    values = {(draft.fields[index].old, draft.fields[index].new) for draft, index in members}
    if len(values) == 1:
        return False
    if len(subjects) == 2:
        first, second = sorted(subjects, key=len)
        if second.partition(" ")[2] == first:
            return False
    return True


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
        # Trained in the same place (a new unit), and the same bullets (a new tech).
        labels = [item.label for item in first.children]
        return first.text == second.text and labels == [item.label for item in second.children]
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
        if children:
            return Item(words.text("notes.new", subject=subjects, scope=draft.scope), children)
        if draft.text and draft.entity is not None and draft.entity[0] == "tech":
            # A new tech, with what it does.
            does = draft.text
            return Item(
                words.text("notes.new_does", subject=subjects, does=does, scope=draft.scope)
            )
        if draft.text:  # a new unit, with where it is trained
            where = draft.text
            return Item(
                words.text("notes.new_at", subject=subjects, where=where, scope=draft.scope)
            )
        return Item(words.text("notes.new_bare", subject=subjects, scope=draft.scope))
    if draft.form in ("affects", "no_longer"):
        key = "notes.affects" if draft.form == "affects" else "notes.no_longer_affects"
        key += "_many" if len(draft.subjects) > 1 else ""
        targets = words.listed(draft.targets)
        return Item(words.text(key, subjects=subjects, targets=targets, scope=draft.scope))
    return Item(draft.text, children)


def ordered(drafts: Sequence[Draft]) -> list[Draft]:
    """A civ's sentences in the order of the official notes, each kind in its own order."""
    return sorted(drafts, key=lambda draft: draft.rank)

# SPDX-License-Identifier: GPL-3.0-or-later
"""Write a comparison as patch notes, the way the official ones read (D-51, diff-rules.md).

The notes are a summary with a fixed meaning: the headline changes of named objects, outside
the low-priority categories, whatever the comparison's filters say. They only reword the change
set, never interpret it (rule 4): a change that can't be written as a clean sentence, such as a
raw effect command or one that shows an unknown ID, is left out and counted in the closing line.
"""

import difflib
import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field, replace
from typing import Final, Literal

from patch_scout.diff.model import CATEGORIES, Change, ChangeSet, CivRef, Entry, Message, Side
from patch_scout.i18n.catalog import Catalog
from patch_scout.report.notes import drafts as drafting
from patch_scout.report.notes.drafts import Child, Draft, Field
from patch_scout.report.notes.model import Group, Item, Notes, Section
from patch_scout.report.notes.phrases import Words
from patch_scout.report.notes.values import shown

# An ID the game gives no name: a sentence showing one says nothing to a reader.
_UNKNOWN_ID: Final = re.compile(r"#-?\d+")
# An effect command with no sentence template: the change is the raw command (O-5, layer 3).
_RAW_COMMAND: Final = "detail.effect_command"
# An effect command written as a sentence (O-5, layer 2).
_SENTENCE: Final = "detail.effect_command_raw"
# Fields whose values are bare IDs: "Made at" holds building IDs.
_ID_FIELDS: Final = frozenset({"field.building"})
# A new civ's tech tree, one line per building.
_TREE_FIELDS: Final = frozenset({"field.tech_tree_at", "field.tech_tree_buildings"})
# Notices the closing line replaces: the notes have no filters to turn on.
_FILTER_NOTICES: Final = frozenset({"levels_hidden", "unnamed_hidden"})
_NOT_AVAILABLE: Final = "NotAvailable"
_BULLET: Final = "\N{BULLET}"
_CHRONICLES: Final = "antiquity"

# Where each kind of sentence goes in a civ's block, as in the official notes: what the civ is,
# its description, its bonuses, then units, techs, what it gains, then what it loses. Techs known
# only by their developers' name come last: they are plumbing.
_RANKS: Final = {
    "civilizations": 0,
    "bonuses": 2,
    "unit_stats": 3,
    "techs": 4,
    "civ_availability": 5,
    "other_effects": 7,
}
_DESCRIPTION_RANK: Final = 1
_LOSS_RANK: Final = 6
_OTHER_RANK: Final = 8
_INTERNAL_RANK: Final = 9

type Access = Literal["gain", "lose"]


@dataclass(frozen=True, slots=True)
class _Context:
    words: Words
    messages: dict[str, str]
    civ_names: dict[str, str]
    # A unit's own name by ID, from the comparison's Unit stats: the tech tree's labels shorten
    # some ("H. Mounted Crossbowman"), which would keep "(Heavy) Mounted Crossbowman" from pairing.
    unit_names: dict[str, str]


def build(change_set: ChangeSet, catalog: Catalog) -> Notes:
    """The comparison as patch notes, every string in the catalog's language."""
    words = Words(catalog)
    title = words.text(
        "notes.title", old=_side(change_set.old, words), new=_side(change_set.new, words)
    )
    notices = tuple(
        words.message(notice.message)
        for notice in change_set.notices
        if notice.kind not in _FILTER_NOTICES
    )
    disclaimer = words.text("notes.disclaimer")
    if change_set.identical:
        return Notes(title, disclaimer, notices, (), None, words.text("notes.empty"))
    context = _Context(
        words=words,
        messages=catalog.messages(),
        civ_names={civ.internal_name: civ.name for civ in change_set.civs},
        unit_names={
            entry.entity.id: entry.entity.name
            for entry in change_set.entries
            if entry.category == "unit_stats" and entry.entity.kind == "unit"
        },
    )
    kept = [
        curated for entry in change_set.entries if (curated := _curated(entry, words)) is not None
    ]
    used: set[int] = set()
    sections = [
        section
        for section in (
            _general(kept, context, used),
            _civs(change_set.civs, kept, context, used, chronicles=False),
            _civs(change_set.civs, kept, context, used, chronicles=True),
        )
        if section is not None
    ]
    left_out = len({id(change) for change in change_set.changes} - used)
    closing = _closing(left_out, words)
    empty = None if sections else words.text("notes.empty")
    return Notes(title, disclaimer, notices, tuple(sections), closing, empty)


def _side(side: Side, words: Words) -> str:
    text = side.label
    if side.game_build and side.game_build not in side.label:
        text = words.text("notes.side", label=side.label, build=side.game_build)
    if side.prerelease:
        text = words.text("notes.prerelease", side=text)
    return text


def _closing(left_out: int, words: Words) -> str | None:
    if left_out == 0:
        return None
    if left_out == 1:
        return words.text("notes.closing_one")
    return words.text("notes.closing", count=left_out)


def _curated(entry: Entry, words: Words) -> Entry | None:
    """The entry with only what the notes can say; None when nothing is left."""
    if entry.low_priority or not entry.entity.named:
        return None
    changes = tuple(change for change in entry.changes if _sayable(change, words))
    if not changes:
        return None
    return entry if len(changes) == len(entry.changes) else replace(entry, changes=changes)


def _sayable(change: Change, words: Words) -> bool:
    if change.level != "headline":
        return False
    if change.detail is not None and change.detail.key == _RAW_COMMAND:
        return False
    if change.field is not None and change.field.key in _ID_FIELDS:
        return False
    label = words.message(change.field) if change.field is not None else ""
    return not any(_UNKNOWN_ID.search(part) for part in (label, change.old or "", change.new or ""))


# --- sections -----------------------------------------------------------------------------------


def _general(kept: Sequence[Entry], context: _Context, used: set[int]) -> Section | None:
    """Changes to every civ: one group per category, then the techs with no name in the game."""
    words = context.words
    overall = [entry for entry in kept if entry.civ is None]
    groups: list[Group] = []
    for category in CATEGORIES:
        mine = [
            entry for entry in overall if entry.category == category and not entry.entity.internal
        ]
        items = _items(mine, context, used, civ=None)
        if items:
            groups.append(Group(words.text(f"category.{category}"), items))
    internal = [entry for entry in overall if entry.entity.internal]
    items = _items(internal, context, used, civ=None)
    if items:
        groups.append(Group(words.text("notes.group.internal"), items))
    if not groups:
        return None
    return Section("general", words.text("notes.section.general"), tuple(groups))


def _civs(
    civs: Sequence[CivRef],
    kept: Sequence[Entry],
    context: _Context,
    used: set[int],
    *,
    chronicles: bool,
) -> Section | None:
    """One group per civ with notes: the base civs, or the Chronicles civs (D-38)."""
    groups: list[Group] = []
    for civ in civs:
        if (civ.era == _CHRONICLES) != chronicles:
            continue
        items = _items(
            (entry for entry in kept if entry.civ == civ.internal_name), context, used, civ
        )
        if items:
            groups.append(Group(civ.name, items, civ=civ.internal_name, icon=civ.icon))
    if not groups:
        return None
    kind: Literal["civs", "chronicles"] = "chronicles" if chronicles else "civs"
    return Section(kind, context.words.text(f"notes.section.{kind}"), tuple(groups))


def _items(
    entries: Iterable[Entry], context: _Context, used: set[int], civ: CivRef | None
) -> tuple[Item, ...]:
    """One group's bullets: drafted, de-duplicated, paired, merged, then ordered."""
    drafts: list[Draft] = []
    for entry in entries:
        drafts += _drafts(entry, context, civ)
    drafts = _without_gains_said_by_new(drafts)
    drafts = drafting.merge(drafting.pair(drafts, context.words), context.words)
    if civ is not None:
        drafts = drafting.ordered(drafts)
    for draft in drafts:
        used.update(id(change) for change in draft.used)
    return tuple(
        drafting.render(draft, context.words) for draft in drafts if draft.form != "silent"
    )


def _without_gains_said_by_new(drafts: list[Draft]) -> list[Draft]:
    """Leave out "Gain access to X" where a NEW item about X says it already."""
    news = {draft.entity: draft for draft in drafts if draft.form == "new" and draft.entity}
    kept: list[Draft] = []
    for draft in drafts:
        said = news.get(draft.entity) if draft.form == "gain" and draft.entity else None
        if said is None:
            kept.append(draft)
        else:
            said.used.extend(draft.used)
    return kept


# --- drafts per category ------------------------------------------------------------------------


def _drafts(entry: Entry, context: _Context, civ: CivRef | None) -> list[Draft]:
    rank = _INTERNAL_RANK if entry.entity.internal else _RANKS.get(entry.category, _OTHER_RANK)
    subject = _subject(entry, context)
    scope = _scope(entry, context)
    if entry.category == "civilizations":
        return _civilization(entry, context, subject, scope)
    if entry.category == "civ_availability":
        return _availability(entry, context, subject, scope, civ)
    if entry.category == "unit_stats":
        return _unit(entry, context, subject, scope)
    if entry.category == "techs":
        return _tech(entry, context, rank, subject, scope)
    # Civ bonuses and other effects: the description, effect sentences, and plain fields.
    drafts: list[Draft] = []
    rest: list[Change] = []
    for change in entry.changes:
        if change.field is not None and change.field.key == "field.civ_bonus_text":
            description = _description(change, context, subject)
            drafts.append(description or Draft("silent", rank, [subject], [change]))
        else:
            rest.append(change)
    drafts += _effects(
        [change for change in rest if _is_sentence(change)], context, rank, subject, scope
    )
    drafts += [
        _came_or_went(change, context, rank, subject, scope)
        for change in rest
        if change.field is None and change.kind in ("added", "removed")
    ]
    fields = [change for change in rest if change.field is not None and not _is_sentence(change)]
    if fields:
        drafts.append(_stats(fields, context, rank, subject, scope))
    return drafts


def _came_or_went(change: Change, context: _Context, rank: int, subject: str, scope: str) -> Draft:
    """Something added or removed as a whole, such as a function of Effects.xs."""
    key = "notes.added" if change.kind == "added" else "notes.removed"
    text = context.words.text(key, subject=subject, scope=scope)
    return Draft("line", rank, [subject], [change], text=text)


def _subject(entry: Entry, context: _Context) -> str:
    if entry.entity.kind == "unit":
        return context.unit_names.get(entry.entity.id, entry.entity.name)
    return entry.entity.name


def _scope(entry: Entry, context: _Context) -> str:
    """ "(except Franks and Persians)": the exceptions of a change every other civ shares."""
    if entry.scope.kind not in ("all_except", "having_except"):
        return ""
    names = [context.civ_names.get(civ, civ) for civ in entry.scope.civs]
    return context.words.text("notes.except", civs=context.words.listed(names))


def _civilization(entry: Entry, context: _Context, subject: str, scope: str) -> list[Draft]:
    rank = _RANKS["civilizations"]
    drafts: list[Draft] = []
    fields: list[Change] = []
    for change in entry.changes:
        if change.field is None and change.kind in ("added", "removed"):
            key = "notes.civ_added" if change.kind == "added" else "notes.civ_removed"
            drafts.append(Draft("line", rank, [subject], [change], text=context.words.text(key)))
        else:
            fields.append(change)
    if fields:
        drafts.append(_stats(fields, context, rank, subject, scope))
    return drafts


def _availability(
    entry: Entry, context: _Context, subject: str, scope: str, civ: CivRef | None
) -> list[Draft]:
    """Gaining and losing access, renamed nodes, and a new civ's tech tree."""
    rank = _RANKS["civ_availability"]
    words = context.words
    entity = (entry.entity.kind, entry.entity.id)
    drafts: list[Draft] = []
    tree: list[Change] = []
    for change in entry.changes:
        key = change.field.key if change.field is not None else None
        access = _status_move(change) if key == "field.node_status" else None
        if key is None and change.kind in ("added", "removed"):
            access = "gain" if change.kind == "added" else "lose"
        if access is not None:
            place = rank if access == "gain" else _LOSS_RANK
            drafts.append(Draft(access, place, [subject], [change], entity=entity, scope=scope))
        elif change.kind == "renamed" and change.old and change.new:
            text = words.text("notes.renamed", old=change.old, new=change.new)
            drafts.append(Draft("line", rank, [subject], [change], text=text))
        elif key in _TREE_FIELDS:
            tree.append(change)
        else:
            drafts.append(_stats([change], context, rank, subject, scope, civ=civ))
    if tree:
        children = [_tree_line(change, words) for change in tree]
        text = words.text("notes.tech_tree")
        drafts.append(Draft("line", rank, [subject], tree, text=text, children=children))
    return drafts


def _tree_line(change: Change, words: Words) -> Child:
    """A new civ's tech tree at one building: "Barracks: Militia, Man-at-Arms, …"."""
    assert change.field is not None  # only tree fields come here
    if change.field.key == "field.tech_tree_at":
        building = words.value(change.field.args.get("building"))
    else:
        building = words.text("notes.tree_buildings")
    return Child(building, change.new or "")


def _status_move(change: Change) -> Access | None:
    """ "gain" or "lose" when a node's status moves from or to Not available."""
    if change.old == _NOT_AVAILABLE and change.new and change.new != _NOT_AVAILABLE:
        return "gain"
    if change.new == _NOT_AVAILABLE and change.old and change.old != _NOT_AVAILABLE:
        return "lose"
    return None


def _unit(entry: Entry, context: _Context, subject: str, scope: str) -> list[Draft]:
    rank = _RANKS["unit_stats"]
    changes = list(entry.changes)
    if entry.kind == "added":
        said: list[Change] = []
        children = _new_children(changes, context, said)
        entity = ("unit", entry.entity.id)
        return [Draft("new", rank, [subject], said, entity, scope, children=children)]
    if entry.kind == "removed":
        return [_removed(changes, context, rank, subject, scope)]
    return [_stats(changes, context, rank, subject, scope)]


def _tech(entry: Entry, context: _Context, rank: int, subject: str, scope: str) -> list[Draft]:
    changes = list(entry.changes)
    effects = [change for change in changes if _is_sentence(change)]
    fields = [change for change in changes if not _is_sentence(change)]
    if entry.kind == "added":
        # Only what the bullets say counts as said; the rest is counted in the closing line.
        said: list[Change] = []
        children = _effect_children(effects, context, said) + _new_children(fields, context, said)
        entity = ("tech", entry.entity.id)
        return [Draft("new", rank, [subject], said, entity, scope, children=children)]
    if entry.kind == "removed":
        return [_removed(changes, context, rank, subject, scope)]
    drafts = [_stats(fields, context, rank, subject, scope)] if fields else []
    return drafts + _effects(effects, context, rank, subject, scope)


def _removed(
    changes: list[Change], context: _Context, rank: int, subject: str, scope: str
) -> Draft:
    text = context.words.text("notes.removed", subject=subject, scope=scope)
    return Draft("line", rank, [subject], changes, text=text)


def _stats(
    changes: Sequence[Change],
    context: _Context,
    rank: int,
    subject: str,
    scope: str,
    civ: CivRef | None = None,
) -> Draft:
    """ "Onager melee attack increased from 50 → 55, pierce armour …": one subject's fields.

    A field with no values says whether it came or went: "Stable building offer added".
    """
    words = context.words
    fields: list[Field] = []
    for change in changes:
        label = words.field(change.field) if change.field else ""
        old, new = change.old or "", change.new or ""
        if not old and not new and change.kind in ("added", "removed"):
            key = "notes.clause.came" if change.kind == "added" else "notes.clause.went"
            label = words.text(key, field=label)
        fields.append(
            Field(label, _word(change, old, context, civ), _word(change, new, context, civ))
        )
    return Draft("stats", rank, [subject], list(changes), scope=scope, fields=fields)


def _word(change: Change, value: str, context: _Context, civ: CivRef | None) -> str:
    """A game keyword as words: a node status, or an age (1 to 4 are the base civs' ages)."""
    if not value or change.field is None:
        return value
    if change.field.key == "field.node_status":
        return context.messages.get(f"status.{value}", value)
    if change.field.key == "field.age" and (civ is None or civ.era != _CHRONICLES):
        return context.messages.get(f"tree.age.{value}", value)
    return value


def _new_children(changes: Sequence[Change], context: _Context, said: list[Change]) -> list[Child]:
    """A new unit's or tech's values, one bullet each; its costs as one: "Cost: 40 wood, 65 gold".

    The cost bullet sits where the first cost was. The changes it says are added to `said`.
    """
    words = context.words
    costs: list[str] = []
    cost_at: int | None = None
    children: list[Child] = []
    for change in changes:
        if change.field is None or not change.new:
            continue
        said.append(change)
        if change.field.key == "field.cost":
            resource = words.value(change.field.args.get("resource"))
            costs.append(words.text("notes.cost_part", amount=shown(change.new), resource=resource))
            if cost_at is None:
                cost_at = len(children)
            continue
        children.append(Child(words.message(change.field), shown(change.new)))
    if cost_at is not None:
        cost = Child(words.text("notes.cost"), words.text("notes.list_separator").join(costs))
        children.insert(cost_at, cost)
    return children


# --- effects ------------------------------------------------------------------------------------


def _is_sentence(change: Change) -> bool:
    return change.detail is not None and change.detail.key == _SENTENCE


@dataclass(slots=True)
class _Given:
    """What an effect gives each target, in the order the targets first appear."""

    parts: dict[str, list[str]] = field(default_factory=dict)
    changes: dict[str, list[Change]] = field(default_factory=dict)

    def add(self, target: str, part: str, change: Change) -> None:
        self.parts.setdefault(target, []).append(part)
        self.changes.setdefault(target, []).append(change)

    def used(self) -> list[Change]:
        return [change for changes in self.changes.values() for change in changes]


def _effects(
    changes: Sequence[Change], context: _Context, rank: int, subject: str, scope: str
) -> list[Draft]:
    """A tech's or bonus's effect sentences.

    What it now gives units reads "Bodkin Arrow now affects Leif Erikson and Dreki:", with what
    each one gets; what it gives no longer, "… no longer affects …". A value that changed the
    same way for several targets is one clause naming them all ("Hand Cannoneer and Bombard
    Cannon movement speed decreased from +15% → +10%"). A sentence with no value reads "new
    effect: Enables Champi Runner".
    """
    words = context.words
    gained, lost = _Given(), _Given()
    moved: dict[tuple[str, str, str], list[str]] = {}  # (attribute, old, new) -> targets
    moved_changes: list[Change] = []
    fields: list[Field] = []
    came: list[Change] = []  # sentences with no value: "Enables X"
    went: list[Change] = []
    for change in changes:
        if change.field is None:
            continue
        old, new = change.old or "", change.new or ""
        aimed = _target_attribute(change.field, words)
        if aimed is not None and bool(old) != bool(new):
            target, attribute = aimed
            (gained if new else lost).add(target, _part(attribute, new or old, words), change)
        elif aimed is not None and old and new:
            target, attribute = aimed
            moved.setdefault((attribute, old, new), []).append(target)
            moved_changes.append(change)
        elif change.field.key == "effect.added":
            came.append(change)
        elif change.field.key == "effect.removed":
            went.append(change)
        else:
            fields.append(Field(words.message(change.field), old, new))
            moved_changes.append(change)
    drafts: list[Draft] = []
    cancelled = _cancel(gained, lost)
    if cancelled:
        drafts.append(Draft("silent", rank, [subject], cancelled))
    for form, given in (("affects", gained), ("no_longer", lost)):
        if given.parts:
            drafts.append(_given(form, given, words, rank, subject, scope))  # type: ignore[arg-type]  # "affects" or "no_longer"
    for (attribute, old, new), targets in moved.items():
        same: dict[str, list[str]] = {target: [] for target in targets}
        named = words.listed([name for name, _ in _paired(same, words)])
        label = words.text("notes.effect_target", target=named, attribute=attribute)
        fields.append(Field(label, old, new))
    if fields:
        drafts.append(Draft("effect", rank, [subject], moved_changes, scope=scope, fields=fields))
    for found, one, several in (
        (came, "notes.effect_new", "notes.effects_new"),
        (went, "notes.effect_gone", "notes.effects_gone"),
    ):
        if found:
            drafts.append(_valueless(found, one, several, words, rank, subject))
    return drafts


def _given(
    form: Literal["affects", "no_longer"],
    given: _Given,
    words: Words,
    rank: int,
    subject: str,
    scope: str,
) -> Draft:
    """What an effect now gives, or no longer gives, its targets.

    One line when every target gets the same ("X now affects A and B: +1 armour."), otherwise one
    bullet per group of targets that get the same ("A and B: +1 armour").
    """
    targets = _paired(given.parts, words)
    groups: dict[tuple[str, ...], list[str]] = {}
    for name, parts in targets:
        groups.setdefault(tuple(parts), []).append(name)
    names = [name for name, _ in targets]
    if len(groups) == 1:
        [shared] = groups
        text = ", ".join(shared)
        return Draft(form, rank, [subject], given.used(), scope=scope, targets=names, text=text)
    children = [
        Child(words.text("notes.target", target=words.listed(group), parts=", ".join(parts)))
        for parts, group in groups.items()
    ]
    return Draft(form, rank, [subject], given.used(), scope=scope, targets=names, children=children)


def _valueless(
    changes: list[Change], one: str, several: str, words: Words, rank: int, subject: str
) -> Draft:
    """Sentences with no value, "Enables X": one line, or one bullet each under the subject."""
    effects = [words.value(change.field.args.get("effect")) for change in changes if change.field]
    if len(effects) == 1:
        text = words.text(one, subjects=subject, effect=effects[0])
        return Draft("line", rank, [subject], changes, text=text)
    text = words.text(several, subjects=subject)
    children = [Child(effect) for effect in effects]
    return Draft("line", rank, [subject], changes, text=text, children=children)


def _cancel(gained: _Given, lost: _Given) -> list[Change]:
    """Take out what an effect gives a target both before and after: a command that only moved.

    The commands are aligned as a sequence (diff-rules.md, Effects), so one moved elsewhere in the
    list reads as removed and added back; to a player nothing changed (Fabric Shields, Incas,
    on 101.103.54800.0).
    """
    cancelled: list[Change] = []
    for target in [name for name in gained.parts if name in lost.parts]:
        for part in list(gained.parts[target]):
            if part not in lost.parts[target]:
                continue
            for given in (gained, lost):
                index = given.parts[target].index(part)
                given.parts[target].pop(index)
                cancelled.append(given.changes[target].pop(index))
                if not given.parts[target]:
                    del given.parts[target]
                    del given.changes[target]
            if target not in gained.parts or target not in lost.parts:
                break
    return cancelled


def _effect_children(
    changes: Sequence[Change], context: _Context, said: list[Change]
) -> list[Child]:
    """What a new tech does, one bullet per target or sentence: "(Heavy) Mounted Crossbowman: …".

    Only what it now does is said; the changes said are added to `said`.
    """
    words = context.words
    gained = _Given()
    children: list[Child] = []
    for change in changes:
        if change.field is None:
            continue
        aimed = _target_attribute(change.field, words)
        if aimed is not None and change.new and not change.old:
            target, attribute = aimed
            gained.add(target, _part(attribute, change.new, words), change)
        elif change.field.key == "effect.added":
            children.append(Child(words.value(change.field.args.get("effect"))))
            said.append(change)
        elif change.new and not change.old:
            children.append(Child(words.message(change.field), shown(change.new)))
            said.append(change)
    said.extend(gained.used())
    targets = [
        Child(words.text("notes.target", target=name, parts=", ".join(parts)))
        for name, parts in _paired(gained.parts, words)
    ]
    return targets + children


def _target_attribute(field: Message, words: Words) -> tuple[str, str] | None:
    """What an effect sentence acts on, and which of its values: ("Archer", "pierce attack").

    A unit's attribute, or a tech's cost or research time. Other sentences have no target.
    """
    args = field.args
    if field.key == "effect.attribute":
        return words.value(args.get("target")), words.attribute(args.get("attribute"))
    if field.key == "effect.tech_resource_cost":
        cost = words.text("notes.resource_cost", resource=words.value(args.get("resource")))
        return words.value(args.get("tech")), words.lowered(cost)
    if field.key == "effect.tech_cost":
        return words.value(args.get("tech")), words.lowered(words.text("notes.cost"))
    if field.key == "effect.tech_time":
        return words.value(args.get("tech")), words.lowered(words.text("notes.research_time"))
    return None


def _part(attribute: str, value: str, words: Words) -> str:
    """What an effect does to one attribute: "+1 pierce attack", "-40% gold cost"."""
    if value.startswith("="):
        return words.text("notes.part_set", attribute=attribute, value=shown(value))
    return words.text("notes.part", value=shown(value), attribute=attribute)


def _paired(parts: dict[str, list[str]], words: Words) -> list[tuple[str, list[str]]]:
    """Targets as the notes name them, in order of appearance.

    "Hearth Troop" and "Elite Hearth Troop" given the same things read "(Elite) Hearth Troop",
    at the place of the first of the two.
    """
    prefixes: dict[str, str] = {}  # base name -> the prefix of the target folded into it
    folded: set[str] = set()
    for name in parts:
        prefix, _, base = name.partition(" ")
        if (
            base in parts
            and base not in prefixes
            and base not in folded
            and name not in prefixes
            and parts[base] == parts[name]
        ):
            prefixes[base] = prefix
            folded.add(name)
    return [
        (words.paired(prefixes[name], name) if name in prefixes else name, found)
        for name, found in parts.items()
        if name not in folded
    ]


# --- the civ's description ----------------------------------------------------------------------


def _description(change: Change, context: _Context, subject: str) -> Draft | None:
    """The civ's description (its bonus text), line by line: what was added, removed or edited.

    None when only spacing or line breaks moved (Byzantines on 101.103.54800.0 wrap a line
    differently).
    """
    old_text = "".join(word.text for word in change.words if word.kind != "added")
    new_text = "".join(word.text for word in change.words if word.kind != "removed")
    old_lines, new_lines = _lines(old_text), _lines(new_text)
    words = context.words
    if not old_lines:
        children = [Child(line) for line in new_lines]  # a new civ: every line is new
    else:
        children = []
        matcher = difflib.SequenceMatcher(a=old_lines, b=new_lines, autojunk=False)
        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            before, after = old_lines[i1:i2], new_lines[j1:j2]
            if tag == "equal" or _squeezed(before) == _squeezed(after):
                continue
            paired = min(len(before), len(after)) if tag == "replace" else 0
            children += [
                Child(words.text("notes.line_changed", old=old, new=new))
                for old, new in zip(before[:paired], after[:paired], strict=True)
            ]
            children += [
                Child(words.text("notes.line_removed", line=line)) for line in before[paired:]
            ]
            children += [
                Child(words.text("notes.line_added", line=line)) for line in after[paired:]
            ]
    if not children:
        return None
    text = words.text("notes.description")
    return Draft("line", _DESCRIPTION_RANK, [subject], [change], text=text, children=children)


def _lines(text: str) -> list[str]:
    """A description's lines, without their bullets and spacing; empty lines dropped."""
    lines = (line.strip().removeprefix(_BULLET).strip() for line in text.split("\n"))
    return [line for line in lines if line]


def _squeezed(lines: Sequence[str]) -> str:
    """Lines joined without any spacing: equal for two texts that only wrap differently."""
    return "".join("".join(lines).split())

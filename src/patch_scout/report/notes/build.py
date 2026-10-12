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
# Fields left to the detailed changes. Required techs: on 101.103.54800.0 every change to them
# was plumbing ("Dupl. Imperial Age", "Civ bonus: Free Chemistry"); players read requirements
# as ages and availability, which the notes say from the tech tree.
_DETAILED_ONLY: Final = frozenset({"field.required_techs"})
# A new civ's tech tree, one line per building.
_TREE_FIELDS: Final = frozenset({"field.tech_tree_at", "field.tech_tree_buildings"})
# A new civ's summary lines: its unique and regional units and techs.
_SPECIAL_LISTS: Final = frozenset(
    {"field.unique_units", "field.unique_techs", "field.regional_units", "field.regional_techs"}
)
# Notices the closing line replaces: the notes have no filters to turn on.
_FILTER_NOTICES: Final = frozenset({"levels_hidden", "unnamed_hidden"})
# Categories whose changes every civ that has the object shares are said once, in General.
_SHARED: Final = frozenset({"unit_stats", "techs"})
_NOT_AVAILABLE: Final = "NotAvailable"
_COST: Final = "field.cost"
_UPGRADE: Final = "effect.upgrade"
_SCRIPT: Final = "effect.script"
_CAME_OR_WENT: Final = frozenset({"effect.added", "effect.removed"})
_BULLET: Final = "\N{BULLET}"
_CHRONICLES: Final = "antiquity"

# Where each kind of sentence goes in a civ's block, as in the official notes: what the civ is,
# its description, its bonuses, then units, techs, what it gains, then what it loses.
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
    redundant, explained = _free_made_redundant(change_set.entries, words)
    kept = [
        curated
        for entry in change_set.entries
        if (curated := _curated(entry, words, redundant | explained)) is not None
    ]
    kept, copies = _holders_in_general(kept)
    # Changes that cancel out for players count as said.
    used: set[int] = set(redundant)
    sections = [
        section
        for section in (
            _general(kept, context, used),
            _civs(change_set.civs, kept, context, used, chronicles=False),
            _civs(change_set.civs, kept, context, used, chronicles=True),
        )
        if section is not None
    ]
    # A change said once in General is said for each civ that has a copy of it.
    used.update(copy for change in list(used) for copy in copies.get(change, ()))
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


def _free_made_redundant(entries: Iterable[Entry], words: Words) -> tuple[set[int], set[int]]:
    """Effects that made a tech free, gone along with the tech's own cost: nothing changed.

    A tech cost 1 food, and a civ's effect set that cost to 0; the patch drops both, so the civ
    still gets the tech for nothing (Incas' "Team bonus: Start w/ Llama", Berbers' Genitour and
    Italians' Condottiero on 101.103.54800.0). Matched by tech name and resource, whatever the
    tech. Returns the effects' changes, which count as said, and the techs' cost changes, which
    are left to the detailed changes and counted: no other civ is known not to have paid them.
    """
    lost_costs: dict[tuple[str, str], list[Change]] = {}
    for entry in entries:
        if entry.category != "techs":
            continue
        for change in entry.changes:
            field = change.field
            if field is not None and field.key == "field.cost" and change.old and not change.new:
                resource = words.value(field.args.get("resource")).casefold()
                lost_costs.setdefault((entry.entity.name, resource), []).append(change)
    redundant: set[int] = set()
    explained: set[int] = set()
    for entry in entries:
        for change in entry.changes:
            field = change.field
            old = change.old or ""
            if (
                field is None
                or field.key != "effect.tech_resource_cost"
                or change.new
                or not old.startswith("=")
                or shown(old) != "0"
            ):
                continue
            tech = words.value(field.args.get("tech"))
            resource = words.value(field.args.get("resource")).casefold()
            matched = lost_costs.get((tech, resource))
            if matched:
                redundant.add(id(change))
                explained.update(id(cost) for cost in matched)
    return redundant, explained


def _holders_in_general(entries: Sequence[Entry]) -> tuple[list[Entry], dict[int, list[int]]]:
    """Move the unit and tech changes every civ that has the object shares to General, once.

    The engine names the civs when a few have the object, and puts a copy of the change on each
    civ's page; the official notes say such a change once, in General (Lou Chuan, Armored
    Elephant, Fortified Church on 101.103.54800.0). Gaining access stays with each civ, as the
    official notes write it, and one civ's own unit stays in its block. Returns the entries, with
    the first copy of each moved to General in name order, and each kept change's other copies.
    """
    kept: list[Entry] = []
    firsts: dict[tuple[object, ...], Entry] = {}
    copies: dict[int, list[int]] = {}
    for entry in entries:
        if entry.civ is None or entry.category not in _SHARED or not entry.scope.every_holder:
            kept.append(entry)
            continue
        key = (entry.category, entry.kind, entry.entity.kind, entry.entity.id, entry.scope.civs)
        first = firsts.get(key)
        if first is None:
            firsts[key] = replace(entry, civ=None)
            continue
        mine = {_said(change): change for change in entry.changes}
        for change in first.changes:
            copy = mine.get(_said(change))
            if copy is not None:
                copies.setdefault(id(change), []).append(id(copy))
    for moved in firsts.values():
        _insert_by_name(kept, moved)
    return kept, copies


def _insert_by_name(entries: list[Entry], moved: Entry) -> None:
    """Put a change moved to General among its category's Overall entries, in name order.

    The engine sorts civ-specific changes first, then by name; in General the moved change reads
    where its name puts it ("Lou Chuan" between "Long Swordsman" and "Man-at-Arms").
    """
    name = moved.entity.name.casefold()
    for position, entry in enumerate(entries):
        if (
            entry.civ is None
            and entry.category == moved.category
            and entry.entity.name.casefold() > name
        ):
            entries.insert(position, moved)
            return
    entries.append(moved)


def _said(change: Change) -> tuple[object, ...]:
    """What a change says, whichever civ's page holds it."""
    field = repr(change.field.to_json()) if change.field is not None else None
    return (field, change.kind, change.old, change.new)


def _curated(entry: Entry, words: Words, dropped: set[int]) -> Entry | None:
    """The entry with only what the notes can say; None when nothing is left.

    Techs known only by their developers' name are plumbing players never see (maintainer,
    2026-10-12): they are counted, never written.
    """
    if entry.low_priority or not entry.entity.named or entry.entity.internal:
        return None
    scripted = entry.category == "techs" and any(_runs_script(change) for change in entry.changes)
    changes = tuple(
        change
        for change in entry.changes
        if id(change) not in dropped
        and _sayable(change, words)
        and not _runs_script(change)
        and not (scripted and _is_sentence(change))
    )
    if not changes:
        return None
    return entry if len(changes) == len(entry.changes) else replace(entry, changes=changes)


def _runs_script(change: Change) -> bool:
    """A sentence saying an effect runs a function of Effects.xs, or no longer does.

    It says nothing a player can read: on 101.103.54800.0 five such scripts only showed a
    message (Kasbah, Cuman Mercenaries, First Crusade, Flemish Revolution, Atheism), and the
    others took over a bonus whose old effects read as removed ("Gold Bonus removed", Malians).
    A tech that gains or loses one leaves all its effect sentences to the detailed changes.
    """
    if change.field is None or change.field.key not in _CAME_OR_WENT:
        return False
    sentence = change.field.args.get("effect")
    return isinstance(sentence, dict) and sentence.get("key") == _SCRIPT


def _sayable(change: Change, words: Words) -> bool:
    if change.level != "headline":
        return False
    if change.detail is not None and change.detail.key == _RAW_COMMAND:
        return False
    if change.field is not None and change.field.key in _ID_FIELDS | _DETAILED_ONLY:
        return False
    label = words.message(change.field) if change.field is not None else ""
    return not any(_UNKNOWN_ID.search(part) for part in (label, change.old or "", change.new or ""))


# --- sections -----------------------------------------------------------------------------------


def _general(kept: Sequence[Entry], context: _Context, used: set[int]) -> Section | None:
    """Changes to every civ: one group per category."""
    words = context.words
    overall = [entry for entry in kept if entry.civ is None]
    groups: list[Group] = []
    for category in CATEGORIES:
        mine = [entry for entry in overall if entry.category == category]
        items = _items(mine, context, used, civ=None)
        if items:
            groups.append(Group(words.text(f"category.{category}"), items))
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
        mine = [entry for entry in kept if entry.civ == civ.internal_name]
        items = _new_civ(mine, context, used) if civ.added else _items(mine, context, used, civ)
        if items:
            groups.append(Group(civ.name, items, civ=civ.internal_name, icon=civ.icon))
    if not groups:
        return None
    kind: Literal["civs", "chronicles"] = "chronicles" if chronicles else "civs"
    return Section(kind, context.words.text(f"notes.section.{kind}"), tuple(groups))


def _new_civ(entries: Sequence[Entry], context: _Context, used: set[int]) -> tuple[Item, ...]:
    """A new civ in a few lines, as a player first wants it: what kind of civ it is, and what
    sets it apart ("Unique units: Jomsviking", "Regional units: Varangian Guard").

    Its bonuses' exact effects, its units' stats and its whole tech tree are in the detailed
    changes and the tech tree; the closing line counts them.
    """
    if not entries:
        return ()
    words = context.words
    kind = ""
    lists: list[Change] = []
    said: list[Change] = []
    for entry in entries:
        for change in entry.changes:
            key = change.field.key if change.field is not None else None
            if entry.category == "civilizations" and change.field is None:
                said.append(change)  # the civ itself, added
            elif key == "field.civ_bonus_text":
                kind = next(iter(_lines(_new_text(change))), "")
                said.append(change)
            elif entry.category == "civilizations" and key in _SPECIAL_LISTS and change.new:
                lists.append(change)
    first = words.text("notes.civ_added_as", kind=kind) if kind else words.text("notes.civ_added")
    items = [Item(first)]
    for change in lists:
        label = words.message(change.field) if change.field is not None else ""
        names = _line_heads(change.new or "", words)
        items.append(Item(words.text("notes.list", field=label, names=names)))
        said.append(change)
    used.update(id(change) for change in said)
    return tuple(items)


def _line_heads(names: str, words: Words) -> str:
    """Names without their upgrades: "Jomsviking, Elite Jomsviking" reads "Jomsviking".

    A name that is another name of the list with one word before it ("Elite Jomsviking", or
    "E. Varangian Guard" as the tree shortens it) is that unit's upgrade: the line is named once.
    """
    listed = [name.strip() for name in names.split(", ") if name.strip()]
    present = set(listed)
    heads = [name for name in listed if name.partition(" ")[2] not in present]
    return words.listed(heads)


def _items(
    entries: Iterable[Entry], context: _Context, used: set[int], civ: CivRef | None
) -> tuple[Item, ...]:
    """One group's bullets: drafted, de-duplicated, paired, merged, then ordered."""
    drafts: list[Draft] = []
    for entry in entries:
        drafts += _drafts(entry, context, civ)
    drafts = _without_gains_said_by_new(drafts)
    if civ is not None:
        drafts = _without_repeats(drafts, civ, context.words)
    drafts = drafting.merge(drafting.pair(drafts, context.words), context.words)
    if civ is not None:
        drafts = drafting.ordered(drafts)
    for draft in drafts:
        used.update(id(change) for change in draft.used)
    return tuple(
        drafting.render(draft, context.words) for draft in drafts if draft.form != "silent"
    )


def _without_repeats(drafts: list[Draft], civ: CivRef, words: Words) -> list[Draft]:
    """Leave out effect lines a civ's changed description already says, in the game's words.

    Teutons on 101.103.54800.0: "Infantry and Mounted Units +1/+2 melee armor" in the description,
    then twice more as what their bonus techs affect. The effects of the civ's bonuses (its own
    entity, and techs named "Civ bonus: …" or "Team bonus: …") and of a tech the changed lines
    name ("Wagenburg Tactics (…)") are left out; the closing line counts them, and the detailed
    changes list them. A civ whose description didn't change keeps them.
    """
    said = [draft.text for draft in drafts if draft.rank == _DESCRIPTION_RANK and draft.text]
    if not said:
        return drafts
    bonuses = tuple(words.text(key, name="") for key in ("name.civ_bonus", "name.team_bonus"))

    def repeats(draft: Draft) -> bool:
        subject = draft.subjects[0]
        return (
            subject == civ.name
            or subject.startswith(bonuses)
            or any(subject in line for line in said)
        )

    return [draft for draft in drafts if not (draft.effect and repeats(draft))]


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
    rank = _RANKS.get(entry.category, _OTHER_RANK)
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
            # Only spacing or line breaks moved: nothing to say (Byzantines on 54800).
            drafts += _description(change, context, subject) or [
                Draft("silent", rank, [subject], [change])
            ]
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
        # One line, as the official notes introduce a unit; its stats are in the detailed changes
        # and the tech tree. The line says the unit is new, so its values count as said.
        entity = ("unit", entry.entity.id)
        where = _trained_at(changes, context.words)
        return [Draft("new", rank, [subject], changes, entity, scope, text=where)]
    if entry.kind == "removed":
        return [_removed(changes, context, rank, subject, scope)]
    return [_stats(changes, context, rank, subject, scope)]


def _trained_at(changes: Sequence[Change], words: Words) -> str:
    """Where a new unit is trained: the building of its first train time, else nothing."""
    for change in changes:
        if change.field is not None and change.field.key == "field.train_locations":
            return words.value(change.field.args.get("location"))
    return ""


def _tech(entry: Entry, context: _Context, rank: int, subject: str, scope: str) -> list[Draft]:
    changes = list(entry.changes)
    effects = [change for change in changes if _is_sentence(change)]
    fields = [change for change in changes if not _is_sentence(change)]
    if entry.kind == "added":
        # One line with what it does, as a player first wants it: "NEW: Ordonnance Companies:
        # (Heavy) Mounted Crossbowman -40% gold cost". Its cost, research time and requirements
        # are in the detailed changes and the tech tree; the line says the tech is new, so they
        # count as said. An effect sentence it doesn't write is counted in the closing line.
        said: list[Change] = list(fields)
        entity = ("tech", entry.entity.id)
        if _upgrades_to_itself(effects, subject, context.words):
            # "NEW: Heavy Mounted Crossbowman upgrade.", not the name twice.
            said.extend(effects)
            named = context.words.text("notes.upgrade", name=subject)
            return [Draft("new", rank, [named], said, entity, scope)]
        does = "; ".join(_what_it_does(effects, context, said))
        return [Draft("new", rank, [subject], said, entity, scope, text=does)]
    if entry.kind == "removed":
        return [_removed(changes, context, rank, subject, scope)]
    drafts = [_stats(fields, context, rank, subject, scope)] if fields else []
    return drafts + _effects(effects, context, rank, subject, scope)


def _upgrades_to_itself(effects: Sequence[Change], subject: str, words: Words) -> bool:
    """Whether a tech's only sentence upgrades a unit into the unit it is named after."""
    if len(effects) != 1 or effects[0].field is None:
        return False
    sentence = effects[0].field.args.get("effect")
    if effects[0].field.key != "effect.added" or not isinstance(sentence, dict):
        return False
    args = sentence.get("args")
    return (
        sentence.get("key") == _UPGRADE
        and isinstance(args, dict)
        and words.value(args.get("to")) == subject
    )


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
        label = _label(change, words)
        old, new = change.old or "", change.new or ""
        if not old and not new and change.kind in ("added", "removed"):
            key = "notes.clause.came" if change.kind == "added" else "notes.clause.went"
            label = words.text(key, field=label)
        fields.append(
            Field(label, _word(change, old, context, civ), _word(change, new, context, civ))
        )
    return Draft("stats", rank, [subject], list(changes), scope=scope, fields=fields)


def _label(change: Change, words: Words) -> str:
    """A field's label; a tech's cost reads "research cost", so an upgrade named after its unit
    ("Elite Rattan Archer", "Demolition Ship" on 101.103.54800.0) isn't read as the unit's."""
    if change.field is None:
        return ""
    if change.category == "techs" and change.field.key == _COST:
        resource = words.value(change.field.args.get("resource"))
        return words.lowered(words.text("notes.research_cost", resource=resource))
    return words.field(change.field)


def _word(change: Change, value: str, context: _Context, civ: CivRef | None) -> str:
    """A game keyword as words: a node status, or an age (1 to 4 are the base civs' ages)."""
    if not value or change.field is None:
        return value
    if change.field.key == "field.node_status":
        return context.messages.get(f"status.{value}", value)
    if change.field.key == "field.age" and (civ is None or civ.era != _CHRONICLES):
        return context.messages.get(f"tree.age.{value}", value)
    return value


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
        # "X now affects Archer" says enough for a unit; for a tech's cost or research time it
        # would read as if the tech itself came or went ("Incas no longer affects Team bonus:
        # Start w/ Llama"), so those keep their numbers, as a clause.
        on_unit = change.field.key == "effect.attribute"
        if aimed is not None and on_unit and bool(old) != bool(new):
            target, attribute = aimed
            (gained if new else lost).add(target, _part(attribute, new or old, words), change)
        elif aimed is not None:
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
        drafts.append(
            Draft("effect", rank, [subject], moved_changes, scope=scope, fields=fields, effect=True)
        )
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
    """Whom an effect now affects, or no longer affects: "Bodkin Arrow now affects Dreki."

    Not what it gives them: players know what Bodkin Arrow does (maintainer, 2026-10-12), and the
    detailed changes have the values. Names pair as usual: "(Elite) Hearth Troop".
    """
    names = [name for name, _ in _paired({name: [] for name in given.parts}, words)]
    return Draft(form, rank, [subject], given.used(), scope=scope, targets=names, effect=True)


def _valueless(
    changes: list[Change], one: str, several: str, words: Words, rank: int, subject: str
) -> Draft:
    """Sentences with no value, "Enables X": one line, or one bullet each under the subject."""
    effects = [words.value(change.field.args.get("effect")) for change in changes if change.field]
    if len(effects) == 1:
        text = words.text(one, subjects=subject, effect=effects[0])
        return Draft("line", rank, [subject], changes, text=text, effect=True)
    text = words.text(several, subjects=subject)
    children = [Child(effect) for effect in effects]
    return Draft("line", rank, [subject], changes, text=text, children=children, effect=True)


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


def _what_it_does(changes: Sequence[Change], context: _Context, said: list[Change]) -> list[str]:
    """What a new tech does, one phrase per target or sentence: "(Heavy) Mounted Crossbowman
    -40% gold cost". Only what it now does is said; the changes said are added to `said`."""
    words = context.words
    gained = _Given()
    sentences: list[str] = []
    for change in changes:
        if change.field is None:
            continue
        aimed = _target_attribute(change.field, words)
        if aimed is not None and change.new and not change.old:
            target, attribute = aimed
            gained.add(target, _part(attribute, change.new, words), change)
        elif change.field.key == "effect.added":
            sentences.append(words.value(change.field.args.get("effect")))
            said.append(change)
        elif change.new and not change.old:
            label = words.message(change.field)
            sentences.append(
                words.text("notes.target_inline", target=label, parts=shown(change.new))
            )
            said.append(change)
    said.extend(gained.used())
    targets = [
        words.text("notes.target_inline", target=name, parts=", ".join(parts))
        for name, parts in _paired(gained.parts, words)
    ]
    return targets + sentences


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


def _description(change: Change, context: _Context, subject: str) -> list[Draft]:
    """The civ's description (its bonus text): one bullet per line that changed, in the game's
    own words, under the game's own heading ("Unique Techs: Bearded Axe (…) → Ordonnance
    Companies (…)"), and only the part that changed when the rest stays ("Wagenburg Tactics
    (Gunpowder Units move +15% → +10% faster)"). Empty when only spacing or line breaks moved.
    """
    old_text = "".join(word.text for word in change.words if word.kind != "added")
    old_lines, new_lines = _headed(old_text), _headed(_new_text(change))
    words = context.words
    texts: list[str] = []
    olds, news = [line for _, line in old_lines], [line for _, line in new_lines]
    matcher = difflib.SequenceMatcher(a=olds, b=news, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal" or _squeezed(olds[i1:i2]) == _squeezed(news[j1:j2]):
            continue
        before, after = old_lines[i1:i2], new_lines[j1:j2]
        paired = min(len(before), len(after)) if tag == "replace" else 0
        for (heading, old), (_, new) in zip(before[:paired], after[:paired], strict=True):
            if _plain(old) == _plain(new):
                # Only punctuation or capitals changed: an arrow would read as a change of
                # meaning (Mapuche on 101.103.54800.0, "Slingers and" → "Slingers, and").
                continue
            texts.append(_in(heading, _compact(old, new, words), "notes.line_in", words))
        for heading, line in before[paired:]:
            texts.append(_in(heading, line, "notes.line_removed", words))
        for heading, line in after[paired:]:
            texts.append(_in(heading, line, "notes.line_added", words))
    return [Draft("line", _DESCRIPTION_RANK, [subject], [change], text=text) for text in texts]


def _in(heading: str, line: str, key: str, words: Words) -> str:
    """A description line, said with the heading it sits under, if any: "New in Team Bonus: …"."""
    if key == "notes.line_in":
        return words.text(key, heading=heading, line=line) if heading else line
    return words.text(f"{key}_in" if heading else key, heading=heading, line=line)


def _compact(old: str, new: str, words: Words) -> str:
    """A changed line with only what changed: "Foragers +15% → +20%", when most of it stays.

    Otherwise, or when the change only adds or removes words, the whole line both ways.
    """
    before, after = old.split(), new.split()
    shortest = min(len(before), len(after))
    head = 0
    while head < shortest and before[head] == after[head]:
        head += 1
    tail = 0
    while tail < shortest - head and before[-1 - tail] == after[-1 - tail]:
        tail += 1
    old_middle = before[head : len(before) - tail]
    new_middle = after[head : len(after) - tail]
    if not old_middle or not new_middle or (head + tail) * 2 < max(len(before), len(after)):
        return words.text("notes.line_changed", old=old, new=new)
    middle = words.text("notes.line_changed", old=" ".join(old_middle), new=" ".join(new_middle))
    return " ".join([*before[:head], middle, *before[len(before) - tail :]])


def _new_text(change: Change) -> str:
    """A text change's new text, rebuilt from its word diff."""
    return "".join(word.text for word in change.words if word.kind != "removed")


def _headed(text: str) -> list[tuple[str, str]]:
    """A description's lines, each with the heading it sits under ("Unique Techs"), if any.

    A heading is a line of the game's text ending with a colon; it is a line too.
    """
    headed: list[tuple[str, str]] = []
    heading = ""
    for line in _lines(text):
        headed.append((heading, line))
        if line.endswith(":"):
            heading = line.removesuffix(":").strip()
    return headed


def _lines(text: str) -> list[str]:
    """A description's lines, without their bullets and spacing; empty lines dropped."""
    lines = (line.strip().removeprefix(_BULLET).strip() for line in text.split("\n"))
    return [line for line in lines if line]


def _plain(line: str) -> str:
    """A line's letters and digits only, lowered: equal for two lines that differ in punctuation."""
    return "".join(char.lower() for char in line if char.isalnum())


def _squeezed(lines: Sequence[str]) -> str:
    """Lines joined without any spacing: equal for two texts that only wrap differently."""
    return "".join("".join(lines).split())

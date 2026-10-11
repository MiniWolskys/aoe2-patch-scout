# SPDX-License-Identifier: GPL-3.0-or-later
"""A unit, building or tech in detail, in both versions, for one civ or none (D-49).

The panel lists the raw values of each version and, for a civ, the bonuses and techs that affect
the entity, as effect sentences. Nothing is applied to the values (D-20): bonuses depend on age,
techs and classes, and a computed value would sometimes be wrong.

Each version is read on its own, with the civ's own slot in it (P-07), then the two are merged
row by row: one value when both agree, old → new when they differ, and new or gone when a row is
in one version only. A version that can't say anything (no stats, no such entity, no such civ)
gives no rows, and the other version's are shown as they are.
"""

import json
from collections.abc import Callable, Iterable, Iterator, Mapping
from dataclasses import dataclass, field
from typing import Final

from patch_scout.diff.allowlist import RESOURCE_KEYS
from patch_scout.diff.classes import ClassKind, attacked_classes, class_field, shown
from patch_scout.diff.effects import Lookup, describe, raw_pair
from patch_scout.diff.model import Message
from patch_scout.diff.names import Names
from patch_scout.diff.reachability import UnitLookup
from patch_scout.diff.values import at_path, display, pair, unknown_id
from patch_scout.diff.vocabulary import Vocabulary
from patch_scout.entity.affects import Kind, Target, affects, script_number
from patch_scout.entity.naming import Naming, effect_record, tech_record
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot
from patch_scout.tree.tooltip import parse

_USE_TYPES: Final[dict[str, Kind]] = {"Unit": "unit", "Building": "building", "Tech": "tech"}
_UNAVAILABLE: Final = "NotAvailable"
_CHRONICLES: Final = "antiquity"
_UPGRADE_NODE: Final = "UnitUpgrade"
# Template runs that the panel shows as its own rows rather than in the description.
_VALUE_RUNS: Final = frozenset({"stat", "cost"})
_GROUPS: Final = ("civ", "team", "unique", "techs")
# The groups that are the civ's own: their scripted bonuses are named (spec, decision 9).
_CIV_GROUPS: Final = frozenset({"civ", "team", "unique"})
_GROUP_TITLES: Final = {
    "civ": "entity.group.civ",
    "team": "entity.group.team",
    "unique": "entity.group.unique",
    "techs": "entity.group.techs",
}

type RowKey = tuple[str, ...]


@dataclass(frozen=True, slots=True)
class _Row:
    """One labelled value of one version, keyed so the two versions' rows can be paired."""

    key: RowKey
    field: Message
    value: JsonValue
    stat_icon: str | None = None


@dataclass(slots=True)
class _Source:
    """One bonus or tech that affects the entity in one version: its name and its lines."""

    key: str
    name: Message
    requires: str | None
    rows: list[_Row] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class _Side:
    """One version, read for one civ (or none)."""

    snapshot: Snapshot
    names: Names
    units: UnitLookup
    civ: str | None
    index: int | None

    @property
    def has_stats(self) -> bool:
        return isinstance(self.snapshot.stats, dict) and bool(self.snapshot.stats)

    @property
    def has_civ(self) -> bool:
        return self.civ is None or self.civ in self.snapshot.tech_trees

    def trees(self) -> list[list[JsonObject]]:
        """The tech trees this side reads: the civ's, or with no civ every base civ's.

        The Chronicles civs are left out then (D-38): their trees give the same units other
        names, such as the Archer as "Bowman".
        """
        if self.civ is not None:
            chosen = [self.civ]
        else:
            base = [
                str(entry.get("internal_name"))
                for entry in self.snapshot.civs
                if isinstance(entry, Mapping) and entry.get("era") != _CHRONICLES
            ]
            chosen = [name for name in base if name in self.snapshot.tech_trees]
            chosen = chosen or list(self.snapshot.tech_trees)
        found: list[list[JsonObject]] = []
        for name in chosen:
            nodes = self.snapshot.tech_trees.get(name)
            if isinstance(nodes, list):
                found.append([node for node in nodes if isinstance(node, dict)])
        return found

    def node(self, use_type: str, node_id: int) -> JsonObject | None:
        """The entity's tree node: the civ's, or with no civ the first available one."""
        fallback: JsonObject | None = None
        for nodes in self.trees():
            for node in nodes:
                if node.get("use_type") != use_type or node.get("node_id") != node_id:
                    continue
                if node.get("node_status") != _UNAVAILABLE:
                    return node
                fallback = fallback or node
        return fallback

    def any_node(self, use_type: str, node_id: int) -> JsonObject | None:
        """The entity's node in any civ's tree, for its icon when the civ doesn't have it."""
        for nodes in self.snapshot.tech_trees.values():
            for node in nodes if isinstance(nodes, list) else []:
                if (
                    isinstance(node, dict)
                    and node.get("use_type") == use_type
                    and node.get("node_id") == node_id
                ):
                    return node
        return None

    def record(self, kind: Kind, entity_id: int) -> JsonObject | None:
        """The entity's record: the civ's own, or with no civ the one most civs share."""
        if not self.has_stats:
            return None
        if kind == "tech":
            return tech_record(self.snapshot, entity_id)
        if self.civ is None:
            return self.units.any_record(entity_id)
        if self.index is None:
            return None
        return self.units.record(entity_id, self.index)


def build(
    old: Snapshot,
    new: Snapshot,
    kind: str,
    entity_id: int,
    civ: str | None,
    *,
    language: str = "en",
) -> JsonObject | None:
    """The details of a unit, building or tech; None when neither version has it."""
    if kind not in _USE_TYPES.values():
        return None
    entity_kind: Kind = kind  # type: ignore[assignment]  # checked against _USE_TYPES just above
    use_type = next(key for key, value in _USE_TYPES.items() if value == entity_kind)
    sides = (_side(old, civ, language), _side(new, civ, language))
    nodes = tuple(side.node(use_type, entity_id) if side.has_civ else None for side in sides)
    records = tuple(side.record(entity_kind, entity_id) for side in sides)
    present = tuple(
        record is not None or node is not None or _in_any_tree(side, use_type, entity_id)
        for side, record, node in zip(sides, records, nodes, strict=True)
    )
    if not any(present):
        return None
    naming = Naming(tuple((side.snapshot, side.names, side.units) for side in reversed(sides)))
    vocabulary = Vocabulary(new, old)
    lookup = Lookup(unit=naming.unit, tech=naming.tech, vocabulary=vocabulary, script=naming.script)
    attacked = attacked_classes((old, new))
    context = _Context(entity_kind, entity_id, use_type, naming, vocabulary, lookup, attacked)
    names = [
        _name(side, entity_kind, entity_id, node, record)
        for side, node, record in zip(sides, nodes, records, strict=True)
    ]
    new_node = nodes[1] or nodes[0]
    icon_node = new_node or sides[1].any_node(use_type, entity_id)
    icon_node = icon_node or sides[0].any_node(use_type, entity_id)
    trigger = _int(new_node.get("trigger_tech_id")) if new_node is not None else None
    # A version that can't say anything about the entity gives no rows.
    usable = tuple(
        record is not None and side.has_civ for side, record in zip(sides, records, strict=True)
    )
    per_side = [
        _side_parts(context, side, record, trigger) if ok else None
        for side, record, ok in zip(sides, records, usable, strict=True)
    ]
    return {
        "kind": entity_kind,
        "id": entity_id,
        "name": names[1] or names[0] or unknown_id(entity_id),
        "old_name": names[0] if names[0] and names[1] and names[0] != names[1] else None,
        "icon": _dict(icon_node.get("icon")) if icon_node is not None else None,
        "age": _int(new_node.get("age_id")) if new_node is not None else None,
        "civ": civ,
        "presence": "both" if all(present) else ("new" if present[1] else "old"),
        "available": {
            "old": _available(sides[0], nodes[0]),
            "new": _available(sides[1], nodes[1]),
        },
        "stats_missing": {"old": not sides[0].has_stats, "new": not sides[1].has_stats},
        "description": _description(sides, nodes),
        "sections": _merge_sections(context, per_side, trigger),
        "groups": _merge_groups(per_side),
        "scripts": _scripts(per_side),
        "note": Message("entity.note" if civ is not None else "entity.note_no_civ").to_json(),
    }


@dataclass(frozen=True, slots=True)
class _Context:
    """What every part of one entity's details needs."""

    kind: Kind
    id: int
    use_type: str
    naming: Naming
    vocabulary: Vocabulary
    lookup: Lookup
    # The classes some attack targets, in either version; other armour classes are left out.
    attacked: frozenset[int]


@dataclass(slots=True)
class _Parts:
    """One version's sections and sources."""

    sections: dict[str, list[_Row]]
    sources: dict[str, list[_Source]]
    scripts: list[str]


def _side(snapshot: Snapshot, civ: str | None, language: str) -> _Side:
    index = None
    if civ is not None:
        for entry in snapshot.civs:
            if isinstance(entry, Mapping) and entry.get("internal_name") == civ:
                index = _int(entry.get("index"))
    return _Side(snapshot, Names(snapshot, language), UnitLookup(snapshot), civ, index)


def _in_any_tree(side: _Side, use_type: str, entity_id: int) -> bool:
    return side.any_node(use_type, entity_id) is not None


def _available(side: _Side, node: JsonObject | None) -> bool | None:
    """Whether the civ's tree offers it; None when its tree doesn't list it at all.

    A unit outside every tree, such as a packed Trebuchet, may still be the civ's (D-37): only a
    node marked NotAvailable says the civ can't get it.
    """
    if side.civ is None or not side.has_civ or node is None:
        return None
    return node.get("node_status") != _UNAVAILABLE


def _name(
    side: _Side, kind: Kind, entity_id: int, node: JsonObject | None, record: JsonObject | None
) -> str | None:
    if node is not None:
        label = side.names.one_line(node.get("name_string_id"))
        if label:
            return label
    if kind == "tech":
        resolved = side.names.tech_name(record or tech_record(side.snapshot, entity_id), entity_id)
    else:
        unit = record or side.units.any_record(entity_id)
        resolved = side.names.one_line(at_path(unit, "language_dll_name"))
    if resolved:
        return resolved
    internal = node.get("name") if node is not None else None
    return internal if isinstance(internal, str) and internal else None


def _description(
    sides: tuple[_Side, _Side], nodes: tuple[JsonObject | None, ...]
) -> list[JsonValue]:
    """The game's help text without its title line and its stat lines, which are rows here."""
    for side, node in ((sides[1], nodes[1]), (sides[0], nodes[0])):
        template = side.names.help_text(node.get("help_string_id")) if node is not None else None
        if not template:
            continue
        lines: list[JsonValue] = []
        for line in parse(template)[1:]:
            if any(run.kind in _VALUE_RUNS for run in line):
                continue
            if not "".join(run.text for run in line).strip() and not any(
                run.kind == "static_cost" for run in line
            ):
                continue
            lines.append([run.to_json() for run in line])
        return lines
    return []


# --- one version ------------------------------------------------------------------------------


def _side_parts(
    context: _Context, side: _Side, record: JsonObject | None, trigger: int | None
) -> _Parts:
    assert record is not None  # the caller only asks for usable versions
    sections: dict[str, list[_Row]] = {}
    targets = [Target(context.kind, context.id, _int(record.get("class_")))]
    if context.kind == "tech":
        sections["research"] = _research(context, record)
        sections["effects"] = _effect_rows(
            context, effect_record(side.snapshot, record.get("effect_id")), None
        )
    else:
        sections["stats"] = _unit_stats(record, context.vocabulary, context.attacked)
        sections["cost"] = _costs(
            at_path(record, "creatable.resource_costs"),
            at_path(record, "creatable.train_locations"),
            "field.train_locations",
            "unit_id",
            "train_time",
            context.naming,
        )
        trigger_record = tech_record(side.snapshot, trigger) if trigger is not None else None
        if trigger is not None and trigger_record is not None:
            sections["upgrade"] = _research(context, trigger_record, requirements=False)
            targets.append(Target("tech", trigger))
    sources, scripts = _sources(context, side, targets)
    return _Parts(sections, sources, scripts)


def _research(context: _Context, tech: JsonObject, *, requirements: bool = True) -> list[_Row]:
    rows = _costs(
        tech.get("resource_costs"),
        tech.get("research_locations"),
        "field.research_locations",
        "location_id",
        "research_time",
        context.naming,
    )
    required = _required(tech, context.naming)
    if requirements and required:
        rows.append(_Row(("required",), Message("field.required_techs"), required))
    return rows


def _required(tech: JsonObject, naming: Naming, *, shown_only: bool = False) -> str | None:
    """Required techs by name; none when the count is 0 (its slots then hold placeholders).

    `shown_only` keeps the techs players see, for the short "Requires" line under a bonus.
    """
    if tech.get("required_tech_count") == 0:
        return None
    ids = tech.get("required_techs")
    numbers = [_int(item) for item in ids] if isinstance(ids, list) else []
    wanted = [item for item in numbers if item is not None and item >= 0]
    named = naming.shown_tech if shown_only else naming.tech
    found = [name for name in map(named, wanted) if name]
    # Tech names can hold commas ("C-Bonus, Free Chemistry"), so the list uses semicolons.
    return "; ".join(found) or None


def _costs(
    costs: JsonValue,
    locations: JsonValue,
    label: str,
    location_key: str,
    time_key: str,
    naming: Naming,
) -> list[_Row]:
    rows: list[_Row] = []
    for entry in costs if isinstance(costs, list) else []:
        if not isinstance(entry, dict) or not entry.get("flag"):
            continue
        resource = entry.get("type")
        name = RESOURCE_KEYS.get(resource) if isinstance(resource, int) else None
        rows.append(
            _Row(
                ("cost", str(resource)),
                Message("field.cost", {"resource": name or unknown_id(resource)}),
                entry.get("amount"),
                stat_icon=name,
            )
        )
    for entry in locations if isinstance(locations, list) else []:
        if not isinstance(entry, dict):
            continue
        location = _int(entry.get(location_key))
        if location is None or location < 0:
            continue
        rows.append(
            _Row(
                ("time", str(location)),
                Message(label, {"location": naming.unit(location)}),
                entry.get(time_key),
            )
        )
    return rows


def _unit_stats(record: JsonObject, vocabulary: Vocabulary, attacked: frozenset[int]) -> list[_Row]:
    """The stats a player reads, in the game's order; a stat the unit doesn't use is left out."""
    rows: list[_Row] = []

    def add(
        key: str,
        path: str,
        label: str,
        icon: str | None = None,
        *,
        keep: Callable[[float], bool] = lambda _: True,
    ) -> None:
        value = at_path(record, path)
        if _number(value) is not None and keep(float(value)):  # type: ignore[arg-type]  # a number
            rows.append(_Row((key,), Message(label), value, stat_icon=icon))

    def nonzero(value: float) -> bool:
        return value != 0

    attacks = _classes(at_path(record, "type_50.attacks"))
    ranged = (_number(at_path(record, "type_50.max_range")) or 0) > 0
    add("hp", "hit_points", "field.hit_points", "hp")
    if attacks or (_number(at_path(record, "type_50.displayed_attack")) or 0) != 0:
        add(
            "attack",
            "type_50.displayed_attack",
            "entity.attack",
            "pierce_attack" if ranged else "melee_attack",
        )
    for armour_class, amount in attacks:
        if amount != 0:
            rows.append(_class_row("attacks", armour_class, amount, vocabulary))
    add("melee_armour", "type_50.displayed_melee_armour", "entity.melee_armour", "melee_armor")
    add(
        "pierce_armour", "creatable.displayed_pierce_armour", "entity.pierce_armour", "pierce_armor"
    )
    # Having an armour class matters even at 0: an attack's bonus against it then applies. A class
    # nothing attacks changes no damage, so it is left out (D-50).
    for armour_class, amount in _classes(at_path(record, "type_50.armours")):
        if shown(armour_class, attacked, vocabulary):
            rows.append(_class_row("armours", armour_class, amount, vocabulary))
    if ranged:
        add("range", "type_50.max_range", "entity.range", "range")
        add("min_range", "type_50.min_range", "field.min_range", "range", keep=nonzero)
    if attacks:
        add("reload", "type_50.reload_time", "field.reload_time", "reload_time")
    if ranged:
        accuracy = _number(at_path(record, "type_50.accuracy_percent"))
        if accuracy is not None:
            rows.append(
                _Row(("accuracy",), Message("field.accuracy_percent"), f"{display(accuracy)}%")
            )
    if (_number(at_path(record, "type_50.blast_width")) or 0) > 0:
        add("blast_width", "type_50.blast_width", "field.blast_width", "blast_radius")
        add("blast_damage", "type_50.blast_damage", "field.blast_damage", "blast_radius")
    add("speed", "speed", "field.speed", "movement_speed", keep=nonzero)
    add("sight", "line_of_sight", "field.line_of_sight")
    add("garrison", "garrison_capacity", "field.garrison_capacity", "garrison", keep=nonzero)
    add(
        "conversion",
        "creatable.conversion_chance_mod",
        "field.conversion_chance_mod",
        "convert",
        keep=nonzero,
    )
    add("charge", "creatable.max_charge", "field.max_charge", keep=nonzero)
    if (_number(at_path(record, "creatable.max_charge")) or 0) > 0:
        add("recharge", "creatable.recharge_rate", "field.recharge_rate")
    add(
        "heal",
        "building.garrison_heal_rate",
        "field.garrison_heal_rate",
        "hp_regen",
        keep=nonzero,
    )
    unit_class = _int(record.get("class_"))
    if unit_class is not None:
        name = vocabulary.unit_class(unit_class) or unknown_id(unit_class)
        rows.append(_Row(("class",), Message("field.unit_class"), name))
    return rows


def _classes(entries: JsonValue) -> list[tuple[int, JsonValue]]:
    found: list[tuple[int, JsonValue]] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        armour_class = _int(entry.get("class_"))
        amount = entry.get("amount")
        if armour_class is not None and _number(amount) is not None:
            found.append((armour_class, amount))
    return found


def _class_row(
    kind: ClassKind, armour_class: int, amount: JsonValue, vocabulary: Vocabulary
) -> _Row:
    return _Row((kind, str(armour_class)), class_field(kind, armour_class, vocabulary), amount)


# --- what affects it --------------------------------------------------------------------------


def _sources(
    context: _Context, side: _Side, targets: list[Target]
) -> tuple[dict[str, list[_Source]], list[str]]:
    """The bonuses and techs that affect the targets in this version, by group; and the titles of
    the civ's scripted bonuses, which can't be matched to units."""
    found: dict[str, list[_Source]] = {group: [] for group in _GROUPS}
    scripts: list[str] = []
    techs = _records(side.snapshot, "techs")
    available, triggers = _researchable(side)
    owner = side.index if side.civ is not None else None

    def add(
        group: str, key: str, name: Message, effect_id: JsonValue, requires: str | None
    ) -> None:
        effect = effect_record(side.snapshot, effect_id)
        if effect is None:
            return
        if group in _CIV_GROUPS:
            for command in _commands(effect):
                number = script_number(command, context.vocabulary)
                if number is not None:
                    scripts.append(context.naming.script(number) or unknown_id(number))
        rows = _effect_rows(context, effect, targets)
        if rows:
            found[group].append(_Source(key, name, requires, rows))

    if owner is not None:
        civ_dat = _civ_dat(side.snapshot, owner)
        add(
            "civ",
            "tree",
            Message("field.tech_tree_effect"),
            civ_dat.get("tech_tree_effect_id"),
            None,
        )
        add(
            "team",
            "team",
            Message("field.team_bonus_effect"),
            civ_dat.get("team_bonus_effect_id"),
            None,
        )
        # The techs tied to the civ: its unique techs, its upgrades, and its bonuses, which are
        # techs of no tree ("C-Bonus, …").
        owned = sorted(
            (int(key), tech)
            for key, tech in techs.items()
            if key.lstrip("-").isdigit() and tech.get("civ") == owner
        )
        for tech_id, tech in owned:
            if tech_id in available or tech_id in triggers:
                continue
            add(
                "civ",
                f"tech:{tech_id}",
                _named(context, tech_id),
                tech.get("effect_id"),
                _required(tech, context.naming, shown_only=True),
            )
    for tech_id in [*available, *(t for t in triggers if t not in available)]:
        researchable = techs.get(str(tech_id))
        if researchable is None:
            continue
        tech = researchable
        slot = _int(tech.get("civ"))
        if slot is not None and slot > 0 and slot != owner:
            continue  # another civ's: with no civ chosen, only the techs no civ owns
        group = "unique" if slot is not None and slot > 0 and tech_id in available else "techs"
        add(
            group,
            f"tech:{tech_id}",
            _named(context, tech_id),
            tech.get("effect_id"),
            _required(tech, context.naming, shown_only=True),
        )
    if context.kind == "tech":
        scripts = []  # a scripted bonus may change a tech's cost, but that can't be told either
    return found, list(dict.fromkeys(scripts))


def _researchable(side: _Side) -> tuple[list[int], list[int]]:
    """The techs of the tree that the civ can research, and its upgrades' techs, in tree order.

    With no civ, those of every civ's tree.
    """
    techs: list[int] = []
    triggers: list[int] = []
    for nodes in side.trees():
        for node in nodes:
            if node.get("node_status") == _UNAVAILABLE:
                continue
            node_id = _int(node.get("node_id"))
            if node.get("use_type") == "Tech" and node_id is not None and node_id not in techs:
                techs.append(node_id)
            trigger = _int(node.get("trigger_tech_id"))
            if (
                node.get("node_type") == _UPGRADE_NODE
                and trigger is not None
                and trigger not in triggers
            ):
                triggers.append(trigger)
    return techs, triggers


def _named(context: _Context, tech_id: int) -> Message:
    return Message("entity.source", {"name": context.naming.tech(tech_id)})


def _effect_rows(
    context: _Context, effect: JsonObject | None, targets: list[Target] | None
) -> list[_Row]:
    """An effect's commands as sentences: all of them, or those that affect the targets.

    A command no template fits stays raw (O-5, layer 3); a row's key counts the same sentence
    repeated, so each is paired with its own counterpart in the other version.
    """
    rows: list[_Row] = []
    seen: dict[str, int] = {}
    for command in _commands(effect):
        if targets is not None and not any(
            affects(command, target, context.vocabulary) for target in targets
        ):
            continue
        sentence = describe(command, context.lookup)
        if sentence is None:
            label, value = Message("field.effect_command"), raw_pair(command, command)[1]
            # Paired by type and target, so one raw command added before another doesn't shift
            # every later one onto the wrong counterpart.
            slots = command if isinstance(command, dict) else {}
            identity = f"raw {slots.get('type')} {slots.get('a')} {slots.get('b')} {slots.get('c')}"
        else:
            label, value = sentence.label, sentence.value or ""
            identity = json.dumps(label.to_json(), sort_keys=True)
        count = seen.get(identity, 0)
        seen[identity] = count + 1
        rows.append(_Row((identity, str(count)), label, value))
    return rows


# --- merging the versions ---------------------------------------------------------------------


def _merge_sections(
    context: _Context, parts: list[_Parts | None], trigger: int | None
) -> list[JsonValue]:
    order = ["research", "effects"] if context.kind == "tech" else ["stats", "cost", "upgrade"]
    sections: list[JsonValue] = []
    for key in order:
        old, new = (part.sections.get(key) if part is not None else None for part in parts)
        if old is None and new is None:
            continue
        rows = _merge_rows(old, new)
        if not rows:
            continue
        title = (
            Message("entity.section.upgrade", {"tech": context.naming.tech(trigger)})
            if key == "upgrade" and trigger is not None
            else Message(f"entity.section.{key}")
        )
        sections.append({"key": key, "title": title.to_json(), "rows": rows})
    return sections


def _merge_groups(parts: list[_Parts | None]) -> list[JsonValue]:
    groups: list[JsonValue] = []
    for group in _GROUPS:
        sides = [part.sources[group] if part is not None else None for part in parts]
        old = {source.key: source for source in sides[0] or []}
        new = {source.key: source for source in sides[1] or []}
        merged: list[JsonValue] = []
        for key in _ordered(new, old):
            source = new.get(key) or old[key]
            old_rows = old[key].rows if key in old else ([] if sides[0] is not None else None)
            new_rows = new[key].rows if key in new else ([] if sides[1] is not None else None)
            merged.append(
                {
                    "key": key,
                    "name": source.name.to_json(),
                    "requires": source.requires,
                    "rows": _merge_rows(old_rows, new_rows),
                }
            )
        if merged:
            groups.append(
                {"key": group, "title": Message(_GROUP_TITLES[group]).to_json(), "sources": merged}
            )
    return groups


def _scripts(parts: list[_Parts | None]) -> list[JsonValue]:
    found: list[str] = []
    for part in reversed(parts):
        found.extend(part.scripts if part is not None else [])
    return list[JsonValue](dict.fromkeys(found))


def _merge_rows(old: list[_Row] | None, new: list[_Row] | None) -> list[JsonValue]:
    """Pair the versions' rows by key. A version with no rows to give (None) leaves the other's
    as they are; a version that has rows but not this one makes it new or gone."""
    if old is None or new is None:
        alone = new if new is not None else old or []
        return [_row(row, row.value, row.value, "same") for row in alone]
    before = {row.key: row for row in old}
    after = {row.key: row for row in new}
    merged: list[JsonValue] = []
    for key in _ordered(after, before):
        if key in before and key in after:
            was, now = before[key].value, after[key].value
            merged.append(_row(after[key], was, now, "same" if was == now else "changed"))
        elif key in after:
            merged.append(_row(after[key], None, after[key].value, "added"))
        else:
            merged.append(_row(before[key], before[key].value, None, "removed"))
    return merged


def _row(row: _Row, old: JsonValue, new: JsonValue, state: str) -> JsonObject:
    old_text: str | None
    new_text: str | None
    if old is not None and new is not None:
        old_text, new_text = pair(old, new)
    else:
        old_text = display(old) if old is not None else None
        new_text = display(new) if new is not None else None
    return {
        "field": row.field.to_json(),
        "stat_icon": row.stat_icon,
        "old": old_text,
        "new": new_text,
        "state": state,
    }


def _ordered[K](first: Mapping[K, object], second: Mapping[K, object]) -> Iterator[K]:
    """The keys of the newer version in its order, then those only the older one has."""
    yield from first
    yield from (key for key in second if key not in first)


# --- small readers ----------------------------------------------------------------------------


def _records(snapshot: Snapshot, section: str) -> dict[str, JsonObject]:
    records = (snapshot.stats or {}).get(section)
    if not isinstance(records, dict):
        return {}
    return {key: value for key, value in records.items() if isinstance(value, dict)}


def _civ_dat(snapshot: Snapshot, index: int) -> JsonObject:
    civ_dat = (snapshot.stats or {}).get("civ_dat")
    if isinstance(civ_dat, list) and 0 <= index < len(civ_dat) and isinstance(civ_dat[index], dict):
        return civ_dat[index]  # type: ignore[return-value]  # checked just above
    return {}


def _commands(effect: JsonObject | None) -> Iterable[JsonValue]:
    commands = effect.get("commands") if effect is not None else None
    return commands if isinstance(commands, list) else []


def _number(value: JsonValue) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def _int(value: JsonValue) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    return None


def _dict(value: JsonValue) -> JsonObject | None:
    return value if isinstance(value, dict) else None

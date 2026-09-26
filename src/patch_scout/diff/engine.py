# SPDX-License-Identifier: GPL-3.0-or-later
"""Compare two snapshots into a change set (diff-rules.md).

`compare` is pure: no I/O, and the same pair of snapshots always gives the same result, down to
the order of the changes. Everything user-visible is a catalog key, so the change set is
language-neutral (P-20).
"""

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Final

from patch_scout.diff import collapse as collapse_module
from patch_scout.diff.allowlist import RESOURCE_KEYS, TECH_FIELDS, UNIT_FIELDS, Field
from patch_scout.diff.model import (
    Change,
    ChangeSet,
    CivRef,
    Entity,
    Message,
    Notice,
    Scope,
    Side,
    sorted_changes,
)
from patch_scout.diff.names import Names, string_table
from patch_scout.diff.reachability import Reachable, UnitLookup, all_civs
from patch_scout.diff.values import at_path, pair, unknown_id, whitespace_only, words
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

logger = logging.getLogger(__name__)

# More than this share of the compared unit values changing raises a warning (diff-rules.md).
VOLUME_THRESHOLD: Final = 0.20
# Civ-specific lines come before global ones inside a category (diff-rules.md).
_CIV_FIRST: Final = 0
_GLOBAL: Final = 1


@dataclass(frozen=True, slots=True)
class Options:
    """What the reader asked to see."""

    show_unreachable: bool = False
    language: str = "en"


@dataclass(frozen=True, slots=True)
class SideInfo:
    """What the library index knows about a snapshot, which the snapshot itself must not (P-18)."""

    label: str | None = None
    prerelease: bool | None = None


@dataclass(slots=True)
class _Run:
    """The state one comparison builds up."""

    old: Snapshot
    new: Snapshot
    options: Options
    old_names: Names
    new_names: Names
    old_units: UnitLookup
    new_units: UnitLookup
    # A civ's slot differs between builds as soon as one is added before it, so each snapshot
    # keeps its own map. Civs themselves are matched by internal name (P-07).
    old_index: dict[str, int] = field(default_factory=dict)
    new_index: dict[str, int] = field(default_factory=dict)
    reachable: dict[str, Reachable] = field(default_factory=dict)
    changes: list[Change] = field(default_factory=list)
    notices: list[Notice] = field(default_factory=list)
    attached_strings: set[str] = field(default_factory=set)
    compared_values: int = 0
    changed_values: int = 0

    @property
    def civ_names(self) -> list[str]:
        """Every civ in either build, in the new build's order, then any the new build dropped."""
        names = list(self.new_index)
        names += [name for name in self.old_index if name not in self.new_index]
        return names

    @property
    def compare_stats(self) -> bool:
        """Stats are compared only when both snapshots have them (P-01)."""
        return self.old.stats_available and self.new.stats_available

    def add(self, change: Change) -> None:
        """Record one change."""
        self.changes.append(change)

    def spread(self, change: Change, scope: Scope) -> None:
        """Put a change on the pages it belongs to: each named civ, or Overall (D-44)."""
        if scope.kind == "some" and scope.civs:
            for internal_name in scope.civs:
                self.add(_with_civ(change, internal_name))
            return
        self.add(_with_civ(change, None))


def order(first: Snapshot, second: Snapshot) -> tuple[Snapshot, Snapshot]:
    """Put the older build first: lower game build, then earlier capture (D-32)."""
    if _build_key(second) < _build_key(first):
        return second, first
    return first, second


def compare(
    old: Snapshot,
    new: Snapshot,
    *,
    options: Options | None = None,
    old_info: SideInfo | None = None,
    new_info: SideInfo | None = None,
) -> ChangeSet:
    """Compare two snapshots and return everything the comparison shows."""
    run = _Run(
        old=old,
        new=new,
        options=options or Options(),
        old_names=Names(old, (options or Options()).language),
        new_names=Names(new, (options or Options()).language),
        old_units=UnitLookup(old),
        new_units=UnitLookup(new),
    )
    sides = (
        _side(old, old_info or SideInfo()),
        _side(new, new_info or SideInfo()),
    )
    if old.sources and old.sources == new.sources:
        return ChangeSet(old=sides[0], new=sides[1], identical=True)

    run.old_index = _civ_indices(old)
    run.new_index = _civ_indices(new)
    _notices(run)
    civ_refs = _civilizations(run)
    _availability(run)
    _bonuses(run)
    if run.compare_stats:
        _unit_stats(run)
        _techs(run)
        _other_effects(run)
    _strings(run)
    _volume(run)

    changes = tuple(sorted_changes(run.changes))
    counts: dict[str, int] = {}
    for change in changes:
        if change.civ is not None:
            counts[change.civ] = counts.get(change.civ, 0) + 1
    civs = tuple(
        CivRef(
            internal_name=ref.internal_name,
            name=ref.name,
            era=ref.era,
            icon=ref.icon,
            added=ref.added,
            count=counts.get(ref.internal_name, 0),
        )
        for ref in civ_refs
        if ref.added or counts.get(ref.internal_name, 0)
    )
    return ChangeSet(
        old=sides[0], new=sides[1], changes=changes, notices=tuple(run.notices), civs=civs
    )


# --- notices ---------------------------------------------------------------------------------


def _notices(run: _Run) -> None:
    for snapshot, which in ((run.old, "old"), (run.new, "new")):
        if not snapshot.stats_available:
            reason = snapshot.flags.get("stats_unavailable_reason")
            run.notices.append(
                Notice(
                    "stats_not_compared",
                    Message(
                        "notice.stats_not_compared",
                        {"side": which, "reason": reason if isinstance(reason, str) else ""},
                    ),
                )
            )
        elif snapshot.flags.get("format_verified") is False:
            run.notices.append(
                Notice(
                    "layout_substituted",
                    Message(
                        "notice.layout_substituted",
                        {
                            "side": which,
                            "found": _text(snapshot.meta.get("dat_format_version")),
                            "used": _text(snapshot.meta.get("dat_layout_version")),
                        },
                    ),
                )
            )


# --- category 1: civilizations ---------------------------------------------------------------


def _civilizations(run: _Run) -> list[CivRef]:
    old_civs = _civ_map(run.old)
    new_civs = _civ_map(run.new)
    refs: list[CivRef] = []
    for internal_name, civ in new_civs.items():
        name = run.new_names.one_line(civ.get("name_string_id")) or internal_name
        era = civ.get("era")
        icon = civ.get("emblem_icon")
        added = internal_name not in old_civs
        refs.append(
            CivRef(
                internal_name=internal_name,
                name=name,
                era=era if isinstance(era, str) else "base",
                icon=icon if isinstance(icon, dict) else None,
                added=added,
                count=0,
            )
        )
        entity = Entity("civ", internal_name, name, icon=icon if isinstance(icon, dict) else None)
        if added:
            run.add(
                Change(
                    category="civilizations",
                    kind="added",
                    entity=entity,
                    scope=Scope("some", (internal_name,)),
                    civ=internal_name,
                    sort_key=(_CIV_FIRST, "", ""),
                )
            )
            continue
        before = old_civs[internal_name]
        if before.get("era") != civ.get("era"):
            old_text, new_text = pair(before.get("era"), civ.get("era"))
            run.add(
                Change(
                    category="civilizations",
                    kind="modified",
                    entity=entity,
                    field=Message("field.era"),
                    old=old_text,
                    new=new_text,
                    scope=Scope("some", (internal_name,)),
                    civ=internal_name,
                    sort_key=(_CIV_FIRST, "", ""),
                )
            )
    for internal_name, civ in old_civs.items():
        if internal_name in new_civs:
            continue
        name = run.old_names.one_line(civ.get("name_string_id")) or internal_name
        run.add(
            Change(
                category="civilizations",
                kind="removed",
                entity=Entity("civ", internal_name, name),
                scope=Scope("some", (internal_name,)),
                sort_key=(_GLOBAL, "", ""),
            )
        )
    return refs


# --- category 2: availability ----------------------------------------------------------------

# What a tech tree node can change about itself, as (aspect key, catalog key).
NODE_FIELDS: Final = (
    ("node_status", "field.node_status"),
    ("age_id", "field.age"),
    ("building_id", "field.building"),
)


def _availability(run: _Run) -> None:
    civs = [name for name in run.civ_names if _has_tree(run, name)]
    keys: set[tuple[str, int]] = set()
    maps: dict[
        str, tuple[dict[tuple[str, int], JsonObject], dict[tuple[str, int], JsonObject]]
    ] = {}
    for internal_name in civs:
        old_nodes = _node_map(run.old, internal_name)
        new_nodes = _node_map(run.new, internal_name)
        maps[internal_name] = (old_nodes, new_nodes)
        keys |= set(old_nodes) | set(new_nodes)
    for key in sorted(keys):
        _node_changes(run, key, civs, maps)
    for internal_name in civs:
        _offers(run, internal_name)


def _node_changes(
    run: _Run,
    key: tuple[str, int],
    civs: Sequence[str],
    maps: Mapping[str, tuple[dict[tuple[str, int], JsonObject], dict[tuple[str, int], JsonObject]]],
) -> None:
    use_type, node_id = key
    in_scope = [name for name in civs if key in maps[name][0] or key in maps[name][1]]
    if not in_scope:
        return
    sample = next(
        (maps[name][1][key] for name in in_scope if key in maps[name][1]),
        next(maps[name][0][key] for name in in_scope if key in maps[name][0]),
    )
    names = run.new_names if any(key in maps[name][1] for name in in_scope) else run.old_names
    entity = Entity(
        kind=use_type.lower(),
        id=str(node_id),
        name=names.one_line(sample.get("name_string_id")) or unknown_id(node_id),
        where=_where(run, in_scope[0], use_type, node_id, sample.get("building_id")),
        icon=_icon_of(sample),
    )
    sort = (_CIV_FIRST, "", "")
    gained = [name for name in in_scope if key not in maps[name][0] and key in maps[name][1]]
    lost = [name for name in in_scope if key in maps[name][0] and key not in maps[name][1]]
    for civ_list, kind in ((gained, "added"), (lost, "removed")):
        if civ_list:
            scope = _scope_for(in_scope, civ_list)
            run.spread(
                Change("civ_availability", kind, entity, scope, sort_key=sort),  # type: ignore[arg-type]
                scope,
            )
    common = [name for name in in_scope if key in maps[name][0] and key in maps[name][1]]
    if not common:
        return
    for aspect, label in NODE_FIELDS:
        changed = {
            name: (maps[name][0][key].get(aspect), maps[name][1][key].get(aspect))
            for name in common
            if maps[name][0][key].get(aspect) != maps[name][1][key].get(aspect)
        }
        kind = "availability" if aspect == "node_status" else "modified"
        for group in collapse_module.collapse(common, changed):
            old_text, new_text = pair(group.old, group.new)
            run.spread(
                Change(
                    category="civ_availability",
                    kind=kind,  # type: ignore[arg-type]  # both are Kind members
                    entity=entity,
                    scope=group.scope,
                    field=Message(label),
                    old=old_text,
                    new=new_text,
                    sort_key=sort,
                ),
                group.scope,
            )
    _node_text(run, entity, key, common, maps, sort)
    _node_icons(run, entity, key, common, maps, sort)


def _node_text(
    run: _Run,
    entity: Entity,
    key: tuple[str, int],
    common: Sequence[str],
    maps: Mapping[str, tuple[dict[tuple[str, int], JsonObject], dict[tuple[str, int], JsonObject]]],
    sort: tuple[int, str, str],
) -> None:
    """A node's name and help text, reported next to the node, not as a loose string."""
    for aspect, label, resolver in (
        ("name_string_id", "field.name", "one_line"),
        ("help_string_id", "field.help_text", "help_text"),
    ):
        changed: dict[str, tuple[JsonValue, JsonValue]] = {}
        for name in common:
            old_id = maps[name][0][key].get(aspect)
            new_id = maps[name][1][key].get(aspect)
            _remember_string(run, old_id if resolver == "one_line" else _help_key(old_id))
            _remember_string(run, new_id if resolver == "one_line" else _help_key(new_id))
            old_text = getattr(run.old_names, resolver)(old_id)
            new_text = getattr(run.new_names, resolver)(new_id)
            if isinstance(old_text, str) and isinstance(new_text, str) and old_text != new_text:
                changed[name] = (old_text, new_text)
        for group in collapse_module.collapse(common, changed):
            run.spread(
                Change(
                    category="text",
                    kind="text_changed",
                    entity=entity,
                    scope=group.scope,
                    field=Message(label),
                    words=words(str(group.old), str(group.new)),
                    sort_key=sort,
                ),
                group.scope,
            )


def _node_icons(
    run: _Run,
    entity: Entity,
    key: tuple[str, int],
    common: Sequence[str],
    maps: Mapping[str, tuple[dict[tuple[str, int], JsonObject], dict[tuple[str, int], JsonObject]]],
    sort: tuple[int, str, str],
) -> None:
    """Icons redrawn or remapped, collapsed the same way as any other per-civ change (D-07)."""
    remapped: dict[str, tuple[JsonValue, JsonValue]] = {}
    redrawn: dict[str, tuple[JsonValue, JsonValue]] = {}
    for name in common:
        old_icon = _icon_of(maps[name][0][key])
        new_icon = _icon_of(maps[name][1][key])
        if old_icon is None or new_icon is None:
            continue
        if old_icon.get("hash") is None or new_icon.get("hash") is None:
            continue
        if old_icon.get("picture_index") != new_icon.get("picture_index"):
            remapped[name] = (old_icon.get("picture_index"), new_icon.get("picture_index"))
        elif old_icon.get("hash") != new_icon.get("hash"):
            redrawn[name] = ("", "")
    for group in collapse_module.collapse(common, remapped):
        old_text, new_text = pair(group.old, group.new)
        run.spread(
            Change(
                "icons",
                "icon_remapped",
                entity,
                group.scope,
                field=Message("field.icon"),
                old=old_text,
                new=new_text,
                sort_key=sort,
            ),
            group.scope,
        )
    for group in collapse_module.collapse(common, redrawn):
        run.spread(
            Change(
                "icons",
                "icon_redrawn",
                entity,
                group.scope,
                field=Message("field.icon"),
                sort_key=sort,
            ),
            group.scope,
        )


def _offers(run: _Run, internal_name: str) -> None:
    old_buildings = _offer_map(run.old, internal_name)
    new_buildings = _offer_map(run.new, internal_name)
    for building_id in sorted(set(old_buildings) | set(new_buildings)):
        before = old_buildings.get(building_id)
        after = new_buildings.get(building_id)
        source = after if after is not None else before
        if source is None:
            continue
        name = (
            run.new_names.node_name(internal_name, "Building", building_id)
            or _text(source.get("name"))
            or unknown_id(building_id)
        )
        entity = Entity("building", str(building_id), name)
        scope = Scope("some", (internal_name,))
        sort = (_CIV_FIRST, "", "")
        if before is None or after is None:
            run.add(
                Change(
                    category="civ_availability",
                    kind="added" if before is None else "removed",
                    entity=entity,
                    scope=scope,
                    field=Message("field.building_offer"),
                    civ=internal_name,
                    sort_key=sort,
                )
            )
            continue
        for list_key, label in (("units", "field.offered_units"), ("techs", "field.offered_techs")):
            gained, lost = _list_difference(before.get(list_key), after.get(list_key))
            if not gained and not lost:
                continue
            run.add(
                Change(
                    category="civ_availability",
                    kind="modified",
                    entity=entity,
                    scope=scope,
                    field=Message(label),
                    old=", ".join(unknown_id(item) for item in lost),
                    new=", ".join(unknown_id(item) for item in gained),
                    civ=internal_name,
                    sort_key=sort,
                )
            )


def _has_tree(run: _Run, internal_name: str) -> bool:
    return internal_name in run.old.tech_trees or internal_name in run.new.tech_trees


def _icon_of(node: JsonObject) -> JsonObject | None:
    icon = node.get("icon")
    return icon if isinstance(icon, dict) else None


def _scope_for(in_scope: Sequence[str], civs: Sequence[str]) -> Scope:
    """The scope for a change that either happened or did not, with no value pair."""
    groups = collapse_module.collapse(in_scope, dict.fromkeys(civs, (None, None)))
    return groups[0].scope if groups else Scope("some", tuple(civs))


# --- category 3: civ and team bonuses ---------------------------------------------------------


def _bonuses(run: _Run) -> None:
    old_civs = _civ_map(run.old)
    new_civs = _civ_map(run.new)
    for internal_name in sorted(set(old_civs) & set(new_civs)):
        before, after = old_civs[internal_name], new_civs[internal_name]
        name = run.new_names.one_line(after.get("name_string_id")) or internal_name
        icon = after.get("emblem_icon")
        entity = Entity("civ", internal_name, name, icon=icon if isinstance(icon, dict) else None)
        _bonus_text(run, internal_name, entity, before, after)
        if run.compare_stats:
            _civ_resources(run, internal_name, entity)
            _civ_effects(run, internal_name, entity, before, after)


def _bonus_text(
    run: _Run, internal_name: str, entity: Entity, before: JsonObject, after: JsonObject
) -> None:
    old_id, new_id = before.get("bonus_string_id"), after.get("bonus_string_id")
    old_text = run.old_names.text(old_id)
    new_text = run.new_names.text(new_id)
    _remember_string(run, old_id)
    _remember_string(run, new_id)
    if old_text is None or new_text is None or old_text == new_text:
        return
    run.add(
        Change(
            category="bonuses",
            kind="text_changed",
            entity=entity,
            scope=Scope("some", (internal_name,)),
            field=Message("field.civ_bonus_text"),
            words=words(old_text, new_text),
            civ=internal_name,
            sort_key=(_CIV_FIRST, "", ""),
        )
    )


def _civ_resources(run: _Run, internal_name: str, entity: Entity) -> None:
    before = _civ_dat(run.old, run.old_index.get(internal_name))
    after = _civ_dat(run.new, run.new_index.get(internal_name))
    if before is None or after is None:
        return
    old_values = before.get("resources")
    new_values = after.get("resources")
    if not isinstance(old_values, list) or not isinstance(new_values, list):
        return
    for position in range(max(len(old_values), len(new_values))):
        old_value = old_values[position] if position < len(old_values) else None
        new_value = new_values[position] if position < len(new_values) else None
        if old_value == new_value:
            continue
        old_text, new_text = pair(old_value, new_value)
        run.add(
            Change(
                category="bonuses",
                kind="modified",
                entity=entity,
                scope=Scope("some", (internal_name,)),
                field=Message("field.civ_resource", {"index": position}),
                old=old_text,
                new=new_text,
                civ=internal_name,
                sort_key=(_CIV_FIRST, "", f"{position:04d}"),
            )
        )


def _civ_effects(
    run: _Run, internal_name: str, entity: Entity, before: JsonObject, after: JsonObject
) -> None:
    old_civ_dat = _civ_dat(run.old, run.old_index.get(internal_name))
    new_civ_dat = _civ_dat(run.new, run.new_index.get(internal_name))
    if old_civ_dat is None or new_civ_dat is None:
        return
    for key, label in (
        ("tech_tree_effect_id", "field.tech_tree_effect"),
        ("team_bonus_effect_id", "field.team_bonus_effect"),
    ):
        old_id, new_id = old_civ_dat.get(key), new_civ_dat.get(key)
        for change in _effect_changes(
            run,
            entity,
            old_id,
            new_id,
            category="bonuses",
            label=Message(label),
            sort=(_CIV_FIRST, "", ""),
        ):
            run.add(_with_civ(change, internal_name))


# --- category 4: unit stats --------------------------------------------------------------------


def _unit_stats(run: _Run) -> None:
    civs = [(name, (run.old_index.get(name), run.new_index.get(name))) for name in run.civ_names]
    run.reachable = all_civs(run.old, run.new, civs, (run.old_units, run.new_units))
    unit_ids = sorted(set(run.old_units.unit_ids) | set(run.new_units.unit_ids))
    for unit_id in unit_ids:
        _unit_change(run, unit_id, civs)


def _unit_change(
    run: _Run, unit_id: int, civs: Sequence[tuple[str, tuple[int | None, int | None]]]
) -> None:
    in_scope: list[str] = []
    records: dict[str, tuple[JsonObject | None, JsonObject | None]] = {}
    for internal_name, (old_slot, new_slot) in civs:
        before = run.old_units.record(unit_id, old_slot) if old_slot is not None else None
        after = run.new_units.record(unit_id, new_slot) if new_slot is not None else None
        if before is None and after is None:
            continue
        reach = run.reachable.get(internal_name)
        shooters = reach.fired_by.get(unit_id, ()) if reach else ()
        reachable = bool(reach and (reach.includes(unit_id) or shooters))
        if not reachable and not run.options.show_unreachable:
            continue
        in_scope.append(internal_name)
        records[internal_name] = (before, after)
    if not in_scope:
        return
    name = run.new_names.record_name(run.new_units.any_record(unit_id), unit_id)
    entity = Entity("unit", str(unit_id), name, icon=_unit_icon(run, unit_id))
    _remember_string(run, at_path(run.new_units.any_record(unit_id), "language_dll_name"))
    for allow in UNIT_FIELDS:
        _field_change(run, entity, allow, in_scope, records, unit_id)


def _field_change(
    run: _Run,
    entity: Entity,
    allow: Field,
    in_scope: Sequence[str],
    records: Mapping[str, tuple[JsonObject | None, JsonObject | None]],
    unit_id: int,
) -> None:
    for sub_key, sub_label in _sub_fields(allow, records):
        changed: dict[str, tuple[JsonValue, JsonValue]] = {}
        for internal_name in in_scope:
            before, after = records[internal_name]
            old_value = _field_value(before, allow, sub_key)
            new_value = _field_value(after, allow, sub_key)
            run.compared_values += 1
            if old_value != new_value:
                run.changed_values += 1
                changed[internal_name] = (old_value, new_value)
        for group in collapse_module.collapse(in_scope, changed):
            old_text, new_text = pair(group.old, group.new)
            run.spread(
                Change(
                    category="unit_stats",
                    kind="modified",
                    entity=entity,
                    scope=group.scope,
                    field=sub_label,
                    stat_icon=allow.stat_icon,
                    old=old_text,
                    new=new_text,
                    sort_key=(
                        _CIV_FIRST if group.scope.kind == "some" else _GLOBAL,
                        "",
                        "",
                    ),
                ),
                group.scope,
            )


def _sub_fields(
    allow: Field, records: Mapping[str, tuple[JsonObject | None, JsonObject | None]]
) -> list[tuple[JsonValue, Message]]:
    """The value slots one allowlist entry produces: one, or one per class or resource."""
    if allow.kind == "value":
        return [(None, Message(allow.label))]
    keys: set[JsonValue] = set()
    for before, after in records.values():
        for record in (before, after):
            for entry in _entries(record, allow):
                key = _entry_key(entry, allow)
                if key is not None:
                    keys.add(key)
    ordered = sorted(keys, key=lambda item: (str(type(item)), str(item)))
    if allow.kind == "resource_costs":
        return [(key, Message("field.cost", {"resource": _resource_name(key)})) for key in ordered]
    if allow.kind == "train_locations":
        return [
            (key, Message(f"field.{allow.key}", {"location": unknown_id(key)})) for key in ordered
        ]
    return [(key, Message(allow.label, {"class": unknown_id(key)})) for key in ordered]


def _entries(record: JsonObject | None, allow: Field) -> list[JsonObject]:
    value = at_path(record, allow.path) if record is not None else None
    return [item for item in (value if isinstance(value, list) else []) if isinstance(item, dict)]


def _entry_key(entry: JsonObject, allow: Field) -> JsonValue:
    if allow.kind == "by_class":
        return entry.get("class_")
    if allow.kind == "resource_costs":
        return entry.get("type")
    return entry.get("unit_id") if "unit_id" in entry else entry.get("location_id")


def _field_value(record: JsonObject | None, allow: Field, sub_key: JsonValue) -> JsonValue:
    if record is None:
        return None
    if allow.kind == "value":
        return at_path(record, allow.path)
    for entry in _entries(record, allow):
        if _entry_key(entry, allow) != sub_key:
            continue
        if allow.kind == "resource_costs":
            return entry.get("amount") if entry.get("flag") else None
        if allow.kind == "train_locations":
            return entry.get("train_time", entry.get("research_time"))
        return entry.get("amount")
    return None


# --- category 5: techs -------------------------------------------------------------------------


def _techs(run: _Run) -> None:
    old_techs = _records(run.old, "techs")
    new_techs = _records(run.new, "techs")
    for key in sorted(set(old_techs) | set(new_techs), key=_numeric_key):
        before, after = old_techs.get(key), new_techs.get(key)
        source = after if after is not None else before
        if source is None:
            continue
        names = run.new_names if after is not None else run.old_names
        name = names.record_name(source, _numeric_key(key))
        entity = Entity("tech", key, name, icon=_node_icon(run, "Tech", _numeric_key(key)))
        _remember_string(run, source.get("language_dll_name"))
        sort = (_GLOBAL, "", "")
        if before is None or after is None:
            run.add(
                Change("techs", "added" if before is None else "removed", entity, sort_key=sort)
            )
            continue
        for allow in TECH_FIELDS:
            for sub_key, label in _sub_fields(allow, {"": (before, after)}):
                old_value = _field_value(before, allow, sub_key)
                new_value = _field_value(after, allow, sub_key)
                if old_value == new_value:
                    continue
                old_text, new_text = pair(old_value, new_value)
                run.add(
                    Change(
                        category="techs",
                        kind="modified",
                        entity=entity,
                        field=label,
                        old=old_text,
                        new=new_text,
                        sort_key=sort,
                    )
                )
        for change in _effect_changes(
            run,
            entity,
            before.get("effect_id"),
            after.get("effect_id"),
            category="techs",
            label=Message("field.tech_effect"),
            sort=sort,
        ):
            run.add(change)


# --- category 6: other effects -----------------------------------------------------------------


def _other_effects(run: _Run) -> None:
    reported = _reported_effect_ids(run)
    old_effects = _records(run.old, "effects")
    new_effects = _records(run.new, "effects")
    for key in sorted(set(old_effects) | set(new_effects), key=_numeric_key):
        if _numeric_key(key) in reported:
            continue
        before, after = old_effects.get(key), new_effects.get(key)
        if before is None or after is None or before == after:
            continue
        name = _text(after.get("name")) or unknown_id(key)
        entity = Entity("effect", key, name)
        for change in _command_changes(
            entity, before, after, "other_effects", Message("field.effect_command")
        ):
            run.add(change)


def _reported_effect_ids(run: _Run) -> set[int]:
    """Effect IDs already covered by the civ bonus and tech categories."""
    reported: set[int] = set()
    for snapshot in (run.old, run.new):
        stats = snapshot.stats or {}
        civ_dat = stats.get("civ_dat")
        for civ in civ_dat if isinstance(civ_dat, list) else []:
            if isinstance(civ, dict):
                for key in ("tech_tree_effect_id", "team_bonus_effect_id"):
                    value = civ.get(key)
                    if isinstance(value, int):
                        reported.add(value)
        techs = stats.get("techs")
        for tech in techs.values() if isinstance(techs, dict) else []:
            effect_id = tech.get("effect_id") if isinstance(tech, dict) else None
            if isinstance(effect_id, int):
                reported.add(effect_id)
    return reported


def _effect_changes(
    run: _Run,
    entity: Entity,
    old_id: JsonValue,
    new_id: JsonValue,
    *,
    category: str,
    label: Message,
    sort: tuple[int, str, str],
) -> list[Change]:
    """Compare the commands of the effect two records point at."""
    changes: list[Change] = []
    if old_id != new_id:
        old_text, new_text = pair(old_id, new_id)
        changes.append(
            Change(
                category=category,
                kind="modified",
                entity=entity,
                field=label,
                old=old_text,
                new=new_text,
                sort_key=sort,
            )
        )
    before = _effect(run.old, old_id)
    after = _effect(run.new, new_id)
    if before is None or after is None:
        return changes
    changes.extend(_command_changes(entity, before, after, category, label, sort))
    return changes


def _command_changes(
    entity: Entity,
    before: JsonObject,
    after: JsonObject,
    category: str,
    label: Message,
    sort: tuple[int, str, str] = (_GLOBAL, "", ""),
) -> list[Change]:
    """Effect commands are compared as ordered lists; each difference gets its own entry.

    No sentence is generated: the command type, attribute and class tables come from Advanced
    Genie Editor and are not yet verified, so the raw command is shown instead (O-5, layer 3).
    """
    old_commands = _commands(before)
    new_commands = _commands(after)
    effect_name = _text(after.get("name")) or _text(before.get("name"))
    changes: list[Change] = []
    for position in range(max(len(old_commands), len(new_commands))):
        old_command = old_commands[position] if position < len(old_commands) else None
        new_command = new_commands[position] if position < len(new_commands) else None
        if old_command == new_command:
            continue
        old_text, new_text = _command_pair(old_command, new_command)
        changes.append(
            Change(
                category=category,
                kind="modified",
                entity=entity,
                field=label,
                old=old_text,
                new=new_text,
                detail=Message(
                    "detail.effect_command",
                    {"effect": effect_name or "", "command": position},
                ),
                raw=f"command {position}",
                sort_key=sort,
            )
        )
    return changes


def _commands(effect: JsonObject) -> list[JsonValue]:
    commands = effect.get("commands")
    return list(commands) if isinstance(commands, list) else []


def _command_pair(old: JsonValue, new: JsonValue) -> tuple[str, str]:
    """Both sides of a raw command, formatted together so their numbers line up (O-5, layer 3)."""
    old_fields = old if isinstance(old, dict) else {}
    new_fields = new if isinstance(new, dict) else {}
    old_parts: list[str] = []
    new_parts: list[str] = []
    for key in ("type", "a", "b", "c", "d"):
        prefix = "type " if key == "type" else f"{key}="
        old_value, new_value = pair(old_fields.get(key), new_fields.get(key))
        old_parts.append(f"{prefix}{old_value}")
        new_parts.append(f"{prefix}{new_value}")
    return (
        " ".join(old_parts) if old_fields else "",
        " ".join(new_parts) if new_fields else "",
    )


# --- category 7: text --------------------------------------------------------------------------


def _strings(run: _Run) -> None:
    language = run.options.language
    old_table = string_table(run.old, language) or string_table(run.old)
    new_table = string_table(run.new, language) or string_table(run.new)
    for key in sorted(set(old_table) | set(new_table), key=_numeric_key):
        if key in run.attached_strings:
            continue
        old_value, new_value = old_table.get(key), new_table.get(key)
        if old_value == new_value:
            continue
        entity = Entity("string", key, key)
        if not isinstance(old_value, str) or not isinstance(new_value, str):
            run.add(
                Change(
                    category="text",
                    kind="added" if old_value is None else "removed",
                    entity=entity,
                    old=_text(old_value) or "",
                    new=_text(new_value) or "",
                    sort_key=(_GLOBAL, "", f"{_numeric_key(key):09d}"),
                )
            )
            continue
        run.add(
            Change(
                category="text",
                kind="text_changed",
                entity=entity,
                words=words(old_value, new_value),
                detail=Message("detail.whitespace_only")
                if whitespace_only(old_value, new_value)
                else None,
                sort_key=(_GLOBAL, "", f"{_numeric_key(key):09d}"),
            )
        )


# --- the change-volume check --------------------------------------------------------------------


def _volume(run: _Run) -> None:
    if run.compared_values == 0:
        return
    share = run.changed_values / run.compared_values
    if share <= VOLUME_THRESHOLD:
        return
    run.notices.append(
        Notice(
            "unusually_many_changes",
            Message(
                "notice.unusually_many_changes",
                {"percent": round(share * 100), "compared": run.compared_values},
            ),
        )
    )


# --- small helpers -------------------------------------------------------------------------------


def _resource_name(resource_type: JsonValue) -> str:
    """A resource by name where the ID is verified, otherwise `#<id>` (allowlist.py)."""
    if isinstance(resource_type, int) and resource_type in RESOURCE_KEYS:
        return RESOURCE_KEYS[resource_type]
    return unknown_id(resource_type)


def _with_civ(change: Change, internal_name: str | None) -> Change:
    return Change(
        category=change.category,
        kind=change.kind,
        entity=change.entity,
        scope=change.scope,
        field=change.field,
        stat_icon=change.stat_icon,
        old=change.old,
        new=change.new,
        words=change.words,
        detail=change.detail,
        raw=change.raw,
        civ=internal_name,
        sort_key=change.sort_key,
    )


def _side(snapshot: Snapshot, info: SideInfo) -> Side:
    label = info.label if info.label is not None else _text(snapshot.meta.get("label_at_capture"))
    prerelease = (
        info.prerelease
        if info.prerelease is not None
        else snapshot.meta.get("prerelease_at_capture") is True
    )
    return Side(
        capture_id=snapshot.capture_id,
        label=label or snapshot.capture_id,
        game_build=snapshot.game_build,
        captured_at=snapshot.captured_at,
        prerelease=prerelease,
        stats_available=snapshot.stats_available,
    )


def _build_key(snapshot: Snapshot) -> tuple[tuple[int, ...], str]:
    build = snapshot.game_build or ""
    parts = tuple(int(part) if part.isdigit() else -1 for part in build.split("."))
    return parts, snapshot.captured_at


def _civ_map(snapshot: Snapshot) -> dict[str, JsonObject]:
    found: dict[str, JsonObject] = {}
    for civ in snapshot.civs:
        if isinstance(civ, dict) and isinstance(civ.get("internal_name"), str):
            found[str(civ["internal_name"])] = civ
    return found


def _node_map(snapshot: Snapshot, internal_name: str) -> dict[tuple[str, int], JsonObject]:
    nodes = snapshot.tech_trees.get(internal_name)
    found: dict[tuple[str, int], JsonObject] = {}
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        use_type, node_id = node.get("use_type"), node.get("node_id")
        if isinstance(use_type, str) and isinstance(node_id, int):
            found[(use_type, node_id)] = node
    return found


def _offer_map(snapshot: Snapshot, internal_name: str) -> dict[int, JsonObject]:
    offers = snapshot.building_offers.get(internal_name)
    buildings = offers.get("buildings") if isinstance(offers, dict) else None
    found: dict[int, JsonObject] = {}
    for building in buildings if isinstance(buildings, list) else []:
        identifier = building.get("id") if isinstance(building, dict) else None
        if isinstance(building, dict) and isinstance(identifier, int):
            found[identifier] = building
    return found


def _records(snapshot: Snapshot, section: str) -> dict[str, JsonObject]:
    stats = snapshot.stats or {}
    records = stats.get(section)
    if not isinstance(records, dict):
        return {}
    return {key: value for key, value in records.items() if isinstance(value, dict)}


def _effect(snapshot: Snapshot, effect_id: JsonValue) -> JsonObject | None:
    if not isinstance(effect_id, int) or effect_id < 0:
        return None
    effect = _records(snapshot, "effects").get(str(effect_id))
    return effect


def _civ_dat(snapshot: Snapshot, index: int | None) -> JsonObject | None:
    stats = snapshot.stats or {}
    civ_dat = stats.get("civ_dat")
    if index is None or not isinstance(civ_dat, list) or not 0 <= index < len(civ_dat):
        return None
    entry = civ_dat[index]
    return entry if isinstance(entry, dict) else None


def _civ_indices(snapshot: Snapshot) -> dict[str, int]:
    """One snapshot's internal_name to civ slot map; the slot is only valid for that snapshot."""
    found: dict[str, int] = {}
    for civ in snapshot.civs:
        if not isinstance(civ, dict):
            continue
        name, index = civ.get("internal_name"), civ.get("index")
        if isinstance(name, str) and isinstance(index, int):
            found[name] = index
    return found


def _unit_icon(run: _Run, unit_id: int) -> JsonObject | None:
    """A unit's icon, from whichever civ's tech tree shows it as a unit or a building."""
    return _node_icon(run, "Unit", unit_id) or _node_icon(run, "Building", unit_id)


def _node_icon(run: _Run, use_type: str, node_id: int) -> JsonObject | None:
    """The icon a tech tree node carries, taken from the first civ that has that node."""
    for names in (run.new_names, run.old_names):
        for internal_name in run.civ_names:
            node = names.node(internal_name, use_type, node_id)
            icon = node.get("icon") if node else None
            if isinstance(icon, dict) and icon.get("hash"):
                return icon
    return None


def _building_name(run: _Run, internal_name: str, building_id: JsonValue) -> str | None:
    if not isinstance(building_id, int) or building_id < 0:
        return None
    return run.new_names.node_name(internal_name, "Building", building_id)


def _where(
    run: _Run, internal_name: str, use_type: str, node_id: int, building_id: JsonValue
) -> str | None:
    """Where a node is trained or researched; a building is not "made at itself"."""
    if use_type == "Building" and building_id == node_id:
        return None
    return _building_name(run, internal_name, building_id)


def _list_difference(
    before: JsonValue, after: JsonValue
) -> tuple[list[JsonValue], list[JsonValue]]:
    old_items = before if isinstance(before, list) else []
    new_items = after if isinstance(after, list) else []
    gained = [item for item in new_items if item not in old_items]
    lost = [item for item in old_items if item not in new_items]
    return gained, lost


def _remember_string(run: _Run, string_id: JsonValue) -> None:
    if isinstance(string_id, int):
        run.attached_strings.add(str(string_id))


def _help_key(help_string_id: JsonValue) -> JsonValue:
    return help_string_id - 79000 if isinstance(help_string_id, int) else None


def _text(value: JsonValue) -> str | None:
    return value if isinstance(value, str) else None


def _numeric_key(key: str) -> int:
    """Sort string keys the way their numbers read; non-numeric keys sort first."""
    return int(key) if key.lstrip("-").isdigit() else 0

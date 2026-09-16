# SPDX-License-Identifier: GPL-3.0-or-later
"""Which units a civ can actually get (D-37, diff-rules.md).

Captures keep every unit slot (P-03); the comparison narrows that to what a civ can reach, so a
change to a scenario-only object never shows up as a Franks change. Reachability is computed
from both snapshots, so a unit added or removed in one of them still counts.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from patch_scout.capture.stats_tier import apply_overrides
from patch_scout.diff.values import at_path
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

# Links followed from a reachable unit to another form of the same unit (D-37).
FORM_LINKS = ("building.transform_unit",)
# Links to the projectiles a unit fires. Projectiles are not units in the report: their changes
# are shown on the unit that fires them.
PROJECTILE_LINKS = (
    "type_50.projectile_unit_id",
    "creatable.secondary_projectile_unit",
    "creatable.charge_projectile_unit",
)


@dataclass(frozen=True, slots=True)
class Reachable:
    """What one civ can get, and which units fire which projectiles."""

    units: frozenset[int] = frozenset()
    projectiles: frozenset[int] = frozenset()
    fired_by: Mapping[int, tuple[int, ...]] = field(default_factory=dict)

    def includes(self, unit_id: int) -> bool:
        """Whether the civ can reach that unit."""
        return unit_id in self.units


class UnitLookup:
    """Reads unit records out of a snapshot's stats section, base plus overrides."""

    def __init__(self, snapshot: Snapshot) -> None:
        units = snapshot.stats.get("units") if snapshot.stats else None
        self._units: Mapping[str, JsonValue] = units if isinstance(units, dict) else {}
        self._cache: dict[tuple[int, int], JsonObject | None] = {}

    @property
    def unit_ids(self) -> list[int]:
        """Every unit ID the snapshot stores, sorted."""
        return sorted(int(key) for key in self._units if key.lstrip("-").isdigit())

    def entry(self, unit_id: int) -> JsonObject | None:
        """The stored base-and-overrides entry for a unit ID."""
        entry = self._units.get(str(unit_id))
        return entry if isinstance(entry, dict) else None

    def record(self, unit_id: int, civ_index: int) -> JsonObject | None:
        """One civ's full unit record, or None when that civ does not have the slot."""
        key = (unit_id, civ_index)
        if key not in self._cache:
            entry = self.entry(unit_id)
            self._cache[key] = apply_overrides(entry, civ_index) if entry is not None else None
        return self._cache[key]

    def any_record(self, unit_id: int) -> JsonObject | None:
        """The base record, for questions that do not depend on the civ."""
        entry = self.entry(unit_id)
        base = entry.get("base") if entry else None
        return base if isinstance(base, dict) else None


def seeds(snapshot: Snapshot, internal_name: str) -> set[int]:
    """The unit and building IDs a civ's tech tree and building offers name (D-37)."""
    found: set[int] = set()
    nodes = snapshot.tech_trees.get(internal_name)
    for node in nodes if isinstance(nodes, list) else []:
        if not isinstance(node, dict):
            continue
        node_id = node.get("node_id")
        if isinstance(node_id, int) and node.get("use_type") in ("Unit", "Building"):
            found.add(node_id)
    offers = snapshot.building_offers.get(internal_name)
    buildings = offers.get("buildings") if isinstance(offers, dict) else None
    for building in buildings if isinstance(buildings, list) else []:
        if not isinstance(building, dict):
            continue
        identifier = building.get("id")
        if isinstance(identifier, int):
            found.add(identifier)
        units = building.get("units")
        found.update(
            item for item in (units if isinstance(units, list) else []) if isinstance(item, int)
        )
    return found


def for_civ(
    old: Snapshot,
    new: Snapshot,
    internal_name: str,
    civ_index: int,
    lookups: tuple[UnitLookup, UnitLookup],
) -> Reachable:
    """Everything a civ can reach, following transform and dismount links until nothing is added."""
    frontier = seeds(old, internal_name) | seeds(new, internal_name)
    units: set[int] = set()
    while frontier:
        unit_id = frontier.pop()
        if unit_id in units:
            continue
        units.add(unit_id)
        for lookup in lookups:
            record = lookup.record(unit_id, civ_index)
            if record is None:
                continue
            frontier.update(_forms(record, lookup, civ_index) - units)
    projectiles: set[int] = set()
    fired_by: dict[int, list[int]] = {}
    for unit_id in sorted(units):
        for lookup in lookups:
            record = lookup.record(unit_id, civ_index)
            if record is None:
                continue
            for target in _projectiles(record):
                projectiles.add(target)
                shooters = fired_by.setdefault(target, [])
                if unit_id not in shooters:
                    shooters.append(unit_id)
    return Reachable(
        units=frozenset(units),
        projectiles=frozenset(projectiles),
        fired_by={key: tuple(value) for key, value in sorted(fired_by.items())},
    )


def _forms(record: JsonObject, lookup: UnitLookup, civ_index: int) -> set[int]:
    """The other forms of a unit: transform targets, and named dismount-style forms."""
    found: set[int] = set()
    for path in FORM_LINKS:
        target = at_path(record, path)
        if isinstance(target, int) and target > 0:
            found.add(target)
    blood = record.get("blood_unit_id")
    if isinstance(blood, int) and blood > 0:
        other = lookup.record(blood, civ_index)
        # Only a form the game names, e.g. Konnik (Dismounted); the rest are corpses (D-37).
        name_id = other.get("language_dll_name") if other is not None else None
        if isinstance(name_id, int) and name_id > 0:
            found.add(blood)
    return found


def _projectiles(record: JsonObject) -> set[int]:
    found: set[int] = set()
    for path in PROJECTILE_LINKS:
        target = at_path(record, path)
        if isinstance(target, int) and target > 0:
            found.add(target)
    return found


def all_civs(
    old: Snapshot,
    new: Snapshot,
    civs: Sequence[tuple[str, int]],
    lookups: tuple[UnitLookup, UnitLookup],
) -> dict[str, Reachable]:
    """Reachability for every civ, keyed by internal name."""
    return {
        internal_name: for_civ(old, new, internal_name, civ_index, lookups)
        for internal_name, civ_index in civs
    }

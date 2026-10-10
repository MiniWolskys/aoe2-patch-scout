# SPDX-License-Identifier: GPL-3.0-or-later
"""Names for the game's numeric IDs, from the snapshot's XS constants (game-files.md §11).

`Constants.xs` is the only file the game ships that names armour classes, unit attributes, unit
classes and effect command types. Its identifiers are game data, like unit names, so labels are
derived from them rather than written into the catalog (AGENTS.md rules 7 and 8). An ID the file
doesn't name has no name: the caller shows `#<id>`.
"""

import re
from typing import Final

from patch_scout.snapshot import JsonValue, Snapshot

# Section title -> (identifier prefix, identifier suffix, offset subtracted from the value).
_ARMOUR: Final = ("Damage Classes", "cDamageClass", "", 0)
_ATTRIBUTE: Final = ("Tech Effect Constants", "c", "", 0)
_UNIT_CLASS: Final = ("Object Classes", "c", "Class", 900)
_RESOURCE: Final = ("Attributes", "cAttribute", "", 0)
_COMMAND: Final = ("Effect Constants", "c", "", 0)

_WORD_START = re.compile(r"(?<=[a-z0-9])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])")


def label(identifier: str) -> str:
    """A readable label from a CamelCase identifier: `ShockInfantry` -> "Shock Infantry"."""
    return _WORD_START.sub(" ", identifier)


class Vocabulary:
    """Names from one or more snapshots; the first one that names an ID wins.

    The comparison passes the new snapshot first, then the old one, as it does for game names.
    """

    def __init__(self, *snapshots: Snapshot) -> None:
        self._tables: dict[tuple[str, str, str, int], dict[int, str]] = {}
        self._snapshots = snapshots

    def armour_class(self, identifier: JsonValue) -> str | None:
        """An attack or armour class, e.g. 29 -> "Shock Infantry"."""
        return self._label(_ARMOUR, identifier)

    def attribute(self, identifier: JsonValue) -> str | None:
        """A unit attribute (the `c` slot of an effect command), e.g. 44 -> "Blast Attack Level"."""
        return self._label(_ATTRIBUTE, identifier)

    def attribute_identifier(self, identifier: JsonValue) -> str | None:
        """A unit attribute's bare identifier, e.g. 9 -> "Attack"."""
        if not isinstance(identifier, int) or isinstance(identifier, bool):
            return None
        return self._table(_ATTRIBUTE).get(identifier)

    def unit_class(self, identifier: JsonValue) -> str | None:
        """A unit class as the `.dat` numbers it, e.g. 36 -> "Cavalry Archer"."""
        return self._label(_UNIT_CLASS, identifier)

    def resource_identifier(self, identifier: JsonValue) -> str | None:
        """A player resource's bare identifier, e.g. 33 -> "EffectFunctionNumber"."""
        if not isinstance(identifier, int) or isinstance(identifier, bool):
            return None
        return self._table(_RESOURCE).get(identifier)

    def resource(self, identifier: JsonValue) -> str | None:
        """A player resource, e.g. 0 -> "Food"."""
        return self._label(_RESOURCE, identifier)

    def command_type(self, identifier: JsonValue) -> str | None:
        """An effect command type's identifier, e.g. 4 -> "AddAttribute"."""
        if not isinstance(identifier, int) or isinstance(identifier, bool):
            return None
        return self._table(_COMMAND).get(identifier)

    def _label(self, kind: tuple[str, str, str, int], identifier: JsonValue) -> str | None:
        if not isinstance(identifier, int) or isinstance(identifier, bool):
            return None
        name = self._table(kind).get(identifier)
        return label(name) if name is not None else None

    def _table(self, kind: tuple[str, str, str, int]) -> dict[int, str]:
        table = self._tables.get(kind)
        if table is None:
            table = {}
            for snapshot in self._snapshots:
                for value, name in _entries(snapshot, kind):
                    table.setdefault(value, name)
            self._tables[kind] = table
        return table


def _entries(snapshot: Snapshot, kind: tuple[str, str, str, int]) -> list[tuple[int, str]]:
    """(ID, bare identifier) for one section; the first identifier for a value wins."""
    title, prefix, suffix, offset = kind
    constants = snapshot.scripts.get("constants")
    section = constants.get(title) if isinstance(constants, dict) else None
    found: list[tuple[int, str]] = []
    seen: set[int] = set()
    for item in section if isinstance(section, list) else []:
        if not (isinstance(item, list) and len(item) == 2):
            continue
        name, value = item
        if not isinstance(name, str) or not isinstance(value, int) or isinstance(value, bool):
            continue
        if not (name.startswith(prefix) and name.endswith(suffix)):
            continue
        bare = name[len(prefix) : len(name) - len(suffix)] if suffix else name[len(prefix) :]
        if not bare or value - offset in seen:
            continue
        seen.add(value - offset)
        found.append((value - offset, bare))
    return found

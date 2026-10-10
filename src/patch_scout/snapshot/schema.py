# SPDX-License-Identifier: GPL-3.0-or-later
"""The snapshot: one immutable, plain-JSON reading of one game install.

The sections and their rules are specified in docs/design/snapshot-format.md. A snapshot holds
plain JSON values only, so it stays readable after any future game format change (D-05).
"""

import re
from dataclasses import dataclass, field, fields
from typing import Final, Self

from patch_scout.errors import PatchScoutError

SCHEMA_VERSION: Final = 1
# A capture ID is also a file name, so it may only be a plain one (UUID4 hex in practice): an
# archive from someone else must never name a file outside the snapshots folder.
CAPTURE_ID: Final = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# The type each section must have; anything else is a damaged or foreign file.
_SECTION_TYPES: Final[dict[str, type | tuple[type, ...]]] = {
    "meta": dict,
    "sources": dict,
    "flags": dict,
    "civs": list,
    "tech_trees": dict,
    "building_offers": dict,
    "unit_lines": list,
    "linked_techs": list,
    "linked_units": list,
    "eras": list,
    "strings": dict,
    "stat_icons": dict,
    "stats": (dict, type(None)),
    "scripts": dict,
    "schema_version": int,
}

type JsonValue = bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"] | None
type JsonObject = dict[str, JsonValue]


class SnapshotFormatError(PatchScoutError):
    """A snapshot file isn't shaped the way the schema says."""


@dataclass(frozen=True, slots=True)
class Snapshot:
    """One capture. Every attribute is a plain JSON value; nothing here is computed."""

    meta: JsonObject
    sources: JsonObject
    flags: JsonObject
    civs: list[JsonValue] = field(default_factory=list)
    tech_trees: JsonObject = field(default_factory=dict)
    building_offers: JsonObject = field(default_factory=dict)
    unit_lines: list[JsonValue] = field(default_factory=list)
    linked_techs: list[JsonValue] = field(default_factory=list)
    linked_units: list[JsonValue] = field(default_factory=list)
    eras: list[JsonValue] = field(default_factory=list)
    strings: JsonObject = field(default_factory=dict)
    stat_icons: JsonObject = field(default_factory=dict)
    scripts: JsonObject = field(default_factory=dict)
    stats: JsonObject | None = None
    schema_version: int = SCHEMA_VERSION

    @property
    def capture_id(self) -> str:
        """The snapshot's ID, which is also its file name."""
        capture_id = _text(self.meta, "capture_id")
        if not CAPTURE_ID.match(capture_id):
            raise SnapshotFormatError(f"not a valid capture ID: {capture_id!r}")
        return capture_id

    @property
    def game_build(self) -> str | None:
        """The game build the capture read, or None when the exe couldn't be read."""
        value = self.meta.get("game_build")
        return value if isinstance(value, str) else None

    @property
    def captured_at(self) -> str:
        """When the capture ran, as an ISO 8601 UTC string."""
        return _text(self.meta, "captured_at")

    @property
    def stats_available(self) -> bool:
        """Whether the stats tier passed every gate."""
        return self.flags.get("stats_available") is True

    def to_json(self) -> JsonObject:
        """Return the snapshot as the JSON object that gets written to disk."""
        return {name.name: getattr(self, name.name) for name in fields(self)}

    @classmethod
    def from_json(cls, data: JsonValue) -> Self:
        """Rebuild a snapshot from a parsed JSON object, refusing anything else."""
        if not isinstance(data, dict):
            raise SnapshotFormatError("a snapshot must be a JSON object")
        known = {f.name for f in fields(cls)}
        unknown = sorted(set(data) - known)
        if unknown:
            raise SnapshotFormatError(f"unknown snapshot sections: {', '.join(unknown)}")
        missing = sorted({"meta", "sources", "flags"} - set(data))
        if missing:
            raise SnapshotFormatError(f"missing snapshot sections: {', '.join(missing)}")
        for name, value in data.items():
            if isinstance(value, bool) or not isinstance(value, _SECTION_TYPES[name]):
                raise SnapshotFormatError(f"snapshot section {name} has the wrong type")
        snapshot = cls(**data)  # type: ignore[arg-type]  # checked above; sections stay plain JSON
        snapshot.capture_id  # noqa: B018  # validates the ID, which is also a file name
        return snapshot


def _text(section: JsonObject, key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str):
        raise SnapshotFormatError(f"meta.{key} must be a string")
    return value

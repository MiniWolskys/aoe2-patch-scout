# SPDX-License-Identifier: GPL-3.0-or-later
"""The snapshot: one immutable, plain-JSON reading of one game install.

The sections and their rules are specified in docs/design/snapshot-format.md. A snapshot holds
plain JSON values only, so it stays readable after any future game format change (D-05).
"""

from dataclasses import dataclass, field, fields
from typing import Final, Self

from patch_scout.errors import PatchScoutError

SCHEMA_VERSION: Final = 1

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
    stats: JsonObject | None = None
    schema_version: int = SCHEMA_VERSION

    @property
    def capture_id(self) -> str:
        """The snapshot's ID, which is also its file name."""
        return _text(self.meta, "capture_id")

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
        return cls(**data)  # type: ignore[arg-type]  # checked above; sections stay plain JSON


def _text(section: JsonObject, key: str) -> str:
    value = section.get(key)
    if not isinstance(value, str):
        raise SnapshotFormatError(f"meta.{key} must be a string")
    return value

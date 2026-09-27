# SPDX-License-Identifier: GPL-3.0-or-later
"""The change set: plain, language-neutral data describing what changed (diff-rules.md).

No user-visible English lives here. Labels are `Message`s, a catalog key plus its values, so the
same change set renders in any language the app grows (O-3, P-20).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from patch_scout.snapshot import JsonObject, JsonValue

# Categories, in the order the comparison shows them (diff-rules.md).
CATEGORIES: Final = (
    "civilizations",
    "civ_availability",
    "bonuses",
    "unit_stats",
    "techs",
    "other_effects",
    "text",
    "icons",
)
# Categories collapsed by default.
LOW_PRIORITY: Final = frozenset({"text", "icons"})

type Kind = Literal[
    "added",
    "removed",
    "availability",
    "modified",
    "renamed",
    "text_changed",
    "icon_redrawn",
    "icon_remapped",
]
# "all" and "all_except" count every civ in the comparison; "having" and "having_except" count
# only the civs that have the entity, when there are too many of them to name.
type ScopeKind = Literal["global", "all", "all_except", "having", "having_except", "some"]


@dataclass(frozen=True, slots=True)
class Message:
    """A catalog key and the values its placeholders need."""

    key: str
    args: dict[str, JsonValue] = field(default_factory=dict)

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {"key": self.key, "args": dict(self.args)}


@dataclass(frozen=True, slots=True)
class Entity:
    """What a change is about: a civ, a unit, a tech, a building, a string or an effect."""

    kind: str
    id: str
    name: str
    where: str | None = None
    icon: JsonObject | None = None
    # False when the game gives the entity no usable name and `name` is only `#<id>`: such
    # changes are hidden unless the reader asks for them (diff-rules.md, Values and formatting).
    named: bool = True

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {
            "kind": self.kind,
            "id": self.id,
            "name": self.name,
            "where": self.where,
            "icon": self.icon,
            "named": self.named,
        }


@dataclass(frozen=True, slots=True)
class Scope:
    """Which civs a change applies to, already collapsed (D-07)."""

    kind: ScopeKind = "global"
    civs: tuple[str, ...] = ()
    # How many civs have the entity; set for "having" and "having_except" only.
    count: int = 0

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {"kind": self.kind, "civs": list(self.civs), "count": self.count}

    @property
    def affected(self) -> tuple[str, ...]:
        """The civs named in the scope; empty for a global or all-civs change."""
        return self.civs if self.kind in ("some", "all_except", "having_except") else ()


@dataclass(frozen=True, slots=True)
class WordDiff:
    """One run of a word-level text diff."""

    kind: Literal["same", "removed", "added"]
    text: str

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {"kind": self.kind, "text": self.text}


@dataclass(frozen=True, slots=True)
class Change:
    """One reported change."""

    category: str
    kind: Kind
    entity: Entity
    scope: Scope = Scope()
    field: Message | None = None
    stat_icon: str | None = None
    old: str | None = None
    new: str | None = None
    words: tuple[WordDiff, ...] = ()
    detail: Message | None = None
    raw: str | None = None
    civ: str | None = None
    sort_key: tuple[int, str, str] = (0, "", "")

    @property
    def low_priority(self) -> bool:
        """Whether the comparison collapses this change by default."""
        return self.category in LOW_PRIORITY

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {
            "category": self.category,
            "kind": self.kind,
            "entity": self.entity.to_json(),
            "scope": self.scope.to_json(),
            "field": self.field.to_json() if self.field else None,
            "stat_icon": self.stat_icon,
            "old": self.old,
            "new": self.new,
            "words": [word.to_json() for word in self.words],
            "detail": self.detail.to_json() if self.detail else None,
            "raw": self.raw,
            "civ": self.civ,
            "low_priority": self.low_priority,
        }


@dataclass(frozen=True, slots=True)
class Entry:
    """One entity's changes on one page with one scope: what a reader sees as one item.

    Built from the field-level changes by `entries.group`; the renderers draw entries, while the
    change set keeps every field-level change for tests and the raw view.
    """

    category: str
    kind: Kind
    entity: Entity
    scope: Scope
    civ: str | None
    changes: tuple[Change, ...]
    # Values a new or removed entity's entry leaves out: defaults, and fields that aren't main
    # stats (diff-rules.md, One entry per entity).
    hidden: int = 0

    @property
    def low_priority(self) -> bool:
        """Whether the comparison collapses this entry by default."""
        return self.category in LOW_PRIORITY

    def to_json(self, positions: Mapping[int, int]) -> JsonObject:
        """The form the GUI reads: its changes as positions in the change set's `changes` list.

        `positions` maps `id(change)` to that position, so no change is written twice.
        """
        return {
            "category": self.category,
            "kind": self.kind,
            "entity": self.entity.to_json(),
            "scope": self.scope.to_json(),
            "civ": self.civ,
            "changes": [
                positions[id(change)] for change in self.changes if id(change) in positions
            ],
            "hidden": self.hidden,
            "low_priority": self.low_priority,
        }


@dataclass(frozen=True, slots=True)
class Notice:
    """Something the reader must know before reading the changes."""

    kind: str
    message: Message

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {"kind": self.kind, "message": self.message.to_json()}


@dataclass(frozen=True, slots=True)
class Side:
    """One of the two versions being compared, as the header shows it."""

    capture_id: str
    label: str
    game_build: str | None
    captured_at: str
    prerelease: bool
    stats_available: bool

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {
            "capture_id": self.capture_id,
            "label": self.label,
            "game_build": self.game_build,
            "captured_at": self.captured_at,
            "prerelease": self.prerelease,
            "stats_available": self.stats_available,
        }


@dataclass(frozen=True, slots=True)
class CivRef:
    """A civ in the comparison's navigation list (D-33)."""

    internal_name: str
    name: str
    era: str
    icon: JsonObject | None
    added: bool
    count: int

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        return {
            "internal_name": self.internal_name,
            "name": self.name,
            "era": self.era,
            "icon": self.icon,
            "added": self.added,
            "count": self.count,
        }


@dataclass(frozen=True, slots=True)
class ChangeSet:
    """Everything a comparison produced, in a deterministic order."""

    old: Side
    new: Side
    changes: tuple[Change, ...] = ()
    notices: tuple[Notice, ...] = ()
    civs: tuple[CivRef, ...] = ()
    identical: bool = False
    # The changes grouped one entry per entity (diff-rules.md); what the renderers draw.
    entries: tuple[Entry, ...] = ()

    @property
    def overall_count(self) -> int:
        """How many entries are not tied to a single civ."""
        return sum(1 for entry in self.entries if entry.civ is None)

    def for_civ(self, internal_name: str | None) -> list[Change]:
        """The changes shown on one civ's page, or on Overall when `internal_name` is None."""
        return [change for change in self.changes if change.civ == internal_name]

    def entries_for(self, internal_name: str | None) -> list[Entry]:
        """The entries shown on one civ's page, or on Overall when `internal_name` is None."""
        return [entry for entry in self.entries if entry.civ == internal_name]

    def to_json(self) -> JsonObject:
        """The form the GUI and the exports read."""
        positions = {id(change): position for position, change in enumerate(self.changes)}
        return {
            "old": self.old.to_json(),
            "new": self.new.to_json(),
            "identical": self.identical,
            "notices": [notice.to_json() for notice in self.notices],
            "civs": [civ.to_json() for civ in self.civs],
            "changes": [change.to_json() for change in self.changes],
            "entries": [entry.to_json(positions) for entry in self.entries],
            "counts": {"overall": self.overall_count, "total": len(self.entries)},
        }


def sorted_changes(changes: list[Change]) -> list[Change]:
    """Order changes the way the comparison and the exports show them (diff-rules.md).

    Category first, then civ-specific before global, then the entity's display name and ID.
    """
    order = {name: index for index, name in enumerate(CATEGORIES)}
    return sorted(
        changes,
        key=lambda change: (
            order.get(change.category, len(CATEGORIES)),
            change.sort_key,
            change.entity.name,
            change.entity.id,
            change.field.key if change.field else "",
        ),
    )

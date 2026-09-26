# SPDX-License-Identifier: GPL-3.0-or-later
"""Resolve the names the comparison shows, from the snapshots' own string tables.

Game names always come from `strings.tables[<lang>]`, falling back to English (O-3). An ID with
no name is shown as `#<id>`, never guessed (diff-rules.md, "Values and formatting").
"""

from collections.abc import Mapping
from typing import Final

from patch_scout.diff.values import at_path, unknown_id
from patch_scout.snapshot import JsonObject, JsonValue, Snapshot

FALLBACK_LANGUAGE: Final = "en"
# Tech tree labels wrap onto two lines in the game's own interface; reports want one line.
_LINE_BREAK: Final = "\\n"


class Names:
    """Looks names up in one snapshot, preferring the new build's text."""

    def __init__(self, snapshot: Snapshot, language: str = FALLBACK_LANGUAGE) -> None:
        self._tables = _tables(snapshot)
        self._language = language
        self._nodes: dict[tuple[str, str, int], JsonObject] = {}
        for internal_name, nodes in snapshot.tech_trees.items():
            for node in nodes if isinstance(nodes, list) else []:
                if not isinstance(node, dict):
                    continue
                use_type, node_id = node.get("use_type"), node.get("node_id")
                if isinstance(use_type, str) and isinstance(node_id, int):
                    self._nodes.setdefault((internal_name, use_type, node_id), node)

    def text(self, string_id: JsonValue) -> str | None:
        """One string by ID, in the chosen language, falling back to English."""
        if not isinstance(string_id, int):
            return None
        key = str(string_id)
        for language in (self._language, FALLBACK_LANGUAGE):
            table = self._tables.get(language)
            if isinstance(table, dict):
                value = table.get(key)
                if isinstance(value, str):
                    return value
        return None

    def help_text(self, help_string_id: JsonValue) -> str | None:
        """A tech tree help text: the ID resolves at `id - 79000` (game-files.md §5)."""
        if not isinstance(help_string_id, int):
            return None
        return self.text(help_string_id - 79000)

    def one_line(self, string_id: JsonValue) -> str | None:
        """A name with the game's line break turned into a space."""
        value = self.text(string_id)
        return value.replace(_LINE_BREAK, " ").strip() if value is not None else None

    def node(self, internal_name: str, use_type: str, node_id: int) -> JsonObject | None:
        """One civ's tech tree node, by its identity (P-07)."""
        return self._nodes.get((internal_name, use_type, node_id))

    def node_name(self, internal_name: str, use_type: str, node_id: int) -> str | None:
        """The label a civ's tech tree shows for a node."""
        node = self.node(internal_name, use_type, node_id)
        return self.one_line(node.get("name_string_id")) if node else None

    def record_name(self, record: JsonObject | None, identifier: int) -> str:
        """The name of a unit or tech record, or `#<id>` when it has none."""
        if record is not None:
            resolved = self.one_line(at_path(record, "language_dll_name"))
            if resolved:
                return resolved
        return unknown_id(identifier)


def _tables(snapshot: Snapshot) -> Mapping[str, JsonValue]:
    tables = snapshot.strings.get("tables")
    return tables if isinstance(tables, dict) else {}


def string_table(snapshot: Snapshot, language: str = FALLBACK_LANGUAGE) -> Mapping[str, JsonValue]:
    """One language's full table, for the string comparison (P-04)."""
    table = _tables(snapshot).get(language)
    return table if isinstance(table, dict) else {}

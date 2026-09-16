# SPDX-License-Identifier: GPL-3.0-or-later
"""Parse the game's key-value string files (game-files.md §9).

Line format: `<key> "<text>"`, with anything after the closing quote ignored. Keys are usually
numeric but not always, `//` starts a comment, and a key can appear twice: the last one wins,
which is what the game shows. Text is stored raw, with its tags and placeholders intact.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Final

from patch_scout.capture.inputs import InputReader
from patch_scout.snapshot import JsonObject

logger = logging.getLogger(__name__)

# game-files.md §9: every non-comment, non-blank line of the real files matches this.
ENTRY: Final = re.compile(r'^(\S+)\s+"((?:[^"\\]|\\.)*)"')

MAIN_FILE: Final = "key-value-strings-utf8.txt"
PAPHOS_FILE: Final = "key-value-paphos-strings-utf8.txt"
NON_LOCALIZED: Final = (
    "resources/_common/strings/key-value/non-localized-key-value-strings-utf8.txt"
)


@dataclass(frozen=True, slots=True)
class StringTable:
    """One language's strings, plus the keys that appeared more than once."""

    entries: dict[str, str] = field(default_factory=dict)
    duplicates: list[str] = field(default_factory=list)


def language_folder(language: str) -> str:
    """Where one language's string files live."""
    return f"resources/{language}/strings/key-value"


def parse(text: str) -> StringTable:
    """Parse one string file; later entries with the same key replace earlier ones."""
    entries: dict[str, str] = {}
    duplicates: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        match = ENTRY.match(stripped)
        if match is None:
            continue
        key, value = match.group(1), match.group(2)
        if key in entries:
            duplicates.append(key)
        entries[key] = value
    return StringTable(entries=entries, duplicates=duplicates)


def read_language(
    reader: InputReader, language: str, *, required: bool = True
) -> tuple[StringTable, list[str]]:
    """Merge one language's main, Chronicles and non-localized files into one table.

    Returns the table and the warnings worth showing: duplicate keys inside a file, and keys
    that two files disagree about. The main file is required for the language the app reads
    names from; a language that simply is not installed is a warning, not a failure.
    """
    folder = language_folder(language)
    merged: dict[str, str] = {}
    duplicates: list[str] = []
    warnings: list[str] = []
    files = [
        (f"{folder}/{MAIN_FILE}", required),
        (f"{folder}/{PAPHOS_FILE}", False),
        (NON_LOCALIZED, False),
    ]
    for relative, required in files:
        text = reader.read_text(relative, required=required)
        if text is None:
            warnings.append(f"string file not found: {relative}")
            continue
        table = parse(text)
        if table.duplicates:
            unique = sorted(set(table.duplicates))
            duplicates.extend(unique)
            warnings.append(f"{relative}: {len(unique)} duplicate keys, the last one wins")
        overlapping = sorted(key for key in table.entries if key in merged)
        if overlapping:
            warnings.append(f"{relative}: {len(overlapping)} keys also in an earlier file")
            duplicates.extend(overlapping)
        merged.update(table.entries)
    return StringTable(entries=merged, duplicates=sorted(set(duplicates))), warnings


def read(reader: InputReader, languages: tuple[str, ...] = ("en",)) -> tuple[JsonObject, list[str]]:
    """Build the snapshot's `strings` section for the languages asked for (O-3)."""
    tables: JsonObject = {}
    duplicates: JsonObject = {}
    warnings: list[str] = []
    for index, language in enumerate(languages):
        table, language_warnings = read_language(reader, language, required=index == 0)
        tables[language] = dict(table.entries)
        duplicates[language] = list(table.duplicates)
        warnings.extend(language_warnings)
    return {"tables": tables, "duplicates": duplicates}, warnings


def lookup(table: JsonObject, string_id: int | None) -> str | None:
    """Resolve a string ID against one language table; None when it does not resolve."""
    if string_id is None:
        return None
    value = table.get(str(string_id))
    return value if isinstance(value, str) else None

# SPDX-License-Identifier: GPL-3.0-or-later
"""The library index: the metadata a user can edit after a capture (P-18).

Snapshot files are immutable, so labels, the pre-release tickbox and notes live here. A lost or
corrupted index is rebuilt from the snapshot files, using each one's `meta.*_at_capture`.
"""

import json
import logging
from dataclasses import asdict, dataclass, replace
from datetime import UTC, datetime
from typing import Final, Literal, Self

from patch_scout.errors import PatchScoutError
from patch_scout.snapshot import JsonValue, Snapshot
from patch_scout.store.paths import DataFolder
from patch_scout.store.snapshots import SnapshotStore

logger = logging.getLogger(__name__)

INDEX_VERSION: Final = 1


class UnknownVersionError(PatchScoutError):
    """The library index has no entry for that capture."""


type Origin = Literal["captured", "imported", "baseline"]


@dataclass(frozen=True, slots=True)
class LibraryEntry:
    """What the user can change about one capture."""

    capture_id: str
    label: str
    prerelease: bool
    notes: str
    origin: Origin
    added_at: str

    @classmethod
    def for_snapshot(cls, snapshot: Snapshot, origin: Origin = "captured") -> Self:
        """Build the entry a freshly stored snapshot starts with."""
        label = snapshot.meta.get("label_at_capture")
        return cls(
            capture_id=snapshot.capture_id,
            label=label if isinstance(label, str) else snapshot.capture_id,
            prerelease=snapshot.meta.get("prerelease_at_capture") is True,
            notes="",
            origin=origin,
            added_at=now_iso(),
        )


def now_iso() -> str:
    """The current UTC time, in the form snapshots and the index use."""
    return datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")


class Library:
    """The library index in one data folder, kept in sync with `library.json`."""

    def __init__(self, folder: DataFolder) -> None:
        self._folder = folder
        self._entries: dict[str, LibraryEntry] = {}
        self._loaded = False

    def reload(self) -> None:
        """Forget the cached entries, so the next read comes from the file.

        A capture adds its entry through its own `Library`, so a long-lived one, such as the
        GUI's, has to be told that the file changed.
        """
        self._loaded = False
        self._entries = {}

    def entries(self) -> list[LibraryEntry]:
        """Every entry, in capture-ID order."""
        self._ensure_loaded()
        return [self._entries[key] for key in sorted(self._entries)]

    def get(self, capture_id: str) -> LibraryEntry | None:
        """One entry, or None when the index doesn't know that capture."""
        self._ensure_loaded()
        return self._entries.get(capture_id)

    def add(self, entry: LibraryEntry) -> LibraryEntry:
        """Add or replace an entry and save the index."""
        self._ensure_loaded()
        self._entries[entry.capture_id] = entry
        self._save()
        return entry

    def update(
        self,
        capture_id: str,
        *,
        label: str | None = None,
        prerelease: bool | None = None,
        notes: str | None = None,
    ) -> LibraryEntry:
        """Change the editable fields of one entry."""
        self._ensure_loaded()
        if capture_id not in self._entries:
            # Another Library may have added it since this one last read the file.
            self.reload()
            self._ensure_loaded()
        if capture_id not in self._entries:
            raise UnknownVersionError(capture_id)
        entry = self._entries[capture_id]
        if label is not None:
            entry = replace(entry, label=label)
        if prerelease is not None:
            entry = replace(entry, prerelease=prerelease)
        if notes is not None:
            entry = replace(entry, notes=notes)
        self._entries[capture_id] = entry
        self._save()
        return entry

    def remove(self, capture_id: str) -> None:
        """Drop an entry and save the index."""
        self._ensure_loaded()
        self._entries.pop(capture_id, None)
        self._save()

    def rebuild_from(self, store: SnapshotStore) -> None:
        """Rebuild the index from the snapshot files, keeping any entry already known."""
        self._ensure_loaded()
        for capture_id in store.capture_ids():
            if capture_id in self._entries:
                continue
            self._entries[capture_id] = LibraryEntry.for_snapshot(store.load(capture_id))
        for capture_id in set(self._entries) - set(store.capture_ids()):
            del self._entries[capture_id]
        self._save()

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        path = self._folder.library_file
        if not path.is_file():
            return
        try:
            data: JsonValue = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            logger.exception("the library index couldn't be read; it will be rebuilt")
            return
        self._entries = dict(_read_entries(data))

    def _save(self) -> None:
        self._folder.root.mkdir(parents=True, exist_ok=True)
        payload = {
            "version": INDEX_VERSION,
            "entries": {
                entry.capture_id: {
                    key: value for key, value in asdict(entry).items() if key != "capture_id"
                }
                for entry in self.entries()
            },
        }
        path = self._folder.library_file
        temporary = path.with_name(path.name + ".part")
        temporary.write_text(
            json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        temporary.replace(path)


def _read_entries(data: JsonValue) -> list[tuple[str, LibraryEntry]]:
    if not isinstance(data, dict):
        return []
    entries = data.get("entries")
    if not isinstance(entries, dict):
        return []
    result = []
    for capture_id, value in entries.items():
        if not isinstance(value, dict):
            continue
        result.append(
            (
                capture_id,
                LibraryEntry(
                    capture_id=capture_id,
                    label=_string(value.get("label"), capture_id),
                    prerelease=value.get("prerelease") is True,
                    notes=_string(value.get("notes"), ""),
                    origin=_origin(value.get("origin")),
                    added_at=_string(value.get("added_at"), ""),
                ),
            )
        )
    return result


def _origin(value: JsonValue) -> Origin:
    """An index from another version may name an origin we don't know; call that imported."""
    if value == "captured":
        return "captured"
    if value == "baseline":
        return "baseline"
    return "imported"


def _string(value: JsonValue, default: str) -> str:
    return value if isinstance(value, str) else default
